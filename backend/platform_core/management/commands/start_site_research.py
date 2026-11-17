from django.core.management.base import BaseCommand, CommandError
from platform_core.models import Site, Membership, ResearchRun
from platform_core.permissions import can
from platform_core.research import enqueue_research
from django.db import transaction

class Command(BaseCommand):
    help='Start public-only URL research for an existing site using its active owner. Never calls AI.'

    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)

    def handle(self,*args,**options):
        with transaction.atomic():
            site=Site.objects.select_for_update().get(pk=options['site'])
            member=Membership.objects.filter(organization=site.organization,role='owner',active=True,user__is_active=True).select_related('user').first()
            if not member or not can(member.user,site,'run_keyword_research'):
                raise CommandError('An active authorized company owner is required.')
            run=ResearchRun.objects.filter(site=site,state__in=['queued','running']).first()
            if not run:
                run=ResearchRun.objects.create(site=site,actor=member.user)
                transaction.on_commit(lambda:enqueue_research(run.pk))
        self.stdout.write(f'Public-only research: {run.pk}; /sites/{site.pk}/research/')
