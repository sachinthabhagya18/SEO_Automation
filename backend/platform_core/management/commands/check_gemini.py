import json
from urllib.parse import quote
import httpx
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from platform_core.models import Site,Membership,ResearchRun
from platform_core.research import reserve_ai_call,AICallBlocked
from platform_core.research_ai import request_json,ProfileFailure,failure_code

class Command(BaseCommand):
    help='Safe key/model metadata check; optional one-request generation probe within the normal daily allowance.'

    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)
        parser.add_argument('--generate',action='store_true')

    def handle(self,*args,**options):
        if not settings.GEMINI_API_KEY or not settings.GEMINI_MODEL:
            raise CommandError('provider_not_configured; edit local .env privately')
        try:
            with httpx.Client(timeout=15,trust_env=False,follow_redirects=False) as client:
                response=client.get('https://generativelanguage.googleapis.com/v1beta/models/'+quote(settings.GEMINI_MODEL,safe=''),
                    headers={'x-goog-api-key':settings.GEMINI_API_KEY})
            code=response.status_code
        except Exception as error:
            raise CommandError(failure_code(error)) from None
        self.stdout.write(f'Model metadata HTTP: {code}. No key or provider body printed.')
        if code!=200 or not options['generate']:
            return
        site=Site.objects.get(pk=options['site'])
        member=Membership.objects.filter(organization=site.organization,role='owner',active=True,user__is_active=True).select_related('user').first()
        if not member: raise CommandError('active_owner_required')
        run=ResearchRun.objects.create(site=site,actor=member.user,use_ai=True,state='running',stage='connection_test')
        status='ai_disabled_budget_or_permission'
        try:
            reserve_ai_call(run.pk)
            raw=request_json('Return JSON with ready set to true. No other text.',
                {'type':'object','properties':{'ready':{'type':'boolean'}},'required':['ready'],'additionalProperties':False},
                max_tokens=128,timeout=25)
            if json.loads(raw)!={'ready':True}: raise ProfileFailure('provider_schema_or_evidence_rejected')
            status='succeeded'
        except Exception as error:
            status=str(error) if isinstance(error,(ProfileFailure,AICallBlocked)) else failure_code(error)
        run.refresh_from_db()
        run.state='succeeded' if status=='succeeded' else 'failed'
        run.stage='connection_test';run.finished_at=timezone.now()
        run.report={'ai_status':status,'coverage':'Provider connection probe only; no crawl, profile update or publication.'}
        run.save()
        self.stdout.write(f'Generation probe: {status}; run {run.pk}; reserved calls: {run.ai_calls}.')
