import csv,uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404,HttpResponse,HttpResponseBadRequest
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.conf import settings
from .models import GoogleConnection,SearchMetricsRun
from .permissions import visible_sites,can
from . import google_search as google
from .search_metrics import queue_sync
from .keyword_views import csv_cell

@login_required
@never_cache
def connection(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    if not can(request.user,site,'manage_integrations'): raise Http404
    current=GoogleConnection.objects.filter(site=site).first()
    if request.method=='POST':
        try:
            operation=request.POST.get('operation')
            if operation=='connect':
                intent,url=google.start_authorization(site,request.user)
                request.session['google_oauth_intent']=str(intent.pk)
                return redirect(url)
            if not current: raise google.GoogleFailure('google_connection_required')
            if operation=='properties':
                properties=google.list_properties(current,request.user)
                messages.info(request,'Authorized matching properties refreshed.' if properties else 'No authorized property matches this website. Complete verification in your Google account, then refresh.')
            elif operation=='select':
                google.select_property(current,request.user,request.POST.get('property_url','')[:2049]);messages.success(request,'Google property authorized for read-only metrics.')
            elif operation=='disconnect':
                google.revoke(current,request.user);messages.success(request,'Local Google connection and pending authorization requests revoked.')
            else: raise google.GoogleFailure('unsupported_google_operation')
        except Exception as error:
            messages.error(request,str(error) if isinstance(error,google.GoogleFailure) else 'google_connection_failed')
        return redirect('google-connection',pk=site.pk)
    return render(request,'platform/google_connection.html',{'site':site,'connection':current,
        'current':bool(current and current.bound_url==site.url),'configured':google.configured(),
        'redirect_uri':settings.GOOGLE_OAUTH_REDIRECT_URI})

@never_cache
@require_GET
def callback(request):
    # Do not put an OAuth code inside a login redirect's next parameter.
    if not request.user.is_authenticated or not request.user.is_active:
        return HttpResponseBadRequest('Google authorization session expired. Sign in and start Connect again.')
    intent=request.session.get('google_oauth_intent')
    try:
        current=google.complete_authorization(request.user,intent,request.GET.get('state',''),request.GET.get('code',''),denied='error' in request.GET)
    except Exception as error:
        code=str(error) if isinstance(error,google.GoogleFailure) else 'google_connection_failed'
        return HttpResponseBadRequest(code)
    request.session.pop('google_oauth_intent',None)
    messages.success(request,'Google authorized. Refresh matching properties and select your verified property.')
    return redirect('google-connection',pk=current.site_id)

def metrics_context(site):
    current=GoogleConnection.objects.filter(site=site,status='connected',bound_url=site.url).first()
    runs=SearchMetricsRun.objects.filter(site=site,connection_version=current.credential_version,property_url=current.property_url,bound_url=site.url) if current else SearchMetricsRun.objects.none()
    return current,runs

@login_required
@never_cache
def analytics(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    if not can(request.user,site,'view_analytics'): raise Http404
    if request.method=='POST':
        try:
            event=uuid.UUID(request.POST.get('event_key',''))
            run=queue_sync(site,request.user,event)
            messages.success(request,'Search Console sync queued. Refresh to see its result; no website content is changed.')
        except Exception as error:
            messages.error(request,str(error) if isinstance(error,google.GoogleFailure) else 'google_sync_request_failed')
        return redirect('site-analytics',pk=pk)
    current,runs=metrics_context(site);latest=runs.first();data=runs.filter(state='succeeded').first()
    report=data.report if data else {}
    return render(request,'platform/analytics.html',{'site':site,'connection':current,'latest':latest,'data_run':data,'report':report,
        'daily':data.metrics.filter(row_kind='daily').order_by('date') if data else [],
        'page_obj':Paginator(data.metrics.filter(row_kind='detail').order_by('-clicks','id'),40).get_page(request.GET.get('page')) if data else None,
        'ctr_percent':report.get('ctr')*100 if report.get('ctr') is not None else None,
        'can_sync':can(request.user,site,'sync_search_metrics'),'can_export':can(request.user,site,'export_report'),
        'can_connect':can(request.user,site,'manage_integrations'),'event_key':uuid.uuid4()})

@login_required
def export(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    if not can(request.user,site,'view_analytics') or not can(request.user,site,'export_report'): raise Http404
    _,runs=metrics_context(site);run=runs.filter(state='succeeded').first()
    if not run: raise Http404
    response=HttpResponse(content_type='text/csv; charset=utf-8');response['Cache-Control']='private, no-store'
    response['Content-Disposition']='attachment; filename="search-console-observations.csv"'
    writer=csv.writer(response);writer.writerow(['row_kind','date_pacific','page','query','country','device','clicks','impressions','ctr','average_position','fetched_at'])
    for row in run.metrics.order_by('row_kind','date').iterator(chunk_size=200):
        writer.writerow([csv_cell(value) for value in [row.row_kind,row.date,row.page,row.query,row.country,row.device,row.clicks,row.impressions,row.ctr,row.position,run.finished_at.isoformat()]])
    return response
