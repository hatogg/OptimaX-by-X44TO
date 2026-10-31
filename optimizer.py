# -*- coding: utf-8 -*-
"""
OptimaX by X44TO — оптимізація Windows 10 / 11 для ігрових ПК, ноутбуків і старих комп'ютерів.

Запуск:   python optimizer.py             — програма сама попросить права адміністратора
          python optimizer.py --dry-run   — перегляд: нічого не змінює в системі
          python optimizer.py --tray      — запуск згорнутим у трей (так стартує автозапуск)
          python optimizer.py --lang=uk   — мова інтерфейсу: uk, ru або en
          python optimizer.py --selftest=report.json [--selftest-ui] — самоперевірка, нічого не змінює
"""
from __future__ import annotations

import ctypes
import ntpath
import os
import subprocess
import sys
import time

if __name__ == "__main__":
    # службові процеси без головного вікна: DNS-фільтр (від імені SYSTEM) і вікно тесту відеокарти
    if "--dns-service" in sys.argv:
        import adblock
        sys.exit(adblock.service_main(sys.argv))
    if "--gpu-bench" in sys.argv:
        import gpubench
        sys.exit(gpubench.run_child(sys.argv))
    if "--gpu-probe" in sys.argv:  # що бачать DirectX і Vulkan — окремим процесом, щоб збій драйвера не закрив програму
        import gpuinfo
        sys.exit(gpuinfo.probe_child(sys.argv))
    if any(a == "--selftest" or a.startswith("--selftest=") for a in sys.argv):
        import selftest  # самоперевірка збірки (CI): тимчасові налаштування й режим перегляду — до імпорту engine
        selftest.prepare(sys.argv)

from PyQt6.QtCore import Qt, QTimer, QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import (QApplication, QWidget, QFrame, QLabel, QPushButton, QStackedWidget, QButtonGroup,
                             QSystemTrayIcon, QMenu, QFileDialog, QScrollArea)

import engine as E
import features as F
import guard as G
import hardware as H
import hotkeys as HK
import lifecycle as L
import mining as MG
import monitor as M
import power as PW
import adblock as AB
import rescue as RS
import baseline as BL  # noqa: F401  (знімок початкових налаштувань перед першою зміною)
import bugreport as BR
import crashlog as CL
import library as LB
import phonemon as PH
import updater as U
import whatsnew as WN
from i18n import tr
from pages_extra import DiagnosePage, NetworkPage, AppsPage
from pages_lab import BenchPage, AdblockPage
import sharecard as SC
import smart_ui as SM
from pages_optimize import OptimizePage, HomePage
from pages_library import LibraryPage
import pages_life as PL
from pages_tools import (GamesPage, HardwarePage, LaptopPage, CleanupPage, StartupPage, LookPage, BackupPage,
                         SettingsPage)
from ui_kit import (T, build_qss, make_font, label, vbox, hbox, dot, styled, nav_icon, logo_pixmap, Toast, Worker,
                    Ask, RunDialog, LOG, dark_titlebar)

ADMIN = E.is_admin()

NAV = [
    ("nav.g.optimize", [("home", "pulse", "nav.home"), ("optimize", "wand", "nav.optimize"),
                        ("library", "library", "nav.library"), ("games", "gamepad", "nav.games"),
                        ("diagnose", "gauge", "nav.diagnose"),
                        ("bench", "bolt", "nav.bench")]),
    ("nav.g.device", [("hardware", "chip", "nav.hardware"), ("laptop", "laptop", "nav.laptop"),
                      ("network", "globe", "nav.network")]),
    ("nav.g.tools", [("cleanup", "broom", "nav.cleanup"), ("adblock", "block", "nav.adblock"),
                     ("apps", "box", "nav.apps"), ("startup", "rocket", "nav.startup"), ("look", "palette", "nav.look")]),
    ("nav.g.system", [("backup", "shield", "nav.backup"), ("settings", "gear", "nav.settings")]),
]


def relaunch(admin: bool = True, extra=()) -> bool:
    """Перезапуск програми (з UAC, якщо admin=True)."""
    if not E.IS_WIN:
        return False
    keep = [a for a in sys.argv[1:] if not a.startswith("--lang=") and a not in ("--restarted", "--trial")]
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, keep
    else:
        exe = sys.executable
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pyw):
            exe = pyw
        args = [os.path.abspath(sys.argv[0])] + keep
    args += list(extra)
    try:
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas" if admin else "open", exe,
                                                subprocess.list2cmdline(args), None, 1)
        return r > 32
    except Exception:
        return False


class Main(QWidget):
    hotkey_pressed = pyqtSignal(str)  # з потоку гарячих клавіш у головний потік
    error_caught = pyqtSignal(str, bool)  # необроблена помилка (з будь-якого потоку) -> вікно звіту в потоці інтерфейсу

    def __init__(self, start_hidden: bool = False):
        super().__init__()
        styled(self, "root")
        self.setWindowTitle(f"{E.APP_TITLE} {E.VERSION}" + (f"  —  {tr('app.preview')}" if E.DRY_RUN else ""))
        self.setWindowIcon(QIcon(logo_pixmap(64)))
        self.resize(1280, 840)
        self.setMinimumSize(1100, 720)
        self.hw = None
        self.analysis = None
        self.checks = []
        self.restore_done = False
        self.quitting = False
        self.start_hidden = start_hidden
        self._workers: set = set()
        self._titled = False
        self.purges = 0
        self.auto_boost = False
        self.lib_boost = None  # {names, ts, seen} — режим гри, увімкнений запуском із «Бібліотеки»
        self._render_seen = {}  # exe -> коли помітили запуск гри (None — уже перевірено)
        self.tracker = LB.Tracker()
        self._ticks = 0
        self._fps_try = {}  # exe -> коли востаннє пробували записати FPS
        native = BR.native_crash()
        # через чергу подій: вікно звіту не відкривається всередині обробника помилки чи з фонового потоку
        self.error_caught.connect(lambda trace, nat: PL.ask_report(self, trace, nat), Qt.ConnectionType.QueuedConnection)
        BR.install(self.error_caught.emit)
        LB.close_lost()
        self.balancer = M.Balancer()
        self.cores = M.GameCores()
        self.rfp = PW.RefreshByPower()
        self.hk_busy = []
        self.hk = HK.Listener(self.hotkey_pressed.emit)
        self.hotkey_pressed.connect(self._hotkey)
        self.update_info = U.cached(F.CFG["updates"])  # знайдена раніше версія не зникає до наступної перевірки
        self._upd_busy = False
        self.crash = None  # збій після останніх змін (аварійний відкат)
        self.interrupted = None  # пакет змін, який обірвало аварійне завершення OptimaX
        self.crash_prompt = "--check-crash" in sys.argv
        self.ipc = L.start_server(self.show_window)  # друга копія програми просить показати це вікно

        h = hbox(self)
        h.addWidget(self._sidebar())
        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        self.pages = {}
        for key, cls in (("home", HomePage), ("optimize", OptimizePage), ("library", LibraryPage), ("games", GamesPage),
                         ("diagnose", DiagnosePage), ("bench", BenchPage), ("hardware", HardwarePage),
                         ("laptop", LaptopPage), ("network", NetworkPage), ("cleanup", CleanupPage),
                         ("adblock", AdblockPage), ("apps", AppsPage),
                         ("startup", StartupPage), ("look", LookPage), ("backup", BackupPage),
                         ("settings", SettingsPage)):
            page = cls(self)
            self.pages[key] = page
            self.stack.addWidget(styled(page, "page"))
        self._toast = Toast(self)
        self._tray()
        self.go("home")

        self.bg_timer = QTimer(self)
        self.bg_timer.timeout.connect(self._background_tick)
        self.bg_timer.start(4000)
        self.guard_timer = QTimer(self)
        self.guard_timer.timeout.connect(self._guard_tick)
        self.guard_timer.start(30 * 60 * 1000)
        if F.CFG["timer_hold"]:
            E.set_timer_resolution(True)
        if F.CFG["booster_state"]:  # минулого разу програма закрилася з увімкненим режимом гри
            self.run_quick(tr("g.title"), lambda log, p: F.BOOSTER.stop(log), ok_msg=tr("g.recovered"))
        lim = F.CFG["charge_limit"]
        if lim and lim.get("method"):  # частина ноутбуків скидає ліміт після перезавантаження
            self.run_quick("charge", lambda log, p: PW.set_charge_limit(lim["method"], lim["pct"], log), silent=True)
        if F.CFG["hotkeys"]:
            self.set_hotkeys(True, quiet=True)
        # минулого разу OptimaX закрилася аварійно посеред змін: повертаємо «напівзастосоване» й питаємо про пакет
        self.run_quick(tr("rec.title"), lambda log, p: RS.recover_on_start(log), silent=True,
                       on_done=self._recovered)
        broken = len(E.legacy_to_repair())
        if broken:  # зміни старіших версій, які виявилися шкідливими (служби ноутбука тощо), — повертаємо з журналу
            self.run_quick(tr("svc.repair_t"), lambda log, p: E.repair_legacy(log),
                           ok_msg=tr("svc.repaired", n=broken))
        self.detect()
        self.guard_refresh()
        # Оновлення перевіряємо окремо від аналізу заліза (раніше перевірка чекала на нього, а якщо аналіз
        # не вдавався — не відбувалася зовсім) і далі щогодини: програма місяцями живе в треї.
        self.upd_timer = QTimer(self)
        self.upd_timer.timeout.connect(lambda: self.check_updates(auto=True))
        self.upd_timer.start(60 * 60 * 1000)
        QTimer.singleShot(8000, lambda: self.check_updates(auto=True, startup=True))
        if G.trial_state() and G.trial_state()[0] == "decide":
            QTimer.singleShot(1500, self.ask_trial)
        self.apply_simple(bool(F.CFG["simple_ui"]))
        if native:  # минулого разу сама OptimaX закрилася аварійно — запропонувати звіт
            QTimer.singleShot(4000, lambda: PL.ask_report(self, native, True))
        self._whats_new = WN.pending()
        if self._whats_new and not start_hidden:
            QTimer.singleShot(2500, self.show_whats_new)
        if (F.CFG["phone"] or {}).get("enabled"):
            self.run_quick("phone", lambda log, p: PH.MONITOR.start(log), silent=True,
                           on_done=lambda _r: self.pages["diagnose"].phone.sync())

    def crash_scan(self):
        """Після запуску: чи не було аварійного перезавантаження, про яке ще не розповіли (і яке не пов'язане зі
        змінами OptimaX — про ті вже питає аварійний відкат)."""
        if self.quitting:
            return
        hw = self.hw or {}

        def job(log, p):
            return CL.analyze(days=7, mining=bool(hw.get("mining_gpu")))

        def done(res):
            if not isinstance(res, dict) or "incidents" not in res:
                return
            new = CL.new_since(res, int(F.CFG["crash_seen"] or 0))
            dg = self.pages["diagnose"]
            if res["incidents"]:
                F.CFG["crash_seen"] = max(i["ts"] for i in res["incidents"])
            if not new or self.crash:
                return
            F.CFG["crash_last"] = dict(res, days=7)
            dg.crash.show(F.CFG["crash_last"])
            inc = new[0]
            title, _text = CL.explain(inc)
            home = self.pages["home"]
            if not home.banner.isVisible():
                home.set_banner("pc_crash", tr("crash.banner_t"), title + (" · " + tr("crash.game", game=inc["game"])
                                                                          if inc.get("game") else ""),
                                (tr("crash.banner_btn"), lambda: (home.set_banner(None), self.go("diagnose"))),
                                (tr("btn.close"), lambda: home.set_banner(None)))
            if not self.isVisible():
                self.toast(tr("crash.banner_t"), "warn")
        self.run_quick("crash", job, silent=True, on_done=done)

    # ── простий вигляд, «Що нового», бібліотека ──
    SIMPLE_NAV = ("home", "library", "games", "diagnose", "backup", "settings")

    def apply_simple(self, on: bool):
        """Простий вигляд: у меню лише головне, на головній — оцінка, одна кнопка й проблеми з «Виправити»."""
        F.CFG["simple_ui"] = bool(on)
        for i, key in enumerate(self.nav_keys):
            self.nav.button(i).setVisible(not on or key in self.SIMPLE_NAV)
        for cap, keys in self.nav_caps:
            cap.setVisible(not on or any(k in self.SIMPLE_NAV for k in keys))
        self.pages["home"].set_simple(on)
        st = self.pages["settings"]
        if hasattr(st, "sw_simple"):
            st.sw_simple.set_quiet(bool(on))

    def show_whats_new(self):
        if not self._whats_new:
            return
        v, self._whats_new = self._whats_new, ""
        PL.show_whats_new(self, v)

    def quick_optimize(self):
        """Одна кнопка простого вигляду: план рекомендованого режиму у «Перегляді змін» (застосування — там)."""
        import modes as MD
        if not self.hw:
            self.toast(tr("home.analyzing"), "warn")
            return
        self.go("optimize")
        op = self.pages["optimize"]
        op.set_mode(0)
        op.modes.choose(MD.recommended(self.hw) or "gaming")

    def launch_game(self, g: dict, btn=None):
        """Запуск із «Бібліотеки»: режим гри (якщо ввімкнено) — до запуску, вимкнеться сам, коли гра закриється."""
        main_exe = g.get("main") or ""
        if LB.setting("boost", True) and not F.BOOSTER.active:
            self.lib_boost = {"names": set(g.get("exes") or []), "ts": time.time(), "seen": False}
            self.auto_boost = True
            self.run_quick(tr("g.title"), lambda log, p: F.BOOSTER.start(log, game=main_exe or None), silent=True,
                           on_done=lambda _r: self.update_booster_ui())
        self.run_quick(g["name"], lambda log, p: LB.launch(g, log), busy=btn, silent=True,
                       on_done=lambda r: self.toast(tr("lib.started", game=g["name"]) if isinstance(r, dict) and
                                                    r.get("ok") else tr("lib.start_fail", game=g["name"]),
                                                    "ok" if isinstance(r, dict) and r.get("ok") else "bad"))

    def _library_tick(self, names: set):
        """Сесії ігор (час гри, «що працювало під час збою»), режим гри від «Бібліотеки» і запис FPS."""
        res = self.tracker.tick(names)
        if res["started"] or res["ended"]:
            lib = self.pages.get("library")
            if lib and lib.isVisible():
                lib.on_show()
        lb = self.lib_boost
        if lb:
            on = bool(names & lb["names"])
            lb["seen"] = lb["seen"] or on
            if (lb["seen"] and not on) or (not lb["seen"] and time.time() - lb["ts"] > 600):
                self.lib_boost = None
                if F.BOOSTER.active and self.auto_boost:
                    self.auto_boost = False
                    self.run_quick(tr("g.title"), lambda log, p: F.BOOSTER.stop(log), silent=True,
                                   on_done=lambda _r: (self.update_booster_ui(), self.toast(tr("g.auto_off"))))
        if not LB.setting("fps", True) or self._workers:
            return
        import fpstest as FT
        fg = (M.foreground_process() or "").lower() if E.IS_WIN else next(iter(self.tracker.active), "")
        if not fg or fg not in self.tracker.active or not FT.find_presentmon():
            return
        if not LB.fps_due(fg, self.tracker.started_at(fg), self._fps_try.get(fg, 0)):
            return
        self._fps_try[fg] = time.time()

        def job(log, p):
            res = FT.capture(fg, LB.FPS_SECONDS, log, None)
            LB.add_fps(fg, res)
            return res
        self.run_quick("FPS", job, silent=True)

    # ── бічне меню ──
    def _sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(244)
        v = vbox(side, (14, 18, 14, 14), 2)
        brand = hbox(margins=(6, 0, 0, 0), spacing=12)
        lg = QLabel()
        lg.setPixmap(logo_pixmap(38))
        brand.addWidget(lg)
        bv = vbox()
        bv.addWidget(label(E.APP_NAME, "brand"))
        bv.addWidget(label(f"by {E.AUTHOR}", "muted"))
        brand.addLayout(bv, 1)
        v.addLayout(brand)
        v.addSpacing(10)
        nav_w = QWidget()
        nav_w.setObjectName("sideNav")
        nv = vbox(nav_w, (0, 0, 4, 0), 2)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(nav_w)
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        self.nav_keys = []
        self.nav_caps = []  # [(заголовок групи, [ключі])] — для простого вигляду
        for cap, items in NAV:
            cl = label(tr(cap), "navcap")
            nv.addWidget(cl)
            self.nav_caps.append((cl, [k for k, _, _ in items]))
            for key, ic, text in items:
                b = QPushButton(tr(text))
                b.setObjectName("nav")
                b.setCheckable(True)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
                b.setIcon(nav_icon(ic))
                b.setIconSize(QSize(19, 19))
                self.nav.addButton(b, len(self.nav_keys))
                self.nav_keys.append(key)
                nv.addWidget(b)
        nv.addStretch()
        v.addWidget(sa, 1)
        self.nav.idClicked.connect(lambda i: self.go(self.nav_keys[i]))
        st = hbox(margins=(10, 0, 0, 4), spacing=8)
        kind, text = (("warn", tr("app.preview")) if E.DRY_RUN else
                      ("ok", tr("app.admin")) if ADMIN else ("bad", tr("app.no_admin")))
        st.addWidget(dot(T[kind]))
        st.addWidget(label(text, "muted"), 1)
        v.addLayout(st)
        self.boost_line = hbox(margins=(10, 0, 0, 4), spacing=8)
        self.boost_dot = dot(T["ok"])
        self.boost_lbl = label(tr("g.on"), "muted")
        self.boost_line.addWidget(self.boost_dot)
        self.boost_line.addWidget(self.boost_lbl, 1)
        v.addLayout(self.boost_line)
        self.boost_dot.hide()
        self.boost_lbl.hide()
        ver = label(tr("app.version", v=E.VERSION), "muted")
        ver.setContentsMargins(10, 0, 0, 0)
        v.addWidget(ver)
        self.upd_side = QPushButton()  # видно на кожній сторінці, навіть коли на головній інший банер
        self.upd_side.setObjectName("sideUpd")
        self.upd_side.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upd_side.clicked.connect(self.install_update)
        self.upd_side.hide()
        v.addSpacing(6)
        v.addWidget(self.upd_side)
        return side

    def go(self, key: str):
        idx = self.nav_keys.index(key)
        self.stack.setCurrentWidget(self.pages[key])
        self.nav.button(idx).setChecked(True)
        page = self.pages[key]
        if hasattr(page, "on_show"):
            page.on_show()
        if key == "backup":
            page.reload()

    # ── трей ──
    def _tray(self):
        self.tray = QSystemTrayIcon(QIcon(logo_pixmap(32)), self)
        self.tray.setToolTip(E.APP_TITLE)
        m = QMenu()
        m.addAction(tr("tray.open")).triggered.connect(self.show_window)
        self.tray_boost = m.addAction(tr("g.btn_on"))
        self.tray_boost.triggered.connect(self.toggle_booster)
        m.addAction(tr("tray.clean_ram")).triggered.connect(
            lambda: self.run_action(E.ACTION_BY_ID["fu_memory"], None))
        self.tray_ab = m.addAction(tr("ab.tray_pause"))
        self.tray_ab.triggered.connect(lambda: self.pages["adblock"]._pause(300))
        self.tray_ab.setVisible(AB.Backend(F.CFG).mode == "filter")
        m.addSeparator()
        m.addAction(tr("tray.quit")).triggered.connect(self.quit_app)
        self.tray_menu = m
        self.tray.setContextMenu(m)
        self.tray.messageClicked.connect(self.show_window)
        self.tray.activated.connect(lambda reason: self.show_window()
                                    if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if getattr(self, "_whats_new", ""):
            QTimer.singleShot(800, self.show_whats_new)

    def quit_app(self):
        self.quitting = True
        self.close()

    # ── сповіщення ──
    def toast(self, text: str, kind: str = "ok"):
        if not self.isVisible() and self.tray.isVisible():
            self.tray.showMessage(E.APP_TITLE, text, QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        self._toast.show_msg(text, kind, QRectF(self.stack.geometry()))

    # ── фонові задачі ──
    def run_quick(self, title: str, job, busy: QPushButton = None, on_done=None, ok_msg: str = None,
                  silent: bool = False):
        """Коротка дія у фоні; журнал — у спільний лог, підсумок — спливаючим повідомленням."""
        E.CANCEL.clear()
        old = busy.text() if busy else None
        if busy:
            busy.setEnabled(False)
            busy.setText(tr("btn.working"))
        w = Worker(job)
        w.log.connect(LOG.write)

        def finished(res):
            if busy:
                try:
                    busy.setEnabled(True)
                    busy.setText(old)
                except RuntimeError:
                    pass
            if on_done:
                on_done(res)
            if not silent:
                failed = isinstance(res, dict) and bool(res.get("error") or res.get("fail") or res.get("ok") is False)
                msg = tr("toast.failed", what=title) if failed else (ok_msg or tr("toast.done", what=title))
                if E.DRY_RUN and not failed:
                    msg += " " + tr("toast.preview")
                self.toast(msg, "bad" if failed else "ok")
                self.refresh_all()

        def reap():
            w.wait()
            self._workers.discard(w)
        w.result.connect(finished)
        w.finished.connect(reap)
        self._workers.add(w)
        w.start()

    def detect(self):
        self.pages["home"].set_analyzing()

        def job(log, p):
            hw = H.detect_hw()
            return {"hw": hw, "an": H.analyze(hw), "checks": H.build_check(hw, F.CFG["games"]), "gpu_t": H.gpu_temp()}
        self.run_quick("hw", job, silent=True, on_done=self._hw_ready)

    def run_analysis(self):
        if not self.hw:
            self.detect()
            return
        self.pages["home"].set_analyzing()
        hw = self.hw
        self.run_quick("analysis", lambda log, p: {"hw": hw, "an": H.analyze(hw),
                                                    "checks": H.build_check(hw, F.CFG["games"]),
                                                    "gpu_t": H.gpu_temp()},
                       silent=True, on_done=self._hw_ready)

    def _hw_ready(self, res):
        if not isinstance(res, dict) or "hw" not in res:
            self.pages["home"].an_state.setText(tr("home.analysis_fail"))
            self.pages["home"].btn_an.setEnabled(True)
            return
        self.hw, self.analysis, self.checks = res["hw"], res["an"], res["checks"]
        self.pages["home"].set_analysis(self.hw, self.analysis, self.checks)
        self.pages["home"].set_gpu_temp(res.get("gpu_t"))
        self.pages["optimize"].set_hw(self.hw)
        self.pages["hardware"].set_hw(self.hw, self.checks)
        self.pages["laptop"].set_hw(self.hw)
        self.pages["games"].set_hw(self.hw)
        self.pages["bench"].sync_mesa()
        self.pages["cleanup"].sync()
        self.pages["look"].sync()
        self.pages["network"].sync()
        self._guard_tick()
        self.safety_check(prompt=self.crash_prompt)
        QTimer.singleShot(6000, self.crash_scan)
        if AB.Backend(F.CFG).mode == "filter":  # після оновлення програми чи збою фільтр має знову працювати
            self.run_quick("adblock", lambda log, p: AB.Backend(F.CFG).ensure_running(log), silent=True)
        if F.CFG["first_run"]:
            F.CFG["first_run"] = False
            self.collect_metrics(snapshot=True, quiet=True)
        else:
            self.collect_metrics(quiet=True)

    def collect_metrics(self, snapshot: bool = False, quiet: bool = False):
        def job(log, p):
            items = F.startup_items()
            return H.collect_metrics(sum(1 for i in items if i["enabled"]))

        def done(m):
            if not isinstance(m, dict) or m.get("error"):
                return
            if snapshot or not F.CFG["snapshot"]:
                F.CFG["snapshot"] = m
            self.pages["home"].set_metrics(m)
            if not quiet:
                self.toast(tr("ba.updated"))
        self.run_quick("metrics", job, silent=True, on_done=done)

    def refresh_all(self):
        self.pages["optimize"].refresh()
        self.pages["backup"].reload()
        self.pages["look"].sync()
        self.pages["laptop"].sync()
        self.pages["cleanup"].sync()
        self.pages["network"].sync()
        self.update_booster_ui()
        self.guard_refresh()
        self.tray_ab.setVisible(AB.Backend(F.CFG).mode == "filter")

    def _background_tick(self):
        self._ticks += 1
        names = None
        if self._ticks % 3 == 0:  # бібліотека: сесії ігор, режим гри від запуску, FPS
            names = F.running_game_names()
            try:
                self._library_tick(names)
            except Exception as e:  # облік ігор не повинен зупиняти решту фонових перевірок
                LOG.write(f"  library: {type(e).__name__}: {e}")
        # автоматичний режим гри
        if F.CFG["booster"].get("auto"):
            names = names if names is not None else F.running_game_names()
            mine = {ntpath.basename(g["path"]).lower(): g["path"] for g in F.CFG["games"] or [] if g.get("boost")}
            found = {}
            if F.CFG["booster"].get("found"):  # Game Booster 2.0: і ігри, знайдені в Steam / Epic / GOG / Ubisoft
                found = {n: n for n in (F.CFG["game_exes"] or {}).get("names") or []}
            wanted = {**found, **mine}
            running = sorted(names & set(wanted))
            game_on = bool(running)
            if game_on and not F.BOOSTER.active:
                self.auto_boost = True
                game = wanted[running[0]] if running[0] in mine else None
                self.run_quick(tr("g.title"), lambda log, p: F.BOOSTER.start(log, game=game), silent=True,
                               on_done=lambda _r: (self.update_booster_ui(), self.toast(tr("g.auto_on"))))
            elif not game_on and F.BOOSTER.active and self.auto_boost and not self.lib_boost:
                self.auto_boost = False
                self.run_quick(tr("g.title"), lambda log, p: F.BOOSTER.stop(log), silent=True,
                               on_done=lambda _r: (self.update_booster_ui(), self.toast(tr("g.auto_off"))))
        # фоновий чистильник пам'яті
        c = F.CFG["cleaner"]
        if c.get("enabled"):
            info = H.memory_lists()
            if info["standby_mb"] >= c.get("standby_mb", 1024) and info["free_mb"] <= c.get("free_mb", 1024):
                E.purge_standby()
                self.purges += 1
                LOG.write(tr("mc.purged", mb=info["standby_mb"]))
            self.pages["games"].set_cleaner_status(info, self.purges)
        games = F.CFG["games"] or []
        # ядра для ігор
        if self.hw and any(g.get("cores") for g in games):
            self.cores.tick(games, self.hw, LOG.write)
        # балансувальник фону на час гри
        if F.BOOSTER.active and F.CFG["booster"].get("balance"):
            self.balancer.tick({ntpath.basename(g["path"]).lower() for g in games}, LOG.write)
        elif self.balancer.lowered:
            self.balancer.restore_all(LOG.write)
        # частота екрана від живлення
        if self.hw and self.hw.get("battery"):
            self.rfp.tick(F.CFG["refresh_power"], LOG.write)
        # майнінгова карта: нові ігри — на неї (раз на 15 хвилин, якщо ввімкнено). Лише коли нічого іншого не
        # працює: оптимізація, відкат чи розумна оптимізація пишуть той самий журнал відкату
        if (self.hw and MG.active(self.hw) and MG.auto_due(F.CFG) and not self._workers and not MG.busy()
                and QApplication.activeModalWidget() is None and not E.JOURNAL.op()):
            MG.mark_scan(F.CFG)
            hw = self.hw
            card = self.pages["games"].mining

            def job(log, p):
                games = MG.discover()
                fresh = MG.new_games(games)
                res = MG.assign(log, hw, games)
                if not res.get("busy"):
                    res.update(list=games, scanned=True, fresh=[g["name"] for g in fresh])
                LB.refresh(games)
                return res

            def done(r):
                if card:
                    card._listed(r)
                fresh = (r or {}).get("fresh") if isinstance(r, dict) else None
                if fresh:
                    self.toast(tr("mg.new_games", n=len(fresh), names=", ".join(fresh[:3])))
            self.run_quick(tr("mg.title", gpu=MG.model(hw)), job, silent=True, on_done=done)
        elif (F.CFG["booster"].get("found") and F.game_exes_due() and not self._workers
              and QApplication.activeModalWidget() is None):
            F.mark_game_exes()
            self.run_quick("games", lambda log, p: LB.refresh(), silent=True)
        # майнінгова карта: на якій карті насправді малює запущена гра (раз за запуск гри, через 40 с після старту)
        if self.hw and MG.active(self.hw) and (F.CFG["mining"] or {}).get("check", True):
            self._render_watch(names)

    def _render_watch(self, names=None):
        card = self.pages["games"].mining
        games = card.games if card else []
        if not games or self._workers or MG.busy():
            return
        names = names if names is not None else F.running_game_names()
        now = time.time()
        seen = self._render_seen
        for n in list(seen):
            if n not in names:
                seen.pop(n, None)  # гру закрили — наступний запуск перевіримо знову
        g = next((g for g in games for x in g["exes"] if ntpath.basename(x["path"]).lower() in names
                  and x["api"] != "other"), None)
        if not g:
            return
        exe = next(ntpath.basename(x["path"]).lower() for x in g["exes"] if ntpath.basename(x["path"]).lower() in names)
        first = seen.setdefault(exe, now)
        if first is None or now - first < 40:
            return
        seen[exe] = None  # перевірено в цьому запуску гри
        hw = self.hw
        exes = {ntpath.basename(x["path"]) for x in g["exes"]}

        def job(log, p):
            import gpuinfo as GI
            luid = GI.summary(GI.probe()).get("luid") or ""
            res = GI.check(exes, luid, 5, game_dir=g["dir"])
            if res.get("verdict") in ("mining", "igpu", "warp"):
                MG.record_check(g, res)
            return res

        def done(res):
            if not isinstance(res, dict):
                return
            if card:
                card.refresh_rows()
            if res.get("verdict") in ("igpu", "warp"):
                self.toast(tr("gr.auto_igpu", game=g["name"], gpu=MG.model(hw)), "warn")
        self.run_quick("render", job, silent=True, on_done=done)

    # ── дії ──
    def toggle_booster(self):
        if F.BOOSTER.active:
            self.auto_boost = False
            job, msg = (lambda log, p: F.BOOSTER.stop(log)), tr("g.stopped")
        else:
            job, msg = (lambda log, p: F.BOOSTER.start(log)), tr("g.started")
        self.run_quick(tr("g.title"), job, ok_msg=msg, on_done=lambda _r: self.update_booster_ui())

    def update_booster_ui(self):
        on = F.BOOSTER.active
        self.pages["games"].update_state()
        self.pages["home"].update_booster()
        self.tray_boost.setText(tr("g.btn_off") if on else tr("g.btn_on"))
        self.boost_dot.setVisible(on)
        self.boost_lbl.setVisible(on)

    def set_timer_hold(self, on: bool):
        F.CFG["timer_hold"] = on
        E.set_timer_resolution(on)
        self.toast(tr("tm.on") if on else tr("tm.off"))

    def toggle_tweak(self, row, on: bool):
        t = row.t
        row.setEnabled(False)
        hw = self.hw or {}
        job = (lambda log, p: E.apply_tweaks([t], log, header=False, hw=hw)) if on else \
            (lambda log, p: E.undo_or_default(t, log))

        def done(_r):
            try:
                row.setEnabled(True)
            except RuntimeError:
                pass
        self.run_quick(t.title, job, on_done=done, ok_msg=tr("toast.on" if on else "toast.off", what=t.title))

    def run_action(self, a, busy):
        hw = self.hw or {}
        self.run_quick(a.title, lambda log, p: E.run_action(a, log, hw), busy=busy)

    def run_tweak_once(self, t, busy):
        hw = self.hw or {}
        self.run_quick(t.title, lambda log, p: E.apply_tweaks([t], log, header=False, hw=hw), busy=busy)

    def do_fix(self, kind: str, val: str, btn=None):
        if kind == "tweak":
            t = E.BY_ID[val]
            if Ask.ask(self, t.title, t.desc, tr("btn.apply")):
                self.run_tweak_once(t, btn)
        elif kind == "action":
            self.run_action(E.ACTION_BY_ID[val], btn)
        elif kind == "url":
            import webbrowser
            webbrowser.open(val)
        elif kind == "settings":
            if E.IS_WIN:
                os.startfile(val)  # noqa: лише Windows
            else:
                self.toast(tr("toast.preview_only"), "warn")
        elif kind == "page":
            self.go(val)
        elif kind == "hint":
            Ask.info(self, tr(f"hint.{val}.t"), tr(f"hint.{val}.d", model=MG.model(self.hw or {})))
        elif kind == "mining":  # «Чому лагає?»: гра малює не на майнінговій карті — до її рядка й вибору режиму
            self.go("games")
            card = self.pages["games"].mining
            row = card.find_row(val) if card else None
            if row:
                card.mode_menu(row)
            else:
                Ask.info(self, tr("hint.mining.t"), tr("gr.not_listed", exe=val or "?"))
        elif kind == "booster":
            b = F.CFG["booster"]
            b[val] = True
            F.CFG["booster"] = b
            self.pages["games"].opt_sw[val].set_quiet(True)
            self.toast(tr("g.opt_enabled", opt=tr(f"g.opt.{val}")))
        if kind in ("tweak", "action"):
            QTimer.singleShot(1500, self.run_analysis)

    def open_wizard(self):
        self.go("optimize")
        self.pages["optimize"].set_mode(1)

    def open_expert(self):
        self.go("optimize")
        self.pages["optimize"].set_mode(2)

    def open_modes(self):
        self.go("optimize")
        self.pages["optimize"].set_mode(0)

    def open_profile(self, key: str):
        self.go("optimize")
        self.pages["optimize"].open_profile(key)

    def start_apply(self, ids, restore_point: bool, sfc: bool, trial: bool = False, smart: bool = False):
        if not ids:
            return
        if smart:
            self.start_smart(ids, restore_point)
            return
        hw = self.hw or {}
        need_snapshot = not F.CFG["snapshot"]
        before = set(E.JOURNAL.data["applied"])

        def job(log, prog):
            if need_snapshot:
                items = F.startup_items()
                F.CFG["snapshot"] = H.collect_metrics(sum(1 for i in items if i["enabled"]))
            res = E.run_selected(ids, log, prog, sfc, hw=hw, restore_point=restore_point and not self.restore_done)
            RS.record_batch(before, "apply", log)
            if trial:
                old = (F.CFG["trial"] or {}).get("ids", [])
                new = [i for i in ids if E.JOURNAL.has(i) and i not in before]
                G.start_trial(list(dict.fromkeys(old + new)), log)
            return res
        dlg = RunDialog(self, tr("rv.run_title"), job)
        dlg.exec()
        if restore_point and dlg.res.get("ok") is not None:
            self.restore_done = True
        self.refresh_all()
        self.run_analysis()
        self.go("home")

    # ── пробний режим ──
    def ask_trial(self):
        st = G.trial_state()
        if not st or st[0] != "decide":
            return
        self.show_window()
        dlg = Ask(self, tr("trial.ask_t"), tr("trial.ask_d", n=len(st[1].get("ids", []))), tr("trial.keep"),
                  tr("trial.revert"), "good")
        QTimer.singleShot(120_000, dlg.reject)  # без відповіді — відкочуємо, як і обіцяли
        self.end_trial(dlg.exec() == Ask.DialogCode.Accepted)

    def end_trial(self, keep: bool):
        if keep:
            self.run_quick(tr("trial.title"), lambda log, p: G.end_trial(True, log), ok_msg=tr("trial.kept"),
                           on_done=lambda _r: self.guard_refresh())
            return
        RunDialog(self, tr("trial.revert"), lambda log, prog: G.end_trial(False, log, prog)).exec()
        self.refresh_all()

    # ── сторож налаштувань ──
    def _guard_tick(self):
        if (F.CFG["guard"] or {}).get("enabled", True) and E.JOURNAL.count() and G.due():
            self.guard_check()

    def guard_check(self, manual: bool = False, btn=None):
        def done(res):
            ids = res.get("reverted", []) if isinstance(res, dict) else []
            self.guard_refresh()
            if ids:
                self.toast(tr("guard.found", n=len(ids)), "warn")
            elif manual:
                self.toast(tr("guard.clean"))
        self.run_quick(tr("guard.title"), lambda log, p: G.run_check(log), busy=btn, silent=True, on_done=done)

    def guard_reapply(self):
        ids = [i for i in ((F.CFG["guard_state"] or {}).get("reverted") or []) if E.JOURNAL.has(i)]
        if not ids:
            return
        RunDialog(self, tr("guard.reapply"), lambda log, prog: G.reapply(ids, log, prog)).exec()
        self.refresh_all()

    def guard_forget(self):
        ids = [i for i in ((F.CFG["guard_state"] or {}).get("reverted") or []) if E.JOURNAL.has(i)]
        if not ids or not Ask.ask(self, tr("guard.forget_q", n=len(ids)), tr("guard.forget_d"), tr("guard.forget")):
            return
        n = G.forget(ids, LOG.write)
        self.toast(tr("guard.forgotten", n=n))
        self.guard_refresh()
        self.refresh_all()

    def guard_refresh(self):
        home = self.pages["home"]
        st = G.trial_state()
        rev = [i for i in ((F.CFG["guard_state"] or {}).get("reverted") or []) if E.JOURNAL.has(i)]
        cr = self.crash
        if cr and any(E.JOURNAL.has(i) for i in cr["ids"]):
            home.set_banner("crash", tr("rs.banner_t", when=time.strftime("%d.%m %H:%M", time.localtime(cr["ts"]))),
                            tr("rs.banner_d", what=RS.describe(cr["kinds"])),
                            (tr("rs.revert", n=len(cr["ids"])), self.rescue_revert),
                            (tr("rs.not_us"), self.rescue_dismiss))
        elif self._interrupted_ids():
            undo = (self.interrupted.get("op") or {}).get("kind") == "undo"
            n = len(self._interrupted_ids())
            when = time.strftime("%d.%m %H:%M", time.localtime((self.interrupted.get("op") or {}).get("ts", 0)))
            home.set_banner("crash", tr("rec.undo_t" if undo else "rec.apply_t", when=when),
                            tr("rec.undo_d" if undo else "rec.apply_d", n=n),
                            (tr("rec.finish" if undo else "rec.revert", n=n), self.interrupted_revert),
                            (tr("rec.keep"), self.interrupted_dismiss))
        elif E.JOURNAL.problem == "lost":
            home.set_banner("guard", tr("rec.lost_t"), tr("rec.lost_d"),
                            (tr("rec.lost_check"), lambda: self.go("backup")), None)
        elif st:
            n = len(st[1].get("ids", []))
            home.set_banner("trial", tr("trial.title"), tr(f"trial.{st[0]}", n=n),
                            (tr("trial.keep"), lambda: self.end_trial(True)),
                            (tr("trial.revert"), lambda: self.end_trial(False)))
        elif rev and G.looks_like_restore(rev):  # відновлення системи: спершу пропонуємо забути, а не застосувати
            home.set_banner("guard", tr("guard.restore_t", n=len(rev)), tr("guard.restore_d"),
                            (tr("guard.forget"), self.guard_forget), (tr("guard.reapply"), self.guard_reapply))
        elif rev:
            home.set_banner("guard", tr("guard.banner_t", n=len(rev)), tr("guard.banner_d"),
                            (tr("guard.reapply"), self.guard_reapply), (tr("guard.details"), lambda: self.go("backup")))
        elif self.update_info and not U.snoozed(F.CFG["updates"], self.update_info["version"]):
            home.set_banner("update", tr("upd.banner_t", v=self.update_info["version"]), tr("upd.banner_d"),
                            (tr("upd.install"), self.install_update), (tr("upd.later"), self.skip_update))
        else:
            home.set_banner(None)
        self.upd_side.setVisible(bool(self.update_info))
        if self.update_info:
            self.upd_side.setText(tr("upd.side", v=self.update_info["version"]))
        self.pages["backup"].reload_guard()

    # ── аварійний відкат ──
    def safety_check(self, prompt: bool = False, manual: bool = False, btn=None):
        def job(log, p):
            gone = RS.sync()  # що повернув OptimaX-Rescue.cmd, поки програма не працювала
            RS.write_rescue()
            return {"gone": gone, "crash": RS.check(force=manual)}

        def done(res):
            if not isinstance(res, dict):
                return
            if res.get("gone"):
                self.toast(tr("rs.synced", n=len(res["gone"])), "warn")
                self.refresh_all()
            self.crash = res.get("crash")
            self.guard_refresh()
            self.pages["backup"].sync_rescue()
            if self.crash and prompt:
                self.show_window()
                QTimer.singleShot(400, self.ask_crash)
            elif manual:
                self.toast(tr("rs.found") if self.crash else tr("rs.clean"), "warn" if self.crash else "ok")
        self.run_quick(tr("rs.title"), job, busy=btn, silent=True, on_done=done)

    # ── аварійне завершення самої OptimaX ──
    def _recovered(self, res):
        if not isinstance(res, dict):
            return
        if res.get("tweak"):
            self.toast(tr("rec.tweak_done", title=E.entry_title(res["tweak"])), "warn")
        if E.JOURNAL.problem == "restored":
            self.toast(tr("rec.restored"), "warn")
        self.interrupted = res if res.get("ids") else None
        self.guard_refresh()
        if res.get("tweak"):
            self.refresh_all()

    def _interrupted_ids(self) -> list:
        return [i for i in (self.interrupted or {}).get("ids") or [] if E.JOURNAL.has(i)]

    def interrupted_revert(self):
        ids = self._interrupted_ids()
        if ids:
            RunDialog(self, tr("rs.title"), lambda log, prog: E.undo_ids(ids, log, prog)).exec()
        E.JOURNAL.end_op()
        self.interrupted = None
        self.refresh_all()

    def interrupted_dismiss(self):
        E.JOURNAL.end_op()
        self.interrupted = None
        self.guard_refresh()
        self.toast(tr("rec.kept"))

    def ask_crash(self):
        cr = self.crash
        if not cr:
            return
        text = tr("rs.ask_d", when=time.strftime("%d.%m.%Y %H:%M", time.localtime(cr["ts"])),
                  what=RS.describe(cr["kinds"]), n=len(cr["ids"]))
        if Ask.ask(self, tr("rs.ask_t"), text, tr("rs.revert", n=len(cr["ids"])), "danger"):
            self.rescue_revert()

    def rescue_revert(self):
        RunDialog(self, tr("rs.title"), lambda log, prog: RS.revert(log, prog)).exec()
        self.crash = None
        self.refresh_all()

    def rescue_dismiss(self):
        RS.dismiss()
        self.crash = None
        self.guard_refresh()
        self.toast(tr("rs.dismissed"))

    # ── розумна оптимізація ──
    def start_smart(self, ids, restore_point: bool = True):
        s = SM.new_session(ids, "new")
        if not (s.live or s.boot):
            self.toast(tr("sm.no_perf"), "warn")
            self.start_apply(ids, restore_point, False)
            return
        SM.SmartDialog(self, s, restore_point and not self.restore_done).exec()
        self.refresh_all()
        self.run_analysis()
        self.pages["bench"].smart.sync()

    def smart_audit(self):
        s = SM.new_session((), "audit")
        if not s.live:
            self.toast(tr("sm.audit_none"), "warn")
            return
        if not Ask.ask(self, tr("sm.audit_t"), tr("sm.audit_q", n=len(s.live)), tr("sm.audit_btn")):
            return
        SM.SmartDialog(self, s).exec()
        self.refresh_all()
        self.pages["bench"].smart.sync()

    def open_smart_plan(self):
        key = (self.hw or {}).get("profile") or "M"
        self.open_profile(key)
        opt = self.pages["optimize"]
        opt.show_review(opt.expert.selected(), "expert")
        opt.review.sw_smart.set_quiet(True)
        opt.review.sw_trial.set_quiet(False)

    def resume_smart(self):
        d = F.CFG["smart"]
        if not d:
            SM.set_resume_task(False)
            return
        try:
            s = SM.AB.Session.from_dict(d)
        except Exception:
            F.CFG["smart"] = None
            return
        if (s.pending or {}).get("do") == "reboot" and G.boot_time() < s.ts:
            return  # ще не перезавантажувались
        self.show_window()
        if not Ask.ask(self, tr("sm.resume_t"), tr("sm.resume_q"), tr("sm.resume_btn")):
            F.CFG["smart"] = None
            SM.set_resume_task(False)
            return
        if (s.pending or {}).get("do") == "reboot":
            s.ok()
        SM.SmartDialog(self, s).exec()
        self.refresh_all()

    def share_result(self):
        SC.ShareDialog(self).exec()

    # ── оновлення ──
    def check_updates(self, auto: bool = False, btn=None, startup: bool = False):
        cfg = F.CFG["updates"] or {}
        if not U.enabled() or (auto and not cfg.get("auto", True)):
            return
        if (auto and not U.due(cfg)) or self._upd_busy:
            if startup:
                self.notify_update(startup=True)  # версію знайшли раніше, а перевіряти ще зарано
            return
        self._upd_busy = True

        def done(info):
            self._upd_busy = False
            c = dict(F.CFG["updates"] or {})
            now = int(time.time())
            c["last_try"] = now
            if isinstance(info, dict) and info.get("error") and not info.get("version"):
                F.CFG["updates"] = c  # невдала спроба: last_check не чіпаємо, повторимо за пів години
                self.pages["settings"].sync_updates(failed=True)
                if not auto:
                    self.toast(tr("upd.fail"), "bad")
                elif startup:
                    self.notify_update(startup=True)
                return
            c["last_check"] = now
            c["latest"] = info if isinstance(info, dict) and info.get("version") else None
            F.CFG["updates"] = c
            self.update_info = c["latest"]
            self.pages["settings"].sync_updates()
            self.guard_refresh()
            if not auto:
                self.toast(tr("upd.found", v=self.update_info["version"]) if self.update_info else tr("upd.none"),
                           "warn" if self.update_info else "ok")
            else:
                self.notify_update(startup=startup)
        self.run_quick(tr("upd.title"), lambda log, p: U.check(log), busy=btn, silent=True, on_done=done)

    def notify_update(self, startup: bool = False):
        """Спливаюче повідомлення про нову версію: під час запуску програми й один раз для кожної нової версії."""
        info = self.update_info
        c = dict(F.CFG["updates"] or {})
        if not info or U.snoozed(c, info["version"]) or (not startup and c.get("notified") == info["version"]):
            return
        c["notified"] = info["version"]
        F.CFG["updates"] = c
        if self.isVisible():
            self.toast(tr("upd.banner_t", v=info["version"]), "warn")
        elif self.tray.isVisible():
            self.tray.showMessage(E.APP_TITLE, tr("upd.banner_t", v=info["version"]) + "\n" + tr("upd.tray_d"),
                                  QSystemTrayIcon.MessageIcon.Information, 10000)

    def install_update(self):
        info = self.update_info
        if not info:
            return
        if not info.get("url") and E.IS_WIN:
            import webbrowser
            webbrowser.open(info.get("page") or "")
            return
        text = tr("upd.ask_d", v=info["version"], cur=E.VERSION) + ("\n\n" + info["notes"] if info.get("notes") else "")
        if not Ask.ask(self, tr("upd.ask_t", v=info["version"]), text, tr("upd.install")):
            return
        dlg = RunDialog(self, tr("upd.title"), lambda log, prog: {"path": U.download(info, log, prog)})
        dlg.exec()
        path = dlg.res.get("path")
        if U.launch(path, info.get("kind", "setup")) and info.get("kind") == "setup":
            self.quit_app()  # інсталятор замінить файли й запустить нову версію
        elif not E.IS_WIN or E.DRY_RUN:
            self.toast(tr("toast.preview_only"), "warn")
        elif dlg.res.get("error") or U.LAST_ERROR:
            # файл не пройшов перевірку (сума, підпис) або не завантажився — не запускаємо, пропонуємо сторінку релізу
            why = U.LAST_ERROR or dlg.res.get("error")
            if Ask.ask(self, tr("vf.fail_t"), tr("vf.fail_d", why=why), tr("fps.open_page")):
                import webbrowser
                webbrowser.open(info.get("page") or "")

    def skip_update(self):
        """«Пізніше»: ховає банер і сповіщення про цю версію на добу (раніше — назавжди)."""
        c = dict(F.CFG["updates"] or {})
        c.pop("skip", None)
        c["snooze"] = {"v": (self.update_info or {}).get("version"), "until": int(time.time()) + U.SNOOZE}
        F.CFG["updates"] = c
        self.guard_refresh()

    # ── гарячі клавіші ──
    def set_hotkeys(self, on: bool, quiet: bool = False):
        F.CFG["hotkeys"] = on
        if on:
            self.hk_busy = self.hk.start()
        else:
            self.hk.stop()
            self.hk_busy = []
        self.pages["settings"].set_hk_state(self.hk_busy)
        if not quiet:
            self.toast(tr("hk.on") if on else tr("hk.off"))

    def _hotkey(self, action: str):
        if action == "boost":
            self.toggle_booster()
        elif action == "clean":
            self.run_action(E.ACTION_BY_ID["fu_memory"], None)

    def create_restore_point(self, btn):
        def done(res):
            ok = isinstance(res, dict) and res.get("ok")
            self.restore_done = self.restore_done or bool(ok)
            if not ok:
                Ask.info(self, tr("rp.fail_t"), tr("rp.fail_d"))
        self.run_quick(tr("home.restore_point"), lambda log, p: E.create_restore_point(log), busy=btn, on_done=done,
                       ok_msg=tr("rp.ok"))

    def export_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("bk.export"), "OptimaX-profile.json", "JSON (*.json)")
        if not path:
            return
        opt = self.pages["optimize"].expert
        try:
            F.export_profile(path, opt.selected(), opt.profile)
            self.toast(tr("bk.exported"))
        except OSError as e:
            Ask.info(self, tr("bk.export"), str(e))

    def import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("bk.import"), "", "JSON (*.json)")
        if not path:
            return
        try:
            data = F.import_profile(path)
        except Exception as e:
            Ask.info(self, tr("bk.import"), str(e))
            return
        self.pages["games"].reload()
        self.open_expert()
        self.pages["optimize"].expert.set_selected(data.get("selected", []))
        self.toast(tr("bk.imported", n=len(data.get("selected", []))))

    def restart_admin(self):
        if relaunch(True, ("--restarted",)):
            self.quit_app()
        else:
            self.toast(tr("app.admin_fail"), "bad")

    def restart_app(self):
        if E.IS_WIN and relaunch(not E.DRY_RUN and ADMIN, ("--restarted",)):
            self.quit_app()
        else:
            self.toast(tr("set.restart_manual"), "warn")

    # ── події вікна ──
    def showEvent(self, e):
        if not self._titled:
            self._titled = True
            dark_titlebar(self)
        super().showEvent(e)

    def closeEvent(self, e):
        if not self.quitting and F.CFG["close_to_tray"] and self.tray.isVisible():
            e.ignore()
            self.hide()
            if not F.CFG["tray_hint_shown"]:
                F.CFG["tray_hint_shown"] = True
                self.tray.showMessage(E.APP_TITLE, tr("tray.hint"), QSystemTrayIcon.MessageIcon.Information, 4000)
            return
        running = [w for w in self._workers if w.isRunning()]
        if running and not Ask.ask(self, tr("app.busy_t"), tr("app.busy_d"), tr("btn.close"), "danger"):
            self.quitting = False
            e.ignore()
            return
        E.CANCEL.set()
        for w in running:
            w.wait(3000)
        if F.BOOSTER.active:
            F.BOOSTER.stop(LOG.write)
        self.balancer.restore_all(LOG.write)
        self.hk.stop()
        try:
            PH.MONITOR.stop(remember=False)  # сервер зупиняється, а ввімкненим лишається до наступного запуску
        except Exception:
            pass
        self.tray.hide()
        BR.clean_exit()
        e.accept()
        QApplication.instance().quit()


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(make_font(13))
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: T["bg"], QPalette.ColorRole.WindowText: T["text"],
        QPalette.ColorRole.Base: T["surf"], QPalette.ColorRole.AlternateBase: T["surf2"],
        QPalette.ColorRole.Text: T["text"], QPalette.ColorRole.Button: T["surf2"],
        QPalette.ColorRole.ButtonText: T["text"], QPalette.ColorRole.Highlight: T["acc"],
        QPalette.ColorRole.HighlightedText: "#FFFFFF", QPalette.ColorRole.ToolTipBase: T["surf2"],
        QPalette.ColorRole.ToolTipText: T["text"], QPalette.ColorRole.PlaceholderText: T["mute"],
        QPalette.ColorRole.Link: T["acc"],
    }
    for role, col in roles.items():
        pal.setColor(role, QColor(col))
    app.setPalette(pal)
    app.setStyleSheet(build_qss())


def maintenance_main() -> int:
    """Запуск із планувальника: тихе обслуговування без вікна."""
    import time as _t
    lines = []
    G.run_maintenance(lines.append)
    try:
        os.makedirs(E.DATA_DIR, exist_ok=True)
        with open(os.path.join(E.DATA_DIR, "maintenance-last.txt"), "w", encoding="utf-8") as f:
            f.write(_t.strftime("%Y-%m-%d %H:%M") + "\n" + "\n".join(map(str, lines)) + "\n")
    except OSError:
        pass
    return 0


def main():
    import selftest
    if selftest.wanted(sys.argv):
        sys.exit(selftest.main(sys.argv, ui_factory=lambda: (Main, apply_theme)))
    if "--maintenance" in sys.argv:
        sys.exit(maintenance_main())
    if "--check-crash" in sys.argv:  # задача «OptimaX Safety» після змін: вікно — лише якщо був збій
        RS.sync()
        if not RS.check() and not E.JOURNAL.op() and not E.JOURNAL.interrupted():
            sys.exit(0)
    code = L.run_cli(sys.argv)  # службові режими інсталятора: --uninstall, --set-autostart …
    if code is not None:
        sys.exit(code)
    if E.IS_WIN:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("X44TO.OptimaX")
        except Exception:
            pass
        if not E.DRY_RUN and not ADMIN and relaunch(True):
            sys.exit(0)
    app = QApplication(sys.argv)
    app.setApplicationName(E.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    if not L.acquire_instance(10.0 if "--restarted" in sys.argv else 0.0) and L.notify_running():
        sys.exit(0)  # OptimaX уже працює — ми лише показали його вікно
    apply_theme(app)
    tray_start = "--tray" in sys.argv
    w = Main(start_hidden=tray_start)
    if not tray_start:
        w.show()
    if F.CFG["smart"]:  # розумна оптимізація чекала перезавантаження
        QTimer.singleShot(2500, w.resume_smart)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
