import pytest
from django.utils import timezone
from platform_core.models import ResearchRun,KnowledgeSource,Page,KeywordCandidate
from platform_core.keywords import build_candidates
from .test_authorization import portfolio

@pytest.fixture
def keywords(portfolio):
    p=portfolio
    source=KnowledgeSource.objects.create(site=p['a'],url=p['a'].url,title='Observed page',excerpt='Wide Leg Jeans',content_hash='a'*64)
    run=ResearchRun.objects.create(site=p['a'],actor=p['owner'],state='succeeded')
    run.sources.add(source)
    report={'keyword_candidates':[{'phrase':'Wide Leg Jeans','source_url':source.url}]}
    build_candidates(run,report)
    return p,run,report,KeywordCandidate.objects.get(site=p['a'])

def test_crawl_deduplicates_and_preserves_human_mapping(keywords):
    p,run,report,candidate=keywords
    target=Page.objects.create(site=p['a'],url=p['a'].url+'/jeans',title='Jeans')
    candidate.target_page=target;candidate.intent='commercial';candidate.locked=True;candidate.reviewed_at=timezone.now();candidate.save()
    report['keyword_candidates'][0]['phrase']=' WIDE   LEG JEANS '
    build_candidates(run,report)
    candidate.refresh_from_db()
    assert KeywordCandidate.objects.filter(site=p['a']).count()==1
    assert candidate.target_page==target and candidate.locked and candidate.intent=='commercial'

def test_foreign_sources_are_not_imported(keywords):
    p,run,report,candidate=keywords
    build_candidates(run,{'keyword_candidates':[{'phrase':'Invented keyword','source_url':p['c'].url}]})
    assert KeywordCandidate.objects.count()==1

def test_map_requires_current_permission_and_scoped_page(client,keywords):
    p,run,report,candidate=keywords
    foreign=Page.objects.create(site=p['c'],url=p['c'].url+'/foreign')
    client.force_login(p['staff'])
    path=f'/sites/{p["a"].pk}/keywords/'
    assert client.post(path,{'candidate':candidate.pk,'intent':'commercial'}).status_code==404
    client.force_login(p['owner'])
    response=client.post(path,{'candidate':candidate.pk,'target_page':foreign.pk,'intent':'commercial','locked':'on'})
    assert response.status_code==200 and response.context['form'].errors
    candidate.refresh_from_db()
    assert candidate.target_page_id is None and candidate.reviewed_at is None

def test_owner_can_review_assignment_without_publishing(client,keywords):
    p,run,report,candidate=keywords
    page=Page.objects.create(site=p['a'],url=p['a'].url+'/target',title='Target')
    client.force_login(p['owner'])
    response=client.post(f'/sites/{p["a"].pk}/keywords/',{'candidate':candidate.pk,'target_page':page.pk,'intent':'commercial','locked':'on'})
    assert response.status_code==302
    candidate.refresh_from_db()
    assert candidate.target_page==page and candidate.locked and candidate.reviewed_by==p['owner']

def test_keyword_views_and_export_scoped_and_csv_safe(client,keywords):
    p,run,report,candidate=keywords
    client.force_login(p['owner'])
    assert client.get(f'/sites/{p["c"].pk}/keywords/').status_code==404
    assert client.get(f'/sites/{p["c"].pk}/keywords/export/').status_code==404
    assert client.get(f'/sites/{p["a"].pk}/keywords/?edit=not-a-uuid').status_code==404
    candidate.phrase='=1+1';candidate.save()
    response=client.get(f'/sites/{p["a"].pk}/keywords/export/')
    assert response.status_code==200 and b"'=1+1" in response.content
    assert b'unknown,unknown' in response.content
    assert response['Cache-Control']=='private, no-store'
    assert client.get(f'/sites/{p["a"].pk}/keywords/').status_code==200
