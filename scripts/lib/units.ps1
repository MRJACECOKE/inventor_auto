# scripts/lib/units.ps1
# THE single unit-conversion point (spec INV-003 / docs/spec/06).
# Nothing else in this codebase may multiply/divide to change units.
#
# Inventor's internal database units are centimetres (length) and radians (angle).
# We never do that arithmetic ourselves: every value carries an explicit unit and
# is handed to Inventor as a unit-qualified expression string
# (e.g. "25.4 mm", "30 deg"). Inventor's UnitsOfMeasure does the conversion.
#
# API refs (Autodesk Inventor API Help, stable across many releases):
#   UnitsOfMeasure.GetValueFromExpression(Expression, UnitsType)   -> Double (internal units)
#   Parameters.UserParameters.AddByExpression(Name, Expression, Units)
#   Both `UnitsType`/`Units` accept a valid unit string ("mm","cm","in","deg")
#   or an Inventor.UnitsTypeEnum. We pass the string form to avoid enum drift.

Set-StrictMode -Version Latest

function Get-UnitExpression {
    param(
        [Parameter(Mandatory)] [double] $Value,
        [Parameter(Mandatory)] [ValidateSet('mm', 'cm', 'in', 'deg', 'count')] [string] $Unit
    )
    if ($Unit -eq 'count') { return [string][int]$Value }
    # invariant formatting so "." stays the decimal separator regardless of locale
    return ('{0} {1}' -f ([double]$Value).ToString([System.Globalization.CultureInfo]::InvariantCulture), $Unit)
}

function Get-InternalValue {
    # Convert a (value, unit) pair to Inventor internal units via UnitsOfMeasure.
    param(
        [Parameter(Mandatory)] $Document,
        [Parameter(Mandatory)] [double] $Value,
        [Parameter(Mandatory)] [string] $Unit
    )
    if ($Unit -eq 'count') { return [int]$Value }
    $expr = Get-UnitExpression -Value $Value -Unit $Unit
    $parseUnit = if ($Unit -eq 'deg') { 'deg' } else { $Unit }
    return $Document.UnitsOfMeasure.GetValueFromExpression($expr, $parseUnit)
}

function Add-UserParameter {
    # Create (or update) a named Inventor user parameter p_<key> from a plan parameter.
    param(
        [Parameter(Mandatory)] $ComponentDefinition,
        [Parameter(Mandatory)] [string] $Key,
        [Parameter(Mandatory)] [double] $Value,
        [Parameter(Mandatory)] [string] $Unit
    )
    $name = "p_$Key"
    $expr = Get-UnitExpression -Value $Value -Unit $Unit
    $userParams = $ComponentDefinition.Parameters.UserParameters
    $existing = $null
    foreach ($p in $userParams) { if ($p.Name -eq $name) { $existing = $p; break } }
    $unitArg = if ($Unit -eq 'count') { 'ul' } elseif ($Unit -eq 'deg') { 'deg' } else { $Unit }
    if ($null -ne $existing) {
        $existing.Expression = $expr
        return $existing
    }
    return $userParams.AddByExpression($name, $expr, $unitArg)
}
