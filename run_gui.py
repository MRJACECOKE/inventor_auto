#!/usr/bin/env python3
"""Launcher for the Photo-to-IPT Builder GUI.

Kept at the repo root so `app` stays a proper package for both source runs and
the PyInstaller build (freezing `app/ipt_builder.py` directly would run it as
`__main__` and break its `from . import ...`).

    python run_gui.py
    python -m app.ipt_builder      # also works
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ipt_builder import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
