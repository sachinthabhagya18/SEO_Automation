from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from platform_core.models import Organization, Membership
from platform_core.services import invite, seed_bundles

class Command(BaseCommand):
    help = 'Create the first company owner and print a one-time local password setup URL. Does not create a Django superuser.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--company', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        # Serialize first-owner bootstrap without relying on a race-prone exists check.
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(782430120)')
        if Organization.objects.exists():
            raise CommandError('Organization already initialized. Use the existing owner account.')
        try:
            validate_email(options['email'])
            organization = Organization.objects.create(name=options['company'])
            seed_bundles(organization)
            _, token = invite(organization, options['email'], role=Membership.Role.OWNER)
        except ValidationError as error:
            raise CommandError(str(error))
        self.stdout.write('Private, single-use link (expires in 24 hours). Do not share or commit:')
        self.stdout.write(f'http://localhost:8000/invitations/{token}/')
