from unittest.mock import patch
from rest_framework.test import APIClient
from platform_core.automation import issue_service_credential
from platform_core.models import ResearchRun
from platform_core.permissions import can
from .test_authorization import portfolio

def client_for(token):
    client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
    return client

def test_scopes_are_separate_and_rotation_preserves_audit(portfolio,settings):
    settings.SECURE_SSL_REDIRECT=False;p=portfolio
    audit,at=issue_service_credential(p['a'],p['owner'])
    research,rt=issue_service_credential(p['a'],p['owner'],'research_drafts')
    audit.refresh_from_db();assert audit.active
    assert client_for(at).post('/api/v1/automation/research-dispatch/',{'site_id':p['a'].pk,'event_id':'one'},format='json').status_code==401
    assert client_for(rt).post('/api/v1/automation/audit-dispatch/',{'site_id':p['a'].pk,'event_id':'one'},format='json').status_code==401
    for action in ['approve_change','publish_change','rollback_change','manage_automation','manage_users']:
        assert not can(research.actor,p['a'],action)

def test_dispatch_deduplicates_and_cannot_change_target(portfolio,settings):
    settings.SECURE_SSL_REDIRECT=False;p=portfolio
    credential,token=issue_service_credential(p['a'],p['owner'],'research_drafts');client=client_for(token)
    data={'site_id':p['a'].pk,'event_id':'n8n:1','use_ai':False}
    with patch('platform_core.research_automation.enqueue_research'):
        first=client.post('/api/v1/automation/research-dispatch/',data,format='json')
        second=client.post('/api/v1/automation/research-dispatch/',data,format='json')
    assert first.status_code==202 and first.json()['run_id']==second.json()['run_id']
    assert ResearchRun.objects.count()==1
    assert client.post('/api/v1/automation/research-dispatch/',{**data,'site_id':p['b'].pk},format='json').status_code==403
    assert client.post('/api/v1/automation/research-dispatch/',{**data,'approve':True},format='json').status_code==400

def test_revoked_credential_cannot_run_queued_research_or_read_foreign_run(portfolio,settings):
    settings.SECURE_SSL_REDIRECT=False;p=portfolio
    credential,token=issue_service_credential(p['a'],p['owner'],'research_drafts')
    foreign=ResearchRun.objects.create(site=p['b'],actor=p['owner'])
    assert client_for(token).get(f'/api/v1/automation/research/{foreign.pk}/').status_code==404
    run=ResearchRun.objects.create(site=p['a'],actor=credential.actor)
    credential.active=False;credential.save()
    from platform_core.research import research_site
    with patch('platform_core.research.collect') as collect: research_site(str(run.pk))
    run.refresh_from_db();assert run.state=='cancelled' and not collect.called
