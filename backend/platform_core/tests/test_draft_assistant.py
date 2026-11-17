from unittest.mock import patch
import pytest
from platform_core.models import ResearchRun,SiteAssignment,Membership,PublishAttempt
from platform_core.research_proposals import build_proposals,save_proposal
from platform_core.draft_assistant import materialize_drafts
from platform_core.permissions import can,owner_organizations
from platform_core.changes import approve,save_draft,submit,ChangeFailure
from .test_changes import review
from .test_authorization import portfolio

def ready(p,actor=None):
    run=ResearchRun.objects.create(site=p['a'],actor=actor or p['owner'],state='succeeded',stage='review',auto_drafts=True)
    run.sources.add(p['source'])
    build_proposals(run,{'pages':[{'url':p['page'].url,'title':'Observed product','headings':[['h1','Observed product']]}]})
    return run,run.proposals.get()

def test_assistant_authors_owner_reviews_without_automatic_publication(review):
    p=review;run,proposal=ready(p)
    with patch('platform_core.changes.wordpress_get',return_value=p['baseline']):
        change=save_proposal(proposal.pk,p['owner'],p['a'],assistant=True)
    author=change.created_by
    assert author.is_service_account and not author.has_usable_password() and change.state=='pending_review'
    assert author!=p['owner'] and not can(author,p['a'],'approve_change') and not can(author,p['a'],'publish_change')
    assert approve(change,p['owner']).state=='approved'
    assert not PublishAttempt.objects.filter(change=change).exists()

def test_owner_edit_still_requires_a_different_reviewer(review):
    p=review;run,proposal=ready(p)
    with patch('platform_core.changes.wordpress_get',return_value=p['baseline']):
        change=save_proposal(proposal.pk,p['owner'],p['a'],assistant=True)
        change=save_draft(p['a'],p['page'],p['owner'],{'description':'Owner edited words'},[p['source']],change=change)
    submit(change,p['owner'])
    with pytest.raises(ChangeFailure,match='self_approval_forbidden'): approve(change,p['owner'])

def test_revoked_assistant_assignment_is_not_recreated(review):
    p=review;run,proposal=ready(p)
    with patch('platform_core.changes.wordpress_get',return_value=p['baseline']):
        change=save_proposal(proposal.pk,p['owner'],p['a'],assistant=True)
    SiteAssignment.objects.filter(site=p['a'],membership__user=change.created_by).delete()
    run,next_proposal=ready(p)
    with pytest.raises(ChangeFailure,match='assistant_access_revoked'):
        save_proposal(next_proposal.pk,p['owner'],p['a'],assistant=True)
    assert not SiteAssignment.objects.filter(site=p['a'],membership__user=change.created_by).exists()

def test_queued_assistant_drafts_recheck_requester_access(review):
    p=review;run,proposal=ready(p,p['staff'])
    p['membership'].active=False;p['membership'].save()
    with patch('platform_core.changes.wordpress_get') as http:
        materialize_drafts(str(run.pk))
    proposal.refresh_from_db()
    assert not http.called and proposal.change_id is None and proposal.draft_error_code=='requester_access_revoked'

def test_service_cannot_gain_human_powers_from_owner_membership(review):
    p=review;run,proposal=ready(p)
    with patch('platform_core.changes.wordpress_get',return_value=p['baseline']):
        change=save_proposal(proposal.pk,p['owner'],p['a'],assistant=True)
    user=change.created_by
    Membership.objects.filter(user=user,organization=p['org']).update(role='owner')
    assert not owner_organizations(user).exists()
    for action in ['approve_change','publish_change','rollback_change','manage_users','manage_integrations','manage_budgets']:
        assert not can(user,p['a'],action)
