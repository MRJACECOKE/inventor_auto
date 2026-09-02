# CLAUDE.md

Project: local Photo-to-IPT engineering agent for Autodesk Inventor 2027.

## Inventor Photo-to-IPT Workflow

- **New product / workflow planning must begin with gstack `/office-hours`.** The
  approved design doc is
  `~/.gstack/projects/inventor_auto/20260901-design-photo-to-ipt.md`; the spec
  suite built on it is `docs/spec/` (00..07 + `TRACEABILITY.md`).
- Photo-to-CAD requests use the `inventor-photo-to-ipt` skill
  (`.claude/skills/inventor-photo-to-ipt/SKILL.md`); the
  `inventor-cad-engineer` agent runs the same pipeline.
- **Never infer physical dimensions from photographs.** Photos give structure
  (topology, holes, slots, symmetry, patterns, datums) only.
- The user's `measurement-input.json` is the single source of truth (SSOT) for
  every real length, diameter, radius, depth, angle, and position.
- Validate before Inventor execution: schema (`schemas/measurement.schema.json`)
  then geometry consistency. No Inventor run on
  `MEASUREMENT_VALIDATION_FAILED`.
- Keep requirement -> JSON field -> parameter -> feature traceability
  (`docs/spec/TRACEABILITY.md`); write the parameter map into every build report.
- Do not report success without a verified `.ipt` on disk (exists, `.ipt`,
  size > 0, `kPartDocumentObject`, >= 1 solid body, no unhealthy features).
- Deferred features (`shell`, `thread`, `work_plane`, `work_axis`) and
  out-of-scope geometry escalate to the user for a drawing/spec - never an
  approximate model.

## Environment

- Windows 11, native. Autodesk Inventor 2027 installed; COM ProgID
  `Inventor.Application` registered.
- **Inventor COM automation runs under Windows PowerShell 5.1 (`powershell.exe`,
  STA).** `pwsh` 7 is MTA and some Inventor COM calls return null there; the
  runner scripts refuse to run outside STA.
- Python 3.9+ for validation/planning. No pip packages required
  (`scripts/_schema_lite.py` is a bundled JSON-Schema subset; `jsonschema` used
  if present).
- No .NET SDK on this machine, so the optional C# runner in
  `docs/spec/06-inventor-automation.md` is not built; the PowerShell COM runner
  is primary.

- A GUI front-end (`app/ipt_builder.py`, PySide6) covers **Phase E–I only**
  (validate → plan → build → verify → report); it consumes the `input/<part>/`
  folder Claude Code produced and does not analyse photos. Spec:
  `docs/spec/08-gui-app.md`. Build: `powershell -File build/build.ps1`.

## Commands

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1  # pinned install -> doctor -> tests -> determinism
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/doctor.ps1     # environment check -> DOCTOR: PASS/FAIL
python tests/run_tests.py                                   # non-Inventor unit tests incl. determinism
python scripts/regen_golden.py --check                      # cad-plan goldens still match (SYS-001)
python tests/gui_smoke.py                                   # GUI logic, offscreen (needs PySide6)
powershell.exe -NoProfile -File scripts/detect_inventor.ps1 # probe Inventor
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test_inventor_env.ps1  # inventor_env.ps1 resolution
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/integration_smoke.ps1  # golden fixture E2E
powershell -File build/build.ps1                            # build the GUI .exe -> build/dist/
```

Determinism: an intentional planner change breaks the goldens - regenerate with
`python scripts/regen_golden.py` and commit `tests/golden/`. Fresh-machine repro:
`docs/RUNBOOK.md`.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool.

- Product ideas / brainstorming / "is this worth building" -> `/office-hours`
- Photo -> Inventor .ipt, "photo to CAD", "사진으로 IPT" -> `inventor-photo-to-ipt`
- Bugs / errors -> `/investigate`
- Review a branch / diff -> `/code-review`
