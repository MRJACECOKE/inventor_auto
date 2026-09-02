# 00 — Office Hours Reference

This spec suite is built on the gstack `/office-hours` design document produced in
the planning phase. Implementation did **not** begin until that document existed
and was approved.

## Design document

- **Path:** `C:\Users\user\.gstack\projects\inventor_auto\20260901-design-photo-to-ipt.md`
- **Date:** 2026-09-01
- **Mode:** Builder (internal CAD automation tool)
- **Status:** APPROVED

## Core decisions carried into this spec

| Decision | Choice |
|---|---|
| Inventor runner | PowerShell COM automation (`Inventor.Application`). No .NET SDK on the machine, so the C# runner from the master prompt is a documented optional upgrade only. Runs under Windows PowerShell 5.1 (STA) — pwsh 7 (MTA) breaks some Inventor COM calls; discovered during implementation. |
| v1 feature vocabulary | Full MVP set: `base_extrude, extrude_add, extrude_cut, hole, slot, fillet, chamfer, mirror, rectangular_pattern, circular_pattern, revolve`. |
| Deferred / stubbed | `shell, thread, work_plane, work_axis` — return an explicit "unsupported feature" error. |
| Inventor window | Visible (`Application.Visible = true`). |
| Validator + planner language | Python 3.11 (`jsonschema` if importable, else bundled minimal Draft 2020-12 checker). |
| Units default | `mm`. All conversion centralized through Inventor `UnitsOfMeasure` expressions. |
| Golden fixture | `simple_plate` — prismatic plate with one hole, dimensions from fixture JSON only. |

## Key premises (locked)

1. Photos yield geometry/topology **hypotheses only**; the user measurement JSON is
   the single source of truth (SSOT) for every real dimension.
2. No CAD is generated unless all required measurements are present **and**
   schema-valid **and** geometry-consistent; otherwise the pipeline returns the
   offending measurement IDs and stops.
3. MVP = one solid part, deterministic feature tree, every geometry-driving
   parameter traceable to a measurement ID.
4. "Done" is claimed only after a real `.ipt` is verified on disk (exists, `.ipt`,
   size > 0, `PartDocument`, ≥ 1 solid body, no unresolved errors).
5. Units are explicit in JSON; all unit/angle conversion is centralized; `mm`
   default; no scattered `/10` magic.

## Rejected alternatives

- **Compiled C# / .NET runner** — blocked (no .NET SDK). Kept as an upgrade path;
  the PowerShell module boundaries mirror the C# class structure so a port is
  mechanical.
- **iLogic-embedded runner** — hard to unit-test off-Inventor, weaker ordering
  determinism and provenance. Rejected for MVP.
- **Pixel-scale dimension inference from photographs** — forbidden by premise 1.
- **Free-form / organic / cast surfaces, gear teeth, un-standardised threads,
  precision-fit tolerancing** — out of scope, pipeline escalates for a drawing.

## Narrowest useful MVP

Photograph a simple dimension-driven mechanical part → analyse structure only →
emit a measurement request → user measures → validate → deterministic CAD plan →
PowerShell COM build in Inventor 2027 → verified `.ipt` + build report.

## Data flow contract (never violated)

```
PHOTO → OBSERVATION → MEASUREMENT REQUEST → USER MEASUREMENT → VALIDATED FACT → CAD FEATURE → IPT
```

Forbidden: `PHOTO → guessed dimensions → IPT`.
