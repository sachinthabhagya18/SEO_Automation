from unittest.mock import patch
import pytest
from django.urls import reverse
from platform_core.models import ResearchRun,ResearchProposal
from platform_core.research_proposals import build_proposals,save_proposal
from platform_core.changes import ChangeFailure
from .test_authorization import portfolio
from .test_changes import review

def proposal_for(p):
    run=ResearchRun.objects.create(site=p['a'],actor=p['staff'],state='succeeded',stage='review')
    run.sources.add(p['source'])
    report={'pages':[{'url':p['page'].url,'title':'Synthetic product','headings':[['h1','Synthetic item']]}]}
    build_proposals(run,report)
    return run.proposals.get(),report

def test_page_proposals_are_idempotent_and_labelled(review):
    p=review;proposal,report=proposal_for(p)
    build_proposals(proposal.run,report)
    assert proposal.run.proposals.count()==1
    assert proposal.provider=='deterministic-page-v1' and proposal.page==p['page']
    assert 'not AI output' in proposal.reason and proposal.sources.count()==1

def test_save_proposal_binds_revision_and_is_idempotent(review):
    p=review;proposal,_=proposal_for(p)
    with patch('platform_core.changes.wordpress_get',return_value=p['baseline']) as http:
        change=save_proposal(proposal.pk,p['staff'],p['a'])
        again=save_proposal(proposal.pk,p['staff'],p['a'])
    assert change.pk==again.pk and http.call_count==1
    assert change.state=='draft' and change.base_revision=='a'*64
    assert change.sources.get()==p['source'] and not change.approvals.exists()

def test_unmapped_page_is_never_sent_to_another_object(review):
    p=review;proposal,_=proposal_for(p)
    proposal.url='https://example.test/product-category/test/';proposal.page=None;proposal.save()
    with patch('platform_core.changes.wordpress_get') as http:
        with pytest.raises(ChangeFailure,match='page_inventory_mapping_required'):
            save_proposal(proposal.pk,p['staff'],p['a'])
    assert not http.called

def test_proposal_routes_scope_and_permissions(client,review):
    p=review;proposal,_=proposal_for(p)
    client.force_login(p['owner'])
    assert client.post(reverse('proposal-draft',kwargs={'pk':p['c'].pk,'proposal_id':proposal.pk})).status_code==404
    p['membership'].active=False;p['membership'].save()
    client.force_login(p['staff'])
    assert client.post(reverse('proposal-draft',kwargs={'pk':p['a'].pk,'proposal_id':proposal.pk})).status_code==404

def test_proposal_requires_page_source(review):
    p=review;proposal,_=proposal_for(p);proposal.sources.clear()
    with pytest.raises(ChangeFailure,match='page_source_evidence_required'):
        save_proposal(proposal.pk,p['staff'],p['a'])

def test_gemini_page_proposal_keeps_provider_and_reason(review):
    p=review;proposal,report=proposal_for(p)
    proposal.delete()
    report['profile_suggestions']={'metadata_drafts':[{'page_url':p['page'].url,'title':'AI proposal',
        'description':'Evidence-backed draft for review.','source_urls':[p['source'].url],'reason':'Observed page evidence.'}]}
    run=ResearchRun.objects.get(pk=proposal.run_id)
    build_proposals(run,report)
    result=run.proposals.get()
    assert result.provider=='gemini-page-v1' and result.reason=='Observed page evidence.'

def test_generation_probe_cannot_bypass_daily_allowance(settings,portfolio):
    from django.core.management import call_command
    from django.utils import timezone
    from io import StringIO
    p=portfolio;settings.RESEARCH_AI_ENABLED=True;settings.GEMINI_API_KEY='synthetic';settings.GEMINI_MODEL='synthetic-model'
    for _ in range(5):
        ResearchRun.objects.create(site=p['a'],actor=p['owner'],state='succeeded',ai_calls=1,ai_reserved_at=timezone.now())
    output=StringIO()
    with patch('platform_core.management.commands.check_gemini.httpx.Client') as metadata,patch('platform_core.management.commands.check_gemini.request_json') as provider:
        metadata.return_value.__enter__.return_value.get.return_value.status_code=200
        call_command('check_gemini',site=p['a'].pk,generate=True,stdout=output)
    assert not provider.called and 'ai_budget_exhausted' in output.getvalue()

def test_ai_page_draft_requires_its_own_page_evidence(settings,portfolio):
    import json
    from platform_core.research_ai import suggest_profile,ProfileFailure
    settings.RESEARCH_AI_ENABLED=True;settings.GEMINI_API_KEY='synthetic';settings.GEMINI_MODEL='synthetic'
    url=portfolio['a'].url
    output={'suggestions':[],'uncertainties':[],'metadata_drafts':[{'page_url':'https://invented.test/',
        'title':'Wrong page','description':'Unbacked content','source_urls':[url],'reason':'Guess'}]}
    with patch('platform_core.research_ai.request_json',return_value=json.dumps(output)):
        with pytest.raises(ProfileFailure):
            suggest_profile(portfolio['a'],[{'url':url,'title':'Source','headings':[],'excerpt':'Observed source'}])
