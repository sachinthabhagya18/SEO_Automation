from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from platform_core.models import Page
from platform_core.metadata_cache import dispatch_read

class Command(BaseCommand):
    help='Redispatch durable queued metadata reads; expire abandoned running reads.'
    def handle(self,**options):
        expired=Page.objects.filter(metadata_load_state='running',metadata_load_requested_at__lt=timezone.now()-timedelta(minutes=2)).update(metadata_load_state='failed',metadata_load_error='metadata_read_expired')
        count=0
        for page in Page.objects.filter(metadata_load_state='queued').only('id','metadata_load_token')[:100]:
            count+=bool(dispatch_read(page.pk,page.metadata_load_token))
        self.stdout.write(f'Redispatched {count}; expired {expired}.')
