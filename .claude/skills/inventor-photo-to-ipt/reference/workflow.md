# Workflow reference

Canonical pipeline (see `docs/spec/02-architecture.md` for the full table):

```
Image Intake -> Visual Feature Analysis -> Measurement Request Generator
  -> [user measures] -> Schema Validator -> Geometry Consistency Validator
  -> CAD Feature Planner -> Inventor API Adapter -> IPT Builder
  -> Verification -> Artifact Report
```

Data-flow contract (never violated):
`PHOTO -> OBSERVATION -> MEASUREMENT REQUEST -> USER MEASUREMENT -> VALIDATED FACT -> CAD FEATURE -> IPT`

## Files per part

```
input/<part>/measurement-request.json   generated (all value: null)
input/<part>/feature-intent.json        generated (structure: params<->measurement ids, feature order)
input/<part>/measurement-input.json     user fills the values
output/<part>/validation-report.json    validator output
output/<part>/cad-plan.json             deterministic feature plan (schema-valid)
output/<part>/cad-plan.md               human-readable plan + parameter map
output/<part>/<part>.ipt                the model
output/<part>/build-log.txt             structured log
output/<part>/build-report.md           PASS/FAIL + parameter map + Inventor result
```

## Commands

```
powershell.exe -NoProfile -File scripts/detect_inventor.ps1
python scripts/validate_measurements.py input/<part>/measurement-input.json --report output/<part>/validation-report.json
python scripts/plan_cad.py --measurements input/<part>/measurement-input.json --intent input/<part>/feature-intent.json --out-dir output/<part>
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/inventor_build.ps1 -PlanPath output/<part>/cad-plan.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/integration_smoke.ps1     # golden fixture E2E
```

## Stop conditions (docs/spec `SAFE-001`)

required measurement null; ambiguous geometry that affects topology; Inventor not
installed; COM connect failure; unsupported feature requested; invalid CAD plan;
inconsistent measurements; output path not writable; missing part template;
Inventor rebuild error; save failure. On any of these: stop, report the reason
and the offending IDs, build nothing approximate.
