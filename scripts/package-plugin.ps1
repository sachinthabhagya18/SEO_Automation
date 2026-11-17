$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
Get-ChildItem -LiteralPath 'wordpress-plugin/company-seo-connector' -Filter '*.php' -Recurse | ForEach-Object {
    if (Get-Command php -ErrorAction SilentlyContinue) {
        php -l $_.FullName
    } else {
        $pluginMount = 'type=bind,source=' + (Join-Path (Get-Location) 'wordpress-plugin/company-seo-connector') + ',target=/plugin,readonly'
        docker run --rm --mount $pluginMount wordpress:7.1.4-php8.3-apache php -l ('/plugin/' + $_.Name)
    }
    if ($LASTEXITCODE -ne 0) { throw "PHP syntax failed: $($_.Name)" }
}
New-Item -ItemType Directory -Force -Path dist | Out-Null
$pluginHeader=Get-Content -Raw -LiteralPath 'wordpress-plugin/company-seo-connector/company-seo-connector.php'
$pluginVersion=[regex]::Match($pluginHeader,'Version: ([0-9.]+)').Groups[1].Value
if (-not $pluginVersion) { throw 'Plugin version missing.' }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$taskPluginRoot=(Get-Item -LiteralPath 'wordpress-plugin/company-seo-connector').FullName
$taskZipPath=Join-Path (Get-Location) "dist/company-seo-connector-$pluginVersion.zip"
$taskZipStream=[IO.File]::Open($taskZipPath,[IO.FileMode]::Create,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$taskArchive=New-Object IO.Compression.ZipArchive($taskZipStream,[IO.Compression.ZipArchiveMode]::Create,$false)
try {
    Get-ChildItem -LiteralPath $taskPluginRoot -File -Recurse | Sort-Object FullName | ForEach-Object {
        $taskRelative=$_.FullName.Substring($taskPluginRoot.Length+1).Replace('\','/')
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($taskArchive,$_.FullName,('company-seo-connector/'+$taskRelative),[IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally { $taskArchive.Dispose();$taskZipStream.Dispose() }
$zip = [IO.Compression.ZipFile]::OpenRead((Join-Path (Get-Location) "dist/company-seo-connector-$pluginVersion.zip"))
try {
    if ($zip.Entries | Where-Object { $_.FullName.Contains('\') -or -not $_.FullName.StartsWith('company-seo-connector/') }) { throw 'ZIP must use portable forward-slash paths.' }
    if (-not ($zip.Entries | Where-Object { $_.FullName -eq 'company-seo-connector/company-seo-connector.php' })) { throw 'ZIP root structure is invalid.' }
} finally { $zip.Dispose() }
Write-Host "Verified ZIP: dist/company-seo-connector-$pluginVersion.zip"
