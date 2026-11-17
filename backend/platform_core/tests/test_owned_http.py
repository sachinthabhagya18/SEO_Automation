import base64
from unittest.mock import Mock,patch
import pytest
from cryptography.fernet import Fernet
from platform_core.connections import save_connection
from platform_core.owned_http import site_fetch
from platform_core.public_http import FetchError,fetch_public,Target
from .test_authorization import portfolio

@pytest.fixture
def protected(portfolio,settings):
    p=portfolio;settings.CONNECTION_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]
    settings.PROTECTED_STAGING_HOSTS=['assigned.example.test']
    c=save_connection(p['a'],p['owner'],'reader','synthetic-password');c.status='connected';c.save()
    return p,c

def test_protected_read_uses_bound_credentials_without_redirects(protected):
    p,c=protected;transport=Mock()
    site_fetch(p['a'],p['a'].url+'/product/',fetch=transport,max_redirects=3)
    args=transport.call_args.kwargs
    assert args['max_redirects']==0 and args['authorization']=='Basic '+base64.b64encode(b'reader:synthetic-password').decode()

def test_protected_origin_and_revocation_fail_before_fetch(protected):
    p,c=protected;transport=Mock()
    for url in ['https://foreign.example.test/','http://assigned.example.test/','https://assigned.example.test:444/']:
        with pytest.raises(FetchError): site_fetch(p['a'],url,fetch=transport)
    c.status='revoked';c.save()
    with pytest.raises(FetchError): site_fetch(p['a'],p['a'].url,fetch=transport)
    assert not transport.called

def test_production_public_read_does_not_receive_credentials(protected):
    p,c=protected;p['a'].environment='production';p['a'].save()
    transport=Mock();site_fetch(p['a'],p['a'].url,fetch=transport)
    assert 'authorization' not in transport.call_args.kwargs

def test_auth_redirect_is_not_followed():
    target=Target('https://owned.example.test/','https','owned.example.test',443,'/',2,'8.8.8.8')
    with patch('platform_core.public_http.resolve_target',return_value=target),patch('platform_core.public_http.PinnedConnection') as factory:
        response=factory.return_value.getresponse.return_value;response.status=302
        response.getheaders.return_value=[('Location','https://foreign.example.test/')]
        with pytest.raises(FetchError): fetch_public(target.url,max_redirects=0,authorization='Basic synthetic')
        assert factory.call_count==1
        assert factory.return_value.request.call_args.kwargs['headers']['Authorization']=='Basic synthetic'

def test_cleartext_auth_is_refused_before_dns():
    with patch('platform_core.public_http.resolve_target') as resolve:
        with pytest.raises(FetchError): fetch_public('http://owned.example.test/',max_redirects=0,authorization='Basic synthetic')
    assert not resolve.called

def test_private_staging_binding_is_fixed_and_idempotent(protected):
    import io,json
    from django.core.management import call_command,CommandError
    from platform_core.models import Site,SiteConnection
    p,c=protected
    data={'url':'https://foreign.example.test','connector_accounts':{'reader':{'username':'seo-staging-reader','application_password':'synthetic-staging-password'}}}
    with patch('sys.stdin',io.StringIO(json.dumps(data))):
        with pytest.raises(CommandError): call_command('bind_staging_connection',source_site=p['a'].pk)
    data['url']='https://staging.denimyard.com';out=io.StringIO()
    for _ in range(2):
        with patch('sys.stdin',io.StringIO(json.dumps(data))): call_command('bind_staging_connection',source_site=p['a'].pk,stdout=out)
    site=Site.objects.get(url=data['url'])
    assert site.paused and site.environment=='staging' and SiteConnection.objects.filter(site=site).count()==1
    assert 'synthetic-staging-password' not in out.getvalue()

def test_explicit_origin_requires_global_ip_and_ca(protected,settings,tmp_path):
    from platform_core.staging_origin import staging_target
    p,c=protected;ca=tmp_path/'public-ca.pem';ca.write_text('SYNTHETIC public certificate placeholder')
    settings.PROTECTED_STAGING_ORIGINS={'assigned.example.test':{'address':'8.8.8.8','ca_file':str(ca)}}
    target=staging_target(p['a'],p['a'].url+'/product/')
    assert target.address=='8.8.8.8' and target.hostname=='assigned.example.test' and target.ca_file==str(ca)
    settings.PROTECTED_STAGING_ORIGINS['assigned.example.test']['address']='127.0.0.1'
    with pytest.raises(FetchError): staging_target(p['a'],p['a'].url)
    p['a'].environment='production'
    assert staging_target(p['a'],p['a'].url) is None

def test_pinned_tls_keeps_hostname_verification_with_explicit_ca():
    import socket
    from platform_core.public_http import PinnedConnection
    target=Target('https://stage.example.test/','https','stage.example.test',443,'/',socket.AF_INET,'8.8.8.8','/operator/public-ca.pem')
    with patch('platform_core.public_http.socket.socket') as sockets,patch('platform_core.public_http.ssl.create_default_context') as context:
        PinnedConnection(target,3).connect()
    context.assert_called_once_with(cafile='/operator/public-ca.pem')
    assert context.return_value.wrap_socket.call_args.kwargs['server_hostname']=='stage.example.test'

def test_pinned_https_host_omits_default_port_and_preserves_explicit_fixture_host():
    import socket
    from platform_core.public_http import PinnedConnection
    target=Target('https://stage.example.test/','https','stage.example.test',443,'/',socket.AF_INET,'8.8.8.8')
    with patch('http.client.HTTPConnection.request') as request:
        PinnedConnection(target,3).request('GET','/')
        assert request.call_args.kwargs['headers']['Host']=='stage.example.test'
        PinnedConnection(target,3).request('GET','/',headers={'Host':'localhost:8081'})
        assert request.call_args.kwargs['headers']['Host']=='localhost:8081'
