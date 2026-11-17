$ErrorActionPreference = 'Stop'
Write-Host "PowerShell $($PSVersionTable.PSVersion)"
Get-Command docker -ErrorAction Stop | Out-Null
docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is unavailable.' }
docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with Linux containers, wait for Engine running, then retry. No data has been removed.' }
Write-Host 'Docker engine is reachable.'
