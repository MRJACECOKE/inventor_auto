<#
  inventor_build.ps1  -  orchestrator: cad-plan.json  ->  parametric .ipt  ->  verify  ->  report

  Usage:
    pwsh -NoProfile -File scripts/inventor_build.ps1 -PlanPath output/<part>/cad-plan.json [-KeepOpen]

  Steps (docs/spec/06, 07): connect/launch Inventor 2027 -> new PartDocument ->
  create user parameters -> build sketches -> build features in plan order ->
  Update -> SaveAs -> verify on disk + reopen -> write build-report.md.

  MUST run under Windows PowerShell 5.1 (powershell.exe): it is STA and uses the
  .NET Framework interop. pwsh 7 is MTA and some Inventor COM calls (e.g.
  TransientObjects.CreateObjectCollection) silently return null there.

  Exit 0 = PASS (verified .ipt), non-zero = FAIL/BLOCKED (reason logged).
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $PlanPath,
    [string] $RepoRoot,
    [string] $OutDir,          # explicit output folder; default <RepoRoot>/output/<part>
    [switch] $KeepOpen
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -ge 6) {
    Write-Host "BLOCKED: run this under Windows PowerShell 5.1 (powershell.exe), not pwsh $($PSVersionTable.PSVersion). pwsh is MTA and breaks Inventor COM."
    exit 2
}
if ([System.Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') {
    Write-Host "BLOCKED: PowerShell apartment state is $([System.Threading.Thread]::CurrentThread.GetApartmentState()), need STA."
    exit 2
}

if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
. "$PSScriptRoot/lib/inventor_env.ps1"
. "$PSScriptRoot/lib/units.ps1"
. "$PSScriptRoot/lib/json.ps1"
. "$PSScriptRoot/lib/geometry.ps1"
. "$PSScriptRoot/lib/features.ps1"

# --- resolve output paths / logging ---------------------------------------- #
$PlanPath = (Resolve-Path -LiteralPath $PlanPath).Path
$plan = Read-CadPlan -Path $PlanPath
$safe = ($plan.part_name -replace '[^A-Za-z0-9_.-]', '_')
$outDir = if ($OutDir) { $OutDir } else { Join-Path $RepoRoot "output/$safe" }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outDir = (Resolve-Path -LiteralPath $outDir).Path
$logPath = Join-Path $outDir 'build-log.txt'
$iptPath = Join-Path $outDir "$safe.ipt"
Set-Content -LiteralPath $logPath -Value "" -Encoding UTF8

# --- build stamp (tool version / commit / interpreter / OS) --------------- #
function Get-BuildStamp {
    param([string] $Root)
    $toolVersion = 'unknown'
    $vf = Join-Path $Root 'VERSION'
    if (Test-Path $vf) { $toolVersion = (Get-Content $vf -TotalCount 1).Trim() }
    $commit = 'unknown'
    try {
        $c = & git -C $Root rev-parse --short HEAD 2>$null
        if ($LASTEXITCODE -eq 0 -and $c) {
            $commit = "$($c.Trim())"
            $dirty = & git -C $Root status --porcelain 2>$null
            if ($dirty) { $commit += '-dirty' }
        }
    } catch { }
    $pyVer = 'n/a'
    try {
        $pyCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pyCmd) { $pyVer = (& $pyCmd.Source -c "import platform;print(platform.python_version())" 2>$null).Trim() }
    } catch { }
    [ordered]@{
        tool_version = $toolVersion
        git_commit   = $commit
        python       = $pyVer
        powershell   = "$($PSVersionTable.PSVersion)"
        os           = "$([System.Environment]::OSVersion.VersionString)"
        built_utc    = (Get-Date).ToUniversalTime().ToString('u')
    }
}
$script:stamp = Get-BuildStamp -Root $RepoRoot
Add-Content -LiteralPath $logPath -Encoding UTF8 -Value (
    "[INFO] stamp: inventor_auto $($stamp.tool_version) | commit $($stamp.git_commit) | " +
    "python $($stamp.python) | PS $($stamp.powershell) | $($stamp.os)")

$script:warnings = New-Object System.Collections.Generic.List[string]
function Write-Log {
    param([string] $Level, [string] $Message)
    $line = "[{0}] {1}" -f $Level, $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    Write-Host $line
    if ($Level -eq 'WARN') { $script:warnings.Add($Message) }
}
function Warn { param([string] $m) Write-Log 'WARN' $m }

function Write-Report {
    param([string] $Result, [hashtable] $Facts)
    $ts = (Get-Date).ToString('u')
    $lines = @()
    $lines += "# CAD Build Report"
    $lines += ""
    $lines += "Part: $($plan.part_name)"
    $lines += "Inventor version: $($Facts.inventor)"
    $lines += "Build timestamp: $ts"
    $lines += ""
    $lines += "## Environment"
    $lines += "inventor_auto version: $($script:stamp.tool_version)"
    $lines += "git commit: $($script:stamp.git_commit)"
    $lines += "Python: $($script:stamp.python)"
    $lines += "PowerShell: $($script:stamp.powershell)"
    $lines += "OS: $($script:stamp.os)"
    $lines += "Built (UTC): $($script:stamp.built_utc)"
    $lines += ""
    $lines += "## Inputs"
    $lines += "CAD plan: $PlanPath"
    $lines += "Measurement JSON: $($plan.provenance.measurement_file)"
    $lines += "Measurement sha256: $($plan.provenance.measurement_sha256)"
    $lines += "Source images: $($plan.provenance.source_images -join ', ')"
    $lines += ""
    $lines += "## Validation"
    $lines += "Schema: $($Facts.schema)"
    $lines += "Geometry: $($Facts.geometry)"
    $lines += ""
    $lines += "## Parameters"
    foreach ($p in $plan.parameters.PSObject.Properties) {
        $src = if ($p.Value.PSObject.Properties.Name.Contains('measurement_id')) { $p.Value.measurement_id } else { 'derived' }
        $lines += ("{0} -> p_{1} = {2} {3}" -f $src, $p.Name, $p.Value.value, $p.Value.unit)
    }
    $lines += ""
    $lines += "## Features"
    foreach ($f in $plan.features) {
        $lines += ("{0}  {1}  (after: {2})" -f $f.id, $f.type, (($f.depends_on) -join ','))
    }
    $lines += ""
    $lines += "## Inventor Result"
    $lines += "Document type: $($Facts.docType)"
    $lines += "Solid bodies: $($Facts.bodies)"
    $lines += "Features (modeled): $($Facts.featureCount)"
    $lines += "Save path: $iptPath"
    $lines += "File size: $($Facts.size) bytes"
    $lines += "Update errors: $($Facts.updateErrors)"
    $lines += ""
    $lines += "## Warnings"
    if ($script:warnings.Count) { $script:warnings | ForEach-Object { $lines += "- $_" } } else { $lines += "- none" }
    $lines += ""
    $lines += "## Result"
    $lines += $Result
    Set-Content -LiteralPath (Join-Path $outDir 'build-report.md') -Value ($lines -join "`n") -Encoding UTF8
}

# --------------------------------------------------------------------------- #
$facts = @{ inventor = 'n/a'; schema = 'passed (see validation-report.json)'; geometry = 'passed';
           docType = 'n/a'; bodies = 0; featureCount = 0; size = 0; updateErrors = 'n/a' }
$launchedByUs = $false
$app = $null
$doc = $null

try {
    Write-Log 'INFO' "Plan loaded: $($plan.part_name)  ($($plan.parameters.PSObject.Properties.Name.Count) params, $($plan.features.Count) features)"

    $dll = Get-InventorInteropDll
    Add-Type -LiteralPath $dll -ErrorAction Stop
    Write-Log 'INFO' "Interop assembly loaded: $dll"

    try {
        $app = [Runtime.InteropServices.Marshal]::GetActiveObject('Inventor.Application')
        Write-Log 'INFO' "Attached to a running Inventor instance"
    } catch {
        Write-Log 'INFO' "No running Inventor; launching via COM ProgID Inventor.Application"
        $app = New-Object -ComObject 'Inventor.Application'
        $launchedByUs = $true
    }
    $app.Visible = $true
    $sv = $app.SoftwareVersion
    $facts.inventor = "$($sv.DisplayName) (build $($sv.Major).$($sv.Minor))"
    Write-Log 'INFO' "Inventor.Application connected: $($facts.inventor)"
    if ($sv.Major -lt 31) { throw "BLOCKED: connected Inventor major version $($sv.Major) is not 2027 (expected 31)" }

    $tmpl = $app.FileManager.GetTemplateFile([Inventor.DocumentTypeEnum]::kPartDocumentObject)
    $doc = $app.Documents.Add([Inventor.DocumentTypeEnum]::kPartDocumentObject, $tmpl, $true)
    $cd = $doc.ComponentDefinition
    Write-Log 'INFO' "Created PartDocument from template $tmpl"

    # user parameters
    foreach ($pp in $plan.parameters.PSObject.Properties) {
        $null = Add-UserParameter -ComponentDefinition $cd -Key $pp.Name -Value ([double]$pp.Value.value) -Unit ([string]$pp.Value.unit)
    }
    Write-Log 'INFO' "$($plan.parameters.PSObject.Properties.Name.Count) user parameters created"

    $ctx = @{ App = $app; Doc = $doc; Cd = $cd; Plan = $plan
              Sketches = @{}; Features = @{}; Warn = { param($m) Warn $m } }

    # sketches
    foreach ($s in $plan.sketches) {
        $basePlane = Get-WorkPlane $cd $s.plane
        $offParam = _prop $s 'offset_param'
        $planeDesc = $s.plane
        if ($offParam) {
            $null = Get-PlanParameter $plan $offParam   # must be a declared parameter
            $offDir = _prop $s 'offset' 'positive'
            $sign = if ($offDir -eq 'negative') { '-' } else { '' }
            $offExpr = "${sign}p_${offParam}"
            try {
                $wpo = $cd.WorkPlanes.AddByPlaneAndOffset($basePlane, $offExpr)
            } catch {
                $op = Get-PlanParameter $plan $offParam
                $ov = (Get-InternalValue -Document $doc -Value ([double]$op.value) -Unit ([string]$op.unit))
                if ($offDir -eq 'negative') { $ov = -$ov }
                Warn "Sketch $($s.id): parametric offset '$offExpr' rejected, using fixed offset $ov cm: $($_.Exception.Message)"
                $wpo = $cd.WorkPlanes.AddByPlaneAndOffset($basePlane, $ov)
            }
            try { $wpo.Visible = $false } catch { }
            $plane = $wpo
            $planeDesc = "$($s.plane)+offset($offExpr)"
        } else {
            $plane = $basePlane
        }
        $sk = $cd.Sketches.Add($plane)
        $prof = $null
        switch ($s.profile.type) {
            'rectangle' {
                $wp = Get-PlanParameter $plan $s.profile.width_param
                $hp = Get-PlanParameter $plan $s.profile.height_param
                $wv = (Get-InternalValue -Document $doc -Value ([double]$wp.value) -Unit ([string]$wp.unit))
                $hv = (Get-InternalValue -Document $doc -Value ([double]$hp.value) -Unit ([string]$hp.unit))
                Add-RectangleGeometry -App $app -ComponentDefinition $cd -Sketch $sk `
                          -WidthVal $wv -HeightVal $hv `
                          -WidthParam ("p_" + $s.profile.width_param) -HeightParam ("p_" + $s.profile.height_param) `
                          -Corner (_prop $s.profile 'corner' 'origin') `
                          -Warn { param($m) Warn $m }
                $prof = $sk.Profiles.AddForSolid()
            }
            'circle' {
                $dp = Get-PlanParameter $plan $s.profile.diameter_param
                $rv = (Get-InternalValue -Document $doc -Value ([double]$dp.value / 2) -Unit ([string]$dp.unit))
                $null = $sk.SketchCircles.AddByCenterRadius((New-P2d $app 0 0), $rv)
                $prof = $sk.Profiles.AddForSolid()
            }
            'polygon' {
                $sidesN = [int]$s.profile.sides
                $cdp = $s.profile.circumdiameter_param
                $cdpar = Get-PlanParameter $plan $cdp
                $rv = (Get-InternalValue -Document $doc -Value ([double]$cdpar.value / 2) -Unit ([string]$cdpar.unit))
                $clockDeg = 0.0
                $clockParam = _prop $s.profile 'clocking_param'
                if ($clockParam) {
                    $cparv = Get-PlanParameter $plan $clockParam
                    $clockDeg = [double]$cparv.value
                }
                Add-PolygonGeometry -App $app -ComponentDefinition $cd -Sketch $sk `
                          -Sides $sidesN -CircumRadiusVal $rv -ClockingDeg $clockDeg `
                          -CircumParam ("p_" + $cdp) -Warn { param($m) Warn $m }
                $prof = $sk.Profiles.AddForSolid()
            }
            default { throw "sketch profile type '$($s.profile.type)' is not supported in v1" }
        }
        $ctx.Sketches[$s.id] = @{ Sketch = $sk; Profile = $prof }
        Write-Log 'INFO' "Sketch $($s.id) on $planeDesc ($($s.profile.type))"
    }

    # features in plan order
    foreach ($f in $plan.features) {
        $obj = Invoke-Feature -ctx $ctx -node $f
        $ctx.Features[$f.id] = $obj
        Write-Log 'INFO' "$($f.id) $($f.type) created"
    }

    $doc.Update()
    Write-Log 'INFO' "Document.Update() completed"

    # health check
    $unresolved = 0
    foreach ($feat in $cd.Features) {
        try { if ($feat.HealthStatus -ne [Inventor.HealthStatusEnum]::kUpToDateHealth -and
                  $feat.HealthStatus -ne [Inventor.HealthStatusEnum]::kUpToDateExceptEditHealth) { $unresolved++ } } catch { }
    }
    $facts.updateErrors = $unresolved
    if ($unresolved -gt 0) { throw "BLOCKED: $unresolved feature(s) unresolved after Update()" }

    $doc.SaveAs($iptPath, $false)
    Write-Log 'INFO' "IPT saved: $iptPath"

    # in-session facts
    $facts.bodies = $cd.SurfaceBodies.Count
    $facts.featureCount = $cd.Features.Count
    $facts.docType = 'kPartDocumentObject'

    if ($launchedByUs -and -not $KeepOpen) {
        $doc.Close($false)
    }
}
catch {
    $ex = $_.Exception
    Write-Log 'ERROR' ("{0}: {1}" -f $ex.GetType().FullName, $ex.Message)
    Write-Log 'ERROR' ("at {0}" -f $_.InvocationInfo.PositionMessage.Trim())
    Write-Log 'ERROR' ("stack: {0}" -f ($_.ScriptStackTrace -replace "`r?`n", ' | '))
    if ($ex.PSObject.Properties.Name -contains 'HResult') { Write-Log 'ERROR' ("HRESULT: 0x{0:X8}" -f $ex.HResult) }
    Write-Report -Result "FAIL  ($($ex.Message))" -Facts $facts
    if ($launchedByUs -and $app -and -not $KeepOpen) { try { $app.Quit() } catch { } }
    Write-Host ""
    Write-Host "BUILD_FAILED"
    exit 1
}

# --- verification (fresh process semantics via reopen) -------------------- #
try {
    $verify = & "$PSScriptRoot/verify_ipt.ps1" -IptPath $iptPath -ExpectedFeatures $plan.features.Count -Existing $app
    $facts.bodies = $verify.bodies
    $facts.featureCount = $verify.features
    $facts.docType = $verify.docType
    $facts.size = $verify.size

    if ($verify.pass) {
        Write-Log 'INFO' "Verification PASS: $($verify.summary)"
        Write-Report -Result "PASS" -Facts $facts
        if ($launchedByUs -and $app -and -not $KeepOpen) { try { $app.Quit() } catch { } }
        Write-Host ""
        Write-Host "BUILD_OK  $iptPath  ($($facts.size) bytes, $($facts.bodies) body/bodies, $($facts.featureCount) features)"
        exit 0
    } else {
        Write-Log 'ERROR' "Verification FAIL: $($verify.summary)"
        Write-Report -Result "FAIL  (verification: $($verify.summary))" -Facts $facts
        if ($launchedByUs -and $app -and -not $KeepOpen) { try { $app.Quit() } catch { } }
        Write-Host ""
        Write-Host "BUILD_FAILED"
        exit 1
    }
}
catch {
    Write-Log 'ERROR' ("verification step threw: {0}" -f $_.Exception.Message)
    Write-Report -Result "FAIL  (verification error: $($_.Exception.Message))" -Facts $facts
    if ($launchedByUs -and $app -and -not $KeepOpen) { try { $app.Quit() } catch { } }
    exit 1
}
