param([int]$SiteId = 1, [switch]$TestAndEnable)
$ErrorActionPreference = 'Stop'
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($SiteId -lt 1) { throw 'Invalid site ID.' }
# Only a non-secret local owner ID is queried. User records/tokens are not exported.
$ownerId = ('SELECT id FROM public."user" WHERE "roleSlug" = ''global:owner'' LIMIT 1;' | docker compose exec -T n8n-db psql -U n8n -d n8n -At)
if ($LASTEXITCODE -ne 0 -or -not $ownerId) { throw 'Complete owner setup at http://localhost:5679 first.' }
$ownerId = $ownerId.Trim()
$bindingsPath = Join-Path (Get-Location) 'automation/n8n/.local-bindings.json'
$bindings = if (Test-Path -LiteralPath $bindingsPath) { Get-Content -Raw -Encoding UTF8 -LiteralPath $bindingsPath | ConvertFrom-Json } else { $null }
$credentialId = if ($bindings -and $bindings.site_id -eq $SiteId) { $bindings.credential_id } else { 'seo-' + [Guid]::NewGuid().ToString('N') }
$credentialName = "SEO read-only audit site $SiteId"
$tokenLines = docker compose exec -T web python manage.py issue_audit_service --site $SiteId
if ($LASTEXITCODE -ne 0) { throw 'Scoped audit credential issuance failed.' }
$serviceToken = ($tokenLines | Select-Object -Last 1).Trim()
if ($serviceToken.Length -lt 32) { throw 'Invalid service credential response; value suppressed.' }
docker compose cp scripts/n8n-import.mjs n8n:/tmp/seo-import.mjs | Out-Null
docker compose cp scripts/n8n-execute.mjs n8n:/tmp/seo-execute.mjs | Out-Null
$runtimeCredential = ConvertTo-Json -Depth 20 -InputObject @(@{id=$credentialId;name=$credentialName;type='httpHeaderAuth';data=@{name='Authorization';value="Bearer $serviceToken"}})
try {
    $runtimeCredential | docker compose exec -T n8n node /tmp/seo-import.mjs credentials $ownerId
    if ($LASTEXITCODE -ne 0) { throw 'Credential binding failed.' }
} finally { $tokenLines=$null; $runtimeCredential=$null }
$workflowBindings = @{}
foreach ($operation in @('onboarding_initial_audit','scheduled_audit')) {
    $workflow = Get-Content -Raw -Encoding UTF8 -LiteralPath "automation/n8n/$operation.json" | ConvertFrom-Json
    $savedId = if ($bindings -and $bindings.site_id -eq $SiteId) { $bindings.workflows.$operation } else { $null }
    $workflowId = if ($savedId) { $savedId } else { 'seo' + [Guid]::NewGuid().ToString('N') }
    $workflow | Add-Member -NotePropertyName id -NotePropertyValue $workflowId -Force
    foreach ($node in $workflow.nodes) {
        if ($node.type -eq 'n8n-nodes-base.httpRequest' -or $node.type -eq 'n8n-nodes-base.webhook') {
            $node | Add-Member -NotePropertyName credentials -NotePropertyValue @{httpHeaderAuth=@{id=$credentialId;name=$credentialName}} -Force
        }
        if ($node.name -eq 'Site parameters') { $node.parameters.assignments.assignments[0].value=$SiteId }
    }
    $workflow | ConvertTo-Json -Depth 50 | docker compose exec -T n8n node /tmp/seo-import.mjs workflow $ownerId
    if ($LASTEXITCODE -ne 0) { throw "Workflow import failed: $operation" }
    $workflowBindings[$operation] = $workflowId
}
@{site_id=$SiteId;credential_id=$credentialId;workflows=$workflowBindings} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $bindingsPath -Encoding UTF8
Write-Host 'Imported two audit workflows unpublished; secrets are stored only encrypted in n8n/app databases.'
Write-Host "Manual audit workflow: http://localhost:5679/workflow/$($workflowBindings['onboarding_initial_audit'])"
Write-Host "Scheduled audit workflow: http://localhost:5679/workflow/$($workflowBindings['scheduled_audit'])"
if ($TestAndEnable) {
    foreach ($workflowId in $workflowBindings.Values) {
        docker compose exec -T n8n n8n publish:workflow --id $workflowId
        if ($LASTEXITCODE -ne 0) { throw 'Audit workflow publication failed.' }
    }
    # Register only this project's authenticated, read-only audit webhooks/schedule.
    docker compose restart n8n | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'n8n restart failed.' }
    docker compose up -d --wait n8n | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'n8n readiness failed.' }
    try {
        $manualResult = Invoke-RestMethod -Uri 'http://localhost:5679/webhook/company-seo-initial-audit' -Method Post -Headers @{Authorization="Bearer $serviceToken"} -ContentType 'application/json' -Body '{}' -TimeoutSec 170
        Write-Host ('n8n initial audit response: ' + ($manualResult | ConvertTo-Json -Depth 6 -Compress))
        if ($manualResult.state -ne 'succeeded') { throw 'Live audit has not succeeded; inspect the job result before enabling further automation.' }
        docker compose exec -T web python manage.py configure_audit_schedule --site $SiteId --interval-minutes 1440
        if ($LASTEXITCODE -ne 0) { throw 'Audit due schedule configuration failed.' }
        $dueResult = Invoke-RestMethod -Uri 'http://localhost:5679/webhook/company-seo-due-audit' -Method Post -Headers @{Authorization="Bearer $serviceToken"} -ContentType 'application/json' -Body '{}' -TimeoutSec 30
        Write-Host ('n8n due dispatch response: ' + ($dueResult | ConvertTo-Json -Compress))
        Write-Host 'Authenticated n8n audit workflow executed. Daily read-only audit schedule is configured; publishing remains paused.'
    } catch {
        # Do not echo PowerShell web request exceptions that may include request headers.
        throw 'Authenticated n8n workflow test did not complete successfully. Inspect local job/workflow status; credentials suppressed.'
    } finally { $serviceToken=$null }
} else { $serviceToken=$null }
