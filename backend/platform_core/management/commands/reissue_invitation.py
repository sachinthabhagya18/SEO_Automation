import hashlib
import secrets
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from platform_core.models import User, Membership, Invitation, AuditEvent

class Command(BaseCommand):
    help = 'Reissue password setup only for an inactive, unactivated invited account. Never resets an active account.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        user = User.objects.select_for_update().filter(email__iexact=options['email'].strip()).first()
        if not user or user.is_active or user.has_usable_password():
            raise CommandError('Only an inactive invited account without a configured password can be reissued.')
        member = Membership.objects.filter(user=user, active=True).first()
        if not member or not Invitation.objects.filter(membership=member, accepted_at__isnull=True).exists():
            raise CommandError('No pending invitation exists for this account.')
        now = timezone.now()
        Invitation.objects.filter(membership=member, accepted_at__isnull=True).update(expires_at=now)
        token = secrets.token_urlsafe(48)
        Invitation.objects.create(membership=member, token_digest=hashlib.sha256(token.encode()).hexdigest(),
                                  expires_at=now + timedelta(hours=24))
        AuditEvent.objects.create(organization=member.organization, action='invitation.reissued', target=str(user.pk))
        self.stdout.write('Private one-time setup link; previous links are expired. Valid for 24 hours:')
        self.stdout.write(f'http://localhost:8000/invitations/{token}/')
