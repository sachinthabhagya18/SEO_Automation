$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.env')) { throw 'Run setup.ps1 to create .env first.' }
$envPath = Join-Path (Get-Location) '.env'
$environmentText = [IO.File]::ReadAllText($envPath)
if ($environmentText -notmatch '(?m)^CONNECTION_ENCRYPTION_KEYS=\S+') {
    $keyBytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($keyBytes) } finally { $rng.Dispose() }
    $keyValue = [Convert]::ToBase64String($keyBytes).Replace('+','-').Replace('/','_')
    if ($environmentText -match '(?m)^CONNECTION_ENCRYPTION_KEYS=.*$') {
        $environmentText = [regex]::Replace($environmentText, '(?m)^CONNECTION_ENCRYPTION_KEYS=.*$', "CONNECTION_ENCRYPTION_KEYS=$keyValue")
    } else { $environmentText += "`nCONNECTION_ENCRYPTION_KEYS=$keyValue`n" }
    [IO.File]::WriteAllText($envPath, $environmentText, (New-Object Text.UTF8Encoding $false))
    Write-Host 'Generated separate connection encryption key in .env; key value is not printed.'
} else { Write-Host 'Existing connection encryption key preserved.' }
