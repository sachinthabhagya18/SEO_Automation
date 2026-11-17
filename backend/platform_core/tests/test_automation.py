import uuid
from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from .test_authorization import portfolio
from platform_core.automation import issue_service_credential
from platform_core.models import ServiceCredential,AuditSchedule,Job
from platform_core.tasks import audit_public_page
from platform_core.permissions import can

def authorized_client(p):
    credential,token=issue_service_credential(p['a'],p['owner'])
    client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
    return client,credential

def test_service_scope_body_validation_and_no_publication_power(portfolio):
    p=portfolio;client,credential=authorized_client(p)
    assert can(credential.actor,p['a'],'run_audit')
    assert not can(credential.actor,p['a'],'publish_change')
    assert not can(credential.actor,p['a'],'approve_change')
    assert not can(credential.actor,p['b'],'run_audit')
    assert not credential.actor.has_usable_password()
    assert client.get('/api/v1/sites/').status_code==403
    assert client.post('/api/v1/automation/audit-dispatch/',{'site_id':p['b'].pk,'event_id':'x'},format='json').status_code==403
    assert client.post('/api/v1/automation/audit-dispatch/',{'site_id':p['a'].pk,'event_id':'x','approve':True},format='json').status_code==400
    response=client.post('/api/v1/automation/audit-dispatch/',{'site_id':p['a'].pk,'event_id':'same-event'},format='json')
    assert response.status_code==202
    repeated=client.post('/api/v1/automation/audit-dispatch/',{'site_id':p['a'].pk,'event_id':'same-event'},format='json')
    assert repeated.data['job_id']==response.data['job_id']
    assert Job.objects.filter(site=p['a']).count()==1

def test_revoked_or_expired_service_cannot_dispatch_or_execute_queued_job(portfolio):
    p=portfolio;client,credential=authorized_client(p)
    response=client.post('/api/v1/automation/audit-dispatch/',{'site_id':p['a'].pk,'event_id':'revoked'},format='json')
    credential.active=False;credential.save()
    assert client.post('/api/v1/automation/dispatch-due/',{},format='json').status_code==401
    with patch('platform_core.tasks.fetch_public') as network:
        audit_public_page.run(str(response.data['job_id']))
    assert not network.called
    assert Job.objects.get(pk=response.data['job_id']).state=='cancelled'
    credential.active=True;credential.expires_at=timezone.now()-timedelta(seconds=1);credential.save()
    assert client.post('/api/v1/automation/dispatch-due/',{},format='json').status_code==401

def test_due_schedule_advances_once_and_overlap_does_not_duplicate(portfolio):
    p=portfolio;client,_=authorized_client(p)
    schedule=AuditSchedule.objects.create(site=p['a'],enabled=True,next_due=timezone.now()-timedelta(minutes=1))
    response=client.post('/api/v1/automation/dispatch-due/',{},format='json')
    assert response.status_code==200 and response.data['job_id']
    schedule.refresh_from_db()
    assert schedule.next_due>timezone.now()
    repeated=client.post('/api/v1/automation/dispatch-due/',{},format='json')
    assert repeated.data['state']=='not_due' and Job.objects.filter(site=p['a']).count()==1
    schedule.enabled=False;schedule.next_due=timezone.now()-timedelta(minutes=1);schedule.save()
    assert client.post('/api/v1/automation/dispatch-due/',{},format='json').data['state']=='not_due'

def test_automation_ui_permissions(client,portfolio):
    p=portfolio;client.force_login(p['staff'])
    assert client.get(f'/sites/{p["a"].pk}/automation/').status_code==404
    client.force_login(p['owner'])
    assert client.post(f'/sites/{p["a"].pk}/automation/',{'operation':'schedule','enabled':'on','interval_minutes':5}).status_code==200
    assert not AuditSchedule.objects.filter(site=p['a']).exists()
    assert client.post(f'/sites/{p["a"].pk}/automation/',{'operation':'schedule','enabled':'on','interval_minutes':1440}).status_code==302
