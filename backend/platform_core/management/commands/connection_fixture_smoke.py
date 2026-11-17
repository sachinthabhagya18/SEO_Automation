import json
import sys
import uuid
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from platform_core.models import Organization, User, Membership, Site
from platform_core.connections import save_connection, check_connection, sync_inventory, ConnectionFailure

class Command(BaseCommand):
    help='Read temporary fixture credentials from stdin; test real WP HTTP auth inside a rolled-back local transaction.'

    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEBUG or not settings.CONNECTOR_LOCAL_FIXTURE_ENABLED: raise CommandError('Explicit isolated local fixture mode required.')
        credentials=json.loads(sys.stdin.read(4096))
        org=Organization.objects.create(name='SYNTHETIC temporary connector smoke')
        key=uuid.uuid4().hex
        user=User.objects.create(username='fixture-'+key,email=key+'@example.test')
        user.set_unusable_password();user.save()
        Membership.objects.create(organization=org,user=user,role='owner')
        site=Site.objects.create(organization=org,name='SYNTHETIC temporary WP connection',url='http://wordpress')
        try:
            connection=save_connection(site,user,credentials['username'],credentials['password'])
            report=check_connection(site,user)
            count=sync_inventory(site,user)
            if report.get('remote_write') is not False or count<1: raise ValueError('Unexpected fixture capabilities or empty inventory')
            transaction.set_rollback(True)
            self.stdout.write(f'WP HTTP Application Password authentication, encrypted storage, capabilities and {count} public inventory records verified. Temporary app records rolled back.')
        except ConnectionFailure as error:
            raise CommandError('Fixture connection failed: '+str(error)) from None
        except Exception:
            raise CommandError('Fixture connection failed; no credentials are printed. Check local WP REST routing/authentication.') from None
