"""Головне вікно на справжньому Qt (offscreen) у режимі перегляду на демо-залізі:
усі розділи, бібліотека ігор, простий вигляд, «Чому впав комп?», монітор на телефоні, застосування плану, банер збою
й аварійний відкат, перенесення налаштувань, розумна оптимізація, «Що нового», звіт про помилку, картка результату.
Аргумент: мова. Знімки — у теку з OPTIMAX_TEST_SHOTS (якщо задано)."""
import _boot
import json
import os
import re
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request

LANG = sys.argv[1] if len(sys.argv) > 1 else "uk"
sys.argv = _boot.argv(f"--lang={LANG}")
import optimizer as O  # noqa: E402
import engine as E  # noqa: E402
import features as F  # noqa: E402
import gpubench as GB  # noqa: E402
import library as LB  # noqa: E402
import mining as MG  # noqa: E402
import pages_life as PL  # noqa: E402
import phonemon as PH  # noqa: E402
import sharecard as SC  # noqa: E402
import smart_ui as SM  # noqa: E402
import ui_kit as UK  # noqa: E402
from PyQt6.QtWidgets import QDialog, QFileDialog, QMenu  # noqa: E402

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
menus = []
QMenu.exec = lambda self, *a, **k: menus.append([x.text() for x in self.actions()])  # меню лише будуємо
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))

w = O.Main()
# вікно ставить свої перехоплювачі (звіт про помилку одним натисканням) — тестові потрібні власні
sys.excepthook = lambda tp, v, tb: errors.append("".join(traceback.format_exception(tp, v, tb))[-2000:])
threading.excepthook = lambda a: errors.append(f"thread {getattr(a.thread, 'name', '?')}: {a.exc_type.__name__}: "
                                               f"{a.exc_value}")
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

# бібліотека ігор: плитки, обрана гра з історією FPS, запуск (режим перегляду) з режимом гри, який вимикається сам
lib = w.pages["library"]
w.go("library")
pump(lambda: len(lib.tiles) >= 4, 30)
st_lib = {"tiles": len(lib.tiles)}


def cs_tile():
    return next((t for t in lib.tiles if t.g.get("appid") == "730"), None)


cs = cs_tile()
if cs:
    g_cs = cs.g
    LB.add_fps("cs2.exe", {"avg": 212.4, "low1": 141.0, "stutters_pm": 0.4})
    cs.clicked.emit(g_cs)
    pump(timeout=0.1)
    st_lib["detail"] = [lib.det.isVisible(), lib.det_name.text(), lib.btn_play.isEnabled(), lib.det_fps.text()]
    n_t = len(toasts)
    started = UK.tr("lib.started", game=g_cs["name"])
    lib.play()
    pump(lambda: any(t == started for _, t in toasts[n_t:]) and F.BOOSTER.active, 30)
    st_lib["started"] = any(t == started for _, t in toasts[n_t:])
    st_lib["boost_on"] = F.BOOSTER.active
    shot(w, "library")
    w._library_tick({"cs2.exe"})  # гра запустилася…
    w._library_tick(set())  # …і закрилася
    pump(lambda: not F.BOOSTER.active, 30)
    pump(timeout=0.2)
    st_lib["boost_off"] = not F.BOOSTER.active and w.lib_boost is None
    st_lib["sessions"] = [s.get("exe") for s in LB.sessions()]
    lib.on_show()
    st_lib["sub"] = cs_tile().sub.text() if cs_tile() else ""
steps["library"] = st_lib

# простий вигляд: перемикач у налаштуваннях, одна кнопка «Оптимізувати» → перегляд змін, повернення
home = w.pages["home"]
setp = w.pages["settings"]
w.go("home")
setp.sw_simple.click()
pump(timeout=0.1)
st_s = {"nav": [k for i, k in enumerate(w.nav_keys) if w.nav.button(i).isVisible()],
        "card": home.simple.isVisible(), "full_hidden": not home.an_card.isVisible(), "cfg": F.CFG["simple_ui"],
        "state": home.s_state.text(), "problems": home.s_box.count()}
shot(w, "home-simple")
home.s_btn.click()
pump(timeout=0.3)
opt = w.pages["optimize"]
st_s["review"] = [opt.stack.currentWidget() is opt.review, len(opt.review.rows)]
opt.back_from_review()
w.go("home")
setp.sw_simple.click()
pump(timeout=0.1)
st_s["restored"] = (all(w.nav.button(i).isVisible() for i in range(len(w.nav_keys))) and home.an_card.isVisible()
                    and not home.simple.isVisible() and not F.CFG["simple_ui"])
steps["simple"] = st_s

# «Чому впав комп?»: демо-журнал Windows — раптове вимкнення, синій екран, скидання драйвера, апаратна помилка
w.go("diagnose")
dg = w.pages["diagnose"]
F.CFG["crash_last"] = None
dg.crash.check()
pump(lambda: isinstance(F.CFG["crash_last"], dict) and dg.crash.btn.isEnabled() and dg.crash.box.count() > 0, 60)
cl = F.CFG["crash_last"] or {}
steps["crash"] = {"kinds": [i["kind"] for i in cl.get("incidents") or []], "rows": dg.crash.box.count(),
                  "head": dg.crash.head.text(), "gpu": (cl.get("gpu") or {}).get("n"),
                  "whea": (cl.get("whea") or {}).get("n")}
dg.crash.memtest()  # запитання → у режимі перегляду лише запис у журнал
shot(w, "crash-card")

# монітор на телефоні: сервер у домашній мережі, QR-код, сторінка й дані, чужий шлях — 404, новий код, вимкнення
pc = dg.phone
st_ph = {}
pc.sw.click()
pump(lambda: PH.MONITOR.running and bool(pc.url.text()), 30)
st_ph.update(running=PH.MONITOR.running, url=pc.url.text(), qr=not pc.qr.pixmap().isNull(), shown=pc.body_w.isVisible())
if PH.MONITOR.running:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f"http://127.0.0.1:{PH.MONITOR.port}/{PH.MONITOR.token}/"
    try:
        page = opener.open(base, timeout=10).read().decode("utf-8")
        api = json.loads(opener.open(base + "api", timeout=10).read().decode("utf-8"))
        st_ph.update(page="OptimaX" in page and "fetch('api'" in page, api="ts" in api)
        try:
            opener.open(f"http://127.0.0.1:{PH.MONITOR.port}/wrong-code/", timeout=10)
            st_ph["foreign"] = 200
        except urllib.error.HTTPError as e:
            st_ph["foreign"] = e.code
    except (OSError, ValueError) as e:
        st_ph["http_error"] = f"{type(e).__name__}: {e}"
    old_token = PH.MONITOR.token
    pc.new_code()
    st_ph["new_code"] = PH.MONITOR.token != old_token and PH.MONITOR.token in pc.url.text()
    shot(w, "phone")
    pc.sw.click()
    pump(lambda: not PH.MONITOR.running, 30)
    pump(timeout=0.1)
    st_ph["stopped"] = not PH.MONITOR.running and not pc.body_w.isVisible() and not (F.CFG["phone"] or {}).get("enabled")
steps["phone"] = st_ph

# майнінгова карта без відеовиходів: розділ на сторінці «Ігри» — пошук і призначення ігор, Mesa для OpenGL, відкат
mc = w.pages["games"].mining
steps["mining_card"] = mc is not None
if mc is not None:
    w.go("games")
    pump(lambda: len(mc.rows) > 0, 30)
    mc.scan()
    pump(lambda: mc.btn_scan.isEnabled() and any(t.startswith("gpu:") for t in MG.our_ids()), 60)
    pump(timeout=0.3)
    shot(w, "mining-scanned")
    for kind in ("mesa", "dxvk"):
        mc.get_layer(kind)
        pump(lambda: MG.layer_info(kind) is not None and mc.layer_btn[kind].text() == UK.tr("mg.got", what=MG.LAYER_NAMES[kind]), 30)
    gl_row = next((r for r in mc.rows if MG.gl_folders(r.g)), None)
    dx_row = next((r for r in mc.rows if MG.layer_targets(r.g, "dxvk")), None)
    ac_row = next((r for r in mc.rows if r.g.get("anticheat")), None)
    for row in (gl_row, dx_row):  # режим «Авто»: OpenGL — Mesa, DirectX 9 — DXVK
        if row:
            mc.mode_menu(row)
            mc.choose_mode(row, "auto")
            pump(lambda: row.btn_mode.isEnabled() and MG.current_mode(row.g) == "auto"
                 and (MG.game_status(row.g)["mesa"] or MG.game_status(row.g)["dxvk"]), 30)
    if ac_row:  # античит: DXVK у режимі DXVK не застосовується, причина — у плані
        steps["anticheat_plan"] = MG.plan(ac_row.g, "dxvk")["blocked"]
    if dx_row:  # перевірка рендерингу (демо) і меню «⋯»
        mc.check_game(dx_row)
        pump(lambda: bool(MG.profile(dx_row.g).get("checks")) and dx_row.btn_check.isEnabled(), 30)
        mc.more_menu(dx_row)
    mc.measure()
    pump(lambda: mc.link_box.count() > 0 and mc.btn_measure.isEnabled(), 30)
    pump(lambda: "МБ" in mc.sc_lbl.text() or "MB" in mc.sc_lbl.text(), 10)
    pump(timeout=0.3)
    shot(w, "mining-layers")
    steps["mining"] = {"rows": len(mc.rows), "gpu": sum(t.startswith("gpu:") for t in MG.our_ids()),
                       "mesa": bool(gl_row and MG.game_status(gl_row.g)["mesa"]),
                       "dxvk": bool(dx_row and MG.game_status(dx_row.g)["dxvk"]),
                       "texts": [r.status.text() for r in mc.rows],
                       "checks": [r.check.text() for r in mc.rows],
                       "checked": bool(dx_row and MG.profile(dx_row.g).get("checks")),
                       "menus": len(menus), "link": mc.link_box.count(), "probe": mc.probe_lbl.text(),
                       "shader": mc.sc_lbl.text(),
                       "bench_note": w.pages["bench"].mesa_note.text()}
    mc.revert()
    pump(lambda: not MG.our_ids() and mc.btn_revert.isEnabled(), 60)
    steps["mining"]["left"] = len(MG.our_ids())
    # «Чому лагає?» на майнінговому ПК: на якій карті малює гра, кадри, PCIe, історія замірів
    w.go("diagnose")
    dp = w.pages["diagnose"]
    dp.dur_i = 0
    n_hist = len(F.CFG["diag_hist"] or [])
    for _ in range(2):
        dp.start_diag()
        pump(lambda: len(F.CFG["diag_hist"] or []) > n_hist, 60)
        n_hist = len(F.CFG["diag_hist"] or [])
        pump(timeout=0.2)
    shot(w, "mining-diag")
    last = F.CFG["diag_last"] or {}
    steps["mining_diag"] = {"keys": [f["key"] for f in last.get("findings") or []],
                            "render": (last.get("render") or {}).get("verdict"), "fps": (last.get("frames") or {}).get("avg"),
                            "hist": len(F.CFG["diag_hist"] or []), "hist_rows": dp.hist_grid.count()}

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
# перенесення налаштувань: експорт набору змін (тут — «старий ПК»); імпорт — після повного відкату нижче
exp_path = os.path.join(tempfile.mkdtemp(prefix="oxtr_"), "optimax-settings.json")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (exp_path, ""))
setp.transfer.export()
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
try:
    with open(exp_path, encoding="utf-8") as f:
        exported = json.load(f)
except (OSError, ValueError):
    exported = {}
steps["transfer"] = {"format": exported.get("format"), "tweaks": len(exported.get("tweaks") or [])}
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

# імпорт на «новому ПК»: зміни, яких тут ще немає, — у перегляді змін (застосування — там, як завжди)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (exp_path, ""))
setp.transfer.import_()
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
pump(timeout=0.3)
opt = w.pages["optimize"]
steps["transfer"]["review"] = [opt.stack.currentWidget() is opt.review, opt.review.source, len(opt.review.rows)]
opt.back_from_review()

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

# «Що нового» і звіт про помилку (попередній перегляд: поза Windows браузер не відкривається)
n_d = len(dialogs)
PL.show_whats_new(w, E.VERSION)
steps["whats_new"] = [len(dialogs) > n_d, F.CFG["seen_version"] == E.VERSION]
n_t = len(toasts)
PL.ask_report(w, 'Traceback (most recent call last):\n  File "C:\\Users\\Ivan\\x.py", line 1\nValueError: boom')
PL.manual_report(w)
preview = re.escape(UK.tr("bug.preview", n=987654)).replace("987654", r"\d+")
steps["report"] = [k for k, t in toasts[n_t:] if re.fullmatch(preview, t or "")]

w.quit_app()
pump(timeout=0.5)
bad = [t for k, t in toasts if k == "bad"]
raw = [t for _, t in toasts if re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)+", t or "")]
_boot.result(steps=steps, dialogs=dialogs, errors=errors[:5], bad=bad, raw=raw, toasts=len(toasts),
             stub=_boot.STUB)
