# 07 — Verification and Acceptance

## Definition of Done

A build is **DONE / PASS** only when all of the following are true and recorded in
`build-report.md`:

1. `measurement-input.json` passed schema validation (VAL-001).
2. `measurement-input.json` passed geometry consistency validation (VAL-002).
3. `cad-plan.json` passed schema + reference validation (VAL-003).
4. Inventor 2027 connected (INV-001), version major = 31.
5. All planned features created; `Document.Update()` reported no unresolved errors.
6. `output/<part>/<part>.ipt` exists on the filesystem.
7. File extension is `.ipt`; file size > 0 bytes.
8. Reopened via COM: document type is `kPartDocumentObject`.
9. `ComponentDefinition.SurfaceBodies.Count >= 1` (at least one solid body).
10. Feature count in the reopened document matches the plan (base features count;
    pattern occurrence bodies allowed to differ).

Any failure → **FAIL**, with the failing step named. No PASS on a 0-byte file, a
missing file, a body-less document, or an update error.

## Test layers

### Non-Inventor tests (always runnable — `python tests/run_tests.py`)

| Test | Requirement |
|---|---|
| schema accepts the golden fixture | VAL-001 |
| schema rejects missing `unit` | MEAS-002 |
| schema rejects unknown top-level field | VAL-001 |
| `null` required value → failure list contains the ID | VAL-002 |
| negative length / zero thickness / zero depth → failure | VAL-002 |
| hole diameter ≥ face span → failure | VAL-002 |
| hole centre outside body outline → failure | VAL-002 |
| pattern count 0 or non-integer → failure | VAL-002 |
| circular pattern angle 0 or > 360 → failure | VAL-002 |
| duplicate measurement IDs → failure lists both | MEAS-004 |
| unit parser: `"25.4 mm"`, `"2.54 cm"`, `"1 in"` → same length; `"30 deg"` angle | INV-003 mirror |
| planner: every parameter has `measurement_id` xor `derivation` | CAD-001 |
| planner: no unbound feature dimension | SYS-002 |
| planner: feature order is a stable topological sort | CAD-002 |
| planner: `shell`/`thread`/`work_plane`/`work_axis` → `FeatureUnsupportedError` | CAD-003 |
| planner: derived value recomputes from sources | MEAS-003 |
| planner output is byte-identical on re-run | SYS-001 |
| provenance sha256 matches input file | SYS-003 |

### Inventor integration smoke (`powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/integration_smoke.ps1` — needs Inventor)

1. Connect / launch Inventor 2027, assert version major 31.
2. Validate + plan `tests/fixtures/simple_plate/measurement-input.json`.
3. Run `inventor_build.ps1` → build `simple_plate`.
4. Assert `output/simple_plate/simple_plate.ipt` exists, size > 0.
5. Reopen, assert `PartDocument`, `SurfaceBodies.Count == 1`, feature count ≥ 3
   (`base_extrude`, `hole`, `fillet`).
6. **Keep** `output/simple_plate/` (the `.ipt`, plan, log, report) so the user
   can open the built part. `-Clean` deletes it afterward (CI use); the fixture
   is synthetic so deletion is always safe.
7. Print `INTEGRATION: PASS` / `INTEGRATION: FAIL <step>` and the `.ipt` path.

The `simple_plate` fixture dimensions are test data. They are never confused with
values inferred from a user photo.

## Acceptance checklist (per real part)

- [ ] Image analysis emitted, zero committed dimensions.
- [ ] `measurement-request.json` generated and validated (all `null`).
- [ ] User `measurement-input.json` validates (schema + geometry).
- [ ] `cad-plan.json` + `cad-plan.md` generated and validated.
- [ ] Inventor connected; part built; `Update` clean.
- [ ] `.ipt` verified (exists, > 0 bytes, PartDocument, ≥ 1 body).
- [ ] `build-report.md` `Result: PASS`.
- [ ] Parameter map in the report links every M-ID to a `p_*` and a feature.

## Code-review gates

- No `catch {}` / `except: pass` (SAFE-002).
- No unit arithmetic outside `scripts/lib/units.ps1` (INV-003).
- No numeric dimension literal in `cad-plan.json` features except the plane /
  direction enums and integer counts (SYS-002).
- Every Inventor API call in `scripts/lib/*.ps1` has a source comment (06).
