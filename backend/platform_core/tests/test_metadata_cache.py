import uuid
from unittest.mock import patch
import pytest
from platform_core.models import Page
from platform_core.metadata_cache import queue_read,refresh_metadata
from platform_core.changes import save_draft
from .test_authorization import portfolio
from .test_changes import review

def test_cached_read_is_scoped_and_has_no_remote_call(review,client,settings):
    settings.SECURE_SSL_REDIRECT=False
    p=review;client.force_login(p['owner'])
    with patch('platform_core.changes.wordpress_get') as remote:
        response=client.get(f"/sites/{p['a'].pk}/pages/{p['page'].pk}/metadata/")
    assert response.status_code==200 and response.json()['ready'] and not remote.called
    assert response.json()['stored']['title']=='Before title'
    assert response.headers['Cache-Control']=='private, no-store'
    assert client.get(f"/sites/{p['b'].pk}/pages/{p['page'].pk}/metadata/").status_code==404

def test_connection_rotation_hides_old_cache(review,client,settings):
    settings.SECURE_SSL_REDIRECT=False
    p=review;connection=p['connection'];connection.credential_version=uuid.uuid4();connection.save()
    client.force_login(p['owner'])
    data=client.get(f"/sites/{p['a'].pk}/pages/{p['page'].pk}/metadata/").json()
    assert not data['ready'] and data['stored']=={}

def test_queue_deduplicates_and_revocation_blocks_read(review):
    p=review
    with patch('platform_core.metadata_cache.dispatch_read'):
        first=queue_read(p['page'],p['staff'])
        assert queue_read(p['page'],p['staff'])==first
    p['membership'].active=False;p['membership'].save()
    with patch('platform_core.changes.remote_metadata') as remote:
        refresh_metadata(p['page'].pk,str(first))
    p['page'].refresh_from_db()
    assert not remote.called and p['page'].metadata_load_state=='cancelled'

def test_worker_persists_valid_snapshot_and_save_still_reads_fresh(review):
    p=review
    with patch('platform_core.metadata_cache.dispatch_read'):
        token=queue_read(p['page'],p['owner'])
    current={**p['baseline'],'revision':'b'*64,'stored':{'title':'New server title','description':'New server description'}}
    with patch('platform_core.changes.wordpress_get',return_value=current) as remote:
        refresh_metadata(p['page'].pk,str(token))
        p['page'].refresh_from_db()
        assert p['page'].metadata_snapshot['stored']['title']=='New server title'
        assert p['page'].metadata_load_state=='ready'
        save_draft(p['a'],p['page'],p['owner'],{'title':'Proposed'},[p['source']])
        assert remote.call_count==2

def test_late_response_cannot_cache_rotated_connection(review):
    p=review
    with patch('platform_core.metadata_cache.dispatch_read'):
        token=queue_read(p['page'],p['owner'])
    def rotate(*args,**kwargs):
        c=p['connection'];c.credential_version=uuid.uuid4();c.save()
        return p['baseline']
    with patch('platform_core.changes.remote_metadata',side_effect=rotate):
        refresh_metadata(p['page'].pk,str(token))
    p['page'].refresh_from_db()
    assert p['page'].metadata_load_state=='cancelled'
