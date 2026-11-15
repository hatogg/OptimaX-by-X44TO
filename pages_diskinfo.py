"""
OptimaX — «Диски» в Hardware Center: усе, що диск каже про себе, як у CrystalDiskInfo, плюс пояснення людською мовою.

Зверху — вкладки дисків зі станом і температурою; далі паспорт вибраного диска (стан і залишок ресурсу, температура,
прошивка, серійник, інтерфейс, режим, стандарт, функції, записано / прочитано, години й увімкнення), повна таблиця SMART
(для NVMe — журнал здоров'я) і висновки. «Копіювати звіт» кладе в буфер текст, як «Edit → Copy» у CrystalDiskInfo.

Лише читання: дані — з storagehealth (IOCTL SMART / NVMe, лічильники Windows). Невідоме показується як «----».
Серійні номери приховані, доки їх не відкрити (знімок екрана не видасть серійник).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGridLayout, QWidget

import features as F
import hwtests as HT
import storagehealth as SH
from i18n import tr
from ui_kit import MONO_CSS, T, button, chip, clear_layout, dot, hbox, label, make_font, Segmented, vbox

LEVEL_KEY = {SH.GOOD: "ok", SH.CAUTION: "warn", SH.BAD: "bad", SH.UNKNOWN: "mute"}
AUTO_REFRESH_MS = 5 * 60 * 1000  # як у CrystalDiskInfo — раз на кілька хвилин, поки розділ відкритий
MASK = "••••••••••••"


def temp_level(t, ssd: bool) -> str:
    if t is None:
        return SH.UNKNOWN
    hot, warm = (70, 60) if ssd else (55, 50)
    return SH.BAD if t >= hot else SH.CAUTION if t >= warm else SH.GOOD


def is_ssd(d: dict) -> bool:
    return d.get("media") in ("SSD", "NVMe") or bool(d.get("nvme"))


class DiskTab(QWidget):
    """Вкладка диска: крапка стану, стан, температура і літери — як верхній рядок CrystalDiskInfo."""
    clicked = pyqtSignal()

    def __init__(self, d: dict):
        super().__init__()
        self.d, self.on, self._hover = d, False, False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(52)
        self.setMinimumWidth(132)
        lab, _ = SH.health_label(d)
        t = (d.get("assess") or {}).get("temperature")
        letters = " ".join(f"{x}:" for x in d.get("letters") or []) or f"#{d.get('id', '?')}"
        self.lines = (tr(f"di.h.{lab}"), f"{t} °C" if t is not None else "-- °C", letters)
        self.lvl, self.tl = lab, temp_level(t, is_ssd(d))
        self.setToolTip(d.get("name") or "")
        self.setAccessibleName(f"{d.get('name')}: {self.lines[0]}, {self.lines[1]}")

    def set_on(self, on: bool) -> None:
        self.on = on
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(T["acc_h"] if self.on else T["line2" if self._hover or self.hasFocus() else "line"]),
                      1.5 if self.on else 1))
        p.setBrush(QColor(T["surf2" if self.on or self._hover else "surf"]))
        p.drawRoundedRect(r, 10, 10)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T[LEVEL_KEY[self.lvl]]))
        p.drawEllipse(QRectF(12, 14, 8, 8))
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(13, QFont.Weight.Medium))
        p.drawText(QRectF(28, 7, r.width() - 36, 20), Qt.AlignmentFlag.AlignVCenter, self.lines[0])
        p.setFont(make_font(12, mono=True))
        p.setPen(QColor(T[LEVEL_KEY[self.tl]] if self.tl in (SH.CAUTION, SH.BAD) else T["sub"]))
        p.drawText(QRectF(28, 27, 60, 18), Qt.AlignmentFlag.AlignVCenter, self.lines[1])
        p.setPen(QColor(T["mute"]))
        p.drawText(QRectF(88, 27, r.width() - 96, 18), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   self.lines[2])


class StatBox(QWidget):
    """Велике поле «Стан» чи «Температура»: підпис, значення, підзначення; рамка й тло — кольору рівня."""

    def __init__(self, caption: str):
        super().__init__()
        self.caption, self.value, self.sub, self.lvl = caption, "----", "", SH.UNKNOWN
        self.setFixedSize(200, 104)

    def set(self, value: str, sub: str, lvl: str) -> None:
        self.value, self.sub, self.lvl = value, sub, lvl
        self.setAccessibleName(f"{self.caption}: {value} {sub}")
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        key = LEVEL_KEY[self.lvl]
        bg = {"ok": "ok_bg", "warn": "warn_bg", "bad": "bad_bg"}.get(key, "surf2")
        ln = {"ok": "ok_line", "warn": "warn_line", "bad": "bad_line"}.get(key, "line2")
        p.setPen(QPen(QColor(T[ln]), 1))
        p.setBrush(QColor(T[bg]))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(QColor(T["sub"]))
        p.setFont(make_font(12))
        p.drawText(QRectF(16, 10, r.width() - 32, 18), Qt.AlignmentFlag.AlignVCenter, self.caption)
        p.setPen(QColor(T[key] if key != "mute" else T["text"]))
        p.setFont(make_font(26, QFont.Weight.Medium))
        p.drawText(QRectF(16, 32, r.width() - 32, 38), Qt.AlignmentFlag.AlignVCenter, self.value)
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(15, mono=True))
        p.drawText(QRectF(16, 72, r.width() - 32, 22), Qt.AlignmentFlag.AlignVCenter, self.sub)


class SmartTable(QWidget):
    """Таблиця SMART як у CrystalDiskInfo: крапка, ID, атрибут, поточне, найгірше, поріг, raw (hex чи dec)."""
    ROW, HEAD = 28, 32

    def __init__(self):
        super().__init__()
        self.rows, self.ata, self.hex = [], True, True
        self.setMinimumHeight(self.HEAD)

    def set(self, rows: list, hex_raw: bool = True) -> None:
        self.rows = rows
        self.ata = any(r[3] is not None for r in rows)
        self.hex = hex_raw
        self.setFixedHeight(self.HEAD + self.ROW * len(rows) + 4)
        self.setAccessibleName(tr("di.smart"))
        self.update()

    def cols(self, w: float) -> list:
        """(ключ заголовка, x, ширина, вирівнювання вправо)."""
        raw_w, num_w = 150, 72
        right = w - 12
        out = [("raw", right - raw_w, raw_w, True)]
        x = right - raw_w
        if self.ata:
            for k in ("thr", "worst", "cur"):
                x -= num_w
                out.append((k, x, num_w, True))
        out += [("id", 30, 44, False), ("name", 80, x - 92, False)]
        return out

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        cols = self.cols(w)
        al_r = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        al_l = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        p.setPen(QColor(T["mute"]))
        p.setFont(make_font(12))
        for k, x, cw, right in cols:
            p.drawText(QRectF(x, 0, cw, self.HEAD), al_r if right else al_l, tr(f"di.col.{k}"))
        p.setPen(QPen(QColor(T["line2"]), 1))
        p.drawLine(0, self.HEAD - 1, w, self.HEAD - 1)
        mono, sans = make_font(13, mono=True), make_font(13)
        for i, (lvl, aid, name, cur, worst, thr, raw) in enumerate(self.rows):
            y = self.HEAD + i * self.ROW
            if i % 2:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(T["surf2"]))
                p.drawRect(QRectF(0, y, w, self.ROW))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T[LEVEL_KEY[lvl]]))
            p.drawEllipse(QRectF(10, y + self.ROW / 2 - 4, 8, 8))
            vals = {"id": f"{aid:02X}", "name": name, "cur": cur, "worst": worst, "thr": thr,
                    "raw": f"{raw:012X}" if self.hex else f"{raw:,}".replace(",", " ")}
            for k, x, cw, right in cols:
                v = vals.get(k)
                p.setFont(sans if k == "name" else mono)
                p.setPen(QColor(T["text"] if k in ("name", "raw") or lvl == SH.GOOD else T[LEVEL_KEY[lvl]]))
                if k in ("cur", "worst", "thr"):
                    p.setPen(QColor(T["sub"]))
                p.drawText(QRectF(x, y, cw, self.ROW), al_r if right else al_l, "" if v is None else str(v))


class DiskInfoPanel(QWidget):
    """Усе про диски: вкладки, паспорт, SMART, висновки. page — HwCenterPage (run_bg, refresh_overview)."""

    def __init__(self, page):
        super().__init__()
        self.page, self.disks, self.cur, self.busy = page, [], 0, False
        self.hex_raw, self.show_serial = True, False
        v = vbox(self, spacing=12)
        bar = hbox(spacing=8)
        self.tabs = hbox(spacing=8)
        bar.addLayout(self.tabs)
        bar.addStretch()
        self.btn_refresh = button(tr("di.refresh"), None, self.load)
        bar.addWidget(self.btn_refresh)
        self.btn_copy = button(tr("di.copy"), None, self.copy)
        bar.addWidget(self.btn_copy)
        v.addLayout(bar)
        self.status = label(tr("di.loading"), "muted")
        v.addWidget(self.status)
        self.body = QFrame()
        self.body.setObjectName("card")
        bv = vbox(self.body, (20, 18, 20, 16), 14)
        head = hbox(spacing=12)
        self.title = label("", "h1", wrap=True)
        head.addWidget(self.title, 1)
        bv.addLayout(head)
        top = hbox(spacing=20)
        boxes = vbox(spacing=10)
        self.health = StatBox(tr("di.health"))
        self.temp = StatBox(tr("di.temp"))
        boxes.addWidget(self.health)
        boxes.addWidget(self.temp)
        boxes.addStretch()
        top.addLayout(boxes)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(8)
        top.addLayout(self.grid, 1)
        bv.addLayout(top)
        tools = hbox(spacing=10)
        tools.addWidget(label(tr("di.smart"), "h2"))
        tools.addStretch()
        self.serial_chip = chip(tr("di.show_serial"))
        self.serial_chip.toggled.connect(self._toggle_serial)
        tools.addWidget(self.serial_chip)
        self.raw_seg = Segmented(["Hex", "Dec"])
        self.raw_seg.changed.connect(self._raw_mode)
        tools.addWidget(self.raw_seg)
        bv.addLayout(tools)
        self.table = SmartTable()
        bv.addWidget(self.table)
        self.no_smart = label("", "desc", wrap=True)
        bv.addWidget(self.no_smart)
        self.findings = vbox(spacing=6)
        bv.addLayout(self.findings)
        v.addWidget(self.body)
        self.body.hide()
        self.timer = QTimer(self)
        self.timer.setInterval(AUTO_REFRESH_MS)
        self.timer.timeout.connect(self._auto)

    # ── дані ──
    def load(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText(tr("btn.working"))
        if not self.disks:
            self.status.setText(tr("di.loading"))
            self.status.show()
        hw = self.page.main.hw or {}
        self.page.run_bg(lambda log, p: SH.check_all(hw), self.fill)

    def _auto(self) -> None:
        if self.isVisible() and not self.busy:
            self.load()

    def fill(self, disks) -> None:
        self.busy = False
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText(tr("di.refresh"))
        if not isinstance(disks, list):
            self.status.setText(tr("di.failed"))
            return
        self.disks = disks
        HT.save(F.CFG, SH.health_result(disks))
        clear_layout(self.tabs)
        self.tab_w = []
        for i, d in enumerate(disks):
            t = DiskTab(d)
            t.clicked.connect(lambda i=i: self.select(i))
            self.tabs.addWidget(t)
            self.tab_w.append(t)
        self.status.setVisible(not disks)
        self.status.setText(tr("di.none"))
        self.body.setVisible(bool(disks))
        if disks:
            self.select(min(self.cur, len(disks) - 1))
        self.timer.start()
        self.page.refresh_overview()

    def select(self, i: int) -> None:
        self.cur = i
        for j, t in enumerate(self.tab_w):
            t.set_on(j == i)
        self.show_disk(self.disks[i])

    def show_disk(self, d: dict) -> None:
        size = f"{d['size_gb']:,}".replace(",", " ") + " GB" if d.get("size_gb") else ""
        self.title.setText(" : ".join(x for x in (d.get("name") or "?", size) if x))
        lab, life = SH.health_label(d)
        self.health.set(tr(f"di.h.{lab}"), f"{life} %" if life is not None else "", lab)
        t = (d.get("assess") or {}).get("temperature")
        self.temp.set(f"{t} °C" if t is not None else "-- °C", "", temp_level(t, is_ssd(d)))
        clear_layout(self.grid)
        rows = SH.details(d)
        half = (len(rows) + 1) // 2
        for i, (k, val) in enumerate(rows):
            r, c = (i, 0) if i < half else (i - half, 2)
            self.grid.addWidget(label(tr(k), "muted"), r, c, Qt.AlignmentFlag.AlignRight)
            if k == "di.serial" and val and not self.show_serial:
                val = MASK
            lb = label(val if val not in (None, "") else "----", wrap=True)
            lb.setStyleSheet(f"{MONO_CSS} font-size: 13px;")
            lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.grid.addWidget(lb, r, c + 1)
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(3, 1)
        tab = SH.smart_table(d)
        self.table.set(tab, self.hex_raw)
        self.table.setVisible(bool(tab))
        self.raw_seg.setVisible(bool(tab))
        self.no_smart.setVisible(not tab)
        self.no_smart.setText(tr("di.no_smart"))
        clear_layout(self.findings)
        for f in (d.get("assess") or {}).get("findings") or []:
            if f[1] == "sh.f.no_smart":
                continue
            row = hbox(spacing=8)
            row.addWidget(dot(T[{HT.FAIL: "bad", HT.WARN: "warn"}.get(f[0], "sub")]), 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(HT.finding_str(f), "desc", wrap=True), 1)
            self.findings.addLayout(row)

    # ── дії ──
    def _raw_mode(self, i: int) -> None:
        self.hex_raw = i == 0
        if self.disks:
            self.table.set(SH.smart_table(self.disks[self.cur]), self.hex_raw)

    def _toggle_serial(self, on: bool) -> None:
        self.show_serial = on
        if self.disks:
            self.show_disk(self.disks[self.cur])

    def copy(self) -> None:
        if not self.disks:
            return
        text = SH.report_text(self.disks)
        if not self.show_serial:
            for d in self.disks:
                s = dict(SH.details(d)).get("di.serial")
                if s:
                    text = text.replace(s, MASK)
        QGuiApplication.clipboard().setText(text)
        self.btn_copy.setText(tr("di.copied"))
        QTimer.singleShot(1800, lambda: self.btn_copy.setText(tr("di.copy")))

