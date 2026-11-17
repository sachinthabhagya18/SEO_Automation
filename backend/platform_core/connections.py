"""Encrypted credentials and bounded read-only WordPress Application Password transport."""
import base64
import json
import socket
import uuid
import time
from urllib.parse import urlsplit, urlunsplit
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import SiteConnection, AuditEvent, Page
from .permissions import can
from .public_http import Target, resolve_target, PinnedConnection, FetchError
from .staging_origin import staging_target

class ConnectionFailure(ValueError):
    pass

def cipher():
    if not settings.CONNECTION_ENCRYPTION_KEYS:
        raise ConnectionFailure('encryption_key_missing')
    try:
        return MultiFernet([Fernet(key.encode()) for key in settings.CONNECTION_ENCRYPTION_KEYS])
    except ValueError:
        raise ConnectionFailure('encryption_key_invalid')

def encrypt_credentials(username, password):
    return cipher().encrypt(json.dumps({'username': username, 'password': password}).encode()).decode()

def decrypt_credentials(connection):
    try:
        return json.loads(cipher().decrypt(connection.encrypted_credentials.encode()))
    except (InvalidToken, ValueError, TypeError):
        raise ConnectionFailure('credential_decryption_failed')

def connection_status(site):
    try:
        connection=site.connection
        if connection.bound_url.rstrip('/') != site.url.rstrip('/'):
            return 'url_changed'
        return connection.status
    except SiteConnection.DoesNotExist:
        return 'not_connected'

def connector_target(base_url, path):
    parts = urlsplit(base_url)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ConnectionFailure('invalid_connection_url')
    url = base_url.rstrip('/') + '/wp-json/company-seo/v1/' + path.lstrip('/')
    if settings.CONNECTOR_LOCAL_FIXTURE_ENABLED and parts.scheme == 'http' and parts.netloc == 'wordpress':
        # Deliberately separate from the public crawler. This fixed name is only for local fixtures.
        result = socket.getaddrinfo('wordpress', 80, type=socket.SOCK_STREAM)[0]
        route, _, query = path.partition('?')
        local_path='/index.php?rest_route=/company-seo/v1/'+route+('&'+query if query else '')
        return Target('http://wordpress'+local_path, 'http', 'wordpress', 80, local_path, result[0], result[4][0])
    if parts.scheme != 'https':
        raise ConnectionFailure('https_required')
    try:
        return resolve_target(url)
    except FetchError:
        raise ConnectionFailure('public_https_target_required')

def wordpress_get(connection, path):
    return wordpress_request(connection,path)

def wordpress_request(connection, path, method='GET', payload=None):
    if method not in ('GET','POST'): raise ConnectionFailure('unsupported_connector_method')
    if method=='POST':
        from .publication_scope import write_scope
        if not write_scope(connection.site): raise ConnectionFailure('local_write_testing_only')
    if connection.status == 'revoked' or connection.site.archived_at:
        raise ConnectionFailure('connection_revoked')
    if connection.bound_url.rstrip('/') != connection.site.url.rstrip('/'):
        raise ConnectionFailure('site_url_changed_resave_credentials')
    credentials = decrypt_credentials(connection)
    try:
        target = staging_target(connection.site,connection.site.url.rstrip('/')+'/wp-json/company-seo/v1/'+path.lstrip('/')) or connector_target(connection.site.url, path)
    except FetchError:
        raise ConnectionFailure('staging_origin_configuration_invalid') from None
    client = PinnedConnection(target, 10)
    encoded = base64.b64encode((credentials['username'] + ':' + credentials['password']).encode()).decode()
    try:
        body=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if method=='POST' else None
        client.request(method, target.path, body=body, headers={'Authorization': 'Basic ' + encoded,
            'Content-Type':'application/json', 'Accept': 'application/json', 'Accept-Encoding': 'identity', 'User-Agent': 'CompanySEOConnector/0.2'})
        response = client.getresponse()
        # Never forward credentials through any redirect, even to a same-host path.
        if response.status in (301, 302, 303, 307, 308): raise ConnectionFailure('redirect_not_allowed')
        if response.status in (401, 403): raise ConnectionFailure('authentication_or_read_capability_denied')
        if response.status == 404: raise ConnectionFailure('remote_change_not_found' if path.startswith('changes/') or '/changes/' in path else 'connector_route_missing')
        if response.status == 409: raise ConnectionFailure('remote_revision_or_payload_conflict')
        if response.status != 200: raise ConnectionFailure('wordpress_http_error')
        if 'application/json' not in (response.getheader('Content-Type') or '').lower(): raise ConnectionFailure('json_response_required')
        if response.getheader('Content-Encoding', 'identity') != 'identity': raise ConnectionFailure('unsupported_encoding')
        deadline=time.monotonic()+20
        parts=[];size=0
        while True:
            if time.monotonic()>=deadline: raise ConnectionFailure('response_timeout')
            chunk=response.read1(min(65536,1_000_001-size))
            if not chunk: break
            size+=len(chunk)
            if size>1_000_000: raise ConnectionFailure('response_too_large')
            parts.append(chunk)
        body=b''.join(parts)
        data = json.loads(body)
        if not isinstance(data, dict): raise ConnectionFailure('invalid_connector_response')
        return data
    except ConnectionFailure:
        raise
    except Exception:
        raise ConnectionFailure('wordpress_connection_failed') from None
    finally:
        client.close()

def save_connection(site, user, username, password):
    if not can(user, site, 'manage_integrations'): raise ConnectionFailure('integration_permission_required')
    encrypted = encrypt_credentials(username, password)
    with transaction.atomic():
        connection, _ = SiteConnection.objects.update_or_create(site=site, defaults={
            'bound_url':site.url, 'encrypted_credentials': encrypted, 'status': 'unverified', 'credential_version': uuid.uuid4(),
            'capabilities': {}, 'plugin_version': '', 'wordpress_version': '', 'renderer_mode': '', 'error_code': '', 'checked_at': None})
        AuditEvent.objects.create(organization=site.organization, site=site, actor=user, action='connection.credentials_saved')
    return connection

def check_connection(site, user):
    if not can(user, site, 'manage_integrations'): raise ConnectionFailure('integration_permission_required')
    connection = SiteConnection.objects.get(site=site)
    version = connection.credential_version
    try:
        report = wordpress_get(connection, 'capabilities')
        if report.get('protocol_version') != 1 or not isinstance(report.get('operations'), list) or 'inventory_read' not in report['operations']:
            raise ConnectionFailure('unsupported_connector_protocol')
        # Store only the expected bounded capability envelope, not arbitrary remote text/markup.
        clean = {key: report[key] for key in ['protocol_version', 'plugin_version', 'wordpress_version', 'mode',
            'rendering', 'conflicts', 'theme', 'theme_title_support', 'elementor_version', 'operations',
            'editable_metadata', 'metadata_write_fields', 'metadata_target_kinds', 'remote_write', 'restore', 'unsupported'] if key in report}
        if len(json.dumps(clean)) > 32_000: raise ConnectionFailure('capability_report_too_large')
        updated = SiteConnection.objects.filter(pk=connection.pk, credential_version=version).exclude(status='revoked').update(
            status='connected', capabilities=clean, plugin_version=str(report.get('plugin_version', ''))[:40],
            wordpress_version=str(report.get('wordpress_version', ''))[:40], renderer_mode=str(report.get('mode', ''))[:40],
            checked_at=timezone.now(), error_code='')
        if not updated: raise ConnectionFailure('connection_changed_during_check')
        AuditEvent.objects.create(organization=site.organization, site=site, actor=user, action='connection.check_succeeded')
        return clean
    except ConnectionFailure as error:
        SiteConnection.objects.filter(pk=connection.pk, credential_version=version).exclude(status='revoked').update(
            status='error', error_code=str(error), checked_at=timezone.now())
        raise

def sync_inventory(site, user, max_pages=3):
    if not can(user, site, 'manage_integrations'): raise ConnectionFailure('integration_permission_required')
    connection = SiteConnection.objects.get(site=site)
    if connection.status != 'connected': raise ConnectionFailure('test_connection_first')
    version = connection.credential_version
    records = []
    for page in range(1, min(max_pages, 3) + 1):
        current = SiteConnection.objects.get(pk=connection.pk)
        if current.status != 'connected' or current.credential_version != version or not can(user, site, 'manage_integrations'):
            raise ConnectionFailure('connection_or_permission_changed')
        report = wordpress_get(current, f'pages?page={page}&per_page=25')
        if not isinstance(report.get('items'), list) or len(report['items']) > 25: raise ConnectionFailure('invalid_inventory_response')
        for item in report['items']:
            if not isinstance(item, dict) or not isinstance(item.get('url'), str) or len(item['url']) > 2048:
                raise ConnectionFailure('invalid_inventory_response')
            if urlsplit(item['url']).hostname != urlsplit(site.url).hostname:
                # Local fixture advertises its host-facing localhost URL, intentionally remapped only in tests.
                if not (settings.CONNECTOR_LOCAL_FIXTURE_ENABLED and site.url == 'http://wordpress' and urlsplit(item['url']).netloc == 'localhost:8081'):
                    raise ConnectionFailure('foreign_inventory_url')
            remote_id=item.get('id')
            if remote_id is not None and (type(remote_id) is not int or remote_id<1): raise ConnectionFailure('invalid_inventory_response')
            records.append({'url':item['url'],'wordpress_id':remote_id,
                'title':str(item.get('title',''))[:1000],'post_type':str(item.get('type',''))[:64]})
        if not isinstance(report.get('pages'), int) or page >= report['pages']: break
    if set(connection.capabilities.get('metadata_target_kinds',[])) & {'home','category'}:
        contexts=wordpress_get(connection,'contexts')
        if not isinstance(contexts.get('items'),list) or len(contexts['items'])>101: raise ConnectionFailure('invalid_context_inventory')
        for item in contexts['items']:
            kind=item.get('kind');remote_id=item.get('id');url=item.get('url')
            if kind not in ('home','category') or type(remote_id) is not int or (kind=='home' and remote_id!=0) or (kind=='category' and remote_id<1):
                raise ConnectionFailure('invalid_context_inventory')
            if not isinstance(url,str) or len(url)>2048 or urlsplit(url).hostname!=urlsplit(site.url).hostname:
                if not (settings.CONNECTOR_LOCAL_FIXTURE_ENABLED and site.url=='http://wordpress' and isinstance(url,str) and urlsplit(url).netloc=='localhost:8081'):
                    raise ConnectionFailure('foreign_context_inventory')
            records.append({'url':url,'wordpress_id':remote_id,'target_kind':kind,'title':str(item.get('title',''))[:1000],'post_type':str(item.get('type',''))[:64]})
    with transaction.atomic():
        current = SiteConnection.objects.select_for_update().get(pk=connection.pk)
        if current.status != 'connected' or current.credential_version != version or not can(user, site, 'manage_integrations'):
            raise ConnectionFailure('connection_or_permission_changed')
        unique={record['url']:record for record in records}
        Page.objects.bulk_create([Page(site=site,**record) for record in unique.values()],update_conflicts=True,
            update_fields=['wordpress_id','title','post_type','target_kind'],unique_fields=['site','url'])
        AuditEvent.objects.create(organization=site.organization, site=site, actor=user, action='connection.inventory_read', target=str(len(records)))
    return len(unique)
