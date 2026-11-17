import json
import sys
import time
import uuid
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from platform_core.models import Organization,User,Membership,Site,Page,KnowledgeSource,ChangeSet,PublishAttempt,AuditEvent
from platform_core.connections import save_connection,check_connection,sync_inventory,wordpress_get,wordpress_request
from platform_core.changes import save_draft,submit,approve,enqueue_change

class Command(BaseCommand):
    help='Prove committed durable publication attempts are executed by the isolated Celery fixture queue, then remove temporary app records.'

    def wait(self,change,wanted):
        deadline=time.monotonic()+145
        while time.monotonic()<deadline:
            change.refresh_from_db()
            if change.state==wanted: return
            if change.state in ['cancelled','retryable_failure','ambiguous_remote_result','stale_conflict','verification_failed','restoration_failed','restoration_conflict']:
                raise CommandError('Fixture worker did not reach '+wanted+': '+change.error_code)
            time.sleep(1)
        raise CommandError('Fixture worker timed out before '+wanted)

    def handle(self,*args,**options):
        if not (settings.DEBUG and settings.LOCAL_PUBLICATION_ENABLED and settings.CONNECTOR_LOCAL_FIXTURE_ENABLED): raise CommandError('Explicit local fixture mode required.')
        credentials=json.loads(sys.stdin.read(4096));key=uuid.uuid4().hex
        org=Organization.objects.create(name='SYNTHETIC temporary Celery publication')
        actors=[];change=None;connection=None
        try:
            for name in ['editor','reviewer']:
                actor=User(username=f'{name}-{key}',email=f'{name}-{key}@example.test');actor.set_unusable_password();actor.save()
                Membership.objects.create(organization=org,user=actor,role='owner');actors.append(actor)
            editor,reviewer=actors
            site=Site.objects.create(organization=org,name='SYNTHETIC Celery local publication',url='http://wordpress',environment='staging',paused=False)
            connection=save_connection(site,editor,credentials['username'],credentials['password'])
            check_connection(site,editor);connection.refresh_from_db();sync_inventory(site,editor)
            page=Page.objects.get(site=site,wordpress_id=credentials['post_id'])
            source=KnowledgeSource.objects.create(site=site,url=page.url,title='Synthetic queue fixture',excerpt='Synthetic facts only.',content_hash='b'*64,source_type='owner_provided')
            change=save_draft(site,page,editor,{'title':'SYNTHETIC Celery Reviewed Title','description':'Synthetic metadata executed through the isolated Celery queue.'},[source],'Synthetic worker smoke')
            submit(change,editor);approve(change,reviewer)
            enqueue_change(change,editor)
            self.wait(change,'verified')
            self.stdout.write('Durable queued apply executed by Celery; public HTML verified.')
            enqueue_change(change,editor,'restore')
            self.wait(change,'restored')
            original=wordpress_get(connection,f'pages/{page.wordpress_id}/seo')
            if original['revision']!=change.base_revision: raise CommandError('Queued restoration revision mismatch.')
            self.stdout.write('Durable queued restore executed by Celery; original HTML/revision verified.')
        finally:
            if change and connection:
                try:
                    result=wordpress_get(connection,f'changes/{change.pk}')
                    if result.get('state')=='applied': wordpress_request(connection,f'changes/{change.pk}/restore','POST',{})
                except Exception: pass  # Never force overwrite when the connector reports a later-edit conflict.
            PublishAttempt.objects.filter(change__site__organization=org).delete()
            ChangeSet.objects.filter(site__organization=org).delete()
            AuditEvent.objects.filter(organization=org).delete()
            org.delete()
            User.objects.filter(pk__in=[a.pk for a in actors]).delete()
        self.stdout.write('Temporary queue fixture application records removed; no live site touched.')
