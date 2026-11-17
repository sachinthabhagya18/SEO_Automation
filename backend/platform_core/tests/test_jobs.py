import uuid
from unittest.mock import patch
import pytest
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from .test_authorization import portfolio
from platform_core.models import Job, PageSnapshot
from platform_core.api import create_public_audit
from platform_core.tasks import audit_public_page
from platform_core.public_http import Response

def test_durable_idempotent_submission_and_different_payload_conflict(portfolio):
    p = portfolio
    key = uuid.uuid4()
    job, created = create_public_audit(p['a'], p['staff'], key)
    repeated, second_created = create_public_audit(p['a'], p['staff'], key)
    assert created and not second_created and repeated.pk == job.pk
    p['a'].url = 'https://changed.example.test'
    p['a'].save()
    with pytest.raises(ValidationError): create_public_audit(p['a'], p['staff'], key)

def test_job_and_audit_endpoints_are_site_scoped(portfolio):
    p = portfolio
    foreign, _ = create_public_audit(p['b'], p['owner'], uuid.uuid4())
    client = APIClient()
    client.force_authenticate(p['staff'])
    response = client.post(f'/api/v1/sites/{p["a"].pk}/public-audit/', {'idempotency_key': str(uuid.uuid4()), 'site_id': p['b'].pk}, format='json')
    assert response.status_code == 400
    assert client.post(f'/api/v1/sites/{p["b"].pk}/public-audit/', {'idempotency_key': str(uuid.uuid4())}, format='json').status_code == 404
    assert client.get(f'/api/v1/jobs/{foreign.pk}/').status_code == 404
    response = client.post(f'/api/v1/sites/{p["a"].pk}/public-audit/', {'idempotency_key': str(uuid.uuid4())}, format='json')
    assert response.status_code == 202 and response.data['scope'] == 'single_public_page_head_checks'

def test_revoked_actor_job_cancelled_before_network_access(portfolio):
    p = portfolio
    job, _ = create_public_audit(p['a'], p['staff'], uuid.uuid4())
    p['membership'].active = False
    p['membership'].save()
    with patch('platform_core.tasks.fetch_public') as network:
        audit_public_page.run(str(job.pk))
    assert not network.called
    job.refresh_from_db()
    assert job.state == 'cancelled' and job.error_code == 'authorization_revoked'

def test_audit_snapshot_issues_and_duplicate_delivery(portfolio):
    p = portfolio
    job, _ = create_public_audit(p['a'], p['staff'], uuid.uuid4())
    def fixture_fetch(url, **kwargs):
        if url.endswith('/robots.txt'):
            return Response(url, 404, {}, b'')
        kwargs['before_fetch'](url)
        return Response(url, 200, {'content-type': 'text/html'}, b'<title>SYNTHETIC</title><h1>Fixture</h1>')
    with patch('platform_core.tasks.fetch_public', side_effect=fixture_fetch) as network:
        audit_public_page.run(str(job.pk))
        first_calls = network.call_count
        audit_public_page.run(str(job.pk))
        assert network.call_count == first_calls
    job.refresh_from_db()
    assert job.state == 'succeeded'
    snapshot = PageSnapshot.objects.get(job=job)
    assert snapshot.page.site_id == p['a'].pk
    assert list(snapshot.issues.values_list('code', flat=True)) == ['description_missing']

def test_robots_denial_is_failed_not_zero_issue_success(portfolio):
    p = portfolio
    job, _ = create_public_audit(p['a'], p['staff'], uuid.uuid4())
    def fixture_fetch(url, **kwargs):
        if url.endswith('/robots.txt'):
            return Response(url, 200, {}, b'User-agent: *\nDisallow: /')
        kwargs['before_fetch'](url)
        raise AssertionError('Page fetch must be denied before connection')
    with patch('platform_core.tasks.fetch_public', side_effect=fixture_fetch):
        audit_public_page.run(str(job.pk))
    job.refresh_from_db()
    assert job.state == 'failed' and job.error_code == 'robots_disallowed'
    assert not PageSnapshot.objects.filter(job=job).exists()

def test_active_job_budget(portfolio):
    p = portfolio
    for _ in range(3): create_public_audit(p['a'], p['staff'], uuid.uuid4())
    with pytest.raises(ValidationError): create_public_audit(p['a'], p['staff'], uuid.uuid4())
