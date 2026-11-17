<?php
define('WP_ENVIRONMENT_TYPE','staging');
set_error_handler(function($level,$message){return $level===E_WARNING && str_contains($message,'WP_ENVIRONMENT_TYPE already defined');});
require '/var/www/html/wp-load.php';
restore_error_handler();
require '/tmp/cseo-staging-guard.php';
$checks=0;
function guard_check($value,$label){global $checks;if(!$value){throw new RuntimeException($label);}$checks++;}
guard_check(wp_get_environment_type()==='staging','staging environment');
guard_check(wp_mail('synthetic@example.test','SYNTHETIC test','No email should leave.')===false,'mail blocked');
$http=wp_remote_get('https://example.test/');
guard_check(is_wp_error($http)&&$http->get_error_code()==='cseo_staging_outbound_disabled','actual WP HTTP preempted');
guard_check(apply_filters('woocommerce_available_payment_gateways',array('cod'=>true))===array(),'gateways blocked');
guard_check(apply_filters('woocommerce_is_purchasable',true)===false,'purchase disabled');
guard_check(apply_filters('woocommerce_webhook_should_deliver',true)===false,'webhook disabled');
guard_check(apply_filters('action_scheduler_allow_async_request_runner',true)===false,'async runner disabled');
guard_check(get_option('blog_public')===0,'nonpublic');
$robots=apply_filters('wp_robots',array());guard_check($robots['noindex']&&$robots['nofollow'],'robots');
$request=new WP_REST_Request('POST','/wc/store/v1/checkout');
$result=apply_filters('rest_pre_dispatch',null,rest_get_server(),$request);
guard_check(is_wp_error($result)&&$result->get_error_data()['status']===403,'store checkout blocked');
$request=new WP_REST_Request('GET','/company-seo/v1/capabilities');
guard_check(apply_filters('rest_pre_dispatch',null,rest_get_server(),$request)===null,'connector read unaffected');
echo $checks." actual WordPress staging guard checks passed. No message or HTTP request sent.\n";
