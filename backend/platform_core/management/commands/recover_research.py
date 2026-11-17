from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from platform_core.models import ResearchRun
from platform_core.research import enqueue_research

class Command(BaseCommand):
    help='Re-dispatch queued URL research; mark expired executions for explicit review without paid retries.'

    def handle(self,*args,**options):
        expired=ResearchRun.objects.filter(state='running',created_at__lt=timezone.now()-timedelta(minutes=10)).update(
            state='failed',error_code='execution_expired_review_required',finished_at=timezone.now())
        queued=0
        for pk in ResearchRun.objects.filter(state='queued').values_list('pk',flat=True):
            queued+=bool(enqueue_research(pk))
        self.stdout.write(f'Expired executions: {expired}; queued dispatches: {queued}. No paid call was retried.')
