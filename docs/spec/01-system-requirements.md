# 01 — System Requirements

Requirement IDs are stable. Each requirement lists: requirement, rationale, input,
output, acceptance criteria, failure behavior, traceability.

Prefixes: `SYS` system, `IMG` image analysis, `MEAS` measurement, `CAD` feature
plan, `INV` Inventor automation, `VAL` validation, `SAFE` failure-safety,
`REP` reporting.

---

## SYS — System

### SYS-001 — Deterministic, rerunnable pipeline
- **Requirement:** Given the same source images identifier set and the same
  measurement JSON, the pipeline produces the same CAD plan and an equivalent
  `.ipt` feature tree on every run.
- **Rationale:** Specification-driven engineering; the user must be able to edit
  the JSON and regenerate.
- **Input:** `measurement-input.json`, part name.
- **Output:** `cad-plan.json`, `<part>.ipt`, `build-report.md`.
- **Acceptance:** Two consecutive runs from the same inputs yield byte-identical
  `cad-plan.json` (after key sort) and the same feature count / body count in the
  `.ipt`.
- **Failure behavior:** If nondeterminism is detected in tests, the build is a
  FAIL.
- **Traceability:** `scripts/plan_cad.py`, `scripts/inventor_build.ps1`,
  `tests/test_plan.py`.

### SYS-002 — Photo/measurement separation
- **Requirement:** No real length, diameter, radius, depth, angle, or position
  dimension may originate from image analysis. All such values come from the
  measurement JSON.
- **Rationale:** Premise 1. Photographs cannot yield trustworthy dimensions.
- **Input:** Images (structure only), measurement JSON (facts).
- **Output:** Image analysis block with zero committed dimensions; CAD parameters
  sourced only from measurement IDs.
- **Acceptance:** Every `parameters[*]` entry in `cad-plan.json` has a
  `measurement_id` or a `derivation` referencing measurement IDs. No numeric
  literal appears as a feature dimension without a bound parameter.
- **Failure behavior:** Planner raises `UnboundDimensionError` and stops.
- **Traceability:** `scripts/plan_cad.py`, `docs/spec/03-image-analysis-contract.md`,
  `tests/test_plan.py::test_no_unbound_dimensions`.

### SYS-003 — Provenance recorded
- **Requirement:** Every output artifact records the source image identifiers/paths
  and the measurement JSON path + hash.
- **Rationale:** Traceability; reproducibility.
- **Input:** image list, measurement JSON.
- **Output:** `provenance` block in `cad-plan.json` and a section in
  `build-report.md`.
- **Acceptance:** `cad-plan.json.provenance.measurement_sha256` matches the input
  file hash; `source_images[*].id` are all present.
- **Failure behavior:** Planner stops if provenance cannot be computed.
- **Traceability:** `scripts/plan_cad.py`, `tests/test_plan.py`.

---

## IMG — Image analysis

### IMG-001 — Structure-only observation
- **Requirement:** Image analysis output contains only: component-type hypothesis,
  visible faces, detected geometric primitives, holes, axes, symmetry, feature
  relationships, occluded regions, ambiguous features, required-measurement list,
  and a per-observation confidence.
- **Rationale:** Premise 1; SYS-002.
- **Input:** one or more photographs.
- **Output:** structured IMAGE ANALYSIS text block + `measurement-request.json`.
- **Acceptance:** Output contains no `mm`/`cm`/`in` numeric dimension assertions;
  every visual feature has a stable ID (`VF###` or `VF-<KIND>-###`); every entry
  has a confidence.
- **Failure behavior:** If the part cannot be resolved to a supported family, the
  analysis states the ambiguity and requests more views or a drawing; no
  measurement request for unsupported geometry.
- **Traceability:** `.claude/skills/inventor-photo-to-ipt/SKILL.md` Phase B,
  `docs/spec/03-image-analysis-contract.md`.

### IMG-002 — Multi-view registration
- **Requirement:** When multiple images are supplied, the same physical feature
  seen in multiple views is given one shared visual-feature ID; uncertain matches
  are left separate and flagged.
- **Rationale:** Consistent measurement requests; avoid double-counting features.
- **Input:** multiple photographs with view hints (front/rear/left/right/top/
  bottom/perspective).
- **Output:** visual-feature table with view coverage per ID.
- **Acceptance:** No feature ID is silently merged across views without a
  confidence ≥ 0.7 note; unmatched features remain distinct.
- **Failure behavior:** Ambiguous correspondence is reported, not guessed.
- **Traceability:** SKILL.md Phase B, `docs/spec/03-image-analysis-contract.md`.

---

## MEAS — Measurement

### MEAS-001 — Measurement request generation
- **Requirement:** For each dimension the CAD build needs, emit a measurement
  entry with: `id`, `name`, `type`, `unit`, `required`, `measurement_instruction`,
  `related_visual_feature`, optional `expected_tool`.
- **Rationale:** The user must know exactly what to measure and how.
- **Input:** image analysis result.
- **Output:** `input/<part>/measurement-request.json` (values `null`).
- **Acceptance:** File validates against `schemas/measurement.schema.json` with
  every `value` null; each entry has a non-empty instruction and a resolvable
  `related_visual_feature`.
- **Failure behavior:** If a needed dimension has no sensible measurement
  instruction, mark it `required: true` with `measurement_instruction` describing
  the difficulty and escalate.
- **Traceability:** `schemas/measurement.schema.json`,
  `.claude/skills/inventor-photo-to-ipt/templates/measurement-request.json`.

### MEAS-002 — Units explicit and supported
- **Requirement:** Every measurement carries an explicit `unit` in `{mm, cm, in,
  deg}`. Length types use `mm|cm|in`; angle types use `deg`.
- **Rationale:** Premise 5; prevent unit ambiguity into Inventor.
- **Input:** measurement JSON.
- **Output:** validated units.
- **Acceptance:** Validator rejects missing unit, unsupported unit, or
  unit/type mismatch (`VAL` failure list).
- **Failure behavior:** `MEASUREMENT_VALIDATION_FAILED` with the offending IDs.
- **Traceability:** `scripts/validate_measurements.py::_check_units`,
  `tests/test_validate.py`.

### MEAS-003 — SSOT and derived dimensions
- **Requirement:** User-supplied measurements are the SSOT. Derived dimensions are
  allowed only if they carry a `derivation` object with a `formula` and
  `source_measurement_ids`.
- **Rationale:** Keep the fact set minimal for the user but auditable.
- **Input:** measurement JSON with optional `derived` list.
- **Output:** resolved parameter set in the CAD plan.
- **Acceptance:** Every derived value re-computes from its sources within 1e-6;
  a derived entry with a missing source is a validation failure.
- **Traceability:** `scripts/plan_cad.py::_resolve_derived`,
  `tests/test_plan.py::test_derived_recompute`.

### MEAS-004 — ID uniqueness
- **Requirement:** All `measurements[*].id` and `derived[*].id` are unique within
  a file; visual-feature IDs are unique.
- **Rationale:** Traceability integrity.
- **Acceptance:** Duplicate ID → validation failure listing the duplicates.
- **Traceability:** `scripts/validate_measurements.py::_check_ids`,
  `tests/test_validate.py::test_duplicate_ids`.

---

## VAL — Validation

### VAL-001 — Schema validation gate
- **Requirement:** The measurement JSON must validate against
  `schemas/measurement.schema.json` (JSON Schema 2020-12) before any geometry
  check or CAD planning.
- **Acceptance:** Invalid JSON → `MEASUREMENT_VALIDATION_FAILED` with JSON-path
  locations; pipeline stops.
- **Traceability:** `scripts/validate_measurements.py`, `tests/test_validate.py`.

### VAL-002 — Geometry consistency validation
- **Requirement:** After schema validation, run engineering checks:
  - required value not null; length > 0; thickness/wall > 0; extrusion depth > 0;
  - hole diameter < containing face min span; hole centre inside body outline;
  - edge distance ≥ 0 and ≥ hole radius where an edge reference exists;
  - fillet/chamfer size < smallest adjacent edge length / 2 (sane bound);
  - pattern count integer ≥ 1; circular pattern total angle in `(0, 360]`;
  - symmetry references resolve and are mutually consistent;
  - no duplicate IDs; all `related_visual_feature` resolve.
- **Acceptance:** Any failure → `MEASUREMENT_VALIDATION_FAILED` with one line per
  offending ID and reason; Inventor is not launched.
- **Failure behavior:** Stop. No approximate model.
- **Traceability:** `scripts/validate_measurements.py` (`_check_geometry`),
  `tests/test_validate.py`.

### VAL-003 — CAD plan validation
- **Requirement:** `cad-plan.json` must validate against
  `schemas/cad-feature-plan.schema.json` and pass reference checks: every feature
  distance/angle/position references a defined parameter; feature `depends_on`
  IDs exist and form a DAG; sketch planes are in `{XY, XZ, YZ}` or a defined
  work plane.
- **Acceptance:** Invalid plan → pipeline stops before Inventor; error names the
  feature ID and field.
- **Traceability:** `scripts/plan_cad.py`, `schemas/cad-feature-plan.schema.json`,
  `tests/test_plan.py`.

---

## CAD — Feature plan

### CAD-001 — Parameters bound to measurement IDs
- **Requirement:** Every entry in `cad-plan.json.parameters` has either a
  `measurement_id` or a `derivation`. Feature geometry fields reference a
  parameter name, never a bare literal (except integer pattern counts and the
  fixed sketch-plane enum).
- **Acceptance:** SYS-002 acceptance check passes.
- **Traceability:** `scripts/plan_cad.py`, `tests/test_plan.py`.

### CAD-002 — Deterministic feature ordering
- **Requirement:** Features are emitted in a stable topological order derived from
  `depends_on` then feature ID; ties broken lexicographically.
- **Acceptance:** `tests/test_plan.py::test_feature_order_stable`.
- **Traceability:** `scripts/plan_cad.py::_order_features`.

### CAD-003 — Supported feature vocabulary
- **Requirement:** Planner accepts only `base_extrude, extrude_add, extrude_cut,
  hole, slot, fillet, chamfer, mirror, rectangular_pattern, circular_pattern,
  revolve`. `shell, thread, work_plane, work_axis` parse but produce a
  `FeatureUnsupportedError` naming the feature.
- **Acceptance:** `tests/test_plan.py::test_unsupported_feature_rejected`.
- **Traceability:** `scripts/plan_cad.py`, `docs/spec/05-cad-feature-plan.md`.

---

## INV — Inventor automation

### INV-001 — Connect or launch Inventor 2027
- **Requirement:** The runner connects to a running `Inventor.Application` if
  present, else starts it via the `Inventor.Application` COM ProgID; sets
  `Visible = true`; confirms the software version is 2027 (major 31).
- **Rationale:** Deterministic automation without GUI macros.
- **Input:** none (environment).
- **Output:** live `Application` handle; version logged.
- **Acceptance:** `detect_inventor.ps1` reports ProgID + version; `inventor_build.ps1`
  logs `Inventor.Application connected` with the version string.
- **Failure behavior:** If COM creation fails, log the `HRESULT`/exception verbatim
  and exit non-zero with `BLOCKED: Inventor COM connect failed`.
- **Traceability:** `scripts/detect_inventor.ps1`, `scripts/inventor_build.ps1`.

### INV-002 — Parametric part construction
- **Requirement:** For each CAD-plan parameter create a named Inventor user
  parameter (`p_<name>`) via a unit expression; build sketches, apply dimensional
  constraints referencing those parameters, then create features in plan order;
  call `Document.Update`.
- **Acceptance:** After build, `UserParameters` contains every `p_<name>`;
  `PartComponentDefinition.Features` count equals the plan's feature count
  (accounting for pattern occurrences); `Update` returns with no unresolved errors.
- **Failure behavior:** On any feature error, log `INV-<featureId> <message>` and
  the COM exception, stop, do not save a partial production `.ipt`.
- **Traceability:** `scripts/inventor_build.ps1`, `scripts/lib/features.ps1`.

### INV-003 — Centralized unit conversion
- **Requirement:** All value→internal conversions go through one helper that builds
  an Inventor unit expression (e.g. `"25.4 mm"`, `"30 deg"`) and calls
  `UnitsOfMeasure.GetValueFromExpression`. No arithmetic unit conversion anywhere
  else.
- **Acceptance:** `grep` for `/ 10` / `* 10` / `0.1` in feature builders returns
  nothing; `tests` include a unit-expression round-trip check via a pure-Python
  mirror (`scripts/lib` documented) and a PowerShell integration assertion.
- **Traceability:** `scripts/lib/units.ps1`, `docs/spec/06-inventor-automation.md`.

### INV-004 — Save and sanitize
- **Requirement:** Output path is `output/<sanitized-part>/<sanitized-part>.ipt`;
  the runner uses `Document.SaveAs(path, False)`.
- **Acceptance:** File exists after save; name matches `^[A-Za-z0-9_.-]+\.ipt$`.
- **Failure behavior:** Save exception logged verbatim; FAIL.
- **Traceability:** `scripts/inventor_build.ps1`.

---

## SAFE — Failure-safety

### SAFE-001 — Stop conditions
- **Requirement:** The build halts (no approximate model, no partial production
  `.ipt`) on any of: required measurement null; ambiguous geometry affecting
  topology; Inventor not installed; COM connect failure; unsupported feature
  requested; invalid CAD plan; inconsistent measurements; output path not
  writable; missing part template; Inventor rebuild error; save failure.
- **Acceptance:** Each condition has a test (unit or integration) asserting a
  non-zero exit and a structured reason.
- **Traceability:** `scripts/*`, `tests/*`.

### SAFE-002 — Exceptions never swallowed
- **Requirement:** Every caught exception is logged with type + message (+ COM
  `HRESULT` where available) to `build-log.txt` and re-surfaced in the report.
- **Acceptance:** No bare `catch {}` / `except: pass` in the codebase.
- **Traceability:** code review checklist in `docs/spec/07-verification-and-acceptance.md`.

---

## REP — Reporting

### REP-001 — Build report
- **Requirement:** Produce `output/<part>/build-report.md` with the sections in
  the master prompt §20: Inputs, Validation, Parameters (M-ID → p_name → sketch
  dim → feature), Features, Inventor Result (document type, solid bodies,
  features, save path, file size), Warnings, Result.
- **Acceptance:** `Result: PASS` appears only when `verify_ipt.ps1` confirmed the
  `.ipt`. Otherwise `Result: FAIL` with the failed step.
- **Traceability:** `scripts/inventor_build.ps1`, `scripts/verify_ipt.ps1`.

### REP-002 — Structured logging
- **Requirement:** Each pipeline step logs `[INFO]`/`[WARN]`/`[ERROR]` lines to
  `build-log.txt`; errors include the exception text.
- **Acceptance:** Log contains one line per major step (schema OK, N measurements
  resolved, Inventor connected, PartDocument created, each feature, update, save).
- **Traceability:** all scripts.
