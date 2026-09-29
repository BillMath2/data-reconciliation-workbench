# Run the installed uv, or this workspace's ignored portable copy.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$UvArguments)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$portableUv = Join-Path $projectRoot '.tools\uv\uv.exe'
if (Test-Path -LiteralPath $portableUv) {
    $uvExecutable = $portableUv
} else {
    $uvExecutable = (Get-Command uv -ErrorAction Stop).Source
}
$env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.tools\python'
Push-Location -LiteralPath $projectRoot
try {
    & $uvExecutable @UvArguments
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
