"""Local-only HTTP smoke checks; never use this as the production crawler."""
from html.parser import HTMLParser
from urllib.request import urlopen

class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.titles = []
        self.metadata = []
        self.canonicals = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self.in_title = True
            self.titles.append('')
        if tag == 'meta': self.metadata.append(attrs)
        if tag == 'link' and attrs.get('rel') == 'canonical': self.canonicals.append(attrs.get('href'))

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False

    def handle_data(self, data):
        if self.in_title: self.titles[-1] += data

def get(url):
    with urlopen(url, timeout=10) as response:
        assert response.status == 200, url
        return response.read().decode('utf-8')

assert 'Welcome back' in get('http://localhost:8000/accounts/login/')
assert len(get('http://localhost:8000/static/dist/app.css')) > 1000
assert len(get('http://localhost:8000/static/dist/alpine.min.js')) > 1000
head = Head()
head.feed(get('http://localhost:8081/'))
assert head.titles == ['SYNTHETIC Service SEO Title'], head.titles
descriptions = [m for m in head.metadata if m.get('name') == 'description']
assert len(descriptions) == 1 and descriptions[0]['content'].startswith('Synthetic description')
assert len(head.canonicals) == 1, head.canonicals
robots = [m for m in head.metadata if m.get('name') == 'robots']
assert len(robots) == 1 and 'noindex' in robots[0]['content'], robots
assert len([m for m in head.metadata if m.get('property') == 'og:title']) == 1
assert 'ok' in get('http://localhost:5679/healthz').lower()
print('HTTP smoke passed: app login/assets, n8n health, WordPress title/description/canonical/robots/Open Graph exactly once; staging privacy preserved.')
