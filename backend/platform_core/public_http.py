"""Bounded public HTTP transport. No cookies, credentials, proxy inheritance or browser.

DNS is resolved once per hop. Every result must be public; the connection uses a
validated literal address while TLS validates the original hostname. Redirects are
revalidated, so neither a second DNS lookup nor a private redirect bypasses policy.
"""
import http.client
import ipaddress
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, urljoin

class FetchError(ValueError):
    pass

@dataclass(frozen=True)
class Target:
    url: str
    scheme: str
    hostname: str
    port: int
    path: str
    family: int
    address: str
    ca_file: str | None = None

@dataclass(frozen=True)
class Response:
    url: str
    status: int
    headers: dict
    body: bytes

def resolve_target(url):
    if len(url) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in url) or '\\' in url:
        raise FetchError('Invalid URL.')
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username is not None or parts.password is not None:
            raise FetchError('Only credential-free HTTP(S) URLs are permitted.')
        hostname = parts.hostname.rstrip('.').encode('idna').decode('ascii').lower()
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        if port not in (80, 443) or '%' in hostname:
            raise FetchError('Only standard public HTTP(S) ports are permitted.')
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (ValueError, UnicodeError, OSError) as error:
        raise FetchError('URL could not be safely resolved.') from error
    if not results:
        raise FetchError('No public address available.')
    for family, _, _, _, sockaddr in results:
        address = ipaddress.ip_address(sockaddr[0])
        if family not in (socket.AF_INET, socket.AF_INET6) or not address.is_global or address.is_multicast or address.is_unspecified:
            raise FetchError('Private, reserved and non-public networks are prohibited.')
    family, _, _, _, sockaddr = results[0]
    host = f'[{hostname}]' if ':' in hostname else hostname
    standard = (parts.scheme, port) in (('http', 80), ('https', 443))
    netloc = host if standard else f'{host}:{port}'
    path = parts.path or '/'
    path += ('?' + parts.query) if parts.query else ''
    return Target(urlunsplit((parts.scheme, netloc, parts.path or '/', parts.query, '')), parts.scheme, hostname, port, path, family, sockaddr[0])

class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, target, timeout):
        super().__init__(target.hostname, target.port, timeout=timeout)
        self.target = target

    def request(self,method,url,body=None,headers=None,*,encode_chunked=False):
        headers=dict(headers or {})
        if not any(name.lower()=='host' for name in headers):
            host='['+self.target.hostname+']' if ':' in self.target.hostname else self.target.hostname
            if (self.target.scheme,self.target.port) not in (('http',80),('https',443)):
                host+=':'+str(self.target.port)
            headers['Host']=host
        return super().request(method,url,body=body,headers=headers,encode_chunked=encode_chunked)

    def connect(self):
        sock = socket.socket(self.target.family, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            destination = (self.target.address, self.target.port, 0, 0) if self.target.family == socket.AF_INET6 else (self.target.address, self.target.port)
            sock.connect(destination)
            if self.target.scheme == 'https':
                context=ssl.create_default_context(cafile=self.target.ca_file) if self.target.ca_file else ssl.create_default_context()
                sock = context.wrap_socket(sock, server_hostname=self.target.hostname)
            self.sock = sock
        except BaseException:
            sock.close()
            raise

def fetch_public(url, *, max_bytes=2_000_000, max_redirects=5, timeout=5, total_timeout=20, before_fetch=None, authorization=None, resolver=None):
    if not 1 <= max_bytes <= 2_000_000 or not 0 <= max_redirects <= 5:
        raise FetchError('Invalid fetch budget.')
    if authorization and (max_redirects!=0 or urlsplit(url).scheme!='https' or '\r' in authorization or '\n' in authorization):
        raise FetchError('Authenticated fetch requires HTTPS without redirects.')
    deadline = time.monotonic() + min(total_timeout, 30)
    for hop in range(max_redirects + 1):
        target = (resolver or resolve_target)(url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError('Fetch time budget exceeded.')
        if before_fetch:
            before_fetch(target.url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError('Fetch time budget exceeded.')
        connection = PinnedConnection(target, min(timeout, remaining))
        try:
            request_headers={'User-Agent': 'CompanySEOAudit/0.1', 'Accept-Encoding': 'identity', 'Accept': 'text/html,text/plain,application/xml'}
            if authorization: request_headers['Authorization']=authorization
            connection.request('GET', target.path, headers=request_headers)
            remote = connection.getresponse()
            headers = {name.lower(): value for name, value in remote.getheaders()}
            if remote.status in (301, 302, 303, 307, 308):
                if hop == max_redirects or not headers.get('location'):
                    raise FetchError('Redirect limit exceeded or invalid redirect.')
                url = urljoin(target.url, headers['location'])
                continue
            if headers.get('content-encoding', 'identity').lower() != 'identity':
                raise FetchError('Compressed responses are not accepted by this bounded transport.')
            length = headers.get('content-length')
            if length and (not length.isdigit() or int(length) > max_bytes):
                raise FetchError('Response exceeds the fetch budget.')
            chunks = []
            size = 0
            while True:
                if time.monotonic() >= deadline:
                    raise FetchError('Fetch time budget exceeded.')
                chunk = remote.read1(min(65_536, max_bytes + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError('Response exceeds the fetch budget.')
                chunks.append(chunk)
            return Response(target.url, remote.status, headers, b''.join(chunks))
        except (OSError, http.client.HTTPException) as error:
            raise FetchError('Public fetch failed.') from error
        finally:
            connection.close()
    raise FetchError('Redirect limit exceeded.')
