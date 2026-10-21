"""
OptimaX — нові сторінки: Діагностика («Чому лагає?», тест FPS, звіт), Мережа (DNS, пінг, bufferbloat),
Програми (оновлення та встановлення через winget), а також вкладки «Що займає місце» і «Старі драйвери».
"""
from __future__ import annotations

import ntpath
import os
import subprocess
import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QGridLayout, QProgressBar, QMenu, QLineEdit, QFileDialog

import apps as A
import engine as E
import features as F
import fpstest as FT
import monitor as M
import netlab as N
import report as RP
from i18n import tr
from ui_kit import (T, label, button, card, vbox, hbox, badge, style_badge, dot, scroller, page_header, clear_layout,
                    section_card, Switch, Check, Segmented, chip, Ask, RunDialog, LogView, Spark, Worker, LOG)

LEVEL_COLOR = {"bad": "bad", "warn": "warn", "info": "acc", "ok": "ok"}


def page_body(margins=(32, 4, 32, 24), spacing=14):
    body = QWidget()
    return body, vbox(body, margins, spacing)


def log_strip(outer, height: int = 100):
    lw = QWidget()
    lv = vbox(lw, (32, 4, 32, 16), 6)
    lv.addWidget(label(tr("log.title"), "muted"))
    lv.addWidget(LogView(height))
    outer.addWidget(lw)


class Busy:
    """Прогрес фонової задачі всередині картки: підпис, смужка і кнопка «Зупинити»."""

    def __init__(self, main, lay, margins=(14, 4, 14, 6)):
        self.main = main
        self.box = QWidget()
        v = vbox(self.box, margins, 6)
        top = hbox(spacing=10)
        self.lbl = label("", "desc", wrap=True)
        top.addWidget(self.lbl, 1)
        self.btn = button(tr("run.stop"), "ghost", self.stop)
        top.addWidget(self.btn)
        v.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        v.addWidget(self.bar)
        self.box.hide()
        lay.addWidget(self.box)
        self.worker = None

    @property
    def running(self) -> bool:
        return self.worker is not None

    def start(self, job, on_done, text: str) -> bool:
        if self.worker is not None:
            self.main.toast(tr("busy.wait"), "warn")
            return False
        E.CANCEL.clear()
        self.lbl.setText(text)
        self.bar.setRange(0, 0)
        self.box.show()
        w = Worker(job)
        self.worker = w
        w.log.connect(LOG.write)
        w.progress.connect(self._progress)
        w.result.connect(lambda res: self._done(res, on_done))
        self.main._workers.add(w)
        w.finished.connect(lambda: self.main._workers.discard(w))
        w.start()
        return True

    def _progress(self, i: int, total: int, text: str):
        if total:
            self.bar.setRange(0, total)
            self.bar.setValue(min(i, total))
        if text:
            self.lbl.setText(text)

    def _done(self, res, cb):
        self.worker = None
        self.box.hide()
        if isinstance(res, dict) and res.get("error"):
            self.main.toast(tr("toast.failed", what=res["error"][:80]), "bad")
        cb(res)

    def stop(self):
        E.CANCEL.set()
        self.lbl.setText(tr("run.stopping_text"))


def finding_row(main, f: dict) -> QFrame:
    row = QFrame()
    row.setObjectName("row")
    h = hbox(row, (14, 10, 14, 10), 12)
    h.addWidget(dot(T[LEVEL_COLOR[f["level"]]], 10), 0, Qt.AlignmentFlag.AlignTop)
    v = vbox(spacing=2)
    v.addWidget(label(tr(f"diag.f.{f['key']}.t", **f.get("kw", {})), "rowTitle", wrap=True))
    v.addWidget(label(tr(f"diag.f.{f['key']}.d", **f.get("kw", {})), "desc", wrap=True))
    h.addLayout(v, 1)
    fix = f.get("fix")
    if fix:
        kind, val = fix
        b = button(tr(f"fix.{kind}"))
        b.clicked.connect(lambda _=False: main.do_fix(kind, val, b))
        h.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


def stat_cell(grid: QGridLayout, i: int, caption: str, value: str, cols: int = 4):
    w = QWidget()
    v = vbox(w, spacing=1)
    v.addWidget(label(caption, "muted"))
    v.addWidget(label(value, "value"))
    grid.addWidget(w, i // cols, i % cols)


# ───────────────────────── Діагностика ─────────────────────────
class DiagnosePage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.diagnose"), tr("diag.sub")))
        body, v = page_body()

        # «Чому лагає?»
        dc = card("cardAccent")
        dv = vbox(dc, (24, 20, 24, 20), 12)
        dv.addWidget(label(tr("diag.title"), "h1"))
        dv.addWidget(label(tr("diag.text"), "sub", wrap=True))
        steps = hbox(spacing=18)
        for i in (1, 2, 3):
            s = hbox(spacing=8)
            num = label(str(i), "stepNum")
            num.setFixedSize(24, 24)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.addWidget(num)
            s.addWidget(label(tr(f"diag.step{i}"), "desc", wrap=True), 1)
            steps.addLayout(s, 1)
        dv.addLayout(steps)
        row = hbox(spacing=10)
        row.addWidget(label(tr("diag.duration"), "desc"))
        self.dur = Segmented([tr("u.sec_n", n=30), tr("u.sec_n", n=60), tr("u.sec_n", n=120)])
        self.dur.select(1)
        self.dur_i = 1
        self.dur.changed.connect(lambda i: setattr(self, "dur_i", i))
        row.addWidget(self.dur)
        row.addStretch()
        self.btn_diag = button(tr("diag.start"), "primary", self.start_diag)
        row.addWidget(self.btn_diag)
        dv.addLayout(row)
        self.busy_diag = Busy(main, dv, (0, 4, 0, 0))
        v.addWidget(dc)
        self.res_card, rv = section_card(tr("diag.result"), "")
        self.res_head = label("", "desc", wrap=True)
        self.res_head.setContentsMargins(14, 0, 14, 4)
        rv.addWidget(self.res_head)
        self.res_box = vbox(spacing=2)
        rv.addLayout(self.res_box)
        self.stat_grid = QGridLayout()
        self.stat_grid.setContentsMargins(14, 8, 14, 8)
        self.stat_grid.setHorizontalSpacing(18)
        self.stat_grid.setVerticalSpacing(10)
        rv.addLayout(self.stat_grid)
        self.res_card.hide()
        v.addWidget(self.res_card)

        # тест FPS
        fc, fv = section_card(tr("fps.title"), tr("fps.sub"))
        self.pm_line = hbox(margins=(14, 0, 14, 4), spacing=10)
        self.pm_state = label("", "desc", wrap=True)
        self.pm_line.addWidget(self.pm_state, 1)
        self.btn_pm = button(tr("fps.get_pm"), None, self.get_pm)
        self.pm_line.addWidget(self.btn_pm)
        fv.addLayout(self.pm_line)
        g = hbox(margins=(14, 4, 14, 4), spacing=10)
        self.btn_game = button(tr("fps.pick_game"), None, self.pick_game)
        g.addWidget(self.btn_game)
        self.fdur = Segmented([tr("u.sec_n", n=30), tr("u.sec_n", n=60)])
        self.fdur_i = 0
        self.fdur.changed.connect(lambda i: setattr(self, "fdur_i", i))
        g.addWidget(self.fdur)
        g.addStretch()
        self.btn_before = button(tr("fps.run_before"), None, lambda: self.run_fps("before"))
        self.btn_after = button(tr("fps.run_after"), "primary", lambda: self.run_fps("after"))
        g.addWidget(self.btn_before)
        g.addWidget(self.btn_after)
        fv.addLayout(g)
        self.busy_fps = Busy(main, fv)
        self.fps_grid = QGridLayout()
        self.fps_grid.setContentsMargins(14, 6, 14, 6)
        self.fps_grid.setHorizontalSpacing(24)
        self.fps_grid.setVerticalSpacing(6)
        fv.addLayout(self.fps_grid)
        self.chart = Spark(130)
        ch = hbox(margins=(14, 2, 14, 4))
        ch.addWidget(self.chart)
        fv.addLayout(ch)
        self.legend = label("", "muted")
        self.legend.setContentsMargins(14, 0, 14, 0)
        fv.addWidget(self.legend)
        vr = hbox(margins=(14, 6, 14, 8), spacing=10)
        self.verdict = label("", "h3", wrap=True)
        vr.addWidget(self.verdict, 1)
        self.btn_revert = button(tr("fps.revert"), "danger", self.revert_between)
        self.btn_revert.hide()
        vr.addWidget(self.btn_revert)
        fv.addLayout(vr)
        v.addWidget(fc)

        # звіт
        rc = card()
        rcv = vbox(rc, (22, 18, 22, 18), 8)
        rcv.addWidget(label(tr("rep.card"), "h2"))
        rcv.addWidget(label(tr("rep.card_d"), "desc", wrap=True))
        rh = hbox(spacing=8)
        rh.addWidget(button(tr("rep.save"), None, self.save_report))
        rh.addWidget(button(tr("rep.copy"), None, self.copy_report))
        rh.addStretch()
        rcv.addLayout(rh)
        v.addWidget(rc)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        log_strip(outer)
        self.game = None
        if F.CFG["diag_last"]:
            self.show_result(F.CFG["diag_last"])
        self.refresh_fps()

    # ── «Чому лагає?» ──
    def start_diag(self):
        secs = (30, 60, 120)[self.dur_i]
        hw = self.main.hw or {}
        import hardware as H

        def job(log, prog):
            log(f"[►] {tr('diag.title')}")
            return M.lag_diagnosis(hw, secs, log, prog, gpu_temp=H.gpu_temp)
        self.busy_diag.start(job, self._diag_done, tr("diag.collecting", s=secs))

    def _diag_done(self, res):
        if not isinstance(res, dict) or "findings" not in res:
            return
        F.CFG["diag_last"] = res
        self.show_result(res)
        self.main.toast(tr("diag.ready"))

    def show_result(self, res: dict):
        self.res_card.show()
        st = res.get("stats", {})
        self.res_head.setText(tr("diag.head", game=res.get("game") or tr("diag.game_unknown"), n=res.get("n", 0)))
        clear_layout(self.res_box)
        for f in res.get("findings", []):
            self.res_box.addWidget(finding_row(self.main, f))
        clear_layout(self.stat_grid)
        fmt = lambda v, u="%": "—" if v is None else f"{v:.0f}{u}"  # noqa: E731
        cells = [(tr("diag.s.cpu"), fmt(st.get("cpu"))), (tr("diag.s.core"), fmt(st.get("core_max"))),
                 (tr("diag.s.gpu"), fmt(st.get("gpu"))),
                 (tr("diag.s.ram"), "—" if st.get("avail_mb") is None else tr("u.gb", v=f"{st['avail_mb'] / 1024:.1f}")),
                 (tr("diag.s.vram"), "—" if not st.get("vram_used") else
                  f"{st['vram_used']:.1f} / {st.get('vram_total') or '?'} GB"),
                 (tr("diag.s.disk"), fmt(st.get("disk"))), (tr("diag.s.temp"), fmt(st.get("temp_max"), "°C")),
                 (tr("diag.s.gpu_t"), fmt(st.get("gpu_t_max"), "°C"))]
        for i, (c, val) in enumerate(cells):
            stat_cell(self.stat_grid, i, c, val)
        top = st.get("top_bg") or []
        if top:
            stat_cell(self.stat_grid, len(cells), tr("diag.s.bg"), ", ".join(f"{n} {p:.0f}%" for n, p in top[:3]), 4)

    # ── тест FPS ──
    def refresh_fps(self):
        pm = FT.find_presentmon()
        self.pm_state.setText(tr("fps.pm_ok") if pm else tr("fps.pm_missing"))
        self.btn_pm.setVisible(not pm)
        for b in (self.btn_before, self.btn_after):
            b.setEnabled(bool(pm and self.game))
        self.btn_game.setText(tr("fps.game", name=F.game_name(self.game)) if self.game else tr("fps.pick_game"))
        clear_layout(self.fps_grid)
        t = (F.CFG["fps_tests"] or {}).get((self.game or "").lower(), {}) if self.game else {}
        b, a = t.get("before"), t.get("after")
        heads = ("", tr("fps.before"), tr("fps.after"))
        for j, h in enumerate(heads):
            self.fps_grid.addWidget(label(h, "muted"), 0, j)
        rows = [("avg", tr("fps.avg")), ("low1", "1% low"), ("low01", "0.1% low"), ("stutters", tr("fps.stutters"))]
        for i, (k, cap) in enumerate(rows, 1):
            self.fps_grid.addWidget(label(cap, "desc"), i, 0)
            for j, r in enumerate((b, a), 1):
                self.fps_grid.addWidget(label("—" if not r else str(r.get(k, "—")), "rowTitle"), i, j)
        self.fps_grid.setColumnStretch(3, 1)
        self.chart.set_series([(b.get("series", []) if b else [], T["mute"]), (a.get("series", []) if a else [],
                                                                               T["acc"])])
        self.legend.setText(tr("fps.legend") if (a or b) else "")
        cmp_ = FT.compare(b, a)
        self.btn_revert.hide()
        if cmp_:
            col = {"better": T["ok"], "same": T["sub"], "worse": T["bad"]}[cmp_["verdict"]]
            self.verdict.setText(tr(f"fps.v.{cmp_['verdict']}", avg=f"{cmp_['d_avg']:+.1f}", low=f"{cmp_['d_low']:+.1f}"))
            self.verdict.setStyleSheet(f"color:{col};")
            if cmp_["verdict"] == "worse" and FT.changes_between(b["ts"], a["ts"]):
                self.btn_revert.show()
        else:
            self.verdict.setText(tr("fps.hint") if self.game else "")
            self.verdict.setStyleSheet("")

    def get_pm(self):
        if not Ask.ask(self, tr("fps.get_pm"), tr("fps.get_pm_q"), tr("fps.download")):
            return

        def done(res):
            if isinstance(res, str):
                self.main.toast(tr("fps.downloaded"))
            elif isinstance(res, dict) and res.get("error"):
                if Ask.ask(self, tr("fps.dl_fail_t"), tr("fps.dl_fail_d"), tr("fps.open_page")):
                    webbrowser.open(FT.RELEASES_PAGE)
            self.refresh_fps()
        self.main.run_quick("PresentMon", lambda log, p: FT.download_presentmon(log), busy=self.btn_pm, on_done=done,
                            silent=True)

    def pick_game(self):
        m = QMenu(self)
        seen = set()
        for g in F.CFG["games"] or []:
            seen.add(g["path"].lower())
            m.addAction(F.game_name(g["path"])).triggered.connect(lambda _=False, p=g["path"]: self._set_game(p))
        run = [(n, p) for n, p in F.running_apps() if p.lower() not in seen]
        if run:
            m.addSeparator()
            for name, path in run[:25]:
                m.addAction(f"{name}    {path}").triggered.connect(lambda _=False, p=path: self._set_game(p))
        if not (F.CFG["games"] or run):
            Ask.info(self, tr("games.running_none_t"), tr("fps.no_games"))
            return
        m.exec(self.btn_game.mapToGlobal(self.btn_game.rect().bottomLeft()))
        self.menu = m

    def _set_game(self, path: str):
        self.game = path
        self.refresh_fps()

    def run_fps(self, which: str):
        if not self.game:
            return
        exe = ntpath.basename(self.game)
        secs = (30, 60)[self.fdur_i]
        if not Ask.ask(self, tr(f"fps.run_{which}"), tr("fps.run_q", game=F.game_name(self.game), s=secs),
                       tr("fps.start")):
            return

        def job(log, prog):
            log(f"[►] {tr('fps.title')}: {exe} ({tr('fps.' + which)})")
            return FT.capture(exe, secs, log, prog)

        def done(res):
            if isinstance(res, dict) and res.get("avg"):
                tests = F.CFG["fps_tests"] or {}
                t = tests.setdefault(self.game.lower(), {})
                t[which] = res
                if which == "before":
                    t.pop("after", None)
                F.CFG["fps_tests"] = tests
                self.main.toast(tr("fps.saved", avg=res["avg"]))
            self.refresh_fps()
        self.busy_fps.start(job, done, tr("fps.recording", s=secs))

    def revert_between(self):
        t = (F.CFG["fps_tests"] or {}).get((self.game or "").lower(), {})
        if not (t.get("before") and t.get("after")):
            return
        ids = FT.changes_between(t["before"]["ts"], t["after"]["ts"])
        if not ids or not Ask.ask(self, tr("fps.revert"), tr("fps.revert_q", n=len(ids)), tr("bk.undo"), "danger"):
            return
        RunDialog(self.main, tr("bk.undo_title"), lambda log, prog: E.undo_ids(ids, log, prog)).exec()
        self.main.refresh_all()

    # ── звіт ──
    def _sections(self):
        return RP.sections(self.main.hw, self.main.checks, self.main.analysis)

    def save_report(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("rep.save"), RP.default_name(), "HTML (*.html)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(RP.to_html(self._sections()))
            self.main.toast(tr("rep.saved"))
            if E.IS_WIN:
                os.startfile(path)  # noqa: лише Windows
        except OSError as e:
            Ask.info(self, tr("rep.save"), str(e))

    def copy_report(self):
        QGuiApplication.clipboard().setText(RP.to_text(self._sections()))
        self.main.toast(tr("rep.copied"))


# ───────────────────────── Мережа ─────────────────────────
DEFAULT_REGIONS = ["eu-central-1", "eu-north-1", "eu-west-1", "eu-west-2", "eu-west-3", "eu-south-1"]


def ms_text(v) -> str:
    return "—" if v is None else tr("u.ms", v=f"{v:.0f}")


class NetworkPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.network"), tr("net.sub")))
        body, v = page_body()

        # DNS
        dc, dv = section_card(tr("net.dns.title"), tr("net.dns.sub"))
        r = hbox(margins=(14, 0, 14, 4), spacing=12)
        self.btn_dns = button(tr("net.dns.test"), "primary", self.test_dns)
        r.addWidget(self.btn_dns)
        self.sw_doh = Switch()
        self.sw_doh.set_quiet(True)
        r.addWidget(self.sw_doh)
        r.addWidget(label(tr("net.dns.doh"), "desc", wrap=True), 1)
        self.btn_dns_undo = button(tr("net.dns.restore"), "ghost", self.restore_dns)
        r.addWidget(self.btn_dns_undo)
        dv.addLayout(r)
        self.busy_dns = Busy(main, dv)
        self.dns_box = vbox(spacing=2)
        dv.addLayout(self.dns_box)
        v.addWidget(dc)

        # пінг
        pc, pv = section_card(tr("net.ping.title"), tr("net.ping.sub"))
        self.region_chips = {}
        rows = [N.REGIONS[:6], N.REGIONS[6:]]
        for part in rows:
            rh = hbox(margins=(14, 2, 14, 2), spacing=6)
            for code in part:
                c = chip(tr(f"net.r.{code}"))
                c.setChecked(code in DEFAULT_REGIONS)
                rh.addWidget(c)
                self.region_chips[code] = c
            rh.addStretch()
            pv.addLayout(rh)
        pr = hbox(margins=(14, 6, 14, 4), spacing=10)
        self.btn_ping = button(tr("net.ping.run"), "primary", self.run_ping)
        pr.addWidget(self.btn_ping)
        pr.addStretch()
        self.host = QLineEdit()
        self.host.setPlaceholderText(tr("net.ping.custom_ph"))
        self.host.setFixedWidth(260)
        pr.addWidget(self.host)
        pr.addWidget(button(tr("net.ping.custom"), None, self.run_custom))
        pv.addLayout(pr)
        self.busy_ping = Busy(main, pv)
        self.ping_box = vbox(spacing=2)
        pv.addLayout(self.ping_box)
        v.addWidget(pc)

        # bufferbloat
        bc, bv = section_card(tr("net.bb.title"), tr("net.bb.sub"))
        br = hbox(margins=(14, 0, 14, 4), spacing=10)
        self.btn_bb = button(tr("net.bb.run"), "primary", self.run_bb)
        br.addWidget(self.btn_bb)
        br.addStretch()
        bv.addLayout(br)
        self.busy_bb = Busy(main, bv)
        self.bb_res = QWidget()
        bh = hbox(self.bb_res, (14, 6, 14, 10), 20)
        self.bb_grade = label("—", "display")
        self.bb_grade.setFixedWidth(84)
        self.bb_grade.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bh.addWidget(self.bb_grade)
        bt = vbox(spacing=4)
        self.bb_line = label("", "rowTitle", wrap=True)
        self.bb_tip = label("", "desc", wrap=True)
        bt.addWidget(self.bb_line)
        bt.addWidget(self.bb_tip)
        bh.addLayout(bt, 1)
        self.bb_res.hide()
        bv.addWidget(self.bb_res)
        v.addWidget(bc)

        tc = card()
        tv = vbox(tc, (22, 16, 22, 16), 6)
        tv.addWidget(label(tr("net.tweaks_t"), "h3"))
        tv.addWidget(label(tr("net.tweaks_d"), "desc", wrap=True))
        tv.addWidget(button(tr("net.tweaks_btn"), "ghost", self.open_tweaks), 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(tc)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        log_strip(outer)
        net = F.CFG["net"] or {}
        if net.get("dns"):
            self.fill_dns(net["dns"])
        if net.get("ping"):
            self.fill_ping(net["ping"])
        if net.get("bb"):
            self.fill_bb(net["bb"])
        self.sync()

    def sync(self):
        self.btn_dns_undo.setVisible(E.JOURNAL.has("dns"))
        win11 = (self.main.hw or {}).get("build", E.win_build()) >= 22000
        self.sw_doh.setEnabled(win11)
        if not win11:
            self.sw_doh.set_quiet(False)

    # ── DNS ──
    def test_dns(self):
        def done(res):
            if isinstance(res, list):
                N.save(F.CFG, "dns", res)
                self.fill_dns(res)
        self.busy_dns.start(lambda log, p: (log(f"[►] {tr('net.dns.title')}"), N.dns_benchmark(log, p))[1], done,
                            tr("net.dns.testing", name="…"))

    def fill_dns(self, res: list):
        clear_layout(self.dns_box)
        best = next((r for r in res if r.get("ms") is not None), None)
        cur_ms = next((r["ms"] for r in res if r["id"] == "current"), None)
        for r in res:
            row = QFrame()
            row.setObjectName("row")
            h = hbox(row, (14, 8, 14, 8), 12)
            tv = vbox(spacing=1)
            top = hbox(spacing=8)
            top.addWidget(label(r["name"], "rowTitle"))
            if r is best:
                top.addWidget(badge(tr("net.dns.best"), "ok"))
            if r["id"] == "current":
                top.addWidget(badge(tr("net.dns.yours"), "muted"))
            top.addStretch()
            tv.addLayout(top)
            tv.addWidget(label(" · ".join(r["ips"]), "muted"))
            h.addLayout(tv, 1)
            ok = r.get("ok", 0)
            h.addWidget(label(ms_text(r.get("ms")), "value"))
            h.addWidget(label(tr("net.dns.ok", pct=round(ok * 100)), "desc"))
            if r["id"] != "current":
                b = button(tr("net.dns.use"), "primary" if r is best else None)
                b.clicked.connect(lambda _=False, rr=r, bb=b: self.use_dns(rr, bb))
                h.addWidget(b)
            self.dns_box.addWidget(row)
        if best and cur_ms and best["id"] != "current":
            note = label(tr("net.dns.gain", name=best["name"], ms=f"{cur_ms - best['ms']:.0f}"), "desc", wrap=True)
            note.setContentsMargins(14, 4, 14, 6)
            self.dns_box.addWidget(note)

    def use_dns(self, r: dict, btn):
        prov = next((p for p in N.DNS_PROVIDERS if p["id"] == r["id"]), None)
        if not prov:
            return
        import adblock as AB
        ab = AB.Backend(F.CFG)
        if ab.mode == "filter":  # DNS-ом керує фільтр реклами — міняємо сервер, куди він пересилає запити
            if prov["id"] in AB.UPSTREAMS:
                self.main.run_quick(prov["name"], lambda log, p: ab.save(upstream=prov["id"]), busy=btn, silent=True)
                self.main.toast(tr("ab.upstream_set", name=prov["name"]))
            else:
                self.main.toast(tr("ab.net_conflict"), "warn")
            return
        t = N.dns_tweak(prov, self.sw_doh.isChecked() and self.sw_doh.isEnabled())
        self.main.run_quick(t.title, lambda log, p: E.apply_tweaks([t], log, header=False), busy=btn,
                            on_done=lambda _r: self.sync(), ok_msg=tr("net.dns.applied", name=prov["name"]))

    def restore_dns(self):
        self.main.run_quick(tr("net.dns.restore"), lambda log, p: E.undo_ids(["dns"], log), busy=self.btn_dns_undo,
                            on_done=lambda _r: self.sync(), ok_msg=tr("net.dns.restored"))

    # ── пінг ──
    def run_ping(self):
        codes = [c for c, ch in self.region_chips.items() if ch.isChecked()]

        def done(res):
            if isinstance(res, list):
                N.save(F.CFG, "ping", res)
                self.fill_ping(res)
        self.busy_ping.start(lambda log, p: (log(f"[►] {tr('net.ping.title')}"), N.ping_regions(codes, log, p))[1],
                             done, tr("net.ping.testing", name="…"))

    def run_custom(self):
        host = self.host.text().strip()
        if not host:
            return

        def done(res):
            if isinstance(res, dict) and "avg" in res:
                cur = [r for r in (F.CFG["net"] or {}).get("ping", []) if r.get("code") != "custom"]
                res["name"] = host
                cur.append(res)
                N.save(F.CFG, "ping", cur)
                self.fill_ping(cur)
        self.busy_ping.start(lambda log, p: N.ping_custom(host, log), done, tr("net.ping.testing", name=host))

    def fill_ping(self, res: list):
        clear_layout(self.ping_box)
        worst = max([r["avg"] for r in res if r.get("avg")] or [1])
        for r in res:
            row = QFrame()
            row.setObjectName("row")
            h = hbox(row, (14, 6, 14, 6), 12)
            name = r.get("name") or tr(f"net.r.{r['code']}")
            nl = label(name + (f"  ·  {tr('net.ping.base')}" if r.get("baseline") else ""), "rowTitle")
            nl.setFixedWidth(260)
            h.addWidget(nl)
            bar = QProgressBar()
            bar.setObjectName("sizebar")
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setRange(0, 1000)
            avg = r.get("avg")
            bar.setValue(int(1000 * (avg or 0) / worst))
            col = T["ok"] if (avg or 999) < 50 else T["warn"] if (avg or 999) < 100 else T["bad"]
            bar.setStyleSheet(f"QProgressBar::chunk {{ background:{col}; border-radius:3px; }}")
            h.addWidget(bar, 1)
            h.addWidget(label(ms_text(avg), "value"))
            h.addWidget(label(tr("net.ping.jl", j=f"{r['jitter']:.0f}" if r.get("jitter") is not None else "—",
                                 l=r.get("loss", 0)), "desc"))
            self.ping_box.addWidget(row)

    # ── bufferbloat ──
    def run_bb(self):
        def done(res):
            if isinstance(res, dict) and res.get("grade"):
                N.save(F.CFG, "bb", res)
                self.fill_bb(res)
        self.busy_bb.start(lambda log, p: (log(f"[►] {tr('net.bb.title')}"), N.bufferbloat(log, p))[1], done,
                           tr("net.bb.idle"))

    def fill_bb(self, r: dict):
        self.bb_res.show()
        g = r["grade"]
        col = T["ok"] if g in ("A+", "A") else T["warn"] if g in ("B", "C") else T["bad"]
        self.bb_grade.setText(g)
        self.bb_grade.setStyleSheet(f"color:{col};")
        self.bb_line.setText(tr("net.bb.line", idle=f"{r['idle']:.0f}", loaded=f"{r['loaded']:.0f}",
                                inc=f"{r['increase']:.0f}", mbps=f"{r['mbps']:.0f}"))
        self.bb_tip.setText(tr("net.bb.tip_good") if g in ("A+", "A") else tr("net.bb.tip_bad"))

    def open_tweaks(self):
        self.main.open_expert()
        self.main.pages["optimize"].expert.set_group("net")


# ───────────────────────── Програми ─────────────────────────
class PickRow(QFrame):
    def __init__(self, title: str, sub: str, tag: str = None, tag_kind: str = "muted", on_toggle=None,
                 wrap: bool = False):
        super().__init__()
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        h = hbox(self, (14, 8, 14, 8), 12)
        self.check = Check()
        if on_toggle:
            self.check.toggled.connect(lambda _: on_toggle())
        h.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)
        v = vbox(spacing=1)
        top = hbox(spacing=8)
        top.addWidget(label(title, "rowTitle"))
        self.tag = badge(tag or "", tag_kind)
        self.tag.setVisible(bool(tag))
        top.addWidget(self.tag)
        top.addStretch()
        v.addLayout(top)
        if sub:
            v.addWidget(label(sub, "muted", wrap=wrap))
        h.addLayout(v, 1)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.check.toggle()
        super().mouseReleaseEvent(e)


class AppsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.apps"), tr("apps.sub")))
        body, v = page_body()
        self.no_wg = QFrame()
        self.no_wg.setObjectName("bannerWarn")
        nv = vbox(self.no_wg, (18, 12, 18, 12), 4)
        nv.addWidget(label(tr("apps.no_winget"), "h3"))
        nv.addWidget(label(tr("apps.no_winget_d"), "desc", wrap=True))
        nv.addWidget(button(tr("apps.get_winget"), "ghost", lambda: webbrowser.open(
            "ms-windows-store://pdp/?productid=9NBLGGH4NNS1")), 0, Qt.AlignmentFlag.AlignLeft)
        self.no_wg.setVisible(not A.winget_path())
        v.addWidget(self.no_wg)

        uc, uv = section_card(tr("apps.upd"), tr("apps.upd_d"))
        ur = hbox(margins=(14, 0, 14, 4), spacing=10)
        self.btn_check = button(tr("apps.check"), "primary", self.check_updates)
        ur.addWidget(self.btn_check)
        ur.addStretch()
        self.upd_count = label("", "desc")
        ur.addWidget(self.upd_count)
        self.btn_upd_sel = button(tr("apps.upd_sel"), None, self.update_selected)
        self.btn_upd_all = button(tr("apps.upd_all"), None, self.update_all)
        for b in (self.btn_upd_sel, self.btn_upd_all):
            b.setEnabled(False)
            ur.addWidget(b)
        uv.addLayout(ur)
        self.busy_upd = Busy(main, uv)
        self.upd_box = vbox(spacing=2)
        uv.addLayout(self.upd_box)
        v.addWidget(uc)

        ic, iv = section_card(tr("apps.inst"), tr("apps.inst_d"))
        self.inst_rows = []
        cols = hbox(margins=(6, 0, 6, 0), spacing=10)
        col_l, col_r = vbox(spacing=2), vbox(spacing=2)
        for n, (cat, items) in enumerate(A.CATALOG):
            col = col_l if n % 2 == 0 else col_r
            cap = label(tr(f"apps.cat.{cat}"), "h3")
            cap.setContentsMargins(8, 8, 8, 2)
            col.addWidget(cap)
            for pkg, name in items:
                r = PickRow(name, pkg, on_toggle=self._count_inst)
                r.pkg, r.name = pkg, name
                col.addWidget(r)
                self.inst_rows.append(r)
        col_l.addStretch()
        col_r.addStretch()
        cols.addLayout(col_l, 1)
        cols.addLayout(col_r, 1)
        iv.addLayout(cols)
        ir = hbox(margins=(14, 8, 14, 6), spacing=10)
        self.inst_state = label(tr("apps.inst_state"), "desc")
        ir.addWidget(self.inst_state, 1)
        self.btn_scan = button(tr("apps.scan"), "ghost", self.scan_installed)
        ir.addWidget(self.btn_scan)
        self.btn_inst = button(tr("apps.install"), "primary", self.install_selected)
        self.btn_inst.setEnabled(False)
        ir.addWidget(self.btn_inst)
        iv.addLayout(ir)
        v.addWidget(ic)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        log_strip(outer)
        self.upd_rows = []
        self.loaded = False

    def on_show(self):
        if not self.loaded:
            self.loaded = True
            self.scan_installed()

    # ── оновлення ──
    def check_updates(self):
        def done(res):
            if isinstance(res, list):
                self.fill_updates(res)
        self.busy_upd.start(lambda log, p: A.list_upgrades(log), done, tr("apps.checking"))

    def fill_updates(self, ups: list):
        clear_layout(self.upd_box)
        self.upd_rows = []
        for u in ups:
            r = PickRow(u["name"], f"{u['id']}   {u['version']} → {u['available']}", on_toggle=self._count_upd)
            r.check.setChecked(True)
            r.u = u
            self.upd_box.addWidget(r)
            self.upd_rows.append(r)
        if not ups:
            lb = label(tr("apps.all_fresh"), "sub")
            lb.setContentsMargins(14, 4, 14, 8)
            self.upd_box.addWidget(lb)
        self.btn_upd_all.setEnabled(bool(ups))
        self._count_upd()

    def _count_upd(self):
        n = sum(r.check.isChecked() for r in self.upd_rows)
        self.upd_count.setText(tr("opt.count", n=n, total=len(self.upd_rows)) if self.upd_rows else "")
        self.btn_upd_sel.setEnabled(n > 0)
        self.btn_upd_sel.setText(tr("apps.upd_sel_n", n=n) if n else tr("apps.upd_sel"))

    def update_selected(self):
        items = [(r.u["id"], r.u["name"]) for r in self.upd_rows if r.check.isChecked()]
        self._run_upgrade(items)

    def update_all(self):
        self._run_upgrade([(r.u["id"], r.u["name"]) for r in self.upd_rows])

    def _run_upgrade(self, items):
        if not items:
            return
        RunDialog(self.main, tr("apps.upd_title"), lambda log, prog: A.upgrade(items, log, prog)).exec()
        self.check_updates()

    # ── встановлення ──
    def scan_installed(self):
        ids = [r.pkg for r in self.inst_rows]

        def done(res):
            if isinstance(res, set):
                for r in self.inst_rows:
                    r.installed = r.pkg in res
                    r.check.setEnabled(not r.installed)
                    r.tag.setVisible(r.installed)
                    if r.installed:
                        style_badge(r.tag, tr("apps.installed"), "ok")
                        r.check.setChecked(False)
                n = len(res)
                self.inst_state.setText(tr("apps.inst_found", n=n, total=len(ids)))
        self.main.run_quick(tr("apps.scan"), lambda log, p: A.installed_ids(ids), busy=self.btn_scan, silent=True,
                            on_done=done)

    def _count_inst(self):
        n = sum(r.check.isChecked() for r in self.inst_rows)
        self.btn_inst.setEnabled(n > 0)
        self.btn_inst.setText(tr("apps.install_n", n=n) if n else tr("apps.install"))

    def install_selected(self):
        items = [(r.pkg, r.name) for r in self.inst_rows if r.check.isChecked()]
        if not items:
            return
        RunDialog(self.main, tr("apps.inst_title"), lambda log, prog: A.install(items, log, prog)).exec()
        for r in self.inst_rows:
            r.check.setChecked(False)
        self.scan_installed()


# ───────────────────────── Що займає місце ─────────────────────────
def human(b: float) -> str:
    for unit, k in (("GB", 2**30), ("MB", 2**20), ("KB", 2**10)):
        if b >= k:
            return f"{b / k:.1f} {unit}"
    return f"{b:.0f} B"


class DiskView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.scan = None
        self.path = None
        v = vbox(self, (32, 4, 32, 24), 14)
        c, cv = section_card(tr("disk.title"), tr("disk.sub"))
        r = hbox(margins=(14, 0, 14, 4), spacing=10)
        self.root = QLineEdit(os.environ.get("SystemDrive", "C:") + "\\")
        self.root.setFixedWidth(260)
        r.addWidget(self.root)
        r.addWidget(button(tr("disk.pick"), None, self.pick))
        self.btn_scan = button(tr("disk.scan"), "primary", self.start)
        r.addWidget(self.btn_scan)
        r.addStretch()
        cv.addLayout(r)
        self.busy = Busy(main, cv)
        nav = hbox(margins=(14, 6, 14, 2), spacing=10)
        self.btn_up = button(tr("disk.up"), "ghost", self.up)
        self.btn_up.setEnabled(False)
        nav.addWidget(self.btn_up)
        self.crumb = label("", "rowTitle", wrap=True)
        nav.addWidget(self.crumb, 1)
        self.btn_open = button(tr("disk.open"), "ghost", lambda: self.open_path(self.path))
        self.btn_open.setEnabled(False)
        nav.addWidget(self.btn_open)
        cv.addLayout(nav)
        self.list = vbox(spacing=2)
        cv.addLayout(self.list)
        v.addWidget(c)
        fc, fv = section_card(tr("disk.files"), tr("disk.files_d"))
        self.files = vbox(spacing=2)
        fv.addLayout(self.files)
        v.addWidget(fc)
        v.addStretch()

    def pick(self):
        path = QFileDialog.getExistingDirectory(self, tr("disk.pick"), self.root.text())
        if isinstance(path, str) and path:
            self.root.setText(os.path.normpath(path))

    def start(self):
        root = self.root.text().strip() or "C:\\"

        def done(res):
            if isinstance(res, A.DiskScan):
                self.scan = res
                self.show_dir(res.root)
                self.fill_files()
                self.main.toast(tr("disk.done", n=f"{res.nfiles:,}".replace(",", " "), size=human(res.sizes.get(res.root, 0))))
        self.busy.start(lambda log, p: A.DiskScan(root).run(p), done, tr("disk.scanning", n=0, path=root))

    def show_dir(self, path: str):
        self.path = path
        sc = self.scan
        total = sc.sizes.get(path, 0) or 1
        self.crumb.setText(f"{path}   ·   {human(sc.sizes.get(path, 0))}")
        self.btn_up.setEnabled(path != sc.root)
        self.btn_open.setEnabled(True)
        clear_layout(self.list)
        items = sc.items(path)
        for p, size, is_dir in items[:40]:
            row = QFrame()
            row.setObjectName("row")
            row.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            h = hbox(row, (14, 6, 14, 6), 12)
            name = (ntpath.basename(p.rstrip("\\")) or p) if is_dir else tr("disk.here")
            nl = label(("▸ " if is_dir and sc.children.get(p) else "") + name, "rowTitle")
            nl.setFixedWidth(300)
            h.addWidget(nl)
            bar = QProgressBar()
            bar.setObjectName("sizebar")
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setRange(0, 1000)
            bar.setValue(int(1000 * size / total))
            h.addWidget(bar, 1)
            h.addWidget(label(f"{100 * size / total:.0f}%", "desc"))
            sz = label(human(size), "value")
            sz.setFixedWidth(90)
            sz.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            h.addWidget(sz)
            if is_dir and sc.children.get(p):
                go = button(tr("disk.enter"), "ghost", lambda pp=p: self.show_dir(pp))
            else:
                go = QLabel()
            go.setFixedWidth(96)
            h.addWidget(go)
            self.list.addWidget(row)
        if not items:
            lb = label(tr("disk.empty"), "sub")
            lb.setContentsMargins(14, 4, 14, 8)
            self.list.addWidget(lb)

    def up(self):
        if self.scan and self.path and self.path != self.scan.root:
            parent = ntpath.dirname(self.path.rstrip("\\")) if "\\" in self.path else os.path.dirname(self.path)
            self.show_dir(parent if parent in self.scan.sizes else self.scan.root)

    def fill_files(self):
        clear_layout(self.files)
        for size, path in self.scan.files[:20]:
            row = QFrame()
            row.setObjectName("row")
            h = hbox(row, (14, 6, 14, 6), 12)
            pl = label(path, "desc")
            pl.setToolTip(path)
            h.addWidget(pl, 1)
            h.addWidget(label(human(size), "value"))
            h.addWidget(button(tr("st.locate"), "ghost", lambda pp=path: self.open_path(pp, True)))
            self.files.addWidget(row)

    def open_path(self, path: str, select: bool = False):
        if not path:
            return
        if E.IS_WIN and os.path.exists(path):
            subprocess.Popen(["explorer.exe", "/select,", path] if select else ["explorer.exe", path])
        else:
            self.main.toast(tr("toast.preview_only"), "warn")


# ───────────────────────── Старі драйвери ─────────────────────────
class DriversView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.rows = []
        v = vbox(self, (32, 4, 32, 24), 14)
        c, cv = section_card(tr("drv.title"), tr("drv.sub"))
        r = hbox(margins=(14, 0, 14, 4), spacing=10)
        self.btn_find = button(tr("drv.find"), "primary", self.find)
        r.addWidget(self.btn_find)
        r.addStretch()
        self.total = label("", "desc")
        r.addWidget(self.total)
        self.btn_del = button(tr("drv.delete"), "danger", self.delete)
        self.btn_del.setEnabled(False)
        r.addWidget(self.btn_del)
        cv.addLayout(r)
        self.busy = Busy(main, cv)
        self.box = vbox(spacing=2)
        cv.addLayout(self.box)
        note = label(tr("drv.note"), "desc", wrap=True)
        note.setContentsMargins(14, 6, 14, 6)
        cv.addWidget(note)
        v.addWidget(c)
        v.addStretch()

    def find(self):
        def done(res):
            if isinstance(res, list):
                self.fill(res)
        self.busy.start(lambda log, p: (log(f"[►] {tr('drv.title')}"), A.old_drivers(log))[1], done, tr("drv.searching"))

    def fill(self, items: list):
        clear_layout(self.box)
        self.rows = []
        for d in items:
            r = PickRow(f"{d['prov']} — {d['cls']}", tr("drv.row", ver=d["ver"], date=d["date"], inf=d["inf"],
                                                         orig=d["orig"]),
                        human(d["size_mb"] * 2**20) if d["size_mb"] else None, "muted", self._count)
            r.check.setChecked(True)
            r.d = d
            self.box.addWidget(r)
            self.rows.append(r)
        if not items:
            lb = label(tr("drv.none"), "sub")
            lb.setContentsMargins(14, 4, 14, 8)
            self.box.addWidget(lb)
        self._count()

    def selected(self):
        return [r.d for r in self.rows if r.check.isChecked()]

    def _count(self):
        sel = self.selected()
        mb = sum(d["size_mb"] for d in sel)
        self.total.setText(tr("drv.total", n=len(sel), size=human(mb * 2**20)) if self.rows else "")
        self.btn_del.setEnabled(bool(sel))

    def delete(self):
        sel = self.selected()
        if not sel or not Ask.ask(self, tr("drv.delete"), tr("drv.delete_q", n=len(sel)), tr("drv.delete"), "danger"):
            return
        RunDialog(self.main, tr("drv.title"), lambda log, prog: A.delete_drivers(sel, log, prog)).exec()
        self.find()
