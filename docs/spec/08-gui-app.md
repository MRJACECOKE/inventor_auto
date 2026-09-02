# 08 — GUI App (Photo-to-IPT Builder)

A Windows desktop front-end over the **Phase E–I** pipeline
(validate → plan → Inventor build → verify → report). Photo → structure
(Phase A–C) stays in Claude Code; the app consumes the `input/<part>/` folder it
produces.

- Code: `app/ipt_builder.py` (PySide6 GUI), `app/pipeline.py` (headless wrapper),
  `app/resources.py` (path/resource resolution).
- Packaging: `build/IptBuilder.spec`, `build/build.ps1`, `requirements-dev.txt`.
- Tests: `tests/test_pipeline_wrapper.py` (8, zero-dep), `tests/gui_smoke.py`
  (offscreen, needs PySide6), `tests/test_inventor_env.ps1` (Inventor present).

Requirement IDs: `GUI-###`.

---

## GUI-001 — Scope is Phase E–I only
- **Requirement:** The app never analyses photographs and never calls an LLM/API.
  It edits measurements, validates, plans, builds in Inventor, verifies, reports.
  It requires a `feature-intent.json` produced upstream by Claude Code
  (`/inventor-photo-to-ipt`).
- **Rationale:** Photo → structure is a conversational/vision task; a plain
  offline `.exe` cannot do it trustworthily. Keeps the binary small, no key.
- **Input:** `input/<part>/measurement-request.json` (+ `feature-intent.json`)
  from Claude Code; user-entered numbers.
- **Output:** `output/<part>/{validation-report.json, cad-plan.json, cad-plan.md,
  <part>.ipt, build-log.txt, build-report.md}`.
- **Acceptance:** With `feature-intent.json` absent, the right dock shows the
  Claude Code empty-state message and `플랜 생성` / `Inventor 빌드` stay disabled
  (`tests/gui_smoke.py` "no feature-intent" checks).
- **Failure behavior:** Missing measurement files → warning dialog, no crash.
- **Traceability:** `app/ipt_builder.py::MainWindow._load_intent`,
  `_refresh_enabled`; `app/pipeline.py::Paths.has_feature_intent`.

## GUI-002 — Working-folder convention, absolute paths
- **Requirement:** The user picks the **part folder** (`…/input/<part>/`). Output
  goes to `<working_root>/output/<part>/` where `working_root` is the grandparent
  when the picked folder's parent is named `input`, else `part_dir.parent`. Every
  path handed to a script is absolute; the Inventor runner is called with
  `-OutDir <abs>`.
- **Rationale:** The `.exe` runs from anywhere on any machine; nothing may depend
  on CWD or the repo layout.
- **Acceptance:** `tests/test_pipeline_wrapper.py::ResolvePathsTests`
  (`input` convention + `out_dir` override); relocation check — copy the built
  app + an `input/<part>/` folder elsewhere, validate + plan + build still write
  to the sibling `output/<part>/`.
- **Traceability:** `app/pipeline.py::resolve_paths`;
  `scripts/inventor_build.ps1` `-OutDir` param.

## GUI-003 — Portability contract
- **Requirement:**
  - Inventor is resolved at runtime via `scripts/lib/inventor_env.ps1`
    (`Get-InventorInteropDll` — registry `Inventor.Application\CLSID` →
    `LocalServer32` → interop DLL; hardcoded 2027 fallback). No install path is
    hardcoded in the runner/feature builders.
  - The Inventor scripts run under **Windows PowerShell 5.1**
    (`powershell.exe`, STA) — always present on Win10/11.
    `resources.powershell_exe()` returns `"powershell.exe"` deliberately;
    `pwsh` 7 is MTA and breaks Inventor COM.
  - Each target PC still needs Autodesk Inventor 2027 installed.
- **Acceptance:** `tests/test_inventor_env.ps1` — `Get-InventorInteropDll` returns
  a `Test-Path`-true path equal to `detect_inventor.ps1`'s JSON `interop_dll`.
  App startup runs `detect_inventor.ps1`; env chip is green (`Inventor <v> 감지됨`)
  or red (`Inventor 미감지`, tooltip = the note) and `Inventor 빌드` is disabled
  while red.
- **Failure behavior:** COM connect / interop resolution failure → the runner
  prints `BLOCKED: …`; the app surfaces it in the log and status line, no partial
  `.ipt`.
- **Traceability:** `scripts/lib/inventor_env.ps1`;
  `app/pipeline.py::probe_inventor`; `app/ipt_builder.py::_probe_done`.

## GUI-004 — In-process validate/plan, out-of-process build
- **Requirement:** `run_validate` / `run_plan` **import**
  `scripts/validate_measurements.py` / `scripts/plan_cad.py` and call their
  functions in-process (no `python.exe` on the target). `run_build` shells to
  `powershell.exe inventor_build.ps1`. `run_plan` output is byte-identical to the
  `plan_cad.py` CLI.
- **Rationale:** One dependency (`powershell.exe`) on the target instead of a
  Python install; deterministic parity with the CLI/spec.
- **Acceptance:**
  `tests/test_pipeline_wrapper.py::PlanParityTests.test_wrapper_plan_matches_cli_byte_for_byte`;
  `run_validate` flags `M004` for `hole_dia >= face span`.
- **Traceability:** `app/pipeline.py::{run_validate,run_plan,run_build}`;
  `app/resources.py::add_scripts_to_syspath`.

## GUI-005 — Build UX (threading, cancel, non-blocking)
- **Requirement:** The Inventor build runs on a `QThread` worker; stdout lines
  stream into the log pane live; the window stays responsive; `취소` terminates
  the child process and any Inventor it launched (`taskkill /IM Inventor.exe /F`).
- **Acceptance:** `tests/gui_smoke.py` exercises the model/gating;
  manual checklist item "cancel mid-build" (below).
- **Traceability:** `app/ipt_builder.py::{BuildWorker,_do_build,_cancel_build}`;
  `app/pipeline.py::{run_build(on_start=…),kill_inventor}`.

## GUI-006 — Measurement form fidelity
- **Requirement:** One row per `measurements[*]`; only `value` is editable; saving
  writes `measurement-input.json` changing only `measurements[*].value`,
  preserving order and every other field/key (`ensure_ascii=False`, `\n`).
  Invalid rows (from `run_validate.failing_ids`) get a red background.
- **Acceptance:**
  `tests/test_pipeline_wrapper.py::MeasurementFormTests` (round-trip preserves
  `id/name/unit/type/required/measurement_instruction`, `None → null`);
  `tests/gui_smoke.py` "M004 row flagged".
- **Traceability:** `app/ipt_builder.py::MeasurementModel`;
  `app/pipeline.py::{load_measurement_request,write_measurement_input}`.

## GUI-007 — Packaging
- **Requirement:** `build/IptBuilder.spec` builds a **`--onedir`** bundle:
  `datas` = `scripts/` + `schemas/` + `docs/guide.html`; `hiddenimports` =
  `_schema_lite, validate_measurements, plan_cad`; `collect_all("PySide6")` minus
  an `excludes` list of unused Qt modules; `console=False`. `build/build.ps1`
  installs dev deps, runs PyInstaller (spec, or `-OneFile` via CLI flags), prints
  the artifact path / size / SHA-256. Artifacts land under `build/dist/` +
  `build/build/` (both git-ignored).
- **Rationale:** `--onedir` avoids the `%TEMP%` re-extract and the heavier
  SmartScreen/AV behaviour of a ~onefile PySide6 `.exe`. Ship the folder zipped.
- **Acceptance:** `powershell -File build/build.ps1` exits 0 and produces
  `build/dist/Photo-to-IPT Builder/Photo-to-IPT Builder.exe`; `_internal/` holds
  `scripts/` (incl. `lib/inventor_env.ps1`), `schemas/`, `docs/guide.html`; the
  exe launches and survives startup (Qt + `MainWindow` + frozen `app.pipeline`
  import). Target dist size ≤ ~180 MB after `excludes`.
- **Traceability:** `build/IptBuilder.spec`, `build/build.ps1`,
  `requirements-dev.txt`, `.gitignore`.

## GUI-008 — Redistribution
- **Requirement:** `build/build.ps1` writes `THIRD-PARTY-NOTICES.txt` next to the
  `.exe` (enumerating the bundled licence files) and copies licence texts into
  `dist/…/licenses/` — from `build/licenses/` (`LGPL-3.0.txt` + `GPL-3.0.txt`,
  verbatim, checked in) and from the installed `pyside6*/shiboken6*`
  `.dist-info/licenses/`. Target PCs need Inventor 2027.
- **Icon:** `build/app.ico` (multi-size, generated by `build/make_icon.py`) is set
  as the EXE icon (spec `icon=`), bundled at the frozen bundle root, and applied
  as the window icon (`QApplication.setWindowIcon`, `resources.app_icon_path()`).
- **Unsigned distribution (personal / research):** `build/build.ps1` drops
  `READ ME FIRST.txt` in the dist root with the first-run unblock steps —
  `Get-ChildItem -Recurse "<folder>" | Unblock-File` (removes Mark-of-the-Web →
  no prompt) or SmartScreen "추가 정보 → 실행" (once per file). This is the
  expected path when no code-signing certificate is available.
- **Signing (optional, cert required):** `build/sign.ps1 -Pfx … | -Thumbprint …`
  runs `signtool sign /fd SHA256 /tr <ts>` on the `.exe` (`-All` also signs the
  bundled `*.dll`/`*.pyd`) and verifies. No certificate ships with the project.
- **Traceability:** `build/build.ps1` licence + icon args; `build/make_icon.py`;
  `build/sign.ps1`; `build/licenses/`.

## GUI-010 — CI (non-Inventor)
- **Requirement:** `ci/run_ci.ps1` runs everything that does not need Inventor —
  `pip install -r requirements-dev.txt`, `python tests/run_tests.py`,
  `python tests/gui_smoke.py`, `build/build.ps1 -SkipDeps`, and frozen
  `"…exe" --selftest` — and exits non-zero on any failure (`CI: PASS`/`FAIL`).
  `.github/workflows/ci.yml` runs it on `windows-latest` and uploads the built
  app as an artifact.
- **Not in CI:** `tests/integration_smoke.ps1`, `tests/test_inventor_env.ps1`,
  `--selftest-build` — these need Inventor 2027 and stay manual (run via
  `tests/run_ps_tests.ps1` on a lab machine).
- **Traceability:** `ci/run_ci.ps1`, `.github/workflows/ci.yml`.

## GUI-009 — Self-test (`--selftest` / `--selftest-build`)
- **Requirement:** `run_gui.py --selftest` (and the built
  `Photo-to-IPT Builder.exe --selftest`) runs headless — no window: verifies the
  import chain, that the bundled `scripts/` + `schemas/` resolve, and runs
  `run_validate` + `run_plan` on a synthetic 3-measurement plate; prints
  `SELFTEST: PASS`/`FAIL`, exit 0/1. `--selftest-build` additionally drives the
  Inventor build (skipped with a pass note when Inventor is not usable).
- **Rationale:** a one-command "does this bundle actually work" check that runs on
  any target PC after copying the folder — catches missing-data / broken-import
  packaging regressions that a GUI launch hides behind a modal dialog.
- **Acceptance:** on this machine, frozen
  `"Photo-to-IPT Builder.exe" --selftest` → `SELFTEST: PASS` exit 0;
  `--selftest-build` → builds + verifies a real `.ipt`, `SELFTEST: PASS`.
- **Traceability:** `app/ipt_builder.py::{_selftest,main}`.

---

## Manual GUI checklist (run once per meaningful change)

Prereq: `pip install -r requirements-dev.txt`; Inventor 2027 installed.

1. **Launch** `python -m app.ipt_builder` (or the built `.exe`). Window opens; the
   env chip reads **`Inventor 2027 (…​) 감지됨`** (green) within a few seconds.
2. **Load** `작업 폴더 선택` → a copy of `tests/fixtures/simple_plate`
   (copy first — the app writes `measurement-input.json` there). Table shows 7
   rows; right dock lists `F001 base_extrude / F002 hole / F003 fillet`.
3. **검증** → status `검증 통과`, log `MEASUREMENT_VALIDATION_OK`. `플랜 생성`
   becomes enabled.
4. **플랜 생성** → `cad-plan.json` + `cad-plan.md` written to
   `…/output/simple_plate/`; log shows the plan; `Inventor 빌드` enabled.
5. **Inventor 빌드** → Inventor launches (visible), log streams
   `[INFO] F001 …` etc., ends `Result: PASS`; status shows
   `BUILD PASS — … 1 body, 3 features`. `.ipt 열기` / `리포트 열기` enabled.
6. **`.ipt 열기`** opens `simple_plate.ipt` in Inventor.
7. **Edit → invalidate:** set `hole_dia` (M004) = `80` → **검증** → status shows
   the failure, the M004 row turns red, `플랜 생성` / `Inventor 빌드` disable.
   Restore to `8`, re-validate, OK again.
8. **Empty state:** load a folder that has `measurement-input.json` but **no**
   `feature-intent.json` → right dock shows the "Claude Code에서 …
   /inventor-photo-to-ipt … 먼저 실행" message; `플랜 생성` stays disabled.
9. **Cancel mid-build:** start `Inventor 빌드`, click `취소` before it finishes →
   log shows `[취소 요청]`, the process stops, no `Result: PASS`, no Inventor left
   running.
10. **Relocation:** copy the built `dist/Photo-to-IPT Builder/` folder + a copy of
    an `input/<part>/` folder to another directory; repeat steps 2–5 there — the
    `.ipt` lands in that folder's sibling `output/<part>/`.

## Automated coverage

| Check | Where |
|---|---|
| resolve_paths, validate parity, plan CLI byte-parity, form round-trip | `tests/test_pipeline_wrapper.py` (in `python tests/run_tests.py`) |
| GUI model + gating + empty state + row flagging (offscreen) | `tests/gui_smoke.py` |
| `Get-InventorInteropDll` == `detect_inventor.ps1` interop_dll, file exists | `tests/test_inventor_env.ps1` |
| full Inventor E2E on the fixture | `tests/integration_smoke.ps1` |
