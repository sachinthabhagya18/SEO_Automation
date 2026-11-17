from rest_framework.test import APIClient
from platform_core.automation import issue_service_credential
from platform_core.models import SearchMetricsRun
from platform_core.permissions import can
from .test_authorization import portfolio

def test_unconfigured_google_is_explicitly_blocked_without_fabricating_a_run(portfolio,settings):
    p=portfolio;settings.SECURE_SSL_REDIRECT=False
    credential,token=issue_service_credential(p['a'],p['owner'],'search_metrics')
    client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
    r=client.post('/api/v1/automation/search-dispatch/',{'site_id':p['a'].pk,'event_id':'n8n:one'},format='json')
    assert r.status_code==200 and r.json()['state']=='blocked'
    assert r.json()['error_code']=='google_property_connection_required' and not SearchMetricsRun.objects.exists()
    assert client.post('/api/v1/automation/search-dispatch/',{'site_id':p['b'].pk,'event_id':'n8n:one'},format='json').status_code==403
    assert client.post('/api/v1/automation/research-dispatch/',{'site_id':p['a'].pk,'event_id':'n8n:one'},format='json').status_code==401
    for action in ['manage_integrations','approve_change','publish_change','rollback_change','generate_ai_draft']:
        assert not can(credential.actor,p['a'],action)
