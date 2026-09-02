# fixture: polygon_cube

A complete worked example for the determinism tests. 100 mm cube, one recessed
regular-polygon pocket (3..8 sides) 30 mm deep centred on each of the 6 faces.

| file | role |
|---|---|
| `ex.png` | source photo - **structure only** (topology, which face carries which polygon) |
| `measurement-request.json` | the blank request Claude Code produced from the photo |
| `feature-intent.json` | structure: which measurement drives which parameter, sketch planes, feature order |
| `measurement-input.json` | the single source of truth for every dimension. M001/M002 are user-stated (100 mm / 30 mm); M003..M008 are **provisional placeholders** (36 mm) chosen to prove the pipeline, not measured from the photo |

Expected planner output: `tests/golden/polygon_cube/cad-plan.json` (+ `.md`).
`tests/test_determinism.py` and `python scripts/regen_golden.py --check` assert a
byte-identical rebuild. If a deliberate planner change moves the output, run
`python scripts/regen_golden.py` and commit the new golden.

`source_images[].path` here points at the committed `ex.png` (relative) so the
`measurement_sha256` in the golden is machine-independent.
