"""
OptimaX — сторінки «Бенчмарки» (власний GPU-тест, стрес-тест, FurMark 2, Superposition та інші)
і «Блок реклами» (DNS-фільтр як Pi-hole зі статистикою, журналом запитів і списками; легкий режим).
"""
from __future__ import annotations

import time
import webbrowser

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QGridLayout, QProgressBar, QMenu, QLineEdit, QPlainTextEdit

import adblock as AB
import benchtools as BT
import engine as E
import features as F
import gpubench as GB
from i18n import tr
from pages_extra import page_body, log_strip, stat_cell, PickRow
from ui_kit import (T, label, button, card, vbox, hbox, badge, style_badge, dot, scroller, page_header, clear_layout,
                    section_card, Switch, Segmented, Ask, RunDialog, Spark, Bars, LOG, asset)


def num(n) -> str:
    return "—" if n is None else f"{int(n):,}".replace(",", " ")


def mmss(sec) -> str:
    sec = int(sec or 0)
    return f"{sec // 60}:{sec % 60:02d}"


def when(ts) -> str:
    return time.strftime("%d.%m %H:%M", time.localtime(ts)) if ts else "—"


# ───────────────────────── Бенчмарки ─────────────────────────
KIND_BADGE = {"gpu": "acc", "cpu": "warn", "stab": "bad", "disk": "ok"}
VERDICT_KIND = {"bench": "acc", "stable": "ok", "errors": "bad", "hot": "warn", "throttle": "warn", "crash": "bad"}
PRESET_KEYS = ("1080p", "1440p", "4k")


class BenchPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.run = None
        self.res_i = self.mode_i = self.min_i = 0
        self.status = {}
        self.loaded = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.bench"), tr("gb.sub")))
        body, v = page_body()
        from smart_ui import SmartCard
        self.smart = SmartCard(main)
        v.addWidget(self.smart)

        # ── власний тест ──
        hc = card("cardAccent")
        hv = vbox(hc, (24, 20, 24, 20), 14)
        top = hbox(spacing=22)
        tv = vbox(spacing=8)
        tv.addWidget(label(tr("gb.title"), "h1"))
        tv.addWidget(label(tr("gb.text"), "sub", wrap=True))
        facts = hbox(spacing=8)
        for k in ("gb.f1", "gb.f2", "gb.f3"):
            facts.addWidget(badge(tr(k), "muted"))
        facts.addStretch()
        tv.addLayout(facts)
        tv.addStretch()
        top.addLayout(tv, 1)
        pic = asset("bench.png")
        if pic:
            pm = QPixmap(pic)
            pm.setDevicePixelRatio(2)
            pl = QLabel()
            pl.setPixmap(pm)
            pl.setFixedSize(320, 180)
            top.addWidget(pl, 0, Qt.AlignmentFlag.AlignTop)
        hv.addLayout(top)
        r1 = hbox(spacing=10)
        r1.addWidget(label(tr("gb.res"), "desc"))
        self.seg_res = Segmented(["1080p", "1440p", "4K"])
        self.seg_res.changed.connect(self._res)
        r1.addWidget(self.seg_res)
        r1.addSpacing(12)
        r1.addWidget(label(tr("gb.mode"), "desc"))
        self.seg_mode = Segmented([tr("gb.mode_bench_s"), tr("gb.mode_stress")])
        self.seg_mode.changed.connect(self._mode)
        r1.addWidget(self.seg_mode)
        r1.addStretch()
        hv.addLayout(r1)
        r2 = hbox(spacing=10)
        self.min_lbl = label(tr("gb.minutes"), "desc")
        r2.addWidget(self.min_lbl)
        self.seg_min = Segmented([tr("u.min_n", n=m) for m in GB.STRESS_MINUTES])
        self.seg_min.changed.connect(lambda i: setattr(self, "min_i", i))
        r2.addWidget(self.seg_min)
        r2.addSpacing(8)
        self.sw_full = Switch()
        r2.addWidget(self.sw_full)
        r2.addWidget(label(tr("gb.fullscreen"), "desc"))
        r2.addStretch()
        self.btn_run = button(tr("gb.start"), "primary", self.start)
        r2.addWidget(self.btn_run)
        hv.addLayout(r2)
        self.min_lbl.hide()
        self.seg_min.hide()
        self.prog = QWidget()
        pv = vbox(self.prog, spacing=6)
        ph = hbox(spacing=10)
        self.prog_lbl = label("", "desc", wrap=True)
        ph.addWidget(self.prog_lbl, 1)
        self.btn_stop = button(tr("run.stop"), "ghost", self.stop)
        ph.addWidget(self.btn_stop)
        pv.addLayout(ph)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        pv.addWidget(self.bar)
        self.prog.hide()
        hv.addWidget(self.prog)
        v.addWidget(hc)

        # ── результат ──
        self.res_card, rv = section_card(tr("gb.result"))
        rt = hbox(margins=(14, 4, 14, 8), spacing=26)
        sb = vbox(spacing=0)
        self.score = label("—", "display")
        sb.addWidget(self.score)
        self.score_cap = label("", "muted")
        sb.addWidget(self.score_cap)
        rt.addLayout(sb)
        vb = vbox(spacing=4)
        self.verdict = label("", "h3", wrap=True)
        vb.addWidget(self.verdict)
        self.verdict_d = label("", "desc", wrap=True)
        vb.addWidget(self.verdict_d)
        rt.addLayout(vb, 1)
        rv.addLayout(rt)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(14, 4, 14, 8)
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(10)
        rv.addLayout(self.grid)
        ch = vbox(margins=(14, 2, 14, 2), spacing=6)
        self.chart = Spark(110, "fps")
        ch.addWidget(self.chart)
        self.chart_t = Spark(70, "°C")
        ch.addWidget(self.chart_t)
        rv.addLayout(ch)
        lr = hbox(margins=(14, 0, 14, 4), spacing=10)
        self.legend = label("", "muted")
        lr.addWidget(self.legend, 1)
        lr.addWidget(button(tr("sc.share"), "ghost", main.share_result))
        rv.addLayout(lr)
        self.res_card.hide()
        v.addWidget(self.res_card)

        # ── історія ──
        self.hist_card, hv2 = section_card(tr("gb.hist"), tr("gb.hist_d"))
        self.hist_box = vbox(spacing=0)
        hv2.addLayout(self.hist_box)
        hb = hbox(margins=(14, 4, 14, 4))
        hb.addStretch()
        hb.addWidget(button(tr("gb.hist_clear"), "ghost", self.clear_hist))
        hv2.addLayout(hb)
        v.addWidget(self.hist_card)

        # ── сторонні бенчмарки ──
        tc, tv2 = section_card(tr("gb.tools"), tr("gb.tools_d"))
        self.tool_rows = {}
        for item in BT.CATALOG:
            row = QFrame()
            row.setObjectName("row")
            h = hbox(row, (14, 10, 14, 10), 10)
            col = vbox(spacing=2)
            th = hbox(spacing=8)
            th.addWidget(label(item["name"], "rowTitle"))
            th.addWidget(badge(tr(f"gb.kind.{item['kind']}"), KIND_BADGE[item["kind"]]))
            st = badge(tr("apps.installed"), "ok")
            st.hide()
            th.addWidget(st)
            th.addStretch()
            col.addLayout(th)
            col.addWidget(label(tr(f"gb.t.{item['id']}"), "desc", wrap=True))
            h.addLayout(col, 1)
            alt = button(tr("gb.open"))
            alt.clicked.connect(lambda _=False, i=item["id"]: self.tool_click(i, "alt"))
            main_b = button(tr("gb.install"))
            main_b.clicked.connect(lambda _=False, i=item["id"]: self.tool_click(i, "main"))
            site = button(tr("gb.site"), "ghost")
            site.clicked.connect(lambda _=False, it=item: BT.open_site(it))
            for b in (alt, main_b, site):
                h.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
            alt.hide()
            self.tool_rows[item["id"]] = dict(state=st, main=main_b, alt=alt)
            tv2.addWidget(row)
        v.addWidget(tc)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        log_strip(outer)
        self.fill_history()
        hist = F.CFG["bench"] or []
        if hist:
            self.show_result(hist[-1])
        self.sync_tools()

    def on_show(self):
        self.smart.sync()
        if not self.loaded:
            self.loaded = True
            self.scan()

    # ── власний тест ──
    def _res(self, i: int):
        self.res_i = i
        self.sync_tools()

    def _mode(self, i: int):
        self.mode_i = i
        self.min_lbl.setVisible(i == 1)
        self.seg_min.setVisible(i == 1)
        self.btn_run.setText(tr("gb.start_stress") if i == 1 else tr("gb.start"))

    @property
    def preset(self) -> str:
        return PRESET_KEYS[self.res_i]

    def start(self):
        if self.run:
            return
        mode = ("bench", "stress")[self.mode_i]
        minutes = GB.STRESS_MINUTES[self.min_i]
        if mode == "stress" and not Ask.ask(self, tr("gb.stress_t"), tr("gb.stress_q", m=minutes), tr("gb.start_stress"),
                                            "danger"):
            return
        try:
            self.run = GB.start(self.preset, mode, minutes, self.sw_full.isChecked())
        except Exception as e:
            Ask.info(self, tr("gb.err_t"), tr("gb.err_d", err=e))
            return
        LOG.write(f"[►] {tr('gb.title')}: {self.preset}, "
                  f"{tr('gb.mode_bench') if mode == 'bench' else tr('gb.mode_stress') + ' ' + tr('u.min_n', n=minutes)}")
        self.btn_run.setEnabled(False)
        self.prog.show()
        self.bar.setRange(0, 0)
        self.prog_lbl.setText(tr("gb.p_start"))
        self.timer.start(400)

    def stop(self):
        if self.run:
            self.run.stop()

    def _tick(self):
        if not self.run:
            self.timer.stop()
            return
        st = self.run.poll()
        s = st.get("state")
        if s == "starting":
            return
        if s in ("warmup", "running"):
            dur = st.get("duration") or GB.BENCH_SECONDS
            self.bar.setRange(0, int(dur))
            self.bar.setValue(int(st.get("t") or 0))
            parts = [tr("gb.p_warm") if s == "warmup" else tr("gb.p_run", t=mmss(st.get("t")), d=mmss(dur))]
            if s == "running" and st.get("fps"):
                parts.append(f"{st['fps']:.0f} FPS")
            sens = st.get("sensors") or {}
            if sens.get("temp") is not None:
                parts.append(f"{sens['temp']} °C")
            if sens.get("clock"):
                parts.append(f"{sens['clock']} MHz")
            if st.get("mode") == "stress":
                parts.append(tr("gb.p_err", n=st.get("errors", 0)))
            self.prog_lbl.setText(" · ".join(parts))
            return
        self._finish(st)

    def _finish(self, st: dict):
        self.timer.stop()
        run, self.run = self.run, None
        run.cleanup()
        self.prog.hide()
        self.btn_run.setEnabled(True)
        s = st.get("state")
        if s == "cancelled":
            LOG.write(tr("gb.cancelled"))
            self.main.toast(tr("gb.cancelled"), "warn")
            return
        if s == "error":
            LOG.write(tr("e.err", err=st.get("error", "?")))
            Ask.info(self, tr("gb.err_t"), tr("gb.err_d", err=st.get("error", "?")))
            return
        res = GB.save_result(F.CFG, dict(st.get("result") or {}, kind="own"))
        self.show_result(res)
        self.fill_history()
        v = res.get("verdict", "bench")
        if res.get("score"):
            LOG.write(tr("gb.log_score", score=num(res["score"]), fps=res.get("avg"), low=res.get("low1")))
            self.main.toast(tr("gb.toast_score", score=num(res["score"])))
        else:
            LOG.write(tr(f"gb.v.{v}.t", **self._kw(res)))
            self.main.toast(tr(f"gb.v.{v}.t", **self._kw(res)), "ok" if v == "stable" else "warn")

    @staticmethod
    def _kw(r: dict) -> dict:
        return dict(n=r.get("errors", 0), t=r.get("temp_max", "—"), drop=f"{r.get('drop') or 0:.0f}",
                    m=r.get("minutes") or round((r.get("dur") or 0) / 60), score=num(r.get("score")))

    def show_result(self, r: dict):
        self.res_card.show()
        v = r.get("verdict") or "bench"
        name = "FurMark 2" if r.get("kind") == "furmark" else "OptimaX"
        preset = {"4k": "4K"}.get(r.get("preset"), r.get("preset") or "")
        if r.get("score"):
            self.score.setText(num(r["score"]))
            self.score_cap.setText(f"{tr('gb.points')} · {name} · {preset}")
        else:
            self.score.setText(tr("u.min_n", n=r.get("minutes") or max(1, round((r.get("dur") or 0) / 60))))
            self.score_cap.setText(f"{tr('gb.mode_stress')} · {preset}")
        self.score.setStyleSheet(f"color:{T[VERDICT_KIND.get(v, 'acc')] if v != 'bench' else T['text']};")
        kw = self._kw(r)
        if v == "bench":
            self.verdict.setText(tr("gb.v.bench.t", score=num(r.get("score")), preset=preset))
            if r.get("delta") is not None:
                d = r["delta"]
                key = "gb.delta_up" if d >= 1 else "gb.delta_down" if d <= -1 else "gb.delta_same"
                text = tr(key, d=f"{d:+.1f}")
                if r.get("changes"):
                    text += " " + tr("gb.delta_changes", n=r["changes"])
                self.verdict_d.setText(text)
            else:
                self.verdict_d.setText(tr("gb.first"))
            self.verdict.setStyleSheet("")
        else:
            self.verdict.setText(tr(f"gb.v.{v}.t", **kw))
            self.verdict_d.setText(tr(f"gb.v.{v}.d", **kw))
            self.verdict.setStyleSheet(f"color:{T[VERDICT_KIND[v]]};")
        clear_layout(self.grid)
        fps = lambda x: "—" if not x else f"{x:.0f}"  # noqa: E731
        cells = [(tr("gb.s.avg"), fps(r.get("avg"))), ("1% low", fps(r.get("low1"))), (tr("gb.s.min"), fps(r.get("min"))),
                 (tr("gb.s.temp"), f"{r['temp_max']} °C" if r.get("temp_max") else "—")]
        if r.get("clock_avg"):
            cells.append((tr("gb.s.clock"), f"{r['clock_avg']} / {r.get('clock_min', '—')} MHz"))
        if r.get("power_max"):
            cells.append((tr("gb.s.power"), f"{r['power_max']:.0f} W"))
        if r.get("mode") == "stress":
            cells.append((tr("gb.s.checks"), tr("gb.s.checks_v", n=r.get("errors", 0), c=r.get("checks", 0))))
            cells.append((tr("gb.s.drop"), f"−{r.get('drop') or 0:.1f}%"))
        if r.get("dur"):
            cells.append((tr("gb.s.dur"), mmss(r["dur"])))
        if r.get("gpu"):
            cells.append((tr("gb.s.gpu"), r["gpu"]))
        if r.get("idle_gpu"):
            self.verdict_d.setText(tr("gb.idle_gpu", gpu=r.get("gpu") or "?", dgpu=r["idle_gpu"]))
        for i, (c, val) in enumerate(cells):
            stat_cell(self.grid, i, c, val)
        fs = r.get("series_fps") or []
        ts = [t for t in (r.get("series_temp") or []) if t is not None]
        self.chart.set_series([(fs, T["acc"])])
        self.chart.setVisible(bool(fs))
        self.chart_t.set_series([(ts, T["warn"])])
        self.chart_t.setVisible(bool(ts))
        self.legend.setText(tr("gb.legend_t") if ts else tr("gb.legend") if fs else "")

    def fill_history(self):
        clear_layout(self.hist_box)
        hist = list(reversed(F.CFG["bench"] or []))[:12]
        self.hist_card.setVisible(bool(hist))
        for h in hist:
            row = QFrame()
            row.setObjectName("row")
            lay = hbox(row, (14, 7, 14, 7), 12)
            dl = label(when(h.get("ts")), "muted")
            dl.setFixedWidth(84)
            lay.addWidget(dl)
            name = "FurMark 2" if h.get("kind") == "furmark" else "OptimaX"
            preset = {"4k": "4K"}.get(h.get("preset"), h.get("preset") or "")
            title = f"{name} · {preset}"
            if h.get("mode") == "stress":
                title += f" · {tr('gb.mode_stress')} {tr('u.min_n', n=h.get('minutes') or '?')}"
            lay.addWidget(label(title, "rowTitle"), 1)
            v = h.get("verdict") or "bench"
            if h.get("score"):
                lay.addWidget(label(num(h["score"]), "value"))
            else:
                lay.addWidget(badge(tr(f"gb.vs.{v}"), VERDICT_KIND.get(v, "muted")))
            if h.get("delta") is not None:
                d = h["delta"]
                lay.addWidget(badge(f"{d:+.1f}%", "ok" if d >= 1 else "bad" if d <= -1 else "muted"))
            b = button(tr("gb.details"), "ghost")
            b.clicked.connect(lambda _=False, hh=h: self.show_result(hh))
            lay.addWidget(b)
            self.hist_box.addWidget(row)

    def clear_hist(self):
        if not Ask.ask(self, tr("gb.hist_clear"), tr("gb.hist_clear_q"), tr("gb.hist_clear"), "danger"):
            return
        F.CFG["bench"] = []
        self.fill_history()
        self.res_card.hide()

    # ── сторонні програми ──
    def scan(self):
        def done(res):
            if isinstance(res, dict) and not res.get("error"):
                self.status = res
                self.sync_tools()
        self.main.run_quick("bench-tools", lambda log, p: BT.status(), silent=True, on_done=done)

    def sync_tools(self):
        for item in BT.CATALOG:
            r = self.tool_rows[item["id"]]
            path = self.status.get(item["id"])
            r["state"].setVisible(bool(path))
            r["alt"].setVisible(bool(path) and item["id"] == "furmark")
            if item.get("steam"):
                r["main"].setText(tr("gb.open_steam"))
            elif not path:
                r["main"].setText(tr("gb.install"))
            elif item["id"] == "furmark":
                r["main"].setText(tr("gb.fm_run", preset={"4k": "4K"}.get(self.preset, self.preset)))
            else:
                r["main"].setText(tr("gb.open"))

    def tool_click(self, tid: str, which: str):
        item = BT.BY_ID[tid]
        path = self.status.get(tid)
        if item.get("steam") or (path and (which == "alt" or tid != "furmark")):
            if BT.launch(item):
                self.main.toast(tr("gb.launched", name=item["name"]))
            else:
                self.main.toast(tr("toast.preview_only"), "warn")
            return
        if path and tid == "furmark":
            self.run_furmark()
            return
        if not Ask.ask(self, tr("gb.install_t", name=item["name"]), tr("gb.install_q", name=item["name"], pkg=item["pkg"]),
                       tr("gb.install")):
            return
        RunDialog(self.main, tr("gb.install_t", name=item["name"]), lambda log, prog: BT.install(item, log, prog)).exec()
        self.scan()

    def run_furmark(self):
        preset = self.preset
        if not Ask.ask(self, "FurMark 2", tr("gb.fm_q", preset={"4k": "4K"}.get(preset, preset)), tr("gb.start")):
            return
        dlg = RunDialog(self.main, f"FurMark 2 · {preset}", lambda log, prog: BT.run_furmark(preset, log, prog))
        dlg.exec()
        res = dlg.res or {}
        if res.get("ok"):
            saved = GB.save_result(F.CFG, dict(res, verdict="bench"))
            self.show_result(saved)
            self.fill_history()


# ───────────────────────── Блок реклами ─────────────────────────
STATUS_BADGE = {"blocked": "bad", "cache": "muted", "ok": "ok", "local": "acc", "fail": "warn"}
UPSTREAM_KEYS = list(AB.UPSTREAMS)


class AdblockPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.ab = AB.Backend(F.CFG)
        self.fetching = False
        self.seg_i = 0
        self.log_flt = "all"
        self.last = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh)
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.adblock"), tr("ab.sub")))
        body, v = page_body()

        # ── стан ──
        hc = card("cardAccent")
        hv = vbox(hc, (24, 20, 24, 20), 14)
        top = hbox(spacing=14)
        self.st_dot = dot(T["mute"], 12)
        top.addWidget(self.st_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        tv = vbox(spacing=3)
        self.st_title = label("", "h1")
        tv.addWidget(self.st_title)
        self.st_sub = label("", "sub", wrap=True)
        tv.addWidget(self.st_sub)
        top.addLayout(tv, 1)
        self.btn_pause = button(tr("ab.pause"), None, self.pause_menu)
        top.addWidget(self.btn_pause, 0, Qt.AlignmentFlag.AlignVCenter)
        self.btn_off = button(tr("ab.disable"), None, self.disable)
        top.addWidget(self.btn_off, 0, Qt.AlignmentFlag.AlignVCenter)
        self.btn_on = button(tr("ab.enable"), "primary", self.enable)
        top.addWidget(self.btn_on, 0, Qt.AlignmentFlag.AlignVCenter)
        hv.addLayout(top)
        self.mode_row = QWidget()
        mr = hbox(self.mode_row, spacing=10)
        mr.addWidget(label(tr("ab.mode"), "desc"))
        self.seg_mode = Segmented([tr("ab.mode_filter"), tr("ab.mode_light")])
        self.seg_mode.changed.connect(self._mode_changed)
        mr.addWidget(self.seg_mode)
        mr.addStretch()
        hv.addWidget(self.mode_row)
        self.how = QWidget()
        hw = hbox(self.how, spacing=18)
        for i in (1, 2, 3):
            s = hbox(spacing=8)
            n = label(str(i), "stepNum")
            n.setFixedSize(24, 24)
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.addWidget(n, 0, Qt.AlignmentFlag.AlignTop)
            s.addWidget(label(tr(f"ab.step{i}"), "desc", wrap=True), 1)
            hw.addLayout(s, 1)
        hv.addWidget(self.how)
        self.tiles = QWidget()
        tg = hbox(self.tiles, spacing=12)
        self.tile = {}
        for key in ("total", "blocked", "domains", "speed"):
            c = card()
            cv = vbox(c, (16, 12, 16, 12), 1)
            val = label("—", "big")
            cv.addWidget(val)
            cv.addWidget(label(tr(f"ab.tile.{key}"), "desc"))
            sub = label("", "muted")
            cv.addWidget(sub)
            tg.addWidget(c, 1)
            self.tile[key] = (val, sub)
        hv.addWidget(self.tiles)
        v.addWidget(hc)

        # ── легкий режим ──
        self.light_card, lv = section_card(tr("ab.light_t"), tr("ab.light_d"))
        self.light_rows = {}
        for prov in AB.LIGHT:
            row = QFrame()
            row.setObjectName("row")
            h = hbox(row, (14, 9, 14, 9), 12)
            col = vbox(spacing=1)
            th = hbox(spacing=8)
            th.addWidget(label(prov["name"], "rowTitle"))
            st = badge(tr("ab.light_active"), "ok")
            st.hide()
            th.addWidget(st)
            th.addStretch()
            col.addLayout(th)
            col.addWidget(label(tr(f"ab.light.{prov['what']}") + "  ·  " + " · ".join(prov["ips"]), "muted"))
            h.addLayout(col, 1)
            b = button(tr("net.dns.use"))
            b.clicked.connect(lambda _=False, pid=prov["id"]: self.use_light(pid))
            h.addWidget(b)
            self.light_rows[prov["id"]] = (st, b)
            lv.addWidget(row)
        lr = hbox(margins=(14, 6, 14, 6), spacing=10)
        self.sw_ldoh = Switch()
        self.sw_ldoh.set_quiet(True)
        lr.addWidget(self.sw_ldoh)
        lr.addWidget(label(tr("net.dns.doh"), "desc", wrap=True), 1)
        lv.addLayout(lr)
        v.addWidget(self.light_card)

        # ── графік ──
        self.chart_card, cv = section_card(tr("ab.chart_t"))
        bw = hbox(margins=(14, 2, 14, 2))
        self.bars = Bars(160)
        bw.addWidget(self.bars)
        cv.addLayout(bw)
        lg = hbox(margins=(14, 4, 14, 4), spacing=6)
        a = QFrame()
        a.setFixedSize(10, 10)
        a.setStyleSheet(f"background:{T['acc_line']}; border-radius:3px;")
        lg.addWidget(a)
        lg.addWidget(label(tr("ab.legend_ok"), "muted"))
        lg.addSpacing(12)
        b = QFrame()
        b.setFixedSize(10, 10)
        b.setStyleSheet(f"background:{T['acc2']}; border-radius:3px;")
        lg.addWidget(b)
        lg.addWidget(label(tr("ab.legend_blocked"), "muted"))
        lg.addStretch()
        cv.addLayout(lg)
        v.addWidget(self.chart_card)

        # ── топи ──
        self.tops = QWidget()
        th2 = hbox(self.tops, spacing=14)
        c1, v1 = section_card(tr("ab.top_blocked"))
        self.top_blk = vbox(spacing=0)
        v1.addLayout(self.top_blk)
        v1.addStretch()
        th2.addWidget(c1, 1)
        c2 = card()
        v2 = vbox(c2, (8, 14, 8, 8), 2)
        self.top_oth_title = label(tr("ab.top_allowed"), "h2")
        self.top_oth_title.setContentsMargins(14, 0, 14, 6)
        v2.addWidget(self.top_oth_title)
        self.top_oth = vbox(spacing=0)
        v2.addLayout(self.top_oth)
        v2.addStretch()
        th2.addWidget(c2, 1)
        v.addWidget(self.tops)

        # ── журнал запитів ──
        self.log_card, lgv = section_card(tr("ab.log_t"), tr("ab.log_d"))
        fr = hbox(margins=(14, 0, 14, 6), spacing=10)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("ab.search"))
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda _: self.search_timer.start(350))
        fr.addWidget(self.search)
        self.seg_log = Segmented([tr("ab.f_all"), tr("ab.f_blocked"), tr("ab.f_allowed")])
        self.seg_log.changed.connect(self._log_filter)
        fr.addWidget(self.seg_log)
        fr.addStretch()
        fr.addWidget(button(tr("ab.refresh"), "ghost", self.refresh))
        lgv.addLayout(fr)
        self.log_box = vbox(spacing=0)
        lgv.addLayout(self.log_box)
        v.addWidget(self.log_card)

        # ── списки ──
        self.lists_card, lsv = section_card(tr("ab.lists_t"), tr("ab.lists_d"))
        self.list_rows = {}
        cols = hbox(margins=(6, 0, 6, 0), spacing=10)
        col_l, col_r = vbox(spacing=2), vbox(spacing=2)
        for n, cat in enumerate(AB.LIST_CATS):
            col = col_l if n % 2 == 0 else col_r
            cap = label(tr(f"ab.cat.{cat}"), "h3")
            cap.setContentsMargins(8, 8, 8, 2)
            col.addWidget(cap)
            for item in [x for x in AB.LISTS if x["cat"] == cat]:
                r = PickRow(item["name"], tr(f"ab.l.{item['id']}"), on_toggle=self._lists_changed, wrap=True)
                r.lid = item["id"]
                col.addWidget(r)
                self.list_rows[item["id"]] = r
        col_l.addStretch()
        col_r.addStretch()
        cols.addLayout(col_l, 1)
        cols.addLayout(col_r, 1)
        lsv.addLayout(cols)
        lf = hbox(margins=(14, 8, 14, 6), spacing=10)
        self.lists_state = label("", "desc", wrap=True)
        lf.addWidget(self.lists_state, 1)
        self.btn_upd = button(tr("ab.lists_update"), "ghost", self.update_lists)
        lf.addWidget(self.btn_upd)
        self.btn_lists = button(tr("ab.lists_save"), "primary", self.save_lists)
        self.btn_lists.setEnabled(False)
        lf.addWidget(self.btn_lists)
        lsv.addLayout(lf)
        v.addWidget(self.lists_card)

        # ── власні правила ──
        self.rules_card, rv = section_card(tr("ab.rules_t"), tr("ab.rules_d"))
        rc = hbox(margins=(14, 0, 14, 4), spacing=14)
        self.rule_edit = {}
        for kind in ("allow", "block"):
            col = vbox(spacing=6)
            col.addWidget(label(tr(f"ab.rules.{kind}"), "h3"))
            ed = QPlainTextEdit()
            ed.setObjectName("log")
            ed.setPlaceholderText(tr(f"ab.rules.{kind}_ph"))
            ed.setFixedHeight(120)
            col.addWidget(ed)
            rc.addLayout(col, 1)
            self.rule_edit[kind] = ed
        rv.addLayout(rc)
        rr = hbox(margins=(14, 4, 14, 6))
        rr.addStretch()
        rr.addWidget(button(tr("ab.rules_save"), None, self.save_rules))
        rv.addLayout(rr)
        v.addWidget(self.rules_card)

        # ── налаштування ──
        self.set_card, sv = section_card(tr("ab.set_t"))
        ur = hbox(margins=(14, 4, 14, 4), spacing=12)
        uc = vbox(spacing=1)
        uc.addWidget(label(tr("ab.upstream"), "rowTitle"))
        uc.addWidget(label(tr("ab.upstream_d"), "desc", wrap=True))
        ur.addLayout(uc, 1)
        self.seg_up = Segmented([AB.UPSTREAMS[k]["name"].split()[0] for k in UPSTREAM_KEYS])
        self.seg_up.changed.connect(lambda i: self.set_opt(upstream=UPSTREAM_KEYS[i]))
        ur.addWidget(self.seg_up, 0, Qt.AlignmentFlag.AlignVCenter)
        sv.addLayout(ur)
        self.sw = {}
        for key in ("doh", "lan", "log_queries", "strict"):
            row = hbox(margins=(14, 8, 14, 8), spacing=12)
            col = vbox(spacing=1)
            col.addWidget(label(tr(f"ab.s.{key}"), "rowTitle"))
            col.addWidget(label(tr(f"ab.s.{key}_d"), "desc", wrap=True))
            if key == "lan":
                self.lan_hint = label("", "warnNote", wrap=True)
                self.lan_hint.setContentsMargins(0, 2, 0, 0)
                self.lan_hint.hide()
                col.addWidget(self.lan_hint)
            row.addLayout(col, 1)
            sw = Switch()
            sw.toggled.connect(lambda on, k=key: self.set_opt(**{k: on}))
            row.addWidget(sw, 0, Qt.AlignmentFlag.AlignVCenter)
            self.sw[key] = sw
            sv.addLayout(row)
        v.addWidget(self.set_card)

        # ── чого DNS не прибере ──
        ib = QFrame()
        ib.setObjectName("bannerInfo")
        iv = vbox(ib, (18, 12, 18, 12), 4)
        iv.addWidget(label(tr("ab.yt_t"), "h3"))
        iv.addWidget(label(tr("ab.yt_d"), "desc", wrap=True))
        iv.addWidget(button(tr("ab.yt_btn"), "ghost", lambda: webbrowser.open("https://ublockorigin.com/")), 0,
                     Qt.AlignmentFlag.AlignLeft)
        v.addWidget(ib)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        log_strip(outer)
        self.fill_cfg()
        self.sync()

    # ── стан сторінки ──
    def on_show(self):
        self.sync()
        self.refresh()
        self.timer.start(4000)

    def _mode_changed(self, i: int):
        self.seg_i = i
        self.sync()

    def sync(self):
        mode = self.ab.mode
        on, light = mode == "filter", mode == "light"
        show_light = light or (mode == "off" and self.seg_i == 1)
        self.mode_row.setVisible(mode == "off")
        self.how.setVisible(mode == "off" and self.seg_i == 0)
        self.tiles.setVisible(on)
        for w in (self.chart_card, self.tops, self.log_card):
            w.setVisible(on)
        self.light_card.setVisible(show_light)
        for w in (self.lists_card, self.rules_card, self.set_card):
            w.setVisible(not show_light)
        self.btn_pause.setVisible(on)
        self.btn_off.setVisible(on or light)
        self.btn_on.setVisible(mode == "off" and self.seg_i == 0)
        cur = self.ab.ui.get("light")
        for pid, (st, b) in self.light_rows.items():
            st.setVisible(light and pid == cur)
            b.setEnabled(not (light and pid == cur))
        if on:
            self._title_on(self.last.get("status"))
        elif light:
            prov = AB.LIGHT_BY_ID.get(cur) or {}
            self.st_title.setText(tr("ab.light_on_t", name=prov.get("name", "DNS")))
            self.st_sub.setText(tr("ab.light_on_d"))
            self.st_dot.setStyleSheet(f"background:{T['ok']}; border-radius:6px;")
        else:
            self.st_title.setText(tr("ab.off_t"))
            self.st_sub.setText(tr("ab.off_d") if self.seg_i == 0 else tr("ab.light_d2"))
            self.st_dot.setStyleSheet(f"background:{T['mute']}; border-radius:6px;")
        self._lists_state()

    def _title_on(self, st):
        if st is None:
            self.st_title.setText(tr("ab.on_t"))
            self.st_sub.setText(tr("ab.waiting"))
            self.st_dot.setStyleSheet(f"background:{T['warn']}; border-radius:6px;")
            return
        paused = st.get("paused_until") or 0
        if paused:
            self.st_title.setText(tr("ab.paused_t", time=time.strftime("%H:%M", time.localtime(paused))))
            self.st_dot.setStyleSheet(f"background:{T['warn']}; border-radius:6px;")
        else:
            self.st_title.setText(tr("ab.on_t"))
            self.st_dot.setStyleSheet(f"background:{T['ok']}; border-radius:6px;")
        up = AB.UPSTREAMS.get(st.get("upstream"), {}).get("name", "DNS")
        sub = tr("ab.on_d", up=up, enc=tr("ab.enc_on") if st.get("doh") and st.get("doh_ok", True) else tr("ab.enc_off"))
        if st.get("lan") and st.get("lan_ips"):
            sub += " " + tr("ab.on_lan", ip=", ".join(st["lan_ips"]))
        self.st_sub.setText(sub)
        self.btn_pause.setText(tr("ab.resume") if paused else tr("ab.pause"))

    def fill_cfg(self):
        cfg = self.ab.cfg()
        for lid, r in self.list_rows.items():
            r.check.blockSignals(True)
            r.check.setChecked(lid in cfg["lists"])
            r.check.blockSignals(False)
        self.rule_edit["allow"].setPlainText("\n".join(cfg.get("allow", [])))
        self.rule_edit["block"].setPlainText("\n".join(cfg.get("block", [])))
        self.seg_up.select(UPSTREAM_KEYS.index(cfg.get("upstream")) if cfg.get("upstream") in UPSTREAM_KEYS else 0)
        for k, sw in self.sw.items():
            sw.set_quiet(bool(cfg.get(k)))
        self.btn_lists.setEnabled(False)
        self._lists_state()

    def _lists_state(self):
        meta = self.ab.lists_meta()
        cfg_lists = [lid for lid, r in self.list_rows.items() if r.check.isChecked()]
        total = 0
        for lid, r in self.list_rows.items():
            m = meta.get(lid) or {}
            if m.get("count"):
                style_badge(r.tag, tr("ab.count", n=num(m["count"])), "ok" if lid in cfg_lists else "muted")
                r.tag.show()
            elif m.get("error"):
                style_badge(r.tag, tr("ab.list_err"), "warn")
                r.tag.show()
            else:
                r.tag.hide()
            if lid in cfg_lists:
                total += m.get("count") or 0
        upd = max([(meta.get(i) or {}).get("updated") or 0 for i in cfg_lists] or [0])
        self.lists_state.setText(tr("ab.lists_state", n=len(cfg_lists), d=num(total), when=when(upd)) if upd else
                                 tr("ab.lists_never", n=len(cfg_lists)))

    # ── дані з фільтра ──
    def refresh(self):
        if self.ab.mode != "filter" or self.fetching:
            return
        if not self.isVisible():
            self.timer.stop()
            return
        self.fetching = True
        flt, text = self.log_flt, self.search.text().strip().lower()
        ab = self.ab

        def job(log, p):
            return dict(status=ab.status(), stats=ab.stats(), log=ab.querylog(20, flt, text))
        self.main.run_quick("adblock", job, silent=True, on_done=self._fill)

    def _fill(self, data):
        self.fetching = False
        if not isinstance(data, dict) or "status" not in data:
            return
        self.last = data
        st, sn = data.get("status"), data.get("stats")
        self._title_on(st)
        if not st:
            if self.ab.mode == "filter":
                self.main.run_quick("adblock", lambda log, p: self.ab.ensure_running(log), silent=True)
            return
        if sn:
            t = sn.get("today", {})
            self.tile["total"][0].setText(num(t.get("total")))
            self.tile["total"][1].setText(tr("ab.tile.total_s", n=num(t.get("cache")), local=num(t.get("local"))))
            self.tile["blocked"][0].setText(num(t.get("blocked")))
            self.tile["blocked"][1].setText(tr("ab.tile.blocked_s", pct=sn.get("pct", 0)))
            self.tile["speed"][0].setText(tr("u.ms", v=sn["avg_ms"]) if sn.get("avg_ms") is not None else "—")
            self.tile["speed"][1].setText(tr("ab.tile.speed_s", pct=sn.get("cache_pct", 0)))
            self.bars.set_data(sn.get("series") or [], AB.Stats.SLOT)
            self._tops(sn)
        self.tile["domains"][0].setText(num(st.get("domains")))
        self.tile["domains"][1].setText(tr("ab.tile.domains_s", n=len(st.get("lists") or {})))
        self._fill_log(data.get("log") or [])
        lan = bool(st.get("lan") and st.get("lan_ips"))
        self.lan_hint.setVisible(lan)
        if lan:
            self.lan_hint.setText(tr("ab.lan_hint", ip=st["lan_ips"][0]))

    def _row(self, box, title: str, count, action=None, sub: str = None):
        row = QFrame()
        row.setObjectName("row")
        h = hbox(row, (14, 6, 14, 6), 10)
        col = vbox(spacing=0)
        tl = label(title, "rowTitle")
        tl.setMinimumWidth(10)
        col.addWidget(tl)
        if sub:
            col.addWidget(label(sub, "muted"))
        h.addLayout(col, 1)
        h.addWidget(label(num(count), "desc"))
        if action:
            text, cb = action
            b = button(text, "ghost")
            b.clicked.connect(lambda _=False: cb())
            h.addWidget(b)
        box.addWidget(row)

    def _tops(self, sn: dict):
        clear_layout(self.top_blk)
        for d, n in (sn.get("top_blocked") or [])[:8]:
            self._row(self.top_blk, d, n, (tr("ab.allow"), lambda dd=d: self.rule(dd, "allow")))
        if not sn.get("top_blocked"):
            self.top_blk.addWidget(label(tr("ab.nothing_yet"), "desc"))
        clear_layout(self.top_oth)
        clients = sn.get("top_clients") or []
        if len(clients) > 1:
            self.top_oth_title.setText(tr("ab.top_clients"))
            for ip, n in clients[:8]:
                self._row(self.top_oth, tr("ab.this_pc") if ip in ("127.0.0.1", "::1") else ip, n)
        else:
            self.top_oth_title.setText(tr("ab.top_allowed"))
            for d, n in (sn.get("top_allowed") or [])[:8]:
                self._row(self.top_oth, d, n, (tr("ab.block"), lambda dd=d: self.rule(dd, "block")))

    def _log_filter(self, i: int):
        self.log_flt = ("all", "blocked", "allowed")[i]
        self.refresh()

    def _fill_log(self, entries: list):
        clear_layout(self.log_box)
        if not entries:
            lb = label(tr("ab.log_empty"), "desc")
            lb.setContentsMargins(14, 4, 14, 8)
            self.log_box.addWidget(lb)
            return
        for e in entries[:20]:
            row = QFrame()
            row.setObjectName("row")
            h = hbox(row, (14, 4, 14, 4), 10)
            tl = label(time.strftime("%H:%M:%S", time.localtime(e["ts"])), "muted")
            tl.setFixedWidth(62)
            h.addWidget(tl)
            h.addWidget(label(e["name"], "rowTitle"), 1)
            h.addWidget(label(f"{e['type']} · {tr('ab.this_pc') if e['client'] in ('127.0.0.1', '::1') else e['client']}",
                              "muted"))
            st = e["status"]
            text = tr(f"ab.st.{st}")
            if st == "blocked" and e.get("src"):
                src = AB.LIST_BY_ID.get(e["src"], {}).get("name") or tr(f"ab.src.{e['src']}")
                text += f" · {src}"
            elif e.get("ms") is not None and st != "cache":
                text += " · " + tr("u.ms", v=round(e["ms"]))
            h.addWidget(badge(text, STATUS_BADGE.get(st, "muted")))
            b = button(tr("ab.allow") if st == "blocked" else tr("ab.block"), "ghost")
            b.clicked.connect(lambda _=False, d=e["name"], k="allow" if st == "blocked" else "block": self.rule(d, k))
            b.setFixedWidth(110)
            h.addWidget(b)
            self.log_box.addWidget(row)

    # ── дії ──
    def enable(self):
        if not Ask.ask(self, tr("ab.enable_t"), tr("ab.enable_q"), tr("ab.enable")):
            return
        RunDialog(self.main, tr("ab.enable_t"), lambda log, prog: self.ab.enable(log, prog)).exec()
        self.after_change()

    def disable(self):
        light = self.ab.mode == "light"
        if not Ask.ask(self, tr("ab.disable_t"), tr("ab.disable_q_light") if light else tr("ab.disable_q"),
                       tr("ab.disable"), "danger"):
            return
        self.main.run_quick(tr("nav.adblock"), lambda log, p: self.ab.disable(log), busy=self.btn_off,
                            ok_msg=tr("ab.disabled"), on_done=lambda _r: self.after_change())

    def after_change(self):
        self.last = {}
        self.fill_cfg()
        self.sync()
        self.refresh()
        self.main.refresh_all()

    def use_light(self, pid: str):
        prov = AB.LIGHT_BY_ID[pid]
        if not Ask.ask(self, prov["name"], tr("ab.light_q", name=prov["name"], ips=", ".join(prov["ips"])),
                       tr("net.dns.use")):
            return
        doh = self.sw_ldoh.isChecked()
        self.main.run_quick(prov["name"], lambda log, p: self.ab.set_light(pid, doh, log),
                            ok_msg=tr("ab.light_ok", name=prov["name"]), on_done=lambda _r: self.after_change())

    def pause_menu(self):
        st = self.last.get("status") or {}
        if st.get("paused_until"):
            self._pause(0)
            return
        m = QMenu(self)
        for sec, key in ((300, "ab.p5"), (1800, "ab.p30"), (3600, "ab.p60"), (4 * 3600, "ab.p240")):
            m.addAction(tr(key)).triggered.connect(lambda _=False, s=sec: self._pause(s))
        m.exec(self.btn_pause.mapToGlobal(self.btn_pause.rect().bottomLeft()))
        self.menu = m

    def _pause(self, sec: int):
        self.main.run_quick("pause", lambda log, p: self.ab.pause(sec), silent=True, on_done=lambda _r: self.refresh())
        self.main.toast(tr("ab.paused", m=sec // 60) if sec else tr("ab.resumed"), "warn" if sec else "ok")

    def rule(self, domain: str, kind: str):
        def done(_r):
            self.fill_cfg()
            self.refresh()
        self.main.run_quick(tr("ab.rules_t"), lambda log, p: self.ab.rule(domain, kind), silent=True, on_done=done)
        self.main.toast(tr("ab.allowed", d=domain) if kind == "allow" else tr("ab.blocked_d", d=domain))

    def save_rules(self):
        get = lambda k: [x.strip() for x in self.rule_edit[k].toPlainText().splitlines() if x.strip()]  # noqa: E731
        allow, block = get("allow"), get("block")
        self.main.run_quick(tr("ab.rules_t"), lambda log, p: self.ab.save(allow=allow, block=block),
                            ok_msg=tr("ab.rules_saved", a=len(allow), b=len(block)), on_done=lambda _r: self.refresh())

    def set_opt(self, **kw):
        cfg = self.ab.cfg()
        if all(cfg.get(k) == v for k, v in kw.items()):
            return
        if kw.get("lan") and not Ask.ask(self, tr("ab.s.lan"), tr("ab.lan_q"), tr("btn.apply")):
            self.sw["lan"].set_quiet(False)
            return
        self.main.run_quick(tr("ab.set_t"), lambda log, p: self.ab.save(**kw), silent=True,
                            on_done=lambda _r: self.refresh())
        self.main.toast(tr("ab.saved"))

    def _lists_changed(self):
        cfg = self.ab.cfg()
        chosen = sorted(lid for lid, r in self.list_rows.items() if r.check.isChecked())
        self.btn_lists.setEnabled(chosen != sorted(cfg["lists"]) and bool(chosen))
        self._lists_state()

    def save_lists(self):
        ids = [lid for lid, r in self.list_rows.items() if r.check.isChecked()]
        if not ids:
            return
        RunDialog(self.main, tr("ab.lists_t"), lambda log, prog: self.ab.apply_lists(ids, log, prog)).exec()
        self.fill_cfg()
        self.refresh()

    def update_lists(self):
        RunDialog(self.main, tr("ab.lists_update"), lambda log, prog: self.ab.update_lists(log, prog)).exec()
        self.fill_cfg()
        self.refresh()
