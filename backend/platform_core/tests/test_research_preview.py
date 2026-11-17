import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from django.db import IntegrityError, transaction
from platform_core.models import ResearchRun, KnowledgeSource
from platform_core.public_http import Response
from platform_core.research import collect, research_site, scoped_url
from platform_core.research_ai import ProfileSuggestions
from .test_authorization import portfolio

def page(url,html):
    return Response(url,200,{'content-type':'text/html'},html.encode())

def test_crawl_is_bounded_and_preserves_owner_facts(portfolio):
    site=portfolio['a']
    original=site.verified_facts
    html='<title>Shop</title><h1>Wide Leg Jeans</h1>'+''.join(f'<a href="/product-category/{i}/">Category</a>' for i in range(20))+'<a href="http://127.0.0.1/admin">x</a>'
    def fetch(url,**kwargs):
        kwargs['before_fetch'](url)
        return page(url,html)
    with patch('platform_core.research.allowed_by_robots',return_value=True),patch('platform_core.research.fetch_public',side_effect=fetch) as http:
        result=collect(site)
    assert http.call_count==5 and len(result['pages'])==5
    assert result['keyword_candidates'][0]['search_volume'] is None
    assert result['competitors']==[]
    site.refresh_from_db()
    assert site.verified_facts==original

def test_scope_excludes_transactions_and_external_origins():
    root='https://shop.test/'
    for url in ['http://shop.test/a','https://evil.test/a','https://shop.test/checkout/','https://shop.test/a?token=x','https://u:p@shop.test/a']:
        assert scoped_url(url,root) is None

def test_research_job_persists_sources_without_publishing(portfolio):
    p=portfolio
    run=ResearchRun.objects.create(site=p['a'],actor=p['owner'])
    report={'pages':[{'url':p['a'].url,'title':'Shop','excerpt':'Observed','content_hash':'a'*64}], 'warnings':[]}
    with patch('platform_core.research.collect',return_value=report) as crawl:
        research_site(str(run.pk)); research_site(str(run.pk))
    run.refresh_from_db()
    assert run.state=='succeeded' and run.stage=='review' and run.ai_calls==0
    assert crawl.call_count==1 and run.sources.count()==1
    assert KnowledgeSource.objects.get(pk=run.sources.first().pk).approved_by_id is None

def test_revoked_research_does_not_fetch(portfolio):
    p=portfolio
    run=ResearchRun.objects.create(site=p['a'],actor=p['staff'])
    p['membership'].active=False;p['membership'].save()
    with patch('platform_core.research.collect') as crawl:
        research_site(str(run.pk))
    run.refresh_from_db()
    assert run.state=='cancelled' and not crawl.called

def test_duplicate_active_run_blocked(portfolio):
    p=portfolio
    ResearchRun.objects.create(site=p['a'],actor=p['owner'])
    with pytest.raises(IntegrityError),transaction.atomic():
        ResearchRun.objects.create(site=p['a'],actor=p['owner'])

def test_research_and_preview_are_tenant_scoped(client,portfolio):
    client.force_login(portfolio['owner'])
    for route in ('research/','preview/','preview/image/?url=https://example.test/a.png'):
        assert client.get(f'/sites/{portfolio["c"].pk}/{route}').status_code==404
    assert client.get(f'/sites/{portfolio["a"].pk}/research/').status_code==200
    assert client.get(f'/sites/{portfolio["a"].pk}/preview/').status_code==200

def test_preview_escapes_injected_script(client,portfolio):
    p=portfolio;client.force_login(p['owner'])
    response=client.post(f'/sites/{p["a"].pk}/preview/',{'url':p['a'].url,'title':'</script><script>alert(1)</script>','description':'" onerror="alert(1)','operation':'preview'})
    assert response.status_code==200
    assert b'</script><script>alert(1)</script>' not in response.content
    assert b'\\u003C/script\\u003E' in response.content

def test_preview_images_reject_tokens_and_active_content(client,portfolio):
    client.force_login(portfolio['owner']);url=f'/sites/{portfolio["a"].pk}/preview/image/'
    with patch('platform_core.preview_views.fetch_public') as fetch:
        assert client.get(url,{'url':'https://example.test/a.png?secret=x'}).status_code==404
        assert not fetch.called
    with patch('platform_core.preview_views.allowed_by_robots',return_value=True),patch('platform_core.preview_views.fetch_public',return_value=Response('https://example.test/a.svg',200,{'content-type':'image/svg+xml'},b'<svg onload="alert(1)"/>')):
        assert client.get(url,{'url':'https://example.test/a.svg'}).status_code==404

def test_ai_rejects_unknown_sources(settings,portfolio):
    from platform_core.research_ai import suggest_profile
    settings.RESEARCH_AI_ENABLED=True;settings.GEMINI_API_KEY='synthetic';settings.GEMINI_MODEL='synthetic-model'
    output=json.dumps({'suggestions':[{'field':'audience','value':'Shoppers','source_urls':['https://invented.test/'],'explanation':'guess'}],'uncertainties':[]})
    with patch('google.genai.Client') as provider:
        provider.return_value.__enter__.return_value.interactions.create.return_value=SimpleNamespace(output_text=output)
        with pytest.raises(ValueError):
            suggest_profile(portfolio['a'],[{'url':portfolio['a'].url,'title':'Shop','headings':[],'excerpt':'Shop'}])
        args=provider.return_value.__enter__.return_value.interactions.create.call_args.kwargs
        assert provider.call_args.kwargs['http_options']['httpx_client'].follow_redirects is False
        assert args['store'] is False and args['automatic_continuation'] is False
        assert args['generation_config']['max_output_tokens']==2048 and 'tools' not in args
        assert args['generation_config']['thinking_level']=='low' and args['timeout']==90
        assert 'temperature' not in args['generation_config']

def test_ai_schema_forbids_unsupported_business_facts():
    with pytest.raises(ValueError):
        ProfileSuggestions.model_validate({'suggestions':[{'field':'verified_facts','value':'Free delivery','source_urls':['https://shop.test/'],'explanation':'claim'}],'uncertainties':[]})

def test_url_only_setup_creates_paused_profile(client,portfolio):
    from platform_core.models import Site
    client.force_login(portfolio['owner'])
    with patch('platform_core.research_views.enqueue_research'):
        response=client.post('/sites/discover/',{'url':'https://new-store.example.test/'})
    assert response.status_code==302
    site=Site.objects.get(url='https://new-store.example.test')
    assert site.paused and site.environment=='production' and site.verified_facts==''
    assert site.research_runs.count()==1
    # A second submission reuses both the website and the active run.
    client.post('/sites/discover/',{'url':'https://new-store.example.test/'})
    assert Site.objects.filter(pk=site.pk).count()==1 and site.research_runs.count()==1

def test_url_setup_requires_owner_and_rejects_credentials(client,portfolio):
    client.force_login(portfolio['staff'])
    assert client.post('/sites/discover/',{'url':'https://new.example.test/'}).status_code==404
    client.force_login(portfolio['owner'])
    response=client.post('/sites/discover/',{'url':'https://user:password@new.example.test/'})
    assert response.status_code==200
    assert not ResearchRun.objects.exists()

def test_paid_call_limit_preserves_collected_evidence(settings,portfolio):
    p=portfolio;settings.RESEARCH_AI_ENABLED=True;settings.GEMINI_API_KEY='synthetic';settings.GEMINI_MODEL='synthetic'
    for _ in range(5):
        from django.utils import timezone
        ResearchRun.objects.create(site=p['a'],actor=p['owner'],state='succeeded',ai_calls=1,ai_reserved_at=timezone.now())
    run=ResearchRun.objects.create(site=p['a'],actor=p['owner'],use_ai=True)
    report={'pages':[{'url':p['a'].url,'title':'Shop','excerpt':'Observed','content_hash':'a'*64}],'warnings':[]}
    with patch('platform_core.research.collect',return_value=report),patch('platform_core.research_ai.suggest_profile') as provider:
        research_site(str(run.pk))
    run.refresh_from_db()
    assert run.state=='succeeded' and run.ai_calls==0 and not provider.called
    assert run.sources.exists() and run.report['warnings']

def test_provider_transport_enforces_one_actual_request():
    import httpx
    from platform_core.research_ai import SingleRequestTransport
    calls=[]
    transport=SingleRequestTransport(httpx.MockTransport(lambda request:(calls.append(request),httpx.Response(503))[1]))
    request=httpx.Request('POST','https://generativelanguage.googleapis.com/v1beta/interactions')
    assert transport.handle_request(request).status_code==503
    with pytest.raises(ValueError):
        transport.handle_request(request)
    assert len(calls)==1

def test_real_sdk_serializes_request_with_mock_http(settings,portfolio):
    import httpx
    from platform_core.research_ai import suggest_profile, SingleRequestTransport
    settings.RESEARCH_AI_ENABLED=True;settings.GEMINI_API_KEY='synthetic';settings.GEMINI_MODEL='synthetic-model'
    calls=[]
    output=json.dumps({'suggestions':[],'uncertainties':['Insufficient evidence']})
    def reply(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'synthetic-interaction','status':'completed','steps':[{
            'type':'model_output','content':[{'type':'text','text':output}]}]})
    transport=SingleRequestTransport(httpx.MockTransport(reply))
    with patch('platform_core.research_ai.SingleRequestTransport',return_value=transport):
        result=suggest_profile(portfolio['a'],[{'url':portfolio['a'].url,'title':'Shop','headings':[],'excerpt':'Shop'}])
    assert result['suggestions']==[] and len(calls)==1
    assert calls[0]['store'] is False and calls[0]['generation_config']['max_output_tokens']==2048

def test_provider_error_codes_never_include_response_or_credentials():
    from platform_core.research_ai import failure_code
    class ProviderError(Exception):
        status_code=403
    assert failure_code(ProviderError('secret-key and untrusted response'))=='provider_http_403'
    assert failure_code(ValueError('private prompt text'))=='provider_schema_or_evidence_rejected'
