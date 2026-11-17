import json
import sys
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from platform_core.models import Site,Membership,SiteConnection
from platform_core.connections import save_connection,decrypt_credentials

class Command(BaseCommand):
    help='Bind the fixed Denim Yard staging reader from private stdin JSON; never prints credentials or enables publishing.'

    def add_arguments(self,parser):
        parser.add_argument('--source-site',type=int,required=True)

    @transaction.atomic
    def handle(self,*args,**options):
        try:
            raw=sys.stdin.read(32001)
            if len(raw)>32000: raise ValueError()
            data=json.loads(raw)
            if data['url']!='https://staging.denimyard.com': raise ValueError()
            account=data['connector_accounts']['reader']
            if account['username']!='seo-staging-reader' or not isinstance(account['application_password'],str) or not 16<=len(account['application_password'])<=100: raise ValueError()
        except (ValueError,TypeError,KeyError): raise CommandError('Invalid staging reader envelope; values suppressed.') from None
        source=Site.objects.get(pk=options['source_site'])
        owner=Membership.objects.filter(organization=source.organization,role='owner',active=True,user__is_active=True).select_related('user').first()
        if not owner or source.archived_at: raise CommandError('Active source owner required.')
        defaults={name:getattr(source,name) for name in ['industry','services','audience','countries','languages','brand_voice','verified_facts','prohibited_claims','conversion_goals','timezone']}
        defaults.update(name='Denim Yard test copy',environment='staging',paused=True,parent_site=source)
        site,created=Site.objects.get_or_create(organization=source.organization,url=data['url'],defaults=defaults)
        if site.environment!='staging' or site.archived_at: raise CommandError('Existing staging profile requires review.')
        existing=SiteConnection.objects.filter(site=site).first()
        if existing:
            expected={'username':account['username'],'password':account['application_password']}
            if existing.bound_url.rstrip('/')!=site.url.rstrip('/') or decrypt_credentials(existing)!=expected:
                raise CommandError('Existing staging credentials differ; refusing silent rotation.')
        else:
            save_connection(site,owner.user,account['username'],account['application_password'])
        self.stdout.write(f'Staging site {site.pk}; /sites/{site.pk}/connection/; reader encrypted; publishing paused; live source unchanged.')
