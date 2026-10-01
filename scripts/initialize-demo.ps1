# Create/upgrade dedicated demo configuration; preserve existing nonempty credentials.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $projectRoot '.env.workbench'
$exists = Test-Path -LiteralPath $target
$content = if ($exists) {
    [System.IO.File]::ReadAllText($target)
} else {
    [System.IO.File]::ReadAllText((Join-Path $projectRoot '.env.example'))
}
$originalContent = $content
foreach ($key in @('WB_SQL_PASSWORD', 'WB_SQL_RUNTIME_PASSWORD', 'WB_DEMO_ANALYST_TOKEN', 'WB_DEMO_OPERATOR_TOKEN')) {
    $emptyPattern = '(?m)^' + $key + '=[ \t]*\r?$'
    if ($content -match ('(?m)^' + $key + '=') -and $content -notmatch $emptyPattern) {
        continue
    }
    $bytes = New-Object byte[] 24
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($bytes) } finally { $random.Dispose() }
    $line = $key + '=Wb1!' + [Convert]::ToBase64String($bytes)
    if ($content -match $emptyPattern) {
        $content = [regex]::Replace($content, $emptyPattern, $line)
    } else {
        $content = $content.TrimEnd() + "`n" + $line + "`n"
    }
}
# Upgrade only the exact P01 default; preserve a deliberately customized database name.
$content = [regex]::Replace($content, '(?m)^WB_SQL_DATABASE=master\r?$', 'WB_SQL_DATABASE=workbench')
if (-not $exists -or $content -ne $originalContent) {
    $mode = if ($exists) { [System.IO.FileMode]::Create } else { [System.IO.FileMode]::CreateNew }
    $stream = [System.IO.File]::Open($target, $mode)
    $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
    try { $writer.Write($content) } finally { $writer.Dispose() }
}
Write-Output 'Demo configuration is ready; existing nonempty credentials were preserved. Values are not printed.'
