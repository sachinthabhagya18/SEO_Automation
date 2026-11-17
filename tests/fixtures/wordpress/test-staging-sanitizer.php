<?php
$input=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);
define('DB_NAME','denimstage');define('DB_USER','denimstage');define('DB_PASSWORD',$input['password']);define('DB_HOST','wp-db');
define('DB_CHARSET','utf8mb4');define('DB_COLLATE','');define('WP_HOME','https://staging.denimyard.com');
define('WP_SITEURL',WP_HOME);define('WP_ENVIRONMENT_TYPE','staging');
$db=new mysqli(DB_HOST,DB_USER,DB_PASSWORD,DB_NAME);
function seed_sql($sql){global $db;if(!$db->query($sql)){throw new RuntimeException('synthetic seed failed');}}
seed_sql("INSERT INTO wp_posts (post_author,post_date,post_date_gmt,post_content,post_title,post_excerpt,post_status,comment_status,ping_status,post_name,post_modified,post_modified_gmt,post_type,to_ping,pinged,post_content_filtered) VALUES (1,NOW(),NOW(),'SYNTHETIC public content','SYNTHETIC KEEP PRODUCT','','publish','closed','closed','synthetic-keep-product',NOW(),NOW(),'product','','','')");
$product=$db->insert_id;
seed_sql("INSERT INTO wp_posts (post_author,post_date,post_date_gmt,post_content,post_title,post_excerpt,post_status,comment_status,ping_status,post_name,post_modified,post_modified_gmt,post_type,to_ping,pinged,post_content_filtered) VALUES (1,NOW(),NOW(),'SYNTHETIC order data','SYNTHETIC REMOVE ORDER','','wc-completed','closed','closed','synthetic-remove-order',NOW(),NOW(),'shop_order','','','')");
seed_sql("INSERT INTO wp_options (option_name,option_value,autoload) VALUES ('synthetic_plugin_api_secret','SYNTHETIC NOT REAL','no') ON DUPLICATE KEY UPDATE option_value=VALUES(option_value)");
seed_sql("CREATE TABLE wp_wc_orders (id BIGINT PRIMARY KEY,synthetic_private TEXT)");
seed_sql("INSERT INTO wp_wc_orders VALUES (1,'SYNTHETIC private order')");
seed_sql("CREATE TABLE wp_synthetic_private (id BIGINT PRIMARY KEY,synthetic_private TEXT)");
seed_sql("INSERT INTO wp_synthetic_private VALUES (1,'SYNTHETIC private plugin data')");
$db->close();
$shim=sys_get_temp_dir().'/cseo-sanitizer-'.bin2hex(random_bytes(8));mkdir($shim,0700);
file_put_contents($shim.'/wp-load.php',"<?php\ndefine('ABSPATH','/var/www/html/');\n\$table_prefix='wp_';\nrequire ABSPATH.'wp-settings.php';\n");
$argv[1]=$shim;
try {
    require '/tmp/staging-sanitize.php';
    global $wpdb;
    $checks=0;
    function sanitized_check($value,$label){global $checks;if(!$value){throw new RuntimeException($label);}$checks++;}
    sanitized_check((int)$wpdb->get_var("SELECT COUNT(*) FROM wp_posts WHERE ID=".(int)$product)===1,'product retained');
    sanitized_check((int)$wpdb->get_var("SELECT COUNT(*) FROM wp_posts WHERE post_type='shop_order'")===0,'legacy order removed');
    sanitized_check((int)$wpdb->get_var('SELECT COUNT(*) FROM wp_wc_orders')===0,'HPOS order emptied');
    sanitized_check((int)$wpdb->get_var('SELECT COUNT(*) FROM wp_users')===0,'source users removed');
    sanitized_check((int)$wpdb->get_var('SELECT COUNT(*) FROM wp_usermeta')===0,'source user secrets removed');
    sanitized_check((int)$wpdb->get_var('SELECT COUNT(*) FROM wp_comments')===0,'source comments removed');
    sanitized_check((int)$wpdb->get_var("SELECT COUNT(*) FROM wp_options WHERE option_name='synthetic_plugin_api_secret'")===0,'plugin secret removed');
    sanitized_check(!$wpdb->get_var("SHOW TABLES LIKE 'wp_synthetic_private'"),'unknown private table removed');
    sanitized_check($wpdb->get_var("SELECT option_value FROM wp_options WHERE option_name='home'")===WP_HOME,'home staging only');
    sanitized_check($wpdb->get_var("SELECT option_value FROM wp_options WHERE option_name='html_type'")==='text/html','HTML MIME retained');
    sanitized_check($wpdb->get_var("SELECT option_value FROM wp_options WHERE option_name='blog_charset'")==='UTF-8','HTML charset retained');
    echo $checks." actual MariaDB/WordPress sanitization checks passed on disposable denimstage DB.\n";
} finally {unlink($shim.'/wp-load.php');rmdir($shim);}
