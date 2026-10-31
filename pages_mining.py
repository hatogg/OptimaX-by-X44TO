"""
OptimaX — розділ «Ігри на <майнінговій карті>» на сторінці «Ігри»: Universal GPU Renderer (режим рендерингу для
кожної гри, перевірка, на якій карті гра малює насправді), аналізатори карти (драйвер і API, пам'ять, PCIe, кеш
шейдерів) і шари DXVK / Mesa. Логіка — у mining.py, gpuinfo.py, gpudiag.py, gamedb.py; тут — лише інтерфейс.
"""
from __future__ import annotations

import ntpath
import time
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFrame, QMenu, QFileDialog

import engine as E
import features as F
import gamedb as DB
import gpudiag as GD
import gpuinfo as GI
import mining as MG
from i18n import tr
from ui_kit import T, label, button, vbox, hbox, badge, dot, clear_layout, Switch, Segmented, Ask

API_NAMES = {"dx9": "DX9", "dx10": "DX10", "dx11": "DX11", "dx12": "DX12", "gl": "OpenGL", "vulkan": "Vulkan",
             "other": "?"}
LEVEL_COLOR = {"ok": "ok", "info": "acc", "warn": "warn", "bad": "bad"}
VERDICT_KIND = {"mining": "ok", "igpu": "bad", "warp": "bad", "idle": "muted", "none": "muted"}


def api_text(g: dict) -> str:
    apis = []
    for x in g["exes"]:
        if x["api"] != "other" and x["api"] not in apis:
            apis.append(x["api"])
    arch = sorted({x.get("arch") or "?" for x in g["exes"] if x["api"] != "other"})
    return " / ".join(API_NAMES[a] for a in apis[:3]) + (f" · {', '.join(arch)}" if arch else "") if apis else "?"


def when(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d.%m %H:%M")
    except (TypeError, ValueError, OSError):
        return "—"


def info_row(level: str, title: str, desc: str = "", btn=None) -> QFrame:
    row = QFrame()
    row.setObjectName("row")
    h = hbox(row, (14, 8, 14, 8), 10)
    h.addWidget(dot(T[LEVEL_COLOR.get(level, "mute")], 9), 0, Qt.AlignmentFlag.AlignTop)
    v = vbox(spacing=1)
    v.addWidget(label(title, "rowTitle", wrap=True))
    if desc:
        v.addWidget(label(desc, "desc", wrap=True))
    h.addLayout(v, 1)
    if btn is not None:
        h.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


class MiningGameRow(QFrame):
    """Гра: API й розрядність, античит, режим рендерингу, що зроблено і що показала остання перевірка."""

    def __init__(self, g: dict, card):
        super().__init__()
        self.g, self.card = g, card
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        h = hbox(self, (14, 9, 14, 9), 10)
        self.dot = dot(T["mute"], 9)
        h.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignTop)
        tv = vbox(spacing=2)
        top = hbox(spacing=6)
        top.addWidget(label(g["name"], "rowTitle"))
        top.addWidget(badge(tr(f"mg.store.{g['store']}"), "muted"))
        top.addWidget(badge(api_text(g), "muted"))
        if g.get("anticheat"):
            ac = badge(g["anticheat"], "warn")
            ac.setToolTip(tr("mg.why.anticheat"))
            top.addWidget(ac)
        self.mode_badge = badge("", "acc")
        top.addWidget(self.mode_badge)
        top.addStretch()
        tv.addLayout(top)
        self.status = label("", "desc", wrap=True)
        tv.addWidget(self.status)
        self.check = label("", "muted", wrap=True)
        tv.addWidget(self.check)
        h.addLayout(tv, 1)
        self.btn_mode = button(tr("gr.mode_btn"), None, lambda: card.mode_menu(self))
        h.addWidget(self.btn_mode, 0, Qt.AlignmentFlag.AlignVCenter)
        self.btn_check = button(tr("gr.check_btn"), "ghost", lambda: card.check_game(self))
        h.addWidget(self.btn_check, 0, Qt.AlignmentFlag.AlignVCenter)
        self.btn_more = button("⋯", "ghost", lambda: card.more_menu(self))
        self.btn_more.setFixedWidth(36)
        h.addWidget(self.btn_more, 0, Qt.AlignmentFlag.AlignVCenter)
        self.sync()

    def sync(self):
        gpu = self.card.gpu
        g = self.g
        st = MG.game_status(g)
        mode = st["mode"]
        self.mode_badge.setText(tr(f"mg.mode.{mode}"))
        parts, color = [], "mute"
        usable = st["total"] - st["dx9"]
        if g.get("risk"):
            parts.append(tr("mg.st.air"))
        elif mode == "original":
            parts.append(tr("gr.st.original"))
        elif usable:
            if st["on"]:
                parts.append(tr("mg.st.on", gpu=gpu) if st["on"] == usable and not st["free"] else
                             tr("mg.st.part", gpu=gpu, n=st["on"], total=usable))
                color = "ok"
            elif st["kept"] and not st["free"]:
                parts.append(tr("mg.st.kept"))
            else:
                parts.append(tr("mg.st.free"))
        if st["dx9"] and not g.get("risk") and mode != "original":
            if st["dx9"] > st["dx9_na"]:
                parts.append(tr("mg.st.dx9_on", gpu=gpu) if st["dxvk"] else tr("mg.st.dx9", gpu=gpu))
                color = "ok" if st["dxvk"] else "warn"
            if st["dx9_na"]:
                parts.append(tr("mg.st.dx9_na"))
        if st.get("dxvk_dx11"):
            parts.append(tr("gr.st.dxvk_dx11"))
        if st["gl"] > st["gl_na"] and mode != "original":
            parts.append(tr("mg.st.gl_on", gpu=gpu) if st["mesa"] else tr("mg.st.gl", gpu=gpu))
            if not st["mesa"]:
                color = "warn"
        if st["gl_na"]:
            parts.append(tr("mg.st.gl_na"))
        self.status.setText(" · ".join(parts))
        last = DB.verified(g)
        if last:
            v = last.get("verdict") or "none"
            text = tr(f"gr.last.{v}", gpu=gpu, when=when(last.get("ts")), mode=tr(f"mg.mode.{last.get('mode') or 'native'}"))
            if last.get("path"):
                text += f" · {last['path']}"
            self.check.setText(text)
            self.check.setStyleSheet(f"color:{T[{'mining': 'ok', 'igpu': 'bad', 'warp': 'bad'}.get(v, 'sub')]};")
            if v in ("igpu", "warp"):
                color = "bad"
            elif v == "mining" and color != "warn":
                color = "ok"
        else:
            rec = MG.recommend(g)
            self.check.setText(tr("gr.rec", mode=tr(f"mg.mode.{rec['mode']}"), why=tr(f"mg.rec.{rec['why'][0]}")))
            self.check.setStyleSheet("")
        self.dot.setStyleSheet(f"background:{T[color]};border-radius:4px;")


class MiningCard(QFrame):
    """Майнінгова карта без відеовиходів (P106/P104/CMP)."""

    def __init__(self, main, hw: dict):
        super().__init__()
        self.main, self.hw = main, hw
        self.gpu = MG.model(hw)
        self.rows = []
        self.games = []
        self.setObjectName("card")
        v = vbox(self, (8, 14, 8, 10), 4)
        head = vbox(margins=(14, 0, 14, 6), spacing=2)
        head.addWidget(label(tr("mg.title", gpu=self.gpu), "h2"))
        head.addWidget(label(tr("mg.sub", gpu=self.gpu), "desc", wrap=True))
        v.addLayout(head)

        # Universal GPU Renderer: що бачать DirectX і Vulkan
        rh = hbox(margins=(14, 4, 14, 2), spacing=10)
        rv = vbox(spacing=1)
        rv.addWidget(label(tr("gr.title"), "h3"))
        self.probe_lbl = label(tr("gr.probe_wait"), "desc", wrap=True)
        rv.addWidget(self.probe_lbl)
        rh.addLayout(rv, 1)
        self.btn_probe = button(tr("gr.probe_btn"), "ghost", lambda: self.probe(True))
        rh.addWidget(self.btn_probe, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(rh)
        self.drv_box = vbox(spacing=2)
        v.addLayout(self.drv_box)
        self.fso_box = vbox(spacing=2)
        v.addLayout(self.fso_box)

        # як перекладати OpenGL
        gr = hbox(margins=(14, 6, 14, 4), spacing=10)
        gv = vbox(spacing=1)
        gv.addWidget(label(tr("gr.gl_t"), "rowTitle"))
        gv.addWidget(label(tr("gr.gl_d"), "desc", wrap=True))
        gr.addLayout(gv, 1)
        self.gl_seg = Segmented([tr("gr.gl_d3d12"), tr("gr.gl_zink")])
        self.gl_seg.select(1 if MG.gl_driver() == "zink" else 0)
        self.gl_seg.changed.connect(self._gl_driver)
        gr.addWidget(self.gl_seg, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(gr)

        for key, title, desc, val in (("auto", "mg.auto", "mg.auto_d", bool((F.CFG["mining"] or {}).get("auto"))),
                                      ("check", "gr.watch", "gr.watch_d",
                                       bool((F.CFG["mining"] or {}).get("check", True)))):
            r = hbox(margins=(14, 4, 14, 4), spacing=10)
            sw = Switch()
            sw.set_quiet(val)
            sw.clicked.connect(lambda on, k=key: self._switch(k, on))
            r.addWidget(sw, 0, Qt.AlignmentFlag.AlignTop)
            tv = vbox(spacing=1)
            tv.addWidget(label(tr(title), "rowTitle"))
            tv.addWidget(label(tr(desc), "desc", wrap=True))
            r.addLayout(tv, 1)
            v.addLayout(r)
            setattr(self, f"{key}_sw", sw)
        b = hbox(margins=(14, 6, 14, 6), spacing=8)
        self.btn_scan = button(tr("mg.scan"), "primary", self.scan)
        b.addWidget(self.btn_scan)
        self.btn_revert = button(tr("mg.revert"), "ghost", self.revert)
        b.addWidget(self.btn_revert)
        b.addStretch()
        b.addWidget(button(tr("gr.export"), "ghost", self.export_profiles))
        b.addWidget(button(tr("gr.import"), "ghost", self.import_profiles))
        v.addLayout(b)
        self.list_box = vbox(spacing=2)
        v.addLayout(self.list_box)
        self.empty = label(tr("mg.empty"), "sub", wrap=True)
        self.empty.setContentsMargins(14, 4, 14, 8)
        v.addWidget(self.empty)

        # шари
        self.layer_lbl, self.layer_btn = {}, {}
        for kind, title, desc in (("dxvk", "mg.dxvk_t", "mg.dxvk_d"), ("mesa", "mg.mesa_t", "mg.mesa_d")):
            mw = QFrame()
            mw.setObjectName("row")
            mh = hbox(mw, (14, 10, 14, 10), 12)
            mv = vbox(spacing=2)
            mv.addWidget(label(tr(title), "rowTitle"))
            mv.addWidget(label(tr(desc, gpu=self.gpu), "desc", wrap=True))
            self.layer_lbl[kind] = label("", "muted")
            mv.addWidget(self.layer_lbl[kind])
            mh.addLayout(mv, 1)
            self.layer_btn[kind] = button("", None, lambda k=kind: self.get_layer(k))
            mh.addWidget(self.layer_btn[kind], 0, Qt.AlignmentFlag.AlignVCenter)
            v.addWidget(mw)
        self.sync_layers()

        # аналізатори: PCIe і пам'ять під навантаженням, кеш шейдерів
        ah = hbox(margins=(14, 10, 14, 2), spacing=10)
        av = vbox(spacing=1)
        av.addWidget(label(tr("gd.title"), "h3"))
        av.addWidget(label(tr("gd.sub"), "desc", wrap=True))
        ah.addLayout(av, 1)
        self.btn_measure = button(tr("gd.measure"), "ghost", self.measure)
        ah.addWidget(self.btn_measure, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(ah)
        self.link_box = vbox(spacing=2)
        v.addLayout(self.link_box)
        sh = hbox(margins=(14, 10, 14, 2), spacing=8)
        sv = vbox(spacing=1)
        sv.addWidget(label(tr("sc.title"), "h3"))
        self.sc_lbl = label(tr("sc.wait"), "desc", wrap=True)
        sv.addWidget(self.sc_lbl)
        sh.addLayout(sv, 1)
        self.btn_sc_clear = button(tr("sc.clear"), "ghost", self.shader_clear)
        self.btn_sc_restore = button(tr("sc.restore"), "ghost", self.shader_restore)
        sh.addWidget(self.btn_sc_clear, 0, Qt.AlignmentFlag.AlignTop)
        sh.addWidget(self.btn_sc_restore, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(sh)
        self.sc_box = vbox(spacing=2)
        v.addLayout(self.sc_box)

        self.sync_fso()
        self.show_probe(F.CFG["gpu_probe"] if isinstance(F.CFG["gpu_probe"], dict) else None)
        # стан без змін: які ігри є і що з ними вже зроблено (пошук іде у фоні — exe ігор бувають великі)
        self.main.run_quick(tr("mg.title", gpu=self.gpu), lambda log, p: {"list": MG.discover()}, silent=True,
                            on_done=self._listed)
        self.probe(False)
        self.shader_scan()

    # ── сумісність зі старими викликами ──
    @property
    def btn_mesa(self):
        return self.layer_btn["mesa"]

    def sync_mesa(self):
        self.sync_layers()

    def get_mesa(self):
        self.get_layer("mesa")

    # ── загальне ──
    def _switch(self, key: str, on: bool):
        m = dict(F.CFG["mining"] or {})
        m[key] = on
        F.CFG["mining"] = m
        if key == "auto" and on:
            MG.mark_scan(F.CFG)  # інакше фонова перевірка за мить запустила б той самий пошук удруге
            self.scan()

    def _busy(self, res) -> bool:
        if isinstance(res, dict) and res.get("busy"):
            self.main.toast(tr("mg.busy").strip(), "warn")
            return True
        return False

    def find_row(self, exe: str):
        exe = (exe or "").lower()
        return next((r for r in self.rows for x in r.g["exes"] if ntpath.basename(x["path"]).lower() == exe), None)

    # ── перевірка DirectX / Vulkan і аналізатор драйвера ──
    def probe(self, force: bool):
        busy = self.btn_probe if force else None
        self.main.run_quick(tr("gr.title"), lambda log, p: GI.probe(force), busy=busy, silent=True,
                            on_done=lambda r: self.show_probe(r if isinstance(r, dict) else None))

    def show_probe(self, pr):
        clear_layout(self.drv_box)
        if not pr:
            return
        rep = GD.driver_report(self.hw, pr)
        s = GI.summary(pr)
        if s.get("gpu"):
            self.probe_lbl.setText(tr("gr.probe", model=rep["model"] or self.gpu, name=s["gpu"],
                                      driver=s.get("driver") or "?",
                                      dx12=tr("gr.yes") if s.get("dx12") else tr("gr.no") if s.get("dx12") is False
                                      else "?",
                                      vk=s.get("vk_api") or tr("gr.no"), display=s.get("display") or "?",
                                      when=when(pr.get("ts"))))
        else:
            self.probe_lbl.setText(tr("gr.probe_none", when=when(pr.get("ts"))))
        for level, key, kw in rep["rows"]:
            if level == "ok":
                continue  # зелене вже сказано в рядку вище
            self.drv_box.addWidget(info_row(level, tr(f"gd.{key}.t", **kw), tr(f"gd.{key}.d", **kw)))
        self.refresh_rows()

    def sync_fso(self):
        clear_layout(self.fso_box)
        if E.JOURNAL.has("fso_global"):
            b = button(tr("gr.fso_btn"), None, self.revert_fso)
            self.fso_box.addWidget(info_row("warn", tr("gr.fso_t"), tr("gr.fso_d", gpu=self.gpu), b))

    def revert_fso(self):
        if not Ask.ask(self, tr("gr.fso_t"), tr("gr.fso_q"), tr("gr.fso_btn")):
            return
        self.main.run_quick(tr("gr.fso_t"), lambda log, p: E.undo_ids(["fso_global"], log), silent=True,
                            on_done=lambda _r: (self.sync_fso(), self.main.toast(tr("gr.fso_done"))))

    def _gl_driver(self, i: int):
        drv = "zink" if i == 1 else "d3d12"
        if drv == MG.gl_driver():
            return
        if drv == "zink" and not Ask.ask(self, tr("gr.gl_t"), tr("gr.zink_q", gpu=self.gpu), tr("gr.gl_zink")):
            self.gl_seg.select(0)
            return
        self.main.run_quick(tr("gr.gl_t"), lambda log, p: MG.set_gl_driver(drv, log), silent=True,
                            on_done=lambda r: self._busy(r) or self.refresh_rows())

    # ── список ігор ──
    def sync_layers(self):
        for kind, lbl in self.layer_lbl.items():
            info = MG.layer_info(kind)
            what = MG.LAYER_NAMES[kind]
            lbl.setText(tr("mg.have", what=what, v=info["version"]) if info else tr("mg.none", what=what))
            if kind == "dxvk" and info and not any("d3d11.dll" in (f or {}) for f in info["arch"].values()):
                lbl.setText(lbl.text() + " " + tr("gr.dxvk_old"))
            self.layer_btn[kind].setText(tr("mg.got", what=what) if info else tr("mg.get", what=what))
            self.layer_btn[kind].setEnabled(not info or (kind == "dxvk" and not any(
                "d3d11.dll" in (f or {}) for f in info["arch"].values())))

    def _listed(self, res):
        games = (res or {}).get("list") if isinstance(res, dict) else None
        if games is None:
            return
        self.games = games
        clear_layout(self.list_box)
        self.rows = []
        for g in games:
            row = MiningGameRow(g, self)
            self.list_box.addWidget(row)
            self.rows.append(row)
        self.empty.setText(tr("mg.empty") if games or not res.get("scanned") else tr("mg.none_found"))
        self.empty.setVisible(not games)

    def refresh_rows(self):
        for row in self.rows:
            try:
                row.sync()
            except RuntimeError:
                pass

    def scan(self):
        hw = self.hw

        def job(log, p):
            games = MG.discover()
            MG.new_games(games)
            import library as LB
            LB.refresh(games)
            res = MG.assign(log, hw, games)
            if not res.get("busy"):
                res.update(list=games, scanned=True)
            return res

        def done(res):
            if self._busy(res):
                return
            self._listed(res)
            if isinstance(res, dict) and not res.get("error"):
                self.main.toast(tr("mg.done", gpu=self.gpu, n=res.get("assigned", 0) + res.get("already", 0)))
        self.main.run_quick(tr("mg.scan"), job, busy=self.btn_scan, on_done=done, silent=True)

    def revert(self):
        if not Ask.ask(self, tr("mg.revert"), tr("mg.revert_q"), tr("mg.revert"), "danger"):
            return
        self.main.run_quick(tr("mg.revert"), lambda log, p: MG.revert(log), busy=self.btn_revert, silent=True,
                            on_done=lambda r: self._busy(r) or (self.refresh_rows(), self.main.toast(tr("mg.reverted"))))

    def get_layer(self, kind: str):
        what = MG.LAYER_NAMES[kind]
        self.main.run_quick(tr("mg.get", what=what), lambda log, p: MG.install_layer(kind, log, p),
                            busy=self.layer_btn[kind],
                            on_done=lambda _r: (self.sync_layers(), self.refresh_rows(),
                                                self.main.pages["bench"].sync_mesa()))

    # ── режим рендерингу гри ──
    def mode_menu(self, row: MiningGameRow):
        g = row.g
        cur = MG.current_mode(g)
        rec = MG.recommend(g)["mode"]
        bad = set(DB.lookup(g).get("bad") or [])
        m = QMenu(self)
        for mode in MG.MODES:
            p = MG.plan(g, mode)
            text = tr(f"mg.mode.{mode}")
            if mode == rec:
                text += "  · " + tr("gr.recommended")
            if mode in bad:
                text += "  · " + tr("gr.marked_bad")
            if p["blocked"]:
                text += "  · " + tr("gr.limited")
            a = m.addAction(("✓  " if mode == cur else "    ") + text)
            a.setToolTip(tr(f"mg.mode.{mode}.d"))
            a.triggered.connect(lambda _=False, md=mode: self.choose_mode(row, md))
        m.setToolTipsVisible(True)
        m.exec(row.btn_mode.mapToGlobal(row.btn_mode.rect().bottomLeft()))
        self.menu = m

    def describe_plan(self, g: dict, mode: str) -> str:
        p = MG.plan(g, mode)
        lines = [tr(f"mg.mode.{mode}.d")]
        if mode == "original":
            lines.append(tr("gr.plan.original"))
        if p["gpu"]:
            lines.append(tr("gr.plan.gpu", n=len(p["gpu"]), gpu=self.gpu))
        for d, (a, names) in p["dxvk"].items():
            lines.append(tr("gr.plan.dxvk", folder=d, arch=a, files=", ".join(names)))
        for d, a in p["mesa"].items():
            lines.append(tr("gr.plan.mesa", folder=d, arch=a, drv=tr("gr.gl_zink") if MG.gl_driver() == "zink"
                            else tr("gr.gl_d3d12")))
        for kind, why in p["blocked"]:
            lines.append(tr("gr.plan.blocked", what=MG.LAYER_NAMES[kind],
                            why="; ".join(tr(f"mg.why.{w}") for w in why)))
        known = DB.lookup(g)
        for n in known.get("notes") or []:
            lines.append("• " + tr(f"db.note.{n}"))
        if known.get("online") and (p["dxvk"] or p["mesa"]):
            lines.append("⚠ " + tr("gr.plan.online"))
        if p["dxvk"] or p["mesa"]:
            lines.append(tr("gr.plan.backup"))
        return "\n\n".join(lines)

    def choose_mode(self, row: MiningGameRow, mode: str):
        g = row.g  # той самий режим теж можна застосувати повторно: нові exe після оновлення гри
        kind = "danger" if mode == "original" else "primary"
        if not Ask.ask(self, tr("gr.mode_q", game=g["name"], mode=tr(f"mg.mode.{mode}")), self.describe_plan(g, mode),
                       tr("btn.apply"), kind):
            return
        hw = self.hw

        def done(res):
            if self._busy(res):
                return
            self.refresh_rows()
            if isinstance(res, dict) and res.get("rolled_back"):
                self.main.toast(tr("gr.mode_rolled", game=g["name"]), "bad")
            elif isinstance(res, dict):
                self.main.toast(tr("gr.mode_done", game=g["name"], mode=tr(f"mg.mode.{mode}")))
        self.main.run_quick(g["name"], lambda log, p: MG.apply_mode(g, mode, log, hw), busy=row.btn_mode,
                            on_done=done, silent=True)

    def check_game(self, row: MiningGameRow):
        g = row.g
        exes = {ntpath.basename(x["path"]) for x in g["exes"]}
        if E.IS_WIN and not GI.pids_of(exes):
            Ask.info(self, tr("gr.check_t", game=g["name"]), tr("gr.check_run", game=g["name"]))
            return

        def job(log, p):
            luid = GI.summary(GI.probe()).get("luid") or ""
            log(tr("gr.checking", game=g["name"]))
            res = GI.check(exes, luid, 6, should_stop=E.CANCEL.is_set, game_dir=g["dir"])
            if res.get("verdict") in ("mining", "igpu", "warp"):
                MG.record_check(g, res)
            log("  " + GI.explain(res, self.gpu) + (f" ({res['path_text']})" if res.get("path_text") else ""))
            return res

        def done(res):
            if not isinstance(res, dict):
                return
            self.refresh_rows()
            v = res.get("verdict")
            text = GI.explain(res, self.gpu)
            if res.get("path_text"):
                text += "\n\n" + tr("gr.path", path=res["path_text"])
            if v in ("igpu", "warp"):
                rec = MG.recommend(g)
                text += "\n\n" + tr("gr.fix_hint", mode=tr(f"mg.mode.{rec['mode']}"))
            Ask.info(self, tr("gr.check_t", game=g["name"]), text)
        self.main.run_quick(tr("gr.check_t", game=g["name"]), job, busy=row.btn_check, on_done=done, silent=True)

    def more_menu(self, row: MiningGameRow):
        g = row.g
        mode = MG.current_mode(g)
        m = QMenu(self)
        m.addAction(tr("gr.rate_ok", mode=tr(f"mg.mode.{mode}"))).triggered.connect(
            lambda: (DB.rate(g, mode, "ok"), self.refresh_rows(), self.main.toast(tr("gr.rated"))))
        m.addAction(tr("gr.rate_bad", mode=tr(f"mg.mode.{mode}"))).triggered.connect(lambda: self.rate_bad(row))
        known = DB.lookup(g)
        if known.get("params"):
            m.addAction(tr("gr.params", p=known["params"])).triggered.connect(lambda: self.copy_params(known["params"]))
        m.addSeparator()
        m.addAction(tr("gr.reset")).triggered.connect(lambda: self.reset_game(row))
        m.exec(row.btn_more.mapToGlobal(row.btn_more.rect().bottomLeft()))
        self.menu = m

    def copy_params(self, params: str):
        QGuiApplication.clipboard().setText(params)
        self.main.toast(tr("gr.params_copied", p=params))

    def rate_bad(self, row: MiningGameRow):
        """Гра не запускається / зависає в цьому режимі: позначаємо й повертаємо попередній режим (з підтвердженням)."""
        g = row.g
        mode = MG.current_mode(g)
        prev = MG.profile(g).get("prev") or ("native" if mode != "native" else "original")
        DB.rate(g, mode, "bad")
        if not Ask.ask(self, tr("gr.rate_bad", mode=tr(f"mg.mode.{mode}")),
                       tr("gr.back_q", game=g["name"], mode=tr(f"mg.mode.{prev}")), tr("btn.apply")):
            self.refresh_rows()
            return
        hw = self.hw
        self.main.run_quick(g["name"], lambda log, p: MG.apply_mode(g, prev, log, hw), busy=row.btn_more, silent=True,
                            on_done=lambda r: self._busy(r) or self.refresh_rows())

    def reset_game(self, row: MiningGameRow):
        g = row.g
        if not Ask.ask(self, tr("gr.reset"), tr("gr.reset_q", game=g["name"]), tr("gr.reset"), "danger"):
            return
        self.main.run_quick(g["name"], lambda log, p: MG.reset_game(g, log), busy=row.btn_more, silent=True,
                            on_done=lambda r: self._busy(r) or self.refresh_rows())

    # ── власні профілі ──
    def export_profiles(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("gr.export"), "optimax-games.json", "JSON (*.json)")
        if path:
            try:
                n = DB.export_profiles(path)
                self.main.toast(tr("gr.exported", n=n))
            except OSError as e:
                self.main.toast(str(e), "bad")

    def import_profiles(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("gr.import"), "", "JSON (*.json)")
        if path:
            try:
                n = DB.import_profiles(path)
                self.refresh_rows()
                self.main.toast(tr("gr.imported", n=n))
            except (OSError, ValueError) as e:
                self.main.toast(tr("gr.import_bad", err=str(e)[:80]), "bad")

    # ── аналізатори ──
    def measure(self):
        """10 секунд показників NVML (краще — коли гра запущена): лінія PCIe під навантаженням і відеопам'ять."""
        def job(log, p):
            nv = []
            if not E.IS_WIN:
                return {"nv": [dict(util=88, pcie_gen=1, pcie_width=4, pcie_max_gen=1, pcie_max_width=4,
                                    pcie_tx=450 * 1024, pcie_rx=300 * 1024, vram_used=5400, vram_total=6144, temp=67,
                                    power=105.0, clock=1708)] * 10}
            import gpubench as GB
            n = GB.Nvml()
            if not n.ok():
                return {"nv": [], "error": "nvml"}
            try:
                for i in range(10):
                    if E.CANCEL.is_set():
                        break
                    p(i, 10, tr("gd.measuring", s=10 - i))
                    nv.append(n.read())
                    time.sleep(1.0)
            finally:
                n.close()
            return {"nv": nv}
        self.main.run_quick(tr("gd.title"), job, busy=self.btn_measure, silent=True, on_done=self.show_measure)

    def show_measure(self, res):
        clear_layout(self.link_box)
        nv = (res or {}).get("nv") if isinstance(res, dict) else None
        if not nv:
            self.link_box.addWidget(info_row("warn", tr("gd.no_nvml")))
            return
        last = nv[-1]
        ev = GD.pcie_eval(nv)
        if ev:
            lvl = "ok" if ev.get("n") else "info"
            desc = tr("gd.pcie_d", gen=ev.get("load_gen") or ev.get("gen") or "?",
                      width=ev.get("load_width") or ev.get("width") or "?", mgen=ev.get("max_gen") or "?",
                      mwidth=ev.get("max_width") or "?", mbps=ev.get("avg_mbps", 0), link=ev.get("link_mbps", 0),
                      share=ev.get("share", 0)) if ev.get("n") else tr("gd.pcie_idle", gen=ev.get("gen") or "?",
                                                                       width=ev.get("width") or "?",
                                                                       mgen=ev.get("max_gen") or "?",
                                                                       mwidth=ev.get("max_width") or "?")
            self.link_box.addWidget(info_row(lvl, tr("gd.pcie_t"), desc))
        for f in GD.pcie_findings(ev, self.hw) + GD.memory_findings(nv, {}, self.hw):
            self.link_box.addWidget(info_row(f["level"], tr(f"diag.f.{f['key']}.t", **f["kw"]),
                                             tr(f"diag.f.{f['key']}.d", **f["kw"])))
        if last.get("vram_total"):
            self.link_box.addWidget(info_row("info", tr("gd.mem_t"), tr(
                "gd.mem_d", used=f"{(last.get('vram_used') or 0) / 1024:.1f}", total=f"{last['vram_total'] / 1024:.1f}",
                temp=last.get("temp", "—"), clock=last.get("clock", "—"), power=last.get("power", "—"))))

    def shader_scan(self):
        def job(log, p):
            pr = F.CFG["gpu_probe"] if isinstance(F.CFG["gpu_probe"], dict) else {}
            return GD.shader_scan(GI.summary(pr).get("driver") or "")
        self.main.run_quick(tr("sc.title"), job, silent=True, on_done=self.show_shader)

    def show_shader(self, scan):
        if not isinstance(scan, dict) or "caches" not in scan:
            return
        clear_layout(self.sc_box)
        self.sc_lbl.setText(tr("sc.summary", mb=f"{scan['total'] / 2**20:.0f}", n=len(scan["caches"])))
        for level, key, kw in GD.shader_advice(scan):
            self.sc_box.addWidget(info_row(level, tr(f"sc.a.{key}.t", **kw), tr(f"sc.a.{key}.d", **kw)))
        b = scan.get("backup") or {}
        self.btn_sc_restore.setEnabled(bool(b))
        self.btn_sc_restore.setToolTip(tr("sc.backup", when=when(b.get("ts")), mb=f"{b.get('size', 0) / 2**20:.0f}")
                                       if b else "")

    def shader_clear(self):
        if not Ask.ask(self, tr("sc.clear"), tr("sc.clear_q"), tr("sc.clear")):
            return
        self.main.run_quick(tr("sc.clear"), lambda log, p: GD.shader_backup_clear(log), busy=self.btn_sc_clear,
                            silent=True, on_done=lambda _r: self.shader_scan())

    def shader_restore(self):
        if not Ask.ask(self, tr("sc.restore"), tr("sc.restore_q"), tr("sc.restore")):
            return
        self.main.run_quick(tr("sc.restore"), lambda log, p: GD.shader_restore(log), busy=self.btn_sc_restore,
                            silent=True, on_done=lambda _r: self.shader_scan())
