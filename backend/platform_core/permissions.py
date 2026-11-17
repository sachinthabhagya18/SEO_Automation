from django.db.models import Q
from django.utils import timezone
from .models import Membership, Site, SiteAssignment, ACTIONS

def owner_organizations(user):
    if not user.is_authenticated or not user.is_active or getattr(user,'is_service_account',False):
        return Membership.objects.none().values_list('organization_id', flat=True)
    return Membership.objects.filter(user=user, active=True, role=Membership.Role.OWNER).values_list('organization_id', flat=True)

def can(user, site, action):
    if site.archived_at or action not in ACTIONS or not user.is_authenticated or not user.is_active:
        return False
    if getattr(user,'is_service_account',False) and action not in ('view_site','edit_draft','submit_for_review','run_keyword_research','generate_ai_draft','view_analytics','sync_search_metrics'):
        return False
    if getattr(user,'is_service_account',False):
        from .models import ServiceCredential
        credentials=ServiceCredential.objects.filter(actor=user)
        if credentials.exists() and not credentials.filter(site=site,active=True,expires_at__gt=timezone.now()).exists():
            return False
    if site.organization_id in owner_organizations(user):
        return True
    assignment = SiteAssignment.objects.filter(
        site=site, membership__user=user, membership__active=True,
        membership__organization_id=site.organization_id, bundle__organization_id=site.organization_id,
    )
    return assignment.filter(Q(bundle__group__permissions__codename=action,
                               bundle__group__permissions__content_type__app_label='platform_core',
                               bundle__group__permissions__content_type__model='site') |
                             Q(grants__action=action)).exists()

def visible_sites(user):
    if not user.is_authenticated or not user.is_active:
        return Site.objects.none()
    # Use the same authorization predicate for collections and object access.
    candidates = Site.objects.filter(archived_at__isnull=True).filter(Q(organization_id__in=owner_organizations(user)) |
                                    Q(siteassignment__membership__user=user, siteassignment__membership__active=True)).distinct()
    return Site.objects.filter(pk__in=[s.pk for s in candidates if can(user, s, 'view_site')])
