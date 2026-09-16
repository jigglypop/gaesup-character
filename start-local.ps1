[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$ApiPort = 8000,
    [ValidateRange(1024, 65535)][int]$UiPort = 5273
)

$ErrorActionPreference = 'Stop'
if ($ApiPort -eq $UiPort) { throw 'API and UI ports must be different.' }
$projectRoot = $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$vitePath = Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $vitePath)) {
    throw 'Frontend dependencies are missing. Run npm ci in frontend/ first.'
}
$uvPath = (Get-Command uv -ErrorAction Stop).Source
$nodePath = (Get-Command node -ErrorAction Stop).Source
$apiUrl = "http://127.0.0.1:$ApiPort"
$uiUrl = "http://127.0.0.1:$UiPort"
$logRoot = Join-Path $env:TEMP ('3d-esset-local\' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

function Test-PortListening([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Wait-LocalHttp([string]$Url) {
    $deadline = (Get-Date).AddSeconds(30)
    do {
        try { return Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3 }
        catch { Start-Sleep -Milliseconds 300 }
    } while ((Get-Date) -lt $deadline)
    throw "Local server did not respond: $Url. Check logs in $logRoot"
}

# Reuse listening servers. Never kill a process simply because it owns a port.
if (-not (Test-PortListening $ApiPort)) {
    $null = Start-Process -FilePath $uvPath -ArgumentList @(
        'run', 'python', '-m', 'uvicorn', 'src.api.server:app',
        '--host', '127.0.0.1', '--port', "$ApiPort"
    ) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logRoot 'api.stdout.log') `
        -RedirectStandardError (Join-Path $logRoot 'api.stderr.log')
}
$apiResponse = Wait-LocalHttp "$apiUrl/health"
$health = $apiResponse.Content | ConvertFrom-Json
if (-not $health.connections -or -not $health.connections.database) {
    throw "Port $ApiPort is serving an unexpected API. Select a different -ApiPort."
}

if (-not (Test-PortListening $UiPort)) {
    $previousBackend = $env:BACKEND_URL
    try {
        $env:BACKEND_URL = $apiUrl
        $null = Start-Process -FilePath $nodePath -ArgumentList @(
            ('"{0}"' -f $vitePath), '--host', '127.0.0.1', '--port', "$UiPort", '--strictPort'
        ) -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $logRoot 'ui.stdout.log') `
            -RedirectStandardError (Join-Path $logRoot 'ui.stderr.log')
    } finally { $env:BACKEND_URL = $previousBackend }
}
$uiResponse = Wait-LocalHttp "$uiUrl/avatar.html"
if ($uiResponse.Content -notmatch '/src/avatar-page\.tsx') {
    throw "Port $UiPort is serving an unexpected UI. Select a different -UiPort."
}
$capabilities = Invoke-RestMethod -Uri "$uiUrl/api/avatar-factory/capabilities" -TimeoutSec 15
if ($capabilities.image_provider -ne 'openai' -or 'weapon' -notin $capabilities.slots) {
    throw 'The UI proxy is not serving the Maple character factory. Check its BACKEND_URL.'
}
if ($health.status -eq 'degraded') {
    Write-Warning 'The configured PostgreSQL connection is unavailable. Factory readiness is reported separately.'
}
[pscustomobject]@{
    UI = "$uiUrl/avatar.html"
    API = $apiUrl
    ImageModel = $capabilities.image_model
    FactoryReady = $capabilities.ready
    Health = $health.status
    Logs = $logRoot
}
