# RUNBOOK - reproduce a build from a clean checkout

Target: a Windows 11 machine with Autodesk Inventor 2027 installed. The
non-Inventor parts (validation, planning, determinism, GUI logic, `.exe` build)
run without Inventor.

## 0. Pinned toolchain

| tool | pinned | why |
|---|---|---|
| OS | Windows 11 (native) | Inventor COM + Windows PowerShell 5.1 |
| Autodesk Inventor | 2027 (major 31) | COM ProgID `Inventor.Application` |
| PowerShell (Inventor steps) | Windows PowerShell 5.1 (`powershell.exe`, STA) | pwsh 7 is MTA; some Inventor COM calls return null there |
| Python | 3.11.7 (`.python-version`); >= 3.9 works for tests | pipeline is stdlib-only |
| PySide6 | 6.11.2 (`requirements-dev.txt`) | GUI + `.exe` build only |
| PyInstaller | 6.15.0 | `.exe` build only |

Resolved dependency closure: `requirements-dev.lock.txt`.

## 1. Clone

```powershell
git clone https://github.com/MRJACECOKE/inventor_auto.git
cd inventor_auto
```

## 2. Bootstrap + environment check

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

Installs the pinned deps, runs `scripts/doctor.ps1`, the test suite, and the
determinism check. Expect `BOOTSTRAP: PASS`.

`doctor.ps1` alone prints a per-check report and ends `DOCTOR: PASS` /
`DOCTOR: FAIL`. Required checks: Python >= 3.9, Windows PowerShell 5.1 STA.
Inventor is reported but not required for tests.

## 3. Non-Inventor verification

```powershell
python tests/run_tests.py                    # unit tests incl. determinism -> "OK"
python scripts/regen_golden.py --check        # -> "regen_golden --check: OK"
powershell -File ci/run_ci.ps1 -NoBuild        # -> "CI: PASS"  (add nothing to also build the .exe)
```

## 4. Inventor end-to-end (needs Inventor 2027)

```powershell
powershell -File tests/run_ps_tests.ps1        # test_inventor_env + integration_smoke -> "PS TESTS: PASS"
```

`integration_smoke.ps1` builds `tests/fixtures/simple_plate` to a verified
`.ipt` at `output/simple_plate/simple_plate.ipt`. Open it in Inventor to eyeball
the result. Add `-Clean` to delete the artifacts afterward.

## 5. Reproduce the polygon_cube example plan

```powershell
python scripts/plan_cad.py `
  --measurements tests/fixtures/parts/polygon_cube/measurement-input.json `
  --intent tests/fixtures/parts/polygon_cube/feature-intent.json `
  --out-dir output/polygon_cube
```

`output/polygon_cube/cad-plan.json` must be byte-identical to
`tests/golden/polygon_cube/cad-plan.json` (that is exactly what the determinism
check asserts). With Inventor present:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/inventor_build.ps1 `
  -PlanPath output/polygon_cube/cad-plan.json
```

`output/polygon_cube/build-report.md` records the environment stamp
(`inventor_auto` version, git commit, Python, PowerShell, OS) alongside the
parameter map and Inventor result. `Result: PASS` is written only after the
`.ipt` is verified on disk.

## 6. Change the plan output on purpose

Determinism means an intentional planner change breaks the goldens. Regenerate
and commit them with the change:

```powershell
python scripts/regen_golden.py
git add tests/golden/
```

## 7. Bump the toolchain

Edit `.python-version` / `requirements-dev.txt` / `VERSION`, then:

```powershell
python -m pip install -r requirements-dev.txt
python -m pip freeze          # update requirements-dev.lock.txt by hand from this
powershell -File scripts/bootstrap.ps1
```
