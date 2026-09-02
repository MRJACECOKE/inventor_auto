#!/usr/bin/env python3
"""Validate a Photo-to-IPT measurement JSON.

Two gates, run in order. Both must pass before CAD planning:

  1. Schema validation  -> schemas/measurement.schema.json (JSON Schema 2020-12).
     Uses the `jsonschema` package if importable, else scripts/_schema_lite.py.
  2. Geometry / engineering consistency validation (VAL-002 in docs/spec/01).

Usage:
  python scripts/validate_measurements.py input/<part>/measurement-input.json
      [--schema schemas/measurement.schema.json]
      [--report output/<part>/validation-report.json]
      [--quiet]

Exit code 0 = valid, 1 = MEASUREMENT_VALIDATION_FAILED, 2 = bad invocation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

DEFAULT_SCHEMA = os.path.join(REPO, "schemas", "measurement.schema.json")

_LEN_TO_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4}

# name-heuristic groups
_STRICT_POSITIVE = ("thickness", "width", "height", "diameter", "_dia", "depth",
                    "length", "radius", "spacing", "pitch", "span", "bore")
_NON_NEGATIVE = ("pos", "from_", "distance", "offset", "edge_distance", "_x", "_y")


def _fail(errs, msg):
    errs.append(msg)


def to_mm(value, unit):
    return value * _LEN_TO_MM[unit]


def load_schema(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def schema_validate(instance, schema):
    """Return (errors:list[str], engine:str)."""
    try:
        import jsonschema  # type: ignore

        v = jsonschema.Draft202012Validator(schema)
        errs = [
            f"{'/'.join(str(p) for p in e.absolute_path) or '$'}: {e.message}"
            for e in sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path))
        ]
        return errs, "jsonschema"
    except ImportError:
        import _schema_lite

        return _schema_lite.validate(instance, schema), "_schema_lite"


# --------------------------------------------------------------------------- #
# geometry / engineering consistency
# --------------------------------------------------------------------------- #

def _index(measurements):
    return {m["id"]: m for m in measurements}


def _resolved_mm(m):
    """value in mm for a length measurement, or None if unusable."""
    if m["value"] is None:
        return None
    if m["type"] != "length":
        return None
    if m["unit"] not in _LEN_TO_MM:
        return None
    return to_mm(m["value"], m["unit"])


def _name_has(name, needles):
    return any(n in name for n in needles)


def _check_ids(doc, errs):
    seen = {}
    for coll in ("measurements", "derived"):
        for item in doc.get(coll, []):
            i = item.get("id")
            if i in seen:
                _fail(errs, f"{i}: duplicate id (also used in {seen[i]})")
            else:
                seen[i] = coll


def _check_units_types(doc, errs):
    for m in doc["measurements"]:
        t, u = m["type"], m["unit"]
        if t == "length" and u not in _LEN_TO_MM:
            _fail(errs, f"{m['id']}: type 'length' needs unit mm|cm|in, got '{u}'")
        if t == "angle" and u != "deg":
            _fail(errs, f"{m['id']}: type 'angle' needs unit 'deg', got '{u}'")
        if t == "count" and u != "count":
            _fail(errs, f"{m['id']}: type 'count' needs unit 'count', got '{u}'")


def _check_values(doc, errs):
    for m in doc["measurements"]:
        mid, name, val = m["id"], m["name"], m["value"]
        if m["required"] and val is None:
            _fail(errs, f"{mid}: required value missing")
            continue
        if val is None:
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
            _fail(errs, f"{mid}: value must be a finite number, got {val!r}")
            continue
        if m["type"] == "count":
            if float(val) != int(val) or int(val) < 1:
                _fail(errs, f"{mid}: count must be an integer >= 1, got {val}")
        elif m["type"] == "length":
            if _name_has(name, _STRICT_POSITIVE) and val <= 0:
                _fail(errs, f"{mid} ({name}): must be > 0, got {val}")
            elif _name_has(name, _NON_NEGATIVE) and val < 0:
                _fail(errs, f"{mid} ({name}): must be >= 0, got {val}")
            elif val < 0:
                _fail(errs, f"{mid} ({name}): negative length {val}")
        elif m["type"] == "angle":
            hi = 360.0 if _name_has(name, ("pattern", "total", "sweep")) else 180.0
            if not (0.0 < val <= hi):
                _fail(errs, f"{mid} ({name}): angle must be in (0, {hi:g}] deg, got {val}")


def _face_span_mm(idx):
    spans = []
    for m in idx.values():
        if m["type"] == "length" and _name_has(m["name"], ("overall_width", "overall_height",
                                                           "plate_width", "plate_height",
                                                           "body_width", "body_height")):
            mm = _resolved_mm(m)
            if mm:
                spans.append((m["id"], m["name"], mm))
    return spans


def _check_hole_vs_face(doc, errs):
    idx = _index(doc["measurements"])
    spans = _face_span_mm(idx)
    if not spans:
        return
    min_span = min(s[2] for s in spans)
    min_span_name = min(spans, key=lambda s: s[2])[1]
    for m in doc["measurements"]:
        if m["type"] != "length":
            continue
        if not _name_has(m["name"], ("hole", "bore")) or not _name_has(m["name"], ("dia", "diameter")):
            continue
        mm = _resolved_mm(m)
        if mm is None:
            continue
        if mm >= min_span:
            _fail(errs, f"{m['id']}: hole diameter ({mm:g} mm) >= available face span "
                        f"({min_span:g} mm, {min_span_name})")


def _check_hole_center_inside(doc, errs):
    idx = _index(doc["measurements"])
    width = height = None
    for m in idx.values():
        mm = _resolved_mm(m)
        if mm is None:
            continue
        if _name_has(m["name"], ("overall_width", "plate_width", "body_width")):
            width = mm
        if _name_has(m["name"], ("overall_height", "plate_height", "body_height")):
            height = mm
    # group hole radius by hole prefix (hole_1_*, hole_a_*)
    def hole_key(name):
        mobj = re.match(r"(hole[_a-z0-9]*?)(_|$)", name)
        return mobj.group(1) if mobj else None

    radii = {}
    for m in idx.values():
        if _name_has(m["name"], ("dia", "diameter")) and _name_has(m["name"], ("hole", "bore")):
            mm = _resolved_mm(m)
            if mm:
                radii[hole_key(m["name"])] = mm / 2.0

    for m in idx.values():
        mm = _resolved_mm(m)
        if mm is None:
            continue
        k = hole_key(m["name"])
        r = radii.get(k, 0.0)
        if _name_has(m["name"], ("pos_x", "from_left", "_x_from", "x_from_origin")) and width:
            if mm - r < 0 or mm + r > width:
                _fail(errs, f"{m['id']}: hole center X ({mm:g} mm) +/- r ({r:g}) falls outside "
                            f"body width (0..{width:g} mm)")
        if _name_has(m["name"], ("pos_y", "from_bottom", "_y_from", "y_from_origin")) and height:
            if mm - r < 0 or mm + r > height:
                _fail(errs, f"{m['id']}: hole center Y ({mm:g} mm) +/- r ({r:g}) falls outside "
                            f"body height (0..{height:g} mm)")


def _check_fillet_chamfer_sane(doc, errs):
    idx = _index(doc["measurements"])
    spans = _face_span_mm(idx)
    if not spans:
        return
    half_min = min(s[2] for s in spans) / 2.0
    for m in doc["measurements"]:
        if m["type"] != "length":
            continue
        if not _name_has(m["name"], ("fillet", "chamfer", "corner_radius")):
            continue
        mm = _resolved_mm(m)
        if mm is None:
            continue
        if mm >= half_min:
            _fail(errs, f"{m['id']}: {m['name']} ({mm:g} mm) >= half the smallest face span "
                        f"({half_min:g} mm) - geometrically impossible")


_ALLOWED_FORMULA = re.compile(r"^[MD0-9_.+\-*/()\s]+$")


def _check_derived(doc, errs):
    idx = _index(doc["measurements"])
    for d in doc.get("derived", []):
        did = d["id"]
        deriv = d["derivation"]
        formula = deriv["formula"]
        srcs = deriv["source_measurement_ids"]
        if not _ALLOWED_FORMULA.match(formula):
            _fail(errs, f"{did}: derivation formula has illegal characters: {formula!r}")
            continue
        symbols = set(re.findall(r"[MD][0-9]{3,}", formula))
        unknown = symbols - set(srcs)
        if unknown:
            _fail(errs, f"{did}: derivation formula references {sorted(unknown)} "
                        f"not in source_measurement_ids")
        missing = [s for s in srcs if s not in idx and not s.startswith("D")]
        if missing:
            _fail(errs, f"{did}: derivation references unknown id(s) {missing}")
            continue
        env = {}
        ok = True
        for s in srcs:
            src = idx.get(s)
            if src is None or src["value"] is None:
                _fail(errs, f"{did}: derivation source {s} has no value")
                ok = False
                break
            env[s] = src["value"]
        if ok:
            try:
                eval(compile(formula, "<derivation>", "eval"), {"__builtins__": {}}, env)
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                _fail(errs, f"{did}: derivation formula failed to evaluate: {exc}")


def _check_symmetry(doc, errs):
    seen_planes = set()
    for s in doc["reference"].get("symmetry", []):
        if s["type"] == "mirror":
            if "plane" not in s:
                _fail(errs, "reference.symmetry: mirror entry needs a 'plane'")
            elif s["plane"] in seen_planes:
                _fail(errs, f"reference.symmetry: duplicate mirror plane '{s['plane']}'")
            else:
                seen_planes.add(s["plane"])
        if s["type"] == "rotational" and ("axis" not in s or "count" not in s):
            _fail(errs, "reference.symmetry: rotational entry needs 'axis' and 'count'")


def geometry_validate(doc):
    errs = []
    _check_ids(doc, errs)
    _check_units_types(doc, errs)
    _check_values(doc, errs)
    _check_hole_vs_face(doc, errs)
    _check_hole_center_inside(doc, errs)
    _check_fillet_chamfer_sane(doc, errs)
    _check_derived(doc, errs)
    _check_symmetry(doc, errs)
    return errs


# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a measurement JSON (schema + geometry).")
    ap.add_argument("input")
    ap.add_argument("--schema", default=DEFAULT_SCHEMA)
    ap.add_argument("--report", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        print(f"error: no such file: {args.input}", file=sys.stderr)
        return 2
    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except json.JSONDecodeError as exc:
        print("MEASUREMENT_VALIDATION_FAILED\n", file=sys.stderr)
        print(f"- {args.input}: invalid JSON: {exc}", file=sys.stderr)
        return 1

    schema = load_schema(args.schema)
    schema_errs, engine = schema_validate(doc, schema)

    geom_errs = []
    if not schema_errs:
        geom_errs = geometry_validate(doc)

    all_errs = [f"[schema] {e}" for e in schema_errs] + [f"[geometry] {e}" for e in geom_errs]
    ok = not all_errs

    n_meas = len(doc.get("measurements", [])) if isinstance(doc, dict) else 0
    n_req_null = 0
    if isinstance(doc, dict):
        n_req_null = sum(1 for m in doc.get("measurements", [])
                         if m.get("required") and m.get("value") is None)

    report = {
        "input": args.input,
        "schema": args.schema,
        "schema_engine": engine,
        "ok": ok,
        "counts": {
            "measurements": n_meas,
            "derived": len(doc.get("derived", [])) if isinstance(doc, dict) else 0,
            "required_unresolved": n_req_null,
        },
        "schema_errors": schema_errs,
        "geometry_errors": geom_errs,
    }
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")

    if ok:
        if not args.quiet:
            print("MEASUREMENT_VALIDATION_OK")
            print(f"{n_meas} measurements, {report['counts']['derived']} derived, "
                  f"all required values resolved  (schema engine: {engine})")
        return 0

    print("MEASUREMENT_VALIDATION_FAILED\n")
    for e in all_errs:
        print(f"- {e}")
    print("\nPlease correct these fields.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
