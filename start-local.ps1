[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$ApiPort = 8016,
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
if (-not $PSBoundParameters.ContainsKey('ApiPort')) {
    $savedEnvPath = Join-Path $projectRoot '.env.local'
    if (Test-Path -LiteralPath $savedEnvPath) {
        $savedEnv = [IO.File]::ReadAllText($savedEnvPath)
        $savedPort = [regex]::Match($savedEnv, '(?m)^LOCAL_BACKEND_URL=http://127\.0\.0\.1:([0-9]{4,5})\s*$')
        if ($savedPort.Success) {
            $chosenPort = [int]$savedPort.Groups[1].Value
            if ($chosenPort -ge 1024 -and $chosenPort -le 65535) { $ApiPort = $chosenPort }
        }
    }
}
if ($ApiPort -eq $UiPort) { throw 'API and UI ports must be different.' }
$uiUrl = "http://127.0.0.1:$UiPort"
$runtimeRoot = Join-Path $projectRoot 'data\local-runtime'
$logRoot = Join-Path $runtimeRoot ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
Push-Location $projectRoot
try {
    $identityJson = & $uvPath run python -m src.runtime_identity
    if ($LASTEXITCODE -ne 0) { throw 'Could not identify the workspace API code.' }
    $expectedRuntime = $identityJson | ConvertFrom-Json
} finally { Pop-Location }

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

# Reuse only this workspace's current code. Preserve unidentified or older processes.
while (Test-PortListening $ApiPort) {
    $existing = $null
    try { $existing = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 3 } catch {}
    if ($existing.runtime.workspace -eq $expectedRuntime.workspace -and
        $existing.runtime.revision -eq $expectedRuntime.revision) { break }
    $ownerIds = (Get-NetTCPConnection -State Listen -LocalPort $ApiPort).OwningProcess | Sort-Object -Unique
    Write-Host "Preserving API port $ApiPort (PID $($ownerIds -join ',')). Selecting an available port."
    do { $ApiPort++ } while ($ApiPort -eq $UiPort)
    if ($ApiPort -gt 65535) { throw 'No available API port.' }
}
$apiUrl = "http://127.0.0.1:$ApiPort"
$apiProcess = $null
if (-not (Test-PortListening $ApiPort)) {
    $apiProcess = Start-Process -FilePath $uvPath -ArgumentList @(
        'run', 'python', '-m', 'uvicorn', 'src.api.server:app',
        '--host', '127.0.0.1', '--port', "$ApiPort"
    ) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logRoot 'api.stdout.log') `
        -RedirectStandardError (Join-Path $logRoot 'api.stderr.log')
}
$launchReceipt = @{ UI = "$uiUrl/"; API = $apiUrl; Logs = $logRoot; Phase = 'starting';
    LauncherPid = if ($apiProcess) { $apiProcess.Id } else { $null };
    Revision = $expectedRuntime.revision; StartedAt = (Get-Date).ToUniversalTime().ToString('o') }
$receiptPath = Join-Path $runtimeRoot 'current.json'
$launchReceipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Host "API $apiUrl; startup receipt: $receiptPath"
$apiResponse = Wait-LocalHttp "$apiUrl/health"
$health = $apiResponse.Content | ConvertFrom-Json
if ($health.runtime.workspace -ne $expectedRuntime.workspace -or $health.runtime.revision -ne $expectedRuntime.revision) {
    throw "Port $ApiPort is not serving the requested workspace revision. Existing UI routing is preserved."
}

# Hand an existing Vite process the chosen API without inheriting an old BACKEND_URL.
$localEnvPath = Join-Path $projectRoot '.env.local'
$localEnv = if (Test-Path -LiteralPath $localEnvPath) { [IO.File]::ReadAllText($localEnvPath) } else { '' }
if ($localEnv -match '(?m)^LOCAL_BACKEND_URL=') {
    $localEnv = [regex]::Replace($localEnv, '(?m)^LOCAL_BACKEND_URL=[^\r\n]*', "LOCAL_BACKEND_URL=$apiUrl")
} else {
    $localEnv = $localEnv.TrimEnd() + "`nLOCAL_BACKEND_URL=$apiUrl`n"
}
[IO.File]::WriteAllText($localEnvPath, $localEnv, [Text.UTF8Encoding]::new($false))
(Get-Item -LiteralPath (Join-Path $frontendRoot 'vite.config.ts')).LastWriteTime = Get-Date

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
if ($uiResponse.Content -notmatch '/src/character-app\.tsx') {
    throw "Port $UiPort is serving an unexpected UI. Select a different -UiPort."
}
$capabilities = Invoke-RestMethod -Uri "$uiUrl/api/avatar-factory/capabilities" -TimeoutSec 15
if ($capabilities.image_provider -ne 'openai' -or 'weapon' -notin $capabilities.slots) {
    throw 'The UI proxy is not serving the Maple character factory. Check its BACKEND_URL.'
}
if ($capabilities.character_pipeline -ne 'parts_to_character_v2') {
    throw 'The UI is connected to an older backend. Restart the workspace API and check BACKEND_URL.'
}
$proxiedHealth = Invoke-RestMethod -Uri "$uiUrl/api/health" -TimeoutSec 5
if ($proxiedHealth.runtime.revision -ne $expectedRuntime.revision -or $proxiedHealth.runtime.pid -ne $health.runtime.pid) {
    throw 'The UI proxy has not picked up the current API revision.'
}
$launchReceipt.Phase = 'ready'
$launchReceipt.ApiPid = $health.runtime.pid
$launchReceipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
if ($health.status -eq 'degraded') {
    Write-Warning 'The configured PostgreSQL connection is unavailable. Factory readiness is reported separately.'
}
[pscustomobject]@{
    UI = "$uiUrl/"
    API = $apiUrl
    ImageModel = $capabilities.image_model
    FactoryReady = $capabilities.ready
    Health = $health.status
    Logs = $logRoot
}
