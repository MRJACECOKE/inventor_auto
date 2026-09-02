<#
  run_ps_tests.ps1  -  runs the PowerShell test scripts and sums their results.

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/run_ps_tests.ps1

  Includes:
    test_inventor_env.ps1   (needs Inventor installed)
    integration_smoke.ps1   (needs Inventor; skip with -NoInventor)

  Exit 0 only if every included script exits 0.
#>
[CmdletBinding()]
param([switch] $NoInventor)

$here = $PSScriptRoot
$scripts = @('test_inventor_env.ps1')
if (-not $NoInventor) { $scripts += 'integration_smoke.ps1' }

$failed = @()
foreach ($s in $scripts) {
    Write-Host "`n=== $s ===" -ForegroundColor Cyan
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here $s)
    if ($LASTEXITCODE -ne 0) { $failed += "$s (exit $LASTEXITCODE)" }
}

Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "PS TESTS: PASS ($($scripts.Count) scripts)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "PS TESTS: FAIL -> $($failed -join '; ')" -ForegroundColor Red
    exit 1
}
