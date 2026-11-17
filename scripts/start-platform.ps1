param([switch]$SkipBuild)
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$previousPreference=$ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    docker info --format '{{.ServerVersion}}' | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Start Docker Desktop, then run this helper again.'}
    $composeArgs=@('compose','--profile','staging-publish','up','-d','--wait')
    if(-not $SkipBuild){$composeArgs+='--build'}
    $composeArgs+=@('web','worker','n8n','staging-publisher')
    docker @composeArgs
    if($LASTEXITCODE -ne 0){throw 'Platform startup failed. Inspect the service health; no volumes were reset.'}
}finally{$ErrorActionPreference=$previousPreference}
Write-Host 'Workspace: http://localhost:8000/sites/1/'
Write-Host 'n8n: http://localhost:5679'
Write-Host 'Existing accounts, volumes and approvals preserved.'
exit 0
