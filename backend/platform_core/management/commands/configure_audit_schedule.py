from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from platform_core.models import Site,AuditSchedule,AuditEvent

class Command(BaseCommand):
    help='Configure one site’s read-only audit schedule. n8n owns triggering; Django owns next_due.'
    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)
        parser.add_argument('--interval-minutes',type=int,default=1440)
        parser.add_argument('--disable',action='store_true')
    def handle(self,*args,**options):
        if not 60<=options['interval_minutes']<=10080: raise CommandError('Interval must be 60–10080 minutes.')
        site=Site.objects.get(pk=options['site'],archived_at__isnull=True)
        schedule,_=AuditSchedule.objects.update_or_create(site=site,defaults={'enabled':not options['disable'],
            'interval_minutes':options['interval_minutes'],'next_due':timezone.now()})
        AuditEvent.objects.create(organization=site.organization,site=site,action='automation.audit_schedule_configured')
        self.stdout.write('Read-only audit schedule '+('disabled.' if not schedule.enabled else f'enabled every {schedule.interval_minutes} minutes; n8n dispatcher required. Publishing remains unchanged.'))
