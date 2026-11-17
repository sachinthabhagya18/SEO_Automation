param([int]$SiteId=1,[switch]$TestAndEnable)
$ErrorActionPreference='Stop'
$OutputEncoding=New-Object System.Text.UTF8Encoding $false
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($SiteId -lt 1) { throw 'Invalid site.' }
$ownerId=('SELECT id FROM public."user" WHERE "roleSlug" = ''global:owner'' LIMIT 1;' | docker compose exec -T n8n-db psql -U n8n -d n8n -At)
if ($LASTEXITCODE -ne 0 -or -not $ownerId) { throw 'Complete local n8n owner setup first.' }
$ownerId=$ownerId.Trim()
$bindingsPath='automation/n8n/.local-research-bindings.json'
$binding=if(Test-Path -LiteralPath $bindingsPath){Get-Content -Raw -Encoding UTF8 -LiteralPath $bindingsPath | ConvertFrom-Json}else{$null}
$credentialId=if($binding -and $binding.site_id -eq $SiteId){$binding.credential_id}else{'sor-'+[Guid]::NewGuid().ToString('N')}
$workflowId=if($binding -and $binding.site_id -eq $SiteId){$binding.workflow_id}else{'sor'+[Guid]::NewGuid().ToString('N')}
$credentialName="SEO research drafts site $SiteId"
$tokenLines=docker compose exec -T web python manage.py issue_audit_service --site $SiteId --scope research_drafts
if ($LASTEXITCODE -ne 0) { throw 'Research credential issuance failed.' }
$serviceToken=($tokenLines | Select-Object -Last 1).Trim()
if ($serviceToken.Length -lt 32) { throw 'Invalid credential response; suppressed.' }
try {
    docker compose cp scripts/n8n-import.mjs n8n:/tmp/seo-import.mjs | Out-Null
    $credential=ConvertTo-Json -Depth 10 -InputObject @(@{id=$credentialId;name=$credentialName;type='httpHeaderAuth';data=@{name='Authorization';value="Bearer $serviceToken"}})
    $credential | docker compose exec -T n8n node /tmp/seo-import.mjs credentials $ownerId
    if ($LASTEXITCODE -ne 0) { throw 'Credential import failed.' }
    $workflow=Get-Content -Raw -Encoding UTF8 automation/n8n/research_drafts.json | ConvertFrom-Json
    $workflow | Add-Member -NotePropertyName id -NotePropertyValue $workflowId -Force
    foreach($node in $workflow.nodes){
        if($node.type -eq 'n8n-nodes-base.httpRequest' -or $node.type -eq 'n8n-nodes-base.webhook'){
            $node | Add-Member -NotePropertyName credentials -NotePropertyValue @{httpHeaderAuth=@{id=$credentialId;name=$credentialName}} -Force
        }
        if($node.name -eq 'Site parameters'){$node.parameters.assignments.assignments[0].value=$SiteId}
    }
    $workflow | ConvertTo-Json -Depth 50 | docker compose exec -T n8n node /tmp/seo-import.mjs workflow $ownerId
    if ($LASTEXITCODE -ne 0) { throw 'Research workflow import failed.' }
    @{site_id=$SiteId;credential_id=$credentialId;workflow_id=$workflowId} | ConvertTo-Json | Set-Content -LiteralPath $bindingsPath -Encoding UTF8
    Write-Host "Research workflow: http://localhost:5679/workflow/$workflowId"
    if($TestAndEnable){
        docker compose exec -T n8n n8n publish:workflow --id $workflowId
        if($LASTEXITCODE -ne 0){throw 'Research workflow publication failed.'}
        docker compose restart n8n | Out-Null
        docker compose up -d --wait n8n | Out-Null
        # Container readiness can precede webhook registration. A denied
        # unauthenticated request proves the protected route is installed.
        $registered=$false
        for($attempt=0;$attempt -lt 20;$attempt++){
            try {
                $null=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5679/webhook/company-seo-research-drafts' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 5
                throw 'Research webhook unexpectedly accepted an unauthenticated request.'
            }catch{
                if($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 403){$registered=$true;break}
            }
            Start-Sleep -Seconds 2
        }
        if(-not $registered){throw 'Protected research webhook registration did not become ready.'}
        try {
            $result=Invoke-RestMethod -Uri 'http://localhost:5679/webhook/company-seo-research-drafts' -Method Post -Headers @{Authorization="Bearer $serviceToken"} -ContentType 'application/json' -Body '{}' -TimeoutSec 450
            Write-Host ('Research execution: '+($result | ConvertTo-Json -Depth 6 -Compress))
            if($result.state -ne 'succeeded'){throw 'Research not complete.'}
        }catch{
            if($_.Exception.Response){Write-Host ('Webhook HTTP status: '+[int]$_.Exception.Response.StatusCode)}
            throw 'Research workflow test failed; inspect local result. Credentials suppressed.'
        }
    }
}finally{$serviceToken=$null;$credential=$null;$tokenLines=$null}
exit 0
