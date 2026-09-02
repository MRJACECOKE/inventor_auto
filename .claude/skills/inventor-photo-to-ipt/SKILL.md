---
name: inventor-photo-to-ipt
description: >-
  Build a parametric Autodesk Inventor 2027 .ipt from photos of a real mechanical
  part WITHOUT guessing dimensions. Use when the user wants to turn a photo into
  an Inventor model / IPT, "photo to CAD", "image to Inventor", "사진으로 Inventor
  모델 생성", "사진 보고 IPT 생성", or asks to generate a .ipt from a measurement
  JSON. The photo is used only for structure (topology, holes, slots, symmetry,
  patterns, datums); every real length/diameter/angle comes from a user-supplied
  measurement JSON that is the single source of truth. Validates (schema +
  geometry), plans deterministic features, drives Inventor over COM, and verifies
  the saved .ipt.
---

# inventor-photo-to-ipt

Turn photographs of a mechanical part into a real, rebuildable, parametric
Autodesk Inventor 2027 `.ipt`. **Photos give structure. The user's measurement
JSON gives every dimension.** Never infer a physical dimension from a photo.

Full engineering spec: `docs/spec/` (00..07 + `TRACEABILITY.md`). Design basis:
`~/.gstack/projects/inventor_auto/20260901-design-photo-to-ipt.md`.

## Environment requirements

- Autodesk Inventor 2027 installed, COM ProgID `Inventor.Application` registered.
  Probe: `powershell.exe -NoProfile -File scripts/detect_inventor.ps1`.
- **Inventor COM steps MUST run under Windows PowerShell 5.1 (`powershell.exe`),
  which is STA.** `pwsh` 7 is MTA and some Inventor COM calls silently return
  null there. The Python steps run under any Python 3.9+.
- Python 3.9+ for validation and planning. No pip packages required
  (`scripts/_schema_lite.py` is a bundled JSON-Schema subset; `jsonschema` is
  used automatically if present).

## Canonical scripts (repo root `scripts/`, not duplicated in the skill)

| script | host | purpose |
|---|---|---|
| `scripts/detect_inventor.ps1` | powershell.exe | probe Inventor / COM / interop |
| `scripts/validate_measurements.py` | python | schema + geometry consistency gate |
| `scripts/plan_cad.py` | python | measurement JSON + feature intent -> `cad-plan.json` / `.md` |
| `scripts/inventor_build.ps1` | powershell.exe (STA) | COM build -> `.ipt` -> verify -> report |
| `scripts/verify_ipt.ps1` | powershell.exe | reopen + inspect a `.ipt` |

## Workflow

### Phase A - Image intake
User supplies one or more photos (drag/drop, paste, or file path) and states the
part intent, e.g. "make this into an Inventor 2027 .ipt". Do not start Inventor.

### Phase B - Visual analysis (structure only)
For each image, produce the `IMAGE ANALYSIS` block from
`docs/spec/03-image-analysis-contract.md`: component-type hypothesis, visible
faces, primitives, holes, axes, symmetry, feature relationships, occlusion,
ambiguity, and a per-observation confidence. Assign stable visual-feature IDs
(`VF001` / `VF-HOLE-001`). Multi-view: one shared ID per physical feature only
when correspondence confidence >= 0.7; otherwise keep separate and flag.
**No millimetre / degree values.** If the part is outside the supported families
(`docs/spec/07`), stop and ask for more views or a dimensioned drawing.

### Phase C - Measurement request
List every dimension the build needs. Write
`input/<part>/measurement-request.json` from
`templates/measurement-request.json`, one entry per dimension with `id`, `name`,
`type`, `unit`, `required`, `measurement_instruction` (tool + datum + "one
quantity per entry"), `related_visual_feature`, `expected_tool`. All `value` are
`null`. Echo the JSON in chat for easy copy/edit. Also write the structural
`input/<part>/feature-intent.json` (which measurement drives which parameter,
sketch planes, feature order, `depends_on`) - see `docs/spec/05`.

### Phase D - User measurement input
User replaces every `null` with a measured number and returns
`input/<part>/measurement-input.json` (paste or path). Only `value` fields (and
optional `metadata`, `material.name`) change.

### Phase E - Validation (hard gate)
```
python scripts/validate_measurements.py input/<part>/measurement-input.json \
    --report output/<part>/validation-report.json
```
Schema (`schemas/measurement.schema.json`) then geometry consistency: missing
required value, non-positive length/thickness/depth, hole dia >= face span, hole
centre outside body, impossible fillet/chamfer, pattern count < 1, pattern angle
outside (0,360], duplicate IDs, unit/type mismatch, bad derivations. On failure
the script prints `MEASUREMENT_VALIDATION_FAILED` and the offending IDs - relay
them and stop. **No Inventor run until this passes clean.**

### Phase F - Feature plan
```
python scripts/plan_cad.py --measurements input/<part>/measurement-input.json \
    --intent input/<part>/feature-intent.json --out-dir output/<part>
```
Produces deterministic `output/<part>/cad-plan.json` (parameters bound to
measurement IDs, topologically ordered features, provenance sha256) and
`cad-plan.md` (human-readable). The planner self-validates against
`schemas/cad-feature-plan.schema.json` and rejects unbound dimensions and the
deferred features (`shell`, `thread`, `work_plane`, `work_axis`).

### Phase G - Inventor build
```
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/inventor_build.ps1 \
    -PlanPath output/<part>/cad-plan.json
```
Connects to / launches Inventor 2027 (Visible), creates `p_<name>` user
parameters from unit expressions, builds sketches and features in plan order,
`Document.Update()`, `SaveAs output/<part>/<part>.ipt`.

### Phase H - Verification
`inventor_build.ps1` calls `verify_ipt.ps1`: file exists, `.ipt`, size > 0,
reopens as `kPartDocumentObject`, >= 1 solid body, feature count, no unhealthy
features. **Only claim success on `Result: PASS`.**

### Phase I - Report
`output/<part>/build-report.md` (inputs + provenance, validation, parameter map
`M-ID -> p_name -> dim -> feature`, features, Inventor result, warnings, PASS/FAIL)
and `output/<part>/build-log.txt` (structured `[INFO]/[WARN]/[ERROR]` per step,
exceptions verbatim).

## Golden fixture (prove the pipeline before any photo)

```
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/integration_smoke.ps1
```
Builds `tests/fixtures/simple_plate` end-to-end to a verified `.ipt`, kept at
`output/simple_plate/simple_plate.ipt` (pass `-Clean` to delete it afterward, for
CI). Fixture dimensions are test data, never confused with photo-derived values.

## Hard rules

1. Never infer a physical dimension from a photograph.
2. `measurement-input.json` is the single source of truth.
3. Validate (schema + geometry) before Inventor runs.
4. Keep requirement -> JSON field -> parameter -> feature traceability
   (`docs/spec/TRACEABILITY.md`); record the parameter map in every build report.
5. Do not report success without a verified `.ipt` on disk.
6. Deferred / unsupported features and out-of-scope geometry -> stop and ask for a
   drawing or spec. Never build an approximate model.
