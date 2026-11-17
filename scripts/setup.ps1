$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.env')) {
    $contents = Get-Content -Raw -LiteralPath '.env.example'
    foreach ($key in @('DJANGO_SECRET_KEY', 'POSTGRES_PASSWORD', 'N8N_DB_PASSWORD', 'N8N_ENCRYPTION_KEY')) {
        $bytes = New-Object byte[] 48
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $secretValue = [Convert]::ToBase64String($bytes)
        $contents = [regex]::Replace($contents, "(?m)^${key}=.*$", "${key}=$secretValue")
    }
    [IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $contents, (New-Object Text.UTF8Encoding $false))
    Write-Host 'Generated local secrets in .env. Existing environments are never overwritten.'
}
& "$PSScriptRoot/ensure-encryption.ps1"
& "$PSScriptRoot/preflight.ps1"
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration failed.' }
docker compose up -d --build --wait
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Run docker compose ps and docker compose logs --tail 80 web migrate.' }
Write-Host 'Application: http://localhost:8000 | n8n: http://localhost:5679'
Write-Host 'Next: docker compose exec web python manage.py bootstrap_owner --email you@example.com --company "Your company"'
