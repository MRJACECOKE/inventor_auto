"""Golden-file determinism tests for scripts/plan_cad.py.

SYS-001 (`docs/spec/01`): given the same measurement JSON and feature intent, the
planner must emit a byte-identical `cad-plan.json` on every run and across
versions. These tests pin that to committed goldens under `tests/golden/`.

Fixtures live in `tests/fixtures/parts/<part>/` (real measurement + intent, plus
the source photo for provenance). Regenerate goldens on a deliberate change with:

    python scripts/regen_golden.py

`scripts/regen_golden.py --check` runs the same comparison from the CLI (used by
`ci/run_ci.ps1` and the GitHub Actions workflow).
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import plan_cad  # noqa: E402

FIXTURES = os.path.join(REPO, "tests", "fixtures", "parts")
GOLDEN = os.path.join(REPO, "tests", "golden")


def _canon(plan) -> str:
    """Match plan_cad._write_json: indent=2, sort_keys, trailing newline."""
    return json.dumps(plan, indent=2, sort_keys=True) + "\n"


def _parts():
    if not os.path.isdir(FIXTURES):
        return []
    return [
        n for n in sorted(os.listdir(FIXTURES))
        if os.path.isfile(os.path.join(FIXTURES, n, "measurement-input.json"))
        and os.path.isfile(os.path.join(FIXTURES, n, "feature-intent.json"))
    ]


def _build(part):
    """Build with repo-relative paths so provenance.measurement_file is stable."""
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        return plan_cad.build_plan(
            f"tests/fixtures/parts/{part}/measurement-input.json",
            f"tests/fixtures/parts/{part}/feature-intent.json",
        )
    finally:
        os.chdir(cwd)


class DeterminismTests(unittest.TestCase):
    def test_at_least_one_fixture_present(self):
        self.assertTrue(_parts(), "expected fixtures under tests/fixtures/parts/")

    def test_golden_matches_for_every_fixture(self):
        for part in _parts():
            with self.subTest(part=part):
                golden = os.path.join(GOLDEN, part, "cad-plan.json")
                self.assertTrue(
                    os.path.isfile(golden),
                    f"missing golden for {part}; run: python scripts/regen_golden.py",
                )
                plan, _ = _build(part)
                with open(golden, "r", encoding="utf-8") as fh:
                    want = fh.read()
                self.assertEqual(
                    _canon(plan), want,
                    f"{part}/cad-plan.json drifted from its golden; if intended run "
                    f"python scripts/regen_golden.py",
                )

    def test_two_builds_are_byte_identical(self):
        for part in _parts():
            with self.subTest(part=part):
                p1, _ = _build(part)
                p2, _ = _build(part)
                self.assertEqual(_canon(p1), _canon(p2))

    def test_provenance_sha256_matches_fixture_bytes(self):
        import hashlib
        for part in _parts():
            with self.subTest(part=part):
                plan, _ = _build(part)
                meas = os.path.join(FIXTURES, part, "measurement-input.json")
                with open(meas, "rb") as fh:
                    want = hashlib.sha256(fh.read()).hexdigest()
                self.assertEqual(plan["provenance"]["measurement_sha256"], want)

    def test_plan_self_validates_against_schema(self):
        import validate_measurements as vm
        schema = vm.load_schema(plan_cad.PLAN_SCHEMA)
        for part in _parts():
            with self.subTest(part=part):
                plan, _ = _build(part)
                errs, _engine = vm.schema_validate(plan, schema)
                self.assertEqual(errs, [], f"{part}: generated plan must satisfy its schema")


if __name__ == "__main__":
    unittest.main()
