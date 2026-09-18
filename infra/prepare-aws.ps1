[CmdletBinding()]
param(
  [string]$Profile = 'mogaesup',
  [string]$Region = 'ap-northeast-2',
  [string]$Bucket = 'gaesup-character-assets-960243570517-apne2',
  [switch]$Upload
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$artifactRoot = Join-Path $repo 'dist/aws'
New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null
function Invoke-Aws([string[]]$Arguments) {
  $result = & aws @Arguments --profile $Profile --region $Region --cli-connect-timeout 5 --cli-read-timeout 20 --output json
  if ($LASTEXITCODE -ne 0) { throw 'AWS CLI request failed.' }
  return ($result | ConvertFrom-Json)
}
$identity = Invoke-Aws @('sts', 'get-caller-identity')
$location = Invoke-Aws @('s3api', 'get-bucket-location', '--bucket', $Bucket)
if ($location.LocationConstraint -ne $Region) { throw 'S3 bucket region mismatch.' }
$validation = Invoke-Aws @('cloudformation', 'validate-template', '--template-body', ('file://' + (Join-Path $PSScriptRoot 'ec2.yaml')))
$archive = Join-Path $artifactRoot 'studio.tar.gz'
Push-Location $repo
try {
  & tar -czf $archive --exclude='node_modules' --exclude='__pycache__' --exclude='*.egg-info' --exclude='build' --exclude='dist' --exclude='test-results' --exclude='playwright-report' --exclude='.env*' backend/src backend/assets backend/pyproject.toml backend/main.py backend/README.md frontend/src frontend/public frontend/index.html frontend/avatar.html frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts pyproject.toml uv.lock infra .dockerignore
  if ($LASTEXITCODE -ne 0) { throw 'Release archive failed.' }
} finally { Pop-Location }
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
$key = 'releases/studio/' + $hash + '.tar.gz'
if ($Upload) {
  & aws s3 cp $archive "s3://$Bucket/$key" --profile $Profile --region $Region --only-show-errors
  if ($LASTEXITCODE -ne 0) { throw 'S3 release upload failed.' }
}
$receipt = [ordered]@{account=$identity.Account; region=$Region; bucket=$Bucket; release_key=$key; sha256=$hash; uploaded=[bool]$Upload; template_validated=$true; ec2_created=$false; created_at=(Get-Date).ToUniversalTime().ToString('o')}
$receipt | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $artifactRoot 'receipt.json')
$receipt | ConvertTo-Json
