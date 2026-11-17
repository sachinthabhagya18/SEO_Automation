param([int]$SiteId = 1)
$ErrorActionPreference = 'Stop'
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
Set-Location (Split-Path $PSScriptRoot -Parent)
$bindings=Get-Content -Raw -Encoding UTF8 automation/n8n/.local-bindings.json | ConvertFrom-Json
if ($bindings.site_id -ne $SiteId) { throw 'Run setup-n8n-audit.ps1 for this site first.' }
$ownerId=('SELECT id FROM public."user" WHERE "roleSlug" = ''global:owner'' LIMIT 1;' | docker compose exec -T n8n-db psql -U n8n -d n8n -At).Trim()
if ($LASTEXITCODE -ne 0 -or -not $ownerId) { throw 'Local n8n owner unavailable.' }
$workflow=Get-Content -Raw -Encoding UTF8 automation/n8n/scheduled_audit.json | ConvertFrom-Json
$workflow | Add-Member -NotePropertyName id -NotePropertyValue $bindings.workflows.scheduled_audit -Force
foreach ($node in $workflow.nodes) {
    if ($node.type -in @('n8n-nodes-base.httpRequest','n8n-nodes-base.webhook')) {
        $node | Add-Member -NotePropertyName credentials -NotePropertyValue @{httpHeaderAuth=@{id=$bindings.credential_id;name="SEO read-only audit site $SiteId"}} -Force
    }
}
$workflow | ConvertTo-Json -Depth 50 | docker compose exec -T n8n node /tmp/seo-import.mjs workflow $ownerId
if ($LASTEXITCODE -ne 0) { throw 'Schedule workflow import failed.' }
docker compose exec -T n8n n8n publish:workflow --id $bindings.workflows.scheduled_audit
if ($LASTEXITCODE -ne 0) { throw 'Schedule publication failed.' }
docker compose restart n8n | Out-Null
docker compose up -d --wait n8n | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'n8n readiness failed.' }
$marker=[DateTime]::UtcNow.ToString('o')
docker compose exec -T web python manage.py configure_audit_schedule --site $SiteId --interval-minutes 1440
if ($LASTEXITCODE -ne 0) { throw 'Read-only audit schedule configuration failed.' }
Write-Host 'Waiting for a real Schedule Trigger tick and its worker result (maximum 90 seconds).'
docker compose exec -T web python manage.py wait_for_audit_schedule --site $SiteId --after $marker
if ($LASTEXITCODE -ne 0) { throw 'Schedule/worker verification did not succeed.' }
