"""Photo-to-IPT Builder - PySide6 GUI over the Phase E-I pipeline.

Front-end only: every action calls app.pipeline. Photo -> structure (Phase A-C)
stays in Claude Code; this window consumes the input/<part>/ folder it produces
(measurement-request.json + feature-intent.json) and drives
validate -> plan -> Inventor build -> verify -> report.

Run from source:  python -m app.ipt_builder
Packaged:         Photo-to-IPT Builder.exe   (see build/)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QAbstractItemView, QTableView, QVBoxLayout, QWidget, QDockWidget,
)
from PySide6.QtCore import QAbstractTableModel, QModelIndex

from . import pipeline, resources

APP_NAME = "Photo-to-IPT Builder"

_OK_GREEN = "#1a7f37"
_ERR_RED = "#b3261e"
_FAIL_BG = QColor("#f9dede")


# --------------------------------------------------------------------------- #
# measurement table model
# --------------------------------------------------------------------------- #

COLS = ("필수", "이름", "값", "단위", "측정 방법")
C_REQ, C_NAME, C_VALUE, C_UNIT, C_INSTR = range(5)


class MeasurementModel(QAbstractTableModel):
    """One row per `measurements[*]` entry. Only the 값 column is editable."""

    def __init__(self, doc: dict, parent=None):
        super().__init__(parent)
        self._rows = list(doc.get("measurements", []))
        self._failing: set = set()

    # --- Qt API ---------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLS[section]
        return None

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == C_VALUE:
            return base | Qt.ItemIsEditable
        return base

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        m = self._rows[index.row()]
        col = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == C_REQ:
                return "●" if m.get("required") else ""
            if col == C_NAME:
                return m.get("name", "")
            if col == C_VALUE:
                v = m.get("value")
                return "" if v is None else _fmt_num(v)
            if col == C_UNIT:
                return m.get("unit", "")
            if col == C_INSTR:
                return m.get("measurement_instruction", "")
        if role == Qt.ToolTipRole and col == C_INSTR:
            return m.get("measurement_instruction", "")
        if role == Qt.ToolTipRole and col == C_NAME:
            return m.get("id", "")
        if role == Qt.TextAlignmentRole and col in (C_REQ, C_VALUE, C_UNIT):
            return int(Qt.AlignCenter)
        if role == Qt.BackgroundRole and m.get("id") in self._failing:
            return QBrush(_FAIL_BG)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or index.column() != C_VALUE:
            return False
        m = self._rows[index.row()]
        text = str(value).strip().replace(",", "")
        if text == "":
            m["value"] = None
        else:
            try:
                m["value"] = float(text)
            except ValueError:
                return False
        self._failing.discard(m.get("id"))
        self.dataChanged.emit(index, index)
        return True

    # --- helpers -----------------------------------------------------------
    def values(self) -> dict:
        return {m["id"]: m.get("value") for m in self._rows}

    def set_failing(self, ids):
        self.beginResetModel()
        self._failing = set(ids or [])
        self.endResetModel()

    def missing_required(self) -> list:
        return [m["id"] for m in self._rows if m.get("required") and m.get("value") is None]


def _fmt_num(v) -> str:
    f = float(v)
    return str(int(f)) if f.is_integer() else f"{f:g}"


# --------------------------------------------------------------------------- #
# workers
# --------------------------------------------------------------------------- #

class ProbeWorker(QObject):
    done = Signal(dict)

    def run(self):
        try:
            self.done.emit(pipeline.probe_inventor())
        except Exception as exc:  # noqa: BLE001 - surfaced to the chip
            self.done.emit({"usable": False, "note": f"{exc}"})


class BuildWorker(QObject):
    line = Signal(str)
    done = Signal(object)  # BuildResult

    def __init__(self, paths):
        super().__init__()
        self._paths = paths
        self._proc = None
        self._cancelled = False

    def run(self):
        try:
            res = pipeline.run_build(
                self._paths,
                on_line=self.line.emit,
                on_start=self._capture,
            )
        except Exception as exc:  # noqa: BLE001
            res = pipeline.BuildResult(ok=False, exit_code=-1, summary=f"예외: {exc}")
        self.done.emit(res)

    def _capture(self, proc):
        self._proc = proc

    def cancel(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass
        pipeline.kill_inventor()


# --------------------------------------------------------------------------- #
# main window
# --------------------------------------------------------------------------- #

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1080, 720)

        self.paths = None
        self.model: MeasurementModel | None = None
        self._env = {"usable": False, "note": "확인 중…"}
        self._validated_ok = False
        self._planned_ok = False
        self._build_thread: QThread | None = None
        self._build_worker: BuildWorker | None = None
        self._probe_thread: QThread | None = None

        self._build_ui()
        self._build_menu()
        self._refresh_enabled()
        self._start_probe()

    # --- UI construction -------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        # top bar
        top = QHBoxLayout()
        self.btn_open = QPushButton("작업 폴더 선택…")
        self.btn_open.clicked.connect(self._pick_folder)
        self.lbl_folder = QLabel("폴더를 선택하세요 (…/input/<part>/)")
        self.lbl_folder.setStyleSheet("color:#555;")
        self.lbl_env = QLabel("Inventor 확인 중…")
        self.lbl_env.setStyleSheet("padding:2px 8px;border-radius:9px;background:#eee;color:#555;")
        top.addWidget(self.btn_open)
        top.addWidget(self.lbl_folder, 1)
        top.addWidget(self.lbl_env)
        outer.addLayout(top)

        # measurement table
        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        outer.addWidget(self.table, 1)

        # actions
        act = QHBoxLayout()
        self.btn_validate = QPushButton("검증")
        self.btn_plan = QPushButton("플랜 생성")
        self.btn_build = QPushButton("Inventor 빌드")
        self.btn_open_ipt = QPushButton(".ipt 열기")
        self.btn_open_report = QPushButton("리포트 열기")
        self.btn_cancel = QPushButton("취소")
        for b in (self.btn_validate, self.btn_plan, self.btn_build,
                  self.btn_open_ipt, self.btn_open_report, self.btn_cancel):
            act.addWidget(b)
        act.addStretch(1)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)  # busy
        self.progress.setFixedWidth(160)
        act.addWidget(self.progress)
        outer.addLayout(act)

        self.btn_validate.clicked.connect(self._do_validate)
        self.btn_plan.clicked.connect(self._do_plan)
        self.btn_build.clicked.connect(self._do_build)
        self.btn_open_ipt.clicked.connect(lambda: self._open(self.paths.ipt if self.paths else None))
        self.btn_open_report.clicked.connect(lambda: self._open(self.paths.build_report if self.paths else None))
        self.btn_cancel.clicked.connect(self._cancel_build)

        # log pane
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9))
        self.log.setMaximumBlockCount(5000)
        self.log.setPlaceholderText("로그…")
        self.log.setFixedHeight(200)
        outer.addWidget(self.log)

        self.setCentralWidget(central)

        # feature-intent dock
        self.intent_view = QPlainTextEdit()
        self.intent_view.setReadOnly(True)
        self.intent_view.setFont(QFont("Consolas", 9))
        dock = QDockWidget("피처 인텐트 (feature-intent.json)", self)
        dock.setObjectName("intentDock")
        dock.setWidget(self.intent_view)
        dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.intent_dock = dock

        self.statusBar().showMessage("준비")

    def _build_menu(self):
        m_file = self.menuBar().addMenu("파일")
        a_open = QAction("작업 폴더 열기…", self)
        a_open.triggered.connect(self._pick_folder)
        a_quit = QAction("종료", self)
        a_quit.triggered.connect(self.close)
        m_file.addAction(a_open)
        m_file.addSeparator()
        m_file.addAction(a_quit)

        m_help = self.menuBar().addMenu("도움말")
        a_guide = QAction("워크플로우 가이드", self)
        a_guide.triggered.connect(lambda: self._open(resources.guide_html()))
        a_claude = QAction("Claude Code에서 사진 분석하기", self)
        a_claude.triggered.connect(self._show_claude_help)
        m_help.addAction(a_guide)
        m_help.addAction(a_claude)

    # --- environment probe --------------------------------------------------
    def _start_probe(self):
        self._probe_thread = QThread(self)
        worker = ProbeWorker()
        worker.moveToThread(self._probe_thread)
        self._probe_thread.started.connect(worker.run)
        worker.done.connect(self._probe_done)
        worker.done.connect(self._probe_thread.quit)
        self._probe_worker = worker
        self._probe_thread.start()

    def _probe_done(self, env: dict):
        self._env = env
        if env.get("usable"):
            ver = env.get("file_version") or env.get("version") or "2027"
            self.lbl_env.setText(f"Inventor {ver} 감지됨")
            self.lbl_env.setStyleSheet(f"padding:2px 8px;border-radius:9px;background:#e6f4ea;color:{_OK_GREEN};")
        else:
            note = env.get("note") or "설치/등록 확인 필요"
            self.lbl_env.setText("Inventor 미감지")
            self.lbl_env.setToolTip(note)
            self.lbl_env.setStyleSheet(f"padding:2px 8px;border-radius:9px;background:#f9dede;color:{_ERR_RED};")
        self._refresh_enabled()

    # --- folder / model ---------------------------------------------------
    def _pick_folder(self):
        start = str(self.paths.part_dir) if self.paths else os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(self, "부품 폴더 선택 (…/input/<part>/)", start)
        if not d:
            return
        self.load_folder(d)

    def load_folder(self, d):
        try:
            paths = pipeline.resolve_paths(d)
            doc = pipeline.load_measurement_request(paths)
        except FileNotFoundError as exc:
            QMessageBox.warning(self, APP_NAME,
                                f"{exc}\n\n이 폴더에는 measurement-request.json / "
                                f"measurement-input.json 이 없습니다.")
            return
        self.paths = paths
        self.model = MeasurementModel(doc, self)
        self.table.setModel(self.model)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(C_INSTR, QHeaderView.Stretch)
        for c in (C_REQ, C_NAME, C_VALUE, C_UNIT):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.lbl_folder.setText(f"{paths.part_name}   →   {paths.out_dir}")
        self._validated_ok = False
        self._planned_ok = False
        self._load_intent()
        self.log.clear()
        self.statusBar().showMessage(f"{paths.part_name} 로드됨")
        self._refresh_enabled()

    def _load_intent(self):
        if not self.paths:
            return
        if self.paths.has_feature_intent():
            import json
            try:
                fi = json.loads(self.paths.feature_intent.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                self.intent_view.setPlainText(f"feature-intent.json 읽기 실패: {exc}")
                return
            lines = [f"part: {fi.get('part_name', self.paths.part_name)}",
                     f"primary_plane: {fi.get('primary_plane', '?')}", "",
                     "sketches:"]
            for s in fi.get("sketches", []):
                lines.append(f"  {s.get('id')}  {s.get('plane')}  {s.get('profile', {}).get('type')}")
            lines.append("")
            lines.append("features (plan order after topo-sort):")
            for f in fi.get("features", []):
                dep = ",".join(f.get("depends_on", [])) or "-"
                lines.append(f"  {f.get('id')}  {f.get('type'):<20} after: {dep}")
            self.intent_view.setPlainText("\n".join(lines))
        else:
            self.intent_view.setPlainText(
                "이 폴더에는 feature-intent.json 이 없습니다.\n\n"
                "Claude Code에서 부품 사진을 첨부하고\n"
                "  /inventor-photo-to-ipt\n"
                "를 먼저 실행하면 input/<part>/ 에\n"
                "measurement-request.json 과 feature-intent.json 이 생성됩니다.\n\n"
                "그 폴더를 여기서 열어 사용하세요."
            )

    # --- actions --------------------------------------------------------
    def _persist_values(self):
        if self.paths and self.model:
            pipeline.write_measurement_input(self.paths, self.model.values())

    def _do_validate(self):
        if not (self.paths and self.model):
            return
        self._persist_values()
        res = pipeline.run_validate(self.paths)
        self.model.set_failing(res.failing_ids)
        self._validated_ok = res.ok
        self._planned_ok = False
        if res.ok:
            self.statusBar().showMessage("검증 통과 (schema + geometry)")
            self._log_block("MEASUREMENT_VALIDATION_OK")
        else:
            self.statusBar().showMessage(f"검증 실패 {len(res.all_errors)}건 — 빨간 행 확인")
            self._log_block("MEASUREMENT_VALIDATION_FAILED\n\n" + "\n".join(f"- {e}" for e in res.all_errors))
        self._refresh_enabled()

    def _do_plan(self):
        if not self.paths:
            return
        self._persist_values()
        pr = pipeline.run_plan(self.paths)
        self._planned_ok = pr.ok
        if pr.ok:
            self.statusBar().showMessage(f"플랜 생성됨 — {len(pr.features)} features")
            body = self.paths.cad_plan_md.read_text(encoding="utf-8") if self.paths.cad_plan_md.is_file() else ""
            self._log_block(f"PLAN_OK\n{body}")
        else:
            self.statusBar().showMessage("플랜 실패")
            self._log_block(f"PLAN_FAILED\n\n- {pr.error}")
        self._refresh_enabled()

    def _do_build(self):
        if not (self.paths and self._planned_ok):
            return
        self._set_running(True)
        self.log.appendPlainText("\n=== Inventor 빌드 시작 ===")
        self._build_thread = QThread(self)
        self._build_worker = BuildWorker(self.paths)
        self._build_worker.moveToThread(self._build_thread)
        self._build_thread.started.connect(self._build_worker.run)
        self._build_worker.line.connect(self.log.appendPlainText)
        self._build_worker.done.connect(self._build_done)
        self._build_worker.done.connect(self._build_thread.quit)
        self._build_thread.start()

    def _cancel_build(self):
        if self._build_worker:
            self.log.appendPlainText("[취소 요청]")
            self._build_worker.cancel()

    def _build_done(self, res):
        self._set_running(False)
        self._build_worker = None
        if res.ok:
            self.statusBar().showMessage(
                f"BUILD PASS — {res.size} bytes, {res.bodies} body, {res.features} features")
        else:
            self.statusBar().showMessage(f"BUILD FAIL — {res.summary}")
        self.log.appendPlainText(f"=== {res.summary} ===")
        self._refresh_enabled()

    # --- helpers -------------------------------------------------------
    def _set_running(self, running: bool):
        self.progress.setVisible(running)
        for b in (self.btn_open, self.btn_validate, self.btn_plan, self.btn_build):
            b.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        self.table.setEnabled(not running)

    def _refresh_enabled(self):
        loaded = self.paths is not None
        has_intent = loaded and self.paths.has_feature_intent()
        env_ok = bool(self._env.get("usable"))
        self.btn_validate.setEnabled(loaded)
        self.btn_plan.setEnabled(loaded and self._validated_ok and has_intent)
        self.btn_build.setEnabled(loaded and self._planned_ok and env_ok)
        self.btn_open_ipt.setEnabled(loaded and self.paths.ipt.is_file())
        self.btn_open_report.setEnabled(loaded and self.paths.build_report.is_file())
        if not hasattr(self, "_cancel_init"):
            self.btn_cancel.setEnabled(False)
            self._cancel_init = True

    def _log_block(self, text: str):
        self.log.appendPlainText(text)
        self.log.appendPlainText("")

    def _open(self, path):
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            QMessageBox.information(self, APP_NAME, f"파일이 없습니다:\n{p}")
            return
        if sys.platform == "win32":
            os.startfile(str(p))  # noqa: S606
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(p)])

    def _show_claude_help(self):
        QMessageBox.information(
            self, APP_NAME,
            "1. Claude Code 를 이 프로젝트에서 실행\n"
            "2. /inventor-photo-to-ipt 스킬 호출\n"
            "3. 부품 사진(전/후/좌/우/상) 첨부 후\n"
            "   \"이 부품을 Inventor 2027 .ipt로 만들어줘\"\n"
            "4. Claude 가 input/<part>/ 에\n"
            "   measurement-request.json + feature-intent.json 생성\n"
            "5. 그 폴더를 이 앱에서 열어 치수 입력 → 검증 → 플랜 → 빌드\n\n"
            "이 앱은 사진 분석을 하지 않습니다 (Phase E~I 전용)."
        )

    def closeEvent(self, event):
        if self._build_worker:
            self._build_worker.cancel()
        for t in (self._build_thread, self._probe_thread):
            if t and t.isRunning():
                t.quit()
                t.wait(2000)
        super().closeEvent(event)


def _selftest(with_build: bool) -> int:
    """Headless proof that this (possibly frozen) bundle actually works:
    import chain OK, bundled scripts/schemas resolve, in-process validate + plan
    run on a synthetic part. With --selftest-build, also drives the Inventor
    build (needs Inventor). Prints SELFTEST: PASS/FAIL, returns an exit code.
    Distribute-and-verify: `"Photo-to-IPT Builder.exe" --selftest`.
    """
    import json
    import shutil
    import tempfile

    resources.add_scripts_to_syspath()
    fails = []

    def ck(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    ck("bundled scripts dir exists", resources.scripts_dir().is_dir())
    ck("measurement schema resolves", resources.schema_path("measurement.schema.json").is_file())
    ck("cad-plan schema resolves", resources.schema_path("cad-feature-plan.schema.json").is_file())
    ck("inventor_build.ps1 bundled", (resources.scripts_dir() / "inventor_build.ps1").is_file())
    ck("inventor_env.ps1 bundled", (resources.scripts_dir() / "lib" / "inventor_env.ps1").is_file())

    d = tempfile.mkdtemp(prefix="iptb_selftest_")
    part = os.path.join(d, "input", "selftest_plate")
    os.makedirs(part)
    meas = {
        "schema_version": "1.0",
        "part": {"name": "selftest_plate", "units": "mm"},
        "source_images": [{"id": "IMG-000", "view": "front"}],
        "reference": {"origin_definition": "corner", "primary_plane": "XY", "symmetry": []},
        "measurements": [
            {"id": "M001", "name": "overall_width", "value": 40.0, "unit": "mm", "type": "length",
             "required": True, "measurement_instruction": "width"},
            {"id": "M002", "name": "overall_height", "value": 25.0, "unit": "mm", "type": "length",
             "required": True, "measurement_instruction": "height"},
            {"id": "M003", "name": "thickness", "value": 4.0, "unit": "mm", "type": "length",
             "required": True, "measurement_instruction": "thickness"},
        ],
    }
    intent = {
        "intent_version": "1.0", "part_name": "selftest_plate", "primary_plane": "XY",
        "parameters": {"overall_width": {"measurement_id": "M001"},
                       "overall_height": {"measurement_id": "M002"},
                       "thickness": {"measurement_id": "M003"}},
        "sketches": [{"id": "S1", "plane": "XY",
                      "profile": {"type": "rectangle", "width_param": "overall_width",
                                  "height_param": "overall_height", "corner": "origin"}}],
        "features": [{"id": "F001", "type": "base_extrude", "sketch": "S1",
                      "distance_param": "thickness", "direction": "positive", "depends_on": []}],
    }
    with open(os.path.join(part, "measurement-input.json"), "w", encoding="utf-8") as fh:
        json.dump(meas, fh)
    with open(os.path.join(part, "feature-intent.json"), "w", encoding="utf-8") as fh:
        json.dump(intent, fh)

    paths = pipeline.resolve_paths(part, out_dir=os.path.join(d, "out"))
    vr = pipeline.run_validate(paths)
    ck("in-process validate ok", vr.ok)
    pr = pipeline.run_plan(paths)
    ck("in-process plan ok", pr.ok)
    ck("cad-plan.json written", paths.cad_plan_json.is_file())
    ck("plan has feature F001", any(f["id"] == "F001" for f in pr.features))

    env = pipeline.probe_inventor()
    print(f"info  inventor probe: usable={env.get('usable')} note={env.get('note') or env.get('file_version')}")

    if with_build:
        if not env.get("usable"):
            ck("inventor build (skipped - Inventor not usable)", True)
        else:
            br = pipeline.run_build(paths, on_line=lambda l: print("   " + l))
            ck("inventor build ok", br.ok)
            ck("verified .ipt on disk", bool(br.ipt_path) and os.path.isfile(br.ipt_path))

    shutil.rmtree(d, ignore_errors=True)
    ok = not fails
    print("SELFTEST: PASS" if ok else f"SELFTEST: FAIL {fails}")
    sys.stdout.flush()
    return 0 if ok else 1


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    if "--selftest" in args or "--selftest-build" in args:
        return _selftest(with_build="--selftest-build" in args)

    resources.add_scripts_to_syspath()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("inventor_auto")
    _icon = resources.app_icon_path()
    if _icon:
        app.setWindowIcon(QIcon(str(_icon)))
    w = MainWindow()
    folder = next((a for a in args if os.path.isdir(a)), None)
    if folder:
        w.load_folder(folder)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
