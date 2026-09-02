# scripts/lib/features.ps1
# One builder per feature type. Each returns the created feature object and
# throws "INV-<id> <message>" (with the COM exception attached) on failure.
#
# Requires (dot-sourced by inventor_build.ps1, in this order):
#   units.ps1  geometry.ps1  json.ps1
# and the Inventor interop assembly already loaded (Add-Type).
#
# API refs: Autodesk Inventor API Help / Autodesk.Inventor.Interop.xml.

Set-StrictMode -Version Latest

function _prop($obj, [string] $name, $default = $null) {
    # StrictMode-safe optional property read on a ConvertFrom-Json object
    if ($null -ne $obj -and $obj.PSObject.Properties.Name -contains $name) { return $obj.$name }
    return $default
}

function _dir([string] $d) {
    switch ($d) {
        'positive'  { [Inventor.PartFeatureExtentDirectionEnum]::kPositiveExtentDirection }
        'negative'  { [Inventor.PartFeatureExtentDirectionEnum]::kNegativeExtentDirection }
        'symmetric' { [Inventor.PartFeatureExtentDirectionEnum]::kSymmetricExtentDirection }
        default     { [Inventor.PartFeatureExtentDirectionEnum]::kPositiveExtentDirection }
    }
}

function _op([string] $o) {
    switch ($o) {
        'new'       { [Inventor.PartFeatureOperationEnum]::kNewBodyOperation }
        'join'      { [Inventor.PartFeatureOperationEnum]::kJoinOperation }
        'cut'       { [Inventor.PartFeatureOperationEnum]::kCutOperation }
        'intersect' { [Inventor.PartFeatureOperationEnum]::kIntersectOperation }
        default     { [Inventor.PartFeatureOperationEnum]::kJoinOperation }
    }
}

function _objcoll($App) { $App.TransientObjects.CreateObjectCollection() }

function _resolveInternal {
    param($ctx, [string] $ParamKey)
    $p = Get-PlanParameter -Plan $ctx.Plan -Key $ParamKey
    return (Get-InternalValue -Document $ctx.Doc -Value ([double]$p.value) -Unit ([string]$p.unit))
}

# --------------------------------------------------------------------------- #

function _assertSketch($ctx, $node) {
    if (-not $ctx.Sketches.ContainsKey($node.sketch)) {
        throw "INV-$($node.id) sketch '$($node.sketch)' was not created"
    }
}

function New-BaseExtrude {
    param($ctx, $node)
    _assertSketch $ctx $node
    # property access (not a function return) so PowerShell never unrolls the Profile
    $prof = $ctx.Sketches[$node.sketch].Profile
    $ex = $ctx.Cd.Features.ExtrudeFeatures
    $def = $ex.CreateExtrudeDefinition($prof, (_op 'new'))
    $def.SetDistanceExtent((Get-ParamExpr $ctx.Plan $node.distance_param), (_dir (_prop $node 'direction' 'positive')))
    try { return $ex.Add($def) }
    catch { throw "INV-$($node.id) base_extrude failed: $($_.Exception.Message)" }
}

function New-ExtrudeAddCut {
    param($ctx, $node, [string] $Kind)   # Kind: join | cut
    _assertSketch $ctx $node
    $prof = $ctx.Sketches[$node.sketch].Profile
    $ex = $ctx.Cd.Features.ExtrudeFeatures
    $def = $ex.CreateExtrudeDefinition($prof, (_op $Kind))
    $dir = _dir (_prop $node 'direction' 'positive')
    if ((_prop $node 'depth') -eq 'through') {
        $def.SetThroughAllExtent($dir)
    } else {
        $def.SetDistanceExtent((Get-ParamExpr $ctx.Plan $node.distance_param), $dir)
    }
    try { return $ex.Add($def) }
    catch { throw "INV-$($node.id) $Kind extrude failed: $($_.Exception.Message)" }
}

function New-Hole {
    param($ctx, $node)
    $plane = Get-WorkPlane $ctx.Cd $node.placement.plane
    $sk = $ctx.Cd.Sketches.Add($plane)
    $xv = _resolveInternal $ctx $node.placement.x_param
    $yv = _resolveInternal $ctx $node.placement.y_param
    $pt = $sk.SketchPoints.Add((New-P2d $ctx.App $xv $yv), $true)
    try {
        # project the part origin into the sketch to dimension against it
        $originSk = $sk.AddByProjectingEntity($ctx.Cd.WorkPoints.Item(1))
        $dx = $sk.DimensionConstraints.AddTwoPointDistance(
            $originSk, $pt, [Inventor.DimensionOrientationEnum]::kHorizontalDim,
            (New-P2d $ctx.App $xv ($yv + 1)))
        $dy = $sk.DimensionConstraints.AddTwoPointDistance(
            $originSk, $pt, [Inventor.DimensionOrientationEnum]::kVerticalDim,
            (New-P2d $ctx.App ($xv + 1) $yv))
        $dx.Parameter.Expression = (Get-ParamExpr $ctx.Plan $node.placement.x_param)
        $dy.Parameter.Expression = (Get-ParamExpr $ctx.Plan $node.placement.y_param)
    } catch {
        & $ctx.Warn "INV-$($node.id) hole position dimension link failed, using nominal position: $($_.Exception.Message)"
    }
    $centers = $ctx.App.TransientObjects.CreateObjectCollection()
    if ($null -eq $centers) { throw "INV-$($node.id) CreateObjectCollection returned null (COM apartment issue?)" }
    $null = $centers.Add($pt)
    $diaExpr = Get-ParamExpr $ctx.Plan $node.diameter_param
    $dir = _dir (_prop $node 'direction' 'positive')
    $holes = $ctx.Cd.Features.HoleFeatures
    try {
        # Inventor 2018+: AddDrilledBy*Extent take a placement definition, not a raw collection
        $placement = $holes.CreateSketchPlacementDefinition($centers)
        if ((_prop $node 'depth' 'through') -eq 'through') {
            return $holes.AddDrilledByThroughAllExtent($placement, $diaExpr, $dir)
        } else {
            $depthExpr = Get-ParamExpr $ctx.Plan $node.depth_param
            return $holes.AddDrilledByDistanceExtent($placement, $diaExpr, $depthExpr, $dir, 118)
        }
    } catch {
        throw "INV-$($node.id) hole failed: $($_.Exception.Message)"
    }
}

function New-Slot {
    param($ctx, $node)
    # Sketched slot (two arcs + two lines) as an Extrude Cut. MVP: axis-aligned in X.
    $plane = Get-WorkPlane $ctx.Cd $node.placement.plane
    $sk = $ctx.Cd.Sketches.Add($plane)
    $cx = _resolveInternal $ctx $node.placement.x_param
    $cy = _resolveInternal $ctx $node.placement.y_param
    $len = _resolveInternal $ctx $node.length_param
    $w = _resolveInternal $ctx $node.width_param
    $r = $w / 2.0
    $x0 = $cx - ($len / 2.0); $x1 = $cx + ($len / 2.0)
    try {
        $L = $sk.SketchLines
        $A = $sk.SketchArcs
        $null = $L.AddByTwoPoints((New-P2d $ctx.App $x0 ($cy + $r)), (New-P2d $ctx.App $x1 ($cy + $r)))
        $null = $L.AddByTwoPoints((New-P2d $ctx.App $x0 ($cy - $r)), (New-P2d $ctx.App $x1 ($cy - $r)))
        $null = $A.AddByCenterStartEndPoint((New-P2d $ctx.App $x1 $cy), (New-P2d $ctx.App $x1 ($cy + $r)), (New-P2d $ctx.App $x1 ($cy - $r)))
        $null = $A.AddByCenterStartEndPoint((New-P2d $ctx.App $x0 $cy), (New-P2d $ctx.App $x0 ($cy - $r)), (New-P2d $ctx.App $x0 ($cy + $r)))
        $prof = $sk.Profiles.AddForSolid()
        $ex = $ctx.Cd.Features.ExtrudeFeatures
        $def = $ex.CreateExtrudeDefinition($prof, (_op 'cut'))
        if ($node.depth -eq 'through') { $def.SetThroughAllExtent((_dir $node.direction)) }
        else { $def.SetDistanceExtent((Get-ParamExpr $ctx.Plan $node.depth_param), (_dir $node.direction)) }
        return $ex.Add($def)
    } catch {
        throw "INV-$($node.id) slot failed: $($_.Exception.Message)"
    }
}

function New-Revolve {
    param($ctx, $node)
    _assertSketch $ctx $node
    $prof = $ctx.Sketches[$node.sketch].Profile
    $axis = Get-Axis $ctx.Cd $node.axis
    $rev = $ctx.Cd.Features.RevolveFeatures
    try {
        if ($node.PSObject.Properties.Name.Contains('full') -and $node.full) {
            return $rev.AddFull($prof, $axis, (_op 'new'))
        }
        $angExpr = Get-ParamExpr $ctx.Plan $node.angle_param
        return $rev.Add($prof, $axis, $angExpr, (_dir $node.direction), (_op 'new'))
    } catch {
        throw "INV-$($node.id) revolve failed: $($_.Exception.Message)"
    }
}

function New-Fillet {
    param($ctx, $node)
    $edges = (Resolve-EdgeSelector -App $ctx.App -ComponentDefinition $ctx.Cd -Selector $node.edges).Coll
    if ($null -eq $edges -or $edges.Count -lt 1) { throw "INV-$($node.id) selector '$($node.edges)' matched no geometry" }
    $radExpr = Get-ParamExpr $ctx.Plan $node.radius_param
    $ff = $ctx.Cd.Features.FilletFeatures
    try {
        $fd = $ff.CreateFilletDefinition()
        $null = $fd.AddConstantRadiusEdgeSet($edges, $radExpr, $true)
        return $ff.Add($fd)
    } catch {
        $firstErr = $_.Exception.Message
        try { return $ff.AddSimple($edges, $radExpr) }
        catch { throw "INV-$($node.id) fillet failed: $($_.Exception.Message) (definition path: $firstErr)" }
    }
}

function New-Chamfer {
    param($ctx, $node)
    $edges = (Resolve-EdgeSelector -App $ctx.App -ComponentDefinition $ctx.Cd -Selector $node.edges).Coll
    if ($null -eq $edges -or $edges.Count -lt 1) { throw "INV-$($node.id) selector '$($node.edges)' matched no geometry" }
    $distExpr = Get-ParamExpr $ctx.Plan $node.distance_param
    $cf = $ctx.Cd.Features.ChamferFeatures
    try { return $cf.AddUsingDistance($edges, $distExpr) }
    catch { throw "INV-$($node.id) chamfer failed: $($_.Exception.Message)" }
}

function _parents($ctx, $node) {
    # returns @{ Coll = <ObjectCollection> } (see note on IEnumerable unrolling)
    $pc = $ctx.App.TransientObjects.CreateObjectCollection()
    $ofList = if ($node.of -is [System.Array]) { $node.of } else { @($node.of) }
    foreach ($fid in $ofList) {
        if (-not $ctx.Features.ContainsKey($fid)) { throw "INV-$($node.id) references unbuilt feature '$fid'" }
        $null = $pc.Add($ctx.Features[$fid])
    }
    return @{ Coll = $pc }
}

function New-Mirror {
    param($ctx, $node)
    $parents = (_parents $ctx $node).Coll
    $plane = Get-WorkPlane $ctx.Cd $node.plane
    $mf = $ctx.Cd.Features.MirrorFeatures
    try {
        $md = $mf.CreateDefinition($parents, $plane)
        return $mf.Add($md)
    } catch {
        try { return $mf.AddByDefinition(($mf.CreateDefinition($parents, $plane))) }
        catch { throw "INV-$($node.id) mirror failed: $($_.Exception.Message)" }
    }
}

function New-RectangularPattern {
    param($ctx, $node)
    $parents = (_parents $ctx $node).Coll
    $xDir = Get-Axis $ctx.Cd 'X'
    $xCount = Get-ParamExpr $ctx.Plan $node.x_count_param
    $xSpace = Get-ParamExpr $ctx.Plan $node.x_spacing_param
    $rp = $ctx.Cd.Features.RectangularPatternFeatures
    try {
        if ($node.PSObject.Properties.Name.Contains('y_count_param')) {
            $yDir = Get-Axis $ctx.Cd 'Y'
            $yCount = Get-ParamExpr $ctx.Plan $node.y_count_param
            $ySpace = Get-ParamExpr $ctx.Plan $node.y_spacing_param
            return $rp.Add($parents, $xDir, $true, $xCount, $xSpace,
                [Inventor.PatternComputeTypeEnum]::kOptimizedCompute, $yDir, $true, $yCount, $ySpace)
        }
        return $rp.Add($parents, $xDir, $true, $xCount, $xSpace)
    } catch {
        throw "INV-$($node.id) rectangular_pattern failed: $($_.Exception.Message)"
    }
}

function New-CircularPattern {
    param($ctx, $node)
    $parents = (_parents $ctx $node).Coll
    $axis = Get-Axis $ctx.Cd $node.axis
    $count = Get-ParamExpr $ctx.Plan $node.count_param
    $angle = if ($node.PSObject.Properties.Name.Contains('full') -and $node.full) { '360 deg' }
             else { Get-ParamExpr $ctx.Plan $node.angle_param }
    $cp = $ctx.Cd.Features.CircularPatternFeatures
    try {
        return $cp.Add($parents, $axis, $true, $count, $angle, $true,
            [Inventor.PatternComputeTypeEnum]::kOptimizedCompute)
    } catch {
        throw "INV-$($node.id) circular_pattern failed: $($_.Exception.Message)"
    }
}

function Invoke-Feature {
    param($ctx, $node)
    switch ($node.type) {
        'base_extrude'        { return New-BaseExtrude $ctx $node }
        'extrude_add'         { return New-ExtrudeAddCut $ctx $node 'join' }
        'extrude_cut'         { return New-ExtrudeAddCut $ctx $node 'cut' }
        'revolve'             { return New-Revolve $ctx $node }
        'hole'                { return New-Hole $ctx $node }
        'slot'                { return New-Slot $ctx $node }
        'fillet'              { return New-Fillet $ctx $node }
        'chamfer'             { return New-Chamfer $ctx $node }
        'mirror'              { return New-Mirror $ctx $node }
        'rectangular_pattern' { return New-RectangularPattern $ctx $node }
        'circular_pattern'    { return New-CircularPattern $ctx $node }
        default { throw "INV-$($node.id) feature type '$($node.type)' is not implemented in v1" }
    }
}
