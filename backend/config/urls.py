from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.routers import DefaultRouter
from platform_core import views
from platform_core import change_views
from platform_core import preview_views
from platform_core import research_views
from platform_core import keyword_views
from platform_core import google_setup
from platform_core import metadata_views
from platform_core import google_views
from platform_core.search_automation import SearchMetricsDispatch,SearchMetricsResult
from platform_core.research_automation import ResearchDispatchView,ResearchResultView
from platform_core.api import SiteViewSet, JobViewSet
from platform_core.automation import AuditDispatchView, DueDispatchView, AutomationJobView

router = DefaultRouter()
router.register('sites', SiteViewSet, basename='api-site')
router.register('jobs', JobViewSet, basename='api-job')
urlpatterns = [
    path('health/ready/', views.health),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth.LogoutView.as_view(), name='logout'),
    path('accounts/password-change/', auth.PasswordChangeView.as_view(template_name='registration/password_change.html', success_url='/'), name='password_change'),
    path('invitations/<str:token>/', views.accept_invitation, name='accept-invitation'),
    path('', views.overview, name='overview'),
    path('sites/new/', views.site_edit, name='site-create'),
    path('sites/discover/', research_views.discover, name='site-discover'),
    path('sites/archived/', views.archived_sites, name='archived-sites'),
    path('sites/<int:pk>/', views.site_detail, name='site-detail'),
    path('sites/<int:pk>/edit/', views.site_edit, name='site-edit'),
    path('sites/<int:pk>/connection/', views.site_connection, name='site-connection'),
    path('sites/<int:pk>/automation/', views.site_automation, name='site-automation'),
    path('sites/<int:pk>/changes/',change_views.draft_list,name='change-list'),
    path('sites/<int:pk>/preview/',preview_views.preview,name='metadata-preview'),
    path('sites/<int:pk>/pages/<int:page_id>/metadata/',metadata_views.snapshot,name='metadata-snapshot'),
    path('sites/<int:pk>/pages/<int:page_id>/metadata/refresh/',metadata_views.refresh,name='metadata-refresh'),
    path('sites/<int:pk>/research/',research_views.research,name='site-research'),
    path('sites/<int:pk>/keywords/',keyword_views.keyword_map,name='keyword-map'),
    path('sites/<int:pk>/google/',google_setup.setup,name='google-setup'),
    path('sites/<int:pk>/google/connection/',google_views.connection,name='google-connection'),
    path('integrations/google/callback/',google_views.callback,name='google-callback'),
    path('sites/<int:pk>/analytics/',google_views.analytics,name='site-analytics'),
    path('sites/<int:pk>/analytics/export/',google_views.export,name='search-metrics-export'),
    path('sites/<int:pk>/keywords/export/',keyword_views.keyword_export,name='keyword-export'),
    path('sites/<int:pk>/research/proposals/<uuid:proposal_id>/draft/',research_views.proposal_draft,name='proposal-draft'),
    path('sites/<int:pk>/research/proposals/<uuid:proposal_id>/test-copy/',research_views.proposal_test_copy,name='proposal-test-copy'),
    path('sites/<int:pk>/preview/image/',preview_views.preview_image,name='metadata-preview-image'),
    path('sites/<int:pk>/changes/new/',change_views.draft_edit,name='change-create'),
    path('sites/<int:pk>/changes/<uuid:change_id>/',change_views.draft_detail,name='change-detail'),
    path('sites/<int:pk>/changes/<uuid:change_id>/status/',change_views.draft_status,name='change-status'),
    path('sites/<int:pk>/changes/<uuid:change_id>/edit/',change_views.draft_edit,name='change-edit'),
    path('sites/<int:pk>/changes/<uuid:change_id>/action/',change_views.draft_action,name='change-action'),
    path('sites/<int:pk>/remove/', views.remove_site, name='site-remove'),
    path('sites/<int:pk>/restore/', views.restore_site, name='site-restore'),
    path('sites/<int:pk>/pause/', views.pause_site, name='site-pause'),
    path('sites/<int:pk>/public-audit/', views.start_public_audit, name='start-public-audit'),
    path('jobs/<uuid:job_id>/', views.job_detail, name='job-detail'),
    path('sites/<int:pk>/references/', views.references, name='site-references'),
    path('sites/<int:pk>/references/<int:reference_pk>/delete/', views.delete_reference, name='reference-delete'),
    path('staff/', views.staff, name='staff'),
    path('staff/assign/', views.assign_staff, name='staff-assign'),
    path('staff/assignments/<int:pk>/revoke/', views.revoke_assignment, name='staff-revoke'),
    path('api/v1/', include(router.urls)),
    path('api/v1/automation/audit-dispatch/', AuditDispatchView.as_view()),
    path('api/v1/automation/research-dispatch/',ResearchDispatchView.as_view()),
    path('api/v1/automation/research/<uuid:run_id>/',ResearchResultView.as_view()),
    path('api/v1/automation/search-dispatch/',SearchMetricsDispatch.as_view()),
    path('api/v1/automation/search/<uuid:run_id>/',SearchMetricsResult.as_view()),
    path('api/v1/automation/dispatch-due/', DueDispatchView.as_view()),
    path('api/v1/automation/jobs/<uuid:job_id>/', AutomationJobView.as_view()),
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
]
