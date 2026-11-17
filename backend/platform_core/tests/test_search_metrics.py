import uuid
from unittest.mock import patch
import pytest
from platform_core.models import GoogleConnection,SearchMetric
from platform_core.search_metrics import queue_sync,sync_search_metrics
from platform_core.google_search import GoogleFailure
from .test_authorization import portfolio
from .test_google_connection import google_setup,connected

def ready(p):
    c=connected(p);c.status='connected';c.property_url='sc-domain:assigned.example.test';c.save()
    with patch('platform_core.search_metrics.dispatch_sync'): run=queue_sync(p['a'],p['owner'])
    return c,run

def reply(run,detail=False,query='observed query'):
    keys=[run.start_date.isoformat()]
    if detail: keys += [run.bound_url.rstrip('/')+'/product/',query,'lka','MOBILE']
    return {'rows':[{'keys':keys,'clicks':10,'impressions':100,'ctr':0.1,'position':2.5}]}

def test_daily_totals_are_not_double_counted_with_detail_rows(google_setup):
    p=google_setup;c,run=ready(p)
    with patch('platform_core.search_metrics.request_json',side_effect=[reply(run),reply(run,True)]) as http:
        sync_search_metrics(str(run.pk))
    run.refresh_from_db();assert run.state=='succeeded' and run.report['clicks']==10 and run.report['impressions']==100
    assert run.metrics.count()==2 and run.report['average_position']==2.5
    assert http.call_count==2 and http.call_args.kwargs['body']['dataState']=='final'

def test_empty_google_results_are_unknown_not_zero(google_setup):
    p=google_setup;c,run=ready(p)
    with patch('platform_core.search_metrics.request_json',return_value={}): sync_search_metrics(str(run.pk))
    run.refresh_from_db();assert run.state=='succeeded' and run.report['clicks'] is None and run.report['average_position'] is None

def test_deduplicated_event_and_revoked_connection_do_not_send_requests(google_setup):
    p=google_setup;c,run=ready(p)
    assert queue_sync(p['a'],p['owner'],run.event_key).pk==run.pk
    c.status='revoked';c.credential_version=uuid.uuid4();c.save()
    with patch('platform_core.search_metrics.request_json') as http: sync_search_metrics(str(run.pk))
    run.refresh_from_db();assert run.state=='cancelled' and not http.called

def test_connection_rotation_mid_fetch_rolls_back_all_metric_rows(google_setup):
    p=google_setup;c,run=ready(p)
    def rotate(*a,**kw):
        c.credential_version=uuid.uuid4();c.save();return reply(run)
    with patch('platform_core.search_metrics.request_json',side_effect=rotate): sync_search_metrics(str(run.pk))
    run.refresh_from_db();assert run.state=='failed' and not run.metrics.exists()

def test_nonfinite_numbers_are_rejected_without_partial_data(google_setup):
    p=google_setup;c,run=ready(p);bad=reply(run);bad['rows'][0]['position']=float('nan')
    with patch('platform_core.search_metrics.request_json',return_value=bad): sync_search_metrics(str(run.pk))
    run.refresh_from_db();assert run.state=='failed' and not run.metrics.exists()

def test_metrics_are_scoped_and_csv_neutralizes_formulas(google_setup,client):
    p=google_setup;c,run=ready(p)
    with patch('platform_core.search_metrics.request_json',side_effect=[reply(run),reply(run,True,'=UNTRUSTED()')]): sync_search_metrics(str(run.pk))
    client.force_login(p['owner']);r=client.get(f"/sites/{p['a'].pk}/analytics/export/")
    assert r.status_code==200 and b"'=UNTRUSTED()" in r.content
    client.force_login(p['staff'])
    assert client.get(f"/sites/{p['b'].pk}/analytics/").status_code==404

def test_query_pagination_is_bounded_and_invalid_foreign_url_rejected(google_setup):
    p=google_setup;c,run=ready(p);bad=reply(run,True);bad['rows'][0]['keys'][1]='https://foreign.example.test/'
    with patch('platform_core.search_metrics.request_json',side_effect=[reply(run),bad]): sync_search_metrics(str(run.pk))
    run.refresh_from_db();assert run.state=='failed' and run.error_code=='google_foreign_metric_page'

def test_detail_pagination_stops_at_three_thousand_rows_and_labels_cap(google_setup):
    p=google_setup;c,run=ready(p)
    pages=[]
    for page in range(3):
        rows=[reply(run,True,f'query {page*1000+i}')['rows'][0] for i in range(1000)]
        pages.append({'rows':rows})
    with patch('platform_core.search_metrics.request_json',side_effect=[reply(run)]+pages) as http:
        sync_search_metrics(str(run.pk))
    run.refresh_from_db()
    assert run.state=='succeeded' and run.report['detail_cap_reached'] and run.report['detail_rows']==3000
    assert run.report['clicks']==10 and http.call_count==4
