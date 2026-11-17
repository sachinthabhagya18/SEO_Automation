from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
import hashlib
from .models import Site, Job
from .permissions import visible_sites, can
from .tasks import enqueue
from .connections import connection_status
from drf_spectacular.utils import extend_schema

class AuditRequest(serializers.Serializer):
    idempotency_key = serializers.UUIDField()

class AuditResponse(serializers.Serializer):
    job_id = serializers.UUIDField()
    state = serializers.CharField()
    scope = serializers.CharField()
    created = serializers.BooleanField()

class SiteSerializer(serializers.ModelSerializer):
    connection_status = serializers.SerializerMethodField()

    def get_connection_status(self, obj) -> str:
        return connection_status(obj)

    class Meta:
        model = Site
        fields = ['id', 'name', 'url', 'environment', 'timezone', 'paused', 'connection_status', 'created_at']
        read_only_fields = fields

class SiteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SiteSerializer

    def get_queryset(self):
        return visible_sites(self.request.user)

    @extend_schema(request=AuditRequest, responses={202: AuditResponse})
    @action(detail=True, methods=['post'], url_path='public-audit', serializer_class=AuditRequest)
    def public_audit(self, request, pk=None):
        site = self.get_object()
        if not can(request.user, site, 'run_audit'):
            raise PermissionDenied('Audit permission required.')
        serializer = AuditRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Explicitly reject body site IDs rather than silently accepting a second target.
        if set(request.data) - {'idempotency_key'}:
            raise ValidationError('Only idempotency_key is accepted. Target comes from the authorized URL.')
        job, created = create_public_audit(site, request.user, serializer.validated_data['idempotency_key'])
        return Response({'job_id': str(job.pk), 'state': job.state, 'scope': 'single_public_page_head_checks', 'created': created}, status=202)

def create_public_audit(site, user, key, service_credential=None):
    if not can(user, site, 'run_audit'):
        raise PermissionDenied('Audit permission required.')
    digest = hashlib.sha256(('public-head-v1:' + site.url).encode()).hexdigest()
    with transaction.atomic():
        site=Site.objects.select_for_update().get(pk=site.pk)
        if not can(user,site,'run_audit'): raise PermissionDenied('Audit permission required.')
        existing = Job.objects.filter(site=site, idempotency_key=key).first()
        if not existing and Job.objects.filter(site=site, state__in=['queued', 'running']).count() >= 3:
            raise ValidationError('This website already has three active audit jobs. Wait for completion or recover interrupted jobs.')
        job, created = Job.objects.get_or_create(site=site, idempotency_key=key,
            defaults={'actor': user, 'payload_hash': digest, 'target_url': site.url, 'service_credential':service_credential})
        if job.payload_hash != digest:
            raise ValidationError('Idempotency key already belongs to a different target revision.')
        if created:
            transaction.on_commit(lambda: enqueue(job.pk))
    return job, created

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ['id', 'site_id', 'state', 'error_code', 'created_at', 'finished_at']

class JobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = JobSerializer

    def get_queryset(self):
        return Job.objects.filter(site__in=visible_sites(self.request.user))
