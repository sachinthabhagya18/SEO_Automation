"""Explicit test targets only. No production publication path."""
from urllib.parse import urlsplit
from django.conf import settings

def write_scope(site):
    if site.environment!='staging' or site.archived_at:
        return None
    if site.url=='http://wordpress' and settings.LOCAL_PUBLICATION_ENABLED and settings.CONNECTOR_LOCAL_FIXTURE_ENABLED:
        return 'fixture'
    parts=urlsplit(site.url)
    try: port=parts.port
    except ValueError: return None
    hosts=getattr(settings,'STAGING_PUBLICATION_HOSTS',())
    if (parts.scheme=='https' and parts.hostname in hosts and port in (None,443)
        and parts.netloc==parts.hostname and parts.path in ('','/')
        and not parts.query and not parts.fragment and site.parent_site_id):
        parent=site.parent_site
        if parent.organization_id==site.organization_id and parent.environment=='production' and not parent.archived_at:
            return 'staging'
    return None
