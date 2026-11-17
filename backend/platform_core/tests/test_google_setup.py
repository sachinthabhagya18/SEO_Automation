import json
from unittest.mock import patch
import pytest
import httpx
from platform_core.models import SearchConsoleSetup
from platform_core.google_setup import lookup_txt,site_domain
from .test_authorization import portfolio

TOKEN='google-site-verification=synthetic-token-12345'

def test_setup_access_and_google_issued_token_required(client,portfolio):
    p=portfolio;client.force_login(p['staff'])
    assert client.get(f'/sites/{p["a"].pk}/google/').status_code==404
    client.force_login(p['owner'])
    assert client.get(f'/sites/{p["c"].pk}/google/').status_code==404
    path=f'/sites/{p["a"].pk}/google/'
    assert client.get(path).status_code==200
    response=client.post(path,{'operation':'save','txt_value':'not-a-verification-token'})
    assert response.status_code==200 and not SearchConsoleSetup.objects.exists()
    assert client.post(path,{'operation':'save','txt_value':TOKEN}).status_code==302
    record=SearchConsoleSetup.objects.get(site=p['a'])
    assert record.domain=='assigned.example.test' and not record.dns_observed

def test_dns_match_is_not_claimed_as_google_verification(client,portfolio):
    p=portfolio;client.force_login(p['owner']);path=f'/sites/{p["a"].pk}/google/'
    client.post(path,{'operation':'save','txt_value':TOKEN})
    with patch('platform_core.google_setup.lookup_txt',return_value=[TOKEN]):
        assert client.post(path,{'operation':'check'}).status_code==302
    record=SearchConsoleSetup.objects.get(site=p['a'])
    assert record.dns_observed and record.checked_at and not hasattr(record,'google_verified')
    assert b'DNS observation is not Google verification' in client.get(path).content

def test_changed_domain_blocks_old_token_dns_lookup(client,portfolio):
    p=portfolio;client.force_login(p['owner']);path=f'/sites/{p["a"].pk}/google/'
    client.post(path,{'operation':'save','txt_value':TOKEN})
    p['a'].url='https://changed.example.test';p['a'].save()
    with patch('platform_core.google_setup.lookup_txt') as dns:
        client.post(path,{'operation':'check'})
    assert not dns.called and TOKEN.encode() not in client.get(path).content

def test_doh_parses_only_exact_domain_txt_and_joins_fragments():
    payload={'Status':0,'Answer':[{'name':'example.test.','type':16,'data':'"google-site-verification=" "synthetic-token-12345"'},
        {'name':'other.test.','type':16,'data':'"foreign-token"'}]}
    calls=[]
    def reply(request):
        calls.append(request)
        return httpx.Response(200,json=payload)
    actual=httpx.Client(transport=httpx.MockTransport(reply))
    with patch('platform_core.google_setup.httpx.Client',return_value=actual):
        assert lookup_txt('example.test')==[TOKEN]
    assert calls[0].url.host=='cloudflare-dns.com' and 'name=example.test' in str(calls[0].url)

def test_ip_address_is_not_a_domain_property(portfolio):
    site=portfolio['a'];site.url='https://127.0.0.1'
    with pytest.raises(ValueError): site_domain(site)
