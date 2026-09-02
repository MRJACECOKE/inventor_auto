# scripts/lib/json.ps1  -  cad-plan.json loader + small accessors.
Set-StrictMode -Version Latest

function Read-CadPlan {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path $Path)) { throw "cad-plan not found: $Path" }
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    # Windows PowerShell 5.1 ConvertFrom-Json has no -Depth arg (and no depth limit).
    $plan = $raw | ConvertFrom-Json
    foreach ($k in 'plan_version', 'part_name', 'units', 'parameters', 'sketches', 'features') {
        if (-not $plan.PSObject.Properties.Name.Contains($k)) {
            throw "cad-plan.json missing required key '$k'"
        }
    }
    if ($plan.plan_version -ne '1.0') { throw "unsupported plan_version '$($plan.plan_version)'" }
    return $plan
}

function Get-PlanParameter {
    param($Plan, [string] $Key)
    $p = $Plan.parameters.PSObject.Properties[$Key]
    if ($null -eq $p) { throw "plan parameter '$Key' not defined" }
    return $p.Value
}

function Get-ParamExpr {
    # Returns the Inventor parameter *name* for a plan parameter key, so feature
    # calls stay linked to the named parameter (never a bare literal).
    param($Plan, [string] $Key)
    $null = Get-PlanParameter -Plan $Plan -Key $Key
    return "p_$Key"
}
