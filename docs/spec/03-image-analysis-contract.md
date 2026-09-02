# 03 — Image Analysis Contract

Defines the boundary between what a photograph may produce (geometry hypotheses)
and what it may never produce (engineering facts).

## Allowed outputs (hypotheses, each with a confidence 0..1)

| Field | Meaning |
|---|---|
| `component_type_hypothesis` | e.g. `plate`, `bracket`, `flange`, `shaft`, `mount`, `housing` + alternatives |
| `visible_faces` | which faces/views are visible (`front`, `rear`, `left`, `right`, `top`, `bottom`, `perspective`) |
| `detected_primitives` | rectangles, circles, arcs, slots, ribs, bosses, pockets — as *shapes*, not sizes |
| `holes` | count, approximate relative arrangement, through vs. blind hypothesis, `VF-HOLE-###` IDs |
| `axes` | candidate axes of revolution / symmetry planes |
| `symmetry` | mirror/rotational symmetry hypotheses and the plane/axis they use |
| `feature_relationships` | "hole B is on the same bolt circle as hole A", "slot C breaks edge D" |
| `patterns` | linear / circular repeat hypotheses with approximate count |
| `datum_candidates` | which face/edge/axis is the likely origin reference |
| `occluded_regions` | areas hidden in all supplied views |
| `ambiguous_features` | anything that cannot be classified confidently |
| `required_measurements` | the list handed to the Measurement Request Generator |
| `confidence` | per observation |

## Forbidden outputs

- Any real `mm` / `cm` / `in` / `deg` value stated as fact or "estimate".
- Hole/bore diameter numbers derived from pixels.
- Dimensions "scaled" from an assumed reference object, coin, ruler, or EXIF data.
- Treating an occluded or inferred region as confirmed geometry.
- Wall thickness, depth, or fillet radius numbers.
- Thread pitch / class, gear module, tolerance, or fit callouts.

## Visual feature IDs

- Generic: `VF001`, `VF002`, ...
- Typed (preferred when the kind is clear): `VF-HOLE-001`, `VF-SLOT-001`,
  `VF-FILLET-001`, `VF-EDGE-001`, `VF-AXIS-001`, `VF-FACE-001`.
- IDs are stable within a session. The same physical feature across multiple views
  keeps one ID **only** when the correspondence confidence ≥ 0.7; otherwise the
  views get distinct IDs and the ambiguity is listed.

## Output block format (chat + file)

```
IMAGE ANALYSIS

Images:
- IMG-001 (view: front, confidence 0.9)
- IMG-002 (view: right, confidence 0.6)

Observed component:
  plate  (alt: bracket)  confidence 0.8

Visual features:
  VF-FACE-001  front face, primary datum candidate            conf 0.85
  VF-HOLE-001  through hole, upper-left quadrant               conf 0.8
  VF-HOLE-002  through hole, upper-right; same row as VF-HOLE-001  conf 0.75
  VF-EDGE-001  left edge, reference for hole X position        conf 0.7

Likely datum:
  origin at back-lower-left corner; primary plane XY on VF-FACE-001   conf 0.7

Symmetry:
  mirror about YZ through the part centre                            conf 0.55  (needs confirmation)

Occluded / uncertain:
  rear face never shown; hole depth (through vs blind) unconfirmed for VF-HOLE-002

Measurements required:
  M001 overall_width
  M002 overall_height
  M003 thickness
  M004 hole_1_diameter        (VF-HOLE-001)
  M005 hole_1_pos_x_from_left  (VF-HOLE-001 -> VF-EDGE-001)
  M006 hole_1_pos_y_from_bottom
  M007 hole_1_to_hole_2_center_distance  (VF-HOLE-001 -> VF-HOLE-002)
```

Then the generator writes `input/<part>/measurement-request.json` and echoes it in
chat for easy copy/edit.

## Escalation triggers

If any of these are true, do **not** emit a measurement request for the affected
geometry — ask the user for more views, a dimensioned drawing, or a spec:

- component family not in the supported list (02/07);
- free-form / organic / cast irregular surface is load-bearing to the shape;
- internal structure matters and is not visible;
- gear teeth, cam profile, or spline without a spec;
- threads without a stated standard;
- a fit/tolerance decision is required to proceed.
