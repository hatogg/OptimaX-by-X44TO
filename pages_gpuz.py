"""
OptimaX — паспорт відеокарт у розділі «Відеокарта» Hardware Center, як у GPU-Z.

Зверху — вибір адаптера (якщо їх кілька: вбудована з монітором + майнінгова, ноутбук з Optimus), далі сітка груп
«Пристрій / Шина / Пам'ять / Частоти й датчики / Графічні API» моноширинним шрифтом і висновки (лінія PCIe нижче
максимуму, Resizable BAR, звідки датчики). Частоти, температура, завантаження й поточна лінія PCIe карти NVIDIA
оновлюються раз на 2 с у фоновому потоці, поки розділ на екрані. Невідоме — «—», а не здогадка.
Дані — gpuz.collect у фоновому потоці; «Копіювати звіт» кладе текст у буфер.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFrame, QGridLayout, QWidget

import engine as E
import gpuz as GZ
from i18n import tr
from ui_kit import MONO_CSS, T, button, clear_layout, dot, hbox, label, Segmented, vbox

LEVEL_COLOR = {"ok": "ok", "warn": "warn", "info": "sub"}
LIVE_MS = 2000


class GpuzPanel(QWidget):
    """page — HwCenterPage (run_bg, main.hw)."""

    def __init__(self, page):
        super().__init__()
        self.page, self.data, self.cur, self.busy, self.live_busy = page, None, 0, False, False
        self.lives, self.values, self.notes = {}, {}, None
        v = vbox(self, spacing=12)
        bar = hbox(spacing=8)
        self.picker_row = hbox(spacing=8)
        bar.addLayout(self.picker_row)
        bar.addStretch()
        self.btn_refresh = button(tr("gz.refresh"), None, self.load)
        bar.addWidget(self.btn_refresh)
        self.btn_probe = button(tr("gz.probe"), None, self.probe)
        bar.addWidget(self.btn_probe)
        self.btn_copy = button(tr("di.copy"), None, self.copy)
        bar.addWidget(self.btn_copy)
        v.addLayout(bar)
        self.body = QFrame()
        self.body.setObjectName("card")
        bv = vbox(self.body, (20, 18, 20, 16), 12)
        self.title = label(tr("gz.loading"), "h1", wrap=True)
        bv.addWidget(self.title)
        self.sub = label("", "muted", wrap=True)
        bv.addWidget(self.sub)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(8)
        bv.addLayout(self.grid)
        self.find_box = vbox(spacing=6)
        bv.addLayout(self.find_box)
        v.addWidget(self.body)
        self.timer = QTimer(self)
        self.timer.setInterval(LIVE_MS)
        self.timer.timeout.connect(self._tick)

    # ── дані ──
    def load(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.btn_refresh.setEnabled(False)
        hw = self.page.main.hw or {}
        self.page.run_bg(lambda log, p: GZ.collect(hw), self.fill)

    def fill(self, d) -> None:
        self.busy = False
        self.btn_refresh.setEnabled(True)
        if not isinstance(d, dict) or "error" in d:  # помилка Worker — не дані
            self.title.setText(tr("gz.failed"))
            self.sub.setText(str((d or {}).get("error") or "") if isinstance(d, dict) else "")
            self.sub.setVisible(bool(self.sub.text()))
            return
        self.data, self.lives = d, {}
        ads = d.get("adapters") or []
        self.cur = min(self.cur, max(0, len(ads) - 1))
        clear_layout(self.picker_row)
        if len(ads) > 1:
            seg = Segmented([a.get("name") or "?" for a in ads])
            seg.select(self.cur)
            seg.changed.connect(self._pick)
            self.picker_row.addWidget(seg)
        self.show_adapter()
        self.timer.start()
        self._tick()

    def adapter(self) -> dict:
        ads = (self.data or {}).get("adapters") or []
        return ads[self.cur] if ads else {}

    def _pick(self, i: int) -> None:
        self.cur = i
        self.show_adapter()
        self._tick()

    # ── вигляд ──
    def show_adapter(self) -> None:
        a = self.adapter()
        clear_layout(self.grid)
        clear_layout(self.find_box)
        self.values, self.notes = {}, None
        if not a:
            self.title.setText(tr("gz.none"))
            self.sub.hide()
            return
        lv = self.lives.get(self.cur) or {}
        self.title.setText(a.get("name") or "?")
        self.sub.setText(" · ".join(x for x in (a.get("vendor"), GZ.role_text(a)) if x))
        self.sub.setVisible(bool(self.sub.text()))
        r = 0
        for gk, fn in GZ.GROUPS:
            head = label(tr(gk), "h3")
            head.setContentsMargins(0, 6 if r else 0, 0, 0)
            self.grid.addWidget(head, r, 0, 1, 4)
            r += 1
            c = 0
            for key, val in fn(a, lv):
                self.grid.addWidget(label(tr(key), "muted"), r, c,
                                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                lb = label(self._val(val), wrap=True)
                lb.setStyleSheet(f"{MONO_CSS} font-size: 13px;")
                lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.values[key] = lb
                self.grid.addWidget(lb, r, c + 1)
                c = 2 if c == 0 else 0
                r += c == 0
            r += c != 0
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(3, 1)
        self._findings(a, lv)

    @staticmethod
    def _val(v) -> str:
        return str(v) if v not in (None, "") else "—"

    def _findings(self, a: dict, lv: dict) -> None:
        notes = GZ.findings(a, lv)
        if notes == self.notes:
            return
        self.notes = notes
        clear_layout(self.find_box)
        for lvl, text in notes:
            row = hbox(spacing=8)
            row.addWidget(dot(T[LEVEL_COLOR.get(lvl, "sub")]), 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(text, "desc", wrap=True), 1)
            self.find_box.addLayout(row)

    # ── живі показники ──
    def _tick(self) -> None:
        # як у «Процесорі»: згорнуте вікно чи інший розділ — не опитувати NVML
        if self.live_busy or not self.data or not self.isVisible() or self.window().isMinimized():
            return
        a, i = self.adapter(), self.cur
        if not a or (E.IS_WIN and a.get("nv_index") is None):
            return
        self.live_busy = True
        self.page.run_bg(lambda log, p: GZ.live(a), lambda lv, i=i: self._live_done(i, lv))

    def _live_done(self, i: int, lv) -> None:
        self.live_busy = False
        if not isinstance(lv, dict) or "error" in lv or not lv:
            return
        self.lives[i] = lv
        if i != self.cur:
            return
        a = self.adapter()
        for gk, fn in GZ.GROUPS:
            for key, val in fn(a, lv):
                lb = self.values.get(key)
                if lb is not None and key in GZ.LIVE_KEYS:
                    lb.setText(self._val(val))
        self._findings(a, lv)

    # ── дії ──
    def probe(self) -> None:
        """Перевірка DirectX / Vulkan — та сама, що в «Майнінгу» й GPU-тесті (окремий процес gpuinfo.probe)."""
        import gpuinfo as GI
        self.btn_probe.setEnabled(False)
        self.btn_probe.setText(tr("gz.probing"))

        def done(_res):
            self.btn_probe.setEnabled(True)
            self.btn_probe.setText(tr("gz.probe"))
            self.load()
        self.page.run_bg(lambda log, p: GI.probe(force=True), done)

    def copy(self) -> None:
        if not self.data:
            return
        QGuiApplication.clipboard().setText(GZ.report_text(self.data, self.lives))
        self.btn_copy.setText(tr("di.copied"))
        QTimer.singleShot(1800, lambda: self.btn_copy.setText(tr("di.copy")))

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)
