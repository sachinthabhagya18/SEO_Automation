import hashlib
import secrets
import uuid
from datetime import timedelta
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from .models import User, Membership, RoleBundle, SiteAssignment, ServiceCredential, AuditSchedule, Site, Job, PageSnapshot, AuditEvent
from .permissions import can

@transaction.atomic
def issue_service_credential(site, owner,scope='public_audit'):
    if not can(owner, site, 'manage_automation'): raise PermissionDenied('Automation management permission required.')
    if scope not in ('public_audit','research_drafts','search_metrics'): raise PermissionDenied('Unsupported service scope.')
    ServiceCredential.objects.filter(site=site,scope=scope).update(active=False)
    key=uuid.uuid4().hex
    actor=User(username=scope+'-service-'+key,email=key+'@automation.invalid',is_service_account=scope!='public_audit')
    actor.set_unusable_password();actor.save()
    member=Membership.objects.create(organization=site.organization,user=actor)
    label={'public_audit':'Audit automation','research_drafts':'Research automation','search_metrics':'Search metrics automation'}[scope]
    group,_=Group.objects.get_or_create(name=f'org:{site.organization_id}:{label}')
    bundle,_=RoleBundle.objects.get_or_create(organization=site.organization,label=label,defaults={'group':group})
    actions={'public_audit':['view_site','run_audit'],
        'research_drafts':['view_site','run_keyword_research','generate_ai_draft','edit_draft','submit_for_review'],
        'search_metrics':['view_site','view_analytics','sync_search_metrics']}[scope]
    group.permissions.set(Permission.objects.filter(content_type__app_label='platform_core',content_type__model='site',codename__in=actions))
    SiteAssignment.objects.create(membership=member,site=site,bundle=bundle)
    token=secrets.token_urlsafe(48)
    credential=ServiceCredential.objects.create(site=site,actor=actor,scope=scope,token_digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(days=30))
    AuditEvent.objects.create(organization=site.organization,site=site,actor=owner,action='automation.service_credential_issued',target=str(credential.pk))
    return credential,token

class AuditServiceAuthentication(BaseAuthentication):
    scope='public_audit'
    action='run_audit'
    def authenticate(self,request):
        header=request.headers.get('Authorization','')
        if not header.startswith('Bearer '): raise AuthenticationFailed('Scoped audit service credential required.')
        token=header[7:]
        if not 32<=len(token)<=200: raise AuthenticationFailed('Invalid service credential.')
        credential=ServiceCredential.objects.select_related('actor','site').filter(token_digest=hashlib.sha256(token.encode()).hexdigest(),active=True,expires_at__gt=timezone.now(),scope=self.scope).first()
        if not credential or not can(credential.actor,credential.site,self.action): raise AuthenticationFailed('Invalid, expired or revoked service credential.')
        return credential.actor,credential

    def authenticate_header(self,request):
        return 'Bearer'

class DispatchRequest(serializers.Serializer):
    site_id=serializers.IntegerField(min_value=1)
    event_id=serializers.CharField(max_length=100)

class DispatchResponse(serializers.Serializer):
    job_id=serializers.UUIDField(allow_null=True)
    state=serializers.CharField()
    next_due=serializers.DateTimeField(allow_null=True,required=False)

class AutomationJobResponse(serializers.Serializer):
    job_id=serializers.UUIDField()
    state=serializers.CharField()
    error_code=serializers.CharField()
    scope=serializers.CharField()
    observed=serializers.JSONField(required=False)

class AuditServiceScheme(OpenApiAuthenticationExtension):
    target_class='platform_core.automation.AuditServiceAuthentication'
    name='AuditServiceBearer'
    def get_security_definition(self,auto_schema):
        return {'type':'http','scheme':'bearer','bearerFormat':'opaque site-scoped token'}

class AuditDispatchView(APIView):
    authentication_classes=[AuditServiceAuthentication]
    permission_classes=[IsAuthenticated]

    @extend_schema(request=DispatchRequest,responses={202:DispatchResponse})
    def post(self,request):
        from .api import create_public_audit
        form=DispatchRequest(data=request.data);form.is_valid(raise_exception=True)
        if set(request.data)-{'site_id','event_id'}: raise ValidationError('Unknown request fields.')
        if form.validated_data['site_id']!=request.auth.site_id: raise PermissionDenied('Service credential is restricted to its assigned site.')
        key=uuid.uuid5(uuid.NAMESPACE_URL,f'audit-event:{request.auth.site_id}:{form.validated_data["event_id"]}')
        job,_=create_public_audit(request.auth.site,request.user,key,service_credential=request.auth)
        return Response({'job_id':job.pk,'state':job.state},status=202)

class DueDispatchView(APIView):
    authentication_classes=[AuditServiceAuthentication]
    permission_classes=[IsAuthenticated]

    @extend_schema(request=None,responses={200:DispatchResponse})
    @transaction.atomic
    def post(self,request):
        from .api import create_public_audit
        if request.data: raise ValidationError('Schedule target is bound to the credential; request body must be empty.')
        schedule=AuditSchedule.objects.select_for_update().filter(site=request.auth.site).first()
        now=timezone.now()
        if not schedule or not schedule.enabled or not schedule.next_due or schedule.next_due>now:
            return Response({'job_id':None,'state':'not_due','next_due':schedule.next_due if schedule else None})
        key=uuid.uuid5(uuid.NAMESPACE_URL,f'due-audit:{schedule.site_id}:{schedule.next_due.isoformat()}')
        job,_=create_public_audit(request.auth.site,request.user,key,service_credential=request.auth)
        schedule.last_dispatched_at=now
        schedule.next_due=now+timedelta(minutes=schedule.interval_minutes)
        schedule.save(update_fields=['next_due','last_dispatched_at'])
        return Response({'job_id':job.pk,'state':job.state,'next_due':schedule.next_due})

class AutomationJobView(APIView):
    authentication_classes=[AuditServiceAuthentication]
    permission_classes=[IsAuthenticated]

    @extend_schema(responses={200:AutomationJobResponse})
    def get(self,request,job_id):
        from django.shortcuts import get_object_or_404
        job=get_object_or_404(Job,pk=job_id,site=request.auth.site)
        result={'job_id':job.pk,'state':job.state,'error_code':job.error_code,'scope':'single_public_page_head_checks'}
        snapshot=PageSnapshot.objects.filter(job=job).first()
        if snapshot:
            result['observed']={'title':snapshot.title,'description':snapshot.description,'status_code':snapshot.status_code,
                                'issues':list(snapshot.issues.values('code','severity','remediation'))}
        return Response(result)
