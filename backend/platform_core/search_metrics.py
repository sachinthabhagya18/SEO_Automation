"""Bounded final Search Console data; daily totals and detail rows stay separate."""
import hashlib,json,math,uuid,re
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import GoogleConnection,SearchMetricsRun,SearchMetric,AuditEvent
from .permissions import can
from .google_search import API,GoogleFailure,access_token,request_json

def allowed(actor,site): return can(actor,site,'view_site') and can(actor,site,'sync_search_metrics')

@transaction.atomic
def queue_sync(site,actor,event_key=None):
    if not allowed(actor,site): raise GoogleFailure('google_sync_permission_required')
    connection=GoogleConnection.objects.select_for_update().filter(site=site,status='connected').first()
    if not connection or connection.bound_url!=site.url or not connection.property_url: raise GoogleFailure('google_property_connection_required')
    event_key=event_key or uuid.uuid4()
    existing=SearchMetricsRun.objects.filter(site=site,event_key=event_key).first() or SearchMetricsRun.objects.filter(site=site,state__in=['queued','running']).first()
    if existing: return existing
    end=datetime.now(ZoneInfo('America/Los_Angeles')).date()-timedelta(days=3)
    run=SearchMetricsRun.objects.create(site=site,actor=actor,event_key=event_key,connection_version=connection.credential_version,
        bound_url=site.url,property_url=connection.property_url,start_date=end-timedelta(days=27),end_date=end)
    transaction.on_commit(lambda:dispatch_sync(run.pk))
    return run

def dispatch_sync(run_id):
    try: sync_search_metrics.apply_async(args=[str(run_id)],retry=False);return True
    except Exception: return False

def current_connection(run):
    run.site.refresh_from_db()
    run.actor.refresh_from_db(fields=['is_active','is_service_account'])
    if not allowed(run.actor,run.site) or run.site.url!=run.bound_url: raise GoogleFailure('google_sync_authorization_changed')
    connection=GoogleConnection.objects.filter(site=run.site,status='connected',credential_version=run.connection_version,
        bound_url=run.bound_url,property_url=run.property_url).select_related('site').first()
    if not connection: raise GoogleFailure('google_sync_connection_changed')
    return connection

def parse_row(run,row,kind):
    keys=row.get('keys')
    if not isinstance(keys,list) or len(keys)!=(1 if kind=='daily' else 5) or any(not isinstance(k,str) for k in keys):
        raise GoogleFailure('google_invalid_metric_dimensions')
    try: day=date.fromisoformat(keys[0])
    except (ValueError,TypeError): raise GoogleFailure('google_invalid_metric_date') from None
    if not run.start_date<=day<=run.end_date: raise GoogleFailure('google_metric_date_outside_window')
    numbers={}
    for field in ('clicks','impressions','ctr','position'):
        number=row.get(field)
        if type(number) not in (int,float) or not math.isfinite(number) or not 0<=number<=10**12:
            raise GoogleFailure('google_invalid_metric_value')
        numbers[field]=number
    if numbers['ctr']>1 or any(not float(numbers[f]).is_integer() for f in ('clicks','impressions')):
        raise GoogleFailure('google_invalid_metric_value')
    values={'run':run,'row_key':hashlib.sha256(json.dumps([kind,keys],ensure_ascii=False).encode()).hexdigest(),
        'row_kind':kind,'date':day,**numbers}
    if kind=='detail':
        if len(keys[1])>2048 or len(keys[2])>1000 or len(keys[3])!=3 or keys[4].upper() not in ('DESKTOP','MOBILE','TABLET'):
            raise GoogleFailure('google_invalid_metric_dimensions')
        if not keys[1].startswith(run.bound_url.rstrip('/')+'/'): raise GoogleFailure('google_foreign_metric_page')
        values.update(page=keys[1],query=keys[2],country=keys[3],device=keys[4])
    return SearchMetric(**values)

def fetch_rows(run,kind):
    dimensions=['date'] if kind=='daily' else ['date','page','query','country','device']
    rows=[];truncated=False
    # One summary call, at most three detail calls: bounded quota and memory.
    for page in range(1 if kind=='daily' else 3):
        connection=current_connection(run)
        data=request_json(API+'sites/'+quote(run.property_url,safe='')+'/searchAnalytics/query',method='POST',token=access_token(connection),
            body={'startDate':run.start_date.isoformat(),'endDate':run.end_date.isoformat(),'dimensions':dimensions,
                'type':'web','dataState':'final','rowLimit':1000,'startRow':page*1000,
                'dimensionFilterGroups':[{'groupType':'and','filters':[{'dimension':'page','operator':'includingRegex','expression':'^'+re.escape(run.bound_url.rstrip('/')+'/')}]}]})
        batch=data.get('rows',[])
        if not isinstance(batch,list) or len(batch)>1000 or any(not isinstance(r,dict) for r in batch): raise GoogleFailure('google_invalid_metric_response')
        rows.extend(parse_row(run,row,kind) for row in batch)
        if len(batch)<1000: break
        truncated=True
    # If the last full batch was followed by a shorter one, the local cap
    # was not reached, though Google's own top-row limits still apply.
    truncated=bool(batch and len(batch)==1000)
    if len({r.row_key for r in rows})!=len(rows): raise GoogleFailure('google_repeated_metric_rows')
    return rows,truncated

@shared_task(time_limit=180,soft_time_limit=160)
def sync_search_metrics(run_id):
    with transaction.atomic():
        run=SearchMetricsRun.objects.select_for_update().select_related('site','actor').get(pk=run_id)
        if run.state!='queued': return
        try: current_connection(run)
        except GoogleFailure as e:
            run.state='cancelled';run.error_code=str(e);run.finished_at=timezone.now();run.save();return
        run.state='running';run.started_at=timezone.now();run.save(update_fields=['state','started_at'])
    try:
        daily,_=fetch_rows(run,'daily');detail,truncated=fetch_rows(run,'detail')
        impressions=sum(r.impressions for r in daily);clicks=sum(r.clicks for r in daily)
        report={'provider':'Google Search Console','data_timezone':'America/Los_Angeles','data_state':'final','search_type':'web',
            'daily_rows':len(daily),'detail_rows':len(detail),'detail_cap_reached':truncated,
            'coverage':'Filtered to the configured website URL prefix. Google returns top rows and can omit anonymized/limited data; detail rows are locally capped at 3,000. Missing days are not assumed zero.',
            'clicks':clicks if daily else None,'impressions':impressions if daily else None,
            'ctr':clicks/impressions if impressions else None,
            'average_position':sum(r.position*r.impressions for r in daily)/impressions if impressions else None}
        with transaction.atomic():
            current=SearchMetricsRun.objects.select_for_update().get(pk=run_id)
            if current.state!='running': return
            connection=GoogleConnection.objects.select_for_update().get(site=run.site)
            current_connection(run)
            SearchMetric.objects.bulk_create(daily+detail)
            current.state='succeeded';current.report=report;current.finished_at=timezone.now();current.save()
            AuditEvent.objects.create(site=run.site,organization=run.site.organization,actor=run.actor,action='google.metrics_synced',target=str(run.pk))
    except Exception as e:
        code=str(e) if isinstance(e,GoogleFailure) else 'google_metrics_sync_failed'
        SearchMetricsRun.objects.filter(pk=run_id,state='running').update(state='failed',error_code=code,finished_at=timezone.now())
