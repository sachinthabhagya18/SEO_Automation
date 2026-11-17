import time
from datetime import datetime
from django.core.management.base import BaseCommand,CommandError
from platform_core.models import Job

class Command(BaseCommand):
    help='Verify an already-configured local n8n timer delivers a new read-only audit and worker result.'
    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)
        parser.add_argument('--after',required=True)
    def handle(self,*args,**options):
        marker=datetime.fromisoformat(options['after'].replace('Z','+00:00'))
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            job=Job.objects.filter(site_id=options['site'],service_credential__isnull=False,created_at__gte=marker).order_by('-created_at').first()
            if job and job.state=='succeeded':
                self.stdout.write(f'n8n Schedule Trigger → scoped Django API → Celery → public evidence verified. job_id={job.pk}')
                return
            if job and job.state in ('failed','cancelled'): raise CommandError('Scheduled job ended with safe error code: '+job.error_code)
            time.sleep(2)
        raise CommandError('No successful newly scheduled audit observed before the 90-second limit.')
