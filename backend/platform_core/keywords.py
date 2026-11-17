import hashlib
from .models import KeywordCandidate
from .research_proposals import plain

def build_candidates(run,report):
    for item in report.get('keyword_candidates',[])[:40]:
        phrase=plain(item.get('phrase',''),200)
        source=run.sources.filter(site=run.site,url=item.get('source_url','')).first()
        if not phrase or not source: continue
        key=hashlib.sha256(phrase.casefold().encode()).hexdigest()
        # Existing owner assignments, intents and locks are never replaced by a crawl.
        KeywordCandidate.objects.get_or_create(site=run.site,phrase_key=key,observed_url=source.url,
            defaults={'phrase':phrase,'source':source})
