from django.conf import settings
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from .models import ResearchRun, Site, Organization
from .forms import SiteForm
from .permissions import can, visible_sites, owner_organizations
from .research import enqueue_research
from django.views.decorators.http import require_POST

class URLSetupForm(forms.Form):
    url = forms.URLField(max_length=2048,assume_scheme='https',label='Website URL')

    def clean_url(self):
        validator = SiteForm(data={'url':self.cleaned_data['url']})
        validator.is_valid()
        if 'url' in validator.errors:
            raise forms.ValidationError(validator.errors['url'])
        return validator.cleaned_data['url']

@login_required
def discover(request):
    organizations = Organization.objects.filter(pk__in=owner_organizations(request.user))
    if not organizations.exists():
        raise Http404
    form=URLSetupForm(request.POST or None)
    if organizations.count()>1:
        form.fields['organization']=forms.ModelChoiceField(queryset=organizations)
    if request.method=='POST' and form.is_valid():
        from urllib.parse import urlsplit
        organization=form.cleaned_data.get('organization') or organizations.first()
        with transaction.atomic():
            site,_=Site.objects.get_or_create(organization=organization,url=form.cleaned_data['url'],defaults={
                'name':urlsplit(form.cleaned_data['url']).hostname,'environment':'production','paused':True})
            site=Site.objects.select_for_update().get(pk=site.pk)
            if not ResearchRun.objects.filter(site=site,state__in=['queued','running']).exists():
                run=ResearchRun.objects.create(site=site,actor=request.user,auto_drafts=True)
                transaction.on_commit(lambda:enqueue_research(run.pk))
        return redirect('site-research',pk=site.pk)
    return render(request,'platform/discover.html',{'form':form})

@login_required
def research(request,pk):
    site = get_object_or_404(visible_sites(request.user),pk=pk)
    if request.method == 'POST':
        if not can(request.user,site,'run_keyword_research'):
            raise Http404
        ai = request.POST.get('use_ai') == 'on'
        if ai and (not can(request.user,site,'generate_ai_draft') or not settings.RESEARCH_AI_ENABLED or not settings.GEMINI_API_KEY or not settings.GEMINI_MODEL):
            messages.error(request,'AI is disabled or not configured. Run public evidence collection without AI.')
        else:
            try:
                with transaction.atomic():
                    auto_drafts=request.POST.get('auto_drafts')=='on'
                    if auto_drafts and not can(request.user,site,'edit_draft'): raise Http404
                    run = ResearchRun.objects.create(site=site,actor=request.user,use_ai=ai,auto_drafts=auto_drafts)
                    transaction.on_commit(lambda:enqueue_research(run.pk))
                messages.success(request,'URL research queued. Refresh this page to see the result.')
            except IntegrityError:
                messages.info(request,'A research run is already queued or running for this website.')
        return redirect('site-research',pk=site.pk)
    available=site.research_runs.exclude(stage='connection_test')
    if request.GET.get('run'):
        import uuid
        try: run_id=uuid.UUID(request.GET['run'])
        except ValueError: raise Http404
        selected=get_object_or_404(available,pk=run_id)
    else:
        selected=available.first()
    from django.utils import timezone
    ai_used=ResearchRun.objects.filter(site__organization=site.organization,ai_calls__gt=0,ai_reserved_at__date=timezone.localdate()).count()
    if selected:
        from django.db.models import prefetch_related_objects
        prefetch_related_objects([selected],'proposals')
    return render(request,'platform/research.html',{'site':site,'runs':[selected] if selected else [],
        'history':available.only('id','created_at','state','stage')[:20],
        'ai_used':ai_used,'ai_model':settings.GEMINI_MODEL,'ai_enabled':settings.RESEARCH_AI_ENABLED,
        'test_copies':visible_sites(request.user).filter(parent_site=site,environment='staging'),
        'ai_configured':bool(settings.GEMINI_API_KEY and settings.GEMINI_MODEL),
        'can_research':can(request.user,site,'run_keyword_research'),
        'can_draft':can(request.user,site,'edit_draft'),
        'ai_available':ai_used<5 and settings.RESEARCH_AI_ENABLED and bool(settings.GEMINI_API_KEY and settings.GEMINI_MODEL) and can(request.user,site,'generate_ai_draft')})

@login_required
@require_POST
def proposal_draft(request,pk,proposal_id):
    from .models import ResearchProposal
    from .research_proposals import save_proposal
    from .changes import ChangeFailure
    from .connections import ConnectionFailure
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    get_object_or_404(ResearchProposal,pk=proposal_id,run__site=site)
    if not can(request.user,site,'edit_draft'): raise Http404
    try:
        change=save_proposal(proposal_id,request.user,site,assistant=request.POST.get('assistant')=='on')
    except (ChangeFailure,ConnectionFailure) as error:
        messages.error(request,str(error))
        return redirect('site-research',pk=site.pk)
    messages.success(request,'Revision-bound draft saved. Review and separate approval are still required; nothing was published.')
    return redirect('change-detail',pk=site.pk,change_id=change.pk)

@login_required
@require_POST
def proposal_test_copy(request,pk,proposal_id):
    from .research_proposals import prepare_ai_test_copy
    from .changes import ChangeFailure
    from .connections import ConnectionFailure
    source=get_object_or_404(visible_sites(request.user),pk=pk)
    from .models import ResearchProposal
    get_object_or_404(ResearchProposal,pk=proposal_id,run__site=source)
    try: target_id=int(request.POST.get('target_site',''))
    except ValueError: raise Http404
    target=get_object_or_404(visible_sites(request.user),pk=target_id,parent_site=source)
    try: change=prepare_ai_test_copy(proposal_id,request.user,source,target)
    except (ChangeFailure,ConnectionFailure):
        messages.error(request,'Could not prepare a verified test-copy draft. Check mapping, evidence, permissions and connection.')
        return redirect('site-research',pk=pk)
    messages.success(request,'AI proposal prepared for the exact test-copy URL. Review its new revision-bound diff; no approval or publication was transferred.')
    return redirect('change-detail',pk=target.pk,change_id=change.pk)
