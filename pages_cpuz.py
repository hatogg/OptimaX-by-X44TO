"""
OptimaX — розділ «Процесор» у Hardware Center: паспорт процесора, кешу, плати, пам'яті, слотів і відеокарт, як у CPU-Z.

Вкладки зверху, під ними — сітка «назва — значення» моноширинним шрифтом. Частота, множник, напруга й шина
оновлюються раз на секунду, поки вкладка «Процесор» на екрані. Поля, які без драйвера ядра не прочитати (напруга,
справжні множник і шина, таймінги з SPD), заповнює PawnIO, якщо його встановлено; ні — тихе «потрібен PawnIO» і
кнопка на pawnio.eu, а не вигадане число.
Дані — cpuz.collect у фоновому потоці; «Копіювати звіт» кладе текст у буфер, як «Save report» у CPU-Z.
"""
from __future__ import annotations

import random

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import QFrame, QGridLayout, QWidget

import cpuz as CZ
import pawnio as PIO
from i18n import tr
from ui_kit import MONO_CSS, button, clear_layout, hbox, label, Segmented, vbox

TABS = ("cpu", "caches", "board", "memory", "spd", "gpu")


class CpuzPanel(QWidget):
    """page — HwCenterPage (run_bg, main.hw)."""

    def __init__(self, page):
        super().__init__()
        self.page, self.data, self.tab, self.slot, self.gpu_i = page, None, "cpu", 0, 0
        self.clock, self.meter, self.busy, self.live, self.reader = None, None, False, {}, None
        self.need_keys = set()
        v = vbox(self, spacing=12)
        bar = hbox(spacing=8)
        self.tabs = Segmented([tr(f"cz.tab.{t}") for t in TABS])
        self.tabs.changed.connect(lambda i: self.show_tab(TABS[i]))
        bar.addWidget(self.tabs)
        bar.addStretch()
        self.btn_copy = button(tr("di.copy"), None, self.copy)
        bar.addWidget(self.btn_copy)
        v.addLayout(bar)
        self.body = QFrame()
        self.body.setObjectName("card")
        bv = vbox(self.body, (20, 18, 20, 16), 12)
        self.title = label(tr("di.loading"), "h1", wrap=True)
        bv.addWidget(self.title)
        self.sub = label("", "muted", wrap=True)
        bv.addWidget(self.sub)
        self.picker_row = hbox(spacing=8)
        bv.addLayout(self.picker_row)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(8)
        bv.addLayout(self.grid)
        nrow = hbox(spacing=10)
        self.note = label(tr("cz.driver_note"), "desc", wrap=True)
        nrow.addWidget(self.note, 1)
        self.btn_pawnio = button(tr("cz.pawnio_get"), None,
                                 lambda: QDesktopServices.openUrl(QUrl(PIO.SITE)))  # сайт відкриває користувач сам
        nrow.addWidget(self.btn_pawnio, 0, Qt.AlignmentFlag.AlignTop)
        bv.addLayout(nrow)
        v.addWidget(self.body)
        self.values = {}
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

    # ── дані ──
    def load(self) -> None:
        if self.busy:
            return
        self.busy = True
        hw = self.page.main.hw or {}
        self.page.run_bg(lambda log, p: CZ.collect(hw), self.fill)

    def fill(self, d) -> None:
        self.busy = False
        if not isinstance(d, dict) or "error" in d:  # 7.1: помилка Worker — це не дані («потрібен PawnIO» тут брехав)
            self.title.setText(tr("di.failed"))
            self.sub.setText(str((d or {}).get("error") or "") if isinstance(d, dict) else "")
            self.sub.setVisible(bool(self.sub.text()))
            return
        self.data = d
        if self.reader and self.reader is not d.get("live"):
            self.reader.close()
        self.reader = d.get("live")
        base = (d.get("cpu") or {}).get("base_mhz") or 0
        if self.meter is None or self.meter.base != base:  # залізо дочиталося пізніше — нова базова частота
            if self.meter:
                self.meter.close()
            self.meter = CZ.ClockMeter(base)
        self.clock = d.get("demo_clock")
        self.live = self.reader.read() if self.reader else CZ.demo_live(d, self.clock)
        self.show_tab(self.tab)
        self.timer.start()

    def _tick(self) -> None:
        if not self.isVisible() or not self.data:
            return
        if self.meter and self.meter.q:
            self.clock = self.meter.mhz() or self.clock
        elif self.data.get("demo_clock"):
            self.clock = self.data["demo_clock"] + random.choice((-100, 0, 0, 100))
        self.live = self.reader.read() if self.reader else CZ.demo_live(self.data, self.clock)
        if self.tab == "cpu":
            rows = CZ.cpu_rows(self.data, self.clock, self.live)
            if any((v is CZ.NEEDS_DRIVER) != (k in self.need_keys) for k, v in rows):
                self.show_tab("cpu")  # «потрібен PawnIO» змінився на значення (чи навпаки) — інший вигляд рядка
                return
            for key, val in rows:
                lb = self.values.get(key)
                if lb is not None and key in ("cz.clock", "cz.multiplier", "cz.voltage", "cz.bus") \
                        and val is not CZ.NEEDS_DRIVER:
                    lb.setText(val or "----")

    # ── вкладки ──
    def show_tab(self, tab: str) -> None:
        self.tab = tab
        self.tabs.select(TABS.index(tab))
        d = self.data
        if not d:
            return
        clear_layout(self.picker_row)
        c = d.get("cpu") or {}
        if tab == "cpu":
            self.title.setText(c.get("name") or c.get("spec") or "?")
            self.sub.setText(" · ".join(x for x in (c.get("codename"), c.get("technology"), c.get("package")) if x))
            rows = CZ.cpu_rows(d, self.clock, self.live)
        elif tab == "caches":
            self.title.setText(tr("cz.tab.caches"))
            self.sub.setText(c.get("name") or "")
            rows = CZ.cache_rows(d)
        elif tab == "board":
            b = d.get("board") or {}
            self.title.setText(" ".join(x for x in (b.get("vendor"), b.get("model")) if x) or tr("cz.tab.board"))
            self.sub.setText(b.get("chipset") or "")
            rows = CZ.board_rows(d)
        elif tab == "memory":
            r = d.get("ram") or {}
            self.title.setText(" ".join(x for x in (r.get("type"), f"{r.get('total_gb')} GB" if r.get("total_gb")
                                                    else "") if x) or tr("cz.tab.memory"))
            self.sub.setText("")
            rows = CZ.memory_rows(d)
        elif tab == "spd":
            mods = [m for m in (d.get("ram") or {}).get("modules") or [] if m.get("mb")]
            self.slot = min(self.slot, max(0, len(mods) - 1))
            if len(mods) > 1:
                self._picker([m.get("slot") or f"#{i + 1}" for i, m in enumerate(mods)], self.slot, self._pick_slot)
            m = mods[self.slot] if mods else {}
            self.title.setText(" ".join(x for x in (m.get("vendor"), m.get("part")) if x) or tr("cz.no_modules"))
            self.sub.setText(m.get("slot") or "")
            rows = CZ.slot_rows(m, d) if m else []
        else:
            gpus = d.get("gpus") or []
            self.gpu_i = min(self.gpu_i, max(0, len(gpus) - 1))
            if len(gpus) > 1:
                self._picker([g.get("name") or "?" for g in gpus], self.gpu_i, self._pick_gpu)
            g = gpus[self.gpu_i] if gpus else {}
            self.title.setText(g.get("name") or tr("hwc.na"))
            self.sub.setText(tr("cz.gpu_more"))
            rows = CZ.gpu_rows(g) if g else []
        self.sub.setVisible(bool(self.sub.text()))
        self._grid(rows)

    def _picker(self, names: list, cur: int, cb) -> None:
        seg = Segmented(names)
        seg.select(cur)
        seg.changed.connect(cb)
        self.picker_row.addWidget(seg)
        self.picker_row.addStretch()

    def _pick_slot(self, i: int) -> None:
        self.slot = i
        self.show_tab("spd")

    def _pick_gpu(self, i: int) -> None:
        self.gpu_i = i
        self.show_tab("gpu")

    def _grid(self, rows: list) -> None:
        clear_layout(self.grid)
        self.values = {}
        self.need_keys = {k for k, v in rows if v is CZ.NEEDS_DRIVER}
        wide = {"cz.instructions", "cz.spec"}
        r = c = 0
        need = False
        for key, val in rows:
            if key in wide and c:
                r, c = r + 1, 0
            self.grid.addWidget(label(tr(key), "muted"), r, c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            if val is CZ.NEEDS_DRIVER:
                need = True
                lb = label(tr("cz.needs_driver"), "muted")
                lb.setToolTip(tr("cz.driver_note"))
            else:
                lb = label(str(val) if val not in (None, "") else "----", wrap=True)
                lb.setStyleSheet(f"{MONO_CSS} font-size: 13px;")
                lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.values[key] = lb
            if key in wide:
                self.grid.addWidget(lb, r, 1, 1, 3)
                r, c = r + 1, 0
                continue
            self.grid.addWidget(lb, r, c + 1)
            c = 2 if c == 0 else 0
            r += c == 0
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(3, 1)
        drv = (self.data or {}).get("driver")
        err = (self.data or {}).get("spd_error")
        if drv == "no_modules":
            self.note.setText(tr("cz.no_modules_bin"))
        elif err and self.tab in ("memory", "spd"):
            self.note.setText(tr("cz.spd_error", e=err))
        else:
            self.note.setText(tr("cz.driver_note"))
        self.note.setVisible(need or drv == "no_modules" or bool(err and self.tab in ("memory", "spd")))
        self.btn_pawnio.setVisible(need and drv == "absent")

    def copy(self) -> None:
        if not self.data:
            return
        QGuiApplication.clipboard().setText(CZ.report_text(self.data, self.clock, self.live))
        self.btn_copy.setText(tr("di.copied"))
        QTimer.singleShot(1800, lambda: self.btn_copy.setText(tr("di.copy")))

    def closeEvent(self, e):
        self.timer.stop()
        if self.meter:
            self.meter.close()
        if self.reader:
            self.reader.close()
        super().closeEvent(e)

