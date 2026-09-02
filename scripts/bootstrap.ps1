<#
  bootstrap.ps1  -  set up a fresh machine to build and test inventor_auto.

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
    powershell ... -File scripts/bootstrap.ps1 -NoDeps      # skip the pip install

  Steps:
    1. pip install the pinned build deps   (requirements-dev.lock.txt)  [unless -NoDeps]
    2. scripts/doctor.ps1                   (environment check)
    3. python tests/run_tests.py           (48 non-Inventor tests incl. determinism)
    4. python scripts/regen_golden.py --check   (goldens still match)

  Idempotent. Exit 0 only if doctor's required checks and every test pass.
  The Inventor end-to-end checks stay manual: tests/run_ps_tests.ps1.
#>
[CmdletBinding()]
param([switch] $NoDeps)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction Stop }
$fail = @()

function Step($name, [scriptblock] $body) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    & $body
    if ($LASTEXITCODE -ne 0) { $script:fail += $name; Write-Host "  -> FAIL ($LASTEXITCODE)" -ForegroundColor Red }
    else { Write-Host "  -> ok" -ForegroundColor Green }
}

if (-not $NoDeps) {
    Step "pip install -r requirements-dev.lock.txt" {
        & $py.Source -m pip install --disable-pip-version-check -r (Join-Path $repo 'requirements-dev.lock.txt')
    }
} else {
    Write-Host "skipping pip install (-NoDeps)" -ForegroundColor DarkGray
}

Step "scripts/doctor.ps1" {
    & (Join-Path $PSScriptRoot 'doctor.ps1')
}
Step "python tests/run_tests.py" {
    & $py.Source (Join-Path $repo 'tests\run_tests.py')
}
Step "python scripts/regen_golden.py --check" {
    & $py.Source (Join-Path $repo 'scripts\regen_golden.py') --check
}

Write-Host ""
if ($fail.Count -eq 0) { Write-Host "BOOTSTRAP: PASS" -ForegroundColor Green; exit 0 }
Write-Host "BOOTSTRAP: FAIL -> $($fail -join '; ')" -ForegroundColor Red
exit 1
