# Measurement guide (for the user)

You only edit `value` fields. Replace each `null` with a real measured number.
Keep the `unit`. Full contract: `docs/spec/04-measurement-contract.md`.

## How to measure

| quantity | tool | how |
|---|---|---|
| overall width / height / thickness | calipers | maximum span; thickness away from fillets |
| hole diameter | calipers (inside jaws) | the hole itself, not a mating bolt; note through vs blind |
| blind hole depth | depth gauge | separate entry from the diameter |
| hole position | calipers | from the declared origin or a named edge; centre-to-centre for pairs |
| corner / edge radius | radius gauge | match the arc |
| chamfer | calipers + protractor | leg distance (and angle if not 45 deg) |
| angle | protractor | between the two named faces |
| pattern spacing / pitch | calipers | centre-to-centre between adjacent instances |
| pattern count | count | integer, >= 1 |

## Rules the validator enforces

- every `required: true` value must be a finite number > 0 (positions may be 0,
  never negative);
- `type` and `unit` must agree: length -> `mm|cm|in`, angle -> `deg`,
  count -> `count`;
- hole diameter must be smaller than the face it sits on;
- hole centre +/- radius must stay inside the body outline;
- fillet / chamfer size must be less than half the smallest face span;
- pattern count integer >= 1; circular pattern total angle in `(0, 360]`;
- measurement IDs unique; `related_visual_feature` must match an ID from the
  image-analysis block.

If validation fails you get `MEASUREMENT_VALIDATION_FAILED` with one line per
problem ID. Fix those values and resubmit. Nothing is built until it passes.

## Derived dimensions

If a value can be computed from others, add a `derived` entry with a
`derivation.formula` over `source_measurement_ids` (only `+ - * / ()` and
numbers). You do not measure derived values.
