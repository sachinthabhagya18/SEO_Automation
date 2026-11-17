<?php
/**
 * Plugin Name: Company SEO Connector
 * Description: Local SEO metadata and a capability-scoped connector. Metadata writes require explicit staging/local enablement.
 * Version: 0.3.0
 * Requires at least: 6.8
 * Requires PHP: 8.2
 * License: GPL-2.0-or-later
 */
namespace CompanySEO;
defined('ABSPATH') || exit;

const VERSION = '0.3.0';
const PREFIX = '_cseo_';

function activate() {
    add_role('company_seo_reader', 'Company SEO Reader', array('read' => true, 'company_seo_read' => true));
    $admin = get_role('administrator');
    if ($admin) { $admin->add_cap('company_seo_read'); }
    add_role('company_seo_metadata_editor', 'Company SEO Metadata Editor', array('read'=>true,
        'company_seo_read'=>true, 'company_seo_meta_write'=>true, 'company_seo_restore'=>true,
        'edit_posts'=>true, 'edit_pages'=>true, 'edit_published_posts'=>true, 'edit_published_pages'=>true,
        'edit_others_posts'=>true, 'edit_others_pages'=>true,
        'edit_products'=>true,'edit_published_products'=>true,'edit_others_products'=>true));
    add_option('cseo_mode', 'standalone');
    add_option('cseo_schema_version', 1);
    add_option('cseo_writes_enabled', false);
    install_ledger();
    install_archive_ledger();
    $editor=get_role('company_seo_metadata_editor');
    if ($editor) { foreach (array('edit_products','edit_published_products','edit_others_products','edit_product_terms','manage_categories') as $cap) { $editor->add_cap($cap); } }
}
register_activation_hook(__FILE__, __NAMESPACE__ . '\\activate');
require_once __DIR__ . '/metadata-changes.php';
require_once __DIR__ . '/metadata-records.php';
require_once __DIR__ . '/archive-metadata.php';
add_action('admin_init', function () {
    if (current_user_can('manage_options') && get_option('cseo_ledger_version') !== '1') { install_ledger(); }
    if (current_user_can('manage_options') && get_option('cseo_archive_ledger_version') !== '1') { install_archive_ledger(); }
});
// Deactivation and uninstall deliberately retain metadata and options.

function conflicts() {
    $found = array();
    if (defined('WPSEO_VERSION')) { $found[] = 'Yoast'; }
    if (defined('RANK_MATH_VERSION')) { $found[] = 'Rank Math'; }
    if (defined('AIOSEO_VERSION') || class_exists('All_in_One_SEO_Pack')) { $found[] = 'All in One SEO'; }
    if (defined('SEOPRESS_VERSION')) { $found[] = 'SEOPress'; }
    return $found;
}

function rendering() {
    return get_option('cseo_mode', 'standalone') === 'standalone' && !conflicts();
}

function fields() {
    return array('title' => 200, 'description' => 500, 'og_title' => 200, 'og_description' => 500);
}

add_action('init', function () {
    foreach (get_post_types(array('public' => true)) as $type) {
        foreach (fields() as $field => $max) {
            register_post_meta($type, PREFIX . $field, array(
                'type' => 'string', 'single' => true, 'show_in_rest' => false,
                'sanitize_callback' => function ($value) use ($max) { return mb_substr(sanitize_text_field($value), 0, $max); },
                'auth_callback' => function ($allowed, $meta_key, $post_id) { return current_user_can('edit_post', $post_id); },
            ));
        }
    }
});

function metadata($id) {
    $values = array();
    foreach (fields() as $field => $max) { $values[$field] = (string) get_post_meta($id, PREFIX . $field, true); }
    return $values;
}

function revision($post) {
    return hash('sha256', wp_json_encode(array('post_modified_gmt' => $post->post_modified_gmt,
        'content' => $post->post_content, 'post_title' => $post->post_title, 'seo' => metadata($post->ID))));
}

add_filter('document_title_parts', function ($parts) {
    if (rendering() && public_context()) {
        $title = rendered_metadata()['title'];
        if ($title !== '') { $parts = array_merge(array('title'=>$title),isset($parts['page'])?array('page'=>$parts['page']):array()); }
    }
    return $parts;
});

function public_context() {
    return !is_404() && !is_search() && !is_feed() && !is_embed() && !is_preview() && !is_attachment()
        && !(is_singular() && post_password_required());
}

function context_canonical() {
    if (!public_context()) { return ''; }
    if (is_singular()) { return wp_get_canonical_url(); }
    // get_pagenum_link retains archive pagination instead of canonicalizing to page one.
    if (is_home() || is_front_page() || is_archive()) { return get_pagenum_link(max(1, (int) get_query_var('paged'))); }
    return '';
}

add_action('wp', function () {
    if (rendering() && public_context()) { remove_action('wp_head', 'rel_canonical'); }
});

add_filter('wp_robots', function ($robots) {
    if (rendering() && (is_search() || is_404() || is_attachment() || is_author() || is_date())) {
        unset($robots['index']);
        $robots['noindex'] = true;
    }
    // Preserve core blog_public privacy; never force index/follow.
    return $robots;
});

function meta_tag($attribute, $name, $value) {
    if ($value !== '') { echo '<meta ' . esc_attr($attribute) . '="' . esc_attr($name) . '" content="' . esc_attr($value) . '" />' . "\n"; }
}

add_action('wp_head', function () {
    if (!rendering() || !public_context()) { return; }
    $canonical = context_canonical();
    if ($canonical) { echo '<link rel="canonical" href="' . esc_url($canonical) . '" />' . "\n"; }
    $seo = rendered_metadata();
    meta_tag('name', 'description', $seo['description']);
    meta_tag('property', 'og:title', $seo['og_title'] ?: wp_get_document_title());
    meta_tag('property', 'og:description', $seo['og_description'] ?: $seo['description']);
    meta_tag('property', 'og:type', is_singular('post') ? 'article' : 'website');
    meta_tag('property', 'og:url', $canonical ?: '');
    meta_tag('name', 'twitter:card', 'summary');
    meta_tag('name', 'twitter:title', $seo['og_title'] ?: wp_get_document_title());
    meta_tag('name', 'twitter:description', $seo['og_description'] ?: $seo['description']);
}, 5);

add_action('add_meta_boxes', function () {
    foreach (get_post_types(array('public' => true)) as $type) {
        add_meta_box('cseo_metadata', 'Company SEO metadata', function ($post) {
            wp_nonce_field('cseo_save', 'cseo_nonce');
            echo '<p>Saved locally. SEO title does not change the visible page heading. Renderer ownership and theme compatibility must be verified.</p>';
            foreach (fields() as $field => $max) {
                echo '<p><label for="cseo_' . esc_attr($field) . '">' . esc_html(ucwords(str_replace('_', ' ', $field))) . '</label><br />';
                echo '<input class="widefat" id="cseo_' . esc_attr($field) . '" name="cseo_' . esc_attr($field) . '" maxlength="' . esc_attr($max) . '" value="' . esc_attr(get_post_meta($post->ID, PREFIX . $field, true)) . '" /></p>';
            }
        }, $type, 'normal');
    }
});

add_action('save_post', function ($id) {
    if (!isset($_POST['cseo_nonce']) || !wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['cseo_nonce'])), 'cseo_save')
        || (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) || wp_is_post_revision($id) || !current_user_can('edit_post', $id)) { return; }
    foreach (fields() as $field => $max) {
        if (isset($_POST['cseo_' . $field]) && is_string($_POST['cseo_' . $field])) {
            update_post_meta($id, PREFIX . $field, mb_substr(sanitize_text_field(wp_unslash($_POST['cseo_' . $field])), 0, $max));
        }
    }
});

add_action('admin_menu', function () {
    add_options_page('Company SEO', 'Company SEO', 'manage_options', 'company-seo', function () {
        if (!current_user_can('manage_options')) { return; }
        if (isset($_POST['cseo_mode'])) {
            check_admin_referer('cseo_settings');
            $mode = sanitize_key(wp_unslash($_POST['cseo_mode']));
            if (in_array($mode, array('standalone', 'external', 'paused'), true)) { update_option('cseo_mode', $mode); }
            update_option('cseo_writes_enabled', isset($_POST['cseo_writes_enabled']) && in_array(wp_get_environment_type(), array('local','staging'), true));
        }
        echo '<div class="wrap"><h1>Company SEO ownership</h1><p>Conflict detection cannot detect every hard-coded theme tag. Verify rendered HTML. Only title/description writes are supported, disabled by default and restricted to local/staging WordPress environments.</p>';
        if (conflicts()) { echo '<div class="notice notice-error"><p>Other SEO output detected: ' . esc_html(implode(', ', conflicts())) . '. Company rendering is suppressed.</p></div>'; }
        echo '<form method="post">';
        wp_nonce_field('cseo_settings');
        echo '<label for="cseo-mode">Renderer mode</label> <select id="cseo-mode" name="cseo_mode">';
        foreach (array('standalone' => 'Standalone renderer', 'external' => 'External SEO owner / connector only', 'paused' => 'Paused / read-only') as $value => $label) {
            echo '<option value="' . esc_attr($value) . '" ' . selected(get_option('cseo_mode', 'standalone'), $value, false) . '>' . esc_html($label) . '</option>';
        }
        echo '</select><p><label><input type="checkbox" name="cseo_writes_enabled" value="1" ' . checked((bool)get_option('cseo_writes_enabled',false),true,false) . ' /> Enable title/description connector writes (local/staging only)</label></p>';
        submit_button('Save ownership');
        echo '</form><p>Deactivating this plugin removes its rendered tags, but retains all saved metadata. Frontend rendering never calls Django or an AI service.</p></div>';
    });
});

function read_permission() {
    $local = wp_get_environment_type() === 'local' && defined('CSEO_ALLOW_INSECURE_LOCAL') && CSEO_ALLOW_INSECURE_LOCAL;
    if (!is_ssl() && !$local) { return new \WP_Error('cseo_https_required', 'HTTPS is required.', array('status' => 403)); }
    return current_user_can('company_seo_read') ? true : new \WP_Error('cseo_forbidden', 'Connector read access required.', array('status' => 403));
}

function object_permission($request) {
    $allowed = read_permission();
    if (is_wp_error($allowed)) { return $allowed; }
    $post = get_post((int) $request['id']);
    if (!$post || !is_post_type_viewable($post->post_type) || $post->post_password !== ''
        || ($post->post_status !== 'publish' && !current_user_can('edit_post', $post->ID))) {
        return new \WP_Error('cseo_not_found', 'Page unavailable.', array('status' => 404));
    }
    return true;
}

add_action('rest_api_init', function () {
    $read = __NAMESPACE__ . '\\read_permission';
    register_rest_route('company-seo/v1', '/capabilities', array('methods' => 'GET', 'permission_callback' => $read, 'callback' => function () {
        global $wp_version;
        return array('protocol_version' => 1, 'plugin_version' => VERSION, 'wordpress_version' => $wp_version,
            'mode' => get_option('cseo_mode', 'standalone'), 'rendering' => rendering(), 'conflicts' => conflicts(),
            'theme' => wp_get_theme()->get('Name'), 'theme_title_support' => current_theme_supports('title-tag'),
            'elementor_version' => defined('ELEMENTOR_VERSION') ? ELEMENTOR_VERSION : null,
            'operations' => connector_operations(),
            'editable_metadata' => array_keys(fields()), 'remote_write' => writes_enabled() && current_user_can('company_seo_meta_write'),
            'restore' => writes_enabled() && current_user_can('company_seo_restore'),
            'metadata_write_fields' => array('title','description'),
            'metadata_target_kinds' => array('post','home','category'),
            'unsupported' => array('body_writes', 'term_metadata', 'json_ld', 'social_images', 'hreflang', 'custom_canonical', 'custom_robots'));
    }));
    register_rest_route('company-seo/v1', '/health', array('methods' => 'GET', 'permission_callback' => $read,
        'callback' => function () { return array('status' => 'ready', 'writes_enabled' => writes_enabled() && current_user_can('company_seo_meta_write')); }));
    register_rest_route('company-seo/v1', '/pages', array('methods' => 'GET', 'permission_callback' => $read,
        'args' => array('page' => array('type' => 'integer', 'default' => 1, 'minimum' => 1, 'maximum' => 10000),
            'per_page' => array('type' => 'integer', 'default' => 25, 'minimum' => 1, 'maximum' => 100)),
        'callback' => function ($request) {
            $query = new \WP_Query(array('post_type' => array_values(get_post_types(array('public' => true))),
                'post_status' => 'publish', 'has_password' => false, 'posts_per_page' => $request['per_page'], 'paged' => $request['page'],
                'orderby' => 'ID', 'order' => 'ASC'));
            $items = array();
            foreach ($query->posts as $post) {
                $items[] = array('id' => $post->ID, 'url' => get_permalink($post), 'title' => $post->post_title,
                    'type' => $post->post_type, 'modified_gmt' => $post->post_modified_gmt, 'revision' => revision($post));
            }
            return array('items' => $items, 'page' => $request['page'], 'total' => (int) $query->found_posts, 'pages' => (int) $query->max_num_pages);
        }));
    foreach (array('seo', 'content-map') as $operation) {
        register_rest_route('company-seo/v1', '/pages/(?P<id>\\d+)/' . $operation, array('methods' => 'GET',
            'args' => array('id' => array('type' => 'integer', 'minimum' => 1)),
            'permission_callback' => __NAMESPACE__ . '\\object_permission',
            'callback' => function ($request) use ($operation) {
                $post = get_post((int) $request['id']);
                if ($operation === 'content-map') {
                    return array('id' => $post->ID, 'detected_adapter' => get_post_meta($post->ID, '_elementor_edit_mode', true) === 'builder' ? 'elementor_readonly' : 'wordpress_readonly',
                        'selected_adapter' => 'metadata_readonly', 'editable_fields' => array(), 'remote_write' => false);
                }
                return array('id' => $post->ID, 'stored' => metadata($post->ID), 'revision' => revision($post),
                    'provenance' => 'wordpress_local_metadata', 'schema_version' => 1, 'effective_requires_public_verification' => true);
            }));
    }
});
