import io
import pytest
from django.core.management import call_command, CommandError
from platform_core.models import Organization, User, Invitation
from platform_core.services import invite
from platform_core.forms import invitation_for

@pytest.mark.django_db
def test_reissue_invalidates_old_link_and_preserves_inactive_user():
    org = Organization.objects.create(name='SYNTHETIC reissue')
    member, old_token = invite(org, 'pending@example.test')
    output = io.StringIO()
    call_command('reissue_invitation', email=member.user.email, stdout=output)
    new_token = output.getvalue().strip().splitlines()[-1].split('/invitations/')[1].rstrip('/')
    assert invitation_for(old_token) is None
    assert invitation_for(new_token).membership_id == member.pk
    member.user.refresh_from_db()
    assert not member.user.is_active
    assert not member.user.has_usable_password()
    assert Invitation.objects.count() == 2

@pytest.mark.django_db
def test_reissue_refuses_active_account():
    User.objects.create_user(username='active', email='active@example.test', password='Test-only-7814')
    with pytest.raises(CommandError):
        call_command('reissue_invitation', email='active@example.test', stdout=io.StringIO())
