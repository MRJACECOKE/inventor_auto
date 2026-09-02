#!/usr/bin/env python3
"""Build a deterministic CAD feature plan from validated engineering facts.

Inputs
  --measurements  input/<part>/measurement-input.json   (the SSOT: real dimensions)
  --intent        input/<part>/feature-intent.json      (structure from image analysis:
                  which measurement drives which parameter, sketch planes, feature order)

Output (into --out-dir, default output/<part-name>/)
  cad-plan.json   deterministic, schema-valid, parameters bound to measurement IDs
  cad-plan.md     human-readable ordered feature list + parameter map

The photo/measurement separation (SYS-002) is enforced here: every feature
dimension must resolve to a named parameter that carries a measurement_id or a
derivation. Bare numeric literals in features are rejected.

Exit 0 = plan written, 3 = plan error (unbound dim / unsupported feature / invalid
plan / measurement validation failed), 2 = bad invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import validate_measurements as vm  # noqa: E402

PLAN_SCHEMA = os.path.join(REPO, "schemas", "cad-feature-plan.schema.json")

SUPPORTED = {
    "base_extrude", "extrude_add", "extrude_cut", "revolve",
    "hole", "slot", "fillet", "chamfer", "mirror",
    "rectangular_pattern", "circular_pattern",
}
DEFERRED = {"shell", "thread", "work_plane", "work_axis"}

_PARAM_KEY_RE = re.compile(r".*_param$")
_ID_RE = re.compile(r"[MD][0-9]{3,}")
_ALLOWED_FORMULA = re.compile(r"^[MD0-9_.+\-*/()\s]+$")


class PlanError(Exception):
    pass


class UnboundDimensionError(PlanError):
    pass


class FeatureUnsupportedError(PlanError):
    pass


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _snake(name):
    s = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "param"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _eval_formula(formula, env):
    if not _ALLOWED_FORMULA.match(formula):
        raise PlanError(f"illegal characters in derivation formula: {formula!r}")
    return float(eval(compile(formula, "<derivation>", "eval"), {"__builtins__": {}}, env))


def _resolve_parameters(intent, m_by_id):
    """intent['parameters'][key] -> {'measurement_id'|'derivation', ...}
    Returns an ordered dict key -> {value, unit, (measurement_id|derivation)}.
    """
    params = {}
    for key in sorted(intent["parameters"]):  # deterministic order
        spec = intent["parameters"][key]
        if "measurement_id" in spec:
            mid = spec["measurement_id"]
            m = m_by_id.get(mid)
            if m is None:
                raise PlanError(f"parameter '{key}' references unknown measurement {mid}")
            if m["value"] is None:
                raise UnboundDimensionError(
                    f"parameter '{key}' needs measurement {mid} ({m['name']}) but its value is null"
                )
            params[key] = {
                "measurement_id": mid,
                "value": float(m["value"]),
                "unit": m["unit"],
            }
        elif "derivation" in spec:
            deriv = spec["derivation"]
            srcs = deriv["source_measurement_ids"]
            env = {}
            for s in srcs:
                sm = m_by_id.get(s)
                if sm is None or sm["value"] is None:
                    raise UnboundDimensionError(
                        f"parameter '{key}' derivation source {s} has no value"
                    )
                env[s] = float(sm["value"])
            symbols = set(_ID_RE.findall(deriv["formula"]))
            if symbols - set(srcs):
                raise PlanError(
                    f"parameter '{key}' derivation references {sorted(symbols - set(srcs))} "
                    f"outside source_measurement_ids"
                )
            value = _eval_formula(deriv["formula"], env)
            unit = spec.get("unit") or m_by_id[srcs[0]]["unit"]
            params[key] = {"derivation": deriv, "value": value, "unit": unit}
        else:
            raise PlanError(f"parameter '{key}' has neither measurement_id nor derivation")
    return params


def _iter_param_refs(node):
    """Yield every value of a key ending in '_param' (recursively)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if _PARAM_KEY_RE.match(k) and isinstance(v, str):
                yield v
            else:
                yield from _iter_param_refs(v)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_param_refs(item)


def _check_bindings(intent, params):
    known = set(params)
    refs = set(_iter_param_refs({"sketches": intent["sketches"], "features": intent["features"]}))
    missing = sorted(refs - known)
    if missing:
        raise UnboundDimensionError(
            "these *_param references are not defined in feature-intent parameters: "
            + ", ".join(missing)
        )
    unused = sorted(known - refs)
    return unused


def _order_features(features):
    by_id = {f["id"]: f for f in features}
    for f in features:
        for dep in f.get("depends_on", []):
            if dep not in by_id:
                raise PlanError(f"feature {f['id']} depends_on unknown feature {dep}")
    ordered = []
    placed = set()
    # deterministic Kahn: repeatedly take the lexicographically smallest id whose
    # deps are all placed
    remaining = sorted(by_id)
    while remaining:
        progress = False
        for fid in list(remaining):
            if all(d in placed for d in by_id[fid].get("depends_on", [])):
                ordered.append(by_id[fid])
                placed.add(fid)
                remaining.remove(fid)
                progress = True
                break
        if not progress:
            raise PlanError(f"dependency cycle among features: {remaining}")
    return ordered


def _check_feature_types(features):
    for f in features:
        t = f["type"]
        if t in DEFERRED:
            raise FeatureUnsupportedError(
                f"{f['id']}: feature type '{t}' is specced but not implemented in v1"
            )
        if t not in SUPPORTED:
            raise FeatureUnsupportedError(f"{f['id']}: unknown feature type '{t}'")


def build_plan(measurements_path, intent_path):
    mdoc = _load(measurements_path)
    intent = _load(intent_path)
    m_by_id = {m["id"]: m for m in mdoc["measurements"]}

    part_name = intent.get("part_name") or mdoc["part"]["name"]
    part_name = re.sub(r"[^A-Za-z0-9_.-]", "_", part_name)

    _check_feature_types(intent["features"])
    params = _resolve_parameters(intent, m_by_id)
    _check_bindings(intent, params)
    ordered = _order_features(intent["features"])

    plan = {
        "plan_version": "1.0",
        "part_name": part_name,
        "units": mdoc["part"]["units"],
        "provenance": {
            "measurement_file": measurements_path.replace("\\", "/"),
            "measurement_sha256": _sha256(measurements_path),
            "source_images": [img["id"] for img in mdoc["source_images"]],
        },
        "parameters": {
            k: _plan_param(v) for k, v in params.items()
        },
        "sketches": intent["sketches"],
        "features": ordered,
    }
    return plan, params


def _plan_param(v):
    out = {"value": round(v["value"], 9), "unit": v["unit"]}
    if "measurement_id" in v:
        out["measurement_id"] = v["measurement_id"]
    if "derivation" in v:
        out["derivation"] = v["derivation"]
    return out


def _write_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _feature_line(f):
    t = f["type"]
    bits = [f"{f['id']} — {t}"]
    if "sketch" in f:
        bits.append(f"sketch {f['sketch']}")
    for k in ("distance_param", "angle_param", "diameter_param", "radius_param",
              "length_param", "width_param", "depth_param", "count_param",
              "x_count_param", "x_spacing_param", "y_count_param", "y_spacing_param"):
        if k in f:
            bits.append(f"{k[:-6]}=p_{f[k]}")
    if "depth" in f:
        bits.append(f"depth={f['depth']}")
    if "direction" in f:
        bits.append(f"dir={f['direction']}")
    if "edges" in f:
        bits.append(f"edges={f['edges']}")
    if "of" in f:
        bits.append(f"of={f['of']}")
    if "plane" in f:
        bits.append(f"plane={f['plane']}")
    if "axis" in f:
        bits.append(f"axis={f['axis']}")
    if f.get("depends_on"):
        bits.append(f"after {','.join(f['depends_on'])}")
    return " · ".join(bits)


def _write_md(plan, params, path):
    lines = []
    lines.append(f"# CAD Feature Plan — {plan['part_name']}")
    lines.append("")
    lines.append(f"- plan_version: {plan['plan_version']}")
    lines.append(f"- units: {plan['units']}")
    lines.append(f"- measurement file: `{plan['provenance']['measurement_file']}`")
    lines.append(f"- measurement sha256: `{plan['provenance']['measurement_sha256']}`")
    lines.append(f"- source images: {', '.join(plan['provenance']['source_images'])}")
    lines.append("")
    lines.append("## Feature order")
    lines.append("")
    for i, f in enumerate(plan["features"], 1):
        lines.append(f"{i}. {_feature_line(f)}")
    lines.append("")
    lines.append("## Parameter map")
    lines.append("")
    lines.append("| parameter | source | value | unit |")
    lines.append("|---|---|---|---|")
    for k, v in sorted(plan["parameters"].items()):
        src = v.get("measurement_id") or ("derived: " + v["derivation"]["formula"])
        lines.append(f"| p_{k} | {src} | {v['value']:g} | {v['unit']} |")
    lines.append("")
    lines.append("## Sketches")
    lines.append("")
    for s in plan["sketches"]:
        where = s["plane"]
        if s.get("offset_param"):
            sign = "-" if s.get("offset") == "negative" else "+"
            where += f" offset {sign}p_{s['offset_param']}"
        lines.append(f"- {s['id']} on {where}: {json.dumps(s['profile'], sort_keys=True)}")
    lines.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measurement JSON + feature intent -> cad-plan.json/.md")
    ap.add_argument("--measurements", required=True)
    ap.add_argument("--intent", required=True)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--skip-validate", action="store_true",
                    help="skip re-running validate_measurements (tests only)")
    args = ap.parse_args(argv)

    for p in (args.measurements, args.intent):
        if not os.path.isfile(p):
            print(f"error: no such file: {p}", file=sys.stderr)
            return 2

    if not args.skip_validate:
        rc = vm.main([args.measurements, "--quiet"])
        if rc != 0:
            print("PLAN_ABORTED: measurement validation failed (run validate_measurements.py)",
                  file=sys.stderr)
            return 3

    try:
        plan, params = build_plan(args.measurements, args.intent)
    except PlanError as exc:
        print(f"PLAN_FAILED\n\n- {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    schema = vm.load_schema(PLAN_SCHEMA)
    errs, engine = vm.schema_validate(plan, schema)
    if errs:
        print("PLAN_FAILED\n\n- cad-plan.json does not satisfy its own schema "
              f"(engine: {engine}):", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 3

    out_dir = args.out_dir or os.path.join(REPO, "output", plan["part_name"])
    _write_json(plan, os.path.join(out_dir, "cad-plan.json"))
    _write_md(plan, params, os.path.join(out_dir, "cad-plan.md"))
    print(f"PLAN_OK  {plan['part_name']}  "
          f"{len(plan['parameters'])} params, {len(plan['features'])} features  "
          f"(schema engine: {engine})")
    print(f"  {os.path.join(out_dir, 'cad-plan.json')}")
    print(f"  {os.path.join(out_dir, 'cad-plan.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
