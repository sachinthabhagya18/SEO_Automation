"""Site-scoped n8n research; never approves or publishes."""
import uuid
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from .automation import AuditServiceAuthentication,AuditServiceScheme,DispatchRequest
from .models import Site,ResearchRun
from .research import enqueue_research

class ResearchServiceAuthentication(AuditServiceAuthentication):
    scope='research_drafts'
    action='run_keyword_research'

class ResearchServiceScheme(AuditServiceScheme):
    target_class='platform_core.research_automation.ResearchServiceAuthentication'
    name='ResearchServiceBearer'

class ResearchDispatchRequest(DispatchRequest):
    use_ai=serializers.BooleanField(default=False)

class ResearchResult(serializers.Serializer):
    run_id=serializers.UUIDField()
    state=serializers.CharField()
    error_code=serializers.CharField(required=False)
    ai_status=serializers.CharField(required=False)
    drafts=serializers.ListField(child=serializers.DictField(),required=False)

class ResearchDispatchView(APIView):
    authentication_classes=[ResearchServiceAuthentication]
    permission_classes=[IsAuthenticated]

    @extend_schema(request=ResearchDispatchRequest,responses={202:ResearchResult})
    @transaction.atomic
    def post(self,request):
        form=ResearchDispatchRequest(data=request.data);form.is_valid(raise_exception=True)
        if set(request.data)-{'site_id','event_id','use_ai'}: raise ValidationError('Unknown fields.')
        if form.validated_data['site_id']!=request.auth.site_id: raise PermissionDenied('Wrong service target.')
        site=Site.objects.select_for_update().get(pk=request.auth.site_id)
        key=uuid.uuid5(uuid.NAMESPACE_URL,f'research-event:{site.pk}:{form.validated_data["event_id"]}')
        run=ResearchRun.objects.filter(pk=key,site=site).first()
        if not run:
            run=ResearchRun.objects.filter(site=site,state__in=['queued','running']).first()
        if not run:
            run=ResearchRun.objects.create(pk=key,site=site,actor=request.user,use_ai=form.validated_data['use_ai'],auto_drafts=True)
            transaction.on_commit(lambda:enqueue_research(run.pk))
        return Response({'run_id':run.pk,'state':run.state},status=202)

class ResearchResultView(APIView):
    authentication_classes=[ResearchServiceAuthentication]
    permission_classes=[IsAuthenticated]

    @extend_schema(responses={200:ResearchResult})
    def get(self,request,run_id):
        run=get_object_or_404(ResearchRun,pk=run_id,site=request.auth.site)
        proposals=list(run.proposals.filter(page__isnull=False))
        waiting=run.auto_drafts and any(not p.change_id and not p.draft_error_code for p in proposals)
        return Response({'run_id':run.pk,'state':'drafting' if run.state=='succeeded' and waiting else run.state,
            'error_code':run.error_code,'ai_status':run.report.get('ai_status','not_requested'),
            'drafts':[{'change_id':str(p.change_id) if p.change_id else None,'url':p.url,'error_code':p.draft_error_code} for p in proposals]})
