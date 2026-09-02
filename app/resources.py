"""Resolve bundled resources whether running from source or a PyInstaller build.

Frozen (PyInstaller): resources live under ``sys._MEIPASS`` (onefile) or next to
the executable (onedir). Source: they live at the repo root.

The Python validators/planner in ``scripts/`` are imported IN-PROCESS by
``app.pipeline`` (no ``python.exe`` needed on the target), so ``scripts/`` must be
on ``sys.path`` -- call :func:`add_scripts_to_syspath` once at startup.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _repo_root_from_source() -> Path:
    # app/resources.py -> app/ -> <repo root>
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """Directory that holds ``scripts/`` and ``schemas/``.

    Frozen: ``sys._MEIPASS`` if present (onefile), else the executable's folder.
    Source: the repo root.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return _repo_root_from_source()


def scripts_dir() -> Path:
    return bundle_dir() / "scripts"


def schemas_dir() -> Path:
    return bundle_dir() / "schemas"


def schema_path(name: str) -> Path:
    """Absolute path to a JSON schema, e.g. ``schema_path("measurement.schema.json")``."""
    return schemas_dir() / name


def guide_html() -> Path:
    """Best-effort path to docs/guide.html (bundled under docs/ when frozen)."""
    return bundle_dir() / "docs" / "guide.html"


def app_icon_path() -> Path | None:
    """app.ico — bundled at the bundle root when frozen, at build/ in source."""
    for p in (bundle_dir() / "app.ico", _repo_root_from_source() / "build" / "app.ico"):
        if p.is_file():
            return p
    return None


def powershell_exe() -> str:
    """Windows PowerShell 5.1 - the required host for the Inventor COM scripts
    (STA; pwsh 7 is MTA and breaks some COM calls). It is always on PATH on
    Windows 10/11."""
    return "powershell.exe"


_SYSPATH_DONE = False


def add_scripts_to_syspath() -> Path:
    """Put ``scripts/`` on ``sys.path`` so ``import validate_measurements`` /
    ``import plan_cad`` / ``import _schema_lite`` resolve. Idempotent. Returns the
    scripts dir."""
    global _SYSPATH_DONE
    sd = scripts_dir()
    p = str(sd)
    if p not in sys.path:
        sys.path.insert(0, p)
    _SYSPATH_DONE = True
    return sd
