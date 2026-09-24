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

# A Python counts only if it actually RUNS and reports 3.8+. An exit code alone
# is not enough: a broken `py` launcher (no Python behind it) or the Microsoft
# Store placeholder can return success while running nothing, and the relay
# then "stops" instantly with no output.
function Test-Python([string[]]$Cmd) {
    try {
        $exe = $Cmd[0]; $pre = @(); if ($Cmd.Count -gt 1) { $pre = $Cmd[1..($Cmd.Count - 1)] }
        $out = & $exe @pre -c "import sys; print('PYOK', sys.version_info[0], sys.version_info[1], sys.executable)" 2>$null
        $line = @($out | Where-Object { "$_" -like 'PYOK *' })[0]
        if (-not $line) { return $null }
        $f = "$line".Split(' ', 4)
        if ([int]$f[1] -gt 3 -or ([int]$f[1] -eq 3 -and [int]$f[2] -ge 8)) { return $f[3].Trim() }
    } catch { }
    return $null
}

function Find-Python {
    $cands = @(@('py', '-3'), @('python'), @('python3'))
    # python.org installs: <root>\Python3xx\python.exe (only roots that exist)
    foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $base) { continue }
        $root = if ($base -eq $env:LOCALAPPDATA) { Join-Path $base 'Programs\Python' } else { $base }
        if (-not (Test-Path -LiteralPath $root)) { continue }
        Get-ChildItem -LiteralPath $root -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending | ForEach-Object {
                $exe = Join-Path $_.FullName 'python.exe'
                if (Test-Path -LiteralPath $exe) { $cands += ,@($exe) }
            }
    }
    foreach ($c in $cands) {
        if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
        $exe = Test-Python $c
        if ($exe) { return $exe }
    }
    return $null
}

$Py = Find-Python
if (-not $Py -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host 'No working Python 3.8+ found. Installing Python 3.12 for your user account (winget)...' -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    $Py = Find-Python
}
if (-not $Py) {
    Write-Host 'No working Python 3.8+ was found. Install it from python.org (tick "Add Python to PATH"), then run this line again.' -ForegroundColor Red
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
$PyVer = (& $Py -c "import sys; print(sys.version.split()[0])" 2>$null)
Write-Host "Starting the relay with Python $PyVer ($Py). Leave this window open; Ctrl+C stops it."
# -u: unbuffered, so every line shows here as it happens
& $Py -u $Relay --branch $Branch @args
$Code = $LASTEXITCODE
Write-Host ""
Write-Host "The relay stopped (exit code $Code). Its log: $Dir\relay.log" -ForegroundColor Yellow
if ($Code -ne 0 -and $Code -ne $null) {
    Write-Host 'Send Claude a screenshot of this window, or the relay.log file.' -ForegroundColor Yellow
}
