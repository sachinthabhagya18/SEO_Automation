$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$credentialJson = docker compose -f compose.yaml -f compose.wordpress.yaml exec -T wordpress php /fixtures/connection-credentials.php
if ($LASTEXITCODE -ne 0) { throw 'Could not create temporary local fixture credential.' }
try { $fixtureCredential = ($credentialJson -join "`n") | ConvertFrom-Json } catch { throw 'Fixture credential response invalid; value suppressed.' }
try {
    ($credentialJson -join "`n") | docker compose exec -T -e CONNECTOR_LOCAL_FIXTURE_ENABLED=true web python manage.py connection_fixture_smoke
    if ($LASTEXITCODE -ne 0) { throw 'WordPress HTTP connection smoke failed.' }
} finally {
    docker compose -f compose.yaml -f compose.wordpress.yaml exec -T wordpress php /fixtures/connection-credentials.php cleanup $fixtureCredential.uuid
    $credentialJson = $null
    $fixtureCredential = $null
}
