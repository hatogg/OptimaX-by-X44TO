"""
OptimaX — сторінка Hardware Center: діагностика й тестування заліза в одному місці.

Розділи (будуються, коли їх уперше відкрити): огляд, відомості про залізо, процесор, відеокарта, відеопам'ять,
оперативна пам'ять, диски, монітор, ноутбук, периферія, стрес-тести, фонові процеси, діагностика Windows, перевірка
перед покупкою, звіти, FPS-оверлей.

Логіка тестів — у hwtests.py, vramtest.py, storagehealth.py, hwinfo.py (і в наявних gpubench, gpuselect, crashlog,
hardware). Тут — лише інтерфейс: запуск і зупинка, прогрес, датчики під час тесту, аварійна зупинка, результат
(PASS / WARN / FAIL / SKIPPED / N/A) і ручні позначки для візуальних перевірок.
"""
from __future__ import annotations

import os
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QFont
from PyQt6.QtWidgets import QWidget, QFrame, QGridLayout, QProgressBar, QStackedWidget, QDialog, QMenu

import engine as E
import features as F
import hwtests as HT
from i18n import tr
from pages_extra import page_body, log_strip
from ui_kit import (T, label, button, card, vbox, hbox, badge, style_badge, dot, scroller, page_header, clear_layout,
                    section_card, Segmented, Ask, Spark, Worker, LOG, chip)

SECTIONS = ("overview", "info", "cpu", "gpu", "vram", "ram", "storage", "display", "laptop", "peripherals", "stress",
            "procs", "windiag", "inspect", "reports", "overlay")
STATUS_KIND = {HT.PASS: "ok", HT.WARN: "warn", HT.FAIL: "bad", HT.SKIPPED: "muted", HT.NA: "muted"}
LEVEL_COLOR = {HT.FAIL: "bad", HT.WARN: "warn", "info": "sub"}


def status_badge(status: str) -> QWidget:
    return badge(tr(f"hwc.st.{status}"), STATUS_KIND.get(status, "muted"))


def finding_text(f) -> str:
    level, key, kw = f
    return tr(key, **(kw or {}))


def value_text(v) -> str:
    if v is None or v == "" or v == []:
        return tr("hwc.na")
    return str(v)


class KV(QWidget):
    """Сітка «назва — значення» з «н/д» для невідомого."""

    def __init__(self, cols: int = 2):
        super().__init__()
        self.cols = cols
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(14, 4, 14, 6)
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(6)

    def set(self, rows) -> None:
        clear_layout(self.grid)
        for i, (k, v) in enumerate(rows):
            r, c = divmod(i, self.cols)
            self.grid.addWidget(label(tr(k) if "." in str(k) and not str(k).startswith(" ") else str(k), "muted"),
                                r, c * 2)
            val = label(value_text(v), "rowTitle", wrap=True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.grid.addWidget(val, r, c * 2 + 1)
        for c in range(self.cols):
            self.grid.setColumnStretch(c * 2 + 1, 1)


class ResultView(QWidget):
    """Підсумок тесту: статус, короткий висновок, знахідки, показники, графіки."""

    def __init__(self, charts: tuple = ()):
        super().__init__()
        v = vbox(self, spacing=6)
        head = hbox(margins=(14, 4, 14, 0), spacing=10)
        self.badge = badge("", "muted")
        head.addWidget(self.badge)
        self.summary = label("", "h3", wrap=True)
        head.addWidget(self.summary, 1)
        v.addLayout(head)
        self.when = label("", "muted")
        self.when.setContentsMargins(14, 0, 14, 0)
        v.addWidget(self.when)
        self.findings = vbox(margins=(14, 2, 14, 2), spacing=4)
        v.addLayout(self.findings)
        self.kv = KV(2)
        v.addWidget(self.kv)
        self.charts = {}
        for key, unit, color in charts:
            sp = Spark(80, unit)
            sp.hide()
            self.charts[key] = (sp, color)
            cw = QWidget()
            cv = vbox(cw, (14, 0, 14, 0), 2)
            cv.addWidget(label(tr(f"hwc.chart.{key}"), "muted"))
            cv.addWidget(sp)
            cw.hide()
            self.charts[key] = (sp, color, cw)
            v.addWidget(cw)
        self.hide()

    def set(self, r: dict) -> None:
        if not r:
            self.hide()
            return
        self.show()
        st = r.get("status", HT.NA)
        style_badge(self.badge, tr(f"hwc.st.{st}"), STATUS_KIND.get(st, "muted"))
        self.summary.setText(r.get("summary") or "")
        tested = "" if r.get("hw_tested", True) else " · " + tr("hwc.mock")
        self.when.setText(time.strftime("%d.%m.%Y %H:%M", time.localtime(r.get("ts") or time.time())) + tested)
        clear_layout(self.findings)
        for f in r.get("findings") or []:
            row = hbox(spacing=8)
            row.addWidget(dot(T[LEVEL_COLOR.get(f[0], "sub")]), 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(finding_text(f), "desc", wrap=True), 1)
            self.findings.addLayout(row)
        self.kv.set(r.get("rows") or [])
        series = r.get("series") or {}
        for key, (sp, color, cw) in self.charts.items():
            vals = [x for x in series.get(key) or [] if x is not None]
            sp.set_series([(vals, T[color])])
            cw.setVisible(bool(vals))


class Progress(QWidget):
    """Підпис, смужка й «Зупинити» під час тесту."""

    def __init__(self, on_stop):
        super().__init__()
        v = vbox(self, (14, 4, 14, 6), 6)
        h = hbox(spacing=10)
        self.text = label("", "desc", wrap=True)
        h.addWidget(self.text, 1)
        self.btn = button(tr("run.stop"), "ghost", on_stop)
        h.addWidget(self.btn)
        v.addLayout(h)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        v.addWidget(self.bar)
        self.hide()

    def set(self, text: str, done: float = None, total: float = None) -> None:
        self.text.setText(text)
        if total:
            self.bar.setRange(0, int(total))
            self.bar.setValue(int(min(done or 0, total)))
        else:
            self.bar.setRange(0, 0)


class TestBox:
    """Один запущений тест у розділі: процес (hwtests / vramtest / gpubench), датчики раз на секунду, аварійна
    зупинка за температурою, підсумок у ResultView і в історію Hardware Center."""

    def __init__(self, page, result_view: ResultView, progress: Progress, start_btn):
        self.page = page
        self.view = result_view
        self.prog = progress
        self.start_btn = start_btn
        self.runs = {}
        self.sensors = None
        self.samples = []
        self.finish_fn = None
        self.describe = None
        self.danger = ""
        self.timer = QTimer(page)
        self.timer.timeout.connect(self.tick)
        self.next_sensor = 0.0

    @property
    def busy(self) -> bool:
        return bool(self.runs)

    def start(self, runs: dict, finish_fn, describe=None, sensors: bool = True, gpu: bool = False) -> None:
        """runs — {назва: запущений тест}; finish_fn(стани, датчики) -> result; describe(стани) -> рядок прогресу."""
        self.runs = runs
        self.finish_fn = finish_fn
        self.describe = describe
        self.danger = ""
        self.samples = []
        self.sensors = HT.Sensors(self.page.main.hw or {}, gpu=gpu) if sensors else None
        self.start_btn.setEnabled(False)
        self.prog.show()
        self.prog.set(tr("hwc.p.start"))
        self.page.busy_sections.add(id(self))
        self.timer.start(500)

    def stop(self) -> None:
        for r in list(self.runs.values()):
            try:
                r.stop()
            except Exception:
                pass

    def tick(self) -> None:
        states = {k: r.poll() for k, r in self.runs.items()}
        running = any(s.get("state") in ("starting", "allocating", "running", "warmup") for s in states.values())
        if self.sensors and running and time.time() >= self.next_sensor:
            self.next_sensor = time.time() + 1.0
            self.sensors.sample(1.0)
            self.samples = self.sensors.samples
            d = HT.danger(self.samples)
            if d and not self.danger:
                self.danger = d
                LOG.write(tr("hwc.log.danger", what=tr(f"hwc.dev.{d}")))
                self.stop()
        if self.describe:
            text, done, total = self.describe(states, self.samples[-1] if self.samples else {})
            self.prog.set(text, done, total)
        if running:
            return
        self.timer.stop()
        for k, r in self.runs.items():
            try:
                r.cleanup()
            except Exception:
                pass
        if self.sensors:
            self.sensors.close()
        res = self.finish_fn(states, self.samples, self.danger)
        self.runs = {}
        self.page.busy_sections.discard(id(self))
        self.prog.hide()
        self.start_btn.setEnabled(True)
        if res:
            HT.save(F.CFG, res)
            self.view.set(res)
            LOG.write(tr("hwc.log.done", test=tr(f"hwc.t.{res['test']}"), st=tr(f"hwc.st.{res['status']}")))
            self.page.main.toast(tr("hwc.log.done", test=tr(f"hwc.t.{res['test']}"), st=tr(f"hwc.st.{res['status']}")),
                                 {HT.PASS: "ok", HT.FAIL: "bad"}.get(res["status"], "warn"))
            self.page.refresh_overview()


# ───────────────────────── сторінка ─────────────────────────
class HwCenterPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.built = {}
        self.busy_sections = set()
        self.boxes = {}
        self.cache = {}
        outer = vbox(self)
        outer.addWidget(page_header(tr("nav.hwc"), tr("hwc.sub")))
        nav = QWidget()
        g = QGridLayout(nav)
        g.setContentsMargins(32, 0, 32, 8)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(6)
        self.chips = {}
        for i, key in enumerate(SECTIONS):
            c = chip(tr(f"hwc.sec.{key}"))
            c.clicked.connect(lambda _=False, k=key: self.show_section(k))
            self.chips[key] = c
            g.addWidget(c, i // 8, i % 8)
        outer.addWidget(nav)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        log_strip(outer, 80)
        self.current = None
        self.show_section("overview")

    def on_show(self):
        if self.current == "overview":
            self.refresh_overview()
        page = self.built.get(self.current)
        if page is not None and hasattr(page, "_on_show"):
            page._on_show()

    def set_hw(self, hw: dict) -> None:
        if self.current == "overview":
            self.refresh_overview()

    def show_section(self, key: str) -> None:
        for k, c in self.chips.items():
            c.setChecked(k == key)
        if key not in self.built:
            body, v = page_body()
            getattr(self, f"_build_{key}")(v)
            v.addStretch()
            w = scroller(body)
            self.built[key] = w
            self.stack.addWidget(w)
        self.current = key
        self.stack.setCurrentWidget(self.built[key])
        hook = getattr(self, f"_show_{key}", None)
        if hook:
            hook()

    # ── спільне ──
    def last(self, test: str) -> dict:
        return (F.CFG["hwc_last"] or {}).get(test) or {}

    def section(self, v, title: str, sub: str = None):
        c, cv = section_card(title, sub)
        v.addWidget(c)
        return c, cv

    def test_area(self, cv, test_ids, charts=()):
        """Прогрес + результат останнього тесту в картці."""
        prog = Progress(lambda: self.boxes.get(id(prog)) and self.boxes[id(prog)].stop())
        cv.addWidget(prog)
        view = ResultView(charts)
        cv.addWidget(view)
        for t in test_ids:
            if self.last(t):
                view.set(self.last(t))
                break
        return prog, view

    def make_box(self, prog: Progress, view: ResultView, btn) -> TestBox:
        box = TestBox(self, view, prog, btn)
        self.boxes[id(prog)] = box
        return box

    def run_bg(self, job, done) -> Worker:
        w = Worker(job)
        w.log.connect(LOG.write)
        w.result.connect(done)
        self.main._workers.add(w)
        w.finished.connect(lambda: self.main._workers.discard(w))
        w.start()
        return w

    def save_manual(self, test: str, status: str, note: str = "") -> dict:
        res = HT.result(test, status, tr(f"hwc.manual.{status}"), manual=True, note=note,
                        rows=[("hwc.r.manual", tr("hwc.yes"))])
        res["hw_tested"] = True
        HT.save(F.CFG, res)
        self.refresh_overview()
        return res

    def ask_mark(self, test: str, view: ResultView = None) -> None:
        """Ручна позначка візуальної перевірки: усе гаразд / є проблема / пропустити."""
        m = QMenu(self)
        for st in (HT.PASS, HT.FAIL, HT.SKIPPED):
            a = m.addAction(tr(f"hwc.mark.{st}"))
            a.triggered.connect(lambda _=False, s=st: view.set(self.save_manual(test, s)) if view else
                                self.save_manual(test, s))
        m.exec(self.cursor().pos())
        self.menu = m

    # ───────────────────────── Огляд ─────────────────────────
    OVERVIEW = (("info", ("info",)), ("cpu", ("cpu_multi", "cpu_stress", "cpu_single")), ("gpu", ("gpu",)),
                ("vram", ("vram",)), ("ram", ("ram",)), ("storage", ("storage_health", "disk_bench", "disk_scan")),
                ("display", ("display_pixels",)), ("laptop", ("battery",)),
                ("peripherals", ("periph_keyboard", "periph_mouse", "periph_speakers", "periph_camera", "periph_mic")),
                ("stress", ("stress_combined",)), ("windiag", ("windiag",)))

    def _build_overview(self, v):
        c, cv = self.section(v, tr("hwc.ov.title"), tr("hwc.ov.sub"))
        self.ov_grid = QGridLayout()
        self.ov_grid.setContentsMargins(14, 4, 14, 8)
        self.ov_grid.setHorizontalSpacing(10)
        self.ov_grid.setVerticalSpacing(10)
        cv.addLayout(self.ov_grid)
        bh = hbox(margins=(14, 4, 14, 8), spacing=8)
        bh.addWidget(button(tr("hwc.ov.inspect"), "primary", lambda: self.show_section("inspect")))
        bh.addWidget(button(tr("hwc.ov.report"), None, lambda: self.show_section("reports")))
        bh.addStretch()
        cv.addLayout(bh)
        self.refresh_overview()

    def refresh_overview(self):
        if not hasattr(self, "ov_grid"):
            return
        clear_layout(self.ov_grid)
        for i, (sec, tests) in enumerate(self.OVERVIEW):
            res = [self.last(t) for t in tests if self.last(t)]
            st = HT.worst([r["status"] for r in res]) if res else None
            tile = card("cardAccent" if st in (HT.FAIL, HT.WARN) else "card")
            tv = vbox(tile, (14, 12, 14, 12), 6)
            th = hbox(spacing=8)
            th.addWidget(label(tr(f"hwc.sec.{sec}"), "h3"), 1)
            th.addWidget(status_badge(st) if st else badge(tr("hwc.ov.not_run"), "muted"))
            tv.addLayout(th)
            when = max((r.get("ts") or 0 for r in res), default=0)
            tv.addWidget(label(time.strftime("%d.%m %H:%M", time.localtime(when)) if when else tr("hwc.ov.never"),
                               "muted"))
            tv.addWidget(button(tr("hwc.ov.open"), "ghost", lambda s=sec: self.show_section(s)), 0,
                         Qt.AlignmentFlag.AlignLeft)
            self.ov_grid.addWidget(tile, i // 3, i % 3)

    # ───────────────────────── Відомості про залізо ─────────────────────────
    def _build_info(self, v):
        top = hbox(spacing=8)
        self.info_btn = button(tr("hwc.info.refresh"), None, lambda: self.load_info(True))
        top.addWidget(self.info_btn)
        top.addWidget(label(tr("hwc.info.note"), "muted", wrap=True), 1)
        v.addLayout(top)
        self.info_box = vbox(spacing=12)
        v.addLayout(self.info_box)
        self.load_info(False)

    def load_info(self, force: bool):
        if self.cache.get("info") and not force:
            self.fill_info(self.cache["info"])
            return
        import hwinfo as HI
        self.info_btn.setEnabled(False)
        self.info_btn.setText(tr("btn.working"))
        hw = self.main.hw or {}
        self.run_bg(lambda log, p: HI.collect(hw), self.fill_info)

    def fill_info(self, d):
        self.info_btn.setEnabled(True)
        self.info_btn.setText(tr("hwc.info.refresh"))
        if not isinstance(d, dict) or d.get("error"):
            return
        self.cache["info"] = d
        res = HT.result("info", HT.PASS, tr("hwc.info.collected"))
        HT.save(F.CFG, res)
        clear_layout(self.info_box)
        cpu, ram, board, bios = d["cpu"], d["ram"], d["board"], d["bios"]
        mhz = f"{cpu['mhz']} {tr('hwc.u.mhz')}" if cpu.get("mhz") else None
        cores = f"{cpu.get('cores')} / {cpu.get('threads')}" if cpu.get("cores") else None
        hybrid = f"{cpu['p_cores']}P + {cpu['e_cores']}E" if cpu.get("e_cores") else None
        self._info_card(tr("hwc.i.cpu"), [("hwc.i.model", cpu.get("name")), ("hwc.i.arch", cpu.get("arch")),
                                          ("hwc.i.cores", cores), ("hwc.i.hybrid", hybrid), ("hwc.i.base", mhz),
                                          ("hwc.i.sockets", cpu.get("sockets")),
                                          ("hwc.i.features", ", ".join(cpu.get("features") or []))])
        for g in d.get("gpus") or []:
            self._info_card(tr("hwc.i.gpu"), [
                ("hwc.i.model", g.get("name")), ("hwc.i.vendor", (g.get("vendor") or "").upper() or None),
                ("hwc.i.kind", tr(f"gs.kind.{g['kind']}") if g.get("kind") else None),
                ("hwc.i.vram", f"{g['vram_gb']} GB" if g.get("vram_gb") else None),
                ("hwc.i.driver_date", g.get("driver_date")),
                ("hwc.i.display", tr("hwc.yes") if g.get("display") else tr("hwc.no") if g.get("display") is False else None)])
        rows = [("hwc.i.total", f"{ram['total_gb']} GB" if ram.get("total_gb") else None),
                ("hwc.i.used", f"{ram['used_gb']} GB" if ram.get("used_gb") is not None else None),
                ("hwc.i.type", ram.get("type")),
                ("hwc.i.speed", f"{ram['speed']} MT/s" + (f" ({tr('hwc.i.max')} {ram['max_speed']})"
                                                          if ram.get("max_speed") and ram["max_speed"] != ram["speed"]
                                                          else "") if ram.get("speed") else None),
                ("hwc.i.slots", f"{len(ram.get('modules') or [])} / {ram['slots']}" if ram.get("slots") else None)]
        for m in ram.get("modules") or []:
            rows.append((f"  {m.get('slot') or '?'}", " · ".join(str(x) for x in (
                f"{m['mb'] // 1024} GB" if m.get("mb") else tr("hwc.i.empty"), m.get("type"), m.get("form"),
                f"{m['conf'] or m['speed']} MT/s" if (m.get("conf") or m.get("speed")) else "", m.get("vendor"),
                m.get("part")) if x)))
        self._info_card(tr("hwc.i.ram"), rows)
        self._info_card(tr("hwc.i.board"), [
            ("hwc.i.vendor", board.get("vendor")), ("hwc.i.model", board.get("model")),
            ("hwc.i.system", board.get("system")), ("hwc.i.bios", " ".join(x for x in (bios.get("vendor"),
                                                                                       bios.get("version")) if x) or None),
            ("hwc.i.bios_date", bios.get("date")), ("hwc.i.firmware", bios.get("type")),
            ("hwc.i.secure_boot", tr("hwc.yes") if bios.get("secure_boot") else tr("hwc.no")
             if bios.get("secure_boot") is False else None)])
        for dk in d.get("disks") or []:
            self._info_card(tr("hwc.i.disk"), [
                ("hwc.i.model", dk.get("name")), ("hwc.i.type", dk.get("media")), ("hwc.i.bus", dk.get("bus")),
                ("hwc.i.size", f"{dk['size_gb']} GB" if dk.get("size_gb") else None),
                ("hwc.i.letters", ", ".join(f"{x}:" for x in dk.get("letters") or []) or None),
                ("hwc.i.health", dk.get("health"))])
        for n in d.get("net") or []:
            self._info_card(tr("hwc.i.net"), [("hwc.i.model", n.get("name")), ("hwc.i.status", n.get("status")),
                                              ("hwc.i.link", n.get("speed")), ("hwc.i.media", n.get("media")),
                                              ("hwc.i.driver", n.get("driver"))])
        for mo in d.get("monitors") or []:
            self._info_card(tr("hwc.i.monitor"), self.monitor_rows(mo))
        for b in d.get("battery") or []:
            self._info_card(tr("hwc.i.battery"), self.battery_rows(b))
        os_ = d.get("os") or {}
        self._info_card(tr("hwc.i.os"), [("hwc.i.model", os_.get("name")), ("hwc.i.build", os_.get("build"))])

    def _info_card(self, title: str, rows):
        c, cv = section_card(title)
        kv = KV(2)
        kv.set(rows)
        cv.addWidget(kv)
        self.info_box.addWidget(c)

    @staticmethod
    def monitor_rows(mo: dict) -> list:
        size = f"{mo['diag_in']}″ ({mo['width_cm']}×{mo['height_cm']} cm)" if mo.get("diag_in") else None
        native = f"{mo['native'][0]}×{mo['native'][1]} @ {mo.get('native_hz')} Hz" if mo.get("native") else None
        rng = f"{mo['min_hz']}–{mo['max_hz']} Hz" if mo.get("max_hz") else None
        gam = tr("hwc.i.gamut_v", s=mo["srgb"], p=mo["p3"]) if mo.get("srgb") else None
        return [("hwc.i.model", mo.get("name") or f"{mo.get('manufacturer')} {mo.get('product')}"),
                ("hwc.i.vendor", mo.get("manufacturer")), ("hwc.i.year", mo.get("year")), ("hwc.i.size", size),
                ("hwc.i.native", native), ("hwc.i.range", rng), ("hwc.i.gamut", gam), ("hwc.i.edid", mo.get("version"))]

    @staticmethod
    def battery_rows(b: dict) -> list:
        return [("hwc.i.model", b.get("name")), ("hwc.i.design", f"{b['design']:,} mWh".replace(",", " ")
                                                 if b.get("design") else None),
                ("hwc.i.full", f"{b['full']:,} mWh".replace(",", " ") if b.get("full") else None),
                ("hwc.i.wear", f"{b['wear']:.0f}%" if b.get("design") else None), ("hwc.i.cycles", b.get("cycles") or None)]

    # ───────────────────────── Процесор ─────────────────────────
    def _build_cpu(self, v):
        c, cv = self.section(v, tr("hwc.cpu.title"), tr("hwc.cpu.sub"))
        r1 = hbox(margins=(14, 4, 14, 4), spacing=10)
        r1.addWidget(label(tr("gb.mode"), "desc"))
        self.cpu_mode = Segmented([tr("hwc.cpu.single"), tr("hwc.cpu.multi"), tr("hwc.cpu.stress")])
        self.cpu_mode_i = 1
        self.cpu_mode.select(1)
        self.cpu_mode.changed.connect(self._cpu_mode)
        r1.addWidget(self.cpu_mode)
        r1.addStretch()
        cv.addLayout(r1)
        r2 = hbox(margins=(14, 0, 14, 4), spacing=10)
        self.cpu_min_l = label(tr("gb.minutes"), "desc")
        r2.addWidget(self.cpu_min_l)
        self.cpu_min = Segmented([tr("u.min_n", n=m) for m in HT.CPU_MINUTES])
        self.cpu_min_i = 1
        self.cpu_min.select(1)
        self.cpu_min.changed.connect(lambda i: setattr(self, "cpu_min_i", i))
        r2.addWidget(self.cpu_min)
        r2.addSpacing(8)
        self.cpu_int_l = label(tr("hwc.cpu.intensity"), "desc")
        r2.addWidget(self.cpu_int_l)
        self.cpu_int = Segmented([tr("hwc.cpu.full"), tr("hwc.cpu.half")])
        self.cpu_int_i = 0
        self.cpu_int.changed.connect(lambda i: setattr(self, "cpu_int_i", i))
        r2.addWidget(self.cpu_int)
        r2.addStretch()
        self.cpu_btn = button(tr("hwc.start"), "primary", self.start_cpu)
        r2.addWidget(self.cpu_btn)
        cv.addLayout(r2)
        cv.addWidget(self._note(tr("hwc.cpu.note")))
        prog, view = self.test_area(cv, ("cpu_stress", "cpu_multi", "cpu_single"),
                                    charts=(("ops", "op/s", "acc"), ("temp", "°C", "warn"), ("mhz", "MHz", "acc2")))
        self.cpu_box = self.make_box(prog, view, self.cpu_btn)
        self._cpu_mode(1)

    def _note(self, text: str):
        n = label(text, "desc", wrap=True)
        n.setContentsMargins(14, 0, 14, 4)
        return n

    def _cpu_mode(self, i: int):
        self.cpu_mode_i = i
        for w in (self.cpu_min_l, self.cpu_min, self.cpu_int_l, self.cpu_int):
            w.setVisible(i == 2)

    def start_cpu(self):
        if self.cpu_box.busy:
            return
        mode = ("single", "multi", "stress")[self.cpu_mode_i]
        threads = os.cpu_count() or 1
        seconds = HT.SCORE_SECONDS
        if mode == "single":
            threads = 1
        elif mode == "stress":
            minutes = HT.CPU_MINUTES[self.cpu_min_i]
            if not Ask.ask(self, tr("hwc.warn_t"), tr("hwc.warn_q", m=minutes), tr("hwc.start"), "danger"):
                return
            seconds = minutes * 60
            if self.cpu_int_i == 1:
                threads = max(1, threads // 2)
        LOG.write(f"[►] {tr(f'hwc.t.cpu_{mode}')}: {threads} × {seconds} {tr('hwc.u.s')}")
        run = HT.start("cpu", dict(threads=threads, seconds=seconds))
        hw = self.main.hw or {}

        def describe(states, s):
            st = states.get("cpu") or {}
            parts = [tr("hwc.p.cpu", t=int(st.get("t") or 0), d=seconds, rate=st.get("rate") or 0)]
            if s.get("temp") is not None:
                parts.append(f"{s['temp']:.0f} °C")
            if s.get("mhz"):
                parts.append(f"{s['mhz']} {tr('hwc.u.mhz')}")
            if st.get("errors"):
                parts.append(tr("hwc.p.errors", n=st["errors"]))
            return " · ".join(parts), st.get("t") or 0, seconds

        def finish(states, samples, danger):
            st = dict(states.get("cpu") or {})
            if danger:
                st["danger"] = danger
            return HT.cpu_result(st, samples, hw, mode)
        self.cpu_box.start({"cpu": run}, finish, describe)

    # ───────────────────────── Відеокарта ─────────────────────────
    def _build_gpu(self, v):
        c, cv = self.section(v, tr("hwc.gpu.title"), tr("hwc.gpu.sub"))
        self.gpu_kv = KV(1)
        cv.addWidget(self.gpu_kv)
        bh = hbox(margins=(14, 4, 14, 8), spacing=8)
        bh.addWidget(button(tr("hwc.gpu.open"), "primary", lambda: self.main.go("bench")))
        self.gpu_tdr_btn = button(tr("hwc.gpu.tdr"), None, self.load_tdr)
        bh.addWidget(self.gpu_tdr_btn)
        bh.addStretch()
        cv.addLayout(bh)
        self.gpu_view = ResultView((("fps", "fps", "acc"), ("temp", "°C", "warn")))
        cv.addWidget(self.gpu_view)

    def _show_gpu(self):
        import gpuselect as GS
        ads = GS.adapters(GS.cached_probe() or {})
        rows = [(tr("gs.gpu"), GS.describe(a)) for a in ads] or \
            [(tr("gs.gpu"), ", ".join(n for n, _, _ in (self.main.hw or {}).get("gpus") or []) or None)]
        self.gpu_kv.set(rows)
        last = (F.CFG["bench"] or [{}])[-1] if F.CFG["bench"] else {}
        if last:
            self.gpu_view.set(self.gpu_result(last))

    @staticmethod
    def gpu_result(b: dict) -> dict:
        return HT.gpu_bench_result(b)

    def load_tdr(self):
        import crashlog as CL
        self.gpu_tdr_btn.setEnabled(False)

        def done(res):
            self.gpu_tdr_btn.setEnabled(True)
            if not isinstance(res, dict):
                return
            g = res.get("gpu") or {}
            text = tr("hwc.gpu.tdr_v", n=g.get("n", 0), d=CL.DAYS) if isinstance(g, dict) else str(g)
            Ask.info(self, tr("hwc.gpu.tdr"), text)

        def job(log, p):
            ev = CL.read_events()
            return {"gpu": CL.gpu_resets(ev)}
        self.run_bg(job, done)

    # ───────────────────────── Відеопам'ять ─────────────────────────
    def _build_vram(self, v):
        import vramtest as VT
        c, cv = self.section(v, tr("hwc.vram.title"), tr("hwc.vram.sub"))
        r = hbox(margins=(14, 4, 14, 4), spacing=10)
        r.addWidget(label(tr("hwc.vram.size"), "desc"))
        self.vram_pct = Segmented([f"{p}%" for p in VT.CHOICES])
        self.vram_pct_i = 1
        self.vram_pct.select(1)
        self.vram_pct.changed.connect(lambda i: setattr(self, "vram_pct_i", i))
        r.addWidget(self.vram_pct)
        r.addStretch()
        self.vram_btn = button(tr("hwc.start"), "primary", self.start_vram)
        r.addWidget(self.vram_btn)
        cv.addLayout(r)
        self.vram_gpu = label("", "desc", wrap=True)
        self.vram_gpu.setContentsMargins(14, 0, 14, 0)
        cv.addWidget(self.vram_gpu)
        cv.addWidget(self._note(tr("hwc.vram.note")))
        prog, view = self.test_area(cv, ("vram",))
        self.vram_box = self.make_box(prog, view, self.vram_btn)

    def _show_vram(self):
        p = self.gpu_plan()
        self.vram_gpu.setText(tr("hwc.vram.on", gpu=p.get("name")) if p.get("name") else "")

    def gpu_plan(self) -> dict:
        import gpuselect as GS
        p = GS.selection(self.main.hw or {})
        return p if p.get("name") else {}

    def start_vram(self):
        import vramtest as VT
        if self.vram_box.busy:
            return
        p = self.gpu_plan()
        hw = self.main.hw or {}
        vram_mb = 0
        for n, vr, _ in hw.get("gpus") or []:
            if not p or n == p.get("name"):
                vram_mb = int(vr * 1024)
                break
        run = VT.start(VT.CHOICES[self.vram_pct_i], p or None, vram_mb, p.get("kind") == "igpu")

        def describe(states, s):
            st = states.get("vram") or {}
            if st.get("state") == "allocating":
                return tr("hwc.p.alloc", mb=st.get("alloc_mb", 0)), None, None
            return tr("hwc.p.vram", p=st.get("pattern", ""), mb=st.get("mb", 0), e=st.get("errors", 0)), \
                st.get("done", 0), st.get("total") or None

        self.vram_box.start({"vram": run}, lambda states, smp, d: VT.vram_result(states.get("vram") or {}, p),
                            describe, sensors=False)

    # ───────────────────────── Оперативна пам'ять ─────────────────────────
    def _build_ram(self, v):
        c, cv = self.section(v, tr("hwc.ram.title"), tr("hwc.ram.sub"))
        r = hbox(margins=(14, 4, 14, 4), spacing=10)
        r.addWidget(label(tr("hwc.ram.size"), "desc"))
        self.ram_pct = Segmented([f"{p}%" for p in HT.RAM_CHOICES])
        self.ram_pct_i = 1
        self.ram_pct.select(1)
        self.ram_pct.changed.connect(self._ram_pct)
        r.addWidget(self.ram_pct)
        self.ram_plan_l = label("", "desc")
        r.addWidget(self.ram_plan_l)
        r.addStretch()
        self.ram_btn = button(tr("hwc.start"), "primary", self.start_ram)
        r.addWidget(self.ram_btn)
        cv.addLayout(r)
        cv.addWidget(self._note(tr("hwc.ram.note")))
        bh = hbox(margins=(14, 0, 14, 6), spacing=8)
        bh.addWidget(button(tr("hwc.ram.mdsched"), None, self.memtest))
        bh.addStretch()
        cv.addLayout(bh)
        prog, view = self.test_area(cv, ("ram",))
        self.ram_box = self.make_box(prog, view, self.ram_btn)
        self._ram_pct(1)

    def _ram_avail(self) -> float:
        return HT.mem_available_mb() or float((self.main.hw or {}).get("ram_gb") or 8) * 1024 * 0.5

    def _ram_pct(self, i: int):
        self.ram_pct_i = i
        mb = HT.ram_plan(self._ram_avail(), HT.RAM_CHOICES[i])
        self.ram_plan_l.setText(tr("hwc.ram.plan", mb=mb) if mb else tr("hwc.ram.too_little"))

    def memtest(self):
        import crashlog as CL
        if Ask.ask(self, tr("hwc.ram.mdsched"), tr("hwc.ram.mdsched_q"), tr("btn.continue")):
            self.main.run_quick(tr("hwc.ram.mdsched"), lambda log, p: CL.start_memtest(log))

    def start_ram(self):
        if self.ram_box.busy:
            return
        avail = self._ram_avail()
        mb = HT.ram_plan(avail, HT.RAM_CHOICES[self.ram_pct_i])
        if not mb:
            Ask.info(self, tr("hwc.ram.title"), tr("hwc.ram.too_little"))
            return
        run = HT.start("ram", dict(mb=mb))
        hw = self.main.hw or {}

        def describe(states, s):
            st = states.get("ram") or {}
            if st.get("state") == "allocating":
                return tr("hwc.p.alloc", mb=mb), None, None
            return tr("hwc.p.ram", p=st.get("pattern", ""), d=st.get("done_mb", 0), t=st.get("total_mb", 0),
                      e=st.get("errors", 0)), st.get("done_mb", 0), st.get("total_mb") or None

        self.ram_box.start({"ram": run}, lambda states, smp, d: HT.ram_result(states.get("ram") or {}, hw, avail),
                           describe, sensors=False)

    # ───────────────────────── Диски ─────────────────────────
    def _build_storage(self, v):
        top = hbox(spacing=8)
        self.sh_btn = button(tr("hwc.sh.check"), "primary", self.load_storage)
        top.addWidget(self.sh_btn)
        top.addWidget(label(tr("hwc.sh.note"), "muted", wrap=True), 1)
        v.addLayout(top)
        self.sh_box = vbox(spacing=12)
        v.addLayout(self.sh_box)
        c, cv = self.section(v, tr("hwc.db.title"), tr("hwc.db.sub"))
        r = hbox(margins=(14, 4, 14, 4), spacing=10)
        r.addWidget(label(tr("hwc.db.disk"), "desc"))
        self.db_disk_btn = button("", None, self._disk_menu)
        r.addWidget(self.db_disk_btn)
        r.addWidget(label(tr("hwc.db.size"), "desc"))
        self.db_size = Segmented([f"{s} MB" if s < 1024 else f"{s // 1024} GB" for s in HT.DISK_SIZES_MB])
        self.db_size_i = 0
        self.db_size.changed.connect(lambda i: setattr(self, "db_size_i", i))
        r.addWidget(self.db_size)
        r.addStretch()
        cv.addLayout(r)
        r2 = hbox(margins=(14, 0, 14, 4), spacing=8)
        self.db_btn = button(tr("hwc.db.start"), "primary", self.start_disk)
        r2.addWidget(self.db_btn)
        self.scan_btn = button(tr("hwc.db.scan"), None, self.start_scan)
        r2.addWidget(self.scan_btn)
        self.fs_btn = button(tr("hwc.db.chkdsk"), None, self.chkdsk)
        r2.addWidget(self.fs_btn)
        r2.addStretch()
        cv.addLayout(r2)
        cv.addWidget(self._note(tr("hwc.db.note")))
        prog, view = self.test_area(cv, ("disk_bench",))
        self.db_box = self.make_box(prog, view, self.db_btn)
        prog2, view2 = self.test_area(cv, ("disk_scan",))
        self.scan_box = self.make_box(prog2, view2, self.scan_btn)
        disks = [d for d in (self.main.hw or {}).get("disks") or [] if d.get("letters")]
        self.db_disk = disks[0] if disks else {}
        self._sync_disk()

    def _sync_disk(self):
        d = self.db_disk
        self.db_disk_btn.setText(f"{(d.get('letters') or ['?'])[0]}: · {d.get('name') or '?'}  ▾" if d else tr("hwc.na"))
        self.db_btn.setEnabled(bool(d))

    def _disk_menu(self):
        m = QMenu(self)
        for d in (self.main.hw or {}).get("disks") or []:
            for letter in d.get("letters") or []:
                a = m.addAction(f"{letter}: · {d.get('name')} ({d.get('media') or '?'})")
                a.triggered.connect(lambda _=False, dd=d, ll=letter: self._pick_disk(dd, ll))
        m.exec(self.db_disk_btn.mapToGlobal(self.db_disk_btn.rect().bottomLeft()))
        self.menu = m

    def _pick_disk(self, d: dict, letter: str):
        self.db_disk = dict(d, letters=[letter] + [x for x in d.get("letters") or [] if x != letter])
        self._sync_disk()

    def load_storage(self):
        import storagehealth as SH
        self.sh_btn.setEnabled(False)
        self.sh_btn.setText(tr("btn.working"))
        hw = self.main.hw or {}
        self.run_bg(lambda log, p: SH.check_all(hw), self.fill_storage)

    def fill_storage(self, disks):
        import storagehealth as SH
        self.sh_btn.setEnabled(True)
        self.sh_btn.setText(tr("hwc.sh.check"))
        if not isinstance(disks, list):
            return
        clear_layout(self.sh_box)
        HT.save(F.CFG, SH.health_result(disks))
        for d in disks:
            c, cv = section_card(d.get("name") or "?", " · ".join(x for x in (
                d.get("media"), d.get("bus"), f"{d['size_gb']} GB" if d.get("size_gb") else "",
                ", ".join(f"{x}:" for x in d.get("letters") or [])) if x))
            a = d["assess"]
            view = ResultView()
            view.set(HT.result("storage_health", a["status"], tr(f"sh.sum1.{a['status']}"), rows=d["rows"],
                               findings=a["findings"]))
            cv.addWidget(view)
            self.sh_box.addWidget(c)
        self.refresh_overview()

    def start_disk(self):
        if self.db_box.busy or not self.db_disk:
            return
        size = HT.DISK_SIZES_MB[self.db_size_i]
        letter = (self.db_disk.get("letters") or ["C"])[0]
        folder = HT.disk_target(letter)
        free = HT.disk_free_mb(folder)
        if not HT.disk_size_ok(free, size):
            Ask.info(self, tr("hwc.db.title"), tr("hwc.f.disk_space", err="", m=HT.DISK_FREE_MARGIN_MB))
            return
        if not Ask.ask(self, tr("hwc.db.title"), tr("hwc.db.q", path=folder, mb=size), tr("hwc.db.start")):
            return
        run = HT.start("disk", dict(dir=folder, mb=size))
        disk = self.db_disk

        def describe(states, s):
            st = states.get("disk") or {}
            return tr("hwc.p.disk", phase=tr(f"hwc.phase.{st.get('phase', 'prepare')}"), d=st.get("done_mb", 0),
                      t=st.get("total_mb", 0)), st.get("done_mb", 0), st.get("total_mb") or None

        def finish(states, smp, d):
            st = dict(states.get("disk") or {}, letter=letter)
            return HT.disk_result(st, disk)
        self.db_box.start({"disk": run}, finish, describe, sensors=False)

    def start_scan(self):
        if self.scan_box.busy or not self.db_disk:
            return
        d = self.db_disk
        if not Ask.ask(self, tr("hwc.db.scan"), tr("hwc.db.scan_q", name=d.get("name") or "?"), tr("hwc.start")):
            return
        dev = f"\\\\.\\PhysicalDrive{d.get('id')}"
        run = HT.start("disk", dict(mode="scan", device=dev, seconds=30, size=int((d.get("size_gb") or 0) * 1e9)))

        def describe(states, s):
            st = states.get("disk") or {}
            return tr("hwc.p.scan", n=st.get("reads", 0), e=st.get("read_errors", 0)), st.get("t") or 0, 30

        self.scan_box.start({"disk": run}, lambda states, smp, x: HT.scan_result(states.get("disk") or {}, d), describe,
                            sensors=False)

    def chkdsk(self):
        """chkdsk без ключів — перевірка лише для читання: нічого не виправляє й не планує на перезавантаження."""
        letter = (self.db_disk.get("letters") or ["C"])[0]
        if not Ask.ask(self, tr("hwc.db.chkdsk"), tr("hwc.db.chkdsk_q", d=letter), tr("btn.continue")):
            return

        def job(log, p):
            if not E.IS_WIN or E.DRY_RUN:
                log(f"  [dry-run] chkdsk {letter}:")
                return {"ok": 1, "rc": 0}
            rc, out = E.run(["chkdsk", f"{letter}:"], 1800, ro=True)
            for line in (out or "").splitlines()[-12:]:
                log("  " + line.strip())
            return {"ok": rc in (0,), "rc": rc}

        def done(res):
            rc = (res or {}).get("rc")
            st = HT.PASS if rc == 0 else HT.WARN if rc in (1, 2) else HT.NA
            r = HT.result("chkdsk", st, tr(f"hwc.db.chk.{st}"), rows=[("hwc.db.drive", f"{letter}:"),
                                                                     ("hwc.db.rc", rc)])
            HT.save(F.CFG, r)
        self.main.run_quick(tr("hwc.db.chkdsk"), job, busy=self.fs_btn, on_done=done)

    # ───────────────────────── Монітор ─────────────────────────
    def _build_display(self, v):
        c, cv = self.section(v, tr("hwc.disp.title"), tr("hwc.disp.sub"))
        self.disp_kv = KV(2)
        cv.addWidget(self.disp_kv)
        bh = hbox(margins=(14, 4, 14, 8), spacing=8)
        bh.addWidget(button(tr("hwc.disp.test"), "primary", self.color_test))
        bh.addWidget(button(tr("hwc.disp.mark"), None, lambda: self.ask_mark("display_pixels", self.disp_view)))
        bh.addStretch()
        cv.addLayout(bh)
        cv.addWidget(self._note(tr("hwc.disp.note")))
        self.disp_view = ResultView()
        cv.addWidget(self.disp_view)
        if self.last("display_pixels"):
            self.disp_view.set(self.last("display_pixels"))
        self.edid_box = vbox(spacing=10)
        v.addLayout(self.edid_box)

    def _show_display(self):
        rows = []
        for i, s in enumerate(QGuiApplication.screens()):
            g = s.geometry()
            dpr = s.devicePixelRatio()
            rows.append((tr("hwc.disp.screen", n=i + 1), f"{s.name()} · {int(g.width() * dpr)}×{int(g.height() * dpr)} · "
                                                         f"{s.refreshRate():.0f} Hz · {round(dpr * 100)}%"))
        self.disp_kv.set(rows)
        if "monitors" in self.cache:
            return
        import hwinfo as HI

        def done(mons):
            if not isinstance(mons, list):
                return
            self.cache["monitors"] = mons
            clear_layout(self.edid_box)
            for mo in mons:
                c, cv = section_card(mo.get("name") or tr("hwc.i.monitor"), tr("hwc.disp.edid"))
                kv = KV(2)
                kv.set(self.monitor_rows(mo))
                cv.addWidget(kv)
                self.edid_box.addWidget(c)
        self.run_bg(lambda log, p: HI.monitors(), done)

    def color_test(self):
        screens = QGuiApplication.screens()
        if len(screens) > 1:
            m = QMenu(self)
            for i, s in enumerate(screens):
                a = m.addAction(tr("hwc.disp.screen", n=i + 1) + f" · {s.name()}")
                a.triggered.connect(lambda _=False, sc=s: self._color_on(sc))
            m.exec(self.cursor().pos())
            self.menu = m
        else:
            self._color_on(screens[0] if screens else None)

    def _color_on(self, screen):
        w = ColorTest(screen)
        w.exec()
        self.ask_mark("display_pixels", self.disp_view)

    # ───────────────────────── Ноутбук ─────────────────────────
    def _build_laptop(self, v):
        c, cv = self.section(v, tr("hwc.lap.title"), tr("hwc.lap.sub"))
        self.lap_kv = KV(2)
        cv.addWidget(self.lap_kv)
        bh = hbox(margins=(14, 4, 14, 8), spacing=8)
        bh.addWidget(button(tr("hwc.lap.battery"), "primary", self.load_battery))
        bh.addWidget(button(tr("hwc.lap.page"), None, lambda: self.main.go("laptop")))
        bh.addStretch()
        cv.addLayout(bh)
        self.lap_view = ResultView()
        cv.addWidget(self.lap_view)
        if self.last("battery"):
            self.lap_view.set(self.last("battery"))

    def _show_laptop(self):
        import gpubench as GB
        import gpuselect as GS
        hw = self.main.hw or {}
        ads = GS.adapters(GS.cached_probe() or {})
        hybrid = len(ads) > 1
        cpu = self.last("cpu_stress") or self.last("cpu_multi")
        thr = [finding_text(f) for f in cpu.get("findings") or [] if f[1] in
               ("hwc.f.thermal", "hwc.f.power_limit", "hwc.f.clock_drop")]
        self.lap_kv.set([
            ("hwc.lap.is", tr("hwc.yes") if hw.get("laptop") else tr("hwc.no")),
            ("hwc.lap.power", tr("gs.on_battery") if GB.power_state() == "battery" else tr("hwc.lap.ac")),
            ("hwc.lap.hybrid", " + ".join(f"{a['name']} ({tr('gs.kind.' + a['kind'])})" for a in ads) if hybrid
             else tr("hwc.no") if ads else None),
            ("hwc.lap.throttle", "; ".join(thr) if thr else (tr("hwc.lap.no_throttle") if cpu else None)),
            ("hwc.lap.temp", f"{cpu['temp_max']:.0f} °C" if cpu.get("temp_max") else None)])

    def load_battery(self):
        import hardware as H

        def done(bats):
            if not isinstance(bats, list):
                return
            if not bats:
                r = HT.result("battery", HT.NA, tr("hwc.lap.no_battery"))
            else:
                b = bats[0]
                wear = b.get("wear") or 0
                st = HT.FAIL if wear >= 40 else HT.WARN if wear >= 20 else HT.PASS
                f = [(st, "hwc.f.battery_wear", dict(w=round(wear)))] if st != HT.PASS else []
                if b.get("cycles") and b["cycles"] >= 800:
                    f.append((HT.WARN, "hwc.f.battery_cycles", dict(n=b["cycles"])))
                    st = HT.worst([st, HT.WARN])
                r = HT.result("battery", st, tr(f"hwc.lap.sum.{st}", w=round(wear)), rows=self.battery_rows(b),
                              findings=f, wear=wear, cycles=b.get("cycles"))
            HT.save(F.CFG, r)
            self.lap_view.set(r)
            self.refresh_overview()
        self.run_bg(lambda log, p: H.battery_report(), done)

    # ───────────────────────── Периферія ─────────────────────────
    PERIPH = ("keyboard", "mouse", "speakers", "camera", "mic")

    def _build_peripherals(self, v):
        c, cv = self.section(v, tr("hwc.per.title"), tr("hwc.per.sub"))
        self.per_views = {}
        for key in self.PERIPH:
            row = QFrame()
            row.setObjectName("row")
            rv = vbox(row, (14, 8, 14, 8), 4)
            h = hbox(spacing=10)
            col = vbox(spacing=2)
            col.addWidget(label(tr(f"hwc.per.{key}"), "rowTitle"))
            col.addWidget(label(tr(f"hwc.per.{key}_d"), "desc", wrap=True))
            h.addLayout(col, 1)
            h.addWidget(button(tr("hwc.per.run"), None, lambda k=key: self.periph(k)), 0, Qt.AlignmentFlag.AlignVCenter)
            h.addWidget(button(tr("hwc.disp.mark"), "ghost", lambda k=key: self.ask_mark(f"periph_{k}",
                                                                                         self.per_views[k])), 0,
                        Qt.AlignmentFlag.AlignVCenter)
            rv.addLayout(h)
            view = ResultView()
            rv.addWidget(view)
            if self.last(f"periph_{key}"):
                view.set(self.last(f"periph_{key}"))
            self.per_views[key] = view
            cv.addWidget(row)
        nc, ncv = self.section(v, tr("hwc.per.net"))
        self.net_kv = KV(1)
        ncv.addWidget(self.net_kv)

    def _show_peripherals(self):
        if "net" in self.cache:
            return
        import hwinfo as HI

        def done(nets):
            if isinstance(nets, list):
                self.cache["net"] = nets
                self.net_kv.set([(n.get("name") or "?", " · ".join(str(x) for x in (n.get("status"), n.get("speed"),
                                                                                  n.get("media")) if x)) for n in nets])
        self.run_bg(lambda log, p: HI.network(), done)

    def periph(self, key: str):
        if key == "keyboard":
            KeyTest(self).exec()
        elif key == "mouse":
            MouseTest(self).exec()
        elif key == "speakers":
            play_tones()
        elif key == "camera":
            open_uri("microsoft.windows.camera:")
        elif key == "mic":
            open_uri("ms-settings:sound")
        self.ask_mark(f"periph_{key}", self.per_views[key])

    # ───────────────────────── Стрес-тести ─────────────────────────
    STRESS_MODES = ("cpu", "gpu", "cpu_gpu", "ram", "vram", "storage")

    def _build_stress(self, v):
        c, cv = self.section(v, tr("hwc.st.title"), tr("hwc.st.sub"))
        r = hbox(margins=(14, 4, 14, 4), spacing=10)
        r.addWidget(label(tr("gb.mode"), "desc"))
        self.st_mode = Segmented([tr(f"hwc.sm.{m}") for m in self.STRESS_MODES])
        self.st_mode_i = 2
        self.st_mode.select(2)
        self.st_mode.changed.connect(lambda i: setattr(self, "st_mode_i", i))
        r.addWidget(self.st_mode)
        r.addStretch()
        cv.addLayout(r)
        r2 = hbox(margins=(14, 0, 14, 4), spacing=10)
        r2.addWidget(label(tr("gb.minutes"), "desc"))
        self.st_min = Segmented([tr("u.min_n", n=m) for m in HT.CPU_MINUTES])
        self.st_min_i = 1
        self.st_min.select(1)
        self.st_min.changed.connect(lambda i: setattr(self, "st_min_i", i))
        r2.addWidget(self.st_min)
        r2.addStretch()
        self.st_btn = button(tr("hwc.start"), "danger", self.start_stress)
        r2.addWidget(self.st_btn)
        cv.addLayout(r2)
        cv.addWidget(self._note(tr("hwc.st.note", c=int(HT.CPU_TEMP_STOP), g=int(HT.GPU_TEMP_STOP))))
        prog, view = self.test_area(cv, ("stress_combined",),
                                    charts=(("temp", "°C", "warn"), ("gpu_temp", "°C", "bad"), ("mhz", "MHz", "acc")))
        self.st_box = self.make_box(prog, view, self.st_btn)

    def start_stress(self):
        import gpubench as GB
        import vramtest as VT
        if self.st_box.busy:
            return
        mode = self.STRESS_MODES[self.st_mode_i]
        minutes = HT.CPU_MINUTES[self.st_min_i]
        if not Ask.ask(self, tr("hwc.warn_t"), tr("hwc.warn_q", m=minutes), tr("hwc.start"), "danger"):
            return
        seconds = minutes * 60
        runs = {}
        hw = self.main.hw or {}
        plan = self.gpu_plan()
        if mode in ("cpu", "cpu_gpu"):
            runs["cpu"] = HT.start("cpu", dict(threads=os.cpu_count() or 1, seconds=seconds))
        if mode in ("gpu", "cpu_gpu"):
            runs["gpu"] = GB.start("1080p", "stress", minutes, adapter=plan or None)
        if mode == "ram":
            runs["ram"] = HT.start("ram", dict(mb=HT.ram_plan(self._ram_avail(), 50), passes=max(1, minutes)))
        if mode == "vram":
            runs["vram"] = VT.start(50, plan or None, 0, plan.get("kind") == "igpu")
        if mode == "storage":
            disks = [d for d in hw.get("disks") or [] if d.get("letters")]
            letter = (disks[0]["letters"][0] if disks else "C")
            runs["disk"] = HT.start("disk", dict(dir=HT.disk_target(letter), mb=1024, rand_seconds=min(60, seconds // 4)))
        LOG.write(f"[►] {tr('hwc.t.stress_combined')}: {tr('hwc.sm.' + mode)}, {tr('u.min_n', n=minutes)}")

        def describe(states, s):
            parts = []
            for k, st in states.items():
                parts.append(f"{tr('hwc.sm.' + k) if k in self.STRESS_MODES else k}: {st.get('state', '?')}")
            if s.get("temp") is not None:
                parts.append(f"CPU {s['temp']:.0f} °C")
            if s.get("gpu_temp") is not None:
                parts.append(f"GPU {s['gpu_temp']:.0f} °C")
            t = max((float(st.get("t") or 0) for st in states.values()), default=0)
            return " · ".join(parts), t, seconds

        def finish(states, samples, danger):
            return self.stress_result(mode, states, samples, danger, hw)
        self.st_box.start(runs, finish, describe, gpu=True)

    @staticmethod
    def stress_result(mode: str, states: dict, samples: list, danger: str, hw: dict) -> dict:
        f = []
        statuses = []
        if danger:
            f.append((HT.FAIL, "hwc.f.overheat_stop", dict(what=tr(f"hwc.dev.{danger}"))))
            statuses.append(HT.FAIL)
        for k, st in states.items():
            s = st.get("state")
            if s == "crash" or (k == "gpu" and (st.get("result") or {}).get("verdict") == "crash"):
                f.append((HT.FAIL, "hwc.f.part_crash", dict(what=tr(f"hwc.sm.{k}") if k in ("cpu", "gpu", "ram", "vram")
                                                           else k)))
                statuses.append(HT.FAIL)
            if st.get("errors"):
                f.append((HT.FAIL, "hwc.f.part_errors", dict(what=tr(f"hwc.sm.{k}") if k in ("cpu", "gpu", "ram", "vram")
                                                            else k, n=st["errors"])))
                statuses.append(HT.FAIL)
            if s == "cancelled" and not danger:
                statuses.append(HT.SKIPPED)
        f += HT.cpu_findings(samples, int(hw.get("mhz") or 0)) + HT.gpu_findings(samples)
        st = HT.worst(statuses + [HT.status_of(f)])
        temps = [s.get("temp") for s in samples if s.get("temp") is not None]
        gtemps = [s.get("gpu_temp") for s in samples if s.get("gpu_temp") is not None]
        rows = [("hwc.r.mode", tr(f"hwc.sm.{mode}")), ("hwc.r.duration", f"{len(samples)} {tr('hwc.u.s')}"),
                ("hwc.r.temp_max", f"{max(temps):.0f} °C" if temps else None),
                ("hwc.r.gpu_temp_max", f"{max(gtemps):.0f} °C" if gtemps else None)]
        return HT.result("stress_combined", st, tr(f"hwc.sum.stress.{st}"), rows=rows, findings=f, mode=mode,
                         series=dict(temp=[s.get("temp") for s in samples], gpu_temp=[s.get("gpu_temp") for s in samples],
                                     mhz=[s.get("mhz") for s in samples]))

    # ───────────────────────── Діагностика Windows ─────────────────────────
    def _build_windiag(self, v):
        c, cv = self.section(v, tr("hwc.wd.title"), tr("hwc.wd.sub"))
        bh = hbox(margins=(14, 4, 14, 8), spacing=8)
        self.wd_btn = button(tr("hwc.wd.analyze"), "primary", self.analyze_windows)
        bh.addWidget(self.wd_btn)
        bh.addWidget(button(tr("hwc.wd.crash_page"), None, lambda: self.main.go("diagnose")))
        bh.addStretch()
        cv.addLayout(bh)
        self.wd_view = ResultView()
        cv.addWidget(self.wd_view)
        if self.last("windiag"):
            self.wd_view.set(self.last("windiag"))
        dc, dcv = self.section(v, tr("hwc.wd.dumps"), tr("hwc.wd.dumps_sub"))
        self.dump_box = vbox(spacing=4)
        dcv.addLayout(self.dump_box)
        db = hbox(margins=(14, 4, 14, 8), spacing=8)
        self.dump_btn = button(tr("hwc.wd.find_dumps"), None, self.load_dumps)
        db.addWidget(self.dump_btn)
        db.addStretch()
        dcv.addLayout(db)
        rc, rcv = self.section(v, tr("hwc.wd.repair"), tr("hwc.wd.repair_sub"))
        rb = hbox(margins=(14, 4, 14, 8), spacing=8)
        for key in ("sfc", "dism_check", "dism_restore"):
            rb.addWidget(button(tr(f"hwc.wd.{key}"), None, lambda k=key: self.repair(k)))
        rb.addStretch()
        rcv.addLayout(rb)

    def analyze_windows(self):
        import dumpanalyzer as DA
        self.wd_btn.setEnabled(False)

        def done(res):
            self.wd_btn.setEnabled(True)
            if isinstance(res, dict) and res.get("test"):
                HT.save(F.CFG, res)
                self.wd_view.set(res)
                self.refresh_overview()
        self.run_bg(lambda log, p: DA.windows_health(log), done)

    def load_dumps(self):
        import dumpanalyzer as DA
        self.dump_btn.setEnabled(False)

        def done(res):
            self.dump_btn.setEnabled(True)
            clear_layout(self.dump_box)
            if not isinstance(res, dict):
                return
            cdb = res.get("cdb")
            self.dump_box.addWidget(self._note(tr("hwc.wd.cdb_found", p=cdb) if cdb else tr("hwc.wd.cdb_missing")))
            for d in res.get("dumps") or []:
                row = QFrame()
                row.setObjectName("row")
                h = hbox(row, (14, 6, 14, 6), 10)
                h.addWidget(label(f"{d['name']} · {time.strftime('%d.%m.%Y %H:%M', time.localtime(d['ts']))}",
                                  "rowTitle"), 1)
                h.addWidget(label(d.get("code_text") or "", "desc"))
                b = button(tr("hwc.wd.analyze_dump"), "ghost", lambda p=d["path"]: self.analyze_dump(p))
                b.setEnabled(bool(cdb))
                h.addWidget(b)
                self.dump_box.addWidget(row)
            if not res.get("dumps"):
                self.dump_box.addWidget(self._note(tr("hwc.wd.no_dumps")))
        self.run_bg(lambda log, p: DA.list_dumps(), done)

    def analyze_dump(self, path: str):
        import dumpanalyzer as DA

        def done(res):
            if not isinstance(res, dict):
                return
            if res.get("test"):
                HT.save(F.CFG, res)
                self.wd_view.set(res)
        self.main.run_quick(tr("hwc.wd.analyze_dump"), lambda log, p: DA.analyze_dump(path, log), on_done=done,
                            silent=True)

    def repair(self, key: str):
        import dumpanalyzer as DA
        if not Ask.ask(self, tr(f"hwc.wd.{key}"), tr(f"hwc.wd.{key}_q"), tr("btn.continue")):
            return
        self.main.run_quick(tr(f"hwc.wd.{key}"), lambda log, p: DA.repair(key, log))

    # ── розділи наступних етапів (процеси, перевірка перед покупкою, звіти, оверлей) підключаються нижче ──
    def _build_procs(self, v):
        import pages_hwc2 as P2
        P2.build_procs(self, v)

    def _show_procs(self):
        import pages_hwc2 as P2
        P2.show_procs(self)

    def _build_inspect(self, v):
        import pages_hwc2 as P2
        P2.build_inspect(self, v)

    def _build_reports(self, v):
        import pages_hwc2 as P2
        P2.build_reports(self, v)

    def _show_reports(self):
        import pages_hwc2 as P2
        P2.show_reports(self)

    def _build_overlay(self, v):
        import pages_hwc2 as P2
        P2.build_overlay(self, v)


# ───────────────────────── інтерактивні перевірки ─────────────────────────
class ColorTest(QDialog):
    """Повноекранні кольори для пошуку битих (чорних) і застряглих (яскравих) пікселів. Клік / пробіл / → — далі,
    ← — назад, Esc — вийти. Визначає дефекти користувач: автоматичного розпізнавання тут немає."""

    COLORS = ("#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#808080", "#00FFFF", "#FF00FF", "#FFFF00")

    def __init__(self, screen=None):
        super().__init__()
        self.i = 0
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setCursor(Qt.CursorShape.BlankCursor)
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.showFullScreen()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.COLORS[self.i]))
        if self.i == 0:
            p.setPen(QColor("#555555"))
            p.setFont(QFont("Segoe UI", 12))
            p.drawText(self.rect().adjusted(0, 0, 0, -40), int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
                       tr("hwc.disp.keys"))
        p.end()

    def step(self, d: int):
        self.i = (self.i + d) % len(self.COLORS)
        self.update()

    def mousePressEvent(self, e):
        self.step(-1 if e.button() == Qt.MouseButton.RightButton else 1)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            self.accept()
        elif k in (Qt.Key.Key_Left, Qt.Key.Key_Backspace):
            self.step(-1)
        else:
            self.step(1)


class KeyTest(QDialog):
    """Натискайте клавіші — кожна з'являється в списку (з кодом), щоб побачити ті, що не спрацьовують."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("hwc.per.keyboard"))
        self.setMinimumSize(620, 320)
        v = vbox(self, (22, 20, 22, 16), 10)
        v.addWidget(label(tr("hwc.per.keyboard_hint"), "sub", wrap=True))
        self.count = label(tr("hwc.per.keys_n", n=0), "h2")
        v.addWidget(self.count)
        self.keys = label("", "mono", wrap=True)
        v.addWidget(self.keys, 1)
        v.addWidget(button(tr("btn.ok"), "primary", self.accept), 0, Qt.AlignmentFlag.AlignRight)
        self.seen = []

    def keyPressEvent(self, e):
        name = e.text().strip() or f"#{e.key()}"
        if e.key() == Qt.Key.Key_Escape:
            self.accept()
            return
        if name not in self.seen:
            self.seen.append(name)
        self.count.setText(tr("hwc.per.keys_n", n=len(self.seen)))
        self.keys.setText("  ".join(self.seen[-120:]))


class MouseTest(QDialog):
    """Ліва, права, середня кнопки й колесо: лічильники для кожного."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("hwc.per.mouse"))
        self.setMinimumSize(520, 260)
        v = vbox(self, (22, 20, 22, 16), 10)
        v.addWidget(label(tr("hwc.per.mouse_hint"), "sub", wrap=True))
        self.n = dict(left=0, right=0, middle=0, up=0, down=0, back=0, forward=0)
        self.lbl = label("", "h3", wrap=True)
        v.addWidget(self.lbl, 1)
        v.addWidget(button(tr("btn.ok"), "primary", self.accept), 0, Qt.AlignmentFlag.AlignRight)
        self._sync()

    def _sync(self):
        self.lbl.setText("   ".join(f"{tr('hwc.per.m.' + k)}: {v}" for k, v in self.n.items()))

    def mousePressEvent(self, e):
        b = e.button()
        key = {Qt.MouseButton.LeftButton: "left", Qt.MouseButton.RightButton: "right",
               Qt.MouseButton.MiddleButton: "middle", Qt.MouseButton.BackButton: "back",
               Qt.MouseButton.ForwardButton: "forward"}.get(b)
        if key:
            self.n[key] += 1
            self._sync()

    def wheelEvent(self, e):
        self.n["up" if e.angleDelta().y() > 0 else "down"] += 1
        self._sync()


def wav_tone(freq: float = 440.0, seconds: float = 0.8, side: str = "left", rate: int = 22050) -> bytes:
    """Стерео WAV у пам'яті: тон лише в лівому чи лише в правому каналі."""
    import math
    import struct
    n = int(seconds * rate)
    frames = bytearray()
    for i in range(n):
        env = min(1.0, i / 800, (n - i) / 800)
        s = int(12000 * env * math.sin(2 * math.pi * freq * i / rate))
        frames += struct.pack("<hh", s if side == "left" else 0, s if side == "right" else 0)
    head = b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 2, rate,
                                                                                      rate * 4, 4, 16)
    return head + b"data" + struct.pack("<I", len(frames)) + bytes(frames)


def play_tones() -> None:
    """Лівий канал, потім правий (winsound лише на Windows; поза Windows — нічого)."""
    if not E.IS_WIN:
        LOG.write("  [demo] ♪ L / R")
        return
    import winsound
    for side, f in (("left", 440.0), ("right", 660.0)):
        winsound.PlaySound(wav_tone(f, 0.8, side), winsound.SND_MEMORY)


def open_uri(uri: str) -> None:
    if not E.IS_WIN:
        LOG.write(f"  [demo] {uri}")
        return
    try:
        os.startfile(uri)  # noqa: лише Windows
    except OSError as e:
        LOG.write(tr("e.err", err=e))
