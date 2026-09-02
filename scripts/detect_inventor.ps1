<#
  detect_inventor.ps1  -  probe only, never launches Inventor.

  Reports: COM ProgID + CLSID + LocalServer32, installed Inventor version from
  Inventor.exe, and whether the .NET interop assembly loads in this PowerShell.

  Exit 0 if Inventor 2027 (major 31) looks usable, 1 otherwise.
  Emits a JSON object on the last line for machine consumption.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. "$PSScriptRoot/lib/inventor_env.ps1"

$result = [ordered]@{
    progid            = 'Inventor.Application'
    clsid             = $null
    local_server      = $null
    exe_path          = $null
    product_name      = $null
    file_version      = $null
    major             = $null
    interop_dll       = $null
    interop_loads     = $false
    usable            = $false
    notes             = @()
}

try {
    $result.clsid = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\Inventor.Application\CLSID" -ErrorAction Stop).'(default)'
    $result.local_server = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\CLSID\$($result.clsid)\LocalServer32" -ErrorAction Stop).'(default)'
} catch {
    $result.notes += "COM ProgID Inventor.Application not registered: $($_.Exception.Message)"
}

$exe = Get-InventorExePath
if ($exe -and (Test-Path $exe)) {
    $vi = (Get-Item $exe).VersionInfo
    $result.exe_path     = $exe
    $result.product_name = $vi.ProductName
    $result.file_version = $vi.FileVersion
    if ($vi.FileVersion -match '(\d+)\.') { $result.major = [int]$Matches[1] }
} else {
    $result.notes += "Inventor.exe not found (registry ProgID + fallback both failed)"
}

$dll = $null
try { $dll = Get-InventorInteropDll } catch { $result.notes += $_.Exception.Message }
if ($dll -and (Test-Path $dll)) {
    $result.interop_dll = $dll
    try {
        Add-Type -LiteralPath $dll -ErrorAction Stop
        $null = [Inventor.DocumentTypeEnum]::kPartDocumentObject
        $result.interop_loads = $true
    } catch {
        $result.notes += "interop assembly failed to load: $($_.Exception.Message)"
    }
} else {
    $result.notes += "interop assembly not found at $dll"
}

$result.usable = ($null -ne $result.local_server) -and ($result.major -eq 31)

Write-Host "ProgID        : $($result.progid)"
Write-Host "CLSID         : $($result.clsid)"
Write-Host "LocalServer32 : $($result.local_server)"
Write-Host "Inventor.exe  : $($result.exe_path)"
Write-Host "Product       : $($result.product_name)"
Write-Host "FileVersion   : $($result.file_version)  (major $($result.major))"
Write-Host "Interop DLL   : $($result.interop_dll)"
Write-Host "Interop loads : $($result.interop_loads)"
Write-Host "Usable (2027) : $($result.usable)"
if ($result.notes.Count) { $result.notes | ForEach-Object { Write-Host "note: $_" } }

($result | ConvertTo-Json -Compress -Depth 5)
if ($result.usable) { exit 0 } else { exit 1 }
