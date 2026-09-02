"""Non-Inventor tests for scripts/plan_cad.py."""
import copy
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import plan_cad  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "simple_plate")
MEAS = os.path.join(FIX, "measurement-input.json")
INTENT = os.path.join(FIX, "feature-intent.json")


def _tmp(obj):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return path


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class PlanTests(unittest.TestCase):
    def test_build_plan_ok(self):
        plan, params = plan_cad.build_plan(MEAS, INTENT)
        self.assertEqual(plan["part_name"], "simple_plate")
        self.assertEqual(len(plan["features"]), 3)
        self.assertEqual(len(plan["parameters"]), 7)

    def test_every_parameter_bound_to_measurement_or_derivation(self):
        plan, _ = plan_cad.build_plan(MEAS, INTENT)
        for k, v in plan["parameters"].items():
            self.assertTrue(("measurement_id" in v) ^ ("derivation" in v),
                            f"parameter {k} must have exactly one of measurement_id/derivation")

    def test_no_unbound_feature_dimension(self):
        intent = load(INTENT)
        # reference a param that does not exist
        intent["features"][0]["distance_param"] = "ghost"
        p = _tmp(intent)
        try:
            with self.assertRaises(plan_cad.UnboundDimensionError):
                plan_cad.build_plan(MEAS, p)
        finally:
            os.remove(p)

    def test_feature_order_is_stable_topological(self):
        intent = load(INTENT)
        # shuffle feature list; order in output must not change
        intent["features"] = list(reversed(intent["features"]))
        p = _tmp(intent)
        try:
            plan, _ = plan_cad.build_plan(MEAS, p)
            self.assertEqual([f["id"] for f in plan["features"]], ["F001", "F002", "F003"])
        finally:
            os.remove(p)

    def test_dependency_cycle_rejected(self):
        intent = load(INTENT)
        intent["features"][0]["depends_on"] = ["F002"]  # F001<-F002, F002<-F001
        p = _tmp(intent)
        try:
            with self.assertRaises(plan_cad.PlanError):
                plan_cad.build_plan(MEAS, p)
        finally:
            os.remove(p)

    def test_unsupported_feature_rejected(self):
        for bad in ("shell", "thread", "work_plane", "work_axis"):
            intent = load(INTENT)
            intent["features"].append({"id": "F099", "type": bad, "depends_on": ["F001"]})
            p = _tmp(intent)
            try:
                with self.assertRaises(plan_cad.FeatureUnsupportedError):
                    plan_cad.build_plan(MEAS, p)
            finally:
                os.remove(p)

    def test_unknown_feature_type_rejected(self):
        intent = load(INTENT)
        intent["features"].append({"id": "F098", "type": "wibble", "depends_on": ["F001"]})
        p = _tmp(intent)
        try:
            with self.assertRaises(plan_cad.FeatureUnsupportedError):
                plan_cad.build_plan(MEAS, p)
        finally:
            os.remove(p)

    def test_null_required_measurement_makes_plan_unbound(self):
        meas = load(MEAS)
        meas["measurements"][2]["value"] = None  # thickness
        p = _tmp(meas)
        try:
            with self.assertRaises(plan_cad.UnboundDimensionError):
                plan_cad.build_plan(p, INTENT)
        finally:
            os.remove(p)

    def test_derived_parameter_recomputes(self):
        meas = load(MEAS)
        meas["derived"].append({
            "id": "D001", "name": "double_width", "type": "length", "unit": "mm",
            "derivation": {"formula": "M001 * 2", "source_measurement_ids": ["M001"]},
        })
        intent = load(INTENT)
        intent["parameters"]["double_width"] = {
            "derivation": {"formula": "M001 * 2", "source_measurement_ids": ["M001"]},
            "unit": "mm",
        }
        mp, ip = _tmp(meas), _tmp(intent)
        try:
            plan, _ = plan_cad.build_plan(mp, ip)
            self.assertAlmostEqual(plan["parameters"]["double_width"]["value"], 200.0)
        finally:
            os.remove(mp)
            os.remove(ip)

    def test_plan_is_byte_identical_on_rerun(self):
        p1, _ = plan_cad.build_plan(MEAS, INTENT)
        p2, _ = plan_cad.build_plan(MEAS, INTENT)
        self.assertEqual(json.dumps(p1, sort_keys=True), json.dumps(p2, sort_keys=True))

    def test_provenance_sha256_matches_input(self):
        import hashlib
        plan, _ = plan_cad.build_plan(MEAS, INTENT)
        with open(MEAS, "rb") as fh:
            want = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(plan["provenance"]["measurement_sha256"], want)

    def test_plan_self_validates_against_schema(self):
        import validate_measurements as vm
        plan, _ = plan_cad.build_plan(MEAS, INTENT)
        sch = vm.load_schema(plan_cad.PLAN_SCHEMA)
        errs, _ = vm.schema_validate(plan, sch)
        self.assertEqual(errs, [], f"generated plan must satisfy its schema: {errs}")

    def test_polygon_profile_and_offset_sketch_plan(self):
        """Regular-polygon pockets on offset work planes (polygon_cube family)."""
        meas = {
            "schema_version": "1.0",
            "part": {"name": "poly_demo", "units": "mm"},
            "source_images": [{"id": "IMG-001"}],
            "reference": {"origin_definition": "cube centre", "primary_plane": "XY"},
            "measurements": [
                {"id": "M001", "name": "cube_edge", "value": 100.0, "unit": "mm",
                 "type": "length", "required": True, "measurement_instruction": "edge"},
                {"id": "M002", "name": "pocket_depth", "value": 30.0, "unit": "mm",
                 "type": "length", "required": True, "measurement_instruction": "depth"},
                {"id": "M003", "name": "hex_dia", "value": 36.0, "unit": "mm",
                 "type": "length", "required": True, "measurement_instruction": "across corners"},
            ],
        }
        intent = {
            "intent_version": "1.0", "part_name": "poly_demo", "primary_plane": "XY",
            "parameters": {
                "cube_edge": {"measurement_id": "M001"},
                "pocket_depth": {"measurement_id": "M002"},
                "half_edge": {"derivation": {"formula": "M001 / 2",
                                             "source_measurement_ids": ["M001"]}, "unit": "mm"},
                "hex_dia": {"measurement_id": "M003"},
            },
            "sketches": [
                {"id": "S1", "plane": "XY",
                 "profile": {"type": "rectangle", "width_param": "cube_edge",
                             "height_param": "cube_edge", "corner": "center"}},
                {"id": "S2", "plane": "XZ", "offset_param": "half_edge", "offset": "negative",
                 "profile": {"type": "polygon", "sides": 6, "circumdiameter_param": "hex_dia"}},
            ],
            "features": [
                {"id": "F001", "type": "base_extrude", "sketch": "S1",
                 "distance_param": "cube_edge", "direction": "symmetric", "depends_on": []},
                {"id": "F002", "type": "extrude_cut", "sketch": "S2",
                 "distance_param": "pocket_depth", "direction": "positive", "depends_on": ["F001"]},
            ],
        }
        mp, ip = _tmp(meas), _tmp(intent)
        try:
            plan, _ = plan_cad.build_plan(mp, ip)
            self.assertEqual(plan["parameters"]["half_edge"]["value"], 50.0)
            s2 = next(s for s in plan["sketches"] if s["id"] == "S2")
            self.assertEqual(s2["offset_param"], "half_edge")
            self.assertEqual(s2["profile"]["type"], "polygon")
            self.assertEqual(s2["profile"]["sides"], 6)
            import validate_measurements as vm
            sch = vm.load_schema(plan_cad.PLAN_SCHEMA)
            errs, _ = vm.schema_validate(plan, sch)
            self.assertEqual(errs, [], f"polygon/offset plan must satisfy schema: {errs}")
        finally:
            os.remove(mp)
            os.remove(ip)

    def test_polygon_circumdiameter_param_must_be_bound(self):
        intent = load(INTENT)
        intent["sketches"].append({
            "id": "S9", "plane": "YZ", "offset_param": "ghost_offset", "offset": "positive",
            "profile": {"type": "polygon", "sides": 5, "circumdiameter_param": "ghost_dia"},
        })
        p = _tmp(intent)
        try:
            with self.assertRaises(plan_cad.UnboundDimensionError):
                plan_cad.build_plan(MEAS, p)
        finally:
            os.remove(p)

    def test_cli_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            rc = plan_cad.main(["--measurements", MEAS, "--intent", INTENT, "--out-dir", d])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(os.path.join(d, "cad-plan.json")))
            self.assertTrue(os.path.isfile(os.path.join(d, "cad-plan.md")))


if __name__ == "__main__":
    unittest.main()
