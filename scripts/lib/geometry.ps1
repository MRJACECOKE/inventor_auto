# scripts/lib/geometry.ps1
# Sketch / point / plane / edge helpers. Positions are computed from parameter
# VALUES (internal units via Get-InternalValue) but every driving dimension is
# then linked to the named parameter by expression (see features.ps1).
#
# API refs (Autodesk Inventor API Help):
#   Application.TransientGeometry.CreatePoint2d(X, Y)
#   PartComponentDefinition.WorkPlanes.Item(1..3)  -> XY(3), XZ(2), YZ(1) by default
#   PlanarSketch.SketchLines.AddAsTwoPointRectangle(PointOne, PointTwo)
#   PlanarSketch.SketchPoints.Add(Point, HoleCenter)
#   Sketch.DimensionConstraints.AddTwoPointDistance(PointOne, PointTwo, Orientation, TextPoint)

Set-StrictMode -Version Latest

function Get-WorkPlane {
    param($ComponentDefinition, [ValidateSet('XY', 'XZ', 'YZ')] [string] $Plane)
    switch ($Plane) {
        'YZ' { return $ComponentDefinition.WorkPlanes.Item(1) }
        'XZ' { return $ComponentDefinition.WorkPlanes.Item(2) }
        'XY' { return $ComponentDefinition.WorkPlanes.Item(3) }
    }
}

function New-P2d {
    param($App, [double] $X, [double] $Y)
    return $App.TransientGeometry.CreatePoint2d($X, $Y)
}

function Set-DimExpression {
    # Link a just-created dimension constraint to a named parameter. Non-fatal:
    # if it fails, the geometry keeps its nominal size and the caller logs WARN.
    param($DimConstraint, [string] $ParamName)
    $DimConstraint.Parameter.Expression = $ParamName
}

function Add-RectangleGeometry {
    <#
      Draws an axis-aligned rectangle sized to WidthVal x HeightVal and links the
      two governing dimensions to WidthParam / HeightParam. Corner 'origin' puts
      the lower-left corner at the sketch origin; corner 'center' centres the
      rectangle on the sketch origin. Emits nothing: the caller calls
      $Sketch.Profiles.AddForSolid() itself (a Profile is IEnumerable and must
      never cross a function-output boundary or PowerShell unrolls it).
    #>
    param(
        $App, $ComponentDefinition, $Sketch,
        [double] $WidthVal, [double] $HeightVal,
        [string] $WidthParam, [string] $HeightParam,
        [ValidateSet('origin', 'center')] [string] $Corner = 'origin',
        [scriptblock] $Warn = $null
    )
    if ($Corner -eq 'center') {
        $p1 = New-P2d $App (-$WidthVal / 2) (-$HeightVal / 2)
        $p2 = New-P2d $App ($WidthVal / 2) ($HeightVal / 2)
    } else {
        $p1 = New-P2d $App 0 0
        $p2 = New-P2d $App $WidthVal $HeightVal
    }
    $rect = $Sketch.SketchLines.AddAsTwoPointRectangle($p1, $p2)
    $null = $rect

    # rect is a collection of 4 SketchLines: [1]=bottom, [2]=right, [3]=top, [4]=left
    try {
        $bottom = $rect.Item(1)
        $left = $rect.Item(4)
        $tp1 = New-P2d $App ($WidthVal / 2) (-1)
        $tp2 = New-P2d $App (-1) ($HeightVal / 2)
        # kHorizontalDim = 46081 ... use enum for safety
        $hDim = $Sketch.DimensionConstraints.AddTwoPointDistance(
            $bottom.StartSketchPoint, $bottom.EndSketchPoint,
            [Inventor.DimensionOrientationEnum]::kHorizontalDim, $tp1)
        $vDim = $Sketch.DimensionConstraints.AddTwoPointDistance(
            $left.StartSketchPoint, $left.EndSketchPoint,
            [Inventor.DimensionOrientationEnum]::kVerticalDim, $tp2)
        Set-DimExpression $hDim $WidthParam
        Set-DimExpression $vDim $HeightParam
    } catch {
        if ($Warn) { & $Warn "rectangle dimension link failed, geometry left at nominal size: $($_.Exception.Message)" }
    }
}

function Add-PolygonGeometry {
    <#
      Draws a regular polygon ($Sides vertices) centred on the sketch origin,
      inscribed in a circle of radius $CircumRadiusVal (internal units). Vertex 0
      sits at (90 deg + $ClockingDeg) so a vertex points "up" by default; the
      remaining vertices follow counter-clockwise. One radial dimension
      (origin -> vertex 0) is linked to "<CircumParam> / 2" so the polygon stays
      parametric. Non-fatal: on link failure the polygon keeps its nominal size
      and the caller logs WARN. Emits nothing: the caller calls
      $Sketch.Profiles.AddForSolid() itself.
    #>
    param(
        $App, $ComponentDefinition, $Sketch,
        [int] $Sides,
        [double] $CircumRadiusVal,
        [double] $ClockingDeg = 0,
        [string] $CircumParam,
        [scriptblock] $Warn = $null
    )
    if ($Sides -lt 3) { throw "polygon needs >= 3 sides, got $Sides" }
    # shared SketchPoints so consecutive edges have exactly coincident endpoints
    # (a closed loop -> Profiles.AddForSolid() gets one region)
    $vp = @()
    for ($k = 0; $k -lt $Sides; $k++) {
        $ang = (90.0 + $ClockingDeg + ($k * 360.0 / $Sides)) * [math]::PI / 180.0
        $x = $CircumRadiusVal * [math]::Cos($ang)
        $y = $CircumRadiusVal * [math]::Sin($ang)
        $vp += $Sketch.SketchPoints.Add((New-P2d $App $x $y), $false)
    }
    $lines = @()
    for ($k = 0; $k -lt $Sides; $k++) {
        $lines += $Sketch.SketchLines.AddByTwoPoints($vp[$k], $vp[($k + 1) % $Sides])
    }
    # keep it a regular polygon under parametric change: equal-length constraints
    try {
        for ($k = 1; $k -lt $Sides; $k++) {
            $null = $Sketch.GeometricConstraints.AddEqualLength($lines[0], $lines[$k])
        }
    } catch {
        if ($Warn) { & $Warn "polygon equal-length constraints failed (regularity not locked): $($_.Exception.Message)" }
    }
    # link one radial dimension to the circumscribed-circle radius
    try {
        $originSk = $Sketch.AddByProjectingEntity($ComponentDefinition.WorkPoints.Item(1))
        $v0 = $lines[0].StartSketchPoint
        $tp = New-P2d $App ($CircumRadiusVal / 2.0) ($CircumRadiusVal / 2.0)
        $rDim = $Sketch.DimensionConstraints.AddTwoPointDistance(
            $originSk, $v0, [Inventor.DimensionOrientationEnum]::kAlignedDim, $tp)
        $rDim.Parameter.Expression = "($CircumParam) / 2"
    } catch {
        if ($Warn) { & $Warn "polygon radial dimension link failed, geometry left at nominal size: $($_.Exception.Message)" }
    }
}

function Get-VerticalOuterEdges {
    # Edges of body 1 that are straight and parallel to Z (the vertical corners
    # of a prismatic base). Returns @{ Coll = <EdgeCollection> } so PowerShell
    # does not unroll the (IEnumerable) collection across the function boundary.
    param($App, $ComponentDefinition)
    $ec = $App.TransientObjects.CreateEdgeCollection()
    $body = $ComponentDefinition.SurfaceBodies.Item(1)
    foreach ($e in $body.Edges) {
        try {
            if ($e.GeometryType -ne [int][Inventor.CurveTypeEnum]::kLineSegmentCurve -and
                $e.GeometryType -ne [int][Inventor.CurveTypeEnum]::kLineCurve) { continue }
            $d = $e.Geometry.Direction    # UnitVector3d
            if ([math]::Abs([math]::Abs($d.Z) - 1.0) -lt 1e-4 -and
                [math]::Abs($d.X) -lt 1e-4 -and [math]::Abs($d.Y) -lt 1e-4) {
                $null = $ec.Add($e)
            }
        } catch { }
    }
    return @{ Coll = $ec }
}

function Resolve-EdgeSelector {
    # Returns @{ Coll = <EdgeCollection> }.
    param($App, $ComponentDefinition, [string] $Selector)
    switch -Regex ($Selector) {
        '^all_vertical_outer$' { return (Get-VerticalOuterEdges -App $App -ComponentDefinition $ComponentDefinition) }
        default { throw "edge selector '$Selector' is not supported in v1" }
    }
}

function Get-Axis {
    param($ComponentDefinition, [string] $Selector)
    switch -Regex ($Selector) {
        '^(axis:)?[Xx]$' { return $ComponentDefinition.WorkAxes.Item(1) }
        '^(axis:)?[Yy]$' { return $ComponentDefinition.WorkAxes.Item(2) }
        '^(axis:)?[Zz]$' { return $ComponentDefinition.WorkAxes.Item(3) }
        default { throw "axis selector '$Selector' is not supported in v1" }
    }
}
