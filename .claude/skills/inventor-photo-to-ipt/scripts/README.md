# Skill scripts

The executable helpers for this skill are **not** duplicated here. They live once,
canonically, at the repo root:

```
scripts/detect_inventor.ps1        probe Inventor / COM / interop            (powershell.exe)
scripts/validate_measurements.py   schema + geometry consistency gate        (python)
scripts/plan_cad.py                measurement JSON + intent -> cad-plan      (python)
scripts/inventor_build.ps1         COM build -> .ipt -> verify -> report     (powershell.exe, STA)
scripts/verify_ipt.ps1             reopen + inspect a .ipt                   (powershell.exe)
scripts/lib/*.ps1                  units / json / geometry / feature builders
scripts/_schema_lite.py            bundled JSON-Schema subset (no pip needed)
```

Templates: `../templates/measurement-request.json`
Schemas:   `../../../../schemas/measurement.schema.json`,
           `../../../../schemas/cad-feature-plan.schema.json`
Tests:     `../../../../tests/` (`run_tests.py`, `integration_smoke.ps1`)
