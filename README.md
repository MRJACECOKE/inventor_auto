# inventor_auto - Photo-to-IPT engineering agent for Autodesk Inventor 2027

[![CI](https://github.com/MRJACECOKE/inventor_auto/actions/workflows/ci.yml/badge.svg)](https://github.com/MRJACECOKE/inventor_auto/actions/workflows/ci.yml)
&nbsp;MIT licensed &nbsp;·&nbsp; `VERSION` 0.1.0

Turn photographs of a real mechanical part into a **parametric, verified Autodesk
Inventor 2027 `.ipt`** - without ever guessing a dimension from a photo.

- Photos are used only for **structure**: topology, faces, holes, slots,
  symmetry, patterns, datum candidates.
- Every real length / diameter / radius / depth / angle / position comes from a
  **measurement JSON you fill in** after measuring the part. That JSON is the
  single source of truth.
- The system validates (JSON Schema + engineering consistency), builds a
  deterministic feature plan, drives Inventor over COM, saves the `.ipt`, and
  verifies it on disk.

Design basis: gstack `/office-hours` (author's local design doc). The
authoritative, in-repo spec is `docs/spec/` (00..08 + `TRACEABILITY.md`).
Reproducing a build from a clean checkout: `docs/RUNBOOK.md`.

## Requirements

| need | detail |
|---|---|
| OS | Windows (native) |
| Inventor | Autodesk Inventor 2027, COM ProgID `Inventor.Application` registered |
| PowerShell | **Windows PowerShell 5.1 (`powershell.exe`)** for Inventor steps - it is STA; `pwsh` 7 is MTA and breaks Inventor COM |
| Python | 3.9+ (no pip packages required) |

Probe your machine:

```bash
powershell.exe -NoProfile -File scripts/detect_inventor.ps1
```

## Use it (via Claude Code)

**STEP 1** Run Claude Code in this project.

**STEP 2** Invoke the skill: `/inventor-photo-to-ipt`

**STEP 3** Attach one or more photos (front / rear / left / right / top help).
Say: `Make this part into an Inventor 2027 .ipt.`

**STEP 4** Claude analyses **structure only** and writes
`input/<part>/measurement-request.json` (every `value` is `null`) plus
`input/<part>/feature-intent.json`.

**STEP 5** Measure the real part (calipers, depth gauge, protractor, radius
gauge). Replace each `null` with a number - keep the `unit`:

```json
{ "id": "M004", "name": "hole_dia", "value": 8.0, "unit": "mm", "type": "length", "required": true,
  "measurement_instruction": "Inner diameter of the through hole with calipers.", "related_visual_feature": "VF-HOLE-001" }
```

**STEP 6** Give the filled JSON back to Claude (paste or file path) as
`input/<part>/measurement-input.json`.

**STEP 7** Validation:

```bash
python scripts/validate_measurements.py input/<part>/measurement-input.json --report output/<part>/validation-report.json
```

Failures print `MEASUREMENT_VALIDATION_FAILED` with the offending IDs. Fix and
resubmit. Nothing is built until this passes.

**STEP 8** Feature plan:

```bash
python scripts/plan_cad.py --measurements input/<part>/measurement-input.json --intent input/<part>/feature-intent.json --out-dir output/<part>
```

Produces `output/<part>/cad-plan.json` (+ `cad-plan.md`).

**STEP 9-10** Build in Inventor 2027:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/inventor_build.ps1 -PlanPath output/<part>/cad-plan.json
```

**STEP 11** Result:

```
output/<part>/<part>.ipt          the model
output/<part>/build-report.md     PASS/FAIL, parameter map, Inventor result
output/<part>/build-log.txt       structured per-step log
```

`Result: PASS` is written only after the `.ipt` is verified (exists, `.ipt`,
size > 0, PartDocument, >= 1 solid body, no unhealthy features).

## GUI app (Photo-to-IPT Builder)

After the one-time Claude Code analysis (STEP 1-4 above), the deterministic part
(STEP 7-11: validate -> plan -> Inventor build -> verify -> report) can be run
from a desktop app instead of the CLI - handy for iterating dimensions.

- Code: `app/ipt_builder.py` (PySide6). Spec: `docs/spec/08-gui-app.md`.
- Scope: **Phase E-I only.** It consumes the `input/<part>/` folder Claude Code
  produced (`measurement-request.json` + `feature-intent.json`); it does **not**
  analyse photos and needs no API key.
- Run from source: `pip install -r requirements-dev.txt` then
  `python -m app.ipt_builder`.
- Build a distributable `.exe`:

```bash
powershell -File build/build.ps1
```

  -> `build/dist/Photo-to-IPT Builder/` (an `--onedir` bundle ~115 MB; zip and
  share the folder). `-OneFile` for a single `.exe`. Each target PC still needs
  Inventor 2027; the Inventor path is resolved from the registry at runtime.
- Verify a bundle on any PC (no window):
  `"Photo-to-IPT Builder.exe" --selftest` (add `-build` to also drive Inventor)
  -> `SELFTEST: PASS`.
- Icon: `python build/build.ps1` picks up `build/app.ico` (regenerate with
  `python build/make_icon.py`).
- Unsigned build is fine for personal/research use. `build.ps1` drops a
  `READ ME FIRST.txt` in the dist folder; recipients unblock once with
  `Get-ChildItem -Recurse "<folder>" | Unblock-File` (or SmartScreen "More info
  -> Run anyway"). To sign later (cert required):
  `powershell -File build/sign.ps1 -Pfx <cert.pfx> -Password <pw>`.
- CI (non-Inventor): `powershell -File ci/run_ci.ps1` (`.github/workflows/ci.yml`
  runs it on `windows-latest`). Inventor E2E stays manual:
  `powershell -File tests/run_ps_tests.ps1`.
- In the app: `작업 폴더 선택` -> the `input/<part>/` folder -> fill the values
  column -> `검증` -> `플랜 생성` -> `Inventor 빌드` -> `.ipt 열기`. Output goes
  to `<working folder>/output/<part>/`. Change a number and rebuild.

## Prove the pipeline (no photo needed)

```bash
python tests/run_tests.py                                                            # non-Inventor tests incl. determinism (pipeline + GUI wrapper)
python scripts/regen_golden.py --check                                               # committed cad-plan goldens still match
python tests/gui_smoke.py                                                            # GUI logic, offscreen (needs PySide6; skips if absent)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test_inventor_env.ps1  # registry-resolves the Inventor install
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/integration_smoke.ps1  # builds the simple_plate fixture E2E
```

The smoke keeps its output: open `output/simple_plate/simple_plate.ipt` after it
passes. Add `-Clean` to delete the fixture artifacts afterward (for CI).

## Reproducibility

Given the same `measurement-input.json` + `feature-intent.json`, the planner emits
a **byte-identical** `cad-plan.json` every run and across versions (SYS-001).
That is pinned to a committed golden for the `polygon_cube` example
(`tests/fixtures/parts/polygon_cube/` carries the photo + measurements;
`tests/golden/polygon_cube/cad-plan.json` is the expected output).
`tests/test_determinism.py` and `python scripts/regen_golden.py --check` enforce
it; CI runs the check.

One-shot environment setup and check:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1   # pinned install -> doctor -> tests -> determinism
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/doctor.ps1      # environment check only -> DOCTOR: PASS/FAIL
```

Pinned toolchain: `.python-version` (3.11.7), `requirements-dev.txt` (`==`),
`requirements-dev.lock.txt` (resolved closure). Every build report
(`build-report.md` / `build-log.txt`) stamps the `inventor_auto` version, git
commit, Python, PowerShell and OS. Full fresh-machine steps: `docs/RUNBOOK.md`.
Intentionally changing plan output: `python scripts/regen_golden.py` then commit
`tests/golden/`.

## Supported scope (MVP)

Single solid part: plate, bracket, spacer, flange, block, shaft-like revolved
part, simple housing / mount, bolt-pattern plate/flange.

Features (implemented + tested): `base_extrude`, `extrude_add`, `extrude_cut`,
`revolve`, `hole`, `slot`, `fillet`, `chamfer`, `mirror`, `rectangular_pattern`,
`circular_pattern`.

Deferred (explicit "unsupported" error): `shell`, `thread`, `work_plane`,
`work_axis`.

Out of scope - the pipeline asks for a dimensioned drawing or spec instead:
free-form / organic / cast irregular surfaces, hidden internal structure, gear
tooth profiles without a spec, threads without a thread standard, precision-fit
decisions without tolerances.

## Layout

```
docs/spec/        00..08 + TRACEABILITY.md  (built on the office-hours design doc)
docs/RUNBOOK.md   reproduce a build from a clean checkout
schemas/          measurement.schema.json, cad-feature-plan.schema.json
scripts/          validate_measurements.py, plan_cad.py, regen_golden.py,
                  doctor.ps1, bootstrap.ps1, *.ps1, lib/*.ps1 (incl. inventor_env.ps1)
app/              ipt_builder.py (PySide6 GUI), pipeline.py, resources.py
build/            IptBuilder.spec, build.ps1   (PyInstaller -> build/dist/)
.claude/          README.md + skills/inventor-photo-to-ipt/ + agents/inventor-cad-engineer.md
tests/            run_tests.py, test_determinism.py, integration_smoke.ps1,
                  fixtures/simple_plate/, fixtures/parts/<part>/, golden/<part>/
input/<part>/     measurement-request.json, feature-intent.json, measurement-input.json
output/<part>/    cad-plan.*, <part>.ipt, build-log.txt, build-report.md
VERSION           SemVer; stamped into every build report
```
