"""Offscreen smoke for app/ipt_builder.py (needs PySide6; NOT run by run_tests.py).

    python tests/gui_smoke.py          # exit 0 = all GUI-logic checks pass

Uses a tempdir COPY of tests/fixtures/simple_plate (the GUI persists edits to the
loaded folder). No Inventor required - stops before the build.
"""
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["gui_smoke"]

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
except ImportError:
    print("SKIP: PySide6 not installed (pip install -r requirements-dev.txt)")
    raise SystemExit(0)

app = QApplication(sys.argv)
from app.ipt_builder import MainWindow  # noqa: E402

fails = []


def check(name, cond):
    print(f"{'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        fails.append(name)


d = tempfile.mkdtemp()
part = os.path.join(d, "input", "simple_plate")
os.makedirs(part)
for n in ("measurement-input.json", "feature-intent.json"):
    shutil.copy(os.path.join(HERE, "fixtures", "simple_plate", n), os.path.join(part, n))

w = MainWindow()
w.load_folder(part)
check("model has 7 rows", w.model.rowCount() == 7)
check("feature-intent detected", w.paths.has_feature_intent())
check("intent panel populated", "features" in w.intent_view.toPlainText())

w._do_validate()
check("fixture validates ok", w._validated_ok is True)
check("plan button enabled after valid+intent", w.btn_plan.isEnabled())

w._do_plan()
check("plan ok", w._planned_ok is True)
check("cad-plan.json written", w.paths.cad_plan_json.is_file())
check("cad-plan.md written", w.paths.cad_plan_md.is_file())

w.model.setData(w.model.index(3, 2), "80", Qt.EditRole)  # M004 -> 80
check("model took M004=80", w.model.values()["M004"] == 80.0)
w._do_validate()
check("invalid measurement fails validation", w._validated_ok is False)
check("M004 row flagged", "M004" in w.model._failing)
check("plan button disabled after invalid", not w.btn_plan.isEnabled())

part2 = os.path.join(d, "input", "no_intent")
os.makedirs(part2)
shutil.copy(os.path.join(part, "measurement-input.json"),
            os.path.join(part2, "measurement-input.json"))
w.load_folder(part2)
check("no feature-intent detected", not w.paths.has_feature_intent())
check("empty-state text shown", "inventor-photo-to-ipt" in w.intent_view.toPlainText())
w._do_validate()
check("plan button stays disabled without intent", not w.btn_plan.isEnabled())

print("RESULT:", "PASS" if not fails else f"FAIL {fails}")
sys.stdout.flush()
sys.stderr.flush()
os._exit(0 if not fails else 1)
