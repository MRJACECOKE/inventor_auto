# `.claude/` - applied skill + agent

This folder is the Claude Code entry point for the photo-to-IPT pipeline. It
carries no logic of its own; the canonical implementation is the repo-root
`scripts/`, `app/`, `schemas/` and `docs/spec/`.

| file | what it is | maps to |
|---|---|---|
| `skills/inventor-photo-to-ipt/SKILL.md` | the workflow (Phase A-I): image intake -> structure analysis -> measurement request -> validate -> plan -> Inventor build -> verify -> report | `scripts/*`, `schemas/*`, `docs/spec/00..08` |
| `skills/inventor-photo-to-ipt/reference/` | API notes, measurement guide, workflow crib | `docs/spec/03..06` |
| `skills/inventor-photo-to-ipt/templates/measurement-request.json` | blank measurement-request skeleton | `docs/spec/04` |
| `agents/inventor-cad-engineer.md` | subagent that runs the same pipeline against the same spec | same as the skill |

## Rules (also in the skill, agent, and `docs/spec/`)

1. Photos give **structure only** (topology, holes, slots, symmetry, patterns,
   datums). Never infer a physical dimension from a photo.
2. `input/<part>/measurement-input.json` is the single source of truth for every
   length, diameter, radius, depth, angle, position.
3. Validate (schema + geometry) before any Inventor call.
4. Keep requirement -> JSON field -> parameter -> feature traceability
   (`docs/spec/TRACEABILITY.md`); write the parameter map into every build report.
5. No success claim without a verified `.ipt` on disk.
6. Deferred features and out-of-scope geometry -> stop and ask for a drawing/spec.

## Determinism

`scripts/plan_cad.py` is a pure function of its inputs (SYS-001). The
`polygon_cube` fixture under `tests/fixtures/parts/` plus `tests/golden/` pin
that; `python scripts/regen_golden.py --check` is the gate. See
`../CONTRIBUTING.md`.
