<#
  run_ci.ps1  -  non-Inventor CI for inventor_auto.

    powershell -NoProfile -ExecutionPolicy Bypass -File ci/run_ci.ps1
    powershell ... -File ci/run_ci.ps1 -NoBuild        # skip the PyInstaller build step

  Runs everything that does NOT need Autodesk Inventor:
    1. python tests/run_tests.py             (unit tests incl. determinism, zero-dep)
    2. python scripts/regen_golden.py --check (committed cad-plan goldens still match)
    3. python tests/gui_smoke.py             (GUI logic, offscreen; needs PySide6)
    4. build/build.ps1 -SkipDeps             (PyInstaller --onedir)          [unless -NoBuild]
    5. frozen "Photo-to-IPT Builder.exe" --selftest   (import + bundle + validate + plan)

  The Inventor end-to-end checks (tests/integration_smoke.ps1,
  tests/test_inventor_env.ps1, --selftest-build) are intentionally NOT run here -
  they require Inventor 2027 and stay manual / on a lab machine.

  Exit 0 only if every step passes.
#>
[CmdletBinding()]
param([switch] $NoBuild)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = (Get-Command python -EA Stop).Source
$fail = @()

function Step($name, [scriptblock] $body) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    & $body
    if ($LASTEXITCODE -ne 0) { $script:fail += $name; Write-Host "  -> FAIL ($LASTEXITCODE)" -ForegroundColor Red }
    else { Write-Host "  -> ok" -ForegroundColor Green }
}

Step "pip install -r requirements-dev.txt" { & $py -m pip install --quiet -r (Join-Path $repo 'requirements-dev.txt') }
Step "python tests/run_tests.py"           { & $py (Join-Path $repo 'tests\run_tests.py') }
Step "python scripts/regen_golden.py --check" { & $py (Join-Path $repo 'scripts\regen_golden.py') --check }
Step "python tests/gui_smoke.py"           { & $py (Join-Path $repo 'tests\gui_smoke.py') }

if (-not $NoBuild) {
    Step "build/build.ps1 -SkipDeps" {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'build\build.ps1') -SkipDeps
    }
    Step "frozen exe --selftest" {
        $exe = Get-ChildItem -Recurse -Path (Join-Path $repo 'build\dist') -Filter 'Photo-to-IPT Builder.exe' -EA SilentlyContinue |
               Select-Object -First 1
        if (-not $exe) { Write-Host "  (no exe built)"; $global:LASTEXITCODE = 1; return }
        $env:QT_QPA_PLATFORM = 'offscreen'
        & $exe.FullName --selftest
    }
}

Write-Host ""
if ($fail.Count -eq 0) { Write-Host "CI: PASS" -ForegroundColor Green; exit 0 }
Write-Host "CI: FAIL -> $($fail -join '; ')" -ForegroundColor Red
exit 1
