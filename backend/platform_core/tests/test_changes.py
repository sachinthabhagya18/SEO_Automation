from unittest.mock import patch
import uuid
import pytest
from django.utils import timezone
from cryptography.fernet import Fernet
from .test_authorization import portfolio
from platform_core.models import Page,KnowledgeSource,SiteConnection,Approval,SitePolicy,PublishAttempt,ChangeSet
from platform_core.connections import save_connection
from platform_core.changes import save_draft,submit,approve,enqueue_change,ChangeFailure,validate_current,digest,immutable_payload
from platform_core.publish_tasks import execute_metadata_change

@pytest.fixture
def review(portfolio,settings):
    p=portfolio
    settings.CONNECTION_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]
    settings.LOCAL_PUBLICATION_ENABLED=True;settings.CONNECTOR_LOCAL_FIXTURE_ENABLED=True
    p['a'].url='http://wordpress';p['a'].paused=False;p['a'].save()
    connection=save_connection(p['a'],p['owner'],'fixture-writer','not-a-real-secret')
    connection.status='connected';connection.capabilities={'remote_write':True,'restore':True,'metadata_write_fields':['title','description']};connection.save()
    page=Page.objects.create(site=p['a'],url='http://localhost:8081/',wordpress_id=42,title='Synthetic fixture')
    source=KnowledgeSource.objects.create(site=p['a'],url=page.url,title='Synthetic owner facts',excerpt='Synthetic example business facts.',content_hash='f'*64,source_type='owner_provided')
    baseline={'id':42,'revision':'a'*64,'stored':{'title':'Before title','description':'Before description','og_title':'','og_description':''}}
    with patch('platform_core.changes.wordpress_get',return_value=baseline):
        change=save_draft(p['a'],page,p['staff'],{'title':'After title','description':'After description'},[source],'Fixture reason')
    return {**p,'page':page,'source':source,'connection':connection,'baseline':baseline,'change':change}

def approved(p):
    submit(p['change'],p['staff']);return approve(p['change'],p['owner'])

def test_edit_revokes_approval_and_changed_payload_cannot_publish(review):
    p=review;change=approved(p)
    assert Approval.objects.filter(change=change,revoked_at__isnull=True).count()==1
    with patch('platform_core.changes.wordpress_get',return_value=p['baseline']):
        change=save_draft(p['a'],p['page'],p['staff'],{'description':'Edited description'},[p['source']],change=change)
    assert change.state=='draft'
    assert not Approval.objects.filter(change=change,revoked_at__isnull=True).exists()
    with pytest.raises(ChangeFailure): enqueue_change(change,p['owner'])

def test_self_approval_including_last_editor_forbidden(review):
    p=review;change=p['change']
    with patch('platform_core.changes.wordpress_get',return_value=p['baseline']):
        change=save_draft(p['a'],p['page'],p['owner'],{'description':'Owner edited'},[p['source']],change=change)
    submit(change,p['owner'])
    with pytest.raises(ChangeFailure,match='self_approval_forbidden'): approve(change,p['owner'])

def test_cross_site_page_and_source_rejected(review):
    p=review
    foreign=Page.objects.create(site=p['b'],url='https://unassigned.example.test/page',wordpress_id=7)
    with pytest.raises(ChangeFailure,match='cross_site'): save_draft(p['a'],foreign,p['staff'],{'title':'Bad'},[p['source']])
    source=KnowledgeSource.objects.create(site=p['b'],url=foreign.url,title='Foreign',excerpt='Foreign facts',content_hash='b'*64)
    with pytest.raises(ChangeFailure,match='cross_site'): save_draft(p['a'],p['page'],p['staff'],{'title':'Bad'},[source])

def test_evidence_or_policy_change_invalidates_approval(review):
    p=review;change=approved(p)
    p['a'].verified_facts='Changed after review';p['a'].save()
    change.refresh_from_db()
    with pytest.raises(ChangeFailure,match='business_evidence_changed'): validate_current(change)
    p['a'].verified_facts='';p['a'].save()
    change.refresh_from_db()
    policy=SitePolicy.objects.get(site=p['a']);policy.version=uuid.uuid4();policy.save()
    with pytest.raises(ChangeFailure,match='policy_or_connection_changed'): validate_current(change)

def test_real_site_write_gate_cannot_be_bypassed(review):
    p=review;change=approved(p)
    p['a'].url='https://denimyard.com';p['a'].environment='production';p['a'].save()
    change.refresh_from_db()
    with pytest.raises(ChangeFailure,match='local_fixture_write_testing_only'): enqueue_change(change,p['owner'])

def test_revoked_queued_publisher_never_calls_remote(review):
    p=review;change=approved(p);attempt=enqueue_change(change,p['owner'])
    p['owner'].is_active=False;p['owner'].save()
    with patch('platform_core.publish_tasks.wordpress_get') as remote:
        execute_metadata_change.run(str(attempt.pk))
    assert not remote.called
    attempt.refresh_from_db();assert attempt.state=='cancelled'

def test_pause_after_queue_blocks_write(review):
    p=review;attempt=enqueue_change(approved(p),p['owner'])
    p['a'].paused=True;p['a'].save()
    with patch('platform_core.publish_tasks.wordpress_request') as remote: execute_metadata_change.run(str(attempt.pk))
    assert not remote.called
    attempt.refresh_from_db();assert attempt.error_code=='site_writes_paused'

def test_stale_payload_and_wrong_approval_permission(review):
    p=review;submit(p['change'],p['staff'])
    with pytest.raises(ChangeFailure,match='approval_permission_required'): approve(p['change'],p['staff'])
    change=approve(p['change'],p['owner'])
    ChangeSet.objects.filter(pk=change.pk).update(proposed_description='Unapproved replacement')
    change.refresh_from_db()
    with pytest.raises(ChangeFailure,match='payload_changed'): enqueue_change(change,p['owner'])

def test_review_routes_scoped_and_form_ids_validated(client,review):
    p=review;client.force_login(p['staff'])
    assert client.get(f'/sites/{p["a"].pk}/changes/{p["change"].pk}/').status_code==200
    assert client.get(f'/sites/{p["b"].pk}/changes/{p["change"].pk}/').status_code==404
    assert client.post(f'/sites/{p["a"].pk}/changes/new/',{'page':999999,'change_title':'on','proposed_title':'Bad'}).status_code==200
    assert ChangeSet.objects.filter(site=p['a']).count()==1

def test_lost_apply_response_reconciles_receipt_without_second_write(review):
    p=review;change=approved(p)
    public={'status':200,'titles':['Before title'],'descriptions':['Before description'],'canonicals':['http://localhost:8081/'],'robots':['noindex']}
    ChangeSet.objects.filter(pk=change.pk).update(public_before=public)
    attempt=enqueue_change(change,p['owner'])
    receipt={'change_id':str(change.pk),'post_id':42,'state':'applied','before_revision':'a'*64,'after_revision':'c'*64,
        'before':{'title':{'value':'Before title','exists':True},'description':{'value':'Before description','exists':True}},
        'after':{'title':'After title','description':'After description','og_title':'','og_description':''}}
    after={**public,'titles':['After title'],'descriptions':['After description']}
    with (
        patch('platform_core.publish_tasks.wordpress_get',return_value=receipt),
        patch('platform_core.publish_tasks.wordpress_request') as writes,
        patch('platform_core.publish_tasks.read_public_head',return_value=after),
    ):
        execute_metadata_change.run(str(attempt.pk))
    assert not writes.called
    change.refresh_from_db();assert change.state=='verified'

def test_no_approval_when_source_evidence_missing(review):
    p=review;p['change'].sources.clear()
    with pytest.raises(ChangeFailure,match='source_evidence_required'): submit(p['change'],p['staff'])
