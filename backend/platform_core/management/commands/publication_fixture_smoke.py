import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from platform_core.models import Organization,User,Membership,Site,Page,KnowledgeSource,ChangeSet
from platform_core.connections import save_connection,check_connection,sync_inventory,wordpress_get,wordpress_request,ConnectionFailure
from platform_core.changes import save_draft,submit,approve,enqueue_change
from platform_core.publish_tasks import execute_metadata_change

class Command(BaseCommand):
    help='Full metadata review/apply/verify/restore against the local WP fixture; temporary app records are rolled back.'

    @transaction.atomic
    def handle(self,*args,**options):
        if not (settings.DEBUG and settings.LOCAL_PUBLICATION_ENABLED and settings.CONNECTOR_LOCAL_FIXTURE_ENABLED): raise CommandError('Explicit local publication fixture mode required.')
        credentials=json.loads(sys.stdin.read(4096));key=uuid.uuid4().hex
        org=Organization.objects.create(name='SYNTHETIC temporary metadata review')
        actors=[]
        for name in ['editor','reviewer']:
            actor=User(username=f'{name}-{key}',email=f'{name}-{key}@example.test');actor.set_unusable_password();actor.save()
            Membership.objects.create(organization=org,user=actor,role='owner');actors.append(actor)
        editor,reviewer=actors
        site=Site.objects.create(organization=org,name='SYNTHETIC local metadata review',url='http://wordpress',environment='staging',paused=False,verified_facts='Synthetic local test page.')
        connection=save_connection(site,editor,credentials['username'],credentials['password'])
        report=check_connection(site,editor)
        if not report.get('remote_write'): raise CommandError('Fixture metadata writes are disabled.')
        connection.refresh_from_db();sync_inventory(site,editor)
        page=Page.objects.get(site=site,wordpress_id=credentials['post_id'])
        source=KnowledgeSource.objects.create(site=site,url=page.url,title='Synthetic fixture source',excerpt='Synthetic test page facts.',content_hash='a'*64,source_type='owner_provided')
        change=save_draft(site,page,editor,{'title':'SYNTHETIC Reviewed SEO Title','description':'Synthetic reviewed metadata description for the local publication fixture.'},[source],'Synthetic local review smoke')
        submit(change,editor);approve(change,reviewer)
        attempt=enqueue_change(change,editor)
        execute_metadata_change.run(str(attempt.pk));change.refresh_from_db()
        if change.state!='verified': raise CommandError('Local apply/public verification failed: '+change.error_code)
        self.stdout.write('Separate-author review, approved apply and actual public HTML verification passed.')
        # A durable unique ledger must survive simultaneous HTTP requests, not only cache locks.
        current=wordpress_get(connection,f'pages/{page.wordpress_id}/seo')
        concurrent_id=str(uuid.uuid4())
        payload={'change_id':concurrent_id,'post_id':page.wordpress_id,'expected_revision':current['revision'],
            'changes':{'description':'SYNTHETIC temporary concurrent editor metadata.'},'approval_hash':'b'*64}
        # Cache the relation before sharing the immutable connection object with HTTP threads.
        connection.site
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:wordpress_request(connection,'changes/apply','POST',payload),range(2)))
        if any(r.get('change_id')!=concurrent_id for r in results) or len({r['after_revision'] for r in results})!=1:
            raise CommandError('Concurrent same-key ledger replay failed.')
        try:
            wordpress_request(connection,f'changes/{change.pk}/restore','POST',{})
            raise CommandError('Conflict restore unexpectedly overwrote the later edit.')
        except ConnectionFailure as error:
            if str(error)!='remote_revision_or_payload_conflict': raise
        wordpress_request(connection,f'changes/{concurrent_id}/restore','POST',{})
        self.stdout.write('Concurrent duplicate request replay and later-edit restore conflict passed.')
        restore=enqueue_change(change,editor,'restore')
        execute_metadata_change.run(str(restore.pk));change.refresh_from_db()
        if change.state!='restored': raise CommandError('Local restore/public verification failed: '+change.error_code)
        restored=wordpress_get(connection,f'pages/{page.wordpress_id}/seo')
        if restored['revision']!=change.base_revision: raise CommandError('Restored WordPress revision mismatch.')
        transaction.set_rollback(True)
        self.stdout.write('Conflict-free restore and actual original public HTML verified. Temporary application records rolled back; no live site touched.')
