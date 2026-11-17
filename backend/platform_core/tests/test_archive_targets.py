from unittest.mock import patch
import pytest
from platform_core.models import Page
from platform_core.changes import remote_metadata,immutable_payload,change_path
from platform_core.publish_tasks import checked_receipt
from platform_core.changes import ChangeFailure
from .test_authorization import portfolio
from .test_changes import review

@pytest.mark.parametrize('kind,remote_id',[('home',0),('category',42)])
def test_typed_targets_do_not_use_post_endpoint(review,kind,remote_id):
    p=review;page=p['page'];page.target_kind=kind;page.wordpress_id=remote_id;page.save()
    with patch('platform_core.changes.wordpress_get',return_value={**p['baseline'],'id':remote_id}) as http:
        remote_metadata(p['connection'],page)
        assert http.call_args.args[1]==f'contexts/{kind}/{remote_id}/seo'
    change=p['change'];change.page=page
    assert change_path(change,'apply')==f'contexts/{kind}/{remote_id}/changes/apply'
    assert immutable_payload(change)['target_kind']==kind

def test_receipt_from_wrong_target_kind_is_refused(review):
    change=review['change'];change.page.target_kind='category'
    with pytest.raises(ChangeFailure,match='remote_target_kind_mismatch'):
        checked_receipt(change,{'target_kind':'post'})
