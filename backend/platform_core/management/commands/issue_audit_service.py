from django.core.management.base import BaseCommand,CommandError
from platform_core.models import Site,Membership
from platform_core.automation import issue_service_credential

class Command(BaseCommand):
    help='Issue a 30-day site-scoped read-only audit service token. Private one-time output; no publishing scope.'
    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)
        parser.add_argument('--scope',choices=['public_audit','research_drafts','search_metrics'],default='public_audit')
    def handle(self,*args,**options):
        site=Site.objects.get(pk=options['site'],archived_at__isnull=True)
        owner=Membership.objects.filter(organization=site.organization,active=True,role='owner',user__is_active=True).first()
        if not owner: raise CommandError('An active company owner is required.')
        _,token=issue_service_credential(site,owner.user,scope=options['scope'])
        self.stdout.write(token)
