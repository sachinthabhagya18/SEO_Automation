<?php
$_SERVER['HTTP_HOST']='localhost:8081';require '/var/www/html/wp-load.php';
if (wp_get_environment_type()!=='local') { exit(2); }
CompanySEO\activate();
$checks=0;
function archive_must($ok,$message) { global $checks;if (!$ok) { fwrite(STDERR,"FAIL: $message\n");exit(1); }$checks++; }
function archive_request($path,$data=null,$method='POST') {
    $r=new WP_REST_Request($method,'/company-seo/v1/'.$path);
    if ($data!==null) { $r->set_header('Content-Type','application/json');$r->set_body(wp_json_encode($data)); }
    return rest_do_request($r);
}
$front=get_option('show_on_front');$enabled=get_option('cseo_writes_enabled');
$term=wp_insert_term('SYNTHETIC Archive Metadata','category');
if (is_wp_error($term)) { exit(3); }$id=(int)$term['term_id'];
$writer=get_user_by('login','synthetic-metadata-editor');
if (!$writer) { $uid=wp_insert_user(array('user_login'=>'synthetic-metadata-editor','user_pass'=>wp_generate_password(48),'role'=>'company_seo_metadata_editor'));$writer=get_user_by('id',$uid); }
try {
    update_option('show_on_front','posts');update_option('cseo_writes_enabled',true);
    foreach (array(array('home',0),array('category',$id)) as $target) {
        list($kind,$target_id)=$target;$prefix="contexts/$kind/$target_id/";
        wp_set_current_user(0);archive_must(archive_request($prefix.'seo',null,'GET')->get_status()!==200,'Anonymous context refused');
        wp_set_current_user($writer->ID);
        $base=archive_request($prefix.'seo',null,'GET')->get_data();
        archive_must(isset($base['revision']) && strlen($base['revision'])===64,'Typed target read');
        $payload=array('change_id'=>wp_generate_uuid4(),'post_id'=>$target_id,'expected_revision'=>$base['revision'],
            'changes'=>array('title'=>"SYNTHETIC Archive's Title",'description'=>'SYNTHETIC archive description.'),'approval_hash'=>str_repeat('a',64));
        $preview=archive_request($prefix.'changes/preview',$payload);
        archive_must($preview->get_status()===200 && $preview->get_data()['writes_performed']===false,'Preview does not write');
        archive_must(CompanySEO\archive_revision($kind,$target_id)===$base['revision'],'Preview preserves revision');
        $apply=archive_request($prefix.'changes/apply',$payload);
        archive_must($apply->get_status()===200 && $apply->get_data()['state']==='applied','Apply succeeds');
        archive_must(CompanySEO\archive_metadata($kind,$target_id)['title']===$payload['changes']['title'],'Typed storage exact');
        archive_must(archive_request($prefix.'changes/apply',$payload)->get_data()===$apply->get_data(),'Same-key replay');
        $wrong=$payload;$wrong['changes']['title']='Changed payload';
        archive_must(archive_request($prefix.'changes/apply',$wrong)->get_status()===409,'Different payload rejected');
        $GLOBALS['wp_query']=new WP_Query($kind==='home'?array('post_type'=>'post'):array('cat'=>$id));
        archive_must(CompanySEO\rendered_metadata()['title']===$payload['changes']['title'],'Frontend selects matching context');
        $parts=apply_filters('document_title_parts',array('title'=>'Before','page'=>'2'));
        archive_must($parts['title']===$payload['changes']['title'] && $parts['page']==='2','Archive title preserves pagination');
        $restore=archive_request($prefix.'changes/'.$payload['change_id'].'/restore',array());
        archive_must($restore->get_status()===200 && $restore->get_data()['state']==='restored','Restore succeeds');
        archive_must(CompanySEO\archive_revision($kind,$target_id)===$base['revision'],'Original revision restored');
        $payload['change_id']=wp_generate_uuid4();archive_request($prefix.'changes/apply',$payload);
        CompanySEO\archive_save_value($kind,$target_id,'description','Later independent edit');
        archive_must(archive_request($prefix.'changes/'.$payload['change_id'].'/restore',array())->get_status()===409,'Later edit blocks restore');
        foreach (array('title','description') as $field) { CompanySEO\archive_save_value($kind,$target_id,$field,$base['stored'][$field],$base['stored'][$field]!==''); }
    }
    archive_must(get_term($id)->name==='SYNTHETIC Archive Metadata','Visible category label unchanged');
    $core=new WP_REST_Request('POST','/wp/v2/categories/'.$id);$core->set_param('name','Unauthorized');
    archive_must(rest_do_request($core)->get_status()===403,'Metadata user cannot change category content');
    echo "$checks archive metadata checks passed.\n";
} finally { wp_delete_term($id,'category');update_option('show_on_front',$front);update_option('cseo_writes_enabled',$enabled); }
