# TRACEABILITY

`Requirement → JSON field → CAD feature → Implementation → Test → Verification`

## Requirement → Implementation → Test

| Req | JSON field(s) | CAD feature | Implementation | Test | Verification |
|---|---|---|---|---|---|
| SYS-001 deterministic | whole file | whole plan | `scripts/plan_cad.py` (`_write_json` sorted, deterministic Kahn order), `scripts/inventor_build.ps1` | `tests/test_plan.py::test_plan_is_byte_identical_on_rerun`; `tests/test_determinism.py` (golden byte-compare + twice-run); `scripts/regen_golden.py --check` (CI) | `tests/golden/<part>/cad-plan.json`; re-run diff in smoke |
| SYS-002 photo/measurement split | `measurements[*].value` | all feature `*_param` | `scripts/plan_cad.py::_bind_params`, `_check_unbound` | `tests/test_plan.py::test_no_unbound_dimensions` | report parameter map |
| SYS-003 provenance | `provenance.*` | — | `scripts/plan_cad.py::_provenance` | `tests/test_plan.py::test_provenance_sha256_matches_input`; `tests/test_determinism.py::test_provenance_sha256_matches_fixture_bytes` | report Inputs section |
| IMG-001 structure-only | `source_images`, image-analysis block | — | `SKILL.md` Phase B | manual / review | analysis block has no mm |
| IMG-002 multi-view registration | `source_images[*].view`, `related_visual_feature` | — | `SKILL.md` Phase B | manual / review | shared VF IDs |
| MEAS-001 request generation | `measurements[*]` (value null) | — | `SKILL.md` Phase C, `templates/measurement-request.json` | `tests/test_validate.py::test_template_all_null_valid` | request file validates |
| MEAS-002 units explicit | `measurements[*].unit`, `.type` | — | `scripts/validate_measurements.py::_check_units` | `tests/test_validate.py::test_missing_unit`, `::test_unit_type_mismatch` | validation report |
| MEAS-003 SSOT + derived | `derived[*].derivation` | derived parameters | `scripts/plan_cad.py::_resolve_derived` | `tests/test_plan.py::test_derived_recompute` | report Parameters |
| MEAS-004 ID uniqueness | `measurements[*].id`, `derived[*].id` | — | `scripts/validate_measurements.py::_check_ids` | `tests/test_validate.py::test_duplicate_ids` | validation report |
| VAL-001 schema gate | whole file | — | `scripts/validate_measurements.py` + `schemas/measurement.schema.json` | `tests/test_validate.py::test_schema_accepts_fixture`, `::test_schema_rejects_unknown_field` | `validation-report.json` |
| VAL-002 geometry consistency | `value`, `related_visual_feature`, `reference.symmetry` | — | `scripts/validate_measurements.py::_check_geometry` | `tests/test_validate.py::test_*_geometry` | validation report |
| VAL-003 plan validation | `cad-plan.json` | all | `scripts/plan_cad.py::_validate_plan` + `schemas/cad-feature-plan.schema.json` | `tests/test_plan.py::test_plan_schema`, `::test_depends_on_dag` | planner exit code |
| CAD-001 params bound | `parameters[*].measurement_id`/`derivation` | all `*_param` | `scripts/plan_cad.py::_bind_params` | `tests/test_plan.py::test_param_binding` | report parameter map |
| CAD-002 deterministic order | `features[*].depends_on`, `id` | feature tree | `scripts/plan_cad.py::_order_features` | `tests/test_plan.py::test_feature_order_stable` | report Features list |
| CAD-003 supported vocab | `features[*].type` | — | `scripts/plan_cad.py::SUPPORTED`, `DEFERRED` | `tests/test_plan.py::test_unsupported_feature_rejected` | planner error |
| CAD-004 regular-polygon pocket | `sketches[*].profile.type="polygon"`, `.sides`, `.circumdiameter_param`, `.clocking_param` | `extrude_cut` on a polygon sketch | `schemas/cad-feature-plan.schema.json` (polygon profile), `scripts/lib/geometry.ps1::Add-PolygonGeometry`, `scripts/inventor_build.ps1` (polygon branch) | `tests/test_plan.py::test_polygon_profile_and_offset_sketch_plan`, `::test_polygon_circumdiameter_param_must_be_bound` | `output/polygon_cube/` build (volume + per-face side count) |
| CAD-005 offset sketch plane | `sketches[*].offset_param`, `.offset` | any feature whose sketch sits on a face-parallel plane | `schemas/cad-feature-plan.schema.json` (sketch offset), `scripts/inventor_build.ps1` (`WorkPlanes.AddByPlaneAndOffset`, expr `±p_<offset_param>`, numeric fallback) | `tests/test_plan.py::test_polygon_profile_and_offset_sketch_plan` | build log "Sketch S# on <plane>+offset(...)" |
| CAD-006 centred base profile | `sketches[*].profile.corner="center"` | `base_extrude` `direction=symmetric` | `scripts/lib/geometry.ps1::Add-RectangleGeometry` (`-Corner center`) | `tests/test_plan.py::test_polygon_profile_and_offset_sketch_plan` | reopened body RangeBox centred on origin |
| INV-001 connect/launch | — | — | `scripts/lib/inventor_env.ps1`, `scripts/detect_inventor.ps1`, `scripts/inventor_build.ps1` (connect block) | `tests/integration_smoke.ps1` step 1, `tests/test_inventor_env.ps1` | log line "Inventor.Application connected"; interop DLL registry-derived |
| INV-002 parametric build | `parameters`, `sketches`, `features` | all | `scripts/inventor_build.ps1`, `scripts/lib/features.ps1` | `tests/integration_smoke.ps1` steps 3,5 | report Inventor Result |
| INV-003 central units | `parameters[*].unit`, `*.unit` | all dimensions | `scripts/lib/units.ps1::ConvertTo-Internal` | `tests/test_validate.py::test_unit_parser` (mirror), smoke step 5 | grep gate in review |
| INV-004 save + sanitize | `part_name` | — | `scripts/inventor_build.ps1` (save block) | `tests/integration_smoke.ps1` step 4 | file on disk, name regex |
| SAFE-001 stop conditions | any invalid | — | `scripts/*` guard clauses | `tests/test_validate.py`, `tests/test_plan.py` negative cases, smoke | non-zero exit + reason |
| SAFE-002 no swallowed exc | — | — | all scripts (`Write-Log` + rethrow) | review checklist | `build-log.txt` has exception text |
| REP-001 build report | all | all | `scripts/inventor_build.ps1::Write-Report` | `tests/integration_smoke.ps1` step 5 | `build-report.md` exists, `Result:` line |
| REP-002 structured logging | — | — | `Write-Log` in all scripts | smoke inspects log | `build-log.txt` step lines |
| REP-003 environment stamp | — | — | `scripts/inventor_build.ps1::Get-BuildStamp` + `Write-Report` `## Environment` | `tests/run_ps_tests.ps1` (report has the section) | `build-report.md` `## Environment` (version, git commit, Python, PS, OS); `build-log.txt` first `[INFO] stamp:` line |
| GUI-001 E–I only + intent gate | `feature-intent.json` presence | — | `app/ipt_builder.py::MainWindow._load_intent/_refresh_enabled` | `tests/gui_smoke.py` (no-intent checks) | 플랜/빌드 disabled, empty-state text |
| GUI-002 working-folder / abs paths | picked folder | — | `app/pipeline.py::resolve_paths`, `scripts/inventor_build.ps1 -OutDir` | `tests/test_pipeline_wrapper.py::ResolvePathsTests` | output in sibling `output/<part>/` |
| GUI-003 portability | — | — | `scripts/lib/inventor_env.ps1`, `app/pipeline.py::probe_inventor` | `tests/test_inventor_env.ps1` | env chip green/red |
| GUI-004 in-proc validate/plan, CLI parity | `measurement*.json`, `cad-plan.json` | all | `app/pipeline.py::{run_validate,run_plan}`, `app/resources.py` | `tests/test_pipeline_wrapper.py::{ValidateTests,PlanParityTests}` | byte-identical `cad-plan.json` |
| GUI-005 build UX / cancel | — | — | `app/ipt_builder.py::{BuildWorker,_do_build,_cancel_build}`, `app/pipeline.py::{run_build,kill_inventor}` | `tests/gui_smoke.py`, manual checklist item 9 | responsive window, no orphan Inventor |
| GUI-006 measurement form fidelity | `measurements[*].value` | — | `app/ipt_builder.py::MeasurementModel`, `app/pipeline.py::{load_measurement_request,write_measurement_input}` | `tests/test_pipeline_wrapper.py::MeasurementFormTests`, `tests/gui_smoke.py` | non-`value` fields + order preserved |
| GUI-007 packaging | — | all bundled | `build/IptBuilder.spec`, `build/build.ps1`, `requirements-dev.txt` | manual (`build/build.ps1` exit 0 + exe launch) | `_internal/` has scripts/schemas/guide.html |

## Parameter mapping (recorded per build in build-report.md)

```
<MEASUREMENT ID> -> p_<name> -> <sketch/feature dimension> -> <feature ID>
```

Example (simple_plate fixture):

```
M001 -> p_overall_width      -> S1 rectangle width      -> F001
M002 -> p_overall_height     -> S1 rectangle height     -> F001
M003 -> p_thickness          -> F001 extrude distance   -> F001
M004 -> p_hole_dia           -> F002 hole diameter      -> F002
M005 -> p_hole_x_from_origin -> F002 sketch point X     -> F002
M006 -> p_hole_y_from_origin -> F002 sketch point Y     -> F002
M007 -> p_corner_radius      -> F003 fillet radius      -> F003
```

## Verification results log

Filled in by each run; template:

| Date | Part | Schema | Geometry | Plan | Inventor | .ipt bytes | Bodies | Result |
|---|---|---|---|---|---|---|---|---|
| 2026-09-01 | simple_plate (fixture) | pass | pass | pass | 2027.1 (31.1) | 158720 | 1 | PASS |
| 2026-09-01 | polygon_cube (provisional polygon sizes) | pass | pass | pass | 2027.1 (31.1) | 184320 | 1 | PASS (100³ mm, vol 865.479 cm³, per-face sides 3/4/5/6/7/8) |
