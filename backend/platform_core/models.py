import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.db import models

ACTIONS = (
    'view_site', 'manage_site_profile', 'run_audit', 'manage_reference_sites',
    'run_keyword_research', 'edit_keyword_map', 'generate_ai_draft', 'edit_draft',
    'submit_for_review', 'approve_change', 'publish_change', 'rollback_change',
    'view_analytics', 'sync_search_metrics', 'export_report', 'manage_automation', 'manage_integrations',
    'manage_users', 'manage_budgets',
)

def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError('Enter an IANA timezone, for example Asia/Colombo.')

class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_service_account = models.BooleanField(default=False)

class Organization(models.Model):
    name = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Super Admin'
        STAFF = 'staff', 'Staff'
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization', 'user'], name='unique_membership')]

class RoleBundle(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    group = models.OneToOneField(Group, on_delete=models.CASCADE)
    label = models.CharField(max_length=80)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization', 'label'], name='unique_role_bundle')]

class Site(models.Model):
    class Environment(models.TextChoices):
        OWNED = 'owned', 'Owned'
        STAGING = 'staging', 'Staging'
        PRODUCTION = 'production', 'Production'
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    parent_site = models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='test_copies')
    name = models.CharField(max_length=160)
    url = models.URLField(max_length=2048)
    environment = models.CharField(max_length=12, choices=Environment.choices, default=Environment.STAGING)
    timezone = models.CharField(max_length=64, default='Asia/Colombo', validators=[validate_timezone])
    industry = models.CharField(max_length=200, blank=True)
    services = models.TextField(blank=True)
    audience = models.TextField(blank=True)
    countries = models.CharField(max_length=200, blank=True)
    languages = models.CharField(max_length=200, blank=True)
    brand_voice = models.TextField(blank=True)
    verified_facts = models.TextField(blank=True)
    prohibited_claims = models.TextField(blank=True)
    conversion_goals = models.TextField(blank=True)
    paused = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint(fields=['organization', 'url'], name='unique_site_url')]
        permissions = [(action, action.replace('_', ' ').capitalize()) for action in ACTIONS if action != 'view_site']

    def __str__(self):
        return self.name

class SiteAssignment(models.Model):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE)
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    bundle = models.ForeignKey(RoleBundle, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['membership', 'site'], name='unique_assignment')]

    def clean(self):
        if self.site.organization_id != self.membership.organization_id or self.bundle.organization_id != self.site.organization_id:
            raise ValidationError('Assignment, site and permission bundle must belong to the same organization.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class SitePermissionGrant(models.Model):
    assignment = models.ForeignKey(SiteAssignment, on_delete=models.CASCADE, related_name='grants')
    action = models.CharField(max_length=40, choices=[(a, a) for a in ACTIONS])

    class Meta:
        constraints = [models.UniqueConstraint(fields=['assignment', 'action'], name='unique_site_grant')]

class AuditEvent(models.Model):
    organization = models.ForeignKey(Organization, null=True, on_delete=models.SET_NULL)
    site = models.ForeignKey(Site, null=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    target = models.CharField(max_length=160, blank=True)
    request_id = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ReferenceSite(models.Model):
    class Relationship(models.TextChoices):
        OWN_SAMPLE = 'own_sample', 'Our own sample'
        COMPETITOR = 'competitor', 'Competitor'
        INSPIRATION = 'inspiration', 'Inspiration'
        RESEARCH = 'research', 'Research source'
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='references')
    url = models.URLField(max_length=2048)
    relationship = models.CharField(max_length=16, choices=Relationship.choices, default=Relationship.RESEARCH)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'id']
        constraints = [models.UniqueConstraint(fields=['site', 'url'], name='unique_reference_url')]

class Job(models.Model):
    class State(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        RUNNING = 'running', 'Running'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    service_credential = models.ForeignKey('ServiceCredential', null=True, blank=True, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    target_url = models.URLField(max_length=2048)
    state = models.CharField(max_length=16, choices=State.choices, default=State.QUEUED)
    lease_token = models.UUIDField(null=True)
    lease_expires_at = models.DateTimeField(null=True)
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['site', 'idempotency_key'], name='unique_site_job_request')]
        indexes = [models.Index(fields=['state', 'lease_expires_at'])]

class Page(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    url = models.URLField(max_length=2048)
    wordpress_id = models.PositiveBigIntegerField(null=True, blank=True)
    target_kind=models.CharField(max_length=16,default='post',choices=[('post','Page / product'),('home','Homepage'),('category','Category archive')])
    title = models.CharField(max_length=1000, blank=True)
    post_type = models.CharField(max_length=64, blank=True)
    publication_lease = models.UUIDField(null=True)
    publication_lease_until = models.DateTimeField(null=True)
    metadata_snapshot=models.JSONField(default=dict)
    metadata_snapshot_at=models.DateTimeField(null=True)
    metadata_snapshot_version=models.UUIDField(null=True)
    metadata_load_token=models.UUIDField(null=True)
    metadata_load_state=models.CharField(max_length=20,blank=True)
    metadata_load_error=models.CharField(max_length=80,blank=True)
    metadata_load_actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='+')
    metadata_load_version=models.UUIDField(null=True)
    metadata_load_requested_at=models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['site', 'url'], name='unique_page_url')]

    def __str__(self):
        return self.title or self.url

class PageSnapshot(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE)
    job = models.OneToOneField(Job, on_delete=models.CASCADE)
    status_code = models.PositiveSmallIntegerField()
    content_hash = models.CharField(max_length=64)
    title = models.CharField(max_length=1000, blank=True)
    description = models.CharField(max_length=1000, blank=True)
    evidence_excerpt = models.TextField(blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

class AuditIssue(models.Model):
    snapshot = models.ForeignKey(PageSnapshot, on_delete=models.CASCADE, related_name='issues')
    code = models.CharField(max_length=80)
    severity = models.CharField(max_length=16)
    evidence = models.TextField()
    remediation = models.TextField()
    rule_version = models.CharField(max_length=30)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['snapshot', 'code'], name='unique_snapshot_rule')]

class SiteConnection(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='connection')
    bound_url = models.URLField(max_length=2048, default='')
    encrypted_credentials = models.TextField()
    status = models.CharField(max_length=20, default='unverified', choices=[(v, v) for v in ['unverified', 'connected', 'error', 'revoked']])
    credential_version = models.UUIDField(default=uuid.uuid4)
    plugin_version = models.CharField(max_length=40, blank=True)
    wordpress_version = models.CharField(max_length=40, blank=True)
    renderer_mode = models.CharField(max_length=40, blank=True)
    capabilities = models.JSONField(default=dict)
    checked_at = models.DateTimeField(null=True)
    error_code = models.CharField(max_length=80, blank=True)

class KnowledgeSource(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='knowledge_sources')
    url = models.URLField(max_length=2048)
    title = models.CharField(max_length=1000, blank=True)
    excerpt = models.TextField()
    content_hash = models.CharField(max_length=64)
    fetched_at = models.DateTimeField(auto_now_add=True)
    source_type = models.CharField(max_length=30, default='public_observation')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-fetched_at']

class ServiceCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    token_digest = models.CharField(max_length=64, unique=True)
    scope = models.CharField(max_length=40, default='public_audit')
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class AuditSchedule(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='audit_schedule')
    enabled = models.BooleanField(default=False)
    interval_minutes = models.PositiveIntegerField(default=1440)
    next_due = models.DateTimeField(null=True)
    last_dispatched_at = models.DateTimeField(null=True)

class SitePolicy(models.Model):
    site = models.OneToOneField(Site,on_delete=models.CASCADE,related_name='policy')
    mode = models.CharField(max_length=24,default='approval_required',choices=[(s,s) for s in ['read_only','draft_only','approval_required']])
    version = models.UUIDField(default=uuid.uuid4)
    forbid_self_approval = models.BooleanField(default=True)
    allow_title = models.BooleanField(default=True)
    allow_description = models.BooleanField(default=True)

class ChangeSet(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    site = models.ForeignKey(Site,on_delete=models.CASCADE)
    page = models.ForeignKey(Page,on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    last_edited_by = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='last_edited_changes')
    sources = models.ManyToManyField(KnowledgeSource,blank=True)
    state = models.CharField(max_length=40,default='draft')
    change_title = models.BooleanField(default=False)
    change_description = models.BooleanField(default=True)
    proposed_title = models.CharField(max_length=200,blank=True)
    proposed_description = models.CharField(max_length=500,blank=True)
    base_metadata = models.JSONField(default=dict)
    base_revision = models.CharField(max_length=64)
    connection_version = models.UUIDField()
    context_hash = models.CharField(max_length=64)
    payload_hash = models.CharField(max_length=64)
    policy_version = models.UUIDField()
    provider = models.CharField(max_length=40,default='manual')
    reason = models.TextField(blank=True)
    error_code = models.CharField(max_length=80,blank=True)
    public_before = models.JSONField(default=dict)
    verification = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering=['-created_at']

class Approval(models.Model):
    change = models.ForeignKey(ChangeSet,on_delete=models.CASCADE,related_name='approvals')
    approver = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    payload_hash = models.CharField(max_length=64)
    base_revision = models.CharField(max_length=64)
    policy_version = models.UUIDField()
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class PublishAttempt(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    change = models.ForeignKey(ChangeSet,on_delete=models.PROTECT,related_name='attempts')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    operation = models.CharField(max_length=16,choices=[('apply','apply'),('restore','restore')])
    state = models.CharField(max_length=40,default='queued')
    receipt = models.JSONField(default=dict)
    error_code = models.CharField(max_length=80,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['change','operation'],name='unique_change_operation')]

class ResearchRun(models.Model):
    """Bounded URL research; observations never overwrite owner-approved facts."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='research_runs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    state = models.CharField(max_length=24, default='queued')
    stage = models.CharField(max_length=40, default='crawl')
    sources = models.ManyToManyField(KnowledgeSource, blank=True)
    report = models.JSONField(default=dict)
    use_ai = models.BooleanField(default=False)
    auto_drafts = models.BooleanField(default=False)
    ai_calls = models.PositiveSmallIntegerField(default=0)
    ai_reserved_at = models.DateTimeField(null=True)
    model = models.CharField(max_length=100, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    lease_token = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['site'], condition=models.Q(state__in=['queued','running']), name='one_active_research_per_site')]

class ResearchProposal(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    run=models.ForeignKey(ResearchRun,on_delete=models.CASCADE,related_name='proposals')
    page=models.ForeignKey(Page,on_delete=models.SET_NULL,null=True)
    url=models.URLField(max_length=2048)
    title=models.CharField(max_length=200)
    description=models.CharField(max_length=500)
    reason=models.TextField(blank=True)
    provider=models.CharField(max_length=40,default='deterministic-page-v1')
    sources=models.ManyToManyField(KnowledgeSource)
    change=models.OneToOneField(ChangeSet,on_delete=models.SET_NULL,null=True)
    draft_error_code=models.CharField(max_length=80,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['run','url'],name='unique_research_page_proposal')]

class KeywordCandidate(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    site=models.ForeignKey(Site,on_delete=models.CASCADE,related_name='keyword_candidates')
    source=models.ForeignKey(KnowledgeSource,on_delete=models.PROTECT)
    phrase=models.CharField(max_length=200)
    phrase_key=models.CharField(max_length=64)
    observed_url=models.URLField(max_length=2048)
    target_page=models.ForeignKey(Page,on_delete=models.SET_NULL,null=True,blank=True)
    intent=models.CharField(max_length=24,default='unknown',choices=[(v,v) for v in ['unknown','informational','commercial','transactional','navigational']])
    locked=models.BooleanField(default=False)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    reviewed_at=models.DateTimeField(null=True)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=['phrase','id']
        constraints=[models.UniqueConstraint(fields=['site','phrase_key','observed_url'],name='unique_observed_keyword')]

class SearchConsoleSetup(models.Model):
    site=models.OneToOneField(Site,on_delete=models.CASCADE,related_name='search_console_setup')
    domain=models.CharField(max_length=253)
    txt_value=models.CharField(max_length=230)
    dns_observed=models.BooleanField(default=False)
    checked_at=models.DateTimeField(null=True)
    error_code=models.CharField(max_length=60,blank=True)

class GoogleConnection(models.Model):
    site=models.OneToOneField(Site,on_delete=models.CASCADE,related_name='google_connection')
    actor=models.ForeignKey(User,on_delete=models.PROTECT,null=True)
    bound_url=models.URLField(max_length=2048)
    client_id=models.CharField(max_length=250,blank=True)
    credential_version=models.UUIDField(default=uuid.uuid4)
    encrypted_tokens=models.TextField(blank=True)
    status=models.CharField(max_length=24,default='disconnected')
    property_url=models.CharField(max_length=2048,blank=True)
    permission_level=models.CharField(max_length=40,blank=True)
    properties=models.JSONField(default=list)
    checked_at=models.DateTimeField(null=True)
    error_code=models.CharField(max_length=80,blank=True)

class GoogleOAuthIntent(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    site=models.ForeignKey(Site,on_delete=models.CASCADE)
    actor=models.ForeignKey(User,on_delete=models.CASCADE)
    bound_url=models.URLField(max_length=2048)
    client_id=models.CharField(max_length=250)
    connection_version=models.UUIDField()
    state_digest=models.CharField(max_length=64,unique=True)
    encrypted_verifier=models.TextField()
    expires_at=models.DateTimeField()
    used_at=models.DateTimeField(null=True)

class SearchMetricsRun(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    site=models.ForeignKey(Site,on_delete=models.CASCADE,related_name='search_metrics_runs')
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    event_key=models.UUIDField(default=uuid.uuid4)
    connection_version=models.UUIDField()
    bound_url=models.URLField(max_length=2048)
    property_url=models.CharField(max_length=2048)
    start_date=models.DateField()
    end_date=models.DateField()
    state=models.CharField(max_length=24,default='queued')
    error_code=models.CharField(max_length=80,blank=True)
    report=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    started_at=models.DateTimeField(null=True)
    finished_at=models.DateTimeField(null=True)
    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['site','event_key'],name='unique_search_sync_event'),
            models.UniqueConstraint(fields=['site'],condition=models.Q(state__in=['queued','running']),name='one_active_search_sync')]

class SearchMetric(models.Model):
    run=models.ForeignKey(SearchMetricsRun,on_delete=models.CASCADE,related_name='metrics')
    row_key=models.CharField(max_length=64)
    row_kind=models.CharField(max_length=12)
    date=models.DateField()
    page=models.URLField(max_length=2048,blank=True)
    query=models.CharField(max_length=1000,blank=True)
    country=models.CharField(max_length=3,blank=True)
    device=models.CharField(max_length=20,blank=True)
    clicks=models.PositiveBigIntegerField()
    impressions=models.PositiveBigIntegerField()
    ctr=models.FloatField()
    position=models.FloatField()
    class Meta:
        constraints=[models.UniqueConstraint(fields=['run','row_key'],name='unique_search_metric_row')]
