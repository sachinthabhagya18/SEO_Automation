<?php
$_SERVER['HTTP_HOST']='localhost:8081';
require '/var/www/html/wp-load.php';
if (wp_get_environment_type()!=='local') { exit(1); }
CompanySEO\activate();
$writer=get_user_by('login','synthetic-metadata-editor');
if (!$writer) {
    $id=wp_insert_user(array('user_login'=>'synthetic-metadata-editor','user_pass'=>wp_generate_password(48),'role'=>'company_seo_metadata_editor'));
    $writer=get_user_by('id',$id);
}
if (isset($argv[1]) && $argv[1]==='cleanup') {
    WP_Application_Passwords::delete_application_password($writer->ID,$argv[2]);
    update_option('cseo_writes_enabled',false);
    echo "Temporary fixture writer password revoked; remote writes disabled.\n";exit;
}
update_option('cseo_mode','standalone');update_option('cseo_writes_enabled',true);
$result=WP_Application_Passwords::create_new_application_password($writer->ID,array('name'=>'Temporary local metadata publication test'));
if (is_wp_error($result)) { exit(1); }
echo wp_json_encode(array('username'=>$writer->user_login,'password'=>$result[0],'uuid'=>$result[1]['uuid'],'post_id'=>(int)get_option('cseo_fixture_page')));
