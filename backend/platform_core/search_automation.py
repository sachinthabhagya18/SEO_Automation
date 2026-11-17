import uuid
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from .automation import AuditServiceAuthentication,AuditServiceScheme,DispatchRequest
from .google_search import GoogleFailure
from .models import SearchMetricsRun
from .search_metrics import queue_sync

class SearchMetricsAuthentication(AuditServiceAuthentication):
    scope='search_metrics'
    action='sync_search_metrics'

class SearchMetricsScheme(AuditServiceScheme):
    target_class='platform_core.search_automation.SearchMetricsAuthentication'
    name='SearchMetricsBearer'

class SearchMetricsResponse(serializers.Serializer):
    run_id=serializers.UUIDField(allow_null=True)
    state=serializers.CharField()
    error_code=serializers.CharField(required=False)
    summary=serializers.JSONField(required=False)

class SearchMetricsDispatch(APIView):
    authentication_classes=[SearchMetricsAuthentication]
    permission_classes=[IsAuthenticated]
    @extend_schema(request=DispatchRequest,responses={200:SearchMetricsResponse,202:SearchMetricsResponse})
    def post(self,request):
        form=DispatchRequest(data=request.data);form.is_valid(raise_exception=True)
        if set(request.data)-{'site_id','event_id'}: raise ValidationError('Unknown fields.')
        if form.validated_data['site_id']!=request.auth.site_id: raise PermissionDenied('Wrong service target.')
        key=uuid.uuid5(uuid.NAMESPACE_URL,f'google-sync-event:{request.auth.site_id}:{form.validated_data["event_id"]}')
        try: run=queue_sync(request.auth.site,request.user,key)
        except GoogleFailure as error:
            return Response({'run_id':None,'state':'blocked','error_code':str(error)})
        return Response({'run_id':run.pk,'state':run.state},status=202)

class SearchMetricsResult(APIView):
    authentication_classes=[SearchMetricsAuthentication]
    permission_classes=[IsAuthenticated]
    @extend_schema(responses={200:SearchMetricsResponse})
    def get(self,request,run_id):
        run=get_object_or_404(SearchMetricsRun,pk=run_id,site=request.auth.site)
        return Response({'run_id':run.pk,'state':run.state,'error_code':run.error_code,'summary':run.report})
