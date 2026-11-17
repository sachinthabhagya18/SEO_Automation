<?php
$_SERVER['HTTP_HOST'] = 'localhost:8081';
require '/var/www/html/wp-load.php';
if (wp_get_environment_type() !== 'local') { exit(1); }
$reader = get_user_by('login', 'synthetic-reader');
if (!$reader) { exit(1); }
if (isset($argv[1]) && $argv[1] === 'cleanup') {
    WP_Application_Passwords::delete_application_password($reader->ID, $argv[2]);
    echo "Fixture Application Password revoked.\n";
    exit;
}
$result = WP_Application_Passwords::create_new_application_password($reader->ID, array('name' => 'Temporary connector HTTP smoke'));
if (is_wp_error($result)) { exit(1); }
echo wp_json_encode(array('username' => $reader->user_login, 'password' => $result[0], 'uuid' => $result[1]['uuid']));
