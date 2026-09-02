# PyInstaller spec for the Photo-to-IPT Builder GUI (--onedir).
#
#   pyinstaller --noconfirm --clean --distpath build/dist --workpath build/build build/IptBuilder.spec
#
# Produces build/dist/Photo-to-IPT Builder/Photo-to-IPT Builder.exe
# For a single-file .exe instead, use  build/build.ps1 -OneFile  (CLI flags).
#
# onedir is the default: a onefile PySide6 .exe is large and re-extracts to
# %TEMP% on every launch, which trips SmartScreen / AV on colleague PCs more
# often. Ship the folder zipped.
#
# We do NOT collect_all("PySide6") - that pulls every Qt module (~670 MB). The
# built-in PyInstaller PySide6 hook bundles only what is imported (QtCore /
# QtGui / QtWidgets + the platform plugin). `excludes` below drops the heavy
# optional Qt modules PyInstaller might otherwise follow. Target: ~90-150 MB.

import os

REPO = os.path.abspath(os.path.join(os.path.dirname(SPEC), os.pardir))

ICON = os.path.join(REPO, "build", "app.ico")

datas = [
    (os.path.join(REPO, "scripts"), "scripts"),
    (os.path.join(REPO, "schemas"), "schemas"),
    (os.path.join(REPO, "docs", "guide.html"), "docs"),
]
if os.path.isfile(ICON):
    datas.append((ICON, "."))          # so the running app can set its window icon

hiddenimports = [
    # the GUI package (entry is run_gui.py so `app` stays a real package)
    "app", "app.ipt_builder", "app.pipeline", "app.resources",
    # imported dynamically by app.pipeline (PyInstaller can't see these)
    "_schema_lite",
    "validate_measurements",
    "plan_cad",
]

excludes = [
    "tkinter", "matplotlib", "numpy", "PIL", "pandas", "scipy", "IPython",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtWebView",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets", "PySide6.QtQml",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtGraphsWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtSql", "PySide6.QtDesigner", "PySide6.QtUiTools", "PySide6.QtHelp",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSerialBus",
    "PySide6.QtTest", "PySide6.QtNetworkAuth", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
    "PySide6.QtHttpServer", "PySide6.QtConcurrent", "PySide6.Qt3DQuick",
]

a = Analysis(
    [os.path.join(REPO, "run_gui.py")],
    pathex=[REPO, os.path.join(REPO, "scripts")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Photo-to-IPT Builder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=(os.environ.get("IPTB_CONSOLE") == "1"),   # GUI: no console; set IPTB_CONSOLE=1 to debug startup
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=(ICON if os.path.isfile(ICON) else None),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Photo-to-IPT Builder",
)
