<?php
$root=$argv[1]??'/home/denimstage/public_html';
$secret_file=$argv[2]??'/root/seo-staging-denimyard/access.json';
require $root.'/wp-load.php';
if (DB_NAME!=='denimstage' || DB_USER!=='denimstage' || wp_get_environment_type()!=='staging' || home_url()!=='https://staging.denimyard.com') {
    fwrite(STDERR,"Staging identity guard refused account setup.\n");exit(2);
}
CompanySEO\activate();
if (get_user_by('login','seo-staging-admin') || file_exists($secret_file)) { fwrite(STDERR,"Staging accounts already exist; refusing reset.\n");exit(3); }
$admin_pass=wp_generate_password(40,true,true);
$admin=wp_insert_user(array('user_login'=>'seo-staging-admin','user_pass'=>$admin_pass,'user_email'=>'staging-admin@example.invalid','role'=>'administrator'));
if (is_wp_error($admin)) { fwrite(STDERR,"Staging admin creation failed.\n");exit(4); }
$result=array('url'=>home_url(),'admin_username'=>'seo-staging-admin','admin_password'=>$admin_pass,'connector_accounts'=>array());
foreach (array('reader'=>'company_seo_reader','editor'=>'company_seo_metadata_editor') as $label=>$role) {
    $username='seo-staging-'.$label;
    $user=wp_insert_user(array('user_login'=>$username,'user_pass'=>wp_generate_password(48,true,true),
        'user_email'=>'staging-'.$label.'@example.invalid','role'=>$role));
    if (is_wp_error($user)) { fwrite(STDERR,"Staging connector creation failed.\n");exit(5); }
    $application=WP_Application_Passwords::create_new_application_password($user,array('name'=>'Company SEO staging '.$label));
    if (is_wp_error($application)) { fwrite(STDERR,"Staging Application Password creation failed.\n");exit(6); }
    $result['connector_accounts'][$label]=array('username'=>$username,'application_password'=>str_replace(' ','',$application[0]));
}
if (file_put_contents($secret_file,json_encode($result,JSON_PRETTY_PRINT),LOCK_EX)===false) { exit(7); }
chmod($secret_file,0600);
update_option('cseo_writes_enabled',false);
echo "Fresh staging-only accounts created; credentials stored privately. Writes remain disabled.\n";
