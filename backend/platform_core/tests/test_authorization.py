from datetime import timedelta
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient
from platform_core.models import User, Organization, Membership, Site, SiteAssignment, SitePermissionGrant, RoleBundle, Invitation, AuditEvent
from platform_core.permissions import can, visible_sites
from platform_core.services import seed_bundles, invite
from platform_core.forms import AcceptInvitationForm, invitation_for

@pytest.fixture
def portfolio(db):
    org = Organization.objects.create(name='SYNTHETIC Agency')
    other = Organization.objects.create(name='SYNTHETIC Other Agency')
    seed_bundles(org)
    seed_bundles(other)
    staff = User.objects.create_user(username='staff', email='staff@example.test', password='Long-test-pass!7824')
    owner = User.objects.create_user(username='owner', email='owner@example.test', password='Long-test-pass!7824')
    operator = User.objects.create_superuser(username='operator', email='operator@example.test', password='Long-test-pass!7824')
    membership = Membership.objects.create(organization=org, user=staff)
    Membership.objects.create(organization=org, user=owner, role='owner')
    a = Site.objects.create(organization=org, name='SYNTHETIC Assigned', url='https://assigned.example.test')
    b = Site.objects.create(organization=org, name='SYNTHETIC Unassigned', url='https://unassigned.example.test')
    c = Site.objects.create(organization=other, name='SYNTHETIC Foreign', url='https://foreign.example.test')
    bundle = RoleBundle.objects.get(organization=org, label='Researcher')
    assignment = SiteAssignment.objects.create(membership=membership, site=a, bundle=bundle)
    return locals()

def test_staff_scope_and_action_separation(portfolio):
    p = portfolio
    assert list(visible_sites(p['staff'])) == [p['a']]
    for action in ['view_site', 'run_audit', 'edit_draft', 'submit_for_review']:
        assert can(p['staff'], p['a'], action)
    for action in ['approve_change', 'publish_change', 'rollback_change', 'manage_users', 'manage_integrations', 'manage_automation']:
        assert not can(p['staff'], p['a'], action)
    assert not p['staff'].is_staff
    assert not can(p['staff'], p['b'], 'view_site')
    assert not can(p['staff'], p['c'], 'view_site')

def test_operational_superuser_has_no_implicit_product_access(portfolio):
    assert not visible_sites(portfolio['operator']).exists()
    assert not can(portfolio['operator'], portfolio['a'], 'publish_change')

def test_owner_is_organization_scoped(portfolio):
    p = portfolio
    assert set(visible_sites(p['owner'])) == {p['a'], p['b']}
    assert can(p['owner'], p['a'], 'approve_change')
    assert not can(p['owner'], p['c'], 'publish_change')

def test_revocation_takes_effect_immediately(portfolio):
    p = portfolio
    assert can(p['staff'], p['a'], 'run_audit')
    p['membership'].active = False
    p['membership'].save()
    assert not can(p['staff'], p['a'], 'run_audit')
    assert not visible_sites(p['staff']).exists()

def test_approval_grant_does_not_grant_publication(portfolio):
    p = portfolio
    SitePermissionGrant.objects.create(assignment=p['assignment'], action='approve_change')
    assert can(p['staff'], p['a'], 'approve_change')
    assert not can(p['staff'], p['a'], 'publish_change')

def test_cross_organization_assignment_rejected(portfolio):
    p = portfolio
    with pytest.raises(ValidationError):
        SiteAssignment.objects.create(membership=p['membership'], site=p['c'], bundle=p['bundle'])

def test_foreign_bundle_rejected(portfolio):
    p = portfolio
    with pytest.raises(ValidationError):
        SiteAssignment.objects.create(membership=p['membership'], site=p['b'], bundle=RoleBundle.objects.get(organization=p['other'], label='Viewer'))

def test_api_list_and_objects_are_scoped(portfolio):
    p = portfolio
    client = APIClient()
    client.force_authenticate(p['staff'])
    response = client.get('/api/v1/sites/')
    assert response.status_code == 200
    assert [s['id'] for s in response.data['results']] == [p['a'].pk]
    for site in [p['b'], p['c']]:
        assert client.get(f'/api/v1/sites/{site.pk}/').status_code == 404
        assert client.patch(f'/api/v1/sites/{site.pk}/', {'organization': p['org'].pk}).status_code == 405
    assert 'organization' not in response.data['results'][0]

def test_browser_cross_site_and_body_ids_rejected(client, portfolio):
    p = portfolio
    client.force_login(p['staff'])
    assert client.get('/').status_code == 200
    assert client.get(f'/sites/{p["a"].pk}/').status_code == 200
    assert client.get(f'/sites/{p["b"].pk}/').status_code == 404
    assert client.get(f'/sites/{p["c"].pk}/').status_code == 404
    assert client.get(f'/sites/{p["a"].pk}/edit/').status_code == 404
    assert client.post('/staff/assign/', {'site': p['c'].pk, 'membership': p['membership'].pk, 'bundle': p['bundle'].pk}).status_code == 404
    assert client.post(f'/sites/{p["a"].pk}/pause/').status_code == 404
    assert client.get('/staff/').status_code == 404

def test_owner_body_cannot_assign_foreign_membership(client, portfolio):
    p = portfolio
    stranger = User.objects.create_user(username='stranger', email='stranger@example.test')
    foreign = Membership.objects.create(organization=p['other'], user=stranger)
    client.force_login(p['owner'])
    assert client.post('/staff/assign/', {'site': p['a'].pk, 'membership': foreign.pk, 'bundle': p['bundle'].pk}).status_code == 404

def test_unauthenticated_and_csrf(portfolio):
    client = APIClient(enforce_csrf_checks=True)
    assert client.get('/api/v1/sites/').status_code == 403
    client.force_login(portfolio['owner'])
    assert client.post('/sites/new/', {'name': 'forged'}).status_code == 403
    assert client.get('/accounts/logout/').status_code == 405

def test_invitation_is_one_time_and_stores_only_digest(db):
    organization = Organization.objects.create(name='SYNTHETIC Invitations')
    member, token = invite(organization, 'invite@example.test')
    invitation = Invitation.objects.get(membership=member)
    assert invitation.token_digest != token
    assert not member.user.is_active
    assert not member.user.has_usable_password()
    form = AcceptInvitationForm(member.user, {'new_password1': 'Unique-test-pass!42917', 'new_password2': 'Unique-test-pass!42917'})
    assert form.is_valid(), form.errors
    form.accept(token)
    assert invitation_for(token) is None
    member.user.refresh_from_db()
    assert member.user.is_active
    assert member.user.check_password('Unique-test-pass!42917')
    assert not member.user.is_staff
    with pytest.raises(ValidationError):
        form.accept(token)

def test_invitation_expiry_and_revoked_membership(db):
    org = Organization.objects.create(name='SYNTHETIC Invite expiry')
    member, token = invite(org, 'expired@example.test')
    Invitation.objects.filter(membership=member).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert invitation_for(token) is None
    member, token = invite(org, 'revoked@example.test')
    member.active = False
    member.save()
    assert invitation_for(token) is None

def test_login_audit_never_contains_password(client, portfolio):
    client.post('/accounts/login/', {'username': 'staff', 'password': 'DO-NOT-LOG-THIS'})
    assert AuditEvent.objects.filter(action='login.failed').exists()
    assert not AuditEvent.objects.filter(target__contains='DO-NOT-LOG-THIS').exists()

def test_profile_normalizes_url_and_cannot_change_organization(client, portfolio):
    p = portfolio
    client.force_login(p['owner'])
    response = client.post(f'/sites/{p["a"].pk}/edit/', {'name': 'Updated', 'url': 'https://EXAMPLE.TEST:443/',
        'environment': 'staging', 'timezone': 'Asia/Colombo', 'organization': p['other'].pk})
    assert response.status_code == 302
    p['a'].refresh_from_db()
    assert p['a'].url == 'https://example.test'
    assert p['a'].organization_id == p['org'].pk

def test_invalid_timezone_and_duplicate_url_shown_as_form_errors(client, portfolio):
    p = portfolio
    client.force_login(p['owner'])
    response = client.post('/sites/new/', {'name': 'Bad', 'url': p['a'].url, 'environment': 'staging', 'timezone': 'Asia/Colombo'})
    assert response.status_code == 200
    assert 'already exists' in response.content.decode()
    response = client.post('/sites/new/', {'name': 'Bad', 'url': 'https://timezone.example.test', 'environment': 'staging', 'timezone': 'Mars/Test'})
    assert response.status_code == 200
    assert 'IANA timezone' in response.content.decode()

def test_reference_inputs_remain_site_scoped(client, portfolio):
    from platform_core.models import ReferenceSite
    p = portfolio
    client.force_login(p['staff'])
    response = client.post(f'/sites/{p["a"].pk}/references/', {'url': 'https://REFERENCE.EXAMPLE.TEST/', 'relationship': 'competitor'})
    assert response.status_code == 302
    reference = ReferenceSite.objects.get(site=p['a'])
    assert reference.url == 'https://reference.example.test'
    assert not Site.objects.filter(url=reference.url).exists()
    assert client.post(f'/sites/{p["b"].pk}/references/', {'url': 'https://foreign.example.test', 'relationship': 'research'}).status_code == 404
    assert client.get(f'/sites/{p["c"].pk}/references/').status_code == 404

def test_reference_csv_is_atomic_and_duplicates_are_skipped(client, portfolio):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from platform_core.models import ReferenceSite
    p = portfolio
    client.force_login(p['staff'])
    url = f'/sites/{p["a"].pk}/references/'
    data = b'url,relationship\nhttps://one.example.test,competitor\nfile:///etc/passwd,research\n'
    response = client.post(url, {'operation': 'import', 'csv_file': SimpleUploadedFile('sources.csv', data)})
    assert response.status_code == 200
    assert not ReferenceSite.objects.exists()
    data = b'url,relationship\nhttps://one.example.test,competitor\nhttps://one.example.test,competitor\n'
    response = client.post(url, {'operation': 'import', 'csv_file': SimpleUploadedFile('sources.csv', data)})
    assert response.status_code == 302
    assert ReferenceSite.objects.filter(site=p['a']).count() == 1

def test_viewer_cannot_add_references(client, portfolio):
    p = portfolio
    p['assignment'].bundle = RoleBundle.objects.get(organization=p['org'], label='Viewer')
    p['assignment'].save()
    client.force_login(p['staff'])
    assert client.get(f'/sites/{p["a"].pk}/references/').status_code == 200
    assert client.post(f'/sites/{p["a"].pk}/references/', {'url': 'https://one.example.test', 'relationship': 'research'}).status_code == 404

def test_reference_csv_size_limit():
    from django.core.files.uploadedfile import SimpleUploadedFile
    from platform_core.forms import ReferenceImportForm
    form = ReferenceImportForm({}, {'csv_file': SimpleUploadedFile('large.csv', b'x' * 100_001)})
    assert not form.is_valid()
    assert '100 KB' in str(form.errors)

def test_login_throttle_blocks_password_even_when_later_correct(client, portfolio):
    for _ in range(5):
        client.post('/accounts/login/', {'username': 'staff', 'password': 'incorrect-fixture-password'})
    response = client.post('/accounts/login/', {'username': 'staff', 'password': 'Long-test-pass!7824'})
    assert response.status_code == 429
    assert 'temporarily limited' in response.content.decode()
    assert '_auth_user_id' not in client.session
