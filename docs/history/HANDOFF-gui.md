# HANDOFF — Photo-to-IPT Builder GUI (.exe)

Continuation doc for a fresh session. **The GUI feature is complete** — steps 1–7
of `.omc/plans/gui-ipt-builder-app.md` + all follow-ups + all polish, done and
verified. The frozen `.exe` is proven end-to-end (`--selftest-build` builds a
real `.ipt`), has an embedded icon, a CI script + workflow, and ships a
`READ ME FIRST.txt`.

**Distribution decision: unsigned** (personal / research use). No code-signing
certificate. Recipients unblock once —
`Get-ChildItem -Recurse "<folder>" | Unblock-File` or SmartScreen
"추가 정보 → 실행". `build/sign.ps1` stays in the repo for later if a cert is
ever obtained. **Nothing is outstanding.**

PRD: `.omc/prd.json` (US-001…US-012, all `passes: true`). Progress:
`.omc/state/progress.txt`.

---

## 1. Current state — everything that works

| Area | Files | Verified by |
|---|---|---|
| Portability | `scripts/lib/inventor_env.ps1`; `inventor_build.ps1` (+ `-OutDir`), `verify_ipt.ps1`, `detect_inventor.ps1` wired | `tests/test_inventor_env.ps1` → **TEST: PASS** (11); `tests/integration_smoke.ps1` → **INTEGRATION: PASS** |
| Headless wrapper | `app/__init__.py`, `app/resources.py`, `app/pipeline.py` | `tests/test_pipeline_wrapper.py` (8); `python tests/run_tests.py` → **Ran 41 tests … OK** |
| GUI | `app/ipt_builder.py` (PySide6), `run_gui.py` entry | `tests/gui_smoke.py` → **15/15 PASS** (offscreen) |
| Packaging | `requirements-dev.txt`, `build/IptBuilder.spec`, `build/build.ps1`, `build/licenses/{LGPL-3.0,GPL-3.0}.txt` | `build/build.ps1` → exit 0, **~115 MB** onedir (from 669 MB); dist ships `THIRD-PARTY-NOTICES.txt` + `licenses/` (LGPL/GPL/Qt-Commercial) |
| Frozen-bundle proof | `app/ipt_builder.py::_selftest` | frozen `"…exe" --selftest` → **SELFTEST: PASS**; `--selftest-build` → launches Inventor 2027, builds + verifies a real `.ipt` (143 872 B), **SELFTEST: PASS** |
| PS test group | `tests/run_ps_tests.ps1` | `test_inventor_env.ps1` + `integration_smoke.ps1` → **PS TESTS: PASS (2 scripts)** |
| Docs | `docs/spec/08-gui-app.md` (GUI-001…009), `docs/spec/06` note, `TRACEABILITY.md` rows, `README.md`, `CLAUDE.md`, `docs/guide.html` §8 | rendered/checked |

### Verify from scratch
```bash
cd C:\Users\user\Desktop\inventor_auto
python tests/run_tests.py                                                              # Ran 41 tests ... OK  (zero-dep)
python tests/gui_smoke.py                                                              # 15/15 PASS (needs PySide6; skips if absent)
python -m app.ipt_builder --selftest-build                                             # SELFTEST: PASS (headless; builds a real .ipt)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/run_ps_tests.ps1         # test_inventor_env + integration_smoke -> PS TESTS: PASS
python -m app.ipt_builder                                                              # real window (needs a display)
powershell -File build\build.ps1                                                       # -> build\dist\Photo-to-IPT Builder\  (~115 MB)
"build\dist\Photo-to-IPT Builder\Photo-to-IPT Builder.exe" --selftest                  # verify the built bundle (any PC)
```

---

## 2. Architecture (unchanged; reference)

```
Claude Code  (사진 첨부 → /inventor-photo-to-ipt)
  → input/<part>/measurement-request.json + feature-intent.json
                    │
Photo-to-IPT Builder.exe   (Phase E–I only; no photo analysis, no API key)
  작업 폴더 선택 → 측정 폼 → 검증 → 플랜 생성 → Inventor 빌드 → .ipt 열기
  치수 바꿔 재빌드 루프 ;  출력 → <작업폴더>/output/<part>/
```

- **validate + plan run in-process** (`app.pipeline` imports
  `validate_measurements` / `plan_cad`; `run_plan` is byte-identical to the CLI).
- **build shells out** to `powershell.exe inventor_build.ps1 -PlanPath <abs>
  -OutDir <abs>` on a `QThread` worker; `취소` → `proc.terminate()` +
  `taskkill /IM Inventor.exe`.
- **Inventor path** is registry-resolved at runtime
  (`scripts/lib/inventor_env.ps1`).
- **Packaging**: `--onedir`; the built-in PySide6 hook (NOT `collect_all`) +
  an `excludes` list of heavy unused Qt modules.

### `app/pipeline.py` public API (stable)
`resolve_paths(part_dir, out_dir=None) -> Paths` ·
`run_validate(paths) -> ValidationResult{ok, schema_errors, geometry_errors, failing_ids, engine}` ·
`run_plan(paths) -> PlanResult{ok, error, plan_path, md_path, features, parameters}` ·
`run_build(paths, on_line=None, on_start=None) -> BuildResult{ok, exit_code, ipt_path, size, bodies, features, report_path, log_tail, summary}` ·
`kill_inventor()` ·
`load_measurement_request(paths) -> dict` ·
`write_measurement_input(paths, {id: number|None}) -> Path` ·
`probe_inventor() -> {usable, file_version?, interop_dll?, note}`

---

## 3. Remaining / optional

- **App icon — DONE.** `build/app.ico` (multi-size, from `build/make_icon.py`) is
  set as the EXE icon (`build/IptBuilder.spec` `icon=`, `build.ps1 -OneFile`
  `--icon`), bundled at `_internal/app.ico`, and applied as the window icon
  (`resources.app_icon_path()` → `QApplication.setWindowIcon`). Verified:
  `ExtractAssociatedIcon` returns an icon from the built exe.
- **Distribution: UNSIGNED — decided.** Personal / research use, no certificate.
  `build/build.ps1` copies `build/dist-extras/READ ME FIRST.txt` (UTF-8 Korean;
  a here-string in the BOM-less `.ps1` mangled it — must stay a separate file)
  into the dist root. Recipients unblock once:
  `Get-ChildItem -Recurse "<folder>" | Unblock-File` (removes Mark-of-the-Web →
  no prompt) or SmartScreen "추가 정보 → 실행". `build/sign.ps1
  -Pfx|-Thumbprint [-All]` is kept in the repo for later if a cert is obtained.
- **Licences — DONE.** `build/licenses/LGPL-3.0.txt` (7 652 B) + `GPL-3.0.txt`
  (35 149 B), verbatim from gnu.org, checked in. `build/build.ps1` copies them
  (+ wheel licence files) into `dist/…/licenses/` and writes
  `THIRD-PARTY-NOTICES.txt` enumerating what shipped.
- **CI — DONE.** `ci/run_ci.ps1` (pip install → `run_tests.py` → `gui_smoke.py` →
  `build/build.ps1 -SkipDeps` → frozen `--selftest`; `CI: PASS`/`FAIL`).
  `.github/workflows/ci.yml` runs it on `windows-latest` + uploads the built app.
  Inventor E2E stays manual via `tests/run_ps_tests.ps1`.

If the dist trim ever regresses (exe won't launch after an `excludes` change):
rebuild with `IPTB_CONSOLE=1 pyinstaller … build/IptBuilder.spec`, run the
console exe (or `--selftest`), read the `ModuleNotFoundError`, remove that name
from the Qt `excludes` in **both** `build/IptBuilder.spec` and
`build/build.ps1`, rebuild.

---

## 4. Gotchas (do not relearn)

1. **Windows PowerShell 5.1 only for Inventor COM.** `pwsh` 7 is MTA →
   `CreateObjectCollection()` returns `null`, `Marshal.GetActiveObject` missing.
   `.ps1` runners hard-block non-STA. `resources.powershell_exe()` returns
   `"powershell.exe"` on purpose.
2. **PowerShell unrolls `IEnumerable` COM objects returned from a function** into
   `Object[]` → next COM call fails `Cannot convert "Object[]" … to "Object"`.
   `scripts/lib/features.ps1`/`geometry.ps1` keep collections in `@{ Coll = … }`
   or read them by property.
3. **In-process import** needs `scripts/` on `sys.path` —
   `app.pipeline` calls `resources.add_scripts_to_syspath()` at import. Frozen:
   PyInstaller bundles `scripts/` as data (spec `datas`) so the `.ps1` files and
   the `.py` modules are both on disk under `_internal/scripts/`.
4. **CLI parity**: `run_plan` must keep calling `plan_cad.build_plan` +
   `plan_cad._write_json`/`_write_md` exactly as the CLI does, or
   `test_pipeline_wrapper.test_wrapper_plan_matches_cli_byte_for_byte` fails.
   `provenance.measurement_file` is literally the path string passed in.
5. **`inventor_build.ps1` output routing**: pass `-OutDir <abs>` or it writes to
   `<repo>/output/<part>` regardless of the working folder. GUI + wrapper pass it.
6. **PyInstaller onedir `sys._MEIPASS`** = `_internal/`; `bundle_dir()` handles
   both onefile and onedir.
7. **Do NOT `collect_all("PySide6")`** — it pulls every Qt module (~670 MB). Use
   the built-in hook + `excludes`. Current build ≈ 116 MB. If you add an exclude
   and the exe stops launching, see §3 last paragraph.
8. **AV / SmartScreen**: default `--onedir` (ship the folder zipped). onefile
   PySide6 re-extracts to `%TEMP%` each launch → worse.
9. **LGPL (PySide6)**: include the licence text in the dist folder before
   distributing.
10. **Fixture has no `measurement-request.json`** — only `measurement-input.json`
    + `feature-intent.json`. `pipeline.base_measurement_file()` falls back to the
    input file. **Copy the fixture to a tempdir before any GUI test** —
    `_do_validate` calls `write_measurement_input` on the loaded folder.
11. **PySide6 offscreen crashes at interpreter teardown on Windows** (cosmetic).
    Test scripts: `sys.stdout.flush(); os._exit(0)` (and flush first — `os._exit`
    skips buffer flush, giving silent runs).
12. **`console=` in the spec** is `os.environ.get("IPTB_CONSOLE") == "1"` — set
    that env var to build a console exe for startup debugging; unset for release.
13. **PyInstaller entry is `run_gui.py`, NOT `app/ipt_builder.py`.** Freezing the
    module directly runs it as `__main__` → `from . import pipeline` fails with
    `attempted relative import with no known parent package`, and with
    `console=False` the crash shows only a modal dialog (looks "alive" to a
    HasExited check — that was a false PASS). The launcher keeps `app` a package.
    `hiddenimports` list `app.*`. **This is fixed and verified** — regression
    guard is `--selftest` (gotcha #15).
14. **`QFontDatabase: Cannot find font directory … _internal/PySide6/lib/fonts`**
    on the built exe is **offscreen-only cosmetic** — Qt no longer ships fonts;
    on a real display it uses the system fonts (Malgun Gothic). Ignore it, or
    bundle DejaVu if a headless render is ever needed.
15. **Verify a bundle with `--selftest`**, not by watching the process.
    `"Photo-to-IPT Builder.exe" --selftest` runs headless: import chain + bundled
    `scripts/`+`schemas/` + in-process validate/plan on a synthetic part →
    `SELFTEST: PASS`/`FAIL`, exit 0/1. `--selftest-build` also drives Inventor.
    This is the deterministic "does the packaged app actually work" check and the
    regression guard for the gotcha #13 class of packaging bug.

---

## 5. Full file inventory (this feature)

```
NEW  scripts/lib/inventor_env.ps1
NEW  app/__init__.py  app/resources.py  app/pipeline.py  app/ipt_builder.py
NEW  run_gui.py        (PyInstaller entry; keeps `app` a real package)
NEW  requirements-dev.txt
NEW  build/IptBuilder.spec  build/build.ps1  build/make_icon.py  build/sign.ps1
NEW  build/app.ico  build/licenses/{README.txt, LGPL-3.0.txt, GPL-3.0.txt}
NEW  build/dist-extras/READ ME FIRST.txt
NEW  ci/run_ci.ps1  .github/workflows/ci.yml
NEW  tests/test_pipeline_wrapper.py  tests/gui_smoke.py
NEW  tests/test_inventor_env.ps1  tests/run_ps_tests.ps1
NEW  docs/spec/08-gui-app.md  docs/guide_ver2.html
NEW  .omc/prd.json  .omc/state/progress.txt  handoff.md
MOD  scripts/inventor_build.ps1   (inventor_env, Get-InventorInteropDll, -OutDir)
MOD  scripts/verify_ipt.ps1       (inventor_env, Get-InventorInteropDll)
MOD  scripts/detect_inventor.ps1  (registry-derived exe + interop_dll)
MOD  docs/spec/06-inventor-automation.md   (inventor_env subsection)
MOD  docs/spec/TRACEABILITY.md             (GUI-001..007 rows, inventor_env under INV-001)
MOD  README.md   (GUI app section, test list, layout)
MOD  CLAUDE.md   (GUI note, Commands block)
MOD  docs/guide.html   (section 8, section 2 note, test count 33->41)
MOD  .gitignore  (build/dist, build/build, dist, *.manifest)
```
`tests/fixtures/simple_plate/measurement-input.json` — unchanged (a mid-run GUI
test briefly reformatted it; restored to the original layout).
