<#
  test_inventor_env.ps1  -  checks scripts/lib/inventor_env.ps1 resolves the real
  Autodesk Inventor install. Requires Inventor installed (any recent version;
  the DLL just has to exist). Runs under pwsh or Windows PowerShell.

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test_inventor_env.ps1

  Prints TEST: PASS / TEST: FAIL <reason>. Exit code matches.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
. (Join-Path $repo 'scripts/lib/inventor_env.ps1')

$fails = @()
function Check($name, $cond) {
    if ($cond) { Write-Host "ok   $name" } else { Write-Host "FAIL $name"; $script:fails += $name }
}

# 1. ProgId
Check "Get-InventorProgId is Inventor.Application" ((Get-InventorProgId) -eq 'Inventor.Application')

# 2. exe path resolves to an existing Inventor.exe
$exe = Get-InventorExePath
Check "Get-InventorExePath resolves"            ($null -ne $exe)
Check "resolved Inventor.exe exists"            ($exe -and (Test-Path $exe))
Check "resolved path ends with Inventor.exe"    ($exe -and ($exe -match 'Inventor\.exe$'))

# 3. interop DLL resolves to an existing file
$dll = $null
try { $dll = Get-InventorInteropDll } catch { Write-Host "FAIL Get-InventorInteropDll threw: $($_.Exception.Message)"; $fails += 'interop-threw' }
Check "Get-InventorInteropDll resolves"         ($null -ne $dll)
Check "interop DLL exists on disk"              ($dll -and (Test-Path $dll))
Check "interop DLL name is correct"             ($dll -and ($dll -match 'Autodesk\.Inventor\.Interop\.dll$'))

# 4. registry-derived, not just the hardcoded fallback (informational + consistency)
if ($exe -and $dll) {
    $binFromExe = Split-Path -Parent $exe
    Check "interop DLL lives under the resolved Bin dir" ($dll.StartsWith($binFromExe, [System.StringComparison]::OrdinalIgnoreCase))
}

# 5. matches detect_inventor.ps1's JSON interop_dll
$detect = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'scripts/detect_inventor.ps1')
$json = $detect | Where-Object { $_.Trim().StartsWith('{') } | Select-Object -Last 1
$parsed = $json | ConvertFrom-Json
Check "detect_inventor.ps1 emitted JSON"        ($null -ne $parsed)
Check "detect interop_dll == Get-InventorInteropDll" (
    $parsed -and $dll -and ($parsed.interop_dll -ieq $dll)
)
Check "detect reports usable"                   ($parsed -and $parsed.usable -eq $true)

if ($fails.Count -eq 0) { Write-Host "`nTEST: PASS"; exit 0 }
else { Write-Host "`nTEST: FAIL $($fails -join ', ')"; exit 1 }
