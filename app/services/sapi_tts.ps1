param(
    [Parameter(Mandatory=$true)][string]$TextPath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][string]$Language,
    [ValidateRange(-3,3)][int]$Rate = 0
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice = $speaker.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Culture.Name -eq $Language
    } | Select-Object -First 1
    if (-not $voice) { throw "No local voice installed for $Language" }
    $speaker.SelectVoice($voice.VoiceInfo.Name)
    $speaker.Rate = $Rate
    $speaker.SetOutputToWaveFile($OutputPath)
    $speaker.Speak([IO.File]::ReadAllText($TextPath, [Text.Encoding]::UTF8))
} finally {
    $speaker.Dispose()
}
