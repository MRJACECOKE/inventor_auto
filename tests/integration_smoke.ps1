<#
  integration_smoke.ps1  -  Inventor-present end-to-end test on the synthetic
  simple_plate fixture (docs/spec/07). Requires Autodesk Inventor 2027.

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/integration_smoke.ps1 [-Clean] [-KeepOpen]

  Artifacts under output/simple_plate/ (including simple_plate.ipt) are KEPT by
  default so you can open the built part. Pass -Clean to delete them afterward
  (use that in CI). -KeepArtifacts is still accepted as a no-op for back-compat.

  Prints INTEGRATION: PASS  or  INTEGRATION: FAIL <step>. Exit code matches.
#>
[CmdletBinding()]
param([switch] $Clean, [switch] $KeepArtifacts, [switch] $KeepOpen)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$fix = Join-Path $repo 'tests/fixtures/simple_plate'
$meas = Join-Path $fix 'measurement-input.json'
$intent = Join-Path $fix 'feature-intent.json'
$outDir = Join-Path $repo 'output/simple_plate'
$ipt = Join-Path $outDir 'simple_plate.ipt'

function Fail($step) { Write-Host "INTEGRATION: FAIL $step"; exit 1 }

Write-Host "== step 1: detect Inventor 2027 =="
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'scripts/detect_inventor.ps1') | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "1-detect (Inventor 2027 not usable)" }

Write-Host "== step 2: validate + plan (python) =="
& python (Join-Path $repo 'scripts/validate_measurements.py') $meas --report (Join-Path $outDir 'validation-report.json') | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "2-validate" }
& python (Join-Path $repo 'scripts/plan_cad.py') --measurements $meas --intent $intent --out-dir $outDir | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "2-plan" }
if (-not (Test-Path (Join-Path $outDir 'cad-plan.json'))) { Fail "2-plan (no cad-plan.json)" }

Write-Host "== step 3: build in Inventor =="
$buildArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
               (Join-Path $repo 'scripts/inventor_build.ps1'),
               '-PlanPath', (Join-Path $outDir 'cad-plan.json'))
if ($KeepOpen) { $buildArgs += '-KeepOpen' }
& powershell.exe @buildArgs | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "3-build" }

Write-Host "== step 4: .ipt on disk =="
if (-not (Test-Path -LiteralPath $ipt)) { Fail "4-ipt-missing" }
$size = (Get-Item -LiteralPath $ipt).Length
if ($size -le 0) { Fail "4-ipt-zero-bytes" }
Write-Host "   $ipt  ($size bytes)"

Write-Host "== step 5: independent verify (reopen) =="
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'scripts/verify_ipt.ps1') -IptPath $ipt -ExpectedFeatures 3 | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "5-verify" }

Write-Host "== step 6: report present =="
$report = Join-Path $outDir 'build-report.md'
if (-not (Test-Path $report)) { Fail "6-report-missing" }
if (-not (Select-String -Path $report -Pattern '^PASS$' -Quiet)) { Fail "6-report-not-pass" }

if ($Clean) {
    Write-Host "== step 7: cleanup (-Clean) =="
    Remove-Item -Recurse -Force -LiteralPath $outDir -ErrorAction SilentlyContinue
    Write-Host "   removed $outDir"
} else {
    Write-Host "== artifacts kept =="
    Write-Host "   built part : $ipt"
    Write-Host "   plan/report: $outDir"
}

Write-Host "INTEGRATION: PASS"
exit 0
