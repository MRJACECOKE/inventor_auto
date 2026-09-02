# 06 — Inventor Automation

Primary implementation: **Windows PowerShell 5.1 (`powershell.exe`) + Inventor COM
Automation**. No GUI macros. Rationale: Inventor 2027 is installed and its COM
server is registered (`Inventor.Application` → `…\Bin\Inventor.exe /Automation`),
but there is no .NET SDK on this machine, so a compiled C# runner cannot be built
here.

**Host must be Windows PowerShell 5.1, not pwsh 7** (verified on this machine):

- pwsh 7 runs **MTA**; Inventor's COM API expects **STA**. Under pwsh 7,
  `Application.TransientObjects.CreateObjectCollection()` was observed to return
  `null`, and `System.Runtime.InteropServices.Marshal.GetActiveObject` does not
  exist in .NET Core.
- Windows PowerShell 5.1 is **STA**, runs .NET Framework (native Inventor
  interop), and `Marshal.GetActiveObject` works.
- `inventor_build.ps1` / `verify_ipt.ps1` guard on `$PSVersionTable.PSVersion` and
  `[Thread]::CurrentThread.GetApartmentState()` and exit `2` (`BLOCKED`) outside
  STA Windows PowerShell.

**PowerShell COM enumeration trap.** Inventor collection objects (`Profile`,
`EdgeCollection`, `ObjectCollection`) are `IEnumerable`; returning one from a
PowerShell **function** makes PowerShell unroll it into `Object[]`, and the next
COM call fails with `Cannot convert "Object[]" … to type "Object"`. Rule in this
codebase: never return such an object from a function — keep it in a hashtable and
read it back by property access, or wrap it as `@{ Coll = $collection }` and read
`.Coll` at the call site.

## API references consulted

The runner must be written against a real API reference, not from memory:

- Local SDK: `C:\Program Files\Autodesk\Inventor 2027\SDK\` (developer docs,
  samples, type library). **Read the relevant `.chm` / sample before writing each
  feature builder.**
- Autodesk Inventor API Help (Object Model, `PartFeatures`, `ExtrudeFeatures`,
  `HoleFeatures`, `FilletFeatures`, `RectangularPatternFeatures`, `UnitsOfMeasure`).

Any API signature used in `scripts/lib/*.ps1` carries a one-line comment citing
where it was confirmed.

## Runtime install resolution (`scripts/lib/inventor_env.ps1`)

So the runner works on any PC with Inventor (not just this one), the install path
is resolved at runtime, never hardcoded in the feature builders:

- `Get-InventorExePath` — `HKLM\SOFTWARE\Classes\Inventor.Application\CLSID`
  → `CLSID\{clsid}\LocalServer32` (`"…\Bin\Inventor.exe" /Automation`) → the
  `Inventor.exe` path; fallback `C:\Program Files\Autodesk\Inventor 2027\Bin\Inventor.exe`.
- `Get-InventorInteropDll` — `<Inventor.exe dir>\Public Assemblies\Autodesk.Inventor.Interop.dll`
  (or `<dir>\Autodesk.Inventor.Interop.dll`); fallback to the 2027 path; throws
  `BLOCKED: …` if neither resolves to a file.
- `Get-InventorProgId` — `"Inventor.Application"`.

`inventor_build.ps1`, `verify_ipt.ps1` and `detect_inventor.ps1` dot-source this
helper. Interop enum integer values are stable across the 2027 line and the
assembly is loaded dynamically, so no code regen is needed for a point release.
Covered by `tests/test_inventor_env.ps1`.

## Connection (INV-001)

```powershell
# scripts/detect_inventor.ps1  – probe only
$progId  = 'Inventor.Application'
$clsid   = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$progId\CLSID").'(default)'
$server  = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\CLSID\$clsid\LocalServer32").'(default)'
```

```powershell
# scripts/inventor_build.ps1  – connect or launch
try   { $inv = [Runtime.InteropServices.Marshal]::GetActiveObject('Inventor.Application') }
catch { $inv = New-Object -ComObject 'Inventor.Application' }
$inv.Visible = $true
$ver = $inv.SoftwareVersion
if ($ver.Major -lt 31) { throw "BLOCKED: connected Inventor major version $($ver.Major) is not 2027 (expected 31)" }
Write-Log "INFO" "Inventor.Application connected: $($ver.DisplayName) build $($ver.Major).$($ver.Minor)"
```

- Enum constants are passed as **integers** (late-bound IDispatch has no enum
  names). Each integer is named in a comment, e.g.
  `# kNewBodyOperation = 20481`, `# kMetricPartDocumentObject = 12290`.
- The runner records whether it launched Inventor; if it did, it closes that
  instance on exit (`$inv.Quit()`), otherwise it leaves the user's session open.

## Part document creation

```powershell
# kPartDocumentObject = 12290 ; template from the design-data path
$tmpl = $inv.FileManager.GetTemplateFile(12290)   # confirm enum in SDK
$doc  = $inv.Documents.Add(12290, $tmpl, $true)
$cd   = $doc.ComponentDefinition
```

If no template resolves → `SAFE-001` stop: `BLOCKED: no part template available`.

## Units (INV-003) — the single conversion point

`scripts/lib/units.ps1` exposes exactly one function:

```powershell
function ConvertTo-Internal {
  param($doc, [double]$Value, [string]$Unit)   # Unit in mm|cm|in|deg
  $expr = "{0} {1}" -f $Value, $Unit           # e.g. "25.4 mm", "30 deg"
  return $doc.UnitsOfMeasure.GetValueFromExpression($expr, <unitTypeEnum>)
}
```

- Length expressions use the length unit type; angle expressions the angle unit
  type (enum integers named in comments, confirmed against the SDK).
- Nothing else in the codebase multiplies or divides to change units. A grep gate
  in `tests` / code review forbids `* 10`, `/ 10`, `0.0393`, `25.4` literals in
  `scripts/lib/features.ps1` and `geometry.ps1`.
- User parameters are created from the expression string so the Inventor parameter
  itself is unit-aware and user-editable:
  `$cd.Parameters.UserParameters.AddByExpression("p_overall_width", "100 mm", <lenEnum>)`.

## Parameter creation

For each `cad-plan.json.parameters` entry, in stable order:

```powershell
$name = "p_$key"
$expr = "{0} {1}" -f $p.value, $p.unit
$cd.Parameters.UserParameters.AddByExpression($name, $expr, $unitTypeEnum)
```

Derived parameters are added as expressions referencing other `p_*` names when the
derivation is a pure pass-through or simple arithmetic; otherwise the resolved
value is used and the derivation is recorded in the report.

## Feature builders (`scripts/lib/features.ps1`)

One function per feature type. Contract: take `$cd`, the feature node, and a
selector resolver; return the created feature object; throw
`"INV-$($node.id) <message>"` with the COM exception attached on failure.

| Function | Inventor calls (confirm in SDK) |
|---|---|
| `New-BaseExtrude` | `cd.Sketches.Add(plane)`; draw rectangle via `SketchLines.AddAsTwoPointRectangle`; add dimension constraints bound to `p_*`; `cd.Features.ExtrudeFeatures.CreateExtrudeDefinition` / `.Add` with `kNewBodyOperation` |
| `New-ExtrudeAddCut` | as above with `kJoinOperation` / `kCutOperation`; `through` → `SetThroughAllExtent` |
| `New-Revolve` | sketch profile + axis line; `cd.Features.RevolveFeatures.AddFull` or `.Add` with angle |
| `New-Hole` | sketch point(s) on face; `cd.Features.HoleFeatures.AddDrilledByThroughAllExtent` or `...ByDistanceExtent`; diameter from `p_*` |
| `New-Slot` | sketched slot (two arcs + two lines) dimensioned to `p_length`,`p_width`; Extrude Cut |
| `New-Fillet` | `EdgeCollection` from selector; `cd.Features.FilletFeatures.Add(FilletDefinition)` constant radius `p_*` |
| `New-Chamfer` | `cd.Features.ChamferFeatures.AddUsingDistance` (or distance+angle) |
| `New-Mirror` | `ObjectCollection` of parent features; `cd.Features.MirrorFeatures.Add(parents, plane, computeType)` |
| `New-RectangularPattern` | `cd.Features.RectangularPatternFeatures.Add(parents, xDir, xCount, xSpacing, ...)` counts as integers, spacings as `p_*` |
| `New-CircularPattern` | `cd.Features.CircularPatternFeatures.Add(parents, axis, count, angle, fitWithinAngle, ...)` |

After all features: `$doc.Update()` then check
`$doc.ComponentDefinition.Features` for `HealthStatus` errors; any error →
`SAFE-001` stop.

## Save (INV-004)

```powershell
$safe = ($plan.part_name -replace '[^A-Za-z0-9_.-]', '_')
$outDir = Join-Path $repo "output/$safe"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$path = Join-Path $outDir "$safe.ipt"
$doc.SaveAs($path, $false)
```

Then hand off to `verify_ipt.ps1`.

## Logging

`Write-Log` appends `[$level] $msg` to `output/<part>/build-log.txt` and echoes to
stdout. Exceptions logged with `$_.Exception.GetType().FullName`,
`$_.Exception.Message`, and `$_.Exception.HResult` when present. No `catch {}`
without a log + rethrow/stop.

## Optional upgrade — C# runner

`tools/InventorCadRunner/` (needs .NET SDK): typed Interop, same `cad-plan.json`
contract, class-per-feature mirroring `features.ps1`. Not built in v1.
