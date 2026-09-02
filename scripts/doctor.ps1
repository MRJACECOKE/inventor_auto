<#
  doctor.ps1  -  one-shot environment check for inventor_auto.

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/doctor.ps1
    powershell ... -File scripts/doctor.ps1 -Quiet     # only the final line

  Checks, in order:
    1. Python           - found on PATH, version >= 3.9 (warns if != .python-version)
    2. Pinned deps      - PySide6 / PyInstaller import and match requirements-dev.txt
                          (INFO only - not needed for the pipeline or tests)
    3. Windows PS 5.1   - powershell.exe present and STA (required for Inventor COM)
    4. Inventor 2027    - runs scripts/detect_inventor.ps1 (INFO only - CI has no Inventor)

  Exit 0 if every REQUIRED check passes (1, 3). Exit 1 otherwise. Runs under
  pwsh 7 or Windows PowerShell 5.1.
#>
[CmdletBinding()]
param([switch] $Quiet)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$repo = Split-Path -Parent $PSScriptRoot
$fail = @()
$warn = @()

function Say($msg) { if (-not $Quiet) { Write-Host $msg } }
function Ok($msg)   { Say "  ok    $msg" }
function Warn($msg) { $script:warn += $msg; Say "  warn  $msg" }
function Bad($msg)  { $script:fail += $msg; Say "  FAIL  $msg" }

# --- 1. Python (REQUIRED) -------------------------------------------------- #
Say "`n[1] Python"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) {
    Bad "python not found on PATH"
} else {
    $ver = (& $py.Source -c "import platform;print(platform.python_version())" 2>$null)
    $parts = "$ver".Split('.')
    $maj = [int]$parts[0]; $min = [int]$parts[1]
    if ($maj -eq 3 -and $min -ge 9) { Ok "python $ver ($($py.Source))" }
    else { Bad "python $ver is below the required 3.9" }
    $pinFile = Join-Path $repo '.python-version'
    if (Test-Path $pinFile) {
        $pin = (Get-Content $pinFile -TotalCount 1).Trim()
        if ($pin -and $pin -ne $ver) { Warn "python $ver != .python-version ($pin) - fine for tests, match it for a byte-exact build" }
    }
}

# --- 2. Pinned build deps (INFO) ---------------------------------------- #
Say "`n[2] Build dependencies (optional - only for the .exe build)"
if ($py) {
    $reqFile = Join-Path $repo 'requirements-dev.txt'
    $pins = @{}
    if (Test-Path $reqFile) {
        foreach ($ln in Get-Content $reqFile) {
            if ($ln -match '^\s*([A-Za-z0-9_.-]+)\s*==\s*([0-9A-Za-z.+-]+)') { $pins[$Matches[1].ToLower()] = $Matches[2] }
        }
    }
    foreach ($mod in 'PySide6', 'PyInstaller') {
        $got = (& $py.Source -c "import $mod,sys; print(getattr($mod,'__version__','?'))" 2>$null)
        if (-not $got) { Warn "$mod not importable (run scripts/bootstrap.ps1 to install pinned deps)" ; continue }
        $want = $pins[$mod.ToLower()]
        if ($want -and $got -ne $want) { Warn "$mod $got installed, pinned $want" }
        else { Ok "$mod $got" }
    }
} else {
    Warn "skipped (no python)"
}

# --- 3. Windows PowerShell 5.1 / STA (REQUIRED for Inventor) ------------ #
Say "`n[3] Windows PowerShell 5.1 (STA) - required for Inventor COM steps"
$wps = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path $wps)) {
    Bad "powershell.exe (Windows PowerShell 5.1) not found at $wps"
} else {
    $probe = & $wps -NoProfile -NonInteractive -Command "Write-Output ([string]`$PSVersionTable.PSVersion.Major); Write-Output ([string][System.Threading.Thread]::CurrentThread.GetApartmentState())"
    $lines = @($probe | Where-Object { "$_".Trim() -ne '' } | ForEach-Object { "$_".Trim() })
    if ($lines.Count -ge 2 -and [int]$lines[0] -eq 5 -and $lines[1] -eq 'STA') { Ok "powershell.exe 5.x, STA" }
    else { Bad "powershell.exe reported '$($lines -join ',')' (need major 5, STA)" }
}

# --- 4. Inventor 2027 (INFO) ------------------------------------------- #
Say "`n[4] Autodesk Inventor 2027 (optional - not present in CI)"
$detect = Join-Path $PSScriptRoot 'detect_inventor.ps1'
if (Test-Path $detect) {
    $wpsForDetect = if (Test-Path $wps) { $wps } else { 'powershell.exe' }
    $out = & $wpsForDetect -NoProfile -ExecutionPolicy Bypass -File $detect 2>$null
    $json = $out | Select-Object -Last 1
    try {
        $d = $json | ConvertFrom-Json
        if ($d.usable) { Ok "Inventor 2027 usable ($($d.product_name) $($d.file_version))" }
        else { Warn "Inventor 2027 not usable here - photo-to-ipt build steps will be blocked (tests still run)" }
    } catch {
        Warn "detect_inventor.ps1 gave no parseable result - assume no Inventor"
    }
} else {
    Warn "scripts/detect_inventor.ps1 missing"
}

# --- verdict ---------------------------------------------------------- #
Say ""
if ($fail.Count -eq 0) {
    if ($warn.Count) { Write-Host "DOCTOR: PASS (with $($warn.Count) warning(s))" -ForegroundColor Yellow }
    else { Write-Host "DOCTOR: PASS" -ForegroundColor Green }
    exit 0
}
Write-Host "DOCTOR: FAIL -> $($fail -join '; ')" -ForegroundColor Red
exit 1
