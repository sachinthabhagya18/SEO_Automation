"""Non-login draft author. It cannot approve, publish or manage integrations."""
from celery import shared_task
from django.contrib.auth.models import Group,Permission
from django.db import transaction
from .models import User,Organization,Membership,RoleBundle,SiteAssignment,ResearchRun,ResearchProposal,AuditEvent
from .permissions import can
from .changes import ChangeFailure

@transaction.atomic
def assistant_for(site,requester):
    if not can(requester,site,'edit_draft') or not can(requester,site,'view_site'): raise ChangeFailure('draft_permission_required')
    Organization.objects.select_for_update().get(pk=site.organization_id)
    user,created=User.objects.get_or_create(username=f'system-draft-assistant-{site.organization_id}',defaults={
        'email':f'draft-assistant-{site.organization_id}@service.invalid','first_name':'Draft','last_name':'Assistant',
        'is_service_account':True,'is_active':True})
    if created: user.set_unusable_password();user.save(update_fields=['password'])
    if not user.is_service_account or not user.is_active: raise ChangeFailure('assistant_access_revoked')
    membership,new=Membership.objects.get_or_create(organization=site.organization,user=user,defaults={'role':'staff','active':True})
    if not membership.active: raise ChangeFailure('assistant_access_revoked')
    group,_=Group.objects.get_or_create(name=f'org:{site.organization_id}:Draft Assistant')
    bundle,new=RoleBundle.objects.get_or_create(organization=site.organization,label='Draft Assistant',defaults={'group':group})
    if new:
        group.permissions.set(Permission.objects.filter(content_type__app_label='platform_core',content_type__model='site',codename__in=['view_site','edit_draft','submit_for_review']))
    assignment=SiteAssignment.objects.filter(site=site,membership=membership).first()
    if not assignment:
        if AuditEvent.objects.filter(site=site,action='assistant.site_granted',target=str(user.pk)).exists():
            raise ChangeFailure('assistant_access_revoked')
        assignment=SiteAssignment.objects.create(site=site,membership=membership,bundle=bundle)
        AuditEvent.objects.create(site=site,organization=site.organization,actor=requester,action='assistant.site_granted',target=str(user.pk))
    if not can(user,site,'edit_draft'): raise ChangeFailure('assistant_access_revoked')
    return user

def enqueue_materialization(run_id):
    try:
        materialize_drafts.apply_async(args=[str(run_id)],retry=False)
        return True
    except Exception:
        return False

@shared_task(time_limit=120,soft_time_limit=110)
def materialize_drafts(run_id):
    from .research_proposals import save_proposal
    from .connections import ConnectionFailure
    run=ResearchRun.objects.select_related('site','actor').get(pk=run_id)
    if run.state!='succeeded' or not run.auto_drafts: return
    order={page['url']:index for index,page in enumerate(run.report.get('pages',[]))}
    proposals=list(run.proposals.filter(page__isnull=False,change__isnull=True))
    proposals.sort(key=lambda p:(order.get(p.url,1000),p.url))
    for proposal in proposals[:3]:
        if not can(run.actor,run.site,'edit_draft') or not can(run.actor,run.site,'view_site'):
            ResearchProposal.objects.filter(pk=proposal.pk,change__isnull=True).update(draft_error_code='requester_access_revoked')
            continue
        try:
            save_proposal(proposal.pk,run.actor,run.site,assistant=True)
        except (ChangeFailure,ConnectionFailure) as error:
            ResearchProposal.objects.filter(pk=proposal.pk,change__isnull=True).update(draft_error_code=str(error)[:80])
        except Exception:
            ResearchProposal.objects.filter(pk=proposal.pk,change__isnull=True).update(draft_error_code='draft_materialization_failed')
