import logging
from urllib.parse import urlsplit,parse_qs
from unittest.mock import patch
from datetime import timedelta
import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from platform_core.models import GoogleConnection,GoogleOAuthIntent
from platform_core import google_search as google
from platform_core.log_filters import CallbackLogFilter
from .test_authorization import portfolio

@pytest.fixture
def google_setup(portfolio,settings):
    settings.SECURE_SSL_REDIRECT=False;settings.DEBUG=True
    settings.CONNECTION_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]
    settings.GOOGLE_OAUTH_CLIENT_ID='synthetic-client.apps.googleusercontent.com'
    settings.GOOGLE_OAUTH_CLIENT_SECRET='synthetic-secret'
    settings.GOOGLE_OAUTH_REDIRECT_URI='http://localhost:8000/integrations/google/callback/'
    return portfolio

def consent(p):
    intent,url=google.start_authorization(p['a'],p['owner'])
    return intent,parse_qs(urlsplit(url).query)['state'][0]

def token_reply():
    return {'access_token':'synthetic-access','refresh_token':'synthetic-refresh','token_type':'Bearer','expires_in':3600,'scope':google.SCOPE}

def connected(p):
    intent,state=consent(p)
    with patch('platform_core.google_search.request_json',return_value=token_reply()):
        connection=google.complete_authorization(p['owner'],str(intent.pk),state,'synthetic-code')
    return connection

def test_oauth_uses_state_pkce_readonly_scope_and_encrypted_tokens(google_setup):
    p=google_setup;intent,state=consent(p)
    assert state not in intent.state_digest and 'verifier' not in intent.encrypted_verifier
    with patch('platform_core.google_search.request_json',return_value=token_reply()) as http:
        connection=google.complete_authorization(p['owner'],str(intent.pk),state,'synthetic-code')
    assert connection.status=='authorized' and 'synthetic-access' not in connection.encrypted_tokens
    assert google.decode_secret(connection.encrypted_tokens)['refresh_token']=='synthetic-refresh'
    assert http.call_args.kwargs['data']['code_verifier']
    with pytest.raises(google.GoogleFailure,match='invalid_or_expired_state'):
        google.complete_authorization(p['owner'],str(intent.pk),state,'synthetic-code')

def test_wrong_session_or_actor_cannot_exchange_code(google_setup):
    p=google_setup;intent,state=consent(p)
    with patch('platform_core.google_search.request_json') as http:
        for actor,session in [(p['owner'],'wrong'),(p['staff'],str(intent.pk))]:
            with pytest.raises(google.GoogleFailure): google.complete_authorization(actor,session,state,'synthetic')
    assert not http.called

def test_expiry_url_change_and_revocation_invalidate_consent(google_setup):
    p=google_setup;intent,state=consent(p)
    intent.expires_at=timezone.now()-timedelta(seconds=1);intent.save()
    with pytest.raises(google.GoogleFailure): google.complete_authorization(p['owner'],str(intent.pk),state,'code')
    intent,state=consent(p);p['a'].url='https://changed.example.test';p['a'].save()
    with pytest.raises(google.GoogleFailure,match='context_changed'): google.complete_authorization(p['owner'],str(intent.pk),state,'code')

def test_revoked_membership_mid_exchange_prevents_token_save(google_setup):
    p=google_setup;intent,state=consent(p)
    def revoke(*a,**kw):
        p['owner'].is_active=False;p['owner'].save()
        return token_reply()
    with patch('platform_core.google_search.request_json',side_effect=revoke):
        with pytest.raises(google.GoogleFailure): google.complete_authorization(p['owner'],str(intent.pk),state,'code')
    assert not GoogleConnection.objects.get(site=p['a']).encrypted_tokens

def test_property_selection_refuses_foreign_and_unverified_entries(google_setup):
    p=google_setup;c=connected(p)
    result={'siteEntry':[{'siteUrl':'sc-domain:assigned.example.test','permissionLevel':'siteOwner'},
        {'siteUrl':'sc-domain:foreign.example.test','permissionLevel':'siteOwner'},
        {'siteUrl':p['a'].url,'permissionLevel':'siteUnverifiedUser'}]}
    with patch('platform_core.google_search.request_json',return_value=result):
        entries=google.list_properties(c,p['owner']);assert len(entries)==1
        with pytest.raises(google.GoogleFailure): google.select_property(c,p['owner'],'sc-domain:foreign.example.test')
        selected=google.select_property(c,p['owner'],'sc-domain:assigned.example.test')
    assert selected.status=='connected' and selected.credential_version!=c.credential_version

def test_revocation_erases_local_tokens_and_invalidates_pending_intents(google_setup):
    p=google_setup;c=connected(p);intent,state=consent(p)
    google.revoke(c,p['owner']);c.refresh_from_db();intent.refresh_from_db()
    assert c.status=='revoked' and not c.encrypted_tokens and intent.used_at
    with patch('platform_core.google_search.request_json') as http:
        with pytest.raises(google.GoogleFailure): google.access_token(c)
    assert not http.called

def test_callback_does_not_redirect_code_to_login_and_logs_are_redacted(google_setup,client):
    response=client.get('/integrations/google/callback/?code=secret-code&state=secret-state')
    assert response.status_code==400 and b'secret-code' not in response.content and 'Location' not in response
    record=logging.LogRecord('django.server',logging.INFO,'',0,'GET /integrations/google/callback/?code=%s&state=%s HTTP/1.1',('secret-code','secret-state'),None)
    CallbackLogFilter().filter(record)
    assert 'secret-code' not in record.getMessage() and 'secret-state' not in record.getMessage()

def test_client_secret_is_never_rendered(google_setup,client):
    p=google_setup;client.force_login(p['owner'])
    response=client.get(f"/sites/{p['a'].pk}/google/connection/")
    assert response.status_code==200 and b'synthetic-secret' not in response.content

def test_expired_access_token_refresh_preserves_offline_token(google_setup):
    p=google_setup;c=connected(p);tokens=google.decode_secret(c.encrypted_tokens)
    tokens['expires_at']=(timezone.now()-timedelta(seconds=1)).isoformat()
    c.encrypted_tokens=google.encode_secret(tokens);c.save()
    with patch('platform_core.google_search.request_json',return_value={'access_token':'refreshed-access','token_type':'Bearer','expires_in':3600}) as http:
        assert google.access_token(c)=='refreshed-access'
    c.refresh_from_db()
    assert google.decode_secret(c.encrypted_tokens)['refresh_token']=='synthetic-refresh'
    assert http.call_args.kwargs['data']['grant_type']=='refresh_token'
