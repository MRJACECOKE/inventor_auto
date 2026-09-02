"""Non-Inventor tests for scripts/validate_measurements.py and scripts/_schema_lite.py.

Run: python tests/run_tests.py   (or:  python -m unittest discover -s tests)
"""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import _schema_lite  # noqa: E402
import validate_measurements as vm  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "simple_plate", "measurement-input.json")
SCHEMA = os.path.join(REPO, "schemas", "measurement.schema.json")


def load_fixture():
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def schema():
    return vm.load_schema(SCHEMA)


def run_all(doc):
    """schema errors + geometry errors as one flat list of strings."""
    s_errs, _ = vm.schema_validate(doc, schema())
    g_errs = vm.geometry_validate(doc) if not s_errs else []
    return s_errs, g_errs


class SchemaTests(unittest.TestCase):
    def test_schema_accepts_fixture(self):
        errs, _ = vm.schema_validate(load_fixture(), schema())
        self.assertEqual(errs, [], f"fixture should be schema-valid, got {errs}")

    def test_schema_rejects_unknown_top_level_field(self):
        doc = load_fixture()
        doc["totally_unexpected"] = 1
        errs, _ = vm.schema_validate(doc, schema())
        self.assertTrue(any("unknown property 'totally_unexpected'" in e or
                            "totally_unexpected" in e for e in errs), errs)

    def test_schema_rejects_missing_unit(self):
        doc = load_fixture()
        del doc["measurements"][0]["unit"]
        errs, _ = vm.schema_validate(doc, schema())
        self.assertTrue(any("unit" in e for e in errs), errs)

    def test_schema_rejects_bad_measurement_id_pattern(self):
        doc = load_fixture()
        doc["measurements"][0]["id"] = "X1"
        errs, _ = vm.schema_validate(doc, schema())
        self.assertTrue(any("does not match" in e and "X1" in e for e in errs), errs)

    def test_schema_lite_enum_and_pattern(self):
        s = {"type": "object", "properties": {"u": {"enum": ["mm", "deg"]}},
             "required": ["u"], "additionalProperties": False}
        self.assertEqual(_schema_lite.validate({"u": "mm"}, s), [])
        self.assertTrue(_schema_lite.validate({"u": "km"}, s))

    def test_schema_lite_ref_resolution(self):
        s = {"type": "object", "properties": {"a": {"$ref": "#/$defs/x"}},
             "$defs": {"x": {"type": "integer", "minimum": 0}}}
        self.assertEqual(_schema_lite.validate({"a": 3}, s), [])
        self.assertTrue(_schema_lite.validate({"a": -1}, s))


class GeometryTests(unittest.TestCase):
    def test_fixture_passes_geometry(self):
        s_errs, g_errs = run_all(load_fixture())
        self.assertEqual(s_errs, [])
        self.assertEqual(g_errs, [], f"fixture geometry should pass, got {g_errs}")

    def test_required_value_missing(self):
        doc = load_fixture()
        doc["measurements"][2]["value"] = None  # thickness, required
        _, g = run_all(doc)
        self.assertTrue(any(e.startswith("M003") and "required value missing" in e for e in g), g)

    def test_zero_thickness(self):
        doc = load_fixture()
        doc["measurements"][2]["value"] = 0.0
        _, g = run_all(doc)
        self.assertTrue(any("M003" in e and "> 0" in e for e in g), g)

    def test_negative_length(self):
        doc = load_fixture()
        doc["measurements"][0]["value"] = -5.0
        _, g = run_all(doc)
        self.assertTrue(any("M001" in e for e in g), g)

    def test_hole_diameter_exceeds_face(self):
        doc = load_fixture()
        doc["measurements"][3]["value"] = 80.0  # hole_dia >= min span (60)
        _, g = run_all(doc)
        self.assertTrue(any("M004" in e and "face span" in e for e in g), g)

    def test_hole_center_outside_body(self):
        doc = load_fixture()
        doc["measurements"][4]["value"] = 99.0  # hole_x near right edge, r=4 -> 103 > 100
        _, g = run_all(doc)
        self.assertTrue(any("M005" in e and "outside" in e for e in g), g)

    def test_fillet_radius_impossible(self):
        doc = load_fixture()
        doc["measurements"][6]["value"] = 40.0  # >= half of 60
        _, g = run_all(doc)
        self.assertTrue(any("M007" in e and "impossible" in e for e in g), g)

    def test_duplicate_ids(self):
        doc = load_fixture()
        doc["measurements"][1]["id"] = "M001"
        _, g = run_all(doc)
        self.assertTrue(any("M001" in e and "duplicate" in e for e in g), g)

    def test_unit_type_mismatch(self):
        doc = load_fixture()
        doc["measurements"][0]["type"] = "angle"  # but unit is mm
        _, g = run_all(doc)
        self.assertTrue(any("M001" in e and "deg" in e for e in g), g)

    def test_count_must_be_positive_integer(self):
        doc = load_fixture()
        doc["measurements"].append({
            "id": "M050", "name": "hole_count", "value": 0, "unit": "count", "type": "count",
            "required": True, "measurement_instruction": "count the holes",
        })
        _, g = run_all(doc)
        self.assertTrue(any("M050" in e and "integer >= 1" in e for e in g), g)

    def test_pattern_angle_out_of_range(self):
        doc = load_fixture()
        doc["measurements"].append({
            "id": "M060", "name": "circular_pattern_total_angle", "value": 400.0,
            "unit": "deg", "type": "angle", "required": True,
            "measurement_instruction": "total sweep angle",
        })
        _, g = run_all(doc)
        self.assertTrue(any("M060" in e and "(0, 360]" in e for e in g), g)

    def test_derived_unknown_source(self):
        doc = load_fixture()
        doc["derived"].append({
            "id": "D001", "name": "span", "type": "length", "unit": "mm",
            "derivation": {"formula": "M001 + M999", "source_measurement_ids": ["M001", "M999"]},
        })
        _, g = run_all(doc)
        self.assertTrue(any("D001" in e and "M999" in e for e in g), g)

    def test_derived_formula_symbol_not_in_sources(self):
        doc = load_fixture()
        doc["derived"].append({
            "id": "D002", "name": "span", "type": "length", "unit": "mm",
            "derivation": {"formula": "M001 + M002", "source_measurement_ids": ["M001"]},
        })
        _, g = run_all(doc)
        self.assertTrue(any("D002" in e and "M002" in e for e in g), g)

    def test_cli_pass_and_fail(self):
        rc = vm.main([FIXTURE, "--quiet"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
