from django import forms
import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.utils import timezone
from .forms import SiteForm, AcceptInvitationForm, invitation_for, ReferenceForm, ReferenceImportForm, ConnectionForm, AuditScheduleForm
from .models import Site, Organization, Membership, SiteAssignment, RoleBundle, AuditEvent, ReferenceSite, Job, PageSnapshot, SiteConnection, Page, AuditSchedule, ServiceCredential
from .connections import connection_status, save_connection, check_connection, sync_inventory, ConnectionFailure
from .permissions import visible_sites, owner_organizations, can
from .services import invite, seed_bundles

def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ready'})

@login_required
def overview(request):
    sites = visible_sites(request.user).filter(parent_site__isnull=True).annotate(public_audits=Count('job', filter=Q(job__state='succeeded'))).order_by('name', 'pk')
    search = request.GET.get('q', '').strip()[:160]
    if search:
        sites = sites.filter(name__icontains=search)
    from django.core.paginator import Paginator
    page = Paginator(sites, 12).get_page(request.GET.get('page'))
    owned = set(owner_organizations(request.user))
    for site in page:
        site.can_edit_profile = can(request.user, site, 'manage_site_profile')
        site.can_remove = site.organization_id in owned
        site.connector_state = connection_status(site)
    return render(request, 'platform/overview.html', {'page_obj': page, 'q': search,
                                                    'is_owner': owner_organizations(request.user).exists()})

@login_required
def site_detail(request, pk):
    site = get_object_or_404(visible_sites(request.user), pk=pk)
    return render(request, 'platform/site.html', {'site': site, 'can_edit': can(request.user, site, 'manage_site_profile'),
        'connector_state': connection_status(site), 'can_integrate': can(request.user, site, 'manage_integrations'),
        'can_automate': can(request.user, site, 'manage_automation'),
        'can_analytics':can(request.user,site,'view_analytics'),
        'test_copies':visible_sites(request.user).filter(parent_site=site),
        'latest_research':site.research_runs.exclude(stage='connection_test').first(),
        'review_count':site.changeset_set.filter(state='pending_review').count(),
        'can_remove': site.organization_id in owner_organizations(request.user),
        'events': AuditEvent.objects.filter(site=site)[:10], 'can_audit': can(request.user, site, 'run_audit'),
        'idempotency_key': uuid.uuid4(), 'jobs': Job.objects.filter(site=site)[:5]})

@login_required
def site_edit(request, pk=None):
    if pk:
        site = get_object_or_404(visible_sites(request.user), pk=pk)
        if not can(request.user, site, 'manage_site_profile'):
            raise Http404
        organization = site.organization
    else:
        organization = Organization.objects.filter(pk__in=owner_organizations(request.user)).first()
        if not organization:
            raise Http404
        site = Site(organization=organization)
    form = SiteForm(request.POST or None, instance=site)
    if request.method == 'POST' and form.is_valid():
        # Organization is set server-side; body parameters cannot change ownership.
        try:
            with transaction.atomic():
                site = form.save(commit=False)
                site.full_clean()
                site.save()
                AuditEvent.objects.create(organization=organization, site=site, actor=request.user,
                                          action='site.profile_saved', request_id=request.request_id)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Website profile saved. Connection setup is still required.')
            return redirect('site-detail', pk=site.pk)
    return render(request, 'platform/site_form.html', {'form': form, 'site': site})

@login_required
@require_POST
def pause_site(request, pk):
    site = get_object_or_404(visible_sites(request.user), pk=pk)
    if not can(request.user, site, 'manage_automation'):
        raise Http404
    # Only emergency pause is exposed until the publishing policy exists.
    site.paused = True
    site.save(update_fields=['paused'])
    AuditEvent.objects.create(organization=site.organization, site=site, actor=request.user, action='site.paused')
    messages.success(request, 'Website writes are paused.')
    return redirect('site-detail', pk=pk)

@never_cache
def accept_invitation(request, token):
    invitation = invitation_for(token)
    if not invitation:
        return render(request, 'registration/invitation_invalid.html', status=400)
    form = AcceptInvitationForm(invitation.membership.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.accept(token)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Your password is set. You can now sign in.')
            return redirect('login')
    return render(request, 'registration/accept.html', {'form': form})

class StaffInviteForm(forms.Form):
    email = forms.EmailField()

@login_required
def staff(request):
    orgs = Organization.objects.filter(pk__in=owner_organizations(request.user))
    organization = orgs.first()
    if not organization:
        raise Http404
    seed_bundles(organization)
    form = StaffInviteForm(request.POST or None)
    invitation_path = None
    if request.method == 'POST' and form.is_valid():
        try:
            _, token = invite(organization, form.cleaned_data['email'], actor=request.user)
            invitation_path = request.build_absolute_uri('/invitations/' + token + '/')
        except ValidationError:
            form.add_error('email', 'An account with this email already exists or cannot be invited.')
    return render(request, 'platform/staff.html', {'form': form, 'invitation_path': invitation_path,
        'memberships': Membership.objects.filter(organization=organization).select_related('user'),
        'sites': Site.objects.filter(organization=organization, archived_at__isnull=True), 'bundles': RoleBundle.objects.filter(organization=organization),
        'assignments': SiteAssignment.objects.filter(site__organization=organization).select_related('membership__user', 'site', 'bundle')})

@login_required
@require_POST
@transaction.atomic
def assign_staff(request):
    site = get_object_or_404(Site, pk=request.POST.get('site'), archived_at__isnull=True, organization_id__in=owner_organizations(request.user))
    member = get_object_or_404(Membership, pk=request.POST.get('membership'), organization=site.organization, role=Membership.Role.STAFF)
    bundle = get_object_or_404(RoleBundle, pk=request.POST.get('bundle'), organization=site.organization)
    SiteAssignment.objects.update_or_create(site=site, membership=member, defaults={'bundle': bundle})
    AuditEvent.objects.create(organization=site.organization, site=site, actor=request.user, action='permissions.assignment_changed', target=str(member.pk))
    messages.success(request, 'Website permissions updated.')
    return redirect('staff')

@login_required
@require_POST
def revoke_assignment(request, pk):
    assignment = get_object_or_404(SiteAssignment, pk=pk, site__organization_id__in=owner_organizations(request.user))
    AuditEvent.objects.create(organization=assignment.site.organization, site=assignment.site, actor=request.user,
                              action='permissions.assignment_revoked', target=str(assignment.membership_id))
    assignment.delete()
    messages.success(request, 'Website access revoked.')
    return redirect('staff')

@login_required
def references(request, pk):
    site = get_object_or_404(visible_sites(request.user), pk=pk)
    allowed = can(request.user, site, 'manage_reference_sites')
    if request.method == 'POST' and not allowed:
        raise Http404
    importing = request.POST.get('operation') == 'import'
    form = ReferenceForm(request.POST if request.method == 'POST' and not importing else None)
    import_form = ReferenceImportForm(request.POST if importing else None, request.FILES if importing else None)
    if request.method == 'POST' and ((importing and import_form.is_valid()) or (not importing and form.is_valid())):
        rows = import_form.cleaned_data['csv_file'] if importing else [form.cleaned_data]
        with transaction.atomic():
            count = 0
            for row in rows:
                _, created = ReferenceSite.objects.get_or_create(site=site, url=row['url'],
                    defaults={'relationship': row['relationship'], 'created_by': request.user})
                count += int(created)
            AuditEvent.objects.create(organization=site.organization, site=site, actor=request.user,
                                      action='references.imported' if importing else 'reference.added', target=str(count))
        messages.success(request, f'{count} reference URLs saved. Research has not run yet.')
        return redirect('site-references', pk=pk)
    from django.core.paginator import Paginator
    return render(request, 'platform/references.html', {'site': site, 'form': form, 'import_form': import_form,
        'allowed': allowed, 'page_obj': Paginator(site.references.all(), 25).get_page(request.GET.get('page'))})

@login_required
@require_POST
def delete_reference(request, pk, reference_pk):
    site = get_object_or_404(visible_sites(request.user), pk=pk)
    if not can(request.user, site, 'manage_reference_sites'):
        raise Http404
    reference = get_object_or_404(ReferenceSite, pk=reference_pk, site=site)
    reference.delete()
    AuditEvent.objects.create(organization=site.organization, site=site, actor=request.user, action='reference.removed', target=str(reference_pk))
    return redirect('site-references', pk=pk)

@login_required
@require_POST
def start_public_audit(request, pk):
    from .api import create_public_audit
    site = get_object_or_404(visible_sites(request.user), pk=pk)
    if not can(request.user, site, 'run_audit'):
        raise Http404
    try:
        key = uuid.UUID(request.POST.get('idempotency_key', ''))
    except (ValueError, TypeError, AttributeError):
        raise Http404
    job, _ = create_public_audit(site, request.user, key)
    return redirect('job-detail', job_id=job.pk)

@login_required
def job_detail(request, job_id):
    job = get_object_or_404(Job.objects.filter(site__in=visible_sites(request.user)).select_related('site'), pk=job_id)
    snapshot = PageSnapshot.objects.filter(job=job).first()
    return render(request, 'platform/job.html', {'job': job, 'site': job.site, 'snapshot': snapshot})

@login_required
def archived_sites(request):
    from django.core.paginator import Paginator
    sites = Site.objects.filter(organization_id__in=owner_organizations(request.user), archived_at__isnull=False)
    if not owner_organizations(request.user).exists():
        raise Http404
    return render(request, 'platform/archived_sites.html', {'page_obj': Paginator(sites, 25).get_page(request.GET.get('page'))})

@login_required
def remove_site(request, pk):
    site = get_object_or_404(Site, pk=pk, archived_at__isnull=True, organization_id__in=owner_organizations(request.user))
    error = None
    if request.method == 'POST':
        if request.POST.get('confirm_name', '') != site.name:
            error = 'Type the website name exactly to confirm removal.'
        else:
            with transaction.atomic():
                site = Site.objects.select_for_update().get(pk=site.pk)
                site.archived_at, site.paused = timezone.now(), True
                site.save(update_fields=['archived_at', 'paused'])
                Job.objects.filter(site=site, state__in=['queued', 'running']).update(
                    state='cancelled', error_code='site_archived', finished_at=timezone.now())
                AuditEvent.objects.create(organization=site.organization, site=site, actor=request.user, action='site.archived')
            messages.success(request, 'Website removed from the active workspace. Its history is retained; restore it from Archived websites.')
            return redirect('overview')
    return render(request, 'platform/site_remove.html', {'site': site, 'error': error})

@login_required
@require_POST
@transaction.atomic
def restore_site(request, pk):
    site = get_object_or_404(Site.objects.select_for_update(), pk=pk, archived_at__isnull=False,
                           organization_id__in=owner_organizations(request.user))
    site.archived_at, site.paused = None, True
    site.save(update_fields=['archived_at', 'paused'])
    AuditEvent.objects.create(organization=site.organization, site=site, actor=request.user, action='site.restored')
    messages.success(request, 'Website restored. Publishing remains paused; cancelled jobs have not been restarted.')
    return redirect('site-detail', pk=site.pk)

@login_required
@never_cache
def site_connection(request, pk):
    site = get_object_or_404(visible_sites(request.user), pk=pk)
    if not can(request.user, site, 'manage_integrations'): raise Http404
    connection = SiteConnection.objects.filter(site=site).first()
    form = ConnectionForm(request.POST if request.method == 'POST' and request.POST.get('operation') == 'save' else None)
    if request.method == 'POST':
        operation = request.POST.get('operation')
        try:
            if operation == 'save' and form.is_valid():
                save_connection(site, request.user, **{'username': form.cleaned_data['username'], 'password': form.cleaned_data['application_password']})
                messages.success(request, 'Credentials saved encrypted. Test the read-only connection next.')
                return redirect('site-connection', pk=pk)
            elif operation == 'check' and connection:
                check_connection(site, request.user)
                messages.success(request, 'WordPress read connection verified. Remote writes remain unavailable.')
                return redirect('site-connection', pk=pk)
            elif operation == 'inventory' and connection:
                count = sync_inventory(site, request.user)
                messages.success(request, f'Read {count} inventory records (maximum 75 per sync). Nothing on WordPress was changed.')
                return redirect('site-connection', pk=pk)
            elif operation == 'revoke' and connection:
                connection.status = 'revoked'
                connection.encrypted_credentials = ''
                connection.save(update_fields=['status', 'encrypted_credentials'])
                AuditEvent.objects.create(organization=site.organization, site=site, actor=request.user, action='connection.revoked')
                messages.success(request, 'Local connection revoked. Revoke its Application Password in WordPress too.')
                return redirect('site-connection', pk=pk)
        except ConnectionFailure as error:
            form.add_error(None, str(error))
    return render(request, 'platform/connection.html', {'site': site, 'form': form, 'connection': connection,
        'connector_state':connection_status(site),
        'pages': Page.objects.filter(site=site).order_by('url')[:75], 'sources': site.knowledge_sources.all()[:10]})

@login_required
def site_automation(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    if not can(request.user,site,'manage_automation'): raise Http404
    schedule=AuditSchedule.objects.filter(site=site).first()
    form=AuditScheduleForm(request.POST if request.method=='POST' and request.POST.get('operation')=='schedule' else None,
        initial={'enabled':schedule.enabled if schedule else False,'interval_minutes':schedule.interval_minutes if schedule else 1440})
    if request.method=='POST':
        if request.POST.get('operation')=='schedule' and form.is_valid():
            AuditSchedule.objects.update_or_create(site=site,defaults={'enabled':form.cleaned_data['enabled'],
                'interval_minutes':form.cleaned_data['interval_minutes'],'next_due':timezone.now() if form.cleaned_data['enabled'] else None})
            AuditEvent.objects.create(organization=site.organization,site=site,actor=request.user,action='automation.audit_schedule_configured')
            messages.success(request,'Read-only audit schedule updated. n8n must be configured; publishing is unchanged.')
            return redirect('site-automation',pk=pk)
        if request.POST.get('operation')=='revoke':
            ServiceCredential.objects.filter(site=site,active=True).update(active=False)
            AuditEvent.objects.create(organization=site.organization,site=site,actor=request.user,action='automation.service_credential_revoked')
            messages.success(request,'Automation service credentials revoked. New dispatches and queued service jobs are blocked.')
            return redirect('site-automation',pk=pk)
    return render(request,'platform/automation.html',{'site':site,'form':form,'schedule':schedule,
        'credentials':ServiceCredential.objects.filter(site=site).order_by('-created_at')[:5],
        'jobs':Job.objects.filter(site=site,service_credential__isnull=False)[:10]})
