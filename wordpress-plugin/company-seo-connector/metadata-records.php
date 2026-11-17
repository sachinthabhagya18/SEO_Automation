<?php
/** Private admin history mirror. SQL ledger remains the idempotency authority. */
namespace CompanySEO;
defined('ABSPATH') || exit;

add_action('init', function () {
    register_post_type('cseo_record', array(
        'labels'=>array('name'=>'SEO Metadata Records','singular_name'=>'SEO Metadata Record'),
        'public'=>false,'publicly_queryable'=>false,'exclude_from_search'=>true,
        'show_ui'=>true,'show_in_menu'=>'options-general.php','show_in_rest'=>false,
        'rewrite'=>false,'query_var'=>false,'supports'=>array('title'),
        'capabilities'=>array('edit_post'=>'manage_options','read_post'=>'manage_options',
            'delete_post'=>'do_not_allow','edit_posts'=>'manage_options','edit_others_posts'=>'manage_options',
            'publish_posts'=>'do_not_allow','read_private_posts'=>'manage_options','create_posts'=>'do_not_allow',
            'delete_posts'=>'do_not_allow','delete_private_posts'=>'do_not_allow','delete_published_posts'=>'do_not_allow'),
        'map_meta_cap'=>false,
    ));
});

function mirror_metadata_record($row) {
    // Post-commit mirror failure must never invalidate a committed receipt.
    $lock='cseo_record_'.str_replace('-','',$row['id']);
    global $wpdb;
    if ((int)$wpdb->get_var($wpdb->prepare('SELECT GET_LOCK(%s,1)',$lock))!==1) { return; }
    try {
        $records=get_posts(array('post_type'=>'cseo_record','post_status'=>'private','numberposts'=>1,
            'meta_key'=>'_cseo_change_id','meta_value'=>$row['id'],'fields'=>'ids'));
        $args=array('post_type'=>'cseo_record','post_status'=>'private',
            'post_title'=>'SEO '.$row['id'].' — '.$row['state']);
        if ($records) { $args['ID']=$records[0]; }
        $id=wp_insert_post(wp_slash($args),true);
        if (is_wp_error($id) || !$id) { return; }
        foreach (array('id'=>'change_id','post_id'=>'target_post_id','target_kind'=>'target_kind','state'=>'state','before_json'=>'before',
            'after_json'=>'after','before_revision'=>'before_revision','after_revision'=>'after_revision') as $key=>$meta) {
            update_post_meta($id,'_cseo_'.$meta,wp_slash((string)($row[$key]??'')));
        }
    } catch (\Throwable $error) {
        // Durable SQL receipt is authoritative; history can be reconciled later.
    } finally { $wpdb->get_var($wpdb->prepare('SELECT RELEASE_LOCK(%s)',$lock)); }
}

add_action('add_meta_boxes_cseo_record',function () {
    add_meta_box('cseo_record_details','Recorded metadata',function ($post) {
        foreach (array('change_id','target_post_id','state','before_revision','after_revision','before','after') as $key) {
            echo '<p><strong>'.esc_html($key).'</strong></p><pre style="white-space:pre-wrap">'.esc_html(get_post_meta($post->ID,'_cseo_'.$key,true)).'</pre>';
        }
        echo '<p>History mirror. Editing this record does not change page metadata. Use the reviewed connector workflow.</p>';
    });
});
