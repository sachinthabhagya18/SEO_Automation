<?php
namespace CompanySEO;
defined('ABSPATH') || exit;

function install_ledger() {
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $table=$wpdb->prefix.'cseo_changes';
    $collate=$wpdb->get_charset_collate();
    dbDelta("CREATE TABLE $table (
        id varchar(36) NOT NULL,
        post_id bigint(20) unsigned NOT NULL,
        payload_hash char(64) NOT NULL,
        before_json longtext NOT NULL,
        after_json longtext NOT NULL,
        before_revision char(64) NOT NULL,
        after_revision char(64) NOT NULL,
        state varchar(20) NOT NULL,
        created_at datetime NOT NULL,
        PRIMARY KEY  (id),
        KEY post_id (post_id)
    ) ENGINE=InnoDB $collate;");
    if ($wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s',$wpdb->esc_like($table))) === $table) { update_option('cseo_ledger_version','1'); }
}

function writes_enabled() {
    return (bool)get_option('cseo_writes_enabled',false) && get_option('cseo_ledger_version')==='1'
        && in_array(wp_get_environment_type(),array('local','staging'),true) && rendering();
}

function connector_operations() {
    $operations=array('inventory_read','seo_read','content_map_read');
    if (writes_enabled() && current_user_can('company_seo_meta_write')) { $operations=array_merge($operations,array('metadata_preview','metadata_apply','change_status')); }
    if (writes_enabled() && current_user_can('company_seo_restore')) { $operations[]= 'metadata_restore'; }
    return array_values(array_unique($operations));
}

function change_error($code,$status=409) { return new \WP_Error('cseo_'.$code,$code,array('status'=>$status)); }

add_filter('rest_pre_dispatch',function($result,$server,$request) {
    if (current_user_can('company_seo_meta_write') && !current_user_can('manage_options')
        && !in_array($request->get_method(),array('GET','HEAD','OPTIONS'),true)
        && !preg_match('#^/company-seo/v1/(changes/|contexts/(home|category)/\d+/changes/)(preview|apply|[a-f0-9-]{36}/restore)$#D',$request->get_route())) {
        return change_error('metadata_account_route_restricted',403);
    }
    return $result;
},10,3);

function change_payload($request) {
    if (strlen($request->get_body())>16384) { return change_error('payload_too_large',413); }
    $data=$request->get_json_params();
    if (!is_array($data) || array_diff(array_keys($data),array('change_id','post_id','expected_revision','changes','approval_hash'))
        || !isset($data['change_id'],$data['post_id'],$data['expected_revision'],$data['changes'],$data['approval_hash'])
        || !is_string($data['change_id']) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/D',$data['change_id'])
        || !is_int($data['post_id']) || $data['post_id']<1
        || !is_string($data['expected_revision']) || !preg_match('/^[a-f0-9]{64}$/D',$data['expected_revision'])
        || !is_string($data['approval_hash']) || !preg_match('/^[a-f0-9]{64}$/D',$data['approval_hash'])
        || !is_array($data['changes']) || !$data['changes'] || array_diff(array_keys($data['changes']),array('title','description'))) {
        return change_error('invalid_payload',400);
    }
    foreach ($data['changes'] as $field=>$value) {
        $max=$field==='title'?200:500;
        if (!is_string($value) || $value==='' || mb_strlen($value)>$max || sanitize_text_field($value)!==$value) {
            return change_error('invalid_metadata_text',400);
        }
    }
    ksort($data['changes']);
    return array('change_id'=>$data['change_id'],'post_id'=>$data['post_id'],
        'expected_revision'=>$data['expected_revision'],'changes'=>$data['changes'],'approval_hash'=>$data['approval_hash']);
}

function change_permission($request,$restore=false,$status=false) {
    $allowed=read_permission();
    if (is_wp_error($allowed)) { return $allowed; }
    if (!writes_enabled()) { return change_error('writes_disabled',403); }
    $permitted=$status?(current_user_can('company_seo_restore') || current_user_can('company_seo_meta_write')):current_user_can($restore?'company_seo_restore':'company_seo_meta_write');
    if (!$permitted) { return change_error('write_capability_required',403); }
    if (isset($request['id'])) {
        global $wpdb;
        $post_id=$wpdb->get_var($wpdb->prepare("SELECT post_id FROM {$wpdb->prefix}cseo_changes WHERE id=%s",$request['id']));
    } else {
        $data=change_payload($request);
        if (is_wp_error($data)) { return $data; }
        $post_id=$data['post_id'];
    }
    $post=get_post((int)$post_id);
    if (!$post || $post->post_status!=='publish' || $post->post_password!=='' || !is_post_type_viewable($post->post_type)
        || !current_user_can('edit_post',$post->ID)) { return change_error('page_unavailable',404); }
    return true;
}

function fresh_post($id) {
    wp_cache_delete($id,'posts'); wp_cache_delete($id,'post_meta');
    return get_post($id);
}

function ledger_transaction($post_id) {
    global $wpdb;
    // Refuse a transactional guarantee on nontransactional installations.
    foreach (array($wpdb->posts,$wpdb->postmeta,$wpdb->prefix.'cseo_changes') as $table) {
        $engine=$wpdb->get_var($wpdb->prepare('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',$table));
        if (strtoupper((string)$engine)!=='INNODB') { return false; }
    }
    if ($wpdb->query('START TRANSACTION')===false) { return false; }
    if (!$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$post_id))) { $wpdb->query('ROLLBACK');return false; }
    if ($wpdb->query($wpdb->prepare("SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d FOR UPDATE",$post_id))===false) { $wpdb->query('ROLLBACK');return false; }
    return true;
}

function receipt($row) {
    return array('change_id'=>$row['id'],'post_id'=>(int)$row['post_id'],'target_kind'=>$row['target_kind']??'post','state'=>$row['state'],
        'before_revision'=>$row['before_revision'],'after_revision'=>$row['after_revision'],
        'before'=>json_decode($row['before_json'],true),'after'=>json_decode($row['after_json'],true));
}

function apply_metadata($request) {
    global $wpdb;
    $data=change_payload($request);
    if (is_wp_error($data)) { return $data; }
    $post_id=$data['post_id']; $table=$wpdb->prefix.'cseo_changes';
    if (!ledger_transaction($post_id)) { return change_error('transaction_unavailable',503); }
    try {
        $hash=hash('sha256',wp_json_encode($data));
        $existing=$wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id=%s FOR UPDATE",$data['change_id']),ARRAY_A);
        if ($existing) {
            $wpdb->query('ROLLBACK');
            return hash_equals($existing['payload_hash'],$hash)?receipt($existing):change_error('idempotency_payload_conflict');
        }
        $post=fresh_post($post_id);
        if (!hash_equals(revision($post),$data['expected_revision'])) { $wpdb->query('ROLLBACK');return change_error('stale_revision'); }
        $before=array();
        foreach ($data['changes'] as $field=>$value) { $before[$field]=array('value'=>(string)get_post_meta($post_id,PREFIX.$field,true),'exists'=>metadata_exists('post',$post_id,PREFIX.$field)); }
        $row=array('id'=>$data['change_id'],'post_id'=>$post_id,'payload_hash'=>$hash,'before_json'=>wp_json_encode($before),
            'after_json'=>'{}','before_revision'=>$data['expected_revision'],'after_revision'=>'','state'=>'applying','created_at'=>current_time('mysql',true));
        if ($wpdb->insert($table,$row)===false) { throw new \RuntimeException('ledger_insert_failed'); }
        foreach ($data['changes'] as $field=>$value) {
            update_post_meta($post_id,PREFIX.$field,wp_slash($value));
            wp_cache_delete($post_id,'post_meta');
            if (get_post_meta($post_id,PREFIX.$field,true)!==$value) { throw new \RuntimeException('metadata_save_failed'); }
        }
        $row['after_json']=wp_json_encode(metadata($post_id));
        $row['after_revision']=revision(fresh_post($post_id)); $row['state']='applied';
        if ($wpdb->update($table,array('after_json'=>$row['after_json'],'after_revision'=>$row['after_revision'],'state'=>'applied'),array('id'=>$row['id']))===false
            || $wpdb->query('COMMIT')===false) { throw new \RuntimeException('commit_failed'); }
        fresh_post($post_id);
        mirror_metadata_record($row);
        return receipt($row);
    } catch (\Throwable $error) { $wpdb->query('ROLLBACK');fresh_post($post_id);return change_error('apply_retryable_failure',503); }
}

function restore_metadata($request) {
    global $wpdb;
    if (strlen($request->get_body())>1024) { return change_error('payload_too_large',413); }
    if ($request->get_json_params()) { return change_error('invalid_restore_payload',400); }
    $table=$wpdb->prefix.'cseo_changes';
    $row=$wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id=%s",$request['id']),ARRAY_A);
    if (!$row) { return change_error('change_unavailable',404); }
    $id=(int)$row['post_id'];
    if (!ledger_transaction($id)) { return change_error('transaction_unavailable',503); }
    try {
        $row=$wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id=%s FOR UPDATE",$request['id']),ARRAY_A);
        if ($row['state']==='restored') { $wpdb->query('ROLLBACK');return receipt($row); }
        if ($row['state']!=='applied' || !hash_equals($row['after_revision'],revision(fresh_post($id)))) { $wpdb->query('ROLLBACK');return change_error('restore_stale_conflict'); }
        foreach (json_decode($row['before_json'],true) as $field=>$old) {
            if (!in_array($field,array('title','description'),true)) { throw new \RuntimeException('invalid_snapshot'); }
            if ($old['exists']) { update_post_meta($id,PREFIX.$field,wp_slash($old['value'])); }
            else { delete_post_meta($id,PREFIX.$field); }
        }
        $post=fresh_post($id);
        if (!hash_equals($row['before_revision'],revision($post))) { throw new \RuntimeException('restore_mismatch'); }
        if ($wpdb->update($table,array('state'=>'restored'),array('id'=>$row['id']))===false || $wpdb->query('COMMIT')===false) { throw new \RuntimeException('restore_commit_failed'); }
        $row['state']='restored';fresh_post($id);mirror_metadata_record($row);return receipt($row);
    } catch (\Throwable $error) { $wpdb->query('ROLLBACK');fresh_post($id);return change_error('restore_retryable_failure',503); }
}

add_action('rest_api_init',function () {
    $permission=function($request) { return change_permission($request); };
    register_rest_route('company-seo/v1','/changes/preview',array('methods'=>'POST','permission_callback'=>$permission,'callback'=>function($request) {
        $data=change_payload($request);if (is_wp_error($data)) { return $data; }
        $post=fresh_post($data['post_id']);
        if (!hash_equals(revision($post),$data['expected_revision'])) { return change_error('stale_revision'); }
        return array('post_id'=>$post->ID,'before'=>metadata($post->ID),'proposed'=>$data['changes'],'writes_performed'=>false);
    }));
    register_rest_route('company-seo/v1','/changes/apply',array('methods'=>'POST','permission_callback'=>$permission,'callback'=>__NAMESPACE__.'\\apply_metadata'));
    register_rest_route('company-seo/v1','/changes/(?P<id>[a-f0-9-]{36})',array('methods'=>'GET','permission_callback'=>function($request) { return change_permission($request,false,true); },'callback'=>function($request) {
        global $wpdb;$row=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}cseo_changes WHERE id=%s",$request['id']),ARRAY_A);
        return $row?receipt($row):change_error('change_unavailable',404);
    }));
    register_rest_route('company-seo/v1','/changes/(?P<id>[a-f0-9-]{36})/restore',array('methods'=>'POST',
        'permission_callback'=>function($request) { return change_permission($request,true); },'callback'=>__NAMESPACE__.'\\restore_metadata'));
});
