"""Bounded evidence collection. Remote text is data, never agent instructions."""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .evidence import extract, audit
from .models import ResearchRun, KnowledgeSource, AuditEvent, Organization
from .permissions import can
from .public_http import fetch_public, FetchError
from .tasks import allowed_by_robots
from .owned_http import site_fetch

MAX_PAGES = 5

class AICallBlocked(ValueError):
    pass

@transaction.atomic
def reserve_ai_call(run_id):
    current=ResearchRun.objects.select_related('site','actor').get(pk=run_id)
    Organization.objects.select_for_update().get(pk=current.site.organization_id)
    current=ResearchRun.objects.select_for_update().select_related('site','actor').get(pk=run_id)
    if not can(current.actor,current.site,'generate_ai_draft') or not can(current.actor,current.site,'run_keyword_research'):
        raise AICallBlocked('ai_permission_required')
    daily=ResearchRun.objects.filter(site__organization_id=current.site.organization_id,
        ai_reserved_at__date=timezone.localdate(),ai_calls__gt=0).count()
    if current.ai_calls: raise AICallBlocked('ai_already_reserved')
    if not settings.RESEARCH_AI_ENABLED: raise AICallBlocked('ai_disabled')
    if not settings.GEMINI_MODEL or not settings.GEMINI_API_KEY: raise AICallBlocked('ai_not_configured')
    if daily>=5: raise AICallBlocked('ai_budget_exhausted')
    current.ai_calls,current.model,current.ai_reserved_at=1,settings.GEMINI_MODEL,timezone.now()
    current.stage='profile_suggestions'
    current.save()
    return current

def scoped_url(url, root):
    parts, origin = urlsplit(url), urlsplit(root)
    if (parts.scheme, parts.hostname, parts.port) != (origin.scheme, origin.hostname, origin.port):
        return None
    if parts.username or parts.password or parts.query or parts.fragment:
        return None
    if re.search(r'/(cart|checkout|my-account|wp-admin|wp-login|feed)(/|\.|$)', parts.path, re.I):
        return None
    if re.search(r'\.(jpg|jpeg|png|pdf|zip|gif|webp|svg|css|js)$', parts.path, re.I):
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path or '/', '', ''))

def collect(site):
    root = scoped_url(site.url, site.url)
    if not root:
        raise FetchError('research_url_requires_clean_origin')
    pending, seen, pages, skipped = [root], set(), [], []
    # One root plus four links: explicit small crawl, not a complete site audit.
    while pending and len(seen) < MAX_PAGES:
        url = pending.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            def guard(hop):
                if not scoped_url(hop, root) or not allowed_by_robots(hop,site=site):
                    raise FetchError('research_scope_or_robots')
            response = site_fetch(site,url,fetch=fetch_public,max_bytes=500_000,max_redirects=2,before_fetch=guard)
            if response.status != 200 or 'text/html' not in response.headers.get('content-type', '').lower():
                raise FetchError('research_html_required')
            e = extract(response.url, response.body.decode('utf-8', errors='replace'))
            pages.append({'url':response.url, 'title':(e.titles or [''])[0],
                'description':(e.descriptions or [''])[0], 'headings':e.headings[:20],
                'excerpt':re.sub(r'\s+', ' ', ' '.join(e.text)).strip()[:4000],
                'content_hash':hashlib.sha256(response.body).hexdigest(), 'issues':audit(e)})
            if len(seen) == 1:
                from django.utils.text import slugify
                preferred=[slugify(line) for line in site.services.splitlines() if len(slugify(line))>=3]
                links = sorted({candidate for link in e.links if (candidate := scoped_url(link, root)) and candidate != root},
                    key=lambda u:(0 if '/product-category/' in u and any(label in u for label in preferred) else 1 if '/product-category/' in u else 2 if '/product/' in u else 3 if any(x in u for x in ('about','contact')) else 4, u))
                pending.extend(links[:MAX_PAGES-1])
        except Exception:
            skipped.append({'url':url, 'reason':'scope_robots_or_fetch_failed'})
    candidates = []
    for page in pages:
        for tag, phrase in page['headings']:
            if tag not in ('h1','h2') or not 3 <= len(phrase) <= 120:
                continue
            if phrase.lower() in {c['phrase'].lower() for c in candidates}:
                continue
            candidates.append({'phrase':phrase, 'source_url':page['url'], 'kind':'observed_heading',
                'search_volume':None, 'difficulty':None})
    return {'pages':pages, 'keyword_candidates':candidates[:40], 'skipped':skipped,
        'coverage':f'At most {MAX_PAGES} public HTML pages; same origin; root links only.',
        'competitors':[], 'competitor_status':'Not researched: a verified search-data provider is not connected.',
        'audience_status':'Unknown until evidence-backed suggestions are reviewed.',
        'profile_suggestions':{}, 'warnings':['Public website claims are observations, not owner-verified facts.']}

def enqueue_research(run_id):
    try:
        research_site.apply_async(args=[str(run_id)], retry=False)
        return True
    except Exception:
        return False

@shared_task(time_limit=240, soft_time_limit=220)
def research_site(run_id):
    import uuid
    lease = uuid.uuid4()
    with transaction.atomic():
        run = ResearchRun.objects.select_for_update().select_related('site','actor').get(pk=run_id)
        if run.state != 'queued':
            return
        if not can(run.actor, run.site, 'run_keyword_research'):
            run.state, run.error_code = 'cancelled', 'authorization_revoked'
            run.save()
            return
        run.state, run.lease_token = 'running', lease
        run.save()
    try:
        report = collect(run.site)
        if not report['pages']:
            raise FetchError('no_public_evidence')
        if run.use_ai:
            from .research_ai import suggest_profile
            try:
                reserve_ai_call(run_id)
                report['profile_suggestions'] = suggest_profile(run.site, report['pages'])
                report['audience_status'] = 'AI hypothesis; requires owner review.'
                report['ai_status'] = 'succeeded'
            except Exception as error:
                from .research_ai import ProfileFailure
                report['ai_status'] = str(error) if isinstance(error,(ProfileFailure,AICallBlocked)) else 'ai_request_failed'
                report['warnings'].append('AI suggestions unavailable or rejected; public evidence remains usable. No automatic retry charge.')
        with transaction.atomic():
            current = ResearchRun.objects.select_for_update().select_related('actor','site').get(pk=run_id)
            if current.lease_token != lease or current.state != 'running':
                return
            if not can(current.actor,current.site,'run_keyword_research'):
                current.state, current.error_code = 'cancelled', 'authorization_revoked'
            else:
                for page in report['pages']:
                    source = KnowledgeSource.objects.create(site=current.site,url=page['url'],title=page['title'],
                        excerpt=page['excerpt'],content_hash=page['content_hash'],source_type='public_observation')
                    current.sources.add(source)
                from .research_proposals import build_proposals
                build_proposals(current,report)
                from .keywords import build_candidates
                build_candidates(current,report)
                current.report, current.state, current.stage = report, 'succeeded', 'review'
                AuditEvent.objects.create(organization=current.site.organization,site=current.site,actor=current.actor,
                    action='research.url_completed',target=str(current.pk))
            current.finished_at = timezone.now()
            current.save()
            if current.state=='succeeded' and current.auto_drafts:
                from .draft_assistant import enqueue_materialization
                transaction.on_commit(lambda:enqueue_materialization(current.pk))
    except Exception:
        ResearchRun.objects.filter(pk=run_id,lease_token=lease,state='running').update(
            state='failed',error_code='research_failed',finished_at=timezone.now())
