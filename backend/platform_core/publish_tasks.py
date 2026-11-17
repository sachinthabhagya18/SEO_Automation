import re
import uuid
from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import ChangeSet,PublishAttempt,Page,User,AuditEvent
from .changes import ChangeFailure,local_write_guard,remote_metadata,proposed_fields,read_public_head,verify_head,change_path
from .connections import wordpress_get,wordpress_request,ConnectionFailure

def checked_receipt(change,result):
    if isinstance(result,dict) and result.get('target_kind','post')!=change.page.target_kind:
        raise ChangeFailure('remote_target_kind_mismatch')
    if not isinstance(result,dict) or result.get('change_id')!=str(change.pk) or result.get('post_id')!=change.page.wordpress_id \
        or result.get('state') not in ('applied','restored') or result.get('before_revision')!=change.base_revision \
        or not re.fullmatch('[a-f0-9]{64}',str(result.get('after_revision',''))):
        raise ChangeFailure('invalid_remote_receipt')
    before,after=result.get('before'),result.get('after')
    if not isinstance(before,dict) or set(before)!=set(proposed_fields(change)) or not isinstance(after,dict): raise ChangeFailure('invalid_remote_receipt')
    for field,value in before.items():
        if not isinstance(value,dict) or type(value.get('exists')) is not bool or not isinstance(value.get('value'),str) or len(value['value'])>1000:
            raise ChangeFailure('invalid_remote_receipt')
        if value['value']!=change.base_metadata.get(field,''): raise ChangeFailure('remote_snapshot_mismatch')
    if set(after)-{'title','description','og_title','og_description'} or any(not isinstance(v,str) or len(v)>1000 for v in after.values()):
        raise ChangeFailure('invalid_remote_receipt')
    if any(after.get(k)!=v for k,v in proposed_fields(change).items()): raise ChangeFailure('remote_applied_value_mismatch')
    receipt={key:result[key] for key in ('change_id','post_id','state','before_revision','after_revision','before','after')}
    if change.page.target_kind!='post': receipt['target_kind']=change.page.target_kind
    return receipt

@shared_task(queue='metadata-fixture',time_limit=120,soft_time_limit=110)
def execute_metadata_change(attempt_id):
    lease=uuid.uuid4()
    with transaction.atomic():
        attempt=PublishAttempt.objects.select_for_update().select_related('change__site','change__page','actor').get(pk=attempt_id)
        if attempt.state not in ('queued','running','applied_pending_verification'): return
        change=attempt.change;page=Page.objects.select_for_update().get(pk=change.page_id)
        if page.publication_lease_until and page.publication_lease_until>timezone.now(): return
        try: local_write_guard(change,attempt.actor,attempt.operation)
        except (ChangeFailure,ConnectionFailure) as error:
            attempt.state='cancelled';attempt.error_code=str(error);attempt.finished_at=timezone.now();attempt.save()
            change.state='cancelled';change.error_code=str(error);change.save(update_fields=['state','error_code']);return
        page.publication_lease=lease;page.publication_lease_until=timezone.now()+timedelta(minutes=6);page.save(update_fields=['publication_lease','publication_lease_until'])
        attempt.state='running';attempt.save(update_fields=['state'])
        change.state='applying' if attempt.operation=='apply' else 'restoring';change.save(update_fields=['state'])
    try:
        change=ChangeSet.objects.select_related('site','page').get(pk=change.pk)
        connection=local_write_guard(change,User.objects.get(pk=attempt.actor_id),attempt.operation)
        try: result=wordpress_get(connection,change_path(change,str(change.pk)))
        except ConnectionFailure as error:
            if str(error)!='remote_change_not_found': raise
            result=None
        if attempt.operation=='apply':
            if result is None:
                remote=remote_metadata(connection,change.page)
                if remote['revision']!=change.base_revision: raise ChangeFailure('stale_remote_revision')
                public=read_public_head(change.site,change.page.url)
                if public['status']!=200: raise ChangeFailure('baseline_public_page_unavailable')
                ChangeSet.objects.filter(pk=change.pk).update(public_before=public)
                change.public_before=public
                payload={'change_id':str(change.pk),'post_id':change.page.wordpress_id,'expected_revision':change.base_revision,
                    'changes':proposed_fields(change),'approval_hash':change.payload_hash}
                wordpress_request(connection,change_path(change,'preview'),'POST',payload)
                # Re-read policy, pause, actor and approval after public/network preflight.
                change=ChangeSet.objects.select_related('site','page').get(pk=change.pk)
                connection=local_write_guard(change,User.objects.get(pk=attempt.actor_id),'apply')
                result=wordpress_request(connection,change_path(change,'apply'),'POST',payload)
            receipt=checked_receipt(change,result)
            if receipt['state']!='applied': raise ChangeFailure('remote_change_already_restored')
        else:
            if result is None: raise ChangeFailure('remote_restore_ledger_missing')
            receipt=checked_receipt(change,result)
            if receipt['state']!='restored':
                connection=local_write_guard(change,User.objects.get(pk=attempt.actor_id),'restore')
                receipt=checked_receipt(change,wordpress_request(connection,change_path(change,f'{change.pk}/restore'),'POST',{}))
        # An API success is not a public verification. Save receipt before fetching HTML.
        with transaction.atomic():
            PublishAttempt.objects.filter(pk=attempt.pk).update(receipt=receipt,state='applied_pending_verification')
            ChangeSet.objects.filter(pk=change.pk).update(state='applied_pending_verification' if attempt.operation=='apply' else 'restoring')
        head=read_public_head(change.site,change.page.url)
        errors=verify_head(change,head,restoring=attempt.operation=='restore')
        state=('restored' if attempt.operation=='restore' else 'verified') if not errors else ('restoration_failed' if attempt.operation=='restore' else 'verification_failed')
        ChangeSet.objects.filter(pk=change.pk).update(state=state,error_code=','.join(errors),verification={'operation':attempt.operation,'head':head,'errors':errors,'checked_at':timezone.now().isoformat()})
        PublishAttempt.objects.filter(pk=attempt.pk).update(state='succeeded',finished_at=timezone.now())
        AuditEvent.objects.create(site=change.site,organization=change.site.organization,actor_id=attempt.actor_id,
            action='change.'+state,target=str(change.pk))
    except (ChangeFailure,ConnectionFailure) as error:
        code=str(error)
        conflict=code in ('stale_remote_revision','remote_revision_or_payload_conflict','remote_snapshot_mismatch')
        ambiguous=code=='wordpress_connection_failed'
        state=('restoration_conflict' if attempt.operation=='restore' else 'stale_conflict') if conflict else ('restoration_failed' if attempt.operation=='restore' else ('ambiguous_remote_result' if ambiguous else 'retryable_failure'))
        ChangeSet.objects.filter(pk=change.pk).update(state=state,error_code=code)
        PublishAttempt.objects.filter(pk=attempt.pk).update(state='ambiguous' if ambiguous else 'failed',error_code=code,finished_at=timezone.now())
    except Exception:
        # A crash after a remote call must be reconciled, never blindly retried.
        ChangeSet.objects.filter(pk=change.pk).update(state='ambiguous_remote_result' if attempt.operation=='apply' else 'restoration_failed',error_code='execution_interrupted_reconcile_required')
        PublishAttempt.objects.filter(pk=attempt.pk).update(state='ambiguous',error_code='execution_interrupted_reconcile_required',finished_at=timezone.now())
    finally:
        Page.objects.filter(pk=change.page_id,publication_lease=lease).update(publication_lease=None,publication_lease_until=None)
