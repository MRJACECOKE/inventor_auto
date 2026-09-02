<#
  verify_ipt.ps1  -  independent verification of a produced .ipt (docs/spec/07).

  Checks: file exists, .ipt extension, size > 0, opens as a PartDocument,
  >= 1 solid body, feature count sane, no unresolved feature health.

  Returns a hashtable (pass/summary/size/bodies/features/docType). Also prints
  VERIFY_PASS / VERIFY_FAIL and sets exit code when run standalone.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $IptPath,
    [int] $ExpectedFeatures = 0,
    $Existing = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$out = @{ pass = $false; summary = ''; size = 0; bodies = 0; features = 0; docType = 'n/a' }
$reasons = New-Object System.Collections.Generic.List[string]

if (-not (Test-Path -LiteralPath $IptPath)) {
    $out.summary = "file does not exist: $IptPath"
    Write-Host "VERIFY_FAIL $($out.summary)"; if (-not $Existing) { exit 1 } else { return $out }
}
$fi = Get-Item -LiteralPath $IptPath
$out.size = $fi.Length
if ($fi.Extension -ne '.ipt') { $reasons.Add("extension is '$($fi.Extension)', not .ipt") }
if ($fi.Length -le 0) { $reasons.Add("file size is 0 bytes") }

. "$PSScriptRoot/lib/inventor_env.ps1"
$dll = Get-InventorInteropDll
Add-Type -LiteralPath $dll -ErrorAction Stop

$app = $Existing
$startedApp = $false
if (-not $app) {
    try { $app = [Runtime.InteropServices.Marshal]::GetActiveObject('Inventor.Application') }
    catch { $app = New-Object -ComObject 'Inventor.Application'; $startedApp = $true }
}

$doc = $null
try {
    $doc = $app.Documents.Open($IptPath, $false)
    $dt = $doc.DocumentType
    if ($dt -eq [Inventor.DocumentTypeEnum]::kPartDocumentObject) { $out.docType = 'kPartDocumentObject' }
    else { $out.docType = [string]$dt; $reasons.Add("document type is $dt, not kPartDocumentObject") }

    $cd = $doc.ComponentDefinition
    $out.bodies = $cd.SurfaceBodies.Count
    $out.features = $cd.Features.Count
    if ($out.bodies -lt 1) { $reasons.Add("0 solid bodies") }
    if ($ExpectedFeatures -gt 0 -and $out.features -lt $ExpectedFeatures) {
        $reasons.Add("modeled feature count $($out.features) < expected $ExpectedFeatures")
    }
    $bad = 0
    foreach ($f in $cd.Features) {
        try { $h = $f.HealthStatus
              if ($h -ne [Inventor.HealthStatusEnum]::kUpToDateHealth -and
                  $h -ne [Inventor.HealthStatusEnum]::kUpToDateExceptEditHealth) { $bad++ } } catch { }
    }
    if ($bad -gt 0) { $reasons.Add("$bad feature(s) with unhealthy status") }

    $doc.Close($false)
}
catch {
    $reasons.Add("reopen/inspect threw: $($_.Exception.Message)")
    if ($doc) { try { $doc.Close($false) } catch { } }
}
finally {
    if ($startedApp) { try { $app.Quit() } catch { } }
}

$out.pass = ($reasons.Count -eq 0)
$out.summary = if ($out.pass) {
    "exists, $($out.size) bytes, $($out.docType), $($out.bodies) body/bodies, $($out.features) features"
} else { $reasons -join '; ' }

if ($out.pass) { Write-Host "VERIFY_PASS $($out.summary)" } else { Write-Host "VERIFY_FAIL $($out.summary)" }

if ($Existing) { return $out }
if ($out.pass) { exit 0 } else { exit 1 }
