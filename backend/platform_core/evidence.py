"""Deterministic, bounded HTML evidence extraction; no ranking/volume claims."""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

class EvidenceParser(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.titles = []
        self.descriptions = []
        self.canonicals = []
        self.robots = []
        self.social = {}
        self.headings = []
        self.links = []
        self.text = []
        self.text_length = 0
        self.hidden = 0
        self.current = None
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style', 'noscript', 'template'):
            self.hidden += 1
        if self.hidden:
            return
        if tag == 'title' or tag in ('h1', 'h2', 'h3'):
            self.current, self.buffer = tag, []
        if tag == 'meta':
            name = attrs.get('name', '').lower()
            if name == 'description': self.descriptions.append(attrs.get('content', '')[:1000])
            if name == 'robots': self.robots.append(attrs.get('content', '')[:500])
            social_key=attrs.get('property',name).lower()
            if social_key in ('og:title','og:description','og:image','og:type','og:url','twitter:title','twitter:description','twitter:image','twitter:card'):
                self.social[social_key]=attrs.get('content','')[:2048]
        if tag == 'link' and 'canonical' in attrs.get('rel', '').lower().split():
            self.canonicals.append(urljoin(self.url, attrs.get('href', '')))
        if tag == 'a' and attrs.get('href') and len(self.links) < 2000:
            self.links.append(urljoin(self.url, attrs['href']))

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.hidden = max(0, self.hidden - 1)
            return
        if not self.hidden and tag == self.current:
            value = re.sub(r'\s+', ' ', ' '.join(self.buffer)).strip()[:1000]
            if tag == 'title': self.titles.append(value)
            else: self.headings.append((tag, value))
            self.current, self.buffer = None, []

    def handle_data(self, value):
        if not self.hidden:
            if self.current: self.buffer.append(value)
            if self.text_length < 100_000:
                clipped = value[:100_000 - self.text_length]
                self.text.append(clipped)
                self.text_length += len(clipped)

def extract(url, html):
    parser = EvidenceParser(url)
    parser.feed(html[:2_000_000])
    return parser

def audit(evidence, status=200):
    issues = []
    def issue(code, severity, excerpt, remediation):
        issues.append({'code': code, 'severity': severity, 'evidence': excerpt[:1000], 'url': evidence.url,
                       'rule_version': 'head-v1', 'remediation': remediation})
    if status >= 400: issue('http_error', 'critical', str(status), 'Investigate the observed HTTP error before editing metadata.')
    if not evidence.titles: issue('title_missing', 'high', 'No title element observed.', 'Verify template title support and the selected SEO owner.')
    elif len(evidence.titles) > 1: issue('title_duplicate', 'high', ' | '.join(evidence.titles), 'Resolve duplicate title output between theme/plugins.')
    if not evidence.descriptions: issue('description_missing', 'medium', 'No meta description observed.', 'Review whether an original, factual description is appropriate.')
    elif len(evidence.descriptions) > 1: issue('description_duplicate', 'high', ' | '.join(evidence.descriptions), 'Choose one SEO metadata renderer.')
    if len(evidence.canonicals) > 1: issue('canonical_duplicate', 'high', ' | '.join(evidence.canonicals), 'Review conflicting canonical output.')
    return issues

RUBRIC = {'technical': 30, 'on_page': 25, 'architecture': 20, 'schema': 10, 'performance': 15}

def health_score(observed):
    """Each category is None (unknown), 'na', or a validated fraction 0..1."""
    if set(observed) - set(RUBRIC): raise ValueError('Unknown score category.')
    known = {}
    applicable_weight = 0
    for category, weight in RUBRIC.items():
        value = observed.get(category)
        if value == 'na': continue
        applicable_weight += weight
        if value is None: continue
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value <= 1:
            raise ValueError('Observed checks must be fractions in [0, 1].')
        known[category] = value
    known_weight = sum(RUBRIC[c] for c in known)
    coverage = known_weight / applicable_weight if applicable_weight else 0
    return {'name': 'SEO Health Score', 'rubric': 'health-v1',
            'score': round(sum(RUBRIC[c] * v for c, v in known.items()) / known_weight * 100, 1) if known_weight and coverage >= .5 else None,
            'coverage': round(coverage, 3), 'confidence': 'limited' if coverage < .8 else 'observed',
            'unknown': [c for c in RUBRIC if observed.get(c) is None],
            'not_applicable': [c for c in RUBRIC if observed.get(c) == 'na']}
