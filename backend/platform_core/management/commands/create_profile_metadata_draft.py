from django.core.management.base import BaseCommand,CommandError
from platform_core.models import Site,Membership,Page,ChangeSet,PageSnapshot,AuditIssue
from platform_core.connections import sync_inventory
from platform_core.changes import save_draft

class Command(BaseCommand):
    help='Create a rule-based English homepage description draft from owner-provided facts. Never approves or publishes.'
    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)
        parser.add_argument('--wordpress-id',type=int)
    def handle(self,*args,**options):
        site=Site.objects.get(pk=options['site'],archived_at__isnull=True)
        if 'english' not in site.languages.lower(): raise CommandError('This starting template supports English only; use the manual editor for other languages.')
        membership=Membership.objects.filter(organization=site.organization,role='owner',active=True,user__is_active=True).first()
        if not membership: raise CommandError('An active company owner is required.')
        sources=list(site.knowledge_sources.filter(source_type='owner_provided')[:10])
        if not sources: raise CommandError('Owner-provided knowledge evidence is required first.')
        sync_inventory(site,membership.user)
        page=Page.objects.filter(site=site,url__in=[site.url.rstrip('/'),site.url.rstrip('/')+'/'],wordpress_id__isnull=False).first()
        if not page:
            snapshot=PageSnapshot.objects.filter(page__site=site,page__url__in=[site.url.rstrip('/'),site.url.rstrip('/')+'/']).order_by('-fetched_at').first()
            if snapshot:
                AuditIssue.objects.get_or_create(snapshot=snapshot,code='homepage_mapping_missing',defaults={
                    'severity':'medium','evidence':'No WordPress homepage post mapping observed in the connected public inventory.',
                    'remediation':'Implement/verify the appropriate homepage or site-default adapter before proposing post metadata writes for this URL.',
                    'rule_version':'mapping-v1'})
        if options['wordpress_id']:
            page=Page.objects.filter(site=site,wordpress_id=options['wordpress_id']).first()
        if not page: raise CommandError('No mapped homepage; choose an explicitly supported page using --wordpress-id or the draft editor.')
        existing=ChangeSet.objects.filter(site=site,page=page).exclude(state__in=['rejected','cancelled','restored']).first()
        if existing:
            self.stdout.write(f'Existing draft/change retained: http://localhost:8000/sites/{site.pk}/changes/{existing.pk}/');return
        categories=', '.join(value.strip() for value in site.services.splitlines() if value.strip())[:120]
        if not categories: raise CommandError('Actual product/service categories must be provided first.')
        description=f'Explore {categories} at {site.name}'+(f' in {site.countries}' if site.countries else '')+'. View product details and available options before ordering.'
        change=save_draft(site,page,membership.user,{'description':description[:500]},sources,
            'Rule-based starting draft grounded in owner-provided categories and target market. No unconfirmed shipping, instalment or payment promises. Human review required.',provider='deterministic-v1')
        self.stdout.write(f'Unapproved draft created: http://localhost:8000/sites/{site.pk}/changes/{change.pk}/')
