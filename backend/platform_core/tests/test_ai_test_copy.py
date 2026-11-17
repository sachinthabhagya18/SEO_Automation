from types import SimpleNamespace
from unittest.mock import patch
import pytest
from platform_core.models import ResearchRun,ResearchProposal,Page
from platform_core.connections import save_connection
from platform_core.research_proposals import prepare_ai_test_copy
from platform_core.changes import ChangeFailure
from .test_authorization import portfolio
from .test_changes import review

def setup(p):
    source=p['a'];source.environment='production';source.save()
    target=p['b'];target.parent_site=source;target.environment='staging';target.save()
    connection=save_connection(target,p['owner'],'synthetic-reader','synthetic-only-secret');connection.status='connected';connection.save()
    page=Page.objects.create(site=target,url=target.url+'/',wordpress_id=0,target_kind='home',title='Test home')
    draft={'page_url':source.url+'/','title':'Validated Gemini title','description':'Evidence-based description.','source_urls':[source.url+'/']}
    run=ResearchRun.objects.create(site=source,actor=p['owner'],state='succeeded',report={'ai_status':'succeeded','profile_suggestions':{'metadata_drafts':[draft]}})
    proposal=ResearchProposal.objects.create(run=run,url=draft['page_url'],title=draft['title'],description=draft['description'],provider='gemini-page-v1')
    return source,target,proposal

def test_ai_proposal_prepares_exact_home_target_without_transferring_approval(review):
    p=review;source,target,proposal=setup(p)
    response=SimpleNamespace(status=200,headers={'content-type':'text/html'},body=b'<title>Test home</title><h1>Observed home</h1>')
    with patch('platform_core.tasks.allowed_by_robots',return_value=True),patch('platform_core.owned_http.site_fetch',return_value=response),patch('platform_core.changes.wordpress_get',return_value={**p['baseline'],'id':0}):
        change=prepare_ai_test_copy(proposal.pk,p['owner'],source,target)
        replay=prepare_ai_test_copy(proposal.pk,p['owner'],source,target)
    assert change.pk==replay.pk and change.site==target and change.page.target_kind=='home'
    assert change.state=='pending_review' and change.provider=='gemini-page-v1' and change.created_by.is_service_account
    assert not change.approvals.exists() and not change.attempts.exists()
    assert change.sources.get().url==target.url+'/'

def test_unvalidated_modified_proposal_cannot_be_labelled_ai(review):
    p=review;source,target,proposal=setup(p)
    proposal.title='Manually changed words';proposal.save()
    with pytest.raises(ChangeFailure,match='validated_ai_proposal_required'):
        prepare_ai_test_copy(proposal.pk,p['owner'],source,target)

def test_unrelated_target_cannot_receive_source_proposal(review):
    p=review;source,target,proposal=setup(p);target.parent_site=None
    with pytest.raises(ChangeFailure,match='related_test_copy_permission_required'):
        prepare_ai_test_copy(proposal.pk,p['owner'],source,target)
