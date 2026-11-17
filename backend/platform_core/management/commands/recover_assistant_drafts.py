from django.core.management.base import BaseCommand
from platform_core.models import ResearchRun
from platform_core.draft_assistant import enqueue_materialization

class Command(BaseCommand):
    help='Re-dispatch pending assistant draft jobs. No AI call, approval or publication.'

    def handle(self,*args,**options):
        count=0
        runs=ResearchRun.objects.filter(state='succeeded',auto_drafts=True,proposals__page__isnull=False,proposals__change__isnull=True).distinct()
        for run in runs:
            count+=bool(enqueue_materialization(run.pk))
        self.stdout.write(f'Assistant draft jobs re-dispatched: {count}. Existing drafts are reused; current permissions are rechecked.')
