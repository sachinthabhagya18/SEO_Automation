import hashlib
import uuid
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Job, Page, PageSnapshot, AuditIssue, AuditEvent, ServiceCredential
from .permissions import can
from .public_http import fetch_public, FetchError
from .evidence import extract, audit
from .owned_http import site_fetch

def allowed_by_robots(url,site=None):
    parts = urlsplit(url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, '/robots.txt', '', ''))
    response = site_fetch(site,robots_url,fetch=fetch_public,max_bytes=100_000,max_redirects=3) if site else fetch_public(robots_url,max_bytes=100_000,max_redirects=3)
    if response.status == 404:
        return True
    if response.status != 200:
        return False
    parser = RobotFileParser()
    parser.parse(response.body.decode('utf-8', errors='replace').splitlines())
    return parser.can_fetch('CompanySEOAudit', url)

def enqueue(job_id):
    # PostgreSQL remains authoritative if Redis is unavailable or loses a message.
    try:
        audit_public_page.apply_async(args=[str(job_id)], retry=False)
    except Exception:
        # Do not log exception strings, remote response bodies, URLs or credentials.
        return False
    return True

def job_authorized(job):
    if not can(job.actor,job.site,'run_audit'): return False
    if job.service_credential_id:
        return ServiceCredential.objects.filter(pk=job.service_credential_id,site=job.site,actor=job.actor,
            active=True,scope='public_audit',expires_at__gt=timezone.now()).exists()
    return True

@shared_task
def audit_public_page(job_id):
    lease = uuid.uuid4()
    with transaction.atomic():
        job = Job.objects.select_for_update().select_related('site', 'actor').get(pk=job_id)
        if job.state != Job.State.QUEUED and not (job.state == Job.State.RUNNING and job.lease_expires_at and job.lease_expires_at < timezone.now()):
            return
        if not job_authorized(job):
            job.state, job.error_code, job.finished_at = Job.State.CANCELLED, 'authorization_revoked', timezone.now()
            job.save()
            return
        job.state, job.lease_token = Job.State.RUNNING, lease
        job.lease_expires_at = timezone.now() + timedelta(minutes=6)
        job.save()
    try:
        def check_hop(url):
            if urlsplit(url).hostname != urlsplit(job.target_url).hostname:
                raise FetchError('cross_host_redirect_requires_review')
            if not allowed_by_robots(url,site=job.site):
                raise FetchError('robots_disallowed')
        response = site_fetch(job.site,job.target_url,fetch=fetch_public,before_fetch=check_hop)
        if 'text/html' not in response.headers.get('content-type', '').lower():
            raise FetchError('html_required')
        evidence = extract(response.url, response.body.decode('utf-8', errors='replace'))
        issues = audit(evidence, response.status)
        with transaction.atomic():
            current = Job.objects.select_for_update().select_related('site', 'actor').get(pk=job_id)
            if current.lease_token != lease or current.state != Job.State.RUNNING:
                return
            if not job_authorized(current):
                current.state, current.error_code = Job.State.CANCELLED, 'authorization_revoked'
            else:
                page, _ = Page.objects.get_or_create(site=current.site, url=response.url)
                snapshot = PageSnapshot.objects.create(page=page, job=current, status_code=response.status,
                    content_hash=hashlib.sha256(response.body).hexdigest(), title=(evidence.titles or [''])[0],
                    description=(evidence.descriptions or [''])[0], evidence_excerpt=' '.join(evidence.text)[:2000])
                AuditIssue.objects.bulk_create([AuditIssue(snapshot=snapshot, **{key: value for key, value in issue.items() if key != 'url'}) for issue in issues])
                current.state = Job.State.SUCCEEDED
                AuditEvent.objects.create(organization=current.site.organization, site=current.site, actor=current.actor,
                                          action='audit.public_page_completed', target=str(current.pk))
            current.finished_at = timezone.now()
            current.save()
    except Exception as error:
        code = str(error) if isinstance(error, FetchError) and str(error) in {'robots_disallowed', 'cross_host_redirect_requires_review', 'html_required'} else 'public_fetch_or_processing_failed'
        Job.objects.filter(pk=job_id, lease_token=lease, state=Job.State.RUNNING).update(
            state=Job.State.FAILED, error_code=code, finished_at=timezone.now())
