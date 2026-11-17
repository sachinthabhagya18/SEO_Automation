param([string]$Destination = 'backups')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
# Copy binary dumps directly; Windows PowerShell redirection can corrupt binary streams.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/seo-backup.dump'
if ($LASTEXITCODE -ne 0) { throw 'Backup failed.' }
docker compose cp db:/tmp/seo-backup.dump "$Destination/seo-$stamp.dump"
if ($LASTEXITCODE -ne 0) { throw 'Backup copy failed.' }
docker compose exec -T db rm -f /tmp/seo-backup.dump
Write-Host "Database dump saved in $Destination. Back up uploads and encrypted configuration separately."
