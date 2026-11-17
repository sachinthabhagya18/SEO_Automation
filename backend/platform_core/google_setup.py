"""Assisted Domain-property setup. A DNS match is not Google ownership approval."""
import ipaddress
import json
import re
import shlex
from urllib.parse import urlsplit
import httpx
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from .models import SearchConsoleSetup,AuditEvent
from .permissions import can,visible_sites

def site_domain(site):
    host=(urlsplit(site.url).hostname or '').rstrip('.').encode('idna').decode('ascii').lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?',host) or '.' not in host:
        raise ValueError('domain_required')
    try: ipaddress.ip_address(host)
    except ValueError: return host
    raise ValueError('domain_required')

class VerificationForm(forms.Form):
    txt_value=forms.RegexField(regex=r'^google-site-verification=[A-Za-z0-9_-]{10,200}$',max_length=230,
        label='TXT value copied from your Google Search Console account',
        help_text='Paste the exact public verification record Google issued. Do not enter an API key or password.')

def lookup_txt(domain):
    with httpx.Client(timeout=10,trust_env=False,follow_redirects=False) as client:
        with client.stream('GET','https://cloudflare-dns.com/dns-query',params={'name':domain,'type':'TXT'},
            headers={'Accept':'application/dns-json'}) as response:
            if response.status_code!=200: raise ValueError('dns_lookup_failed')
            body=bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body)>65536: raise ValueError('dns_lookup_failed')
    data=json.loads(body)
    if data.get('Status')!=0: raise ValueError('dns_lookup_failed')
    records=[]
    for answer in data.get('Answer',[])[:100]:
        if answer.get('type')==16 and answer.get('name','').rstrip('.').lower()==domain:
            try: records.append(''.join(shlex.split(answer.get('data',''))))
            except ValueError: continue
    return records

@login_required
def setup(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    if not can(request.user,site,'manage_integrations'): raise Http404
    try: domain=site_domain(site)
    except ValueError: raise Http404
    record=SearchConsoleSetup.objects.filter(site=site).first()
    form=VerificationForm(request.POST if request.method=='POST' and request.POST.get('operation')=='save' else None,
        initial={'txt_value':record.txt_value if record and record.domain==domain else ''})
    if request.method=='POST':
        operation=request.POST.get('operation')
        if operation=='save' and form.is_valid():
            SearchConsoleSetup.objects.update_or_create(site=site,defaults={'domain':domain,'txt_value':form.cleaned_data['txt_value'],
                'dns_observed':False,'checked_at':None,'error_code':''})
            AuditEvent.objects.create(site=site,organization=site.organization,actor=request.user,action='google.verification_record_saved',target=domain)
            messages.success(request,'Verification record saved locally. Add this TXT record in Cloudflare, then check public DNS.')
            return redirect('google-setup',pk=site.pk)
        if operation=='check':
            if not record or record.domain!=domain:
                messages.error(request,'Save a Google-issued token for the current domain first.')
            else:
                try:
                    record.dns_observed=record.txt_value in lookup_txt(domain)
                    record.error_code='' if record.dns_observed else 'verification_txt_not_observed'
                except Exception:
                    record.dns_observed=False;record.error_code='dns_lookup_failed'
                record.checked_at=timezone.now();record.save(update_fields=['dns_observed','error_code','checked_at'])
                AuditEvent.objects.create(site=site,organization=site.organization,actor=request.user,action='google.verification_dns_checked',target=domain)
                messages.info(request,'DNS record observed. Complete Verify in your Google account; this is not proof of Google ownership approval.' if record.dns_observed else 'Matching TXT not observed. Check the exact record and allow DNS propagation.')
            return redirect('google-setup',pk=site.pk)
    return render(request,'platform/google_setup.html',{'site':site,'domain':domain,'record':record,'form':form,
        'record_current':bool(record and record.domain==domain)})
