"""
OptimaX — сторінки інструментів: Ігри, Залізо, Ноутбук, Очищення, Автозавантаження, Вигляд,
Резервні копії, Налаштування.
"""
from __future__ import annotations

import os
import subprocess
import webbrowser
from datetime import datetime

from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QColor, QGuiApplication, QRegularExpressionValidator
from PyQt6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QLineEdit, QGridLayout, QSlider, QColorDialog,
                             QFileDialog, QMenu, QSpinBox, QStackedWidget)

import engine as E
import features as F
import guard as G
import hardware as H
import hotkeys as HK
import i18n
import lifecycle as L
import mining as MG
import power as PW
import report as RP
import updater as U
from i18n import tr
from pages_optimize import TweakRow
from ui_kit import (T, label, button, card, vbox, hbox, badge, style_badge, dot, scroller, page_header, bottom_bar,
                    clear_layout, section_card, Switch, Check, Ring, OptionCard, Segmented, chip, Ask, RunDialog,
                    LogView, make_font, png_icon, APP_DIR)

DEEPSEEK_URL = "https://chat.deepseek.com"
AFTERBURNER_URL = "https://www.msi.com/Landing/afterburner/graphics-cards"


PROFILES = ("custom", "latency", "stable")  # профілі режиму гри (features.BOOST_PROFILES)


def page_body(margins=(32, 4, 32, 24), spacing=14):
    body = QWidget()
    v = vbox(body, margins, spacing)
    return body, v


class ActionRow(QFrame):
    def __init__(self, title: str, desc: str, run, btn_text: str = None):
        super().__init__()
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        h = hbox(self, (14, 10, 14, 10), 14)
        v = vbox(spacing=3)
        v.addWidget(label(title, "rowTitle"))
        v.addWidget(label(desc, "desc", wrap=True))
        h.addLayout(v, 1)
        self.btn = button(btn_text or tr("btn.run"))
        self.btn.setFixedWidth(124)
        self.btn.clicked.connect(lambda _=False: run(self.btn))
        h.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignVCenter)


def toggle_row(main, t: E.Tweak, rows: list, title: str = None) -> TweakRow:
    """Рядок, що застосовує або відкочує твік одразу при перемиканні."""
    row = TweakRow(t, title=title, impact=False)
    row.clicked.connect(lambda on, r=row: main.toggle_tweak(r, on))
    rows.append(row)
    return row


def sync_toggles(rows: list, hw: dict) -> None:
    for row in rows:
        if hw:
            row.set_compat(*E.compat(row.t, hw))
        row.sw.set_quiet(E.probe(row.t))
        row.applied.hide()


# ───────────────────────── Ігри ─────────────────────────
class GameRow(QFrame):
    def __init__(self, g: dict, page):
        super().__init__()
        self.g, self.page = g, page
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        v = vbox(self, (14, 10, 14, 10), 6)
        top = hbox(spacing=10)
        tv = vbox(spacing=1)
        tv.addWidget(label(F.game_name(g["path"]), "rowTitle"))
        p = label(g["path"], "muted")
        p.setToolTip(g["path"])
        tv.addWidget(p)
        top.addLayout(tv, 1)
        self.btn_prof = button("", "ghost", self._profile_menu)
        self.btn_prof.setToolTip(tr("games.prof.tip"))
        self._sync_prof()
        top.addWidget(self.btn_prof)
        top.addWidget(button(tr("games.remove"), "ghost", lambda: page.remove(g["path"])))
        v.addLayout(top)
        chips = hbox(spacing=6)
        self.chips = {}
        for opt in ("prio", "dgpu", "fso", "cores", "boost"):
            c = chip(tr(f"games.opt.{opt}"))
            c.setToolTip(tr(f"games.opt.{opt}.tip"))
            c.setChecked(bool(g.get(opt)))
            c.clicked.connect(lambda on, o=opt: page.set_option(self, o, on))
            chips.addWidget(c)
            self.chips[opt] = c
        chips.addStretch()
        v.addLayout(chips)

    def _sync_prof(self):
        p = self.g.get("profile") or ""
        self.btn_prof.setText(tr("games.prof", name=tr(f"g.prof.{p}") if p in PROFILES else tr("games.prof.global")))

    def _profile_menu(self):
        m = QMenu(self)
        for p in ("",) + PROFILES[1:]:
            name = tr(f"g.prof.{p}") if p else tr("games.prof.global")
            a = m.addAction(("✓  " if (self.g.get("profile") or "") == p else "    ") + name)
            a.triggered.connect(lambda _=False, p=p: self._set_prof(p))
        m.exec(self.btn_prof.mapToGlobal(self.btn_prof.rect().bottomLeft()))
        self.menu = m

    def _set_prof(self, p: str):
        F.update_game(self.g["path"], profile=p)
        self.g["profile"] = p
        self._sync_prof()

    def set_hw(self, hw: dict):
        ok = bool(hw.get("multi_gpu") or hw.get("laptop"))
        self.chips["dgpu"].setEnabled(ok or self.chips["dgpu"].isChecked())
        if not ok:
            self.chips["dgpu"].setToolTip(tr("games.opt.dgpu.na"))
        mode = hw.get("cores_mode")
        self.chips["cores"].setEnabled(bool(mode) or self.chips["cores"].isChecked())
        self.chips["cores"].setToolTip(tr(f"games.opt.cores.tip.{mode}") if mode else tr("games.opt.cores.na"))


from pages_mining import MiningCard, MiningGameRow  # noqa: E402,F401  (розділ майнінгової карти)


class GamesPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.games"), tr("games.sub")))
        body, v = page_body()

        # режим гри
        bc = card("cardAccent")
        bv = vbox(bc, (24, 20, 24, 20), 12)
        bh = hbox(spacing=12)
        tv = vbox(spacing=3)
        tv.addWidget(label(tr("g.title"), "h1"))
        tv.addWidget(label(tr("g.sub"), "sub", wrap=True))
        bh.addLayout(tv, 1)
        self.state = badge(tr("g.off"), "muted")
        bh.addWidget(self.state, 0, Qt.AlignmentFlag.AlignTop)
        bv.addLayout(bh)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        self.opt_sw = {}
        for i, key in enumerate(("power", "services", "kill", "purge", "timer", "dnd", "balance", "auto")):
            sw = Switch()
            sw.set_quiet(bool(F.CFG["booster"].get(key)))
            sw.clicked.connect(lambda on, k=key: self._set_opt(k, on))
            row = hbox(spacing=10)
            row.addWidget(sw)
            tv2 = vbox(spacing=1)
            tv2.addWidget(label(tr(f"g.opt.{key}"), "rowTitle"))
            tv2.addWidget(label(tr(f"g.opt.{key}.d"), "desc", wrap=True))
            row.addLayout(tv2, 1)
            grid.addLayout(row, i // 2, i % 2)
            self.opt_sw[key] = sw
        bv.addLayout(grid)
        brow = hbox(spacing=10)
        self.btn = button(tr("g.btn_on"), "primary", main.toggle_booster)
        brow.addWidget(self.btn)
        brow.addStretch()
        brow.addWidget(label(tr("g.profile"), "desc"))
        self.prof = Segmented([tr("g.prof.custom"), tr("g.prof.latency"), tr("g.prof.stable")])
        self.prof.setToolTip(tr("g.prof.tip"))
        self.prof.select(PROFILES.index(F.boost_profile()))
        self.prof.changed.connect(self._set_profile)
        brow.addWidget(self.prof)
        bv.addLayout(brow)
        fr = hbox(spacing=10)
        self.found_sw = Switch()
        self.found_sw.set_quiet(bool(F.CFG["booster"].get("found")))
        self.found_sw.clicked.connect(self._set_found)
        fr.addWidget(self.found_sw)
        ftv = vbox(spacing=1)
        ftv.addWidget(label(tr("g.opt.found"), "rowTitle"))
        ftv.addWidget(label(tr("g.opt.found.d"), "desc", wrap=True))
        fr.addLayout(ftv, 1)
        bv.addLayout(fr)
        self._sync_profile()
        v.addWidget(bc)

        # майнінгова карта без відеовиходів: розділ з'являється, щойно залізо визначено (set_hw)
        self.mining = None
        self.mining_box = vbox()
        v.addLayout(self.mining_box)

        # мої ігри
        gc, gv = section_card(tr("games.my"), tr("games.my_d"))
        self.games_box = vbox(spacing=2)
        gv.addLayout(self.games_box)
        self.games_empty = label(tr("games.empty"), "sub", wrap=True)
        self.games_empty.setContentsMargins(14, 6, 14, 10)
        gv.addWidget(self.games_empty)
        ab = hbox(margins=(14, 6, 14, 6), spacing=8)
        ab.addWidget(button(tr("games.add_file"), None, self.add_file))
        self.btn_running = button(tr("games.add_running"), None, self.add_running)
        ab.addWidget(self.btn_running)
        ab.addStretch()
        gv.addLayout(ab)
        v.addWidget(gc)

        # чистильник пам'яті і таймер
        two = hbox(spacing=14)
        mc, mv = section_card(tr("mc.title"), tr("mc.sub"))
        r = hbox(margins=(14, 4, 14, 4), spacing=10)
        self.mc_sw = Switch()
        self.mc_sw.set_quiet(bool(F.CFG["cleaner"].get("enabled")))
        self.mc_sw.clicked.connect(self._cleaner_on)
        r.addWidget(self.mc_sw)
        r.addWidget(label(tr("mc.enable"), "rowTitle"), 1)
        mv.addLayout(r)
        g2 = QGridLayout()
        g2.setContentsMargins(14, 4, 14, 4)
        g2.setHorizontalSpacing(10)
        self.spin = {}
        for i, key in enumerate(("standby_mb", "free_mb")):
            g2.addWidget(label(tr(f"mc.{key}"), "desc"), i, 0)
            s = QSpinBox()
            s.setRange(256, 65536)
            s.setSingleStep(256)
            s.setSuffix(" " + tr("u.mb"))
            s.setValue(int(F.CFG["cleaner"].get(key, 1024)))
            s.valueChanged.connect(lambda val, k=key: self._cleaner_val(k, val))
            g2.addWidget(s, i, 1)
            self.spin[key] = s
        g2.setColumnStretch(0, 1)
        mv.addLayout(g2)
        self.mc_status = label("", "desc", wrap=True)
        self.mc_status.setContentsMargins(14, 4, 14, 8)
        mv.addWidget(self.mc_status)
        two.addWidget(mc, 1)
        tc, tv3 = section_card(tr("tm.title"), tr("tm.sub"))
        r2 = hbox(margins=(14, 4, 14, 10), spacing=10)
        self.tm_sw = Switch()
        self.tm_sw.set_quiet(bool(F.CFG["timer_hold"]))
        self.tm_sw.clicked.connect(main.set_timer_hold)
        r2.addWidget(self.tm_sw)
        r2.addWidget(label(tr("tm.enable"), "rowTitle"), 1)
        tv3.addLayout(r2)
        tv3.addStretch()
        two.addWidget(tc, 1)
        v.addLayout(two)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        lw = QWidget()
        lv = vbox(lw, (32, 4, 32, 16), 6)
        lv.addWidget(label(tr("log.title"), "muted"))
        lv.addWidget(LogView(110))
        outer.addWidget(lw)
        self.rows = []
        self.reload()
        self.update_state()
        if main.hw:
            self._mining_card(main.hw)

    def _mining_card(self, hw: dict):
        if self.mining is None and MG.active(hw):
            self.mining = MiningCard(self.main, hw)
            self.mining_box.addWidget(self.mining)

    def _set_opt(self, key: str, on: bool):
        b = F.CFG["booster"]
        b[key] = on
        if key in F.BOOST_KEYS and F.boost_profile() != "custom" and F.BOOST_PROFILES[F.boost_profile()][key] != on:
            b["profile"] = "custom"  # перемикач змінено вручну — це вже власний набір
            self.prof.select(0)
        F.CFG["booster"] = b
        self._sync_profile()

    def _set_profile(self, i: int):
        b = F.CFG["booster"]
        b["profile"] = PROFILES[i]
        F.CFG["booster"] = b
        self._sync_profile()
        self.main.toast(tr("g.prof_set", name=tr(f"g.prof.{PROFILES[i]}")))

    def _set_found(self, on: bool):
        b = F.CFG["booster"]
        b["found"] = on
        F.CFG["booster"] = b
        if on and F.game_exes_due():
            F.mark_game_exes()
            import mining as MGx
            self.main.run_quick("games", lambda log, p: F.remember_game_exes(MGx.discover()), silent=True)

    def _sync_profile(self):
        opts = F.boost_options()
        prof = F.boost_profile()
        for k, sw in self.opt_sw.items():
            if k in F.BOOST_KEYS:
                sw.set_quiet(bool(opts.get(k)))
                sw.setToolTip(tr("g.prof.locked", name=tr(f"g.prof.{prof}")) if prof != "custom" else "")

    def _cleaner_on(self, on: bool):
        c = F.CFG["cleaner"]
        c["enabled"] = on
        F.CFG["cleaner"] = c
        self.main.toast(tr("mc.on") if on else tr("mc.off"))

    def _cleaner_val(self, key: str, val: int):
        c = F.CFG["cleaner"]
        c[key] = val
        F.CFG["cleaner"] = c

    def set_cleaner_status(self, info: dict, purges: int):
        self.mc_status.setText(tr("mc.status", standby=f"{info['standby_mb'] / 1024:.1f}",
                                  free=f"{info['free_mb'] / 1024:.1f}", n=purges))

    def update_state(self):
        on = F.BOOSTER.active
        style_badge(self.state, tr("g.on") if on else tr("g.off"), "ok" if on else "muted")
        self.btn.setText(tr("g.btn_off") if on else tr("g.btn_on"))
        self.btn.setObjectName("danger" if on else "primary")
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)

    def reload(self):
        clear_layout(self.games_box)
        self.rows = []
        for g in F.CFG["games"] or []:
            r = GameRow(g, self)
            if self.main.hw:
                r.set_hw(self.main.hw)
            self.games_box.addWidget(r)
            self.rows.append(r)
        self.games_empty.setVisible(not self.rows)

    def set_hw(self, hw: dict):
        for r in self.rows:
            r.set_hw(hw)
        self._mining_card(hw)

    def add_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("games.pick"), "", tr("games.filter"))
        if path:
            self._add(os.path.normpath(path))

    def add_running(self):
        apps = F.running_apps()
        if not apps:
            Ask.info(self, tr("games.running_none_t"), tr("games.running_none_d"))
            return
        m = QMenu(self)
        for name, path in apps[:40]:
            act = m.addAction(f"{name}    {path}")
            act.triggered.connect(lambda _=False, p=path: self._add(p))
        m.exec(self.btn_running.mapToGlobal(self.btn_running.rect().bottomLeft()))

    def _add(self, path: str):
        if F.add_game(path):
            self.reload()
            self.main.toast(tr("games.added", name=F.game_name(path)))
        else:
            self.main.toast(tr("games.exists"), "warn")

    def remove(self, path: str):
        self.main.run_quick(F.game_name(path), lambda log, p: F.remove_game(path, log), silent=True,
                            on_done=lambda _r: (self.reload(), self.main.toast(tr("games.removed"))))

    def set_option(self, row: GameRow, opt: str, on: bool):
        path = row.g["path"]
        F.update_game(path, **{opt: on})
        row.g[opt] = on
        if opt == "boost":
            return
        if opt == "cores":
            mode = (self.main.hw or {}).get("cores_mode")
            self.main.toast(tr("games.cores_on", mode=tr(f"cores.mode.{mode}")) if on and mode else
                            tr("games.cores_off"))
            return
        row.chips[opt].setEnabled(False)

        def done(_r):
            try:
                row.chips[opt].setEnabled(True)
            except RuntimeError:
                pass
        self.main.run_quick(f"{F.game_name(path)}: {tr('games.opt.' + opt)}",
                            lambda log, p: F.set_game_option(path, opt, on, log), on_done=done,
                            ok_msg=tr("games.opt_on" if on else "games.opt_off", opt=tr("games.opt." + opt)))


# ───────────────────────── Залізо ─────────────────────────
class InfoCard(QFrame):
    def __init__(self, caption: str):
        super().__init__()
        self.setObjectName("card")
        v = vbox(self, (20, 16, 20, 18), 6)
        v.addWidget(label(caption, "muted"))
        self.value = label(tr("hw.detecting"), "value", wrap=True)
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.value)
        self.sub = label("", "desc", wrap=True)
        v.addWidget(self.sub)
        v.addStretch()

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value or tr("hw.unknown"))
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))


OC_PROMPT_KEY = "oc.prompt"


class CheckRow(QFrame):
    def __init__(self, c: dict, main):
        super().__init__()
        self.setObjectName("row")
        h = hbox(self, (14, 10, 14, 10), 12)
        h.addWidget(dot(T[{"warn": "warn", "info": "acc", "ok": "ok"}[c["level"]]], 10), 0,
                    Qt.AlignmentFlag.AlignTop)
        v = vbox(spacing=2)
        v.addWidget(label(c["title"], "rowTitle", wrap=True))
        if c["detail"]:
            v.addWidget(label(c["detail"], "desc", wrap=True))
        h.addLayout(v, 1)
        fix = c.get("fix")
        if fix and c["level"] != "ok":
            kind, val = fix
            b = button(tr(f"fix.{kind}"))
            b.clicked.connect(lambda _=False: main.do_fix(kind, val, b))
            h.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)


class MsiRow(QFrame):
    def __init__(self, d: dict, page):
        super().__init__()
        self.d = d
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        h = hbox(self, (14, 9, 14, 9), 12)
        v = vbox(spacing=2)
        top = hbox(spacing=8)
        top.addWidget(label(d["name"], "rowTitle"))
        top.addWidget(badge(tr(f"msi.cls.{d['cls']}"), "muted"))
        state = "default" if d["msi"] is None else "on" if d["msi"] else "off"
        top.addWidget(badge(tr(f"msi.{state}"), "ok" if state == "on" else "muted"))
        top.addStretch()
        v.addLayout(top)
        h.addLayout(v, 1)
        self.sw = Switch()
        self.sw.set_quiet(bool(d["msi"]))
        self.sw.clicked.connect(lambda on: page.set_msi(self, on))
        h.addWidget(self.sw)


class HardwarePage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.hardware"), tr("hw.sub")))
        body, v = page_body()
        grid = QGridLayout()
        grid.setSpacing(14)
        self.cards = {k: InfoCard(tr(f"hw.{k}")) for k in ("cpu", "gpu", "ram", "disk", "display", "os")}
        for i, k in enumerate(("cpu", "gpu", "ram", "disk", "display", "os")):
            grid.addWidget(self.cards[k], i // 3, i % 3)
        v.addLayout(grid)
        self.notes = vbox(spacing=10)
        v.addLayout(self.notes)
        cc, cv = section_card(tr("hw.checks"), tr("hw.checks_d"))
        self.check_box = vbox(spacing=2)
        cv.addLayout(self.check_box)
        v.addWidget(cc)
        mc, mv = section_card(tr("msi.title"), tr("msi.sub"))
        self.msi_box = vbox(spacing=2)
        mv.addLayout(self.msi_box)
        self.msi_load = button(tr("msi.load"), "ghost", self.load_msi)
        mv.addWidget(self.msi_load, 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(mc)
        oc = card()
        ov = vbox(oc, (22, 18, 22, 18), 8)
        ov.addWidget(label(tr("oc.title"), "h2"))
        ov.addWidget(label(tr("oc.sub"), "sub", wrap=True))
        bh = hbox(spacing=10)
        self.btn_copy = button(tr("oc.copy"), "primary", self.copy)
        self.btn_copy.setEnabled(False)
        btn_ds = button(tr("oc.deepseek"), None, lambda: webbrowser.open(DEEPSEEK_URL))
        btn_msi = button("MSI Afterburner", None, self.open_afterburner)
        for b, ic in ((btn_ds, "deepsek.png"), (btn_msi, "msi.png")):
            icon = png_icon(ic)
            if icon:
                b.setIcon(icon)
        for b in (self.btn_copy, btn_ds, btn_msi):
            bh.addWidget(b)
        bh.addStretch()
        ov.addLayout(bh)
        v.addWidget(oc)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        self.msi_rows = []
        self.msi_loaded = False

    def set_hw(self, hw: dict, checks: list):
        self.cards["cpu"].set(hw.get("cpu"), H.cpu_sub(hw))
        gpus = hw.get("gpus", [])
        mining = {m["name"]: m["model"] for m in hw.get("mining") or []}

        def gpu_sub(name, vr, dt):
            drv = tr("hw.driver", d=dt) if dt else ""
            if H.is_integrated(name, vr):
                return ", ".join(x for x in (tr("hw.integrated"), drv) if x)
            mine = tr("hw.mining", model=mining[name]) if name in mining else ""
            return ", ".join(x for x in (mine, H.vram_text(vr), drv) if x)
        self.cards["gpu"].set("\n".join(n for n, _, _ in gpus), "\n".join(gpu_sub(*g) for g in gpus))
        self.cards["ram"].set(tr("u.gb", v=H.fmt_gb(hw["ram_gb"])) if hw.get("ram_gb") else "", H.ram_sub(hw))
        self.cards["disk"].set(H.disk_kind(hw), hw.get("disk_name", ""))
        rc, rm = hw.get("refresh") or (0, 0)
        self.cards["display"].set(tr("hw.hz", hz=rc) if rc else "", tr("hw.hz_max", hz=rm) if rm else "")
        self.cards["os"].set(hw.get("os", ""), tr("hw.build", b=hw["build"]) if hw.get("build") else "")
        clear_layout(self.notes)
        for key in ("x3d_dual", "hybrid", "xeon", "old", "laptop"):
            if hw.get(key):
                f = QFrame()
                f.setObjectName("bannerWarn" if key in ("x3d_dual", "old") else "bannerInfo")
                fh = vbox(f, (18, 12, 18, 12), 3)
                fh.addWidget(label(tr(f"plat.{key}.t"), "h3"))
                fh.addWidget(label(tr(f"plat.{key}.d"), "desc", wrap=True))
                self.notes.addWidget(f)
        clear_layout(self.check_box)
        for c in sorted(checks, key=lambda c: {"warn": 0, "info": 1, "ok": 2}[c["level"]]):
            self.check_box.addWidget(CheckRow(c, self.main))
        self.btn_copy.setEnabled(True)

    def on_show(self):
        if not self.msi_loaded:
            self.load_msi()

    def load_msi(self):
        self.msi_loaded = True
        self.msi_load.setEnabled(False)
        self.main.run_quick("MSI Mode", lambda log, p: H.msi_devices(), silent=True, on_done=self._fill_msi)

    def _fill_msi(self, devs):
        self.msi_load.setEnabled(True)
        self.msi_load.setText(tr("msi.reload"))
        clear_layout(self.msi_box)
        self.msi_rows = []
        for d in devs if isinstance(devs, list) else []:
            r = MsiRow(d, self)
            self.msi_box.addWidget(r)
            self.msi_rows.append(r)
        if not self.msi_rows:
            lb = label(tr("msi.none"), "sub")
            lb.setContentsMargins(14, 4, 14, 8)
            self.msi_box.addWidget(lb)

    def set_msi(self, row: MsiRow, on: bool):
        tid = "msi:" + row.d["id"]

        def job(log, p):
            if E.JOURNAL.has(tid):  # спершу повертаємо початкове значення драйвера
                E.undo_ids([tid], log)
                v = E.reg_get(E.msi_key(row.d["id"]), "MSISupported")
                if bool(v and v[1]) == on:
                    return {"ok": 1, "reboot": True}
            return E.apply_tweaks([H.msi_tweak(row.d, on)], log, header=False)
        self.main.run_quick(row.d["name"], job, ok_msg=tr("msi.changed"), on_done=lambda _r: self.load_msi())

    def copy(self):
        hw = self.main.hw or {}
        text = tr(OC_PROMPT_KEY, cpu=hw.get("cpu", "?"), gpu=RP.gpus_line(hw) or "?", ram=H.ram_line(hw),
                  os=f"{hw.get('os', '')} {hw.get('build', '')}")
        QGuiApplication.clipboard().setText(text)
        self.main.toast(tr("oc.copied"))

    def open_afterburner(self):
        cands = [os.path.join(APP_DIR, d, "MSIAfterburner.exe") for d in ("MSI", "msi")]
        for env in ("ProgramFiles(x86)", "ProgramFiles"):
            if os.environ.get(env):
                cands.append(os.path.join(os.environ[env], "MSI Afterburner", "MSIAfterburner.exe"))
        for d in ("MSI", "msi"):
            folder = os.path.join(APP_DIR, d)
            if os.path.isdir(folder):
                cands += [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.lower().endswith(".exe")]
        for c in cands:
            if os.path.isfile(c):
                try:
                    os.startfile(c)  # noqa: лише Windows
                    self.main.toast(tr("oc.ab_start"))
                except Exception as e:
                    Ask.info(self, tr("oc.ab_fail"), str(e))
                return
        if Ask.ask(self, tr("oc.ab_none_t"), tr("oc.ab_none_d"), tr("oc.ab_open")):
            webbrowser.open(AFTERBURNER_URL)


# ───────────────────────── Ноутбук ─────────────────────────
class LaptopPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.rows = []
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.laptop"), tr("lp.sub")))
        body, v = page_body()
        self.banner = QFrame()
        self.banner.setObjectName("bannerInfo")
        bv = vbox(self.banner, (18, 12, 18, 12), 3)
        bv.addWidget(label(tr("lp.no_battery_t"), "h3"))
        bv.addWidget(label(tr("lp.no_battery_d"), "desc", wrap=True))
        self.banner.hide()
        v.addWidget(self.banner)
        bc = card()
        bh = hbox(bc, (22, 18, 22, 18), 18)
        self.ring = Ring(T["ok"], 96, 8, 20)
        bh.addWidget(self.ring)
        bt = vbox(spacing=4)
        bt.addWidget(label(tr("lp.battery"), "h2"))
        self.bat_text = label(tr("lp.battery_wait"), "sub", wrap=True)
        bt.addWidget(self.bat_text)
        br = hbox(spacing=8)
        br.addWidget(button(tr("lp.refresh"), None, self.load_battery))
        br.addWidget(button(tr("lp.full_report"), "ghost", self.full_report))
        br.addStretch()
        bt.addLayout(br)
        bh.addLayout(bt, 1)
        v.addWidget(bc)
        pc, pv = section_card(tr("lp.power"), tr("lp.power_d"))
        for t in E.TWEAKS:
            if t.group == "laptop":
                pv.addWidget(toggle_row(main, t, self.rows))
        pv.addWidget(toggle_row(main, E.BY_ID["hybrid_cores"], self.rows))
        v.addWidget(pc)
        self.rfp_card, rv = section_card(tr("rfp.title"), tr("rfp.sub"))
        r = hbox(margins=(14, 4, 14, 4), spacing=12)
        self.sw_rfp = Switch()
        self.sw_rfp.set_quiet(bool(F.CFG["refresh_power"].get("enabled")))
        self.sw_rfp.clicked.connect(self.set_rfp)
        r.addWidget(self.sw_rfp)
        r.addWidget(label(tr("rfp.enable"), "rowTitle"), 1)
        r.addWidget(label(tr("rfp.battery_hz"), "desc"))
        self.spin_hz = QSpinBox()
        self.spin_hz.setRange(30, 240)
        self.spin_hz.setSingleStep(10)
        self.spin_hz.setSuffix(" " + tr("u.hz"))
        self.spin_hz.setValue(int(F.CFG["refresh_power"].get("battery_hz") or 60))
        self.spin_hz.valueChanged.connect(self.set_hz)
        r.addWidget(self.spin_hz)
        rv.addLayout(r)
        self.rfp_state = label("", "desc", wrap=True)
        self.rfp_state.setContentsMargins(14, 2, 14, 8)
        rv.addWidget(self.rfp_state)
        v.addWidget(self.rfp_card)
        self.chg_card, cv = section_card(tr("chg.title"), tr("chg.sub"))
        self.chg_box = vbox(margins=(14, 2, 14, 8), spacing=8)
        cv.addLayout(self.chg_box)
        v.addWidget(self.chg_card)
        tip = card()
        tv = vbox(tip, (22, 16, 22, 16), 6)
        tv.addWidget(label(tr("lp.dgpu_t"), "h3"))
        tv.addWidget(label(tr("lp.dgpu_d"), "desc", wrap=True))
        tv.addWidget(button(tr("lp.dgpu_btn"), "ghost", lambda: main.go("games")), 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(tip)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        self.loaded = False

    def set_hw(self, hw: dict):
        self.banner.setVisible(not hw.get("battery"))
        sync_toggles(self.rows, hw)
        for c in (self.rfp_card, self.chg_card):
            c.setVisible(bool(hw.get("battery")))
        self.sync_rfp()
        if hw.get("battery"):
            self.main.run_quick("charge", lambda log, p: PW.charge_method(hw) or "", silent=True,
                                on_done=lambda m: self.fill_charge(hw, m if isinstance(m, str) else ""))

    def sync(self):
        sync_toggles(self.rows, self.main.hw or {})
        self.sync_rfp()

    # ── частота екрана від живлення ──
    def set_rfp(self, on: bool):
        c = F.CFG["refresh_power"]
        c["enabled"] = on
        F.CFG["refresh_power"] = c
        self.main.rfp.last = None
        self.main.toast(tr("rfp.on") if on else tr("rfp.off"))
        if not on:
            rates = PW.rates()
            if rates:
                PW.set_rate(max(rates))
        self.main._background_tick()
        self.sync_rfp()

    def set_hz(self, hz: int):
        c = F.CFG["refresh_power"]
        c["battery_hz"] = int(hz)
        F.CFG["refresh_power"] = c
        self.main.rfp.last = None

    def sync_rfp(self):
        rates = PW.rates()
        self.rfp_state.setText(tr("rfp.state", hz=PW.current_rate(), src=tr("rfp.ac" if PW.on_ac() else "rfp.dc"),
                                  rates=", ".join(map(str, rates)) or "—"))

    # ── ліміт заряду ──
    def fill_charge(self, hw: dict, method: str):
        clear_layout(self.chg_box)
        self.chg_method = method
        if not method:
            self.chg_box.addWidget(label(tr(f"chg.hint.{PW.vendor_key(hw)}"), "desc", wrap=True))
            return
        cur = (F.CFG["charge_limit"] or {}).get("pct", 100)
        r = hbox(spacing=12)
        r.addWidget(label(tr("chg.limit"), "rowTitle"))
        self.chg_seg = Segmented(["60%", "80%", "100%"])
        self.chg_vals = [60, 80, 100]
        self.chg_seg.select(self.chg_vals.index(cur) if cur in self.chg_vals else 2)
        self.chg_pick = self.chg_vals.index(cur) if cur in self.chg_vals else 2
        self.chg_seg.changed.connect(lambda i: setattr(self, "chg_pick", i))
        r.addWidget(self.chg_seg)
        r.addStretch()
        self.btn_chg = button(tr("btn.apply"), "primary", self.apply_charge)
        r.addWidget(self.btn_chg)
        self.chg_box.addLayout(r)
        self.chg_box.addWidget(label(tr(f"chg.note.{method}"), "desc", wrap=True))

    def apply_charge(self):
        pct = self.chg_vals[self.chg_pick]
        method = self.chg_method

        def job(log, p):
            res = PW.set_charge_limit(method, pct, log)
            if res.get("ok"):
                F.CFG["charge_limit"] = None if pct >= 100 else dict(method=method, pct=pct)
            return res
        self.main.run_quick(tr("chg.title"), job, busy=self.btn_chg, ok_msg=tr("chg.limit_set", pct=pct))

    def on_show(self):
        if not self.loaded:
            self.load_battery()

    def load_battery(self):
        self.loaded = True
        self.main.run_quick(tr("lp.battery"), lambda log, p: H.battery_report(), silent=True, on_done=self._fill)

    def _fill(self, bats):
        if not isinstance(bats, list) or not bats:
            self.ring.text = "—"
            self.ring.set_value(0)
            self.bat_text.setText(tr("lp.battery_none"))
            return
        b = bats[0]
        health = max(0.0, 100 - b["wear"])
        self.ring.text = f"{health:.0f}%"
        self.ring.set_value(health / 100, T["ok"] if health >= 80 else T["warn"] if health >= 60 else T["bad"])
        self.bat_text.setText(tr("lp.battery_text", name=b["name"], full=f"{b['full'] / 1000:.1f}",
                                 design=f"{b['design'] / 1000:.1f}", wear=f"{b['wear']:.0f}",
                                 cycles=b["cycles"] or "—"))

    def full_report(self):
        if not E.IS_WIN:
            self.main.toast(tr("toast.preview_only"), "warn")
            return
        path = H.battery_html_report()
        if os.path.exists(path):
            os.startfile(path)  # noqa: лише Windows


# ───────────────────────── Очищення та виправлення ─────────────────────────
def hiberfil_gb() -> float:
    try:
        return os.path.getsize(os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "hiberfil.sys")) / 2**30
    except OSError:
        return 0.0


class CleanupPage(QWidget):
    def __init__(self, main):
        super().__init__()
        from pages_extra import DiskView, DriversView
        self.main = main
        self.rows = []
        outer = vbox(self)
        self.seg = Segmented([tr("cl.tab.clean"), tr("cl.tab.disk"), tr("cl.tab.drivers")])
        self.seg.changed.connect(self.set_tab)
        outer.addWidget(page_header(tr("nav.cleanup"), tr("cl.sub"), self.seg))
        self.stack = QStackedWidget()
        body, v = page_body()
        cols = hbox(spacing=14)
        left = vbox(spacing=14)
        right = vbox(spacing=14)
        c1, c1v = section_card(tr("cl.clean"), tr("cl.clean_d"))
        c2, c2v = section_card(tr("cl.fix"), tr("cl.fix_d"))
        for a in E.ACTIONS:
            row = ActionRow(a.title, a.desc, lambda b, a=a: main.run_action(a, b))
            (c1v if a.kind == "clean" else c2v).addWidget(row)
        left.addWidget(c1)
        right.addWidget(c2)
        c3, c3v = section_card(tr("cl.space"), tr("cl.space_d"))
        self.hib = label("", "desc", wrap=True)
        self.hib.setContentsMargins(14, 0, 14, 4)
        c3v.addWidget(self.hib)
        for t in E.TWEAKS:
            if t.group == "space":
                c3v.addWidget(toggle_row(main, t, self.rows))
        left.addWidget(c3)
        c4, c4v = section_card(tr("cl.maint"), tr("cl.maint_d"))
        for t in E.TWEAKS:
            if t.group == "maint":
                c4v.addWidget(ActionRow(t.title, t.desc, lambda b, t=t: main.run_tweak_once(t, b)))
        right.addWidget(c4)
        left.addStretch()
        right.addStretch()
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        v.addLayout(cols)
        v.addStretch()
        self.disk = DiskView(main)
        self.drivers = DriversView(main)
        for w in (body, self.disk, self.drivers):
            self.stack.addWidget(scroller(w))
        outer.addWidget(self.stack, 1)
        lw = QWidget()
        lv = vbox(lw, (32, 4, 32, 16), 6)
        lv.addWidget(label(tr("log.title"), "muted"))
        lv.addWidget(LogView(110))
        outer.addWidget(lw)
        self.sync()

    def set_tab(self, i: int):
        self.seg.select(i)
        self.stack.setCurrentIndex(i)

    def sync(self):
        sync_toggles(self.rows, self.main.hw or {})
        gb = hiberfil_gb()
        self.hib.setText(tr("cl.hiberfil", gb=f"{gb:.1f}") if gb else "")
        self.hib.setVisible(bool(gb))


# ───────────────────────── Автозавантаження ─────────────────────────
class StartupRow(QFrame):
    def __init__(self, item: dict, page):
        super().__init__()
        self.item = item
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        h = hbox(self, (14, 9, 14, 9), 12)
        self.sw = Switch()
        self.sw.set_quiet(item["enabled"])
        self.sw.clicked.connect(lambda on: page.toggle(self, on))
        h.addWidget(self.sw)
        v = vbox(spacing=2)
        top = hbox(spacing=8)
        top.addWidget(label(item["name"], "rowTitle"))
        top.addWidget(badge(tr(item["src"]), "muted"))
        top.addStretch()
        v.addLayout(top)
        cmd = label(item["cmd"], "muted")
        cmd.setToolTip(item["cmd"])
        v.addWidget(cmd)
        h.addLayout(v, 1)
        if item.get("file"):
            h.addWidget(button(tr("st.locate"), "ghost", lambda: page.locate(item)))


class StartupPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.startup"), tr("st.sub"), button(tr("st.refresh"), None, self.load)))
        body, v = page_body()
        self.summary = label(tr("st.loading"), "sub")
        v.addWidget(self.summary)
        c = card()
        cv = vbox(c, (8, 8, 8, 8), 2)
        self.box = vbox(spacing=2)
        cv.addLayout(self.box)
        v.addWidget(c)
        v.addWidget(label(tr("st.note"), "desc", wrap=True))
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        self.loaded = False
        self.rows = []

    def on_show(self):
        if not self.loaded:
            self.load()

    def load(self):
        self.loaded = True
        self.summary.setText(tr("st.loading"))
        self.main.run_quick(tr("nav.startup"), lambda log, p: F.startup_items(), silent=True, on_done=self._fill)

    def _fill(self, items):
        clear_layout(self.box)
        self.rows = []
        items = items if isinstance(items, list) else []
        for it in items:
            r = StartupRow(it, self)
            self.box.addWidget(r)
            self.rows.append(r)
        self._summary()

    def _summary(self):
        on = sum(r.sw.isChecked() for r in self.rows)
        self.summary.setText(tr("st.summary", on=on, total=len(self.rows)) if self.rows else tr("st.empty"))

    def toggle(self, row: StartupRow, on: bool):
        def done(res):
            if isinstance(res, dict) and not res.get("ok"):
                row.sw.set_quiet(not on)
            row.item["enabled"] = row.sw.isChecked()
            self._summary()
        self.main.run_quick(row.item["name"], lambda log, p: F.set_startup(row.item, on, log), on_done=done,
                            ok_msg=tr("st.on" if on else "st.off", name=row.item["name"]))

    def locate(self, item: dict):
        path = item.get("file") or ""
        if E.IS_WIN and os.path.exists(path):
            subprocess.Popen(["explorer.exe", "/select,", path])
        else:
            self.main.toast(tr("st.no_file"), "warn")


# ───────────────────────── Вигляд ─────────────────────────
class ColorEditor(QFrame):
    def __init__(self, tid: str, main):
        super().__init__()
        self.tid, self.main = tid, main
        self.t = E.BY_ID[tid]
        self._sync = False
        self.setObjectName("row")
        v = vbox(self, (14, 12, 14, 12), 10)
        top = hbox(spacing=14)
        self.swatch = QPushButton()
        self.swatch.setFixedSize(44, 44)
        self.swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swatch.setToolTip(tr("lk.pick"))
        self.swatch.clicked.connect(self._pick)
        top.addWidget(self.swatch)
        tv = vbox(spacing=3)
        tv.addWidget(label(self.t.title, "rowTitle"))
        tv.addWidget(label(self.t.desc, "desc", wrap=True))
        top.addLayout(tv, 1)
        v.addLayout(top)
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        self.sl, self.vals = [], []
        for i, (ch, col) in enumerate((("R", T["bad"]), ("G", T["ok"]), ("B", T["acc"]))):
            g.addWidget(label(ch, "muted"), i, 0)
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(0, 255)
            s.setStyleSheet(f"QSlider::sub-page:horizontal {{ background:{col}; border-radius:2px; }}")
            s.valueChanged.connect(self._from_sliders)
            g.addWidget(s, i, 1)
            val = label("0", "muted")
            val.setFixedWidth(30)
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            g.addWidget(val, i, 2)
            self.sl.append(s)
            self.vals.append(val)
        v.addLayout(g)
        bh = hbox(spacing=8)
        self.hex = QLineEdit()
        self.hex.setFixedWidth(110)
        self.hex.setFont(make_font(13, mono=True))
        self.hex.setValidator(QRegularExpressionValidator(QRegularExpression(r"#?[0-9A-Fa-f]{0,6}")))
        self.hex.textEdited.connect(self._from_hex)
        bh.addWidget(self.hex)
        bh.addStretch()
        self.btn_reset = button(tr("lk.reset"), None, self._reset)
        self.btn_apply = button(tr("btn.apply"), "primary", self._apply)
        bh.addWidget(self.btn_reset)
        bh.addWidget(self.btn_apply)
        v.addLayout(bh)
        self.set_rgb(E.current_color(tid))

    def rgb(self):
        return tuple(s.value() for s in self.sl)

    def set_rgb(self, rgb) -> None:
        self._sync = True
        for s, val, c in zip(self.sl, self.vals, rgb):
            s.setValue(int(c))
            val.setText(str(int(c)))
        self.hex.setText("#{:02X}{:02X}{:02X}".format(*rgb))
        self._sync = False
        self._paint()

    def _paint(self):
        r, g, b = self.rgb()
        self.swatch.setStyleSheet(f"QPushButton {{ background: rgb({r},{g},{b}); border: 2px solid {T['line3']};"
                                  f" border-radius: 10px; }} QPushButton:hover {{ border-color: {T['text']}; }}")

    def _from_sliders(self, _=None):
        if self._sync:
            return
        rgb = self.rgb()
        for val, c in zip(self.vals, rgb):
            val.setText(str(c))
        self._sync = True
        self.hex.setText("#{:02X}{:02X}{:02X}".format(*rgb))
        self._sync = False
        self._paint()

    def _from_hex(self, text: str):
        h = text.lstrip("#")
        if len(h) == 6:
            self.set_rgb(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))

    def _pick(self):
        c = QColorDialog.getColor(QColor(*self.rgb()), self, self.t.title)
        if c.isValid():
            self.set_rgb((c.red(), c.green(), c.blue()))

    def _apply(self):
        rgb = self.rgb()
        self.main.run_quick(self.t.title, lambda log, p: E.apply_tweaks([E.color_tweak(self.tid, rgb)], log,
                                                                         header=False),
                            busy=self.btn_apply, ok_msg=tr("lk.applied", what=self.t.title))

    def _reset(self):
        self.main.run_quick(self.t.title, lambda log, p: E.undo_or_default(self.t, log), busy=self.btn_reset,
                            on_done=lambda _r: self.set_rgb(E.current_color(self.tid)),
                            ok_msg=tr("lk.restored", what=self.t.title))


class LookPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.rows = []
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.look"), tr("lk.sub")))
        body, v = page_body()
        cols = hbox(spacing=14)
        c1, c1v = section_card(tr("lk.explorer"), tr("lk.explorer_d"))
        for t in E.TWEAKS:
            if t.group == "visual" and not t.custom:
                c1v.addWidget(toggle_row(main, t, self.rows))
        c2, c2v = section_card(tr("lk.colors"), tr("lk.colors_d"))
        self.colors = [ColorEditor("sel_color", main), ColorEditor("sel_text_color", main)]
        for ce in self.colors:
            c2v.addWidget(ce)
        c3, c3v = section_card(tr("grp.explorer"), tr("grp.explorer.d"))
        for t in E.TWEAKS:
            if t.group == "explorer":
                c3v.addWidget(toggle_row(main, t, self.rows))
        lc = vbox(spacing=14)
        lc.addWidget(c1)
        lc.addWidget(c3)
        lc.addStretch()
        rc = vbox(spacing=14)
        rc.addWidget(c2)
        rc.addStretch()
        cols.addLayout(lc, 1)
        cols.addLayout(rc, 1)
        v.addLayout(cols)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        self.sync()

    def sync(self):
        sync_toggles(self.rows, self.main.hw or {})


# ───────────────────────── Резервні копії ─────────────────────────
class BackupRow(QFrame):
    def __init__(self, tid: str, entry: dict, page):
        super().__init__()
        self.tid = tid
        self.title = E.entry_title(tid)
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        h = hbox(self, (14, 10, 10, 10), 14)
        self.check = Check()
        self.check.toggled.connect(lambda _: page.update_count())
        h.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)
        v = vbox(spacing=2)
        top = hbox(spacing=8)
        top.addWidget(label(self.title, "rowTitle"))
        t = E.BY_ID.get(tid)
        if (t and t.reboot) or tid.startswith("msi:"):
            top.addWidget(badge(tr("b.reboot"), "muted"))
        if entry.get("partial"):  # відкат пройшов не повністю — кроки, що лишилися, можна повторити
            pb = badge(tr("bk.partial"), "warn")
            pb.setToolTip(tr("bk.partial_d"))
            top.addWidget(pb)
        top.addStretch()
        v.addLayout(top)
        when = datetime.fromtimestamp(entry.get("ts", 0)).strftime("%d.%m.%Y, %H:%M")
        gid = t.group if t else entry.get("group", "")
        group = tr(f"grp.{gid}") if gid and f"grp.{gid}" in i18n.STR else ""
        v.addWidget(label(tr("bk.when_group", group=group, when=when) if group else tr("bk.when", when=when), "desc"))
        h.addLayout(v, 1)
        self.btn = button(tr("bk.undo_one"), "ghost")
        self.btn.clicked.connect(lambda _=False: page.undo_single(self))
        h.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.check.toggle()
        super().mouseReleaseEvent(e)


class BackupPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.rows = []
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.backup"), tr("bk.sub")))
        body, v = page_body()
        self.trial_banner = QFrame()
        self.trial_banner.setObjectName("bannerInfo")
        tb = hbox(self.trial_banner, (18, 12, 18, 12), 12)
        tbv = vbox(spacing=3)
        tbv.addWidget(label(tr("trial.title"), "h3"))
        self.trial_text = label("", "desc", wrap=True)
        tbv.addWidget(self.trial_text)
        tb.addLayout(tbv, 1)
        self.btn_keep = button(tr("trial.keep"), "good", lambda: main.end_trial(True))
        self.btn_drop = button(tr("trial.revert"), None, lambda: main.end_trial(False))
        tb.addWidget(self.btn_keep, 0, Qt.AlignmentFlag.AlignVCenter)
        tb.addWidget(self.btn_drop, 0, Qt.AlignmentFlag.AlignVCenter)
        self.trial_banner.hide()
        v.addWidget(self.trial_banner)
        gc, gv = section_card(tr("guard.title"), tr("guard.sub"))
        gr = hbox(margins=(14, 4, 14, 4), spacing=12)
        self.sw_guard = Switch()
        self.sw_guard.set_quiet(bool(F.CFG["guard"].get("enabled", True)))
        self.sw_guard.clicked.connect(self.set_guard)
        gr.addWidget(self.sw_guard)
        gr.addWidget(label(tr("guard.enable"), "rowTitle"), 1)
        self.btn_gcheck = button(tr("guard.check"), None, lambda: main.guard_check(manual=True, btn=self.btn_gcheck))
        gr.addWidget(self.btn_gcheck)
        gv.addLayout(gr)
        self.guard_state = label("", "desc", wrap=True)
        self.guard_state.setContentsMargins(14, 2, 14, 4)
        gv.addWidget(self.guard_state)
        self.guard_box = vbox(spacing=2)
        gv.addLayout(self.guard_box)
        self.btn_reapply = button(tr("guard.reapply"), "primary", main.guard_reapply)
        rr = hbox(margins=(14, 4, 14, 8))
        rr.addWidget(self.btn_reapply)
        rr.addStretch()
        gv.addLayout(rr)
        v.addWidget(gc)
        two = hbox(spacing=14)
        rp = card()
        rv = vbox(rp, (22, 18, 22, 18), 8)
        rv.addWidget(label(tr("bk.rp"), "h2"))
        rv.addWidget(label(tr("bk.rp_d"), "desc", wrap=True))
        rh = hbox(spacing=8)
        self.btn_rp = button(tr("home.restore_point"), "good", lambda: main.create_restore_point(self.btn_rp))
        rh.addWidget(self.btn_rp)
        rh.addWidget(button(tr("bk.rstrui"), None, self.open_rstrui))
        rh.addStretch()
        rv.addLayout(rh)
        two.addWidget(rp, 1)
        pf = card()
        pv = vbox(pf, (22, 18, 22, 18), 8)
        pv.addWidget(label(tr("bk.profiles"), "h2"))
        pv.addWidget(label(tr("bk.profiles_d"), "desc", wrap=True))
        ph = hbox(spacing=8)
        ph.addWidget(button(tr("bk.export"), None, main.export_profile))
        ph.addWidget(button(tr("bk.import"), None, main.import_profile))
        ph.addStretch()
        pv.addLayout(ph)
        two.addWidget(pf, 1)
        v.addLayout(two)
        rc = card()
        rcv = vbox(rc, (22, 18, 22, 18), 8)
        rcv.addWidget(label(tr("rs.title"), "h2"))
        rcv.addWidget(label(tr("rs.card_d"), "desc", wrap=True))
        self.rescue_state = label("", "muted", wrap=True)
        rcv.addWidget(self.rescue_state)
        rch = hbox(spacing=8)
        self.btn_rcheck = button(tr("rs.check"), None, lambda: main.safety_check(manual=True, btn=self.btn_rcheck))
        rch.addWidget(self.btn_rcheck)
        rch.addWidget(button(tr("rs.open"), None, self.open_rescue))
        rch.addWidget(button(tr("rs.howto"), "ghost", lambda: Ask.info(self, tr("rs.howto_t"), tr("rs.howto_d"))))
        rch.addStretch()
        rcv.addLayout(rch)
        v.addWidget(rc)
        # знімок початкових налаштувань: запасний відкат, якщо журнал загубився
        bc = card()
        bcv = vbox(bc, (22, 18, 22, 18), 8)
        bcv.addWidget(label(tr("bl.title"), "h2"))
        bcv.addWidget(label(tr("bl.card_d"), "desc", wrap=True))
        self.bl_state = label("", "muted", wrap=True)
        bcv.addWidget(self.bl_state)
        self.bl_box = vbox(spacing=2)
        bcv.addLayout(self.bl_box)
        bch = hbox(spacing=8)
        self.btn_blcheck = button(tr("bl.check"), None, self.check_baseline)
        bch.addWidget(self.btn_blcheck)
        self.btn_blrestore = button(tr("bl.restore"), "primary", self.restore_baseline)
        self.btn_blrestore.hide()
        bch.addWidget(self.btn_blrestore)
        bch.addStretch()
        bcv.addLayout(bch)
        v.addWidget(bc)
        self.orphans = []
        v.addWidget(label(tr("bk.journal"), "h2"))
        v.addWidget(label(tr("bk.journal_d"), "desc", wrap=True))
        self.list_card = card()
        self.list_lay = vbox(self.list_card, (8, 8, 8, 8), 2)
        v.addWidget(self.list_card)
        self.empty = card()
        ev = vbox(self.empty, (28, 24, 28, 24), 6)
        ev.addWidget(label(tr("bk.empty_t"), "h2"))
        ev.addWidget(label(tr("bk.empty_d"), "sub", wrap=True))
        v.addWidget(self.empty)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        bar, bh = bottom_bar()
        self.count = label("", "sub")
        bh.addWidget(self.count)
        bh.addStretch()
        self.btn_all = button(tr("opt.select_all"), None, self.toggle_all)
        bh.addWidget(self.btn_all)
        self.btn_undo = button(tr("bk.undo"), "primary", self.undo_selected)
        bh.addWidget(self.btn_undo)
        outer.addWidget(bar)
        self.reload()

    def sync_rescue(self):
        import rescue as RS
        st = RS.state()
        when = datetime.fromtimestamp(st["updated"]).strftime("%d.%m.%Y %H:%M") if st["updated"] else "—"
        self.rescue_state.setText(tr("rs.state", n=st["n"], last=st["last"], when=when, path=st["path"]))

    def open_rescue(self):
        import rescue as RS
        path = RS.write_rescue() or RS.rescue_path()
        if E.IS_WIN:
            import subprocess
            subprocess.Popen(["explorer.exe", "/select,", path])
        else:
            self.main.toast(tr("toast.preview_only"), "warn")

    def set_guard(self, on: bool):
        g = F.CFG["guard"]
        g["enabled"] = on
        F.CFG["guard"] = g
        self.main.toast(tr("guard.on") if on else tr("guard.off"))

    def reload_guard(self):
        st = F.CFG["guard_state"] or {}
        ids = [i for i in st.get("reverted", []) if E.JOURNAL.has(i)]
        if st.get("ts"):
            when = datetime.fromtimestamp(st["ts"]).strftime("%d.%m.%Y, %H:%M")
            self.guard_state.setText(tr("guard.state_bad" if ids else "guard.state_ok", when=when, os=st.get("os", ""),
                                        n=len(ids)))
        else:
            self.guard_state.setText(tr("guard.never"))
        clear_layout(self.guard_box)
        for tid in ids:
            r = hbox(margins=(14, 2, 14, 2), spacing=10)
            r.addWidget(dot(T["warn"], 8), 0, Qt.AlignmentFlag.AlignVCenter)
            r.addWidget(label(E.entry_title(tid), "rowTitle"), 1)
            self.guard_box.addLayout(r)
        self.btn_reapply.setVisible(bool(ids))
        self.btn_reapply.setText(tr("guard.reapply_n", n=len(ids)))
        t = G.trial_state()
        self.trial_banner.setVisible(bool(t))
        if t:
            self.trial_text.setText(tr(f"trial.{t[0]}", n=len(t[1].get("ids", []))))

    def reload(self):
        self.reload_guard()
        self.sync_rescue()
        self.sync_baseline()
        keep = {r.tid for r in self.rows if r.check.isChecked()}
        clear_layout(self.list_lay)
        self.rows = []
        for tid in E.JOURNAL.newest_first():
            r = BackupRow(tid, E.JOURNAL.get(tid) or {}, self)
            r.check.setChecked(tid in keep)
            self.rows.append(r)
            self.list_lay.addWidget(r)
        self.list_card.setVisible(bool(self.rows))
        self.empty.setVisible(not self.rows)
        self.update_count()

    def selected(self):
        return [r.tid for r in self.rows if r.check.isChecked()]

    def update_count(self):
        n = len(self.selected())
        self.count.setText(tr("opt.count", n=n, total=len(self.rows)) if self.rows else "")
        self.btn_undo.setEnabled(n > 0)
        self.btn_undo.setText(tr("bk.undo_n", n=n) if n else tr("bk.undo"))
        self.btn_all.setEnabled(bool(self.rows))
        self.btn_all.setText(tr("opt.clear_all") if self.rows and n == len(self.rows) else tr("opt.select_all"))

    def toggle_all(self):
        on = len(self.selected()) != len(self.rows)
        for r in self.rows:
            r.check.setChecked(on)

    def undo_selected(self):
        ids = self.selected()
        if not ids or not Ask.ask(self, tr("bk.undo_q", n=len(ids)), tr("bk.undo_text"), tr("bk.undo")):
            return
        RunDialog(self.main, tr("bk.undo_title"), lambda log, prog: E.undo_ids(ids, log, prog)).exec()
        self.main.refresh_all()

    def undo_single(self, row: BackupRow):
        self.main.run_quick(row.title, lambda log, p: E.undo_ids([row.tid], log), busy=row.btn,
                            ok_msg=tr("bk.undone", what=row.title))

    # ── знімок початкових налаштувань ──
    def sync_baseline(self):
        import baseline as BL
        st = BL.state()
        if st["exists"]:
            when = datetime.fromtimestamp(st["ts"]).strftime("%d.%m.%Y %H:%M")
            self.bl_state.setText(tr("bl.state", when=when, n=st["n"]))
        else:
            self.bl_state.setText(tr("bl.none"))
        self.btn_blcheck.setEnabled(st["exists"])

    def check_baseline(self):
        import baseline as BL
        self.main.run_quick(tr("bl.title"), lambda log, p: {"orphans": BL.orphans()}, busy=self.btn_blcheck,
                            silent=True, on_done=self._baseline_checked)

    def _baseline_checked(self, res):
        self.orphans = (res or {}).get("orphans") or [] if isinstance(res, dict) else []
        clear_layout(self.bl_box)
        titles = list(dict.fromkeys(E.entry_title(t) for o in self.orphans for t in o["tweaks"][:1]))
        for title in titles[:8]:
            r = hbox(margins=(0, 2, 0, 2), spacing=10)
            r.addWidget(dot(T["warn"], 8), 0, Qt.AlignmentFlag.AlignVCenter)
            r.addWidget(label(title, "rowTitle"), 1)
            self.bl_box.addLayout(r)
        if len(titles) > 8:
            self.bl_box.addWidget(label(tr("bl.more", n=len(titles) - 8), "muted"))
        self.btn_blrestore.setVisible(bool(self.orphans))
        self.btn_blrestore.setText(tr("bl.restore_n", n=len(self.orphans)))
        self.main.toast(tr("bl.found", n=len(self.orphans)) if self.orphans else tr("bl.clean"),
                        "warn" if self.orphans else "ok")

    def restore_baseline(self):
        import baseline as BL
        items = list(self.orphans)
        if not items or not Ask.ask(self, tr("bl.restore"), tr("bl.restore_q", n=len(items)), tr("bl.restore"),
                                    "danger"):
            return
        RunDialog(self.main, tr("bl.title"), lambda log, prog: BL.restore(items, log, prog)).exec()
        self.orphans = []
        clear_layout(self.bl_box)
        self.btn_blrestore.hide()
        self.main.refresh_all()

    def open_rstrui(self):
        if E.DRY_RUN or not E.IS_WIN:
            self.main.toast(tr("toast.preview_only"), "warn")
            return
        try:
            subprocess.Popen(["rstrui.exe"])
        except Exception as e:
            Ask.info(self, tr("bk.rstrui_fail"), str(e))


# ───────────────────────── Налаштування ─────────────────────────
class SettingsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.settings"), tr("set.sub")))
        body, v = page_body()
        lc, lv = section_card(tr("set.lang"), tr("set.lang_d"))
        self.lang_cards = []
        box = hbox(margins=(14, 4, 14, 8), spacing=10)
        for code, name in i18n.LANGS:
            c = OptionCard(name, tr(f"set.lang.{code}"))
            c.setMinimumHeight(70)
            c.setChecked(code == i18n.LANG)
            c.clicked.connect(lambda _=False, cd=code: self.pick_lang(cd))
            box.addWidget(c)
            self.lang_cards.append((code, c))
        lv.addLayout(box)
        self.lang_note = label("", "warnNote", wrap=True)
        self.lang_note.hide()
        lv.addWidget(self.lang_note)
        self.btn_restart = button(tr("set.restart"), "primary", main.restart_app)
        self.btn_restart.hide()
        rb = hbox(margins=(14, 0, 14, 8))
        rb.addWidget(self.btn_restart)
        rb.addStretch()
        lv.addLayout(rb)
        v.addWidget(lc)
        bc, bv = section_card(tr("set.bg"), tr("set.bg_d"))
        for key, cb, state in (("tray", self.set_tray, bool(F.CFG["close_to_tray"])),
                               ("autostart", self.set_autostart, False)):
            r = hbox(margins=(14, 4, 14, 4), spacing=12)
            sw = Switch()
            sw.set_quiet(state)
            sw.clicked.connect(cb)
            r.addWidget(sw)
            tv = vbox(spacing=1)
            tv.addWidget(label(tr(f"set.{key}"), "rowTitle"))
            tv.addWidget(label(tr(f"set.{key}.d"), "desc", wrap=True))
            r.addLayout(tv, 1)
            bv.addLayout(r)
            setattr(self, f"sw_{key}", sw)
        v.addWidget(bc)
        sc, sv = section_card(tr("sched.title"), tr("sched.sub"))
        sch = F.CFG["schedule"]
        r = hbox(margins=(14, 4, 14, 4), spacing=12)
        self.sw_sched = Switch()
        self.sw_sched.set_quiet(bool(sch.get("enabled")))
        self.sw_sched.clicked.connect(lambda on: self.save_schedule(on))
        r.addWidget(self.sw_sched)
        r.addWidget(label(tr("sched.enable"), "rowTitle"), 1)
        sv.addLayout(r)
        r2 = hbox(margins=(14, 4, 14, 4), spacing=10)
        r2.addWidget(label(tr("sched.day"), "desc"))
        self.day_seg = Segmented([tr(f"day.{d}") for d in range(7)])
        self.day = int(sch.get("day", 6))
        self.day_seg.select(self.day)
        self.day_seg.changed.connect(self.pick_day)
        r2.addWidget(self.day_seg)
        r2.addSpacing(10)
        r2.addWidget(label(tr("sched.hour"), "desc"))
        self.hour = QSpinBox()
        self.hour.setRange(0, 23)
        self.hour.setSuffix(":00")
        self.hour.setValue(int(sch.get("hour", 12)))
        self.hour.valueChanged.connect(lambda _v: self.save_schedule(self.sw_sched.isChecked()))
        r2.addWidget(self.hour)
        r2.addStretch()
        sv.addLayout(r2)
        r3 = hbox(margins=(14, 2, 14, 8), spacing=10)
        self.sched_state = label("", "desc", wrap=True)
        r3.addWidget(self.sched_state, 1)
        self.btn_maint = button(tr("sched.run_now"), None, self.run_maint)
        r3.addWidget(self.btn_maint)
        sv.addLayout(r3)
        v.addWidget(sc)
        hc, hv = section_card(tr("hk.title"), tr("hk.sub"))
        r = hbox(margins=(14, 4, 14, 4), spacing=12)
        self.sw_hk = Switch()
        self.sw_hk.set_quiet(bool(F.CFG["hotkeys"]))
        self.sw_hk.clicked.connect(main.set_hotkeys)
        r.addWidget(self.sw_hk)
        r.addWidget(label(tr("hk.enable"), "rowTitle"), 1)
        hv.addLayout(r)
        for action in ("boost", "clean"):
            kr = hbox(margins=(14, 2, 14, 2), spacing=12)
            kb = label(HK.label(action), "mono")
            kb.setFixedWidth(130)
            kr.addWidget(kb)
            kr.addWidget(label(tr(f"hk.{action}"), "desc"), 1)
            hv.addLayout(kr)
        self.hk_state = label("", "warnNote", wrap=True)
        self.hk_state.hide()
        hv.addWidget(self.hk_state)
        v.addWidget(hc)
        self.upd_card, uv = section_card(tr("upd.title"), tr("upd.sub"))
        ur = hbox(margins=(14, 4, 14, 4), spacing=12)
        self.sw_upd = Switch()
        self.sw_upd.set_quiet(bool((F.CFG["updates"] or {}).get("auto", True)))
        self.sw_upd.clicked.connect(self.set_auto_update)
        ur.addWidget(self.sw_upd)
        ur.addWidget(label(tr("upd.auto"), "rowTitle"), 1)
        self.btn_upd = button(tr("guard.check"), None, lambda: main.check_updates(auto=False, btn=self.btn_upd))
        ur.addWidget(self.btn_upd)
        uv.addLayout(ur)
        ur2 = hbox(margins=(14, 2, 14, 8), spacing=10)
        self.upd_state = label("", "desc", wrap=True)
        ur2.addWidget(self.upd_state, 1)
        self.btn_upd_install = button(tr("upd.install"), "primary", main.install_update)
        self.btn_upd_install.hide()
        ur2.addWidget(self.btn_upd_install)
        uv.addLayout(ur2)
        self.upd_card.setVisible(U.enabled())
        v.addWidget(self.upd_card)
        # вигляд, «Що нового», перенесення налаштувань, звіт про проблему
        import pages_life as PL
        xc, xv = section_card(tr("set.more"), tr("set.more_d"))
        r = hbox(margins=(14, 4, 14, 4), spacing=12)
        self.sw_simple = Switch()
        self.sw_simple.set_quiet(bool(F.CFG["simple_ui"]))
        self.sw_simple.clicked.connect(main.apply_simple)
        r.addWidget(self.sw_simple, 0, Qt.AlignmentFlag.AlignTop)
        tv = vbox(spacing=1)
        tv.addWidget(label(tr("set.simple"), "rowTitle"))
        tv.addWidget(label(tr("set.simple_d"), "desc", wrap=True))
        r.addLayout(tv, 1)
        xv.addLayout(r)
        xb = hbox(margins=(14, 4, 14, 10), spacing=8)
        xb.addWidget(button(tr("set.whats_new"), None, lambda: PL.show_whats_new(self, E.VERSION)))
        xb.addWidget(button(tr("set.report"), None, lambda: PL.manual_report(main)))
        xb.addStretch()
        xv.addLayout(xb)
        v.addWidget(xc)
        self.transfer = PL.TransferCard(main, v)
        ac = card()
        av = vbox(ac, (22, 18, 22, 18), 6)
        av.addWidget(label(E.APP_TITLE, "h2"))
        av.addWidget(label(tr("set.version", v=E.VERSION) + " · " + tr("lc.installed" if L.is_installed() else "lc.portable"),
                           "desc"))
        mode = tr("set.mode.preview") if E.DRY_RUN else tr("set.mode.admin") if E.is_admin() else tr("set.mode.user")
        av.addWidget(label(mode, "desc"))
        ah = hbox(spacing=8)
        ah.addWidget(button(tr("set.data"), None, self.open_data))
        ah.addStretch()
        av.addLayout(ah)
        v.addWidget(ac)
        v.addStretch()
        outer.addWidget(scroller(body), 1)

    def on_show(self):
        self.main.run_quick("autostart", lambda log, p: F.autostart_enabled(), silent=True,
                            on_done=lambda on: self.sw_autostart.set_quiet(bool(on)))
        self.sync_sched()
        self.sync_updates()

    def pick_day(self, i: int):
        self.day = i
        self.save_schedule(self.sw_sched.isChecked())

    def save_schedule(self, on: bool):
        day, hour = self.day, self.hour.value()

        def done(ok):
            if not ok:
                self.sw_sched.set_quiet(False)
            self.sync_sched()
        self.main.run_quick(tr("sched.title"), lambda log, p: G.set_schedule(on, day, hour, log), on_done=done,
                            ok_msg=tr("sched.on", day=tr(f"day.{day}"), hour=hour) if on else tr("sched.off"),
                            silent=not on and not F.CFG["schedule"].get("enabled"))

    def sync_sched(self):
        last = F.CFG["maint_last"]
        if last:
            when = datetime.fromtimestamp(last["ts"]).strftime("%d.%m.%Y, %H:%M")
            self.sched_state.setText(tr("sched.last", when=when, mb=last.get("freed_mb", 0), n=last.get("reverted", 0)))
        else:
            self.sched_state.setText(tr("sched.never"))

    def run_maint(self):
        self.main.run_quick(tr("sched.title"), lambda log, p: G.run_maintenance(log), busy=self.btn_maint,
                            on_done=lambda _r: (self.sync_sched(), self.main.guard_refresh()))

    def set_auto_update(self, on: bool):
        c = F.CFG["updates"] or {}
        c["auto"] = on
        F.CFG["updates"] = c

    def sync_updates(self, failed: bool = False):
        info = self.main.update_info
        last = (F.CFG["updates"] or {}).get("last_check")
        if failed and not info:
            self.upd_state.setText(tr("upd.state_fail", v=E.VERSION))
        elif info:
            self.upd_state.setText(tr("upd.state_new", v=info["version"], cur=E.VERSION))
        elif last:
            self.upd_state.setText(tr("upd.state_ok", v=E.VERSION,
                                      when=datetime.fromtimestamp(last).strftime("%d.%m.%Y, %H:%M")))
        else:
            self.upd_state.setText(tr("upd.state_never", v=E.VERSION))
        self.btn_upd_install.setVisible(bool(info))

    def set_hk_state(self, busy: list):
        self.hk_state.setVisible(bool(busy))
        if busy:
            self.hk_state.setText(tr("hk.busy", keys=", ".join(HK.label(a) for a in busy)))

    def pick_lang(self, code: str):
        for c, card_ in self.lang_cards:
            card_.setChecked(c == code)
        F.CFG["language"] = code
        changed = code != i18n.LANG
        self.lang_note.setText(tr("set.lang_restart"))
        self.lang_note.setVisible(changed)
        self.btn_restart.setVisible(changed)

    def set_tray(self, on: bool):
        F.CFG["close_to_tray"] = on

    def set_autostart(self, on: bool):
        def done(ok):
            if not ok:
                self.sw_autostart.set_quiet(not on)
        self.main.run_quick(tr("set.autostart"), lambda log, p: F.set_autostart(on, log), on_done=done,
                            ok_msg=tr("set.autostart_on" if on else "set.autostart_off"))

    def open_data(self):
        os.makedirs(E.DATA_DIR, exist_ok=True)
        if E.IS_WIN:
            os.startfile(E.DATA_DIR)  # noqa: лише Windows
        else:
            self.main.toast(E.DATA_DIR)
