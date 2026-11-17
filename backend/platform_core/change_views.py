from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404,JsonResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from .models import ChangeSet,Page
from .permissions import visible_sites,can
from .forms import MetadataDraftForm
from .changes import save_draft,submit,approve,enqueue_change,retry_public_verification,ChangeFailure
from .connections import ConnectionFailure

@login_required
def draft_list(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    from django.core.paginator import Paginator
    states=[('','All drafts'),('pending_review','Needs review'),('approved','Approved'),('verified','Verified'),('stale_conflict','Conflict')]
    selected=request.GET.get('state','')
    if selected not in dict(states): selected=''
    changes=ChangeSet.objects.filter(site=site).select_related('page')
    if selected: changes=changes.filter(state=selected)
    return render(request,'platform/changes.html',{'site':site,'state':selected,'state_choices':states,
        'can_create':can(request.user,site,'edit_draft'),'page_obj':Paginator(changes,25).get_page(request.GET.get('page'))})

@login_required
def draft_edit(request,pk,change_id=None):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    if not can(request.user,site,'edit_draft'): raise Http404
    change=get_object_or_404(ChangeSet,pk=change_id,site=site) if change_id else None
    if change and change.state not in ('draft','pending_review','approved','rejected','stale_conflict'): raise Http404
    if change:
        initial={'page':change.page_id,'change_title':change.change_title,'proposed_title':change.proposed_title,
            'change_description':change.change_description,'proposed_description':change.proposed_description,
            'sources':list(change.sources.values_list('pk',flat=True)),'reason':change.reason}
    else:
        categories=', '.join(line.strip() for line in site.services.splitlines() if line.strip())[:120]
        initial={'change_title':False,'change_description':True,
            'proposed_title':f'{site.name} | {categories}'[:200] if categories else site.name,
            'proposed_description':f'Explore {categories or "our collections"} at {site.name}. View product details and available options before ordering.'[:500],
            'sources':list(site.knowledge_sources.filter(source_type='owner_provided').values_list('pk',flat=True)[:10]),
            'reason':'Rule-based starting suggestion from the site profile; review facts and wording before submitting. Not AI-generated.'}
    form=MetadataDraftForm(request.POST or None,site=site,initial=initial)
    if request.method=='POST' and form.is_valid():
        data=form.cleaned_data
        values={key:value for flag,key,value in [(data['change_title'],'title',data['proposed_title']),
            (data['change_description'],'description',data['proposed_description'])] if flag}
        try:
            saved=save_draft(site,data['page'],request.user,values,list(data['sources']),data['reason'],change)
        except (ChangeFailure,ConnectionFailure) as error: form.add_error(None,str(error))
        else:
            messages.success(request,'Draft saved with the current WordPress revision. Nothing was published.')
            return redirect('change-detail',pk=site.pk,change_id=saved.pk)
    return render(request,'platform/change_form.html',{'site':site,'change':change,'form':form,
        'preview_data':{'site_id':site.pk,'mode':'edit' if change else 'new','url':change.page.url if change else site.url,
            'title':(change.base_metadata.get('title') or change.page.title) if change else site.name,
            'description':change.base_metadata.get('description','') if change else '', 'image_url':'',
            'base_page_id':str(change.page_id) if change else '',
            'page_urls':{str(p.pk):p.url for p in form.fields['page'].queryset},
            'page_titles':{str(p.pk):p.title for p in form.fields['page'].queryset}}})

@login_required
def draft_detail(request,pk,change_id):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    change=get_object_or_404(ChangeSet.objects.select_related('page','created_by','last_edited_by'),pk=change_id,site=site)
    from .publication_scope import write_scope
    scope=write_scope(site)
    from .changes import policy_for
    self_review=policy_for(site).forbid_self_approval and request.user.pk in (change.created_by_id,change.last_edited_by_id)
    return render(request,'platform/change.html',{'site':site,'change':change,'write_scope':scope,
        'self_review':self_review,'attempts':change.attempts.all(),
        'can_test':not self_review and scope=='staging' and can(request.user,site,'approve_change') and can(request.user,site,'publish_change') and can(request.user,site,'manage_automation'),
        'can_edit':can(request.user,site,'edit_draft'),'can_submit':can(request.user,site,'submit_for_review'),
        'can_approve':not self_review and can(request.user,site,'approve_change'),'can_publish':bool(scope) and can(request.user,site,'publish_change'),
        'can_restore':bool(scope) and can(request.user,site,'rollback_change')})

@login_required
def draft_status(request,pk,change_id):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    change=get_object_or_404(ChangeSet,pk=change_id,site=site)
    response=JsonResponse({'state':change.state,'error_code':change.error_code})
    response['Cache-Control']='private, no-store'
    return response

@login_required
@require_POST
def draft_action(request,pk,change_id):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    change=get_object_or_404(ChangeSet,pk=change_id,site=site)
    operation=request.POST.get('operation')
    try:
        if operation=='submit': submit(change,request.user);messages.success(request,'Submitted for human review.')
        elif operation=='approve': approve(change,request.user);messages.success(request,'Approval saved against this exact payload/revision/policy.')
        elif operation=='approve_test':
            from django.db import transaction
            from .models import Site,AuditEvent
            from .publication_scope import write_scope
            with transaction.atomic():
                target=Site.objects.select_for_update().get(pk=site.pk)
                if write_scope(target)!='staging' or not can(request.user,target,'manage_automation'):
                    raise ChangeFailure('approved_staging_target_required')
                target.paused=False;target.save(update_fields=['paused'])
                approved=approve(change,request.user)
                enqueue_change(approved,request.user)
                AuditEvent.objects.create(site=target,organization=target.organization,actor=request.user,action='staging.test_authorized',target=str(change.pk))
            messages.success(request,'Approved this draft and queued the protected test copy only. The production site is unchanged.')
        elif operation=='reject':
            if not can(request.user,site,'approve_change'): raise ChangeFailure('approval_permission_required')
            from django.db import transaction
            from django.utils import timezone
            from .models import AuditEvent
            with transaction.atomic():
                current=ChangeSet.objects.select_for_update().get(pk=change.pk)
                if current.state!='pending_review': raise ChangeFailure('pending_review_required')
                current.state='rejected';current.save(update_fields=['state'])
                current.approvals.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
                AuditEvent.objects.create(site=site,organization=site.organization,actor=request.user,action='change.rejected',target=str(change.pk))
            messages.success(request,'Draft rejected. Nothing was published.')
        elif operation in ('publish','restore'):
            if operation=='publish' and site.paused:
                from django.db import transaction
                from .models import Site
                from .publication_scope import write_scope
                with transaction.atomic():
                    target=Site.objects.select_for_update().get(pk=site.pk)
                    if write_scope(target)!='staging' or not can(request.user,target,'manage_automation'):
                        raise ChangeFailure('site_writes_paused')
                    target.paused=False;target.save(update_fields=['paused'])
                    enqueue_change(change,request.user,'apply')
            else:
                enqueue_change(change,request.user,'apply' if operation=='publish' else 'restore')
            messages.success(request,'Test-target operation queued. Production writes are disabled.')
        elif operation=='verify':
            retry_public_verification(change,request.user)
            messages.success(request,'Public verification rechecked without another write.')
        else: raise ChangeFailure('unsupported_action')
    except (ChangeFailure,ConnectionFailure) as error: messages.error(request,str(error))
    return redirect('change-detail',pk=pk,change_id=change_id)
