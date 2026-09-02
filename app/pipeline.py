"""Headless wrapper over the inventor_auto Phase E-I pipeline.

- validate + plan run IN-PROCESS (import scripts/validate_measurements.py and
  scripts/plan_cad.py) -- no python.exe needed on the target machine.
- the Inventor build shells out to Windows PowerShell 5.1 running
  scripts/inventor_build.ps1 (STA requirement).

The GUI (app/ipt_builder.py) wires buttons to these functions; nothing here
imports PySide6, so it is unit-testable on its own.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import resources

resources.add_scripts_to_syspath()

_ID_RE = re.compile(r"\b[MD][0-9]{3,}\b")


# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #

@dataclass
class Paths:
    part_dir: Path
    part_name: str
    working_root: Path
    out_dir: Path
    measurement_request: Path
    measurement_input: Path
    feature_intent: Path
    validation_report: Path
    cad_plan_json: Path
    cad_plan_md: Path
    ipt: Path
    build_report: Path
    build_log: Path

    def has_feature_intent(self) -> bool:
        return self.feature_intent.is_file()

    def base_measurement_file(self) -> Optional[Path]:
        """Prefer an existing filled-in input file, else the blank request."""
        if self.measurement_input.is_file():
            return self.measurement_input
        if self.measurement_request.is_file():
            return self.measurement_request
        return None


def resolve_paths(part_dir, out_dir=None) -> Paths:
    """`part_dir` is the folder the user picked (typically `.../input/<part>/`).

    Output goes to `<working_root>/output/<part>/`. When `part_dir`'s parent is
    named `input`, working_root is its grandparent; otherwise working_root is
    `part_dir.parent`. `out_dir` overrides the computed output folder.
    """
    part_dir = Path(part_dir).resolve()
    part_name = part_dir.name
    if part_dir.parent.name.lower() == "input":
        working_root = part_dir.parent.parent
    else:
        working_root = part_dir.parent
    od = Path(out_dir).resolve() if out_dir else (working_root / "output" / part_name)
    return Paths(
        part_dir=part_dir,
        part_name=part_name,
        working_root=working_root,
        out_dir=od,
        measurement_request=part_dir / "measurement-request.json",
        measurement_input=part_dir / "measurement-input.json",
        feature_intent=part_dir / "feature-intent.json",
        validation_report=od / "validation-report.json",
        cad_plan_json=od / "cad-plan.json",
        cad_plan_md=od / "cad-plan.md",
        ipt=od / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', part_name)}.ipt",
        build_report=od / "build-report.md",
        build_log=od / "build-log.txt",
    )


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #

@dataclass
class ValidationResult:
    ok: bool
    schema_errors: list = field(default_factory=list)
    geometry_errors: list = field(default_factory=list)
    failing_ids: list = field(default_factory=list)
    engine: str = ""

    @property
    def all_errors(self) -> list:
        return [f"[schema] {e}" for e in self.schema_errors] + \
               [f"[geometry] {e}" for e in self.geometry_errors]


@dataclass
class PlanResult:
    ok: bool
    error: str = ""
    plan_path: Optional[str] = None
    md_path: Optional[str] = None
    features: list = field(default_factory=list)
    parameters: list = field(default_factory=list)


@dataclass
class BuildResult:
    ok: bool
    exit_code: int
    ipt_path: Optional[str] = None
    size: int = 0
    bodies: Optional[int] = None
    features: Optional[int] = None
    report_path: Optional[str] = None
    log_tail: list = field(default_factory=list)
    summary: str = ""


# --------------------------------------------------------------------------- #
# validation (in-process)
# --------------------------------------------------------------------------- #

def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run_validate(paths: Paths, write_report: bool = True) -> ValidationResult:
    import validate_measurements as vm  # noqa: WPS433 - deliberate in-process import

    src = paths.base_measurement_file()
    if src is None:
        return ValidationResult(ok=False,
                                schema_errors=[f"no measurement file in {paths.part_dir}"])
    try:
        doc = _load_json(src)
    except json.JSONDecodeError as exc:
        return ValidationResult(ok=False, schema_errors=[f"{src.name}: invalid JSON: {exc}"])

    schema = vm.load_schema(str(resources.schema_path("measurement.schema.json")))
    s_errs, engine = vm.schema_validate(doc, schema)
    g_errs = vm.geometry_validate(doc) if not s_errs else []

    failing = sorted({m for e in (s_errs + g_errs) for m in _ID_RE.findall(e)})
    res = ValidationResult(ok=not (s_errs or g_errs),
                           schema_errors=s_errs, geometry_errors=g_errs,
                           failing_ids=failing, engine=engine)

    if write_report:
        paths.out_dir.mkdir(parents=True, exist_ok=True)
        with open(paths.validation_report, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({
                "input": str(src),
                "ok": res.ok,
                "schema_engine": engine,
                "schema_errors": s_errs,
                "geometry_errors": g_errs,
                "failing_ids": failing,
            }, fh, indent=2, sort_keys=True)
            fh.write("\n")
    return res


# --------------------------------------------------------------------------- #
# planning (in-process, CLI-parity)
# --------------------------------------------------------------------------- #

def run_plan(paths: Paths) -> PlanResult:
    import plan_cad  # noqa: WPS433
    import validate_measurements as vm  # noqa: WPS433

    src = paths.base_measurement_file()
    if src is None:
        return PlanResult(ok=False, error=f"no measurement file in {paths.part_dir}")
    if not paths.feature_intent.is_file():
        return PlanResult(ok=False, error=f"feature-intent.json missing in {paths.part_dir} "
                                          f"(run /inventor-photo-to-ipt in Claude Code first)")
    try:
        plan, params = plan_cad.build_plan(str(src), str(paths.feature_intent))
    except plan_cad.PlanError as exc:
        return PlanResult(ok=False, error=f"{type(exc).__name__}: {exc}")

    schema = vm.load_schema(str(resources.schema_path("cad-feature-plan.schema.json")))
    errs, _ = vm.schema_validate(plan, schema)
    if errs:
        return PlanResult(ok=False, error="cad-plan.json failed its schema: " + "; ".join(errs))

    paths.out_dir.mkdir(parents=True, exist_ok=True)
    plan_cad._write_json(plan, str(paths.cad_plan_json))
    plan_cad._write_md(plan, params, str(paths.cad_plan_md))
    return PlanResult(
        ok=True,
        plan_path=str(paths.cad_plan_json),
        md_path=str(paths.cad_plan_md),
        features=[{"id": f["id"], "type": f["type"], "depends_on": f.get("depends_on", [])}
                  for f in plan["features"]],
        parameters=sorted(plan["parameters"].keys()),
    )


# --------------------------------------------------------------------------- #
# Inventor build (out-of-process, Windows PowerShell 5.1 / STA)
# --------------------------------------------------------------------------- #

def _no_window_flags() -> int:
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def run_build(paths: Paths,
              on_line: Optional[Callable[[str], None]] = None,
              on_start: Optional[Callable[["subprocess.Popen"], None]] = None) -> BuildResult:
    if not paths.cad_plan_json.is_file():
        return BuildResult(ok=False, exit_code=2, summary="cad-plan.json not found - run plan first")

    script = resources.scripts_dir() / "inventor_build.ps1"
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [resources.powershell_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", str(script), "-PlanPath", str(paths.cad_plan_json),
           "-OutDir", str(paths.out_dir)]

    lines: list = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=_no_window_flags())
    if on_start:
        on_start(proc)
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip("\r\n")
        lines.append(line)
        if on_line:
            on_line(line)
    code = proc.wait()

    return _parse_build(paths, code, lines)


def kill_inventor() -> None:
    """Best-effort: kill any Inventor.exe (used on build cancel)."""
    if sys.platform != "win32":
        return
    try:
        subprocess.run(["taskkill", "/IM", "Inventor.exe", "/F"],
                       capture_output=True, creationflags=_no_window_flags(), timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass


def _parse_build(paths: Paths, code: int, lines: list) -> BuildResult:
    joined = "\n".join(lines)
    ok = code == 0 and "BUILD_OK" in joined
    size = paths.ipt.stat().st_size if paths.ipt.is_file() else 0
    bodies = features = None
    m = re.search(r"BUILD_OK.*?\((\d+) bytes, (\d+) body/bodies, (\d+) features\)", joined)
    if m:
        size = int(m.group(1))
        bodies = int(m.group(2))
        features = int(m.group(3))
    summary = ""
    for key in ("BUILD_OK", "BUILD_FAILED", "BLOCKED"):
        for ln in lines:
            if ln.startswith(key):
                summary = ln
                break
        if summary:
            break
    return BuildResult(
        ok=ok, exit_code=code,
        ipt_path=str(paths.ipt) if paths.ipt.is_file() else None,
        size=size, bodies=bodies, features=features,
        report_path=str(paths.build_report) if paths.build_report.is_file() else None,
        log_tail=lines[-40:],
        summary=summary or (f"exit {code}"),
    )


# --------------------------------------------------------------------------- #
# measurement form I/O
# --------------------------------------------------------------------------- #

def load_measurement_request(paths: Paths) -> dict:
    """Return the full measurement doc (from the filled input file if present,
    else the blank request). The GUI builds one form row per `measurements[*]`."""
    src = paths.base_measurement_file()
    if src is None:
        raise FileNotFoundError(f"no measurement-request.json / measurement-input.json in {paths.part_dir}")
    return _load_json(src)


def write_measurement_input(paths: Paths, values: dict) -> Path:
    """`values` maps measurement id -> number (or None). Loads the base doc,
    overwrites only `measurements[*].value` by id, preserves every other field
    and key order, writes `measurement-input.json`."""
    src = paths.base_measurement_file()
    if src is None:
        raise FileNotFoundError(f"no base measurement file in {paths.part_dir}")
    doc = _load_json(src)
    for m in doc.get("measurements", []):
        if m["id"] in values:
            v = values[m["id"]]
            m["value"] = None if v is None else float(v)
    paths.part_dir.mkdir(parents=True, exist_ok=True)
    with open(paths.measurement_input, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return paths.measurement_input


# --------------------------------------------------------------------------- #
# environment probe
# --------------------------------------------------------------------------- #

def probe_inventor(timeout: float = 30.0) -> dict:
    """Run detect_inventor.ps1 and parse its trailing JSON line."""
    script = resources.scripts_dir() / "detect_inventor.ps1"
    try:
        cp = subprocess.run(
            [resources.powershell_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(script)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=_no_window_flags(),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"usable": False, "note": f"detect_inventor.ps1 failed: {exc}"}
    for line in reversed(cp.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                d = json.loads(line)
                d.setdefault("note", "")
                return d
            except json.JSONDecodeError:
                pass
    return {"usable": False, "note": f"detect_inventor.ps1 gave no JSON (exit {cp.returncode})"}
