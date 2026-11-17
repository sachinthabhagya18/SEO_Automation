import hashlib
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from platform_core.models import Site, KnowledgeSource, AuditEvent
from platform_core.tasks import allowed_by_robots
from platform_core.public_http import fetch_public
from platform_core.evidence import extract

class Command(BaseCommand):
    help = 'Bounded Denim Yard public research plus owner-confirmed profile facts. Never changes WordPress.'

    def add_arguments(self, parser):
        parser.add_argument('--site', type=int, required=True)

    def handle(self, *args, **options):
        site = Site.objects.get(pk=options['site'], archived_at__isnull=True)
        if site.url.rstrip('/') != 'https://denimyard.com': raise CommandError('This example is restricted to the owner-selected Denim Yard URL.')
        collected=[]
        for path in ['/', '/about-us/', '/delivery-exchange-policy/', '/contact-us/', '/product-category/wide-leg/', '/product-category/womens-denim/']:
            url='https://denimyard.com'+path
            try:
                def guard(hop):
                    from urllib.parse import urlsplit
                    if urlsplit(hop).hostname!='denimyard.com' or not allowed_by_robots(hop):
                        raise ValueError('Crawl scope or robots restriction')
                response=fetch_public(url,before_fetch=guard)
                if response.status!=200: self.stdout.write(f'{path}: HTTP {response.status}');continue
                evidence=extract(response.url,response.body.decode('utf-8',errors='replace'))
                text=re.sub(r'\s+',' ',' '.join(evidence.text)).strip()
                excerpt='Headings: '+' | '.join(value for _,value in evidence.headings[:8])+'\nObserved text: '+text[:600]
                collected.append((response.url,(evidence.titles or [''])[0],excerpt[:1200],hashlib.sha256(response.body).hexdigest()))
                self.stdout.write(f'{path}: observed; title={evidence.titles[:1]}')
            except Exception as error:
                self.stdout.write(f'{path}: unavailable ({type(error).__name__})')
        with transaction.atomic():
            site=Site.objects.select_for_update().get(pk=site.pk)
            for url,title,excerpt,digest in collected:
                KnowledgeSource.objects.create(site=site,url=url,title=title,excerpt=excerpt,content_hash=digest)
            # The owner explicitly confirmed these facts in the current setup conversation.
            site.environment='production'
            site.industry='E-commerce / Women’s denim retail'
            site.services='Wide Leg\nWomen’s Denim'
            site.countries='Sri Lanka'
            site.languages='English'
            if not site.audience: site.audience='Customers in Sri Lanka shopping for women’s denim and wide-leg styles.'
            if not site.brand_voice: site.brand_voice='Clear, helpful, concise and product-focused; no unsupported quality or delivery claims.'
            confirmed='Owner-confirmed: WordPress + WooCommerce; target market Sri Lanka; English content; Wide Leg and Women’s Denim categories; Cash on Delivery available. Shipping configuration is not finalized. PayHere is planned, not confirmed active.'
            if confirmed not in site.verified_facts: site.verified_facts=(site.verified_facts+'\n'+confirmed).strip()
            restriction='Do not claim PayHere, Koko/Mintpay instalments, delivery thresholds/times, returns or exchange guarantees are active without owner confirmation. Public marketing copy is evidence to review, not an approved business fact. Do not invent stock, prices, discounts, ratings or certifications.'
            if restriction not in site.prohibited_claims: site.prohibited_claims=(site.prohibited_claims+'\n'+restriction).strip()
            if not site.conversion_goals: site.conversion_goals='Completed purchases; product enquiries; add-to-cart (separate from completed sales). Analytics connection pending.'
            site.paused=True
            site.save()
            KnowledgeSource.objects.create(site=site,url=site.url,title='Owner-provided setup facts',excerpt=confirmed,
                content_hash=hashlib.sha256(confirmed.encode()).hexdigest(),source_type='owner_provided')
            AuditEvent.objects.create(organization=site.organization,site=site,action='profile.owner_facts_and_public_research',target=str(len(collected)))
        self.stdout.write(f'Profile updated from owner-confirmed facts; {len(collected)} bounded public observations stored. Publishing remains paused. No remote writes.')
