"""Explicit fixed test-copy writer binding. Never creates approvals or publishes."""
import json,sys
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from platform_core.models import Site,Membership,AuditEvent
from platform_core.connections import save_connection

class Command(BaseCommand):
    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)

    @transaction.atomic
    def handle(self,**options):
        try:
            data=json.loads(sys.stdin.read(32001));account=data['connector_accounts']['editor']
            if data['url']!='https://staging.denimyard.com' or account['username']!='seo-staging-editor' or not 16<=len(account['application_password'])<=100: raise ValueError()
        except (ValueError,TypeError,KeyError): raise CommandError('Invalid test-copy writer envelope; values suppressed.') from None
        site=Site.objects.select_for_update().get(pk=options['site'])
        from platform_core.publication_scope import write_scope
        if write_scope(site)!='staging' or site.url!='https://staging.denimyard.com': raise CommandError('Approved staging identity required.')
        owner=Membership.objects.filter(organization=site.organization,role='owner',active=True,user__is_active=True).select_related('user').first()
        if not owner: raise CommandError('Active owner required.')
        site.paused=True;site.save(update_fields=['paused'])
        save_connection(site,owner.user,account['username'],account['application_password'])
        for change in site.changeset_set.filter(state__in=['draft','pending_review','approved']):
            change.approvals.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
            change.state='stale_conflict';change.error_code='policy_or_connection_changed';change.save(update_fields=['state','error_code'])
        AuditEvent.objects.create(site=site,organization=site.organization,actor=owner.user,action='staging.writer_prepared')
        self.stdout.write('Test-copy writer encrypted. Existing drafts invalidated; new human approval is required. Publishing remains paused.')
