# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses simple
[SemVer](https://semver.org/) on the `VERSION` file.

## [0.1.0] - 2026-09-02

Initial public release.

### Pipeline
- Photo-to-IPT engineering agent for Autodesk Inventor 2027: structure from
  photos, every real dimension from a user-supplied `measurement-input.json`
  (single source of truth). Validate (schema + geometry) -> deterministic
  feature plan -> Inventor COM build -> on-disk `.ipt` verification -> report.
- `inventor-photo-to-ipt` skill and `inventor-cad-engineer` agent under
  `.claude/`.
- Engineering spec suite `docs/spec/00..08` + `TRACEABILITY.md`.
- PySide6 GUI (`app/ipt_builder.py`) covering Phase E-I, with a PyInstaller
  `--onedir` build (`build/build.ps1`).

### Reproducibility
- Golden determinism tests (`tests/test_determinism.py`,
  `scripts/regen_golden.py`) pinning `cad-plan.json` byte-output to a committed
  golden for the `polygon_cube` example fixture (photo + measurements included
  under `tests/fixtures/parts/`).
- Pinned build environment: `.python-version` (3.11.7),
  `requirements-dev.txt` (`==`), `requirements-dev.lock.txt` (resolved
  closure), `pyproject.toml`.
- `scripts/doctor.ps1` (environment check) and `scripts/bootstrap.ps1`
  (pinned install -> doctor -> tests -> determinism check).
- Build reports (`build-report.md` / `build-log.txt`) now stamp
  `inventor_auto` version, git commit, Python, PowerShell and OS.
- CI (`ci/run_ci.ps1`, `.github/workflows/ci.yml`) runs the determinism check;
  Inventor end-to-end stays manual (`tests/run_ps_tests.ps1`).
