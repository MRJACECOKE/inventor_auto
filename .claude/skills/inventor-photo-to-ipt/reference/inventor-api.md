# Inventor API reference notes

Primary runner: **Windows PowerShell 5.1 (`powershell.exe`) + Inventor COM**.
Full strategy in `docs/spec/06-inventor-automation.md`.

## Why Windows PowerShell 5.1, not pwsh 7

- pwsh 7 runs **MTA**. Inventor's COM API expects **STA**. Under pwsh 7 some
  calls (observed: `Application.TransientObjects.CreateObjectCollection()`)
  silently return `null`, and `System.Runtime.InteropServices.Marshal.GetActiveObject`
  does not exist in .NET Core.
- Windows PowerShell 5.1 is **STA**, runs .NET Framework (native Inventor
  interop), and `Marshal.GetActiveObject` works.
- `scripts/inventor_build.ps1` and `scripts/verify_ipt.ps1` refuse to run under
  pwsh / non-STA.

## Interop assembly

`C:\Program Files\Autodesk\Inventor 2027\Bin\Public Assemblies\Autodesk.Inventor.Interop.dll`
`Add-Type -LiteralPath` it to get real enum names, e.g.
`[Inventor.DocumentTypeEnum]::kPartDocumentObject` (12290),
`[Inventor.PartFeatureOperationEnum]::kNewBodyOperation` (20485),
`[Inventor.PartFeatureExtentDirectionEnum]::kPositiveExtentDirection` (20993),
`[Inventor.CurveTypeEnum]::kLineSegmentCurve` (5123).

## COM object enumeration trap (PowerShell)

Inventor collection objects (`Profile`, `EdgeCollection`, `ObjectCollection`) are
`IEnumerable`. If a PowerShell **function returns one**, PowerShell unrolls it
into `Object[]` and the next COM call fails with
`Cannot convert "Object[]" ... to type "Object"`. Mitigations used here:
- keep the object in a hashtable and read it back by **property access**
  (`$ctx.Sketches[$id].Profile`), or
- wrap it: `return @{ Coll = $collection }` and read `.Coll` at the call site.

## Connect / launch

```powershell
try   { $app = [Runtime.InteropServices.Marshal]::GetActiveObject('Inventor.Application') }
catch { $app = New-Object -ComObject 'Inventor.Application' }
$app.Visible = $true
if ($app.SoftwareVersion.Major -lt 31) { throw 'not Inventor 2027' }
```
Attaching to a **dirty** running instance (orphan unsaved part docs from failed
runs) can also make `CreateObjectCollection` misbehave - close stray Inventor
instances if builds start failing oddly.

## Units - single conversion point (`scripts/lib/units.ps1`)

Never do unit arithmetic. Build a unit-qualified expression string
(`"25.4 mm"`, `"30 deg"`) and let Inventor convert:
`AddByExpression($name, $expr, $unitString)` for user parameters,
`UnitsOfMeasure.GetValueFromExpression($expr, $unitString)` for an internal value.

## Feature calls confirmed against Inventor 2027 interop (`scripts/lib/features.ps1`)

- Extrude: `Features.ExtrudeFeatures.CreateExtrudeDefinition(profile, op)` ->
  `def.SetDistanceExtent(expr, dir)` / `def.SetThroughAllExtent(dir)` ->
  `ExtrudeFeatures.Add(def)`.
- Hole: `HoleFeatures.CreateSketchPlacementDefinition(objColl of sketch hole-centre points)`
  -> `HoleFeatures.AddDrilledByThroughAllExtent(placement, diaExpr, dir)` /
  `AddDrilledByDistanceExtent(placement, diaExpr, depthExpr, dir, tipAngle)`.
  (The `AddDrilledBy*` overloads take a **placement definition**, not a raw
  collection.)
- Fillet: `FilletFeatures.CreateFilletDefinition()` ->
  `def.AddConstantRadiusEdgeSet(edgeColl, radiusExpr, $true)` -> `Add(def)`;
  fallback `FilletFeatures.AddSimple(edgeColl, radiusExpr)`.
- Sketch-point dimensioning to origin: project the origin work point into the
  sketch (`sketch.AddByProjectingEntity($cd.WorkPoints.Item(1))`) then
  `DimensionConstraints.AddTwoPointDistance(originSk, pt, orientation, textPt)`
  and set `dim.Parameter.Expression = 'p_<name>'`.
