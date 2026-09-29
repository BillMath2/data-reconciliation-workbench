# Create a dedicated Compose environment without reading or replacing the existing .env.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $projectRoot '.env.workbench'
if (Test-Path -LiteralPath $target) {
    Write-Output '.env.workbench already exists; left unchanged.'
    exit 0
}
$bytes = New-Object byte[] 24
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $random.GetBytes($bytes)
} finally {
    $random.Dispose()
}
$demoPassword = 'Wb1!' + [Convert]::ToBase64String($bytes)
$template = [System.IO.File]::ReadAllText((Join-Path $projectRoot '.env.example'))
$content = $template.Replace('WB_SQL_PASSWORD=', ('WB_SQL_PASSWORD=' + $demoPassword))
# CreateNew prevents an accidental overwrite if another process creates the file.
$stream = [System.IO.File]::Open($target, [System.IO.FileMode]::CreateNew)
$writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
try {
    $writer.Write($content)
} finally {
    $writer.Dispose()
}
Write-Output 'Created .env.workbench with a generated demo credential. Its contents are not printed.'
