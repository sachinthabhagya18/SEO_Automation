from unittest.mock import patch
import pytest
from platform_core.publication_scope import write_scope
from platform_core.models import Site,PublishAttempt
from platform_core.changes import safe_dispatch,enqueue_change,ChangeFailure,submit,approve
from .test_authorization import portfolio
from .test_changes import review

def stage(p,settings):
    settings.STAGING_PUBLICATION_HOSTS=('staging.denimyard.com',)
    parent=Site.objects.create(organization=p['org'],name='Main',url='https://denimyard.com',environment='production')
    site=p['a'];site.parent_site=parent;site.url='https://staging.denimyard.com';site.environment='staging';site.save()
    return site

def test_scope_requires_explicit_host_parent_and_staging(review,settings):
    site=stage(review,settings)
    assert write_scope(site)=='staging'
    site.environment='production';assert write_scope(site) is None
    site.environment='staging';site.url='https://staging.denimyard.com.attacker.example';assert write_scope(site) is None
    site.url='https://staging.denimyard.com/path';assert write_scope(site) is None
    site.url='https://staging.denimyard.com';site.parent_site=None;assert write_scope(site) is None

def test_scope_default_and_foreign_organization_refused(review,settings):
    site=stage(review,settings)
    settings.STAGING_PUBLICATION_HOSTS=();assert write_scope(site) is None
    settings.STAGING_PUBLICATION_HOSTS=('staging.denimyard.com',)
    site.parent_site=review['b'];assert write_scope(site) is None

def test_staging_queue_is_separate_and_never_approves(review,settings):
    site=stage(review,settings)
    attempt=PublishAttempt.objects.create(change=review['change'],actor=review['owner'],operation='apply')
    with patch('platform_core.publish_tasks.execute_metadata_change') as task:
        assert safe_dispatch(task,str(attempt.pk))
        assert task.apply_async.call_args.kwargs['queue']=='metadata-staging'
    review['change'].refresh_from_db()
    assert review['change'].state=='draft' and not review['change'].approvals.exists()

def test_production_guard_and_pause_still_block(review,settings):
    p=review;site=stage(p,settings);change=p['change'];change.site=site
    site.paused=True;site.save()
    with pytest.raises(ChangeFailure,match='site_writes_paused'): enqueue_change(change,p['owner'])
    site.environment='production';site.paused=False;site.save()
    with pytest.raises(ChangeFailure,match='local_fixture_write_testing_only'): enqueue_change(change,p['owner'])

def test_approve_test_rolls_back_unpause_when_draft_not_reviewable(review,settings,client):
    p=review;site=stage(p,settings);site.paused=True;site.save()
    settings.SECURE_SSL_REDIRECT=False
    client.force_login(p['owner'])
    response=client.post(f"/sites/{site.pk}/changes/{p['change'].pk}/action/",{'operation':'approve_test'})
    assert response.status_code==302
    site.refresh_from_db();p['change'].refresh_from_db()
    assert site.paused and p['change'].state=='draft'
    assert not p['change'].approvals.exists() and not p['change'].attempts.exists()

def test_existing_approved_test_can_run_while_paused_without_new_approval(review,settings,client):
    from platform_core.changes import save_draft
    p=review;site=stage(p,settings);site.paused=True;site.save()
    connection=p['connection'];connection.bound_url=site.url;connection.save()
    page=p['page'];page.url=site.url+'/product/example/';page.save()
    with patch('platform_core.changes.wordpress_get',return_value=p['baseline']):
        change=save_draft(site,page,p['staff'],{'description':'Approved test description'},[p['source']])
    submit(change,p['staff']);approve(change,p['owner'])
    settings.SECURE_SSL_REDIRECT=False;client.force_login(p['owner'])
    response=client.post(f'/sites/{site.pk}/changes/{change.pk}/action/',{'operation':'publish'})
    site.refresh_from_db();change.refresh_from_db()
    assert response.status_code==302 and not site.paused and change.state=='queued'
    assert change.approvals.count()==1 and change.attempts.count()==1
