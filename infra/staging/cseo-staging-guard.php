<?php
/** Must-use isolation. Install on the separate staging copy only. */
defined('ABSPATH') || exit;
if (wp_get_environment_type() !== 'staging') { return; }
add_filter('pre_wp_mail',function () { return false; },PHP_INT_MAX);
add_filter('pre_http_request',function () { return new WP_Error('cseo_staging_outbound_disabled','Outbound WordPress HTTP is disabled on this staging copy.'); },PHP_INT_MAX);
add_filter('pre_option_blog_public',function () { return 0; });
add_filter('wp_robots',function ($robots) { $robots['noindex']=true;$robots['nofollow']=true;$robots['noarchive']=true;return $robots; });
add_action('send_headers',function () { header('X-Robots-Tag: noindex, nofollow, noarchive',true); });
add_filter('woocommerce_available_payment_gateways',function () { return array(); },PHP_INT_MAX);
add_filter('woocommerce_is_purchasable',function () { return false; },PHP_INT_MAX);
add_filter('woocommerce_webhook_should_deliver',function () { return false; },PHP_INT_MAX);
add_filter('action_scheduler_allow_async_request_runner',function () { return false; },PHP_INT_MAX);
add_action('woocommerce_checkout_process',function () {
    if (function_exists('wc_add_notice')) { wc_add_notice('Checkout is disabled on this staging copy.','error'); }
});
add_filter('rest_pre_dispatch',function ($result,$server,$request) {
    if ($request->get_method()!=='GET' && preg_match('#^/wc/store/v[0-9]+/(checkout|cart)(/|$)#',$request->get_route())) {
        return new WP_Error('cseo_staging_checkout_disabled','Checkout is disabled on this staging copy.',array('status'=>403));
    }
    return $result;
},PHP_INT_MAX,3);
