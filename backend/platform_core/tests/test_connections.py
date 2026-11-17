import json
from unittest.mock import patch, Mock
import pytest
from cryptography.fernet import Fernet
from django.urls import reverse
from .test_authorization import portfolio
from platform_core.connections import save_connection, check_connection, sync_inventory, decrypt_credentials, wordpress_get, ConnectionFailure, connector_target
from platform_core.models import SiteConnection, Page

@pytest.fixture(autouse=True)
def encryption_key(settings):
    settings.CONNECTION_ENCRYPTION_KEYS = [Fernet.generate_key().decode()]

def test_connection_credentials_encrypted_and_never_rendered(client, portfolio):
    p=portfolio
    connection=save_connection(p['a'],p['owner'],'reader','not-a-real-application-password')
    assert 'not-a-real-application-password' not in connection.encrypted_credentials
    assert decrypt_credentials(connection)['username']=='reader'
    client.force_login(p['owner'])
    response=client.get(reverse('site-connection',kwargs={'pk':p['a'].pk}))
    assert response.status_code==200
    assert 'not-a-real-application-password' not in response.content.decode()
    response=client.get(f'/api/v1/sites/{p["a"].pk}/')
    assert 'encrypted_credentials' not in response.content.decode()

def test_reader_cannot_manage_credentials_or_access_foreign_site(client,portfolio):
    p=portfolio
    client.force_login(p['staff'])
    assert client.get(f'/sites/{p["a"].pk}/connection/').status_code==404
    client.force_login(p['owner'])
    assert client.post(f'/sites/{p["c"].pk}/connection/',{'operation':'save','username':'x','application_password':'x'}).status_code==404

def test_capabilities_and_inventory_check_current_permissions(portfolio):
    p=portfolio
    connection=save_connection(p['a'],p['owner'],'reader','fixture-only')
    report={'protocol_version':1,'operations':['inventory_read','seo_read'],'plugin_version':'0.1.0','wordpress_version':'7.1.4','mode':'standalone','remote_write':False}
    with patch('platform_core.connections.wordpress_get',return_value=report):
        check_connection(p['a'],p['owner'])
    connection.refresh_from_db()
    assert connection.status=='connected'
    with patch('platform_core.connections.wordpress_get',return_value={'items':[{'url':p['a'].url+'/product/synthetic'}],'pages':1}):
        assert sync_inventory(p['a'],p['owner'])==1
    assert Page.objects.filter(site=p['a']).count()==1
    with pytest.raises(ConnectionFailure): sync_inventory(p['a'],p['staff'])

def test_remote_secrets_not_saved_in_capability_envelope(portfolio):
    p=portfolio
    connection=save_connection(p['a'],p['owner'],'reader','fixture-only')
    with patch('platform_core.connections.wordpress_get',return_value={'protocol_version':1,'operations':['inventory_read'],'password':'remote-secret'}):
        check_connection(p['a'],p['owner'])
    connection.refresh_from_db()
    assert 'password' not in connection.capabilities

def test_private_https_and_nonhttps_targets_rejected():
    with pytest.raises(ConnectionFailure): connector_target('http://example.test','capabilities')
    with pytest.raises(ConnectionFailure): connector_target('https://user:pass@example.test','capabilities')
    import socket
    with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))]):
        with pytest.raises(ConnectionFailure,match='public_https_target_required'):
            connector_target('https://example.test','capabilities')

def test_authenticated_requests_never_follow_redirects(portfolio):
    p=portfolio
    connection=save_connection(p['a'],p['owner'],'reader','fixture-only')
    response=Mock(status=302)
    client=Mock()
    client.getresponse.return_value=response
    target=Mock(path='/wp-json/company-seo/v1/capabilities')
    with patch('platform_core.connections.connector_target',return_value=target),patch('platform_core.connections.PinnedConnection',return_value=client):
        with pytest.raises(ConnectionFailure,match='redirect_not_allowed'): wordpress_get(connection,'capabilities')
    assert client.request.call_count==1

def test_inventory_rejects_foreign_host(portfolio):
    p=portfolio
    connection=save_connection(p['a'],p['owner'],'reader','fixture-only')
    connection.status='connected';connection.save()
    with patch('platform_core.connections.wordpress_get',return_value={'items':[{'url':'https://foreign.example.test/'}],'pages':1}):
        with pytest.raises(ConnectionFailure,match='foreign_inventory_url'): sync_inventory(p['a'],p['owner'])
    assert not Page.objects.filter(site=p['a']).exists()

def test_site_url_edit_never_forwards_existing_credentials_to_new_domain(portfolio):
    from platform_core.connections import connection_status
    p=portfolio
    connection=save_connection(p['a'],p['owner'],'reader','fixture-only')
    p['a'].url='https://other.example.test';p['a'].save()
    connection.refresh_from_db()
    assert connection_status(p['a'])=='url_changed'
    with patch('platform_core.connections.PinnedConnection') as network:
        with pytest.raises(ConnectionFailure,match='site_url_changed_resave_credentials'):
            wordpress_get(connection,'capabilities')
    assert not network.called
