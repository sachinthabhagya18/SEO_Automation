$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.env')) { throw 'Run setup.ps1 first.' }
$environmentText = [IO.File]::ReadAllText((Join-Path (Get-Location) '.env'))
foreach ($key in @('WP_DB_PASSWORD', 'WP_DB_ROOT_PASSWORD', 'WP_FIXTURE_ADMIN_PASSWORD')) {
    if ($environmentText -notmatch "(?m)^${key}=") {
        $secretBytes = New-Object byte[] 48
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($secretBytes) } finally { $rng.Dispose() }
        $environmentText += "`n${key}=$([Convert]::ToBase64String($secretBytes))`n"
    }
}
[IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $environmentText, (New-Object Text.UTF8Encoding $false))
docker compose -f compose.yaml -f compose.wordpress.yaml --profile wp-test up -d --wait wordpress
if ($LASTEXITCODE -ne 0) { throw 'WordPress fixture startup failed.' }
$installOutput = docker compose -f compose.yaml -f compose.wordpress.yaml exec -T wordpress php /fixtures/install.php
if ($LASTEXITCODE -ne 0 -or ($installOutput -join "`n") -notmatch 'Fixture installed') { throw 'WordPress fixture installation did not complete.' }
$installOutput | Write-Host
$testOutput = docker compose -f compose.yaml -f compose.wordpress.yaml exec -T wordpress php /fixtures/test-plugin.php
if ($LASTEXITCODE -ne 0 -or ($testOutput -join "`n") -notmatch 'WordPress plugin checks passed') { throw 'WordPress connector checks did not complete.' }
$testOutput | Write-Host
Write-Host 'Synthetic WordPress fixture: http://localhost:8081. This is not a customer website.'
