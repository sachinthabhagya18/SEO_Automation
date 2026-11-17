"""Bounded reads for an explicitly allowlisted, password-protected staging site."""
import base64
from urllib.parse import urlsplit
from django.conf import settings
from .models import SiteConnection
from .connections import decrypt_credentials
from .public_http import fetch_public,FetchError
from .staging_origin import staging_target

def site_fetch(site,url,*,fetch=fetch_public,**kwargs):
    base=urlsplit(site.url) if site else None
    if not site or site.environment!='staging' or base.hostname not in settings.PROTECTED_STAGING_HOSTS:
        return fetch(url,**kwargs)
    parts=urlsplit(url)
    if parts.scheme!='https' or base.scheme!='https' or parts.hostname!=base.hostname or (parts.port or 443)!=(base.port or 443) or parts.username or parts.password:
        raise FetchError('Protected staging origin mismatch.')
    connection=SiteConnection.objects.select_related('site').filter(site=site,status='connected').first()
    if not connection or connection.site.archived_at or connection.site.url!=site.url or connection.bound_url.rstrip('/')!=site.url.rstrip('/'):
        raise FetchError('Current verified staging read connection required.')
    credentials=decrypt_credentials(connection)
    authorization='Basic '+base64.b64encode((credentials['username']+':'+credentials['password']).encode()).decode()
    kwargs['max_redirects']=0
    if staging_target(site,url):
        kwargs['resolver']=lambda candidate:staging_target(site,candidate)
    return fetch(url,authorization=authorization,**kwargs)
