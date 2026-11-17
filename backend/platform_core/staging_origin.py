"""Operator-pinned public origin + explicit public CA for an owned private stage.

This never disables certificate/hostname verification or accepts private IPs.
"""
import ipaddress
from pathlib import Path
import socket
from urllib.parse import urlsplit,urlunsplit
from django.conf import settings
from .public_http import Target,FetchError

def staging_target(site,url):
    base=urlsplit(site.url)
    config=settings.PROTECTED_STAGING_ORIGINS.get(base.hostname)
    if site.environment!='staging' or base.hostname not in settings.PROTECTED_STAGING_HOSTS or not config:
        return None
    if len(url)>2048 or '\\' in url or any(ord(c)<33 or ord(c)==127 for c in url): raise FetchError('Invalid staging URL.')
    parts=urlsplit(url)
    if base.scheme!='https' or parts.scheme!='https' or parts.hostname!=base.hostname or (parts.port or 443)!=443 or parts.username or parts.password:
        raise FetchError('Protected staging origin mismatch.')
    try:
        address=ipaddress.ip_address(config['address'])
        ca=Path(config['ca_file'])
        if not address.is_global or address.is_multicast or address.is_unspecified or not ca.is_file(): raise ValueError()
    except (ValueError,KeyError,TypeError): raise FetchError('Staging origin configuration requires review.') from None
    path=(parts.path or '/')+('?' + parts.query if parts.query else '')
    clean=urlunsplit(('https',base.hostname,parts.path or '/',parts.query,''))
    return Target(clean,'https',base.hostname,443,path,socket.AF_INET6 if address.version==6 else socket.AF_INET,str(address),str(ca))
