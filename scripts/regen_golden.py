#!/usr/bin/env python3
"""Regenerate (or check) the committed golden CAD plans.

The pipeline is required to be deterministic: given the same measurement JSON and
feature intent, `scripts/plan_cad.py` must produce a byte-identical `cad-plan.json`
(SYS-001, `docs/spec/01`). This script pins that guarantee to disk.

Layout:
  tests/fixtures/parts/<part>/measurement-input.json   committed real inputs
  tests/fixtures/parts/<part>/feature-intent.json
  tests/golden/<part>/cad-plan.json                    committed expected output
  tests/golden/<part>/cad-plan.md

Usage:
  python scripts/regen_golden.py            # rewrite goldens from the fixtures
  python scripts/regen_golden.py --check    # fail (exit 1) if any golden drifted

`--check` is what CI runs. `tests/test_determinism.py` covers the same ground from
unittest; this script is the operator-facing way to update the goldens on a
deliberate change.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import plan_cad  # noqa: E402

FIXTURES = os.path.join(REPO, "tests", "fixtures", "parts")
GOLDEN = os.path.join(REPO, "tests", "golden")


def _canon_json(plan) -> str:
    """Exactly how plan_cad._write_json serialises: indent=2, sort_keys, trailing \\n."""
    return json.dumps(plan, indent=2, sort_keys=True) + "\n"


def discover_parts() -> list[str]:
    if not os.path.isdir(FIXTURES):
        return []
    parts = []
    for name in sorted(os.listdir(FIXTURES)):
        d = os.path.join(FIXTURES, name)
        if (os.path.isfile(os.path.join(d, "measurement-input.json"))
                and os.path.isfile(os.path.join(d, "feature-intent.json"))):
            parts.append(name)
    return parts


def build(part: str):
    """Build the plan with a repo-relative measurement path so `provenance`
    (which records the path verbatim) is machine-independent."""
    rel_meas = f"tests/fixtures/parts/{part}/measurement-input.json"
    rel_intent = f"tests/fixtures/parts/{part}/feature-intent.json"
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        plan, params = plan_cad.build_plan(rel_meas, rel_intent)
    finally:
        os.chdir(cwd)
    return plan, params


def check() -> int:
    parts = discover_parts()
    if not parts:
        print("regen_golden: no fixtures under tests/fixtures/parts/", file=sys.stderr)
        return 1
    failures = 0
    for part in parts:
        golden_path = os.path.join(GOLDEN, part, "cad-plan.json")
        plan, _ = build(part)
        got = _canon_json(plan)
        if not os.path.isfile(golden_path):
            print(f"MISSING GOLDEN: {golden_path} (run: python scripts/regen_golden.py)")
            failures += 1
            continue
        with open(golden_path, "r", encoding="utf-8") as fh:
            want = fh.read()
        if got != want:
            failures += 1
            print(f"DRIFT: {part}/cad-plan.json no longer matches the golden")
            diff = difflib.unified_diff(
                want.splitlines(keepends=True), got.splitlines(keepends=True),
                fromfile=f"golden/{part}/cad-plan.json", tofile=f"regenerated/{part}/cad-plan.json",
            )
            sys.stdout.writelines(diff)
        # second build must be byte-identical to the first (in-run determinism)
        plan2, _ = build(part)
        if _canon_json(plan2) != got:
            failures += 1
            print(f"NONDETERMINISTIC: {part} produced two different plans in one run")
    if failures:
        print(f"\nregen_golden --check: {failures} problem(s). "
              f"If the change is intended: python scripts/regen_golden.py")
        return 1
    print(f"regen_golden --check: OK ({len(parts)} part(s) match their golden)")
    return 0


def regen() -> int:
    parts = discover_parts()
    if not parts:
        print("regen_golden: no fixtures under tests/fixtures/parts/", file=sys.stderr)
        return 1
    for part in parts:
        plan, params = build(part)
        out_dir = os.path.join(GOLDEN, part)
        os.makedirs(out_dir, exist_ok=True)
        plan_cad._write_json(plan, os.path.join(out_dir, "cad-plan.json"))
        plan_cad._write_md(plan, params, os.path.join(out_dir, "cad-plan.md"))
        print(f"wrote golden: tests/golden/{part}/cad-plan.json  "
              f"({len(plan['parameters'])} params, {len(plan['features'])} features)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true",
                    help="verify goldens instead of rewriting them (exit 1 on drift)")
    args = ap.parse_args(argv)
    return check() if args.check else regen()


if __name__ == "__main__":
    raise SystemExit(main())
