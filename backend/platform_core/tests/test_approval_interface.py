from unittest.mock import patch
from platform_core.changes import submit,approve
from .test_authorization import portfolio
from .test_changes import review

def test_self_review_explanation_replaces_approval_button(review,client,settings):
    settings.SECURE_SSL_REDIRECT=False;p=review;c=p['change']
    c.last_edited_by=p['owner'];c.state='pending_review';c.save()
    client.force_login(p['owner'])
    response=client.get(f'/sites/{c.site_id}/changes/{c.pk}/')
    assert response.status_code==200
    assert b'Approval is blocked because you created or last edited' in response.content
    assert b'value="approve"' not in response.content and b'value="approve_test"' not in response.content
    assert b'_cseo_title' in response.content and b'Where these tags will be saved' in response.content

def test_progress_is_site_scoped_private_and_read_only(review,client,settings):
    settings.SECURE_SSL_REDIRECT=False;p=review;c=p['change'];client.force_login(p['staff'])
    with patch('platform_core.changes.wordpress_request') as remote:
        response=client.get(f'/sites/{c.site_id}/changes/{c.pk}/status/')
    assert response.status_code==200 and response.json()['state']=='draft' and not remote.called
    assert response.headers['Cache-Control']=='private, no-store'
    assert client.get(f"/sites/{p['b'].pk}/changes/{c.pk}/status/").status_code==404
