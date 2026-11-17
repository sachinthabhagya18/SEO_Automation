from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from platform_core.models import SearchMetricsRun
from platform_core.search_metrics import dispatch_sync

class Command(BaseCommand):
    help='Recover durable queued Google syncs; expire abandoned running requests without automatic API retry.'
    def handle(self,**options):
        expired=SearchMetricsRun.objects.filter(state='running',started_at__lt=timezone.now()-timedelta(minutes=6)).update(
            state='failed',error_code='google_sync_execution_expired',finished_at=timezone.now())
        count=sum(dispatch_sync(run.pk) for run in SearchMetricsRun.objects.filter(state='queued').only('pk')[:100])
        self.stdout.write(f'Redispatched {count}; expired {expired}. No Google approvals created.')
