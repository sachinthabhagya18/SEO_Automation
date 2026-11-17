$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$verificationId = [Guid]::NewGuid().ToString('N').Substring(0,12)
$verificationDb = "seo_restore_verify_$verificationId"
$containerDump = "/tmp/seo-restore-$verificationId.dump"
$createdVerificationDb = $false
if ($verificationDb -notmatch '^seo_restore_verify_[a-f0-9]{12}$') { throw 'Unsafe verification database name.' }
try {
    docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$1"' sh $containerDump
    if ($LASTEXITCODE -ne 0) { throw 'Source backup failed.' }
    docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh $verificationDb
    if ($LASTEXITCODE -ne 0) { throw 'Disposable verification database creation failed.' }
    $createdVerificationDb = $true
    docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error --no-owner "$2"' sh $verificationDb $containerDump
    if ($LASTEXITCODE -ne 0) { throw 'Restoration failed.' }
    $restoredCount = 'SELECT count(*) FROM django_migrations;' | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$1" -At' sh $verificationDb
    if ($LASTEXITCODE -ne 0 -or [int]$restoredCount -lt 1) { throw 'Restored schema validation failed.' }
    $sourceCount = 'SELECT count(*) FROM django_migrations;' | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At'
    if ($LASTEXITCODE -ne 0 -or $sourceCount -ne $restoredCount) { throw 'Source/restored migration counts differ.' }
    Write-Host "Backup restored to isolated temporary database; $restoredCount migration records matched. Source database unchanged."
} finally {
    # The only database dropped is this invocation's validated random disposable name.
    if ($createdVerificationDb) {
        docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$1"' sh $verificationDb
    }
    docker compose exec -T db rm -f $containerDump
}
