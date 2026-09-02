# Contributing

## Environment

Windows 11 native. Autodesk Inventor 2027 for the build/verify steps; the
validation, planning and determinism tests are pure Python stdlib and run
anywhere.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

`bootstrap.ps1` installs the pinned build deps, runs `doctor.ps1`, then the test
suite + determinism check. Run `scripts/doctor.ps1` on its own any time to check
the environment (Python >= 3.9, Windows PowerShell 5.1 STA, Inventor 2027).

## Tests

```powershell
python tests/run_tests.py                 # non-Inventor unit tests incl. determinism
python scripts/regen_golden.py --check     # cad-plan goldens still match
python tests/gui_smoke.py                 # GUI logic, offscreen (needs PySide6)
powershell -File tests/run_ps_tests.ps1    # Inventor env + integration smoke (needs Inventor 2027)
```

CI (`ci/run_ci.ps1`, GitHub Actions `windows-latest`) runs everything that does
not need Inventor. The Inventor end-to-end checks stay manual.

## Determinism (SYS-001)

Given the same `measurement-input.json` + `feature-intent.json`,
`scripts/plan_cad.py` must emit a **byte-identical** `cad-plan.json` on every run
and across versions. This is enforced by `tests/test_determinism.py` and
`scripts/regen_golden.py --check` against committed goldens in `tests/golden/`.

If you make a change that *intentionally* alters plan output:

```powershell
python scripts/regen_golden.py        # rewrite the goldens
git add tests/golden/                  # commit them with the change
```

A golden diff in a PR that is not explained by an intentional planner change is a
bug. Do not regenerate goldens to make a red test pass without understanding why
the output moved.

## Example fixtures

`tests/fixtures/parts/<part>/` holds a complete worked example (source photo,
`feature-intent.json`, `measurement-input.json`). `polygon_cube` is the current
one - a 100 mm cube with a regular-polygon pocket on each face, built from
`ex.png`. Add a new fixture by dropping the same three files in a new folder and
running `python scripts/regen_golden.py`.

## Scope

Single solid parts (see `README.md` -> Supported scope). Deferred features
(`shell`, `thread`, `work_plane`, `work_axis`) and out-of-scope geometry must
stop and ask for a dimensioned drawing - never an approximate model. Keep
requirement -> JSON field -> parameter -> feature traceability
(`docs/spec/TRACEABILITY.md`).
