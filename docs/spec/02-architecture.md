# 02 — Architecture

## Pipeline

```
Image Intake
  → Visual Feature Analysis
  → Measurement Request Generator
  → Measurement JSON            (user fills values)
  → Schema Validator
  → Geometry Consistency Validator
  → CAD Feature Planner
  → Inventor API Adapter
  → IPT Builder
  → Verification
  → Artifact Report
```

## Stage responsibilities

| Stage | Implementation | Reads | Writes | May fail with |
|---|---|---|---|---|
| Image Intake | Claude Code chat (SKILL Phase A) | photo path(s) / paste | in-memory image refs | no images |
| Visual Feature Analysis | Claude (SKILL Phase B) | images | IMAGE ANALYSIS block, visual-feature IDs | unsupported family → escalate |
| Measurement Request Generator | Claude (SKILL Phase C) | analysis | `input/<part>/measurement-request.json` | no sensible instruction |
| Measurement JSON | user | request template | `input/<part>/measurement-input.json` | — |
| Schema Validator | `scripts/validate_measurements.py` | `measurement-input.json`, `schemas/measurement.schema.json` | `validation-report.json`, exit code | `MEASUREMENT_VALIDATION_FAILED` |
| Geometry Consistency Validator | same script, `--geometry` | validated JSON | appended report | `MEASUREMENT_VALIDATION_FAILED` |
| CAD Feature Planner | `scripts/plan_cad.py` | validated JSON, analysis intent | `output/<part>/cad-plan.json` + `.md` | `UnboundDimensionError`, `FeatureUnsupportedError`, plan schema fail |
| Inventor API Adapter | `scripts/inventor_build.ps1` + `scripts/lib/*.ps1` | `cad-plan.json` | live Inventor session | `BLOCKED: Inventor COM connect failed` |
| IPT Builder | `scripts/lib/features.ps1` | plan | `output/<part>/<part>.ipt` | `INV-<featureId>` errors |
| Verification | `scripts/verify_ipt.ps1` | `.ipt` path | verification block | FAIL (0 bytes / no body / update errors) |
| Artifact Report | `inventor_build.ps1` (final step) | all of the above | `output/<part>/build-report.md`, `build-log.txt` | — |

## Directory layout

```
inventor_auto/
  docs/spec/                     00..07 + TRACEABILITY.md
  schemas/
    measurement.schema.json
    cad-feature-plan.schema.json
  scripts/
    validate_measurements.py     schema + geometry validation (CLI)
    plan_cad.py                  measurement JSON -> cad-plan.json / .md
    detect_inventor.ps1          COM ProgID + version probe
    inventor_build.ps1           orchestrator: connect -> build -> save -> verify -> report
    verify_ipt.ps1               reopen + inspect a .ipt
    lib/
      units.ps1                  ONE unit-expression helper (INV-003)
      geometry.ps1               profile / point helpers
      features.ps1               per-feature builders (base_extrude ... revolve)
      json.ps1                   plan loader
  .claude/
    skills/inventor-photo-to-ipt/
      SKILL.md
      reference/{workflow,inventor-api,measurement-guide}.md
      templates/measurement-request.json
      scripts/README.md          -> points at repo-root scripts/ (canonical, no duplication)
    agents/inventor-cad-engineer.md
  tests/
    test_validate.py
    test_plan.py
    run_tests.py                 stdlib unittest runner (no pip needed)
    integration_smoke.ps1        Inventor-present E2E on the fixture
    fixtures/simple_plate/
      measurement-input.json
      expected-plan.json
  input/<part>/                  measurement-request.json, measurement-input.json
  output/<part>/                 cad-plan.json, cad-plan.md, <part>.ipt, build-log.txt, build-report.md
  CLAUDE.md                      project rules (Inventor Photo-to-IPT Workflow)
  README.md
```

## Language / runtime split

| Concern | Runtime | Why |
|---|---|---|
| Schema + geometry validation, CAD planning | Python 3.11 | present; easy JSON + math; `jsonschema` optional with bundled fallback |
| Inventor COM automation, `.ipt` verification | Windows PowerShell 5.1 (`powershell.exe`, STA) | only reliable no-install path to `Inventor.Application`; pwsh 7 is MTA and breaks some COM calls |
| Tests (non-Inventor) | Python `unittest` (stdlib) | no pip dependency to run |
| Tests (Inventor) | PowerShell | needs the live COM server |

`inventor_build.ps1` shells out to `python scripts/plan_cad.py` and
`python scripts/validate_measurements.py` so a single command runs the whole
pipeline; each stage is also runnable standalone.

## Determinism rules

- JSON written with sorted keys, `\n` newlines, 2-space indent.
- Feature order = topological sort on `depends_on`, ties broken by feature ID.
- No timestamps inside `cad-plan.json` (timestamps live in `build-report.md` /
  `build-log.txt` only).
- Parameter names derived deterministically from measurement `name`
  (`p_<snake_case>`; collisions get a numeric suffix in ID order).

## Upgrade path (documented, not built)

`tools/InventorCadRunner/` C# project: replace `scripts/lib/*.ps1` with typed
Inventor Interop classes (`UnitConverter`, `BaseExtrudeBuilder`, ...,
`PartVerifier`). `cad-plan.json` is the stable contract between planner and runner,
so the Python side is unchanged. Requires installing the .NET SDK.
