"""Non-Inventor tests for the GUI's headless wrapper (app/pipeline.py).

Covers resolve_paths, in-process validate, CLI-parity planning, and measurement
form round-trip. The Inventor build (run_build) is exercised by
tests/integration_smoke.ps1, not here.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from app import pipeline as P  # noqa: E402

FIX = os.path.join(REPO, "tests", "fixtures", "simple_plate")


def _copy_fixture(dst_part_dir):
    os.makedirs(dst_part_dir, exist_ok=True)
    for name in ("measurement-input.json", "feature-intent.json"):
        shutil.copy(os.path.join(FIX, name), os.path.join(dst_part_dir, name))


class ResolvePathsTests(unittest.TestCase):
    def test_input_convention(self):
        with tempfile.TemporaryDirectory() as d:
            part = os.path.join(d, "input", "bracket_9")
            os.makedirs(part)
            paths = P.resolve_paths(part)
            self.assertEqual(paths.part_name, "bracket_9")
            self.assertEqual(str(paths.working_root), d)
            self.assertEqual(str(paths.out_dir), os.path.join(d, "output", "bracket_9"))
            self.assertTrue(str(paths.cad_plan_json).endswith(os.path.join("output", "bracket_9", "cad-plan.json")))
            self.assertTrue(str(paths.ipt).endswith("bracket_9.ipt"))

    def test_out_dir_override_and_non_input_parent(self):
        paths = P.resolve_paths(FIX, out_dir=os.path.join(tempfile.gettempdir(), "x"))
        self.assertEqual(paths.part_name, "simple_plate")
        self.assertTrue(paths.has_feature_intent())
        self.assertEqual(str(paths.out_dir), os.path.abspath(os.path.join(tempfile.gettempdir(), "x")))


class ValidateTests(unittest.TestCase):
    def test_fixture_valid(self):
        with tempfile.TemporaryDirectory() as d:
            part = os.path.join(d, "input", "simple_plate")
            _copy_fixture(part)
            res = P.run_validate(P.resolve_paths(part))
            self.assertTrue(res.ok, res.all_errors)
            self.assertEqual(res.failing_ids, [])
            self.assertTrue(os.path.isfile(P.resolve_paths(part).validation_report))

    def test_hole_diameter_too_big_flags_m004(self):
        with tempfile.TemporaryDirectory() as d:
            part = os.path.join(d, "input", "simple_plate")
            _copy_fixture(part)
            f = os.path.join(part, "measurement-input.json")
            doc = json.load(open(f, encoding="utf-8"))
            for m in doc["measurements"]:
                if m["id"] == "M004":
                    m["value"] = 80.0  # >= min face span (60)
            json.dump(doc, open(f, "w", encoding="utf-8"), indent=2)
            res = P.run_validate(P.resolve_paths(part))
            self.assertFalse(res.ok)
            self.assertIn("M004", res.failing_ids)


class PlanParityTests(unittest.TestCase):
    def test_wrapper_plan_matches_cli_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as d:
            part = os.path.join(d, "input", "simple_plate")
            _copy_fixture(part)
            meas = os.path.join(part, "measurement-input.json")
            intent = os.path.join(part, "feature-intent.json")

            # wrapper
            wrap_out = os.path.join(d, "wrap")
            paths = P.resolve_paths(part, out_dir=wrap_out)
            self.assertTrue(P.run_validate(paths).ok)
            pr = P.run_plan(paths)
            self.assertTrue(pr.ok, pr.error)
            self.assertEqual([f["id"] for f in pr.features], ["F001", "F002", "F003"])

            # CLI, same input path
            cli_out = os.path.join(d, "cli")
            rc = subprocess.call([sys.executable, os.path.join(REPO, "scripts", "plan_cad.py"),
                                  "--measurements", meas, "--intent", intent, "--out-dir", cli_out],
                                 stdout=subprocess.DEVNULL)
            self.assertEqual(rc, 0)

            a = open(os.path.join(wrap_out, "cad-plan.json"), "rb").read()
            b = open(os.path.join(cli_out, "cad-plan.json"), "rb").read()
            self.assertEqual(a, b, "wrapper cad-plan.json must be byte-identical to the CLI's")

    def test_plan_without_feature_intent_errors(self):
        with tempfile.TemporaryDirectory() as d:
            part = os.path.join(d, "input", "simple_plate")
            os.makedirs(part)
            shutil.copy(os.path.join(FIX, "measurement-input.json"),
                        os.path.join(part, "measurement-input.json"))
            pr = P.run_plan(P.resolve_paths(part, out_dir=os.path.join(d, "o")))
            self.assertFalse(pr.ok)
            self.assertIn("feature-intent.json", pr.error)


class MeasurementFormTests(unittest.TestCase):
    def test_round_trip_preserves_non_value_fields(self):
        with tempfile.TemporaryDirectory() as d:
            part = os.path.join(d, "input", "simple_plate")
            _copy_fixture(part)
            paths = P.resolve_paths(part)
            doc = P.load_measurement_request(paths)
            originals = {m["id"]: dict(m) for m in doc["measurements"]}

            new_vals = {mid: 42.5 for mid in originals}
            P.write_measurement_input(paths, new_vals)

            back = json.load(open(paths.measurement_input, encoding="utf-8"))
            self.assertEqual([m["id"] for m in back["measurements"]],
                             [m["id"] for m in doc["measurements"]])  # order preserved
            for m in back["measurements"]:
                o = originals[m["id"]]
                self.assertEqual(m["value"], 42.5)
                for key in ("id", "name", "unit", "type", "required", "measurement_instruction"):
                    self.assertEqual(m[key], o[key], f"{m['id']}.{key} changed")
            # untouched top-level keys survive
            self.assertEqual(back["part"], doc["part"])
            self.assertEqual(back["reference"], doc["reference"])

    def test_none_value_written_as_null(self):
        with tempfile.TemporaryDirectory() as d:
            part = os.path.join(d, "input", "simple_plate")
            _copy_fixture(part)
            paths = P.resolve_paths(part)
            P.write_measurement_input(paths, {"M001": None})
            back = json.load(open(paths.measurement_input, encoding="utf-8"))
            m1 = next(m for m in back["measurements"] if m["id"] == "M001")
            self.assertIsNone(m1["value"])


if __name__ == "__main__":
    unittest.main()
