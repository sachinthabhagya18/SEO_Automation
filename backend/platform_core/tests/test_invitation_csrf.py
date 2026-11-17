import pytest
from django.test import Client
from platform_core.models import Organization
from platform_core.services import invite
from platform_core.forms import invitation_for

@pytest.mark.django_db
@pytest.mark.parametrize('secure', [False, True])
def test_invitation_accepts_valid_same_origin_browser_post(secure):
    org = Organization.objects.create(name='SYNTHETIC CSRF browser')
    member, token = invite(org, 'browser@example.test')
    client = Client(enforce_csrf_checks=True)
    path = f'/invitations/{token}/'
    response = client.get(path, secure=secure, HTTP_HOST='localhost:8000')
    assert response.status_code == 200
    assert response['Referrer-Policy'] == 'strict-origin'
    assert 'no-store' in response['Cache-Control']
    origin = ('https' if secure else 'http') + '://localhost:8000'
    response = client.post(path, {'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        'new_password1': 'Synthetic-browser-pass!9182', 'new_password2': 'Synthetic-browser-pass!9182'},
        secure=secure, HTTP_HOST='localhost:8000', HTTP_ORIGIN=origin)
    assert response.status_code == 302
    member.user.refresh_from_db()
    assert member.user.is_active
    assert invitation_for(token) is None

@pytest.mark.django_db
def test_null_origin_still_denied_and_invitation_not_consumed():
    org = Organization.objects.create(name='SYNTHETIC null origin')
    member, token = invite(org, 'opaque@example.test')
    client = Client(enforce_csrf_checks=True)
    path = f'/invitations/{token}/'
    client.get(path, HTTP_HOST='localhost:8000')
    response = client.post(path, {'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        'new_password1': 'Synthetic-browser-pass!9182', 'new_password2': 'Synthetic-browser-pass!9182'},
        HTTP_HOST='localhost:8000', HTTP_ORIGIN='null')
    assert response.status_code == 403
    assert invitation_for(token) is not None
    member.user.refresh_from_db()
    assert not member.user.is_active

@pytest.mark.django_db
def test_https_post_with_origin_only_referer_accepts_valid_csrf():
    org = Organization.objects.create(name='SYNTHETIC secure referrer')
    _, token = invite(org, 'referer@example.test')
    client = Client(enforce_csrf_checks=True)
    path = f'/invitations/{token}/'
    client.get(path, secure=True, HTTP_HOST='localhost:8000')
    response = client.post(path, {'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        'new_password1': 'Synthetic-browser-pass!9182', 'new_password2': 'Synthetic-browser-pass!9182'},
        secure=True, HTTP_HOST='localhost:8000', HTTP_REFERER='https://localhost:8000/')
    assert response.status_code == 302
