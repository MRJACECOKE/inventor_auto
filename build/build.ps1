<#
  build.ps1  -  build the Photo-to-IPT Builder .exe with PyInstaller.

    powershell -File build/build.ps1              # --onedir (default, recommended)
    powershell -File build/build.ps1 -OneFile     # single .exe (bigger, more AV noise)
    powershell -File build/build.ps1 -SkipDeps    # don't pip install first

  Output (kept under build/ so the repo root stays clean):
    --onedir : build/dist/Photo-to-IPT Builder/Photo-to-IPT Builder.exe
    --onefile: build/dist/Photo-to-IPT Builder.exe

  Runs on any shell (pwsh or Windows PowerShell); it only shells out to python.
#>
[CmdletBinding()]
param([switch] $OneFile, [switch] $SkipDeps)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$py = (Get-Command python -ErrorAction Stop).Source
Write-Host "python : $py"

if (-not $SkipDeps) {
    Write-Host "== pip install -r requirements-dev.txt =="
    & $py -m pip install -r (Join-Path $repo 'requirements-dev.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

$distPath = Join-Path $repo 'build\dist'
$workPath = Join-Path $repo 'build\build'

$qtExcludes = @(
    'PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebChannel',
    'PySide6.QtQuick','PySide6.QtQuick3D','PySide6.QtQml','PySide6.Qt3DCore',
    'PySide6.Qt3DRender','PySide6.Qt3DExtras','PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets','PySide6.QtCharts','PySide6.QtDataVisualization',
    'PySide6.QtPdf','PySide6.QtPdfWidgets','PySide6.QtSql','PySide6.QtDesigner',
    'PySide6.QtUiTools','PySide6.QtHelp','PySide6.QtOpenGL','PySide6.QtOpenGLWidgets',
    'PySide6.QtBluetooth','PySide6.QtPositioning','PySide6.QtSensors',
    'PySide6.QtSerialPort','PySide6.QtTest','PySide6.QtNetworkAuth',
    'PySide6.QtScxml','PySide6.QtStateMachine','PySide6.QtTextToSpeech',
    'PySide6.QtHttpServer','tkinter','matplotlib','numpy','PIL'
)

Write-Host "== PyInstaller =="
if ($OneFile) {
    # Rely on the built-in PySide6 hook (only bundles imported Qt modules); do
    # NOT --collect-all PySide6. Mirrors build/IptBuilder.spec.
    $excludeArgs = $qtExcludes | ForEach-Object { '--exclude-module', $_ }
    $iconArgs = @()
    if (Test-Path "$repo\build\app.ico") { $iconArgs = @('--icon', "$repo\build\app.ico", '--add-data', "$repo\build\app.ico;.") }
    & $py -m PyInstaller --noconfirm --clean --windowed --onefile `
        --name "Photo-to-IPT Builder" --distpath $distPath --workpath $workPath `
        --paths "$repo" --paths "$repo\scripts" `
        --add-data "$repo\scripts;scripts" `
        --add-data "$repo\schemas;schemas" `
        --add-data "$repo\docs\guide.html;docs" `
        @iconArgs `
        --hidden-import app --hidden-import app.ipt_builder --hidden-import app.pipeline --hidden-import app.resources `
        --hidden-import _schema_lite --hidden-import validate_measurements --hidden-import plan_cad `
        @excludeArgs `
        "$repo\run_gui.py"
} else {
    & $py -m PyInstaller --noconfirm --clean --distpath $distPath --workpath $workPath `
        "$repo\build\IptBuilder.spec"
}
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host ""
Write-Host "== artifact =="
$exe = Get-ChildItem -Recurse -Path $distPath -Filter 'Photo-to-IPT Builder.exe' |
       Sort-Object Length -Descending | Select-Object -First 1
if (-not $exe) { throw "no .exe produced under $distPath" }
$distRoot = if ($OneFile) { $exe.Directory.FullName } else { $exe.Directory.FullName }

# --- third-party licences (PySide6 / Qt used under LGPL-3.0; ship the texts) ---
$licDir = Join-Path $distRoot 'licenses'
New-Item -ItemType Directory -Force -Path $licDir | Out-Null
$copied = 0
# a) a curated copy checked into the repo (recommended: drop LGPL-3.0.txt here)
if (Test-Path (Join-Path $repo 'build\licenses')) {
    Get-ChildItem -File (Join-Path $repo 'build\licenses') |
        Where-Object { $_.Name -notmatch '^README' } |
        ForEach-Object { Copy-Item -Force $_.FullName $licDir; $copied++ }
}
# b) whatever the installed wheels ship in <pkg>.dist-info/licenses/
$sp = & $py -c "import sysconfig;print(sysconfig.get_paths()['purelib'])"
if ($sp -and (Test-Path $sp)) {
    Get-ChildItem -Path $sp -Directory -EA SilentlyContinue |
        Where-Object { $_.Name -match '^(pyside6|shiboken6).*\.dist-info$' } |
        ForEach-Object {
            $l = Join-Path $_.FullName 'licenses'
            if (Test-Path $l) {
                Get-ChildItem -File $l | ForEach-Object { Copy-Item -Force $_.FullName $licDir; $copied++ }
            }
        }
}
$licList = (Get-ChildItem -File $licDir -EA SilentlyContinue | ForEach-Object { "  - licenses/$($_.Name)" }) -join "`n"
if (-not $licList) { $licList = "  (none bundled - see the warning below)" }
@"
THIRD-PARTY NOTICES - Photo-to-IPT Builder

This application bundles Qt for Python (PySide6) and the Qt libraries, used under
the GNU Lesser General Public License v3.0 (LGPL-3.0). The Qt libraries are
dynamically linked and unmodified.

Bundled licence texts (this folder):
$licList

  LGPL-3.0 canonical : https://www.gnu.org/licenses/lgpl-3.0.txt
  Qt source code     : https://download.qt.io/official_releases/qt/
  PySide6            : https://pypi.org/project/PySide6/

The application code (app/, scripts/, schemas/) belongs to the inventor_auto
project and is not covered by the above.
"@ | Set-Content -Path (Join-Path $distRoot 'THIRD-PARTY-NOTICES.txt') -Encoding UTF8
if ($copied -eq 0) {
    Write-Host "NOTE: no licence text files were bundled - add build/licenses/LGPL-3.0.txt for a local copy." -ForegroundColor Yellow
}

# --- READ ME FIRST.txt : first-run steps for an unsigned build ---
# copied byte-for-byte from a UTF-8 source (a here-string in this BOM-less .ps1
# would be re-decoded as the system ANSI codepage and mangle the Korean text).
$readme = Join-Path $repo 'build\dist-extras\READ ME FIRST.txt'
if (Test-Path $readme) {
    Copy-Item -Force $readme (Join-Path $distRoot 'READ ME FIRST.txt')
} else {
    Write-Host "NOTE: build/dist-extras/READ ME FIRST.txt missing - dist has no first-run note." -ForegroundColor Yellow
}

$hash = (Get-FileHash -Algorithm SHA256 $exe.FullName).Hash
Write-Host ("path   : {0}" -f $exe.FullName)
Write-Host ("size   : {0:N1} MB" -f ($exe.Length / 1MB))
if (-not $OneFile) {
    $folderMB = (Get-ChildItem -Recurse -File $distRoot | Measure-Object Length -Sum).Sum / 1MB
    Write-Host ("folder : {0:N0} MB total" -f $folderMB)
}
Write-Host ("sha256 : {0}" -f $hash)
Write-Host ("licences: {0}" -f $licDir)
Write-Host ""
Write-Host "Unsigned build - recipients unblock once:" -ForegroundColor Green
Write-Host ("  Get-ChildItem -Recurse `"<extract path>`" | Unblock-File   (or SmartScreen: 추가 정보 -> 실행)")
Write-Host "Quick check on this or any target PC:" -ForegroundColor Green
Write-Host ("  `"{0}`" --selftest" -f $exe.FullName)
Write-Host "Distribute the whole 'build\dist\Photo-to-IPT Builder\' folder (zip it) - includes 'READ ME FIRST.txt'." -ForegroundColor Green
