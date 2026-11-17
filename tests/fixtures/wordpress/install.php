<?php
// Intentionally only usable in the isolated local fixture container.
define('WP_INSTALLING', true);
$_SERVER['HTTP_HOST'] = 'localhost:8081';
require '/var/www/html/wp-load.php';
if (wp_get_environment_type() !== 'local' || !getenv('WP_FIXTURE_ADMIN_PASSWORD')) { exit(1); }
require_once ABSPATH . 'wp-admin/includes/upgrade.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
if (!is_blog_installed()) {
    wp_install('DEMO SYNTHETIC SEO Fixture', 'fixture-owner', 'fixture@example.test', false, '', getenv('WP_FIXTURE_ADMIN_PASSWORD'));
}
update_option('home', 'http://localhost:8081');
update_option('siteurl', 'http://localhost:8081');
update_option('blog_public', '0');
switch_theme('synthetic-seo');
$result = activate_plugin('company-seo-connector/company-seo-connector.php');
if (is_wp_error($result)) { fwrite(STDERR, $result->get_error_message()); exit(1); }
if (!get_option('cseo_fixture_page')) {
    $id = wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish', 'post_title' => 'SYNTHETIC Service Page', 'post_content' => '<p>Synthetic bicycle servicing in a fictional market. Not a real business.</p>'), true);
    if (is_wp_error($id)) { exit(1); }
    update_option('cseo_fixture_page', $id);
    update_post_meta($id, '_cseo_title', 'SYNTHETIC Service SEO Title');
    update_post_meta($id, '_cseo_description', 'Synthetic description for local SEO output verification.');
}
update_option('show_on_front', 'page');
update_option('page_on_front', (int) get_option('cseo_fixture_page'));
echo "Fixture installed; privacy remains noindex. No credentials printed.\n";
