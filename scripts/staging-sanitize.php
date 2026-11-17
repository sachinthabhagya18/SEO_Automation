<?php
/** Invoked on the NEW database only, before normal staging bootstrap. */
$root=$argv[1]??'/home/denimstage/public_html';
define('SHORTINIT',true);
require $root.'/wp-load.php';
global $wpdb;
if (DB_NAME!=='denimstage' || DB_USER!=='denimstage' || !defined('WP_HOME') || WP_HOME!=='https://staging.denimyard.com'
    || wp_get_environment_type()!=='staging' || !preg_match('/^[a-zA-Z0-9_]+$/',$wpdb->prefix)) {
    fwrite(STDERR,"Staging identity guard refused sanitization.\n");exit(2);
}
$prefix=$wpdb->prefix;
$core=array('options','posts','postmeta','terms','term_taxonomy','term_relationships','termmeta','users','usermeta','comments','commentmeta','links');
$public=array('wc_product_meta_lookup','wc_product_attributes_lookup','woocommerce_attribute_taxonomies','woocommerce_termmeta',
    'woocommerce_tax_rates','woocommerce_tax_rate_locations','woocommerce_shipping_zones','woocommerce_shipping_zone_locations',
    'woocommerce_shipping_zone_methods','wc_category_lookup');
$empty=array('wc_orders','wc_orders_meta','wc_order_addresses','wc_order_operational_data','wc_order_stats','wc_order_product_lookup',
    'wc_order_tax_lookup','wc_order_coupon_lookup','wc_customer_lookup','wc_download_log','woocommerce_downloadable_product_permissions',
    'woocommerce_order_items','woocommerce_order_itemmeta','woocommerce_payment_tokens','woocommerce_payment_tokenmeta',
    'woocommerce_sessions','wc_webhooks','woocommerce_api_keys','actionscheduler_actions','actionscheduler_claims','actionscheduler_groups',
    'actionscheduler_logs','woocommerce_log','wc_logs');
$tables=$wpdb->get_col('SHOW TABLES');
foreach ($tables as $table) {
    if (!preg_match('/^[a-zA-Z0-9_]+$/',$table) || strpos($table,$prefix)!==0) { fwrite(STDERR,"Unexpected table; refusing.\n");exit(3); }
}
function staging_sql($query) {
    global $wpdb;
    if ($wpdb->query($query)===false) { fwrite(STDERR,"Staging sanitization query failed; details suppressed.\n");exit(4); }
}
foreach ($tables as $table) {
    $suffix=substr($table,strlen($prefix));
    if (in_array($suffix,array_merge($core,$public),true)) { continue; }
    if (in_array($suffix,$empty,true)) { staging_sql("TRUNCATE TABLE `$table`"); }
    else { staging_sql("DROP TABLE `$table`"); }
}
staging_sql("DELETE FROM `{$prefix}posts` WHERE post_type IN ('shop_order','shop_order_refund','shop_order_placehold','shop_coupon','shop_webhook','revision','scheduled-action') OR post_status NOT IN ('publish','inherit')");
staging_sql("DELETE m FROM `{$prefix}postmeta` m LEFT JOIN `{$prefix}posts` p ON p.ID=m.post_id WHERE p.ID IS NULL");
staging_sql("DELETE r FROM `{$prefix}term_relationships` r LEFT JOIN `{$prefix}posts` p ON p.ID=r.object_id WHERE p.ID IS NULL");
foreach (array('users','usermeta','comments','commentmeta','links') as $suffix) { staging_sql("TRUNCATE TABLE `{$prefix}{$suffix}`"); }
staging_sql("UPDATE `{$prefix}posts` SET post_author=1,comment_count=0");
$options=array('siteurl','home','blogname','blogdescription','blog_public','blog_charset','html_type','template','stylesheet','current_theme','active_plugins',
    'db_version','initial_db_version','permalink_structure','show_on_front','page_on_front','page_for_posts','timezone_string','gmt_offset',
    'date_format','time_format','start_of_week','WPLANG','sidebars_widgets','nav_menu_options',$prefix.'user_roles',
    'woocommerce_version','woocommerce_db_version','woocommerce_currency','woocommerce_default_country','woocommerce_permalinks',
    'woocommerce_shop_page_id','woocommerce_cart_page_id','woocommerce_checkout_page_id','woocommerce_myaccount_page_id','woocommerce_terms_page_id',
    'woocommerce_weight_unit','woocommerce_dimension_unit','woocommerce_tax_display_shop');
$placeholders=implode(',',array_fill(0,count($options),'%s'));
staging_sql($wpdb->prepare("DELETE FROM `{$prefix}options` WHERE option_name NOT IN ($placeholders) AND option_name NOT LIKE 'theme_mods_%%' AND option_name NOT LIKE 'widget_%%'",$options));
$values=array('siteurl'=>WP_HOME,'home'=>WP_HOME,'blog_public'=>'0','blog_charset'=>'UTF-8','html_type'=>'text/html','admin_email'=>'staging-admin@example.invalid',
    'active_plugins'=>serialize(array('woocommerce/woocommerce.php','shortcoder/shortcoder.php','company-seo-connector/company-seo-connector.php')),
    'cron'=>serialize(array()),'woocommerce_enable_guest_checkout'=>'no','woocommerce_enable_myaccount_registration'=>'no');
foreach ($values as $name=>$value) {
    staging_sql($wpdb->prepare("INSERT INTO `{$prefix}options` (option_name,option_value,autoload) VALUES (%s,%s,'yes') ON DUPLICATE KEY UPDATE option_value=VALUES(option_value)",$name,$value));
}
echo "Staging-only sanitization complete; public content retained.\n";
