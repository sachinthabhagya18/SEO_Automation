from django.contrib.auth.decorators import login_required
from django.http import Http404,JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from .models import Page,SiteConnection
from .permissions import visible_sites
from .metadata_cache import allowed,queue_read

@login_required
def snapshot(request,pk,page_id):
    page=get_object_or_404(Page.objects.select_related('site'),pk=page_id,site_id=pk,site__in=visible_sites(request.user))
    if not allowed(request.user,page.site): raise Http404
    connection=SiteConnection.objects.filter(site=page.site,status='connected').first()
    ready=bool(connection and connection.bound_url.rstrip('/')==page.site.url.rstrip('/') and page.metadata_snapshot_version==connection.credential_version and page.metadata_snapshot_at)
    ready=ready and page.metadata_snapshot.get('id')==page.wordpress_id and page.metadata_snapshot.get('target_kind','post')==page.target_kind
    response=JsonResponse({'ready':ready,'page_title':page.title,'url':page.url,
        'stored':page.metadata_snapshot.get('stored',{}) if ready else {},
        'read_at':page.metadata_snapshot_at.isoformat() if ready else None,
        'state':page.metadata_load_state,'error_code':page.metadata_load_error})
    response['Cache-Control']='private, no-store'
    return response

@login_required
@require_POST
def refresh(request,pk,page_id):
    page=get_object_or_404(Page.objects.select_related('site'),pk=page_id,site_id=pk,site__in=visible_sites(request.user))
    if not allowed(request.user,page.site): raise Http404
    try: token=queue_read(page,request.user)
    except ValueError:
        return JsonResponse({'queued':False,'error_code':'verified_inventory_connection_required'},status=409)
    return JsonResponse({'queued':True,'request_id':str(token)},status=202)
