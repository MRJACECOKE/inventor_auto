# scripts/lib/inventor_env.ps1
# Resolve the Autodesk Inventor install at runtime so the runner works on any PC
# that has Inventor 2027, not just this one. No hardcoded install path in the
# feature builders / runner.
#
# Resolution: HKLM\SOFTWARE\Classes\Inventor.Application\CLSID
#   -> HKLM\SOFTWARE\Classes\CLSID\{clsid}\LocalServer32  (e.g. "...\Bin\Inventor.exe /Automation")
#   -> <Inventor.exe dir>\Public Assemblies\Autodesk.Inventor.Interop.dll
# Fallback: the well-known 2027 path.

Set-StrictMode -Version Latest

$script:InventorProgId = 'Inventor.Application'
$script:InventorFallbackDll = 'C:\Program Files\Autodesk\Inventor 2027\Bin\Public Assemblies\Autodesk.Inventor.Interop.dll'

function Get-InventorProgId { return $script:InventorProgId }

function Get-InventorExePath {
    # Returns the resolved Inventor.exe path, or $null.
    try {
        $clsid = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$($script:InventorProgId)\CLSID" -ErrorAction Stop).'(default)'
        $ls = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\CLSID\$clsid\LocalServer32" -ErrorAction Stop).'(default)'
        # LocalServer32 looks like:  "C:\...\Bin\Inventor.exe" /Automation   (quotes optional)
        if ($ls -match '"?(.*?Inventor\.exe)"?') { return $Matches[1] }
    } catch { }
    $fallbackExe = 'C:\Program Files\Autodesk\Inventor 2027\Bin\Inventor.exe'
    if (Test-Path $fallbackExe) { return $fallbackExe }
    return $null
}

function Get-InventorInteropDll {
    # Returns the path to Autodesk.Inventor.Interop.dll (registry-derived when
    # possible, else the 2027 fallback). Throws if nothing resolves to a file.
    $exe = Get-InventorExePath
    if ($exe) {
        $bin = Split-Path -Parent $exe
        foreach ($cand in @(
            (Join-Path $bin 'Public Assemblies\Autodesk.Inventor.Interop.dll'),
            (Join-Path $bin 'Autodesk.Inventor.Interop.dll')
        )) {
            if (Test-Path $cand) { return $cand }
        }
    }
    if (Test-Path $script:InventorFallbackDll) { return $script:InventorFallbackDll }
    throw "BLOCKED: Autodesk.Inventor.Interop.dll not found (registry ProgID '$($script:InventorProgId)' and fallback '$($script:InventorFallbackDll)' both failed). Is Autodesk Inventor installed?"
}
