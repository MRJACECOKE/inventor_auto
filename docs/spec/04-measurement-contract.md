# 04 — Measurement Contract

How the user supplies engineering facts. This JSON is the Single Source of Truth
for every real dimension.

## File

- Request template: `input/<part>/measurement-request.json` (all `value: null`).
- User input: `input/<part>/measurement-input.json` (user replaces `null` with
  numbers; nothing else needs to change).
- Accepted by paste into chat or by file path.

## Structure (see `schemas/measurement.schema.json` for the authority)

```json
{
  "schema_version": "1.0",
  "part": { "name": "bracket_001", "description": "", "units": "mm" },
  "source_images": [
    { "id": "IMG-001", "path": "provided-in-chat", "view": "front" }
  ],
  "reference": {
    "origin_definition": "back-lower-left corner of the plate",
    "primary_plane": "XY",
    "symmetry": [
      { "type": "mirror", "plane": "YZ", "confidence_note": "user confirmed" }
    ]
  },
  "measurements": [
    {
      "id": "M001",
      "name": "overall_width",
      "value": 100.0,
      "unit": "mm",
      "type": "length",
      "required": true,
      "measurement_instruction": "Max overall width across the part with calipers.",
      "related_visual_feature": "VF-FACE-001",
      "expected_tool": "calipers"
    }
  ],
  "derived": [
    {
      "id": "D001",
      "name": "hole_row_span",
      "type": "length",
      "unit": "mm",
      "derivation": { "formula": "M007", "source_measurement_ids": ["M007"] }
    }
  ],
  "constraints": [],
  "material": { "name": null },
  "metadata": { "measured_by": null, "notes": null }
}
```

## Measurement types and units

| `type` | Allowed `unit` | Notes |
|---|---|---|
| `length` | `mm`, `cm`, `in` | width, height, thickness, depth, diameter, radius, spacing, position, edge distance |
| `angle` | `deg` | draft, revolve angle, chamfer angle, pattern total angle |
| `count` | `count` | integer ≥ 1; pattern occurrences |

`part.units` sets the display default; every measurement still carries its own
explicit `unit`.

## Rules

1. `value` may be `null` in the request template; in the input file, every
   `required: true` measurement must be a finite number.
2. `id` values are unique across `measurements` + `derived`.
3. `related_visual_feature` must match an ID from the image-analysis block (or be
   omitted for global dimensions like `overall_width` when no single feature
   applies — still list a face).
4. `type`/`unit` must agree (length↔mm/cm/in, angle↔deg, count↔count).
5. Negative lengths, zero thickness, zero depth, non-integer counts, count < 1 are
   invalid.
6. Derived entries never carry a `value`; they carry a `derivation`. The formula is
   a restricted arithmetic expression over `source_measurement_ids`
   (`+ - * /`, parentheses, numeric literals). Any symbol not in
   `source_measurement_ids` is a validation failure.
7. The user only ever needs to edit `value` fields (and optionally `metadata`,
   `material.name`, `reference.symmetry[*].confidence_note`).

## Measurement instructions (guidance the generator must follow)

- State the tool (`calipers`, `depth gauge`, `micrometer`, `protractor`,
  `rule`, `radius gauge`, `thread gauge`).
- State the datum: "from the left edge (VF-EDGE-001)", "centre-to-centre".
- For holes: measure the **hole** diameter (not a mating bolt); note through vs.
  blind and, if blind, request depth as a separate entry.
- For diameters on turned parts: measure at the largest full-round cross section.
- For positions: always relative to the declared origin / a named edge, never
  "roughly centred".
- One physical quantity per entry.

## Validation output

On failure the pipeline returns:

```
MEASUREMENT_VALIDATION_FAILED

- M004: required value missing
- M008: hole diameter (12 mm) exceeds available face width span (10 mm)
- M011: unit missing
- D001: derivation references unknown id M099

Please correct these fields.
```

No CAD plan and no Inventor launch happen until validation passes clean.
