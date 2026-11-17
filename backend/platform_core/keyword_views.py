import csv
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404,HttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from .models import KeywordCandidate,Page,AuditEvent
from .permissions import can,visible_sites

class KeywordMapForm(forms.ModelForm):
    class Meta:
        model=KeywordCandidate
        fields=['target_page','intent','locked']

    def __init__(self,*args,site,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['target_page'].queryset=Page.objects.filter(site=site).order_by('url')
        self.fields['target_page'].required=False
        self.fields['locked'].help_text='Keep this human assignment protected from future automated remapping.'

@login_required
def keyword_map(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    selected=request.POST.get('candidate') if request.method=='POST' else request.GET.get('edit')
    candidate=None;form=None
    if selected:
        try: candidate=get_object_or_404(KeywordCandidate,pk=selected,site=site)
        except (ValueError,forms.ValidationError): raise Http404
        if not can(request.user,site,'edit_keyword_map'): raise Http404
        form=KeywordMapForm(request.POST or None,site=site,instance=candidate)
    if request.method=='POST':
        if not candidate or not can(request.user,site,'edit_keyword_map'): raise Http404
        if form.is_valid():
            with transaction.atomic():
                current=KeywordCandidate.objects.select_for_update().get(pk=candidate.pk,site=site)
                current.target_page=form.cleaned_data['target_page'];current.intent=form.cleaned_data['intent'];current.locked=form.cleaned_data['locked']
                current.reviewed_by=request.user;current.reviewed_at=timezone.now();current.save()
                AuditEvent.objects.create(site=site,organization=site.organization,actor=request.user,action='keyword.mapping_reviewed',target=str(current.pk))
            messages.success(request,'Keyword assignment saved. Search demand remains unknown; nothing was published.')
            return redirect('keyword-map',pk=site.pk)
    candidates=site.keyword_candidates.select_related('target_page','source')
    query=request.GET.get('q','').strip()[:200]
    if query: candidates=candidates.filter(phrase__icontains=query)
    return render(request,'platform/keywords.html',{'site':site,'page_obj':Paginator(candidates,40).get_page(request.GET.get('page')),
        'form':form,'candidate':candidate,'q':query,'can_edit_map':can(request.user,site,'edit_keyword_map'),
        'can_export':can(request.user,site,'export_report')})

def csv_cell(value):
    value=str(value or '')
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value

@login_required
def keyword_export(request,pk):
    site=get_object_or_404(visible_sites(request.user),pk=pk)
    if not can(request.user,site,'export_report'): raise Http404
    response=HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition']='attachment; filename="keyword-map.csv"'
    response['Cache-Control']='private, no-store'
    writer=csv.writer(response)
    writer.writerow(['phrase','observed_url','target_url','intent','reviewed','locked','source_fetched_at','search_volume','difficulty'])
    for candidate in site.keyword_candidates.select_related('target_page','source').iterator(chunk_size=200):
        writer.writerow([csv_cell(value) for value in [candidate.phrase,candidate.observed_url,
            candidate.target_page.url if candidate.target_page_id else '',candidate.intent,bool(candidate.reviewed_at),candidate.locked,
            candidate.source.fetched_at.isoformat(),'unknown','unknown']])
    return response
