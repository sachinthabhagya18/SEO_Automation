"""Read-only Google authorization and bounded transport. Never logs tokens."""
import base64,hashlib,json,secrets,uuid,time
from datetime import datetime,timedelta
from urllib.parse import urlencode,urlsplit,quote
import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .connections import cipher
from .models import GoogleConnection,GoogleOAuthIntent,AuditEvent
from .permissions import can

SCOPE='https://www.googleapis.com/auth/webmasters.readonly'
API='https://www.googleapis.com/webmasters/v3/'
TOKEN='https://oauth2.googleapis.com/token'

class GoogleFailure(ValueError): pass

def configured():
    parts=urlsplit(settings.GOOGLE_OAUTH_REDIRECT_URI)
    secure=parts.scheme=='https' or (settings.DEBUG and parts.scheme=='http' and parts.hostname in ('localhost','127.0.0.1'))
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET and secure and
        parts.path=='/integrations/google/callback/' and not parts.username and not parts.password and not parts.query and not parts.fragment)

def encode_secret(value): return cipher().encrypt(json.dumps(value).encode()).decode()
def decode_secret(value):
    try: return json.loads(cipher().decrypt(value.encode()))
    except Exception: raise GoogleFailure('google_token_decryption_failed') from None

def request_json(url,*,method='GET',data=None,body=None,token=None):
    if not (url==TOKEN or url.startswith(API)):
        raise GoogleFailure('google_origin_refused')
    try:
        with httpx.Client(timeout=20,trust_env=False,follow_redirects=False) as client:
            headers={'Accept':'application/json'}
            if token: headers['Authorization']='Bearer '+token
            with client.stream(method,url,data=data,json=body,headers=headers) as response:
                if response.status_code!=200: raise GoogleFailure(f'google_http_{response.status_code}')
                raw=bytearray()
                deadline=time.monotonic()+30
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw)>2_000_000 or time.monotonic()>deadline: raise GoogleFailure('google_response_too_large_or_slow')
        result=json.loads(raw)
        if not isinstance(result,dict): raise GoogleFailure('google_invalid_response')
        if 'error' in result: raise GoogleFailure('google_api_error_response')
        return result
    except GoogleFailure: raise
    except Exception: raise GoogleFailure('google_network_or_response_failed') from None

def token_values(result,refresh_token=None):
    access=result.get('access_token');refresh=result.get('refresh_token') or refresh_token;expires=result.get('expires_in')
    if not isinstance(access,str) or not 1<=len(access)<=8192 or not isinstance(refresh,str) or not 1<=len(refresh)<=8192 \
        or result.get('token_type','').lower()!='bearer' or type(expires) is not int or not 60<=expires<=86400:
        raise GoogleFailure('google_offline_token_required')
    return {'access_token':access,'refresh_token':refresh,'expires_at':(timezone.now()+timedelta(seconds=expires)).isoformat()}

@transaction.atomic
def start_authorization(site,actor):
    if not can(actor,site,'manage_integrations') or not configured(): raise GoogleFailure('google_oauth_not_configured_or_allowed')
    connection,_=GoogleConnection.objects.get_or_create(site=site,defaults={'bound_url':site.url})
    connection=GoogleConnection.objects.select_for_update().get(pk=connection.pk)
    nonce=secrets.token_urlsafe(40);verifier=secrets.token_urlsafe(48)
    intent=GoogleOAuthIntent.objects.create(site=site,actor=actor,bound_url=site.url,client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        connection_version=connection.credential_version,state_digest=hashlib.sha256(nonce.encode()).hexdigest(),
        encrypted_verifier=encode_secret({'verifier':verifier}),expires_at=timezone.now()+timedelta(minutes=10))
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri':settings.GOOGLE_OAUTH_REDIRECT_URI,'response_type':'code','scope':SCOPE,'state':nonce,
        'access_type':'offline','prompt':'consent','code_challenge':challenge,'code_challenge_method':'S256'})
    return intent,url

def complete_authorization(actor,session_intent,state,code,denied=False):
    if not configured() or not isinstance(state,str) or not 32<=len(state)<=200: raise GoogleFailure('google_invalid_state')
    with transaction.atomic():
        intent=GoogleOAuthIntent.objects.select_for_update().select_related('site').filter(state_digest=hashlib.sha256(state.encode()).hexdigest()).first()
        if not intent or str(intent.pk)!=str(session_intent) or intent.actor_id!=actor.pk or intent.used_at or intent.expires_at<=timezone.now():
            raise GoogleFailure('google_invalid_or_expired_state')
        if not can(actor,intent.site,'manage_integrations') or intent.site.url!=intent.bound_url or intent.client_id!=settings.GOOGLE_OAUTH_CLIENT_ID:
            raise GoogleFailure('google_authorization_context_changed')
        intent.used_at=timezone.now();intent.save(update_fields=['used_at'])
    if denied: raise GoogleFailure('google_consent_declined')
    if not isinstance(code,str) or not 1<=len(code)<=4096: raise GoogleFailure('google_code_required')
    values=request_json(TOKEN,method='POST',data={'client_id':settings.GOOGLE_OAUTH_CLIENT_ID,'client_secret':settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri':settings.GOOGLE_OAUTH_REDIRECT_URI,'grant_type':'authorization_code','code':code,
        'code_verifier':decode_secret(intent.encrypted_verifier)['verifier']})
    if SCOPE not in str(values.get('scope','')).split(): raise GoogleFailure('google_read_scope_required')
    tokens=token_values(values)
    with transaction.atomic():
        current=GoogleConnection.objects.select_for_update().get(site=intent.site)
        intent.site.refresh_from_db()
        actor.refresh_from_db(fields=['is_active','is_service_account'])
        if current.credential_version!=intent.connection_version or intent.site.url!=intent.bound_url or not can(actor,intent.site,'manage_integrations'):
            raise GoogleFailure('google_authorization_context_changed')
        current.actor=actor;current.bound_url=intent.bound_url;current.client_id=intent.client_id
        current.credential_version=uuid.uuid4();current.encrypted_tokens=encode_secret(tokens)
        current.status='authorized';current.property_url='';current.permission_level='';current.properties=[]
        current.checked_at=timezone.now();current.error_code='';current.save()
        AuditEvent.objects.create(site=intent.site,organization=intent.site.organization,actor=actor,action='google.oauth_authorized')
    return current

@transaction.atomic
def access_token(connection):
    current=GoogleConnection.objects.select_for_update().select_related('site').get(pk=connection.pk)
    if current.credential_version!=connection.credential_version or current.status not in ('authorized','connected') \
        or current.site.archived_at or current.site.url!=current.bound_url or current.client_id!=settings.GOOGLE_OAUTH_CLIENT_ID:
        raise GoogleFailure('google_connection_not_current')
    tokens=decode_secret(current.encrypted_tokens)
    try: expires=datetime.fromisoformat(tokens['expires_at'])
    except (ValueError,KeyError,TypeError): raise GoogleFailure('google_invalid_token') from None
    if timezone.is_naive(expires): raise GoogleFailure('google_invalid_token')
    if expires<=timezone.now()+timedelta(seconds=60):
        reply=request_json(TOKEN,method='POST',data={'client_id':settings.GOOGLE_OAUTH_CLIENT_ID,'client_secret':settings.GOOGLE_OAUTH_CLIENT_SECRET,
            'grant_type':'refresh_token','refresh_token':tokens['refresh_token']})
        tokens=token_values(reply,tokens['refresh_token']);current.encrypted_tokens=encode_secret(tokens);current.save(update_fields=['encrypted_tokens'])
    return tokens['access_token']

def matching_property(site,value):
    host=(urlsplit(site.url).hostname or '').lower()
    if value=='sc-domain:'+host: return True
    parts=urlsplit(value)
    return bool(parts.scheme in ('http','https') and parts.hostname==host and not parts.username and not parts.password and
        not parts.query and not parts.fragment and value.rstrip('/')==site.url.rstrip('/'))

def list_properties(connection,actor):
    if not can(actor,connection.site,'manage_integrations'): raise GoogleFailure('google_permission_required')
    result=request_json(API+'sites',token=access_token(connection))
    entries=result.get('siteEntry',[])
    if not isinstance(entries,list) or len(entries)>1000: raise GoogleFailure('google_invalid_properties')
    accepted=[]
    for entry in entries:
        if not isinstance(entry,dict): raise GoogleFailure('google_invalid_properties')
        value=entry.get('siteUrl');level=entry.get('permissionLevel')
        if isinstance(value,str) and len(value)<=2048 and matching_property(connection.site,value) and level in ('siteOwner','siteFullUser','siteRestrictedUser'):
            accepted.append({'url':value,'permission_level':level})
    actor.refresh_from_db(fields=['is_active','is_service_account']);connection.site.refresh_from_db()
    if not can(actor,connection.site,'manage_integrations') or connection.site.url!=connection.bound_url:
        raise GoogleFailure('google_authorization_context_changed')
    updated=GoogleConnection.objects.filter(pk=connection.pk,credential_version=connection.credential_version).update(properties=accepted,checked_at=timezone.now())
    if not updated: raise GoogleFailure('google_connection_changed')
    return accepted

@transaction.atomic
def select_property(connection,actor,value):
    choices=list_properties(connection,actor)
    chosen=next((p for p in choices if p['url']==value),None)
    if not chosen: raise GoogleFailure('google_property_not_authorized')
    current=GoogleConnection.objects.select_for_update().get(pk=connection.pk)
    connection.site.refresh_from_db()
    if current.credential_version!=connection.credential_version or connection.site.url!=current.bound_url or not can(actor,connection.site,'manage_integrations'):
        raise GoogleFailure('google_connection_changed')
    current.property_url=value;current.permission_level=chosen['permission_level'];current.status='connected'
    current.credential_version=uuid.uuid4();current.save(update_fields=['property_url','permission_level','status','credential_version'])
    AuditEvent.objects.create(site=connection.site,organization=connection.site.organization,actor=actor,action='google.property_selected',target=value[:160])
    return current

@transaction.atomic
def revoke(connection,actor):
    if not can(actor,connection.site,'manage_integrations'): raise GoogleFailure('google_permission_required')
    current=GoogleConnection.objects.select_for_update().get(pk=connection.pk)
    current.status='revoked';current.encrypted_tokens='';current.property_url='';current.properties=[];current.credential_version=uuid.uuid4();current.save()
    GoogleOAuthIntent.objects.filter(site=connection.site,used_at__isnull=True).update(used_at=timezone.now())
    AuditEvent.objects.create(site=connection.site,organization=connection.site.organization,actor=actor,action='google.connection_revoked')
