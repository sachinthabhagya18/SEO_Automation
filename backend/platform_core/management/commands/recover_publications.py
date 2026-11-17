from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from platform_core.models import PublishAttempt
from platform_core.changes import safe_dispatch
from platform_core.publish_tasks import execute_metadata_change

class Command(BaseCommand):
    help='Redis/crash recovery for existing local metadata attempts; current authorization and remote status are rechecked.'
    def handle(self,*args,**options):
        attempts=PublishAttempt.objects.filter(Q(state='queued') | (Q(state__in=['running','applied_pending_verification']) &
            (Q(change__page__publication_lease_until__lt=timezone.now()) | Q(change__page__publication_lease_until__isnull=True)))).values_list('pk',flat=True)[:100]
        count=sum(safe_dispatch(execute_metadata_change,str(pk)) for pk in attempts)
        self.stdout.write(f'Dispatched {count} existing local metadata attempts; no approvals or new changes created.')
