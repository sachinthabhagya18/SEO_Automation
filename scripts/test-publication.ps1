$ErrorActionPreference = 'Stop'
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose -f compose.yaml -f compose.wordpress.yaml --profile wp-test up -d --build --wait metadata-test-worker
if ($LASTEXITCODE -ne 0) { throw 'Isolated metadata fixture worker failed to start.' }
docker compose -f compose.yaml -f compose.wordpress.yaml exec -T wordpress php /fixtures/test-metadata-changes.php
if ($LASTEXITCODE -ne 0) { throw 'WordPress ledger/restore checks failed.' }
$credentialJson=docker compose -f compose.yaml -f compose.wordpress.yaml exec -T wordpress php /fixtures/publication-credentials.php
if ($LASTEXITCODE -ne 0) { throw 'Temporary fixture writer creation failed.' }
try { $credential=($credentialJson -join "`n") | ConvertFrom-Json } catch { throw 'Fixture credential JSON invalid; values suppressed.' }
try {
    ($credentialJson -join "`n") | docker compose exec -T -e CONNECTOR_LOCAL_FIXTURE_ENABLED=true -e LOCAL_PUBLICATION_ENABLED=true web python manage.py publication_fixture_smoke
    if ($LASTEXITCODE -ne 0) { throw 'Local metadata publication smoke failed.' }
    ($credentialJson -join "`n") | docker compose exec -T -e CONNECTOR_LOCAL_FIXTURE_ENABLED=true -e LOCAL_PUBLICATION_ENABLED=true web python manage.py publication_queue_fixture_smoke
    if ($LASTEXITCODE -ne 0) { throw 'Queued local metadata publication smoke failed.' }
} finally {
    docker compose -f compose.yaml -f compose.wordpress.yaml exec -T wordpress php /fixtures/publication-credentials.php cleanup $credential.uuid
    $credentialJson=$null;$credential=$null
}
