<?php
$_SERVER['HTTP_HOST'] = 'localhost:8081';
require '/var/www/html/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
if (wp_get_environment_type() !== 'local') { exit(1); }
$checks = 0;
function check($condition, $message) {
    global $checks;
    if (!$condition) { fwrite(STDERR, 'FAIL: ' . $message . "\n"); exit(1); }
    $checks++;
}
$id = (int) get_option('cseo_fixture_page');
check($id > 0, 'Fixture page exists');
$role = get_role('company_seo_reader');
check($role && !isset($role->capabilities['install_plugins']) && !isset($role->capabilities['edit_users']) && !isset($role->capabilities['edit_posts']), 'Reader is least privilege');
$reader = get_user_by('login', 'synthetic-reader');
if (!$reader) {
    $reader_id = wp_insert_user(array('user_login' => 'synthetic-reader', 'user_pass' => wp_generate_password(40), 'role' => 'company_seo_reader'));
    $reader = get_user_by('id', $reader_id);
}
wp_set_current_user(0);
$request = new WP_REST_Request('GET', '/company-seo/v1/capabilities');
$result = rest_do_request($request);
check($result->get_status() === 403, 'Anonymous capabilities denied');
wp_set_current_user($reader->ID);
$result = rest_do_request($request);
check($result->get_status() === 200 && $result->get_data()['remote_write'] === false, 'Authenticated capability report');
$request = new WP_REST_Request('GET', '/company-seo/v1/pages/' . $id . '/seo');
$result = rest_do_request($request);
check($result->get_status() === 200 && strlen($result->get_data()['revision']) === 64, 'SEO values and revision');
$draft = wp_insert_post(array('post_type' => 'page', 'post_status' => 'draft', 'post_title' => 'SYNTHETIC PRIVATE'));
$request = new WP_REST_Request('GET', '/company-seo/v1/pages/' . $draft . '/seo');
check(rest_do_request($request)->get_status() === 404, 'Reader cannot inspect drafts');
wp_delete_post($draft, true);
$request = new WP_REST_Request('GET', '/company-seo/v1/pages');
$request->set_param('per_page', 101);
check(rest_do_request($request)->get_status() === 400, 'Inventory bounds enforced');
$request = new WP_REST_Request('POST', '/company-seo/v1/changes/apply');
check(rest_do_request($request)->get_status() === 403, 'Reader cannot use metadata write route');
update_option('cseo_mode', 'external');
check(!CompanySEO\rendering(), 'External SEO owner disables renderer');
update_option('cseo_mode', 'paused');
check(!CompanySEO\rendering(), 'Paused renderer disables output');
update_option('cseo_mode', 'standalone');
check(CompanySEO\rendering(), 'Standalone fixture rendering active');
$previous = get_post_meta($id, '_cseo_title', true);
deactivate_plugins('company-seo-connector/company-seo-connector.php');
check(get_post_meta($id, '_cseo_title', true) === $previous, 'Deactivation retains data');
activate_plugin('company-seo-connector/company-seo-connector.php');
define('WPSEO_VERSION', 'synthetic-conflict-fixture');
check(!CompanySEO\rendering() && in_array('Yoast', CompanySEO\conflicts(), true), 'Known SEO conflict suppresses output');
echo $checks . " WordPress plugin checks passed.\n";
