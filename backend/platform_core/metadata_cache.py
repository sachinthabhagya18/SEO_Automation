"""Fast editor reads; the publication/draft services still read a fresh revision."""
import uuid
from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Page,SiteConnection,User
from .permissions import can

def allowed(actor,site):
    return can(actor,site,'view_site') and can(actor,site,'edit_draft')

def cache_result(connection,page,result):
    # Cache only the validated SEO envelope, never arbitrary connector JSON.
    Page.objects.filter(pk=page.pk,site=connection.site).update(metadata_snapshot={'id':result['id'],
        'revision':result['revision'],'stored':result['stored'],'target_kind':page.target_kind},metadata_snapshot_at=timezone.now(),
        metadata_snapshot_version=connection.credential_version)

@transaction.atomic
def queue_read(page,actor):
    if not allowed(actor,page.site): raise ValueError('draft_permission_required')
    page=Page.objects.select_for_update().select_related('site').get(pk=page.pk)
    connection=SiteConnection.objects.filter(site=page.site,status='connected').first()
    if not connection or connection.bound_url.rstrip('/')!=page.site.url.rstrip('/') or page.wordpress_id is None:
        raise ValueError('verified_inventory_connection_required')
    if page.metadata_load_state in ('queued','running') and page.metadata_load_version==connection.credential_version \
        and page.metadata_load_requested_at and page.metadata_load_requested_at>timezone.now()-timedelta(minutes=2):
        return page.metadata_load_token
    token=uuid.uuid4()
    page.metadata_load_token=token;page.metadata_load_state='queued';page.metadata_load_error=''
    page.metadata_load_actor=actor;page.metadata_load_version=connection.credential_version;page.metadata_load_requested_at=timezone.now()
    page.save(update_fields=['metadata_load_token','metadata_load_state','metadata_load_error','metadata_load_actor','metadata_load_version','metadata_load_requested_at'])
    transaction.on_commit(lambda:dispatch_read(page.pk,token))
    return token

def dispatch_read(page_id,token):
    try:
        refresh_metadata.apply_async(args=[page_id,str(token)],retry=False)
        return True
    except Exception:
        return False

@shared_task(time_limit=75,soft_time_limit=60)
def refresh_metadata(page_id,token):
    from .changes import remote_metadata
    from .connections import ConnectionFailure
    with transaction.atomic():
        page=Page.objects.select_for_update(of=('self',)).select_related('site','metadata_load_actor').get(pk=page_id)
        if str(page.metadata_load_token)!=token or page.metadata_load_state!='queued': return
        actor=page.metadata_load_actor
        connection=SiteConnection.objects.filter(site=page.site,status='connected',credential_version=page.metadata_load_version).first()
        if not actor or not allowed(actor,page.site) or not connection or connection.bound_url.rstrip('/')!=page.site.url.rstrip('/'):
            page.metadata_load_state='cancelled';page.metadata_load_error='permission_or_connection_changed';page.save(update_fields=['metadata_load_state','metadata_load_error']);return
        page.metadata_load_state='running';page.save(update_fields=['metadata_load_state'])
    try:
        result=remote_metadata(connection,page,cache=False)
        with transaction.atomic():
            current=Page.objects.select_for_update(of=('self',)).select_related('site','metadata_load_actor').get(pk=page_id)
            valid=SiteConnection.objects.filter(site=current.site,status='connected',credential_version=page.metadata_load_version,bound_url=connection.bound_url).exists()
            if str(current.metadata_load_token)!=token: return
            if not valid or not current.metadata_load_actor or not allowed(current.metadata_load_actor,current.site):
                current.metadata_load_state='cancelled';current.metadata_load_error='permission_or_connection_changed'
            else:
                cache_result(connection,current,result)
                current.metadata_load_state='ready';current.metadata_load_error=''
            current.save(update_fields=['metadata_load_state','metadata_load_error'])
    except Exception as error:
        code=str(error) if isinstance(error,ConnectionFailure) else 'metadata_read_failed'
        Page.objects.filter(pk=page_id,metadata_load_token=token).update(metadata_load_state='failed',metadata_load_error=code[:80])
