# Optional Windows-only production tool; no cloud speech service or cloned voice.
param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$target = [System.IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $target) { throw 'Use a new narration directory.' }
[System.IO.Directory]::CreateDirectory($target) | Out-Null
$source = Get-Content -Raw -Encoding utf8 (Join-Path $PSScriptRoot '../docs/release-narration.json') | ConvertFrom-Json
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $speaker.SelectVoice('Microsoft David Desktop')
    $speaker.Rate = 2
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    foreach ($chapter in $source.chapters) {
        $sentences = [regex]::Split($chapter.text, '(?<=[.!?])\s+')
        for ($i=0; $i -lt $sentences.Length; $i++) {
            $path = Join-Path $target ($chapter.id + '-' + $i + '.wav')
            $speaker.SetOutputToWaveFile($path, $format)
            $speaker.Speak($sentences[$i])
            $speaker.SetOutputToNull()
        }
    }
} finally { $speaker.Dispose() }
Write-Output 'Synthetic narration created locally; no voice cloning or provider call.'
