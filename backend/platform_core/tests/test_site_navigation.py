import uuid
from django.urls import reverse
from .test_authorization import portfolio
from platform_core.models import Site, Job, AuditEvent
from platform_core.permissions import can

def test_ui_and_api_have_distinct_route_names(client, portfolio):
    p = portfolio
    assert reverse('site-detail', kwargs={'pk': p['a'].pk}) == f'/sites/{p["a"].pk}/'
    assert reverse('api-site-detail', kwargs={'pk': p['a'].pk}) == f'/api/v1/sites/{p["a"].pk}/'
    client.force_login(p['owner'])
    response = client.get('/')
    assert f'href="/sites/{p["a"].pk}/"' in response.content.decode()
    assert f'href="/sites/{p["a"].pk}/edit/"' in response.content.decode()
    assert f'href="/sites/{p["a"].pk}/remove/"' in response.content.decode()
    response = client.get(reverse('site-detail', kwargs={'pk': p['a'].pk}))
    assert response['Content-Type'].startswith('text/html')
    assert 'Edit website' in response.content.decode()
    assert 'Delete from workspace' in response.content.decode()

def test_profile_save_returns_to_html_not_json(client, portfolio):
    p = portfolio
    client.force_login(p['owner'])
    response = client.post(f'/sites/{p["a"].pk}/edit/', {'name': 'Updated profile', 'url': p['a'].url,
        'environment': 'production', 'timezone': 'Asia/Colombo'}, follow=True)
    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/html')
    assert response.redirect_chain[-1][0] == f'/sites/{p["a"].pk}/'

def test_archive_requires_confirmation_and_retains_history(client, portfolio):
    p = portfolio
    client.force_login(p['owner'])
    job = Job.objects.create(site=p['a'], actor=p['owner'], idempotency_key=uuid.uuid4(), payload_hash='x'*64, target_url=p['a'].url)
    event = AuditEvent.objects.create(site=p['a'], organization=p['org'], action='fixture.history')
    path = f'/sites/{p["a"].pk}/remove/'
    assert client.get(path).status_code == 200
    p['a'].refresh_from_db()
    assert p['a'].archived_at is None
    assert client.post(path, {'confirm_name': 'wrong'}).status_code == 200
    assert client.post(path, {'confirm_name': p['a'].name}).status_code == 302
    p['a'].refresh_from_db()
    job.refresh_from_db()
    assert p['a'].archived_at and p['a'].paused
    assert job.state == 'cancelled' and job.error_code == 'site_archived'
    assert AuditEvent.objects.filter(pk=event.pk).exists()
    assert Site.objects.filter(pk=p['a'].pk).exists()
    assert not can(p['owner'], p['a'], 'run_audit')
    assert client.get(f'/sites/{p["a"].pk}/').status_code == 404
    assert client.get(f'/api/v1/sites/{p["a"].pk}/').status_code == 404
    assert client.get(f'/api/v1/jobs/{job.pk}/').status_code == 404
    assert p['a'].name in client.get('/sites/archived/').content.decode()
    assert client.get(f'/sites/{p["a"].pk}/restore/').status_code == 405
    assert client.post(f'/sites/{p["a"].pk}/restore/').status_code == 302
    p['a'].refresh_from_db()
    job.refresh_from_db()
    assert p['a'].archived_at is None and p['a'].paused
    assert job.state == 'cancelled'
    assert client.get(f'/sites/{p["a"].pk}/').status_code == 200

def test_staff_and_foreign_org_cannot_remove_or_restore(client, portfolio):
    p = portfolio
    client.force_login(p['staff'])
    assert client.get(f'/sites/{p["a"].pk}/remove/').status_code == 404
    assert client.post(f'/sites/{p["a"].pk}/remove/', {'confirm_name': p['a'].name}).status_code == 404
    assert client.get('/sites/archived/').status_code == 404
    client.force_login(p['owner'])
    assert client.get(f'/sites/{p["c"].pk}/remove/').status_code == 404
    assert client.post(f'/sites/{p["c"].pk}/restore/').status_code == 404
