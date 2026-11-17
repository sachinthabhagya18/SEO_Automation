"""One fixed, private staging copy. Run as root on the verified VPS.

Default is a read-only plan. --apply creates only the new denimstage account,
database and virtual server. All command details/secrets stay in a root-only job.
"""
import argparse
import base64
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import subprocess
import urllib.request
import zipfile

SOURCE=Path('/home/denimyard/public_html')
TARGET=Path('/home/denimstage/public_html')
JOB=Path('/root/seo-staging-denimyard')
DOMAIN='staging.denimyard.com'
URL='https://'+DOMAIN
APACHE_ROOT=Path('/etc/httpd') if Path('/etc/httpd').is_dir() else Path('/etc/apache2')
AUTH=APACHE_ROOT/'cseo-staging-denimyard.htpasswd'
STATE=JOB/'state.json'

def check_paths():
    if os.geteuid()!=0 or not (SOURCE/'wp-config.php').is_file() or SOURCE.resolve()!=SOURCE:
        raise RuntimeError('source_identity_guard')
    if not APACHE_ROOT.is_dir(): raise RuntimeError('apache_layout_requires_review')
    if TARGET.exists() and (TARGET.is_symlink() or TARGET.resolve()!=TARGET): raise RuntimeError('target_path_guard')
    if SOURCE==TARGET or SOURCE in TARGET.parents: raise RuntimeError('target_path_guard')
    for tool in ('virtualmin','php','rsync','mysql','mysqldump','htpasswd'):
        if not shutil.which(tool): raise RuntimeError('missing_tool_'+tool)

def capture(args):
    result=subprocess.run(args,capture_output=True,text=True)
    if result.returncode: raise RuntimeError('read_only_inventory_failed')
    return result.stdout.strip()

def php_string(value):
    return "'"+str(value).replace('\\','\\\\').replace("'","\\'")+"'"

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');options=parser.parse_args()
    check_paths()
    source_domain=capture(['virtualmin','list-domains','--domain','denimyard.com','--name-only'])
    if source_domain!='denimyard.com': raise RuntimeError('source_domain_not_confirmed')
    probe=subprocess.run(['virtualmin','list-domains','--domain',DOMAIN,'--name-only'],capture_output=True,text=True)
    if probe.returncode and ('Virtual server '+DOMAIN+' does not exist') not in probe.stdout+probe.stderr:
        raise RuntimeError('target_inventory_failed')
    existing=probe.stdout.strip() if not probe.returncode else ''
    if existing and existing!=DOMAIN: raise RuntimeError('target_inventory_failed')
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    if existing and not state.get('created'): raise RuntimeError('existing_target_requires_review')
    print(json.dumps({'source':str(SOURCE),'target':str(TARGET),'domain':DOMAIN,'separate_user_database':'denimstage',
        'target_exists':bool(existing),'mode':'apply' if options.apply else 'plan','dns_changes':False,'live_changes':False}))
    if not options.apply: return
    if state.get('complete'):
        print('Private staging already prepared; no reset performed. DNS/TLS connection remains a separate step.');return
    JOB.mkdir(mode=0o700,exist_ok=True);JOB.chmod(0o700)
    def save():
        STATE.write_text(json.dumps(state,indent=2));STATE.chmod(0o600)
    def run(name,args,stdin=None):
        with (JOB/'provision.log').open('ab') as log:
            result=subprocess.run(args,input=stdin,stdout=log,stderr=log)
        (JOB/'provision.log').chmod(0o600)
        if result.returncode: raise RuntimeError('phase_failed_'+name)
        print('Completed:',name,flush=True)
    password_file=JOB/'virtualmin-password.txt'
    if not password_file.exists(): password_file.write_text(secrets.token_urlsafe(40));password_file.chmod(0o600)
    password=password_file.read_text().strip()
    if not state.get('created'):
        if subprocess.run(['id','-u','denimstage'],capture_output=True).returncode==0: raise RuntimeError('existing_unix_user_requires_review')
        run('create_private_domain',['virtualmin','create-domain','--domain',DOMAIN,'--desc','Company SEO isolated staging',
            '--user','denimstage','--db','denimstage','--passfile',str(password_file),'--unix','--dir','--mysql','--logrotate','--acme-never'])
        state['created']=True;save()
    user=pwd.getpwnam('denimstage')
    if user.pw_dir!='/home/denimstage' or user.pw_uid==SOURCE.stat().st_uid: raise RuntimeError('unix_isolation_guard')
    TARGET.mkdir(exist_ok=True)
    if TARGET.resolve()!=TARGET: raise RuntimeError('target_path_guard')
    domain_file=Path(capture(['virtualmin','list-domains','--domain',DOMAIN,'--file-only']))
    if Path('/etc/webmin/virtual-server/domains') not in domain_file.resolve().parents: raise RuntimeError('domain_record_guard')
    domain_config=dict(line.split('=',1) for line in domain_file.read_text().splitlines() if '=' in line)
    if any(domain_config.get(k)!=v for k,v in {'dom':DOMAIN,'user':'denimstage','mysql_user':'denimstage','db':'denimstage'}.items()):
        raise RuntimeError('target_database_guard')
    password=domain_config.get('mysql_pass','')
    if not password: raise RuntimeError('target_database_password_unavailable')
    if not state.get('copied'):
        exclusions=['wp-config.php','.htaccess','.htpasswd','.user.ini','php.ini','.git','.env','.env.*','.well-known','*.pem','*.key','*.sql','*.zip','*.log','error_log',
            'wp-content/uploads','wp-content/cache','wp-content/updraft','wp-content/ai1wm-backups',
            'wp-content/object-cache.php','wp-content/advanced-cache.php','wp-content/db.php','wp-content/sunrise.php',
            'wp-content/plugins/company-seo-connector-*']
        args=['rsync','-a','--no-owner','--no-group','--safe-links']
        for item in exclusions: args+=['--exclude',item]
        run('copy_files',args+[str(SOURCE)+'/',str(TARGET)+'/'])
        uploads=TARGET/'wp-content/uploads';uploads.mkdir(parents=True,exist_ok=True)
        args=['rsync','-a','--no-owner','--no-group','--safe-links','--include','*/']
        for extension in ('jpg','jpeg','png','gif','webp','avif','JPG','JPEG','PNG'):
            args+=['--include','*.'+extension]
        args+=['--exclude','*',str(SOURCE/'wp-content/uploads')+'/',str(uploads)+'/']
        if (SOURCE/'wp-content/uploads').is_dir(): run('copy_public_raster_media',args)
        state['copied']=True;save()
    config_text=(SOURCE/'wp-config.php').read_text()
    match=re.search(r"\$table_prefix\s*=\s*['\"]([A-Za-z0-9_]+)['\"]",config_text)
    if not match: raise RuntimeError('prefix_requires_review')
    prefix=match.group(1)
    if not state.get('configured'):
        lines=['<?php']
        constants={'DB_NAME':'denimstage','DB_USER':'denimstage','DB_PASSWORD':password,'DB_HOST':'localhost',
            'DB_CHARSET':'utf8mb4','DB_COLLATE':'','WP_HOME':URL,'WP_SITEURL':URL,'WP_ENVIRONMENT_TYPE':'staging'}
        for key in ('AUTH_KEY','SECURE_AUTH_KEY','LOGGED_IN_KEY','NONCE_KEY','AUTH_SALT','SECURE_AUTH_SALT','LOGGED_IN_SALT','NONCE_SALT'):
            constants[key]=secrets.token_urlsafe(64)
        for key,value in constants.items(): lines.append('define('+php_string(key)+','+php_string(value)+');')
        lines+=['define("DISABLE_WP_CRON",true);','define("DISALLOW_FILE_EDIT",true);','define("WP_DEBUG",false);',
            '$table_prefix='+php_string(prefix)+';','if (!defined("ABSPATH")) define("ABSPATH", __DIR__."/");','require_once ABSPATH."wp-settings.php";']
        (TARGET/'wp-config.php').write_text('\n'.join(lines)+'\n');(TARGET/'wp-config.php').chmod(0o600)
        mu=TARGET/'wp-content/mu-plugins';mu.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(JOB/'cseo-staging-guard.php',mu/'cseo-staging-guard.php')
        package=JOB/'company-seo-connector-0.2.0.zip'
        plugins=TARGET/'wp-content/plugins'
        with zipfile.ZipFile(package) as archive:
            for item in archive.infolist():
                dest=(plugins/item.filename).resolve()
                if not item.filename.startswith('company-seo-connector/') or plugins not in dest.parents or (item.external_attr>>16)&0o170000==0o120000:
                    raise RuntimeError('plugin_archive_guard')
            archive.extractall(plugins)
        (TARGET/'robots.txt').write_text('User-agent: CompanySEOAudit\nAllow: /\nUser-agent: *\nDisallow: /\n')
        state['configured']=True;save()
    else:
        # Virtualmin templates may generate a DB password distinct from the
        # Unix password. Resolve the new target's actual value without printing it.
        config_file=TARGET/'wp-config.php'
        config_file.write_text(re.sub(r"^define\('DB_PASSWORD',.*\);$",lambda match:'define(\'DB_PASSWORD\','+php_string(password)+');',config_file.read_text(),flags=re.MULTILINE))
    if not state.get('imported'):
        helper=r'''<?php
define('SHORTINIT',true);require '/home/denimyard/public_html/wp-load.php';
if (DB_HOST!=='localhost' || !preg_match('/^[A-Za-z0-9_]+$/',DB_NAME)) exit(2);
function opt($v){return '"'.str_replace(array('\\',"\n","\r",'"'),array('\\\\','\\n','\\r','\\"'),$v).'"';}
$body="[client]\nuser=".opt(DB_USER)."\npassword=".opt(DB_PASSWORD)."\nhost=localhost\n";
file_put_contents('/root/seo-staging-denimyard/source-client.cnf',$body);chmod('/root/seo-staging-denimyard/source-client.cnf',0600);
file_put_contents('/root/seo-staging-denimyard/source-db.txt',DB_NAME);
'''
        run('prepare_source_read_auth',['php'],helper.encode())
        database=(JOB/'source-db.txt').read_text().strip()
        if database=='denimstage' or not re.fullmatch('[A-Za-z0-9_]+',database): raise RuntimeError('database_identity_guard')
        dump=JOB/'source-snapshot.sql'
        try:
            with dump.open('wb') as output,(JOB/'provision.log').open('ab') as log:
                result=subprocess.run(['mysqldump','--defaults-extra-file='+str(JOB/'source-client.cnf'),
                    '--single-transaction','--skip-lock-tables','--no-tablespaces','--skip-triggers','--skip-events',database],stdout=output,stderr=log)
            dump.chmod(0o600)
            if result.returncode: raise RuntimeError('source_snapshot_failed')
        finally:
            (JOB/'source-client.cnf').unlink(missing_ok=True)
        target_auth=JOB/'target-client.cnf'
        quoted=password.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')
        target_auth.write_text('[client]\nuser=denimstage\npassword="'+quoted+'"\nhost=localhost\n');target_auth.chmod(0o600)
        with dump.open('rb') as data,(JOB/'provision.log').open('ab') as log:
            result=subprocess.run(['mysql','--defaults-extra-file='+str(target_auth),'denimstage'],stdin=data,stdout=log,stderr=log)
        if result.returncode: raise RuntimeError('target_import_failed')
        state['imported']=True;save()
    if not state.get('sanitized'):
        run('sanitize_copy',['php',str(JOB/'staging-sanitize.php'),str(TARGET)])
        state['sanitized']=True;save()
    phar=JOB/'wp-cli.phar'
    if not phar.exists():
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base='https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar'
        data=opener.open(base,timeout=30).read(40_000_000)
        expected=opener.open(base+'.sha512',timeout=15).read(1024).decode().split()[0]
        if hashlib.sha512(data).hexdigest()!=expected: raise RuntimeError('wp_cli_digest_mismatch')
        phar.write_bytes(data);phar.chmod(0o600)
    if not state.get('rewritten'):
        for old in ('https://denimyard.com','http://denimyard.com'):
            run('rewrite_staging_urls',['php',str(phar),'--allow-root','--path='+str(TARGET),'search-replace',old,URL,
                '--all-tables-with-prefix','--skip-columns=guid','--precise','--skip-plugins','--skip-themes','--report-changed-only'])
        state['rewritten']=True;save()
    access=JOB/'access.json'
    if not state.get('accounts'):
        run('create_staging_accounts',['php',str(JOB/'staging-accounts.php'),str(TARGET),str(access)])
        state['accounts']=True;save()
    credentials=json.loads(access.read_text())
    hashes=[]
    for account in credentials['connector_accounts'].values():
        result=subprocess.run(['htpasswd','-niB',account['username']],input=account['application_password']+'\n',capture_output=True,text=True)
        if result.returncode: raise RuntimeError('http_auth_hash_failed')
        hashes.append(result.stdout.strip())
    apache_group='apache' if APACHE_ROOT==Path('/etc/httpd') else 'www-data'
    AUTH.write_text('\n'.join(hashes)+'\n');os.chown(AUTH,0,grp.getgrnam(apache_group).gr_gid);AUTH.chmod(0o640)
    htaccess='''AuthType Basic
AuthName "Private Denim Yard staging"
AuthUserFile CSEO_AUTH_FILE
SetEnvIf Request_URI "^/\\.well-known/acme-challenge/" cseo_acme=1
<RequireAny>
Require env cseo_acme
Require valid-user
</RequireAny>
<Files wp-config.php>
Require all denied
</Files>
<IfModule mod_headers.c>
Header always set X-Robots-Tag "noindex, nofollow, noarchive"
Header always set Content-Security-Policy "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'none'; form-action 'self'; base-uri 'self'"
</IfModule>
# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
RewriteBase /
RewriteRule ^index\\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.php [L]
</IfModule>
# END WordPress
'''
    (TARGET/'.htaccess').write_text(htaccess.replace('CSEO_AUTH_FILE',str(AUTH)))
    run('set_staging_ownership',['chown','-R','--no-dereference','denimstage:denimstage',str(TARGET)])
    if not state.get('web_enabled'):
        run('enable_protected_staging_web',['virtualmin','enable-feature','--domain',DOMAIN,'--web','--ssl'])
        state['web_enabled']=True;save()
    apache=shutil.which('apache2ctl') or shutil.which('httpd')
    if not apache: raise RuntimeError('apache_binary_missing')
    run('apache_configuration_check',[apache,'-t'] if Path(apache).name=='httpd' else [apache,'configtest'])
    state['complete']=True;state['dns_tls_pending']=True;save()
    (JOB/'source-snapshot.sql').unlink(missing_ok=True)
    (JOB/'target-client.cnf').unlink(missing_ok=True)
    print('Private staging prepared. Customer/order/session data removed; mail, checkout and WordPress HTTP blocked. DNS/TLS pending. Credentials are root-only; no live source changed.')

if __name__=='__main__':
    try: main()
    except Exception as error:
        code=str(error) if isinstance(error,RuntimeError) and re.fullmatch('[a-z0-9_]+',str(error)) else type(error).__name__
        print('Provisioning stopped safely:',code,'Inspect the root-only job log; secrets are not printed.')
        raise SystemExit(1)
