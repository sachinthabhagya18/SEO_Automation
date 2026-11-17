import hashlib
import secrets
from datetime import timedelta
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils import timezone
from .models import User, Membership, RoleBundle, Invitation, AuditEvent

BUNDLES = {
    'Researcher': ['view_site', 'run_audit', 'manage_reference_sites', 'run_keyword_research', 'generate_ai_draft', 'edit_draft', 'submit_for_review'],
    'Content Editor': ['view_site', 'run_audit', 'generate_ai_draft', 'edit_draft', 'submit_for_review', 'edit_keyword_map'],
    'Reviewer': ['view_site', 'approve_change', 'view_analytics'],
    'Viewer': ['view_site', 'view_analytics'],
}

def seed_bundles(organization):
    for label, actions in BUNDLES.items():
        group, _ = Group.objects.get_or_create(name=f'org:{organization.pk}:{label}')
        bundle, created = RoleBundle.objects.get_or_create(organization=organization, label=label, defaults={'group': group})
        if created:
            bundle.group.permissions.set(Permission.objects.filter(content_type__app_label='platform_core', content_type__model='site', codename__in=actions))

@transaction.atomic
def invite(organization, email, role=Membership.Role.STAFF, actor=None):
    # Invitations never attach an existing account to a new organization implicitly.
    email = email.strip().lower()
    user = User(username=email, email=email, is_active=False)
    user.set_unusable_password()
    user.full_clean()
    user.save()
    membership = Membership.objects.create(organization=organization, user=user, role=role)
    token = secrets.token_urlsafe(48)
    Invitation.objects.create(membership=membership, token_digest=hashlib.sha256(token.encode()).hexdigest(), expires_at=timezone.now() + timedelta(hours=24))
    AuditEvent.objects.create(organization=organization, actor=actor, action='invitation.created', target=str(user.pk))
    return membership, token
