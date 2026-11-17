from urllib.parse import urlsplit, urljoin
from django import forms
from django.contrib.auth.decorators import login_required
from django.http import Http404,HttpResponse
from django.shortcuts import get_object_or_404,render
from .permissions import visible_sites
from .public_http import fetch_public
from .tasks import allowed_by_robots
from .evidence import extract
from .owned_http import site_fetch

class PreviewForm(forms.Form):
    url=forms.URLField(max_length=2048,assume_scheme='https')
    title=forms.CharField(max_length=200,required=False)
    description=forms.CharField(max_length=500,required=False,widget=forms.Textarea(attrs={'rows':4}))
    image_url=forms.URLField(max_length=2048,required=False,assume_scheme='https',help_text='Public image URL without credentials or query tokens. Images are proxied with network limits.')

@login_required
def preview(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    initial={'url':site.url,'title':site.name}
    form=PreviewForm(request.POST or None,initial=initial)
    values=initial
    if request.method=='POST' and form.is_valid():
        values=form.cleaned_data
        if request.POST.get('operation')=='fetch':
            try:
                if urlsplit(values['url']).hostname!=urlsplit(site.url).hostname: raise ValueError('Use this managed website’s URL.')
                def guard(url):
                    if urlsplit(url).hostname!=urlsplit(site.url).hostname or not allowed_by_robots(url,site=site): raise ValueError('Crawl scope or robots policy blocked this page.')
                response=site_fetch(site,values['url'],fetch=fetch_public,before_fetch=guard)
                if response.status!=200 or 'text/html' not in response.headers.get('content-type','').lower(): raise ValueError('Public HTML page required.')
                evidence=extract(response.url,response.body.decode('utf-8',errors='replace'))
                values={**values,'title':(evidence.titles or [''])[0][:200],'description':(evidence.descriptions or [''])[0][:500],
                    'image_url':urljoin(response.url,evidence.social.get('og:image',evidence.social.get('twitter:image',''))) if evidence.social.get('og:image',evidence.social.get('twitter:image','')) else ''}
                form=PreviewForm(initial=values)
            except Exception:
                form.add_error(None,'Could not read this public page within scope/robots/network limits. You can still preview typed values.')
    data={'site_id':site.pk,'url':values.get('url',site.url),'title':values.get('title',''),
          'description':values.get('description',''),'image_url':values.get('image_url','')}
    return render(request,'platform/preview.html',{'site':site,'form':form,'preview_data':data})

@login_required
def preview_image(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    url=request.GET.get('url','')
    try:
        parts=urlsplit(url)
        if len(url)>2048 or parts.scheme not in ('http','https') or parts.username or parts.password or parts.query or parts.fragment: raise ValueError()
        if not allowed_by_robots(url,site=site): raise ValueError()
        response=site_fetch(site,url,fetch=fetch_public,max_bytes=1_000_000,max_redirects=0)
        content_type=response.headers.get('content-type','').split(';')[0].strip().lower()
        body=response.body
        valid=(content_type=='image/png' and body.startswith(b'\x89PNG\r\n\x1a\n')) or \
            (content_type=='image/jpeg' and body.startswith(b'\xff\xd8\xff')) or \
            (content_type=='image/gif' and body.startswith((b'GIF87a',b'GIF89a'))) or \
            (content_type=='image/webp' and body.startswith(b'RIFF') and body[8:12]==b'WEBP')
        if response.status!=200 or not valid: raise ValueError()
    except Exception: raise Http404
    result=HttpResponse(body,content_type=content_type)
    result['Cache-Control']='private, max-age=300'
    result['X-Content-Type-Options']='nosniff'
    return result
