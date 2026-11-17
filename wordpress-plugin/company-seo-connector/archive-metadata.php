<?php
/** Typed archive targets; separate ledger prevents post/term ID confusion. */
namespace CompanySEO;
defined('ABSPATH') || exit;

function install_archive_ledger() {
    global $wpdb;
    require_once ABSPATH.'wp-admin/includes/upgrade.php';
    $table=$wpdb->prefix.'cseo_archive_changes';$collate=$wpdb->get_charset_collate();
    dbDelta("CREATE TABLE $table (
        id varchar(36) NOT NULL,
        post_id bigint(20) unsigned NOT NULL,
        target_kind varchar(16) NOT NULL,
        payload_hash char(64) NOT NULL,
        before_json longtext NOT NULL,
        after_json longtext NOT NULL,
        before_revision char(64) NOT NULL,
        after_revision char(64) NOT NULL,
        state varchar(20) NOT NULL,
        created_at datetime NOT NULL,
        PRIMARY KEY  (id)
    ) ENGINE=InnoDB $collate;");
    add_option('cseo_home_lock','1','',false);
    if ($wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s',$wpdb->esc_like($table)))===$table) { update_option('cseo_archive_ledger_version','1'); }
}

function archive_object($kind,$id) {
    if ($kind==='home' && $id===0 && get_option('show_on_front')!=='page') { return array('name'=>get_option('blogname'),'mode'=>get_option('show_on_front')); }
    if ($kind==='category' && $id>0) {
        $term=get_term($id);
        if ($term && !is_wp_error($term) && in_array($term->taxonomy,array('category','product_cat'),true)) { return array('name'=>$term->name,'slug'=>$term->slug,'taxonomy'=>$term->taxonomy,'description'=>$term->description); }
    }
    return null;
}
function archive_metadata($kind,$id) {
    $values=array();
    foreach (fields() as $field=>$max) { $values[$field]=(string)($kind==='home'?get_option('_cseo_home_'.$field,''):get_term_meta($id,PREFIX.$field,true)); }
    return $values;
}
function archive_clear($kind,$id) {
    if ($kind==='home') {
        wp_cache_delete('alloptions','options');wp_cache_delete('notoptions','options');
        foreach (fields() as $field=>$max) { wp_cache_delete('_cseo_home_'.$field,'options'); }
    } else { clean_term_cache($id);wp_cache_delete($id,'term_meta'); }
}
function archive_revision($kind,$id) { return hash('sha256',wp_json_encode(array('kind'=>$kind,'id'=>$id,'object'=>archive_object($kind,$id),'seo'=>archive_metadata($kind,$id)))); }
function archive_permission($request,$write=false,$restore=false) {
    $read=read_permission();if (is_wp_error($read)) { return $read; }
    $kind=$request['kind'];$id=(int)$request['target'];
    if (!archive_object($kind,$id)) { return change_error('archive_unavailable',404); }
    if ($write && (!writes_enabled() || get_option('cseo_archive_ledger_version')!=='1' || !current_user_can($restore?'company_seo_restore':'company_seo_meta_write') || ($kind==='category' && !current_user_can('edit_term',$id)))) { return change_error('archive_write_denied',403); }
    return true;
}
function archive_payload($request) {
    $data=$request->get_json_params();
    // Reuse the bounded native-field validator, with a synthetic positive ID
    // only inside validation; the actual typed target remains in the route.
    if (!is_array($data) || !isset($data['post_id']) || $data['post_id']!==(int)$request['target']) { return change_error('archive_target_mismatch',400); }
    $copy=new \WP_REST_Request('POST','/');$data['post_id']=max(1,$data['post_id']);
    $copy->set_header('Content-Type','application/json');$copy->set_body(wp_json_encode($data));
    $checked=change_payload($copy);
    if (is_wp_error($checked)) { return $checked; }
    $checked['post_id']=(int)$request['target'];$checked['target_kind']=$request['kind'];return $checked;
}
function archive_transaction($kind,$id) {
    global $wpdb;
    $tables=array($wpdb->prefix.'cseo_archive_changes',$kind==='home'?$wpdb->options:$wpdb->termmeta);
    if ($kind==='category') { $tables[]=$wpdb->terms;$tables[]=$wpdb->term_taxonomy; }
    foreach ($tables as $table) {
        $engine=$wpdb->get_var($wpdb->prepare('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',$table));
        if (strtoupper((string)$engine)!=='INNODB') { return false; }
    }
    if ($wpdb->query('START TRANSACTION')===false) { return false; }
    if ($kind==='home') {
        $locked=$wpdb->get_var("SELECT option_id FROM {$wpdb->options} WHERE option_name='cseo_home_lock' FOR UPDATE");
        $wpdb->query("SELECT option_id FROM {$wpdb->options} WHERE option_name IN ('_cseo_home_title','_cseo_home_description','_cseo_home_og_title','_cseo_home_og_description','blogname','show_on_front','page_on_front') FOR UPDATE");
    }
    else {
        $locked=$wpdb->get_var($wpdb->prepare("SELECT term_id FROM {$wpdb->terms} WHERE term_id=%d FOR UPDATE",$id));
        $wpdb->query($wpdb->prepare("SELECT term_taxonomy_id FROM {$wpdb->term_taxonomy} WHERE term_id=%d FOR UPDATE",$id));
        $wpdb->query($wpdb->prepare("SELECT meta_id FROM {$wpdb->termmeta} WHERE term_id=%d FOR UPDATE",$id));
    }
    if (!$locked) { $wpdb->query('ROLLBACK');return false; }
    archive_clear($kind,$id);return true;
}
function archive_save_value($kind,$id,$field,$value,$exists=true) {
    if ($kind==='home') { if ($exists) { update_option('_cseo_home_'.$field,$value,false); } else { delete_option('_cseo_home_'.$field); } }
    else { if ($exists) { update_term_meta($id,PREFIX.$field,wp_slash($value)); } else { delete_term_meta($id,PREFIX.$field); } }
    archive_clear($kind,$id);
}
function archive_change($request,$restore=false) {
    global $wpdb;
    $kind=$request['kind'];$id=(int)$request['target'];$table=$wpdb->prefix.'cseo_archive_changes';
    $data=$restore?null:archive_payload($request);
    if (is_wp_error($data)) { return $data; }
    if ($restore && ($request->get_json_params() || strlen($request->get_body())>1024)) { return change_error('invalid_restore_payload',400); }
    if (!archive_transaction($kind,$id)) { return change_error('transaction_unavailable',503); }
    try {
        $change_id=$restore?$request['id']:$data['change_id'];
        $row=$wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id=%s FOR UPDATE",$change_id),ARRAY_A);
        if ($row && ($row['target_kind']!==$kind || (int)$row['post_id']!==$id)) { $wpdb->query('ROLLBACK');return change_error('archive_target_mismatch'); }
        if ($restore) {
            if (!$row) { $wpdb->query('ROLLBACK');return change_error('change_unavailable',404); }
            if ($row['state']==='restored') { $wpdb->query('ROLLBACK');return receipt($row); }
            if ($row['state']!=='applied' || !hash_equals($row['after_revision'],archive_revision($kind,$id))) { $wpdb->query('ROLLBACK');return change_error('restore_stale_conflict'); }
            foreach (json_decode($row['before_json'],true) as $field=>$old) {
                if (!in_array($field,array('title','description'),true) || !is_string($old['value']) || !is_bool($old['exists'])) { throw new \RuntimeException(); }
                archive_save_value($kind,$id,$field,$old['value'],$old['exists']);
            }
            if (!hash_equals($row['before_revision'],archive_revision($kind,$id))) { throw new \RuntimeException(); }
            $row['state']='restored';
            if ($wpdb->update($table,array('state'=>'restored'),array('id'=>$change_id))===false) { throw new \RuntimeException(); }
        } else {
            $hash=hash('sha256',wp_json_encode($data));
            if ($row) { $wpdb->query('ROLLBACK');return hash_equals($hash,$row['payload_hash'])?receipt($row):change_error('idempotency_payload_conflict'); }
            if (!hash_equals($data['expected_revision'],archive_revision($kind,$id))) { $wpdb->query('ROLLBACK');return change_error('stale_revision'); }
            $before=array();$stored=archive_metadata($kind,$id);
            foreach ($data['changes'] as $field=>$value) {
                $exists=$kind==='home'?get_option('_cseo_home_'.$field,null)!==null:metadata_exists('term',$id,PREFIX.$field);
                $before[$field]=array('value'=>$stored[$field],'exists'=>$exists);
                archive_save_value($kind,$id,$field,$value);
                if (archive_metadata($kind,$id)[$field]!==$value) { throw new \RuntimeException(); }
            }
            $row=array('id'=>$change_id,'post_id'=>$id,'target_kind'=>$kind,'payload_hash'=>$hash,'before_json'=>wp_json_encode($before),
                'after_json'=>wp_json_encode(archive_metadata($kind,$id)),'before_revision'=>$data['expected_revision'],
                'after_revision'=>archive_revision($kind,$id),'state'=>'applied','created_at'=>current_time('mysql',true));
            if ($wpdb->insert($table,$row)===false) { throw new \RuntimeException(); }
        }
        if ($wpdb->query('COMMIT')===false) { throw new \RuntimeException(); }
        archive_clear($kind,$id);mirror_metadata_record($row);return receipt($row);
    } catch (\Throwable $error) { $wpdb->query('ROLLBACK');archive_clear($kind,$id);return change_error('archive_retryable_failure',503); }
}

add_action('rest_api_init',function () {
    register_rest_route('company-seo/v1','/contexts',array('methods'=>'GET','permission_callback'=>__NAMESPACE__.'\\read_permission','callback'=>function () {
        $items=array();
        if (get_option('show_on_front')!=='page') { $items[]=array('id'=>0,'kind'=>'home','type'=>'homepage','url'=>home_url('/'),'title'=>get_option('blogname')); }
        $taxonomies=array_values(array_filter(array('category','product_cat'),'taxonomy_exists'));
        $terms=get_terms(array('taxonomy'=>$taxonomies,'hide_empty'=>false,'number'=>100));
        if (!is_wp_error($terms)) { foreach ($terms as $term) { $url=get_term_link($term);if (!is_wp_error($url)) { $items[]=array('id'=>$term->term_id,'kind'=>'category','type'=>$term->taxonomy,'url'=>$url,'title'=>$term->name); } } }
        return array('items'=>$items,'truncated'=>!is_wp_error($terms) && count($terms)>=100);
    }));
    $base='/contexts/(?P<kind>home|category)/(?P<target>\d+)';
    register_rest_route('company-seo/v1',$base.'/seo',array('methods'=>'GET','permission_callback'=>function($r) { return archive_permission($r); },'callback'=>function($r) {
        $kind=$r['kind'];$id=(int)$r['target'];archive_clear($kind,$id);return array('id'=>$id,'stored'=>archive_metadata($kind,$id),'revision'=>archive_revision($kind,$id));
    }));
    foreach (array('preview','apply') as $operation) {
        register_rest_route('company-seo/v1',$base.'/changes/'.$operation,array('methods'=>'POST','permission_callback'=>function($r) { return archive_permission($r,true); },'callback'=>function($r) use($operation) {
            if ($operation==='apply') { return archive_change($r); }
            $data=archive_payload($r);if (is_wp_error($data)) { return $data; }
            if (!hash_equals($data['expected_revision'],archive_revision($r['kind'],(int)$r['target']))) { return change_error('stale_revision'); }
            return array('post_id'=>(int)$r['target'],'before'=>archive_metadata($r['kind'],(int)$r['target']),'proposed'=>$data['changes'],'writes_performed'=>false);
        }));
    }
    $status=$base.'/changes/(?P<id>[a-f0-9-]{36})';
    register_rest_route('company-seo/v1',$status,array('methods'=>'GET','permission_callback'=>function($r) { return archive_permission($r,true); },'callback'=>function($r) {
        global $wpdb;$row=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}cseo_archive_changes WHERE id=%s AND target_kind=%s AND post_id=%d",$r['id'],$r['kind'],(int)$r['target']),ARRAY_A);
        return $row?receipt($row):change_error('change_unavailable',404);
    }));
    register_rest_route('company-seo/v1',$status.'/restore',array('methods'=>'POST','permission_callback'=>function($r) { return archive_permission($r,true,true); },'callback'=>function($r) { return archive_change($r,true); }));
});

function rendered_metadata() {
    if (is_singular()) { return metadata(get_queried_object_id()); }
    if (is_front_page()) { return archive_metadata('home',0); }
    if (is_category() || is_tax('product_cat')) { return archive_metadata('category',get_queried_object_id()); }
    return array_fill_keys(array_keys(fields()),'');
}
