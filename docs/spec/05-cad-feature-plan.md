# 05 — CAD Feature Plan

How validated measurements become an Inventor feature tree. The planner
(`scripts/plan_cad.py`) consumes `measurement-input.json` (post-validation) plus
the structural intent from image analysis and emits a deterministic
`cad-plan.json` (+ human-readable `cad-plan.md`).

## Plan shape (authority: `schemas/cad-feature-plan.schema.json`)

```json
{
  "plan_version": "1.0",
  "part_name": "bracket_001",
  "units": "mm",
  "provenance": {
    "measurement_file": "input/bracket_001/measurement-input.json",
    "measurement_sha256": "…",
    "source_images": ["IMG-001", "IMG-002"]
  },
  "parameters": {
    "overall_width":  { "measurement_id": "M001", "value": 100.0, "unit": "mm" },
    "overall_height": { "measurement_id": "M002", "value": 60.0,  "unit": "mm" },
    "thickness":      { "measurement_id": "M003", "value": 6.0,   "unit": "mm" },
    "hole_1_dia":     { "measurement_id": "M004", "value": 6.5,   "unit": "mm" },
    "hole_row_span":  { "derivation": { "formula": "M007", "source_measurement_ids": ["M007"] },
                        "value": 80.0, "unit": "mm" }
  },
  "sketches": [
    {
      "id": "S1", "plane": "XY",
      "profile": {
        "type": "rectangle",
        "width_param": "overall_width",
        "height_param": "overall_height",
        "corner": "origin"
      }
    }
  ],
  "features": [
    { "id": "F001", "type": "base_extrude", "sketch": "S1",
      "distance_param": "thickness", "direction": "positive", "depends_on": [] },
    { "id": "F002", "type": "hole",
      "placement": { "plane": "XY", "x_param": "hole_1_x", "y_param": "hole_1_y" },
      "diameter_param": "hole_1_dia", "depth": "through",
      "depends_on": ["F001"] },
    { "id": "F003", "type": "rectangular_pattern", "of": "F002",
      "x_count_param": "hole_cols", "x_spacing_param": "hole_pitch_x",
      "y_count_param": "hole_rows", "y_spacing_param": "hole_pitch_y",
      "depends_on": ["F002"] },
    { "id": "F004", "type": "fillet", "edges": "all_vertical_outer",
      "radius_param": "corner_radius", "depends_on": ["F001"] }
  ]
}
```

## Rules

- **Every** `*_param` names a key in `parameters`. Integer counts may also be a
  `*_param` pointing at a `count` parameter. The only bare literals allowed in
  `features` are the `plane` enum (`XY|XZ|YZ`), `direction`
  (`positive|negative|symmetric`), and `depth` when it is the literal string
  `through`.
- `parameters[*]` has `measurement_id` XOR `derivation`. `value` is copied from the
  validated measurement for the runner's convenience and for the report; the
  runner still builds the Inventor parameter from a unit expression, not the raw
  number (INV-003).
- `features` form a DAG via `depends_on`. The planner emits them in topological
  order, ties broken by feature ID.
- Parameter names: `p_` prefix is added by the runner
  (`overall_width` → Inventor user parameter `p_overall_width`).

## Sketch profiles (v1 — implemented in `scripts/inventor_build.ps1`)

| `profile.type` | Required fields | Geometry (centred on the sketch origin) |
|---|---|---|
| `rectangle` | `width_param`, `height_param`, `corner` (`origin`\|`center`) | axis-aligned rectangle; `origin` = lower-left at sketch origin, `center` = centred on it |
| `circle` | `diameter_param` | circle centred on the sketch origin |
| `polygon` | `sides` (int 3–24, structural literal), `circumdiameter_param`, optional `clocking_param` | regular n-gon inscribed in the circumscribed circle; vertex 0 at `90° + clocking` so a vertex points "up"; one radial dimension is linked to `circumdiameter_param / 2` |

`polyline`, `slot`, `revolve_profile` are in the schema enum but not yet built by
the runner.

### Offset sketch planes

A sketch may sit on a plane parallel to an origin plane instead of on the origin
plane itself:

```json
{ "id": "S2", "plane": "YZ", "offset_param": "half_edge", "offset": "positive",
  "profile": { "type": "polygon", "sides": 3, "circumdiameter_param": "tri_dia" } }
```

The runner creates `WorkPlanes.AddByPlaneAndOffset(<origin plane>, "±p_<offset_param>")`
(`offset: negative` negates the expression; falls back to a fixed numeric offset
with a WARN if the parametric expression is rejected). Inventor 2027 default
template normals: `XY → +Z`, `XZ → +Y`, `YZ → +X`; `offset: positive` moves along
that normal. This keeps `work_plane` deferred for *free-standing / angled* planes
while allowing the common face-parallel case.

## Feature vocabulary (v1 — all implemented and tested)

| `type` | Required fields | Inventor mapping (see 06) |
|---|---|---|
| `base_extrude` | `sketch`, `distance_param`, `direction` | `Features.ExtrudeFeatures.Add`, NewBody |
| `extrude_add` | `sketch`, `distance_param`, `direction` | Extrude, Join |
| `extrude_cut` | `sketch`, `distance_param` or `through`, `direction` | Extrude, Cut |
| `revolve` | `sketch`, `axis`, `angle_param` or `full` | `RevolveFeatures.Add` |
| `hole` | `placement`, `diameter_param`, `depth` (`through` or `depth_param`) | sketch point(s) + `HoleFeatures.AddDrilledByThroughAllExtent` / `...ByDistanceExtent` |
| `slot` | `placement`, `length_param`, `width_param`, `depth` | sketched slot profile + Extrude Cut |
| `fillet` | `edges` selector, `radius_param` | `FilletFeatures.Add` |
| `chamfer` | `edges` selector, `distance_param` (+ optional `angle_param`) | `ChamferFeatures.Add` |
| `mirror` | `of` (feature id or list), `plane` | `MirrorFeatures.Add` |
| `rectangular_pattern` | `of`, `x_count_param`, `x_spacing_param`, optional `y_*` | `RectangularPatternFeatures.Add` |
| `circular_pattern` | `of`, `axis`, `count_param`, `angle_param` or `full` | `CircularPatternFeatures.Add` |

## Deferred (parse → explicit error)

`shell`, `thread`, `work_plane`, `work_axis` → planner raises
`FeatureUnsupportedError: <type> is specced but not implemented in v1`.

## Edge / face selectors (`edges`, `axis`, `plane`)

Deterministic named selectors resolved by the runner against the part:

- `all_vertical_outer` — outer edges parallel to Z on the base body.
- `top_face_perimeter`, `bottom_face_perimeter`.
- `edge:<sketchId>:<segmentIndex>` — explicit.
- `axis:Z`, `axis:Y`, `axis:X`, `axis:work:<id>`.
- `plane:XY|XZ|YZ`.

If a selector resolves to zero entities, the runner stops with
`INV-<featureId> selector '<sel>' matched no geometry`.

## cad-plan.md (human review artifact)

Ordered, plain-English feature list plus the parameter map, e.g.:

```
1. F001 — base_extrude: rectangle S1 on XY, width p_overall_width, height p_overall_height, extrude p_thickness (+Z), new body
2. F002 — hole: through hole Ø p_hole_1_dia at (p_hole_1_x, p_hole_1_y) on XY
3. F003 — rectangular_pattern of F002: p_hole_cols × p_hole_pitch_x, p_hole_rows × p_hole_pitch_y
4. F004 — fillet: all_vertical_outer edges, R p_corner_radius

Parameter map:
  M001 -> p_overall_width  -> S1 width  -> F001
  M003 -> p_thickness      -> F001 distance
  M004 -> p_hole_1_dia     -> F002 diameter
  D001 -> p_hole_row_span  (derived: M007)
```

Both `cad-plan.json` and the measurement JSON must be schema-valid before the
Inventor runner is invoked.
