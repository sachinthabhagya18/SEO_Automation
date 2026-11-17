$ErrorActionPreference='Stop'
$OutputEncoding=New-Object System.Text.UTF8Encoding $false
Set-Location (Split-Path $PSScriptRoot -Parent)
$composeArgs=@('compose','-f','compose.yaml','-f','compose.wordpress.yaml')
docker @composeArgs cp infra/staging/cseo-staging-guard.php wordpress:/tmp/cseo-staging-guard.php
if ($LASTEXITCODE -ne 0) { throw 'Guard copy failed.' }
docker @composeArgs cp scripts/staging-sanitize.php wordpress:/tmp/staging-sanitize.php
if ($LASTEXITCODE -ne 0) { throw 'Sanitizer copy failed.' }
docker @composeArgs exec -T wordpress php /fixtures/test-staging-guard.php
if ($LASTEXITCODE -ne 0) { throw 'Staging guard checks failed.' }
$taskOriginalPreference=$ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    $refusal=docker @composeArgs exec -T wordpress php /tmp/staging-sanitize.php /var/www/html 2>&1
    $taskRefusalExit=$LASTEXITCODE
} finally { $ErrorActionPreference=$taskOriginalPreference }
if ($taskRefusalExit -ne 2) { throw 'Sanitizer did not refuse the original fixture identity.' }
Write-Host 'Original database identity refused before sanitization, as required.'
$passwordBytes=New-Object byte[] 24
$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
try {$rng.GetBytes($passwordBytes)} finally {$rng.Dispose()}
$taskPassword=([BitConverter]::ToString($passwordBytes)).Replace('-','').ToLowerInvariant()
$inspect="SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='denimstage'; SELECT COUNT(*) FROM mysql.user WHERE User='denimstage';"
$existing=$inspect | docker @composeArgs exec -T wp-db sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot -N'
if ($LASTEXITCODE -ne 0 -or (($existing -join '').Trim() -ne '00')) { throw 'Disposable target already exists or inspection failed; no reset attempted.' }
$created=$false
try {
    $sql="CREATE DATABASE denimstage; CREATE USER 'denimstage'@'%' IDENTIFIED BY '$taskPassword'; GRANT ALL ON denimstage.* TO 'denimstage'@'%';"
    $setupOutput=$sql | docker @composeArgs exec -T wp-db sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot' 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Disposable database creation failed; details suppressed.' }
    $created=$true
    docker @composeArgs exec -T wp-db sh -c 'export MYSQL_PWD="$MARIADB_ROOT_PASSWORD"; mariadb-dump -uroot --single-transaction --skip-triggers wordpress_fixture | mariadb -uroot denimstage'
    if ($LASTEXITCODE -ne 0) { throw 'Disposable fixture clone failed.' }
    @{password=$taskPassword} | ConvertTo-Json -Compress | docker @composeArgs exec -T wordpress php /fixtures/test-staging-sanitizer.php
    if ($LASTEXITCODE -ne 0) { throw 'Staging sanitization checks failed.' }
} finally {
    if ($created) {
        "DROP DATABASE denimstage; DROP USER 'denimstage'@'%';" | docker @composeArgs exec -T wp-db sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot'
        if ($LASTEXITCODE -ne 0) { throw 'Disposable staging cleanup failed.' }
    }
    $taskPassword=$null;$sql=$null;$setupOutput=$null
}
Write-Host 'Only disposable local fixture data changed; no VPS or live site touched.'
