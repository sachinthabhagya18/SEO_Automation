from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from platform_core.models import Job
from platform_core.tasks import enqueue

class Command(BaseCommand):
    help = 'Redis recovery: redispatch queued/expired internal audit jobs. Does not create business schedules.'

    def handle(self, *args, **options):
        jobs = Job.objects.filter(Q(state='queued') | Q(state='running', lease_expires_at__lt=timezone.now())).values_list('pk', flat=True)[:100]
        count = sum(enqueue(pk) for pk in jobs)
        self.stdout.write(f'Dispatched {count} durable job records; active leases and completed jobs are skipped.')
