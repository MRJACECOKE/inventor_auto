<#
  sign.ps1  -  Authenticode-sign the built Photo-to-IPT Builder.

  A code-signing certificate is NOT shipped with this project - supply your own
  (a PFX file, or a cert already imported into the CurrentUser\My store).
  Needs signtool.exe (installed with the Windows 10/11 SDK).

    powershell -File build/sign.ps1 -Pfx C:\certs\code.pfx -Password ****
    powershell -File build/sign.ps1 -Thumbprint A1B2C3D4E5...            # cert in CurrentUser\My
    powershell -File build/sign.ps1 -Thumbprint A1B2... -All             # also sign every _internal *.dll / *.pyd

  Signs (and timestamps) the .exe by default; -All also signs the bundled
  native libraries. Verifies each signature afterwards.
#>
[CmdletBinding()]
param(
    [string] $DistDir = (Join-Path $PSScriptRoot 'dist\Photo-to-IPT Builder'),
    [string] $Pfx,
    [string] $Password,
    [string] $Thumbprint,
    [string] $TimestampUrl = 'http://timestamp.digicert.com',
    [switch] $All
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $DistDir)) { throw "dist folder not found: $DistDir  (run build/build.ps1 first)" }
if (-not $Pfx -and -not $Thumbprint) { throw "supply -Pfx <file> [-Password ...] OR -Thumbprint <sha1>" }

# --- locate signtool.exe ---
$signtool = (Get-Command signtool.exe -EA SilentlyContinue).Source
if (-not $signtool) {
    $signtool = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Recurse -Filter signtool.exe -EA SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } |
        Sort-Object FullName -Descending | Select-Object -First 1 -Expand FullName
}
if (-not $signtool) { throw "signtool.exe not found. Install the Windows 10/11 SDK ('Windows SDK Signing Tools')." }
Write-Host "signtool: $signtool"

# --- files to sign ---
$exe = Get-ChildItem -Recurse -Path $DistDir -Filter 'Photo-to-IPT Builder.exe' | Select-Object -First 1
if (-not $exe) { throw "no Photo-to-IPT Builder.exe under $DistDir" }
$targets = @($exe.FullName)
if ($All) {
    $internal = Join-Path (Split-Path $exe.FullName) '_internal'
    if (Test-Path $internal) {
        $targets += (Get-ChildItem -Recurse -Path $internal -Include *.dll, *.pyd -File).FullName
    }
}
Write-Host ("signing {0} file(s)" -f $targets.Count)

# --- common signtool args ---
$common = @('/fd', 'SHA256', '/tr', $TimestampUrl, '/td', 'SHA256')
if ($Pfx) {
    if (-not (Test-Path $Pfx)) { throw "PFX not found: $Pfx" }
    $common += @('/f', $Pfx)
    if ($Password) { $common += @('/p', $Password) }
} else {
    $common += @('/sha1', $Thumbprint)
}

$failed = @()
foreach ($t in $targets) {
    & $signtool sign @common $t
    if ($LASTEXITCODE -ne 0) { $failed += $t; continue }
    & $signtool verify /pa /q $t
    if ($LASTEXITCODE -ne 0) { $failed += "$t (verify failed)" }
}

Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host ("SIGN: OK  ({0} file(s), timestamped via {1})" -f $targets.Count, $TimestampUrl) -ForegroundColor Green
    & $signtool verify /pa /v $exe.FullName
    exit 0
} else {
    Write-Host "SIGN: FAIL" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  $_" }
    exit 1
}
