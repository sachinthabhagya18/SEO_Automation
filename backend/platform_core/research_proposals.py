"""Page-specific suggestions, followed by explicit revision-bound draft creation."""
import re
from django.db import transaction
from .models import Page,ResearchProposal
from .changes import save_draft,ChangeFailure,validate_text
from .permissions import can

def plain(value,limit):
    return re.sub(r'\s+',' ',re.sub(r'[\x00-\x1f\x7f<>]',' ',str(value))).strip()[:limit]

def build_proposals(run,report):
    ai={d['page_url']:d for d in report.get('profile_suggestions',{}).get('metadata_drafts',[])}
    for evidence in report['pages']:
        url=evidence['url']
        page=Page.objects.filter(site=run.site,url=url,wordpress_id__isnull=False).first()
        suggestion=ai.get(url)
        if suggestion:
            values={'title':suggestion['title'],'description':suggestion['description']}
            provider='gemini-page-v1';reason=suggestion['reason'];source_urls=suggestion['source_urls']
        else:
            headings=evidence.get('headings',[])
            label=next((text for tag,text in headings if tag=='h1' and text.strip()),evidence.get('title') or (page.title if page else ''))
            label=plain(label,120)
            if not label: continue
            values={'title':plain(evidence.get('title') or label,200),
                'description':plain(f'Explore {label}. Review '+('product details before ordering.' if page and page.post_type=='product' else 'the page details for more information.'),500)}
            provider='deterministic-page-v1'
            reason='Rule-based starting wording from this page, not AI output. Review relevance and all factual claims before submission.'
            source_urls=[url]
        validate_text(values)
        proposal,created=ResearchProposal.objects.get_or_create(run=run,url=url,defaults={
            'page':page,'title':values['title'],'description':values['description'],'reason':reason,'provider':provider})
        if created: proposal.sources.set(run.sources.filter(url__in=source_urls))

@transaction.atomic
def save_proposal(proposal_id,actor,site,assistant=False):
    proposal=ResearchProposal.objects.select_for_update(of=('self',)).select_related('run','change','page').get(pk=proposal_id,run__site=site)
    if not can(actor,site,'edit_draft') or not can(actor,site,'view_site'):
        raise ChangeFailure('draft_permission_required')
    if proposal.change_id: return proposal.change
    if proposal.run.state!='succeeded': raise ChangeFailure('completed_research_required')
    # A current inventory mapping is required; category/homepage URLs cannot
    # silently be sent to another WordPress object.
    page=Page.objects.filter(site=site,url=proposal.url,wordpress_id__isnull=False).first()
    if not page: raise ChangeFailure('page_inventory_mapping_required')
    sources=list(proposal.sources.filter(site=site))
    if not sources or not any(s.url==proposal.url for s in sources):
        raise ChangeFailure('page_source_evidence_required')
    author=actor
    if assistant:
        from .draft_assistant import assistant_for
        author=assistant_for(site,actor)
    change=save_draft(site,page,author,{'title':proposal.title,'description':proposal.description},sources,
        proposal.reason,provider=proposal.provider)
    proposal.page=page;proposal.change=change;proposal.draft_error_code='';proposal.save(update_fields=['page','change','draft_error_code'])
    if assistant:
        from .models import AuditEvent
        from .changes import submit
        submit(change,author)
        change.refresh_from_db()
        AuditEvent.objects.create(site=site,organization=site.organization,actor=actor,action='change.assistant_draft_requested',target=str(change.pk))
    return change

@transaction.atomic
def prepare_ai_test_copy(proposal_id,actor,source_site,target_site):
    """Prepare a new target-bound draft; approvals never cross environments."""
    from urllib.parse import urlsplit,urlunsplit
    from .models import ResearchRun,KnowledgeSource,AuditEvent,ChangeSet
    from .owned_http import site_fetch
    from .tasks import allowed_by_robots
    from .evidence import extract
    import hashlib
    if source_site.environment!='production' or target_site.parent_site_id!=source_site.pk or target_site.organization_id!=source_site.organization_id \
        or target_site.environment!='staging' or not can(actor,source_site,'view_site') or not can(actor,target_site,'edit_draft'):
        raise ChangeFailure('related_test_copy_permission_required')
    proposal=ResearchProposal.objects.select_for_update(of=('self',)).select_related('run').get(pk=proposal_id,run__site=source_site)
    accepted=proposal.run.report.get('profile_suggestions',{}).get('metadata_drafts',[])
    if proposal.provider!='gemini-page-v1' or proposal.run.report.get('ai_status')!='succeeded' or not any(
        p.get('page_url')==proposal.url and p.get('title')==proposal.title and p.get('description')==proposal.description for p in accepted):
        raise ChangeFailure('validated_ai_proposal_required')
    prefix=str(proposal.pk)+':'
    previous=AuditEvent.objects.filter(site=target_site,action='change.ai_test_copy_prepared',target__startswith=prefix).first()
    if previous:
        existing=ChangeSet.objects.filter(pk=previous.target.split(':')[-1],site=target_site).first()
        if existing: return existing
    original=urlsplit(proposal.url);base=urlsplit(source_site.url);target=urlsplit(target_site.url)
    if (original.scheme,original.netloc)!=(base.scheme,base.netloc) or base.path not in ('','/') or target.path not in ('','/'):
        raise ChangeFailure('test_copy_url_mapping_required')
    url=urlunsplit((target.scheme,target.netloc,original.path or '/','',''))
    page=Page.objects.filter(site=target_site,url=url,wordpress_id__isnull=False).first()
    if not page or not allowed_by_robots(url,site=target_site): raise ChangeFailure('verified_test_page_mapping_required')
    response=site_fetch(target_site,url,max_bytes=500_000,max_redirects=0)
    if response.status!=200 or 'text/html' not in response.headers.get('content-type','').lower():
        raise ChangeFailure('test_page_html_required')
    evidence=extract(url,response.body.decode('utf-8',errors='replace'))
    actor.refresh_from_db(fields=['is_active','is_service_account'])
    if not can(actor,source_site,'view_site') or not can(actor,target_site,'edit_draft'):
        raise ChangeFailure('related_test_copy_permission_required')
    source=KnowledgeSource.objects.create(site=target_site,url=url,title=(evidence.titles or [page.title])[0],
        excerpt=' '.join(evidence.text)[:4000],content_hash=hashlib.sha256(response.body).hexdigest(),source_type='public_observation')
    run=ResearchRun.objects.create(site=target_site,actor=actor,state='succeeded',stage='review',report={
        'coverage':'Prepared from a validated source-site Gemini proposal and fresh test-page evidence; no new AI call.',
        'origin_run_id':str(proposal.run_id),'origin_proposal_id':str(proposal.pk),'origin_url':proposal.url})
    run.sources.add(source)
    copy=ResearchProposal.objects.create(run=run,page=page,url=url,title=proposal.title,description=proposal.description,
        reason=f'Gemini proposal from {proposal.url}; original run {proposal.run_id}. Review this separate test target. No approval transferred.',provider=proposal.provider)
    copy.sources.add(source)
    change=save_proposal(copy.pk,actor,target_site,assistant=True)
    AuditEvent.objects.create(site=target_site,organization=target_site.organization,actor=actor,action='change.ai_test_copy_prepared',target=prefix+str(change.pk))
    return change
