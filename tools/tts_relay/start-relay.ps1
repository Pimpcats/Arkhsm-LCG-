# THE STILL HOUR - start the TTS relay (Windows PowerShell 5.1+ or PowerShell 7).
#
# One line, from any local PowerShell window (no checkout needed):
#   irm https://raw.githubusercontent.com/Pimpcats/Arkhsm-LCG-/main/tools/tts_relay/start-relay.ps1 | iex
#
# Downloads the current relay.py into %USERPROFILE%\StillHourRelay each start
# (so a restart always runs the latest relay), makes sure Pillow is present
# for screenshots, then runs the relay until you press Ctrl+C.

$ErrorActionPreference = 'Continue'   # 'Stop' turns a native command's stderr into a fatal error in PS 5.1
$Branch = 'main'
$Raw = "https://raw.githubusercontent.com/Pimpcats/Arkhsm-LCG-/$Branch/tools/tts_relay/relay.py"
$Dir = Join-Path $env:USERPROFILE 'StillHourRelay'
New-Item -ItemType Directory -Force -Path $Dir | Out-Null

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host 'Git is not installed. Install it from https://git-scm.com, then run this line again.' -ForegroundColor Red
    return
}

$Py = $null
foreach ($c in @('py', 'python', 'python3')) {
    if (Get-Command $c -ErrorAction SilentlyContinue) {
        & $c -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Py = $c; break }
    }
}
if (-not $Py) {
    Write-Host 'Python 3.8+ was not found. Install it from python.org (tick "Add Python to PATH"), then run this line again.' -ForegroundColor Red
    return
}

& $Py -c "import PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing Pillow (needed for screenshots)...'
    & $Py -m pip install --quiet Pillow
}

$Relay = Join-Path $Dir 'relay.py'
$Stamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
try {
    Invoke-WebRequest -ErrorAction Stop -UseBasicParsing -Uri ("{0}?t={1}" -f $Raw, $Stamp) -OutFile $Relay
} catch {
    # the work branch is deleted once merged: fall back to main
    $Main = "https://raw.githubusercontent.com/Pimpcats/Arkhsm-LCG-/main/tools/tts_relay/relay.py"
    Invoke-WebRequest -ErrorAction Stop -UseBasicParsing -Uri ("{0}?t={1}" -f $Main, $Stamp) -OutFile $Relay
}
Write-Host "Relay downloaded to $Relay"
& $Py $Relay --branch $Branch @args
