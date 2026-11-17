<?php
$_SERVER['HTTP_HOST']='localhost:8081';
require '/var/www/html/wp-load.php';
if (wp_get_environment_type()!=='local') { exit(1); }
CompanySEO\activate();
$checks=0;
function must($condition,$message) { global $checks;if (!$condition) { fwrite(STDERR,'FAIL: '.$message."\n");exit(1); }$checks++; }
function request_json($route,$payload=array(),$method='POST') {
    $r=new WP_REST_Request($method,'/company-seo/v1/'.$route);
    if ($method==='POST') { $r->set_header('Content-Type','application/json');$r->set_body(wp_json_encode($payload)); }
    return rest_do_request($r);
}
$id=(int)get_option('cseo_fixture_page');
$original=CompanySEO\metadata($id);$original_revision=CompanySEO\revision(get_post($id));
$original_content=get_post_field('post_content',$id);$original_visible_title=get_post_field('post_title',$id);
$writer=get_user_by('login','synthetic-metadata-editor');
if (!$writer) { $uid=wp_insert_user(array('user_login'=>'synthetic-metadata-editor','user_pass'=>wp_generate_password(48),'role'=>'company_seo_metadata_editor'));$writer=get_user_by('id',$uid); }
$payload=array('change_id'=>wp_generate_uuid4(),'post_id'=>$id,'expected_revision'=>$original_revision,
    'changes'=>array('title'=>"SYNTHETIC Editor's & Local Title",'description'=>'Synthetic reviewed metadata description.'),'approval_hash'=>str_repeat('a',64));
wp_set_current_user(0);
must(request_json('changes/apply',$payload)->get_status()===403,'Anonymous apply denied');
wp_set_current_user($writer->ID);update_option('cseo_writes_enabled',false);
must(request_json('changes/apply',$payload)->get_status()===403,'Emergency writes-off enforced');
update_option('cseo_writes_enabled',true);update_option('cseo_mode','standalone');
$reader=get_user_by('login','synthetic-reader');wp_set_current_user($reader->ID);
must(request_json('changes/apply',$payload)->get_status()===403,'Reader cannot apply metadata');
wp_set_current_user($writer->ID);
$core=new WP_REST_Request('POST','/wp/v2/pages/'.$id);$core->set_param('content','UNAUTHORIZED BODY CHANGE');
must(rest_do_request($core)->get_status()===403,'Metadata account cannot mutate core content routes');
$bad=$payload;$bad['changes']['canonical']='https://example.test';
must(request_json('changes/apply',$bad)->get_status()===400,'Unknown/high-risk fields rejected');
$preview=request_json('changes/preview',$payload);
must($preview->get_status()===200 && $preview->get_data()['writes_performed']===false,'Preview performs no writes');
must(CompanySEO\revision(CompanySEO\fresh_post($id))===$original_revision,'Preview preserves revision');
$first=request_json('changes/apply',$payload);
must($first->get_status()===200 && $first->get_data()['state']==='applied','Metadata applies transactionally');
$applied=$first->get_data();
must(CompanySEO\metadata($id)['title']===$payload['changes']['title'],'Quotes and ampersand preserved');
must(get_post_field('post_content',$id)===$original_content && get_post_field('post_title',$id)===$original_visible_title,'Visible body and post title unchanged');
$repeat=request_json('changes/apply',$payload);
must($repeat->get_status()===200 && $repeat->get_data()['after_revision']===$applied['after_revision'],'Same-key replay returns prior receipt');
$changed=$payload;$changed['changes']['description']='Different payload';
must(request_json('changes/apply',$changed)->get_status()===409,'Same key/different payload rejected');
$stale=$payload;$stale['change_id']=wp_generate_uuid4();
must(request_json('changes/apply',$stale)->get_status()===409,'New key/stale revision rejected');
must(request_json('changes/'.$payload['change_id'],array(),'GET')->get_status()===200,'Status recovery available');
$writer->add_cap('company_seo_restore',false);wp_set_current_user(0);wp_set_current_user($writer->ID);
must(request_json('changes/'.$payload['change_id'].'/restore')->get_status()===403,'Metadata-write capability does not bypass separate restore capability');
$writer->remove_cap('company_seo_restore');wp_set_current_user(0);wp_set_current_user($writer->ID);
update_post_meta($id,'_cseo_description','SYNTHETIC later editor change');
must(request_json('changes/'.$payload['change_id'].'/restore')->get_status()===409,'Restore refuses to overwrite later edits');
update_post_meta($id,'_cseo_description',wp_slash($payload['changes']['description']));
$restored=request_json('changes/'.$payload['change_id'].'/restore');
must($restored->get_status()===200 && $restored->get_data()['state']==='restored','Conflict-free restore succeeds');
must(CompanySEO\revision(CompanySEO\fresh_post($id))===$original_revision && CompanySEO\metadata($id)===$original,'Original metadata restored');
must(request_json('changes/'.$payload['change_id'].'/restore')->get_status()===200,'Restore replay is idempotent');
$description_existed=metadata_exists('post',$id,'_cseo_description');
delete_post_meta($id,'_cseo_description');
$missing_revision=CompanySEO\revision(CompanySEO\fresh_post($id));
$missing_payload=array('change_id'=>wp_generate_uuid4(),'post_id'=>$id,'expected_revision'=>$missing_revision,
    'changes'=>array('description'=>'SYNTHETIC missing-field restore test.'),'approval_hash'=>str_repeat('c',64));
must(request_json('changes/apply',$missing_payload)->get_status()===200,'Previously missing metadata can be applied');
must(request_json('changes/'.$missing_payload['change_id'].'/restore')->get_status()===200,'Missing-field restore succeeds');
must(!metadata_exists('post',$id,'_cseo_description'),'Restore preserves original missing-key existence');
if ($description_existed) { update_post_meta($id,'_cseo_description',wp_slash($original['description'])); }
$record_type=get_post_type_object('cseo_record');
must($record_type && !$record_type->public && !$record_type->show_in_rest && !$record_type->publicly_queryable,'SEO record CPT is private and excluded from public REST');
$records=get_posts(array('post_type'=>'cseo_record','post_status'=>'private','meta_key'=>'_cseo_change_id','meta_value'=>$payload['change_id'],'fields'=>'ids'));
must(count($records)===1 && get_post_meta($records[0],'_cseo_state',true)==='restored','One private CPT record mirrors restored metadata receipt');
must(!current_user_can('edit_post',$records[0]),'Connector writer cannot edit private history records');
update_option('cseo_writes_enabled',false);
echo $checks." WordPress metadata change checks passed.\n";
