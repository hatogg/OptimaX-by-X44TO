"""Головне вікно на справжньому Qt (offscreen) у режимі перегляду на демо-залізі:
усі розділи, застосування плану, банер збою й аварійний відкат, розумна оптимізація, картка результату.
Аргумент: мова. Знімки — у теку з OPTIMAX_TEST_SHOTS (якщо задано)."""
import _boot
import os
import re
import sys
import time
import traceback

LANG = sys.argv[1] if len(sys.argv) > 1 else "uk"
sys.argv = _boot.argv(f"--lang={LANG}")
import optimizer as O  # noqa: E402
import engine as E  # noqa: E402
import features as F  # noqa: E402
import gpubench as GB  # noqa: E402
import sharecard as SC  # noqa: E402
import smart_ui as SM  # noqa: E402
import ui_kit as UK  # noqa: E402
from PyQt6.QtWidgets import QDialog, QFileDialog  # noqa: E402

DEMO = os.environ.get("OPTIMAX_DEMO", "gaming")
SHOTS = os.environ.get("OPTIMAX_TEST_SHOTS")
GB.DemoRun.SPEED = 3000.0  # демо-заміри FPS за частки секунди
errors, dialogs, steps = [], [], {}
sys.excepthook = lambda tp, v, tb: errors.append("".join(traceback.format_exception(tp, v, tb))[-2000:])

app = O.QApplication(sys.argv)
O.apply_theme(app)


def pump(cond=lambda: False, timeout: float = 5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def shot(widget, name: str) -> None:
    if SHOTS and not _boot.STUB:
        os.makedirs(SHOTS, exist_ok=True)
        widget.grab().save(os.path.join(SHOTS, f"{DEMO}-{LANG}-{name}.png"))


def drive_stub(dlg) -> None:
    """Лише для заглушки Qt: там таймери не спрацьовують, тож кроки сесії викликаємо самі."""
    dlg.started = True
    dlg.step()
    for _ in range(20000):
        if dlg.finished_ok:
            return
        if dlg.run:
            dlg._poll()
            time.sleep(0.002)
        elif dlg.worker is None:
            dlg.step()


_orig_exec = QDialog.exec


def auto_exec(dlg, *a):
    name = type(dlg).__name__
    dialogs.append(name)
    if _boot.STUB:
        if isinstance(dlg, SM.SmartDialog):
            drive_stub(dlg)
        return _orig_exec(dlg)
    dlg.show()
    if isinstance(dlg, (UK.RunDialog, SM.SmartDialog)):
        if not pump(lambda: dlg.finished_ok, 900):
            errors.append(f"{name} did not finish")
        pump(timeout=0.2)
    else:
        pump(timeout=0.2)
    shot(dlg, f"dialog{len(dialogs):02d}-{name}")
    dlg.hide()
    return 1  # як справжній exec(): int, «Прийняти»


QDialog.exec = auto_exec
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))

w = O.Main()
toasts = []
w._toast.show_msg = lambda text, kind="ok", area=None: toasts.append([kind, text])
w.show()
steps["hw"] = pump(lambda: w.hw is not None, 120)
shot(w, "home")

# усі розділи
for key in list(w.nav_keys):
    w.go(key)
    pump(timeout=0.15)
    shot(w, f"page-{key}")
steps["pages"] = len(w.nav_keys)

# режими оптимізації: план під демо-залізо → перегляд змін (для «Ігрового» — із замірами)
w.open_modes()
pump(timeout=0.2)
opt = w.pages["optimize"]
shot(w, "modes")
opt.modes.show_why("gaming")
pump(timeout=0.1)
shot(w, "modes-why")
opt.modes.choose("gaming")
pump(timeout=0.2)
steps["modes"] = {"rows": len(opt.review.rows), "smart": bool(opt.review.sw_smart.isChecked()),
                  "safe": len((opt.modes.plans.get("safe") or {}).get("ids") or []),
                  "limit": bool(opt.modes.limit.text())}
shot(w, "modes-review")
opt.back_from_review()

# застосувати рекомендований план (режим перегляду), потім «збій» і аварійний відкат
plan = (w.analysis or {}).get("recommended") or []
w.start_apply(plan, False, False)
pump(lambda: E.JOURNAL.count() > 0, 60)
steps["applied"] = E.JOURNAL.count()
safety = F.CFG["safety"] or {}
steps["batch"] = len(safety.get("ids") or [])
F.CFG["demo_crash"] = True
_ask = w.ask_crash


def ask_and_note():
    home = w.pages["home"]
    steps["banner"] = [home.banner.isVisible(), home.banner_t.text(), home.banner_b1.text()]
    shot(w, "crash-banner")
    _ask()


w.ask_crash = ask_and_note  # банер видно між перевіркою і запитанням
n_run = dialogs.count("RunDialog")
w.safety_check(prompt=True)
if _boot.STUB:  # у заглушці QTimer.singleShot не спрацьовує
    pump(lambda: w.crash is not None, 5)
    w.ask_crash()
pump(lambda: dialogs.count("RunDialog") > n_run and w.crash is None, 120)
steps["after_rescue"] = sum(E.JOURNAL.has(i) for i in safety.get("ids") or [])
F.CFG["demo_crash"] = False
E.undo_ids(E.JOURNAL.newest_first(), lambda *_: None)

# розумна оптимізація: заміряти → застосувати → заміряти → знайти шкідливе
w.open_smart_plan()
rv = w.pages["optimize"].review
steps["smart_switch"] = bool(rv.sw_smart.isChecked())
rv.apply()
pump(lambda: F.CFG["smart_last"] is not None, 900)
sm = F.CFG["smart_last"] or {}
steps["smart"] = {"result": sm.get("result"), "delta": sm.get("delta"), "removed": sm.get("removed"),
                  "measures": sm.get("measures")}
w.go("bench")
pump(timeout=0.2)
shot(w, "bench-after-smart")

# картка результату
card = SC.render(SC.collect(w), 1.0)
steps["card"] = [card.width(), card.height()]
if SHOTS and not _boot.STUB:
    card.save(os.path.join(SHOTS, f"{DEMO}-{LANG}-share-card.png"))
w.share_result()

w.quit_app()
pump(timeout=0.5)
bad = [t for k, t in toasts if k == "bad"]
raw = [t for _, t in toasts if re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)+", t or "")]
_boot.result(steps=steps, dialogs=dialogs, errors=errors[:5], bad=bad, raw=raw, toasts=len(toasts),
             stub=_boot.STUB)
