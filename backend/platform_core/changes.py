"""Deterministic metadata review and local-only publication services; no AI approval."""
import hashlib
import json
import re
import uuid
from datetime import timedelta
from urllib.parse import urlsplit
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import SitePolicy,SiteConnection,ChangeSet,Approval,PublishAttempt,Page,KnowledgeSource,AuditEvent
from .permissions import can
from .connections import wordpress_get,wordpress_request,ConnectionFailure,connector_target
from .public_http import fetch_public,PinnedConnection,Target
from .evidence import extract
from .owned_http import site_fetch

class ChangeFailure(ValueError): pass

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def context_hash(site,sources):
    return digest({'name':site.name,'services':site.services,'countries':site.countries,'languages':site.languages,
        'facts':site.verified_facts,'prohibited':site.prohibited_claims,'voice':site.brand_voice,
        'sources':sorted((s.pk,s.content_hash,s.approved_by_id,s.source_type) for s in sources)})

def policy_for(site): return SitePolicy.objects.get_or_create(site=site)[0]

def proposed_fields(change):
    return {key:value for enabled,key,value in [(change.change_title,'title',change.proposed_title),
        (change.change_description,'description',change.proposed_description)] if enabled}

def immutable_payload(change):
    payload={'site':change.site_id,'url':change.site.url,'page':change.page_id,'page_url':change.page.url,
        'wordpress_id':change.page.wordpress_id,'base_revision':change.base_revision,'base':change.base_metadata,
        'changes':proposed_fields(change),'connection_version':str(change.connection_version),
        'policy_version':str(change.policy_version),'context_hash':change.context_hash,
        'sources':sorted(change.sources.values_list('pk',flat=True))}
    if change.page.target_kind!='post': payload['target_kind']=change.page.target_kind
    return payload

def validate_text(values):
    if not values or set(values)-{'title','description'}: raise ChangeFailure('supported_metadata_fields_required')
    for field,value in values.items():
        if not isinstance(value,str) or not value.strip() or len(value)>(200 if field=='title' else 500) \
            or any(ord(c)<32 for c in value) or '<' in value or '>' in value:
            raise ChangeFailure('plain_bounded_metadata_text_required')

def change_path(change,suffix):
    page=change.page
    return (f'contexts/{page.target_kind}/{page.wordpress_id}/' if page.target_kind!='post' else '')+'changes/'+suffix

def remote_metadata(connection,page,cache=True):
    if page.wordpress_id is None or page.site_id!=connection.site_id: raise ChangeFailure('page_inventory_mapping_required')
    path=f'pages/{page.wordpress_id}/seo' if page.target_kind=='post' else f'contexts/{page.target_kind}/{page.wordpress_id}/seo'
    result=wordpress_get(connection,path)
    if result.get('id')!=page.wordpress_id or not re.fullmatch('[a-f0-9]{64}',str(result.get('revision',''))): raise ChangeFailure('invalid_remote_metadata')
    stored=result.get('stored')
    if not isinstance(stored,dict) or set(stored)-{'title','description','og_title','og_description'} \
        or any(not isinstance(v,str) or len(v)>1000 for v in stored.values()): raise ChangeFailure('invalid_remote_metadata')
    if cache:
        from .metadata_cache import cache_result
        cache_result(connection,page,result)
    return result

@transaction.atomic
def save_draft(site,page,actor,values,sources,reason='',change=None,provider='manual'):
    if not can(actor,site,'edit_draft') or not can(actor,site,'view_site'): raise ChangeFailure('draft_permission_required')
    if page.site_id!=site.pk or any(s.site_id!=site.pk for s in sources): raise ChangeFailure('cross_site_evidence_rejected')
    validate_text(values)
    policy=policy_for(site)
    if policy.mode=='read_only': raise ChangeFailure('site_read_only')
    connection=SiteConnection.objects.get(site=site)
    if connection.status!='connected': raise ChangeFailure('verified_read_connection_required')
    if change:
        change=ChangeSet.objects.select_for_update().get(pk=change.pk,site=site)
        if change.state not in ('draft','pending_review','approved','rejected','stale_conflict'):
            raise ChangeFailure('change_is_not_editable')
        change.approvals.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    else: change=ChangeSet(site=site,page=page,created_by=actor)
    baseline=remote_metadata(connection,page)
    change.page=page;change.last_edited_by=actor;change.state='draft';change.change_title='title' in values;change.change_description='description' in values
    change.proposed_title=values.get('title','');change.proposed_description=values.get('description','')
    change.base_metadata=baseline['stored'];change.base_revision=baseline['revision'];change.connection_version=connection.credential_version
    change.context_hash=context_hash(site,sources);change.policy_version=policy.version;change.reason=reason[:2000];change.provider=provider
    change.error_code='';change.save();change.sources.set(sources);change.payload_hash=digest(immutable_payload(change));change.save(update_fields=['payload_hash'])
    AuditEvent.objects.create(site=site,organization=site.organization,actor=actor,action='change.draft_saved',target=str(change.pk))
    return change

@transaction.atomic
def submit(change,actor):
    change=ChangeSet.objects.select_for_update().select_related('site','page').get(pk=change.pk)
    if not can(actor,change.site,'submit_for_review'): raise ChangeFailure('submit_permission_required')
    if change.state!='draft': raise ChangeFailure('draft_state_required')
    validate_text(proposed_fields(change))
    if not change.sources.exists(): raise ChangeFailure('source_evidence_required')
    if digest(immutable_payload(change))!=change.payload_hash: raise ChangeFailure('payload_changed')
    change.state='pending_review';change.save(update_fields=['state'])
    AuditEvent.objects.create(site=change.site,organization=change.site.organization,actor=actor,action='change.submitted',target=str(change.pk))
    return change

def validate_current(change,require_approval=True):
    site=change.site;policy=policy_for(site);connection=SiteConnection.objects.get(site=site)
    if site.archived_at or policy.mode!='approval_required': raise ChangeFailure('current_policy_blocks_publication')
    if change.policy_version!=policy.version or change.connection_version!=connection.credential_version: raise ChangeFailure('policy_or_connection_changed')
    if connection.status!='connected' or connection.bound_url.rstrip('/')!=site.url.rstrip('/'): raise ChangeFailure('connection_not_current')
    if change.context_hash!=context_hash(site,list(change.sources.all())): raise ChangeFailure('business_evidence_changed')
    if change.payload_hash!=digest(immutable_payload(change)): raise ChangeFailure('payload_changed')
    if ('title' in proposed_fields(change) and not policy.allow_title) or ('description' in proposed_fields(change) and not policy.allow_description): raise ChangeFailure('field_not_allowed')
    if require_approval:
        approval=change.approvals.filter(revoked_at__isnull=True,payload_hash=change.payload_hash,base_revision=change.base_revision,policy_version=policy.version).select_related('approver').last()
        if not approval or not can(approval.approver,site,'approve_change'): raise ChangeFailure('valid_current_approval_required')
        if policy.forbid_self_approval and approval.approver_id in (change.created_by_id,change.last_edited_by_id): raise ChangeFailure('self_approval_forbidden')
    return connection

@transaction.atomic
def approve(change,actor):
    change=ChangeSet.objects.select_for_update().select_related('site','page').get(pk=change.pk)
    if not can(actor,change.site,'approve_change'): raise ChangeFailure('approval_permission_required')
    if change.state!='pending_review': raise ChangeFailure('pending_review_required')
    policy=policy_for(change.site)
    if policy.forbid_self_approval and actor.pk in (change.created_by_id,change.last_edited_by_id): raise ChangeFailure('self_approval_forbidden')
    validate_current(change,False)
    Approval.objects.create(change=change,approver=actor,payload_hash=change.payload_hash,base_revision=change.base_revision,policy_version=change.policy_version)
    change.state='approved';change.save(update_fields=['state'])
    AuditEvent.objects.create(site=change.site,organization=change.site.organization,actor=actor,action='change.approved',target=str(change.pk))
    return change

def local_write_guard(change,actor,operation):
    if not can(actor,change.site,'publish_change' if operation=='apply' else 'rollback_change'): raise ChangeFailure('execution_permission_revoked')
    from .publication_scope import write_scope
    if not write_scope(change.site): raise ChangeFailure('local_fixture_write_testing_only')
    if change.site.paused: raise ChangeFailure('site_writes_paused')
    connection=validate_current(change)
    if change.page.target_kind!='post' and change.page.target_kind not in connection.capabilities.get('metadata_target_kinds',[]):
        raise ChangeFailure('connector_target_kind_not_supported')
    if not connection.capabilities.get('remote_write' if operation=='apply' else 'restore'): raise ChangeFailure('connector_write_capability_missing')
    if set(proposed_fields(change))-set(connection.capabilities.get('metadata_write_fields',[])): raise ChangeFailure('connector_field_not_supported')
    return connection

@transaction.atomic
def enqueue_change(change,actor,operation='apply'):
    change=ChangeSet.objects.select_for_update().select_related('site','page').get(pk=change.pk)
    if operation not in ('apply','restore'): raise ChangeFailure('unsupported_operation')
    local_write_guard(change,actor,operation)
    allowed=('approved','ambiguous_remote_result','retryable_failure') if operation=='apply' else ('verified','verification_failed','applied_pending_verification','restoration_failed')
    existing=PublishAttempt.objects.filter(change=change,operation=operation).first()
    if existing and existing.state in ('queued','running','succeeded'): return existing
    if change.state not in allowed: raise ChangeFailure('change_state_blocks_execution')
    attempt,_=PublishAttempt.objects.update_or_create(change=change,operation=operation,defaults={'actor':actor,'state':'queued','error_code':''})
    change.state='queued' if operation=='apply' else 'restoration_queued';change.save(update_fields=['state'])
    from .publish_tasks import execute_metadata_change
    transaction.on_commit(lambda: safe_dispatch(execute_metadata_change,str(attempt.pk)))
    return attempt

def safe_dispatch(task,attempt_id):
    from .publication_scope import write_scope
    try:
        attempt=PublishAttempt.objects.select_related('change__site__parent_site').get(pk=attempt_id)
        queue='metadata-staging' if write_scope(attempt.change.site)=='staging' else 'metadata-fixture'
        task.apply_async(args=[attempt_id],queue=queue,retry=False)
    except Exception: return False
    return True

def read_public_head(site,url):
    if settings.CONNECTOR_LOCAL_FIXTURE_ENABLED and site.url=='http://wordpress':
        parsed=urlsplit(url)
        if parsed.netloc not in ('localhost:8081','wordpress'): raise ChangeFailure('invalid_local_verification_url')
        target=connector_target('http://wordpress','capabilities')
        path=parsed.path or '/'
        if parsed.query: path+='?'+parsed.query
        target=Target('http://wordpress'+path,'http','wordpress',80,path,target.family,target.address)
        client=PinnedConnection(target,5)
        try:
            client.request('GET',target.path,headers={'Host':'localhost:8081','Cache-Control':'no-cache'})
            response=client.getresponse();body=response.read(2_000_001)
            if len(body)>2_000_000: raise ChangeFailure('verification_body_too_large')
            status=response.status
        finally: client.close()
    else:
        if urlsplit(url).hostname!=urlsplit(site.url).hostname: raise ChangeFailure('foreign_verification_url')
        response=site_fetch(site,url,fetch=fetch_public,max_redirects=0);status=response.status;body=response.body
    evidence=extract(url,body.decode('utf-8',errors='replace'))
    return {'status':status,'titles':evidence.titles[:5],'descriptions':evidence.descriptions[:5],
        'canonicals':evidence.canonicals[:5],'robots':evidence.robots[:5]}

def verify_head(change,head,restoring=False):
    errors=[]
    if head['status']!=200: errors.append('public_http_not_ok')
    if len(head['titles'])!=1: errors.append('title_output_not_single')
    if len(head['canonicals'])>1 or len(head['robots'])>1: errors.append('duplicate_canonical_or_robots')
    if restoring:
        if head['titles']!=change.public_before.get('titles'): errors.append('restored_title_mismatch')
        if head['descriptions']!=change.public_before.get('descriptions'): errors.append('restored_description_mismatch')
    else:
        values=proposed_fields(change)
        if 'title' in values and head['titles']!=[values['title']]: errors.append('public_title_mismatch')
        if 'description' in values and head['descriptions']!=[values['description']]: errors.append('public_description_mismatch')
    if any('noindex' in value.lower() for value in change.public_before.get('robots',[])) and not any('noindex' in value.lower() for value in head['robots']):
        errors.append('privacy_noindex_lost')
    return errors

def retry_public_verification(change,actor):
    if not can(actor,change.site,'view_site'): raise ChangeFailure('view_permission_required')
    if change.state not in ('verification_failed','applied_pending_verification','restoration_failed'):
        raise ChangeFailure('verification_retry_not_available')
    count=change.verification.get('manual_retries',0)
    if count>=3: raise ChangeFailure('verification_retry_limit_reached')
    restoring=change.state=='restoration_failed'
    attempt=change.attempts.filter(operation='restore' if restoring else 'apply').last()
    if not attempt or not attempt.receipt: raise ChangeFailure('remote_receipt_required')
    from .publish_tasks import checked_receipt
    checked_receipt(change,attempt.receipt)
    head=read_public_head(change.site,change.page.url)
    errors=verify_head(change,head,restoring)
    change.state=('restored' if restoring else 'verified') if not errors else ('restoration_failed' if restoring else 'verification_failed')
    change.error_code=','.join(errors)
    change.verification={'operation':'restore' if restoring else 'apply','head':head,'errors':errors,
        'checked_at':timezone.now().isoformat(),'manual_retries':count+1}
    change.save(update_fields=['state','error_code','verification'])
    return change
