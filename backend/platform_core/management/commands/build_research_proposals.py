from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from platform_core.models import ResearchRun
from platform_core.research_proposals import build_proposals

class Command(BaseCommand):
    help='Create idempotent page-specific proposals from the latest completed research evidence; no AI or WordPress writes.'

    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)

    @transaction.atomic
    def handle(self,*args,**options):
        run=ResearchRun.objects.select_for_update().filter(site_id=options['site'],state='succeeded',stage='review').first()
        if not run or not run.report.get('pages'): raise CommandError('completed_page_evidence_required')
        build_proposals(run,run.report)
        from platform_core.keywords import build_candidates
        build_candidates(run,run.report)
        self.stdout.write(f'Research {run.pk}: {run.proposals.count()} proposals; no provider calls or WordPress writes.')
