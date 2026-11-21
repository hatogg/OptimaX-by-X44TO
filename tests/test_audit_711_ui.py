"""Аудит 7.1.1, інтерфейс: головна не крутить анімацій у треї, сторінки не будуються для прихованого вікна, winget
шукається фоном, банер збою не затирає інших банерів, системні exe — за повним шляхом."""
import os
import re
import subprocess
import sys

from _util import ROOT, env_for, has_qt, skip, tail

SCRIPT = r'''
import json, sys
sys.path.insert(0, ROOT)
sys.argv = ["x", "--lang=en", "--dry-run"]
import apps as A
import lifecycle as L
import optimizer as O
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QSystemTrayIcon

L.start_server = lambda *a, **k: None
QSystemTrayIcon.show = lambda self: None
quick = []
O.Main.run_quick = lambda self, title, job, *a, **k: quick.append(title)
sync_wg = []
A.winget_path = lambda: sync_wg.append(1) or "winget"
O.Main.BUILD_DELAY_MS = 30

app = O.QApplication(sys.argv)
O.apply_theme(app)


def spin(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


r = {}
w = O.Main(start_hidden=True)
home = w.pages["home"]
spin(400)
r["hidden_built"] = sorted(dict.keys(w.pages))
r["hidden_home_timer"] = home.timer.isActive()
w.pages["apps"]  # на вимогу (трей, фонова дія) сторінка будується й без показу вікна
r["wg_sync"] = len(sync_wg)
r["wg_bg"] = "winget" in quick
r["no_wg_hidden"] = w.pages["apps"].no_wg.isHidden()
w.show()
spin(50)
r["shown_home_timer"] = home.timer.isActive()
for _ in range(100):
    if not w.pages.next_missing():
        break
    spin(100)
r["all_built"] = w.pages.next_missing() is None
w.hide()
spin(50)
r["tray_home_timer"] = home.timer.isActive()
ab = w.pages["adblock"]
ab.timer.start(4000)
ab.refresh()  # фільтр вимкнений -> таймер зупиняється, а не тікає вічно
r["ab_timer_off"] = ab.timer.isActive()
print("RESULT " + json.dumps(r))
'''


def test_idle_ui_and_lazy_pages():
    if not has_qt():
        skip("PyQt6 is not installed")
    env = env_for("gaming")
    p = subprocess.run([sys.executable, "-c", "ROOT = %r\n" % ROOT + SCRIPT], cwd=ROOT, env=env,
                       capture_output=True, timeout=300)
    out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
    line = next((x for x in reversed(out.splitlines()) if x.startswith("RESULT ")), None)
    assert p.returncode == 0 and line, tail(out)
    import json
    r = json.loads(line[7:])
    assert r["hidden_built"] == ["home"], f"pages must not be built for a window in the tray: {r}"
    assert not r["hidden_home_timer"], "the home tick must not run while the window is hidden"
    assert r["wg_sync"] == 0 and r["wg_bg"] and r["no_wg_hidden"], f"winget must be looked up in the background: {r}"
    assert r["shown_home_timer"] and r["all_built"], r
    assert not r["tray_home_timer"], "hiding the window must stop the home tick"
    assert not r["ab_timer_off"], "the ad-block refresh timer must stop when the filter is off"


MY_FILES = ("optimizer.py", "pages_optimize.py", "pages_extra.py", "pages_lab.py", "pages_cpuz.py", "pages_tools.py",
            "pages_life.py", "pages_hwc2.py", "pages_health.py", "pages_memory.py", "pages_diskinfo.py", "ui_kit.py",
            "ui_motion.py", "monitor.py", "apps.py")


def _src(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_no_bare_exe_launch():
    bad = []
    for name in MY_FILES:
        for m in re.finditer(r"Popen\(\s*\[\s*[\"'][\w.-]+(\.exe)?[\"']", _src(name)):
            bad.append(f"{name}: {m.group(0)}")
    assert not bad, "system programs must be started by full path (SF.explorer_exe / SF.sysexe): " + "; ".join(bad)


def test_crash_banner_uses_is_hidden_and_reports_are_new_files():
    src = _src("optimizer.py")
    i = src.index("def crash_scan")
    body = src[i:src.index("\n    def ", i + 10)]
    assert "banner.isVisible()" not in body and "banner.isHidden()" in body
    hw = _src("pages_hwc2.py")
    for fn in ("def view_report", "def compare_reports"):
        j = hw.index(fn)
        part = hw[j:hw.index("\ndef ", j + 5)]
        assert "SF.remove_then_create(" in part and 'open(path, "w"' not in part, fn
