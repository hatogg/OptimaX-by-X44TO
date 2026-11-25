"""
OptimaX — розділ «Датчики» в Hardware Center: таблиця показників за пристроями (поточне / мін / макс / середнє), як
в AIDA64 «Датчики» чи HWiNFO «Sensors only». Кнопки: скинути мін/макс, запис у CSV. Пороги температур зі
сповіщенням (з гістерезисом — без спаму).

7.1.1-правило продуктивності: опитування раз на секунду лише поки розділ на екрані й вікно не згорнуте. Виняток —
увімкнений запис у CSV (користувач сам попросив писати, зокрема під час гри зі згорнутим вікном): тоді опитування
триває, а таблиця не перемальовується, поки її не видно; сповіщення тоді йдуть у трей (Main.toast).
Читання — у фоновому потоці (sensors.Hub.read), щоб повільне джерело не гальмувало інтерфейс.
"""
from __future__ import annotations

import os
import threading
import time

from PyQt6.QtCore import QEvent, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QFileDialog, QSpinBox, QWidget

import features as F
import sensors as S
from i18n import tr
from ui_kit import LOG, T, Ask, Switch, button, hbox, label, make_font, section_card, vbox

LIMIT_KEYS = ("cpu", "gpu", "ssd", "hdd")


class SensorTable(QWidget):
    """Намальована таблиця: заголовок групи (пристрій), під ним показники; числа — моноширинним шрифтом із
    одиницями, перевищений поріг — червоним."""
    ROW, HEAD, GROUP = 26, 30, 34
    COLS = ("cur", "min", "max", "avg")

    def __init__(self):
        super().__init__()
        self.groups, self.stats, self.hot = [], {}, set()
        self.setMinimumHeight(self.HEAD)
        self.setAccessibleName(tr("sn.title"))

    def set(self, groups: list, stats: dict, hot: set) -> None:
        self.groups, self.stats, self.hot = groups, stats, hot
        h = self.HEAD + sum(self.GROUP + self.ROW * len(rows) for _g, rows in groups) + 4
        if self.height() != h:
            self.setFixedHeight(h)
        self.update()

    def col_x(self, w: float) -> list:
        num = 96 if w > 640 else 78
        right = w - 10
        xs = []
        for k in reversed(self.COLS):
            right -= num
            xs.append((k, right, num))
        return list(reversed(xs))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        cols = self.col_x(w)
        name_w = cols[0][1] - 28
        al_r = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        al_l = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        p.setFont(make_font(12))
        p.setPen(QColor(T["mute"]))
        p.drawText(QRectF(12, 0, name_w, self.HEAD), al_l, tr("sn.col.name"))
        for k, x, cw in cols:
            p.drawText(QRectF(x, 0, cw - 6, self.HEAD), al_r, tr(f"sn.col.{k}"))
        p.setPen(QPen(QColor(T["line2"]), 1))
        p.drawLine(0, self.HEAD - 1, w, self.HEAD - 1)
        mono, sans, head = make_font(13, mono=True), make_font(13), make_font(13, QFont.Weight.Medium)
        small = make_font(11)
        y = self.HEAD
        for g, rows in self.groups:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T["surf2"]))
            p.drawRoundedRect(QRectF(2, y + 4, w - 4, self.GROUP - 6), 8, 8)
            p.setPen(QColor(T["text"]))
            p.setFont(head)
            kind = tr(f"sn.k.{g['kind']}")
            p.drawText(QRectF(12, y + 4, w - 24, self.GROUP - 6), al_l,
                       p.fontMetrics().elidedText(g["title"], Qt.TextElideMode.ElideRight, int(w * 0.7)))
            p.setFont(small)
            p.setPen(QColor(T["mute"]))
            p.drawText(QRectF(12, y + 4, w - 24, self.GROUP - 6), al_r, kind)
            y += self.GROUP
            for r in rows:
                st = self.stats.get(r["id"]) or S.Stat()
                hot = r["id"] in self.hot
                if hot:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(T["bad_bg"]))
                    p.drawRect(QRectF(0, y, w, self.ROW))
                    p.setBrush(QColor(T["bad"]))
                    p.drawEllipse(QRectF(10, y + self.ROW / 2 - 3, 6, 6))
                p.setFont(sans)
                p.setPen(QColor(T["text"] if not hot else T["bad"]))
                p.drawText(QRectF(24, y, name_w, self.ROW), al_l,
                           p.fontMetrics().elidedText(S.name_text(r), Qt.TextElideMode.ElideRight, int(name_w)))
                unit = S.unit_text(r["unit"])
                p.setFont(mono)
                for k, x, cw in cols:
                    v = st.cur if k == "cur" else st.min if k == "min" else st.max if k == "max" else st.avg
                    text = S.fmt(v, r["unit"])
                    text = f"{text} {unit}" if v is not None else text
                    p.setPen(QColor(T["bad"] if hot and k == "cur" else T["text"] if k == "cur" else T["sub"]))
                    p.drawText(QRectF(x, y, cw - 6, self.ROW), al_r, text)
                y += self.ROW


class SensorsPanel(QWidget):
    """page — HwCenterPage (main: toast, hw)."""
    got = pyqtSignal(object)

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.hub = S.Hub(page.main.hw or {})
        self.alerts = S.Alerts()
        self.limits = S.load_limits(F.CFG)
        self.rec = None
        self.rec_cols = []
        self._job = None
        self._hw_seen = bool(page.main.hw)
        self._restart = False  # 7.2: залізо визначилось — новий Hub, щойно поточне читання закінчиться
        self._win = None
        self.got.connect(self._consume)
        v = vbox(self, spacing=12)
        c, cv = section_card(tr("sn.title"), tr("sn.sub"))
        bar = hbox(margins=(14, 4, 14, 6), spacing=8)
        self.btn_reset = button(tr("sn.reset"), None, self.reset)
        bar.addWidget(self.btn_reset)
        self.btn_rec = button(tr("sn.rec"), "primary", self.toggle_record)
        bar.addWidget(self.btn_rec)
        self.rec_state = label("", "muted")
        bar.addWidget(self.rec_state, 1)
        cv.addLayout(bar)
        self.banner = label("", "warnNote", wrap=True)
        self.banner.hide()
        cv.addWidget(self.banner)
        self.table = SensorTable()
        tw = QWidget()
        th = vbox(tw, (8, 0, 8, 6))
        th.addWidget(self.table)
        cv.addWidget(tw)
        self.note = label("", "desc", wrap=True)
        self.note.setContentsMargins(14, 0, 14, 4)
        self.note.hide()
        cv.addWidget(self.note)
        cv.addWidget(self._muted(tr("sn.note.pause")))
        v.addWidget(c)
        v.addWidget(self._alerts_card())
        self.timer = QTimer(self)
        self.timer.setInterval(S.INTERVAL_MS)
        self.timer.timeout.connect(self._tick)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    @staticmethod
    def _muted(text: str):
        lb = label(text, "muted", wrap=True)
        lb.setContentsMargins(14, 0, 14, 6)
        return lb

    def _alerts_card(self):
        c, cv = section_card(tr("sn.al.title"), tr("sn.al.sub", h=f"{S.HYSTERESIS:.0f}", n=S.HOLD))
        row = hbox(margins=(14, 4, 14, 4), spacing=10)
        self.al_on = Switch()
        self.al_on.setChecked(self.limits["on"])
        self.al_on.toggled.connect(lambda _on: self._save_limits())
        row.addWidget(self.al_on)
        row.addWidget(label(tr("sn.al.on"), "desc"))
        row.addStretch()
        cv.addLayout(row)
        grid = hbox(margins=(14, 2, 14, 8), spacing=10)
        self.spins = {}
        for k in LIMIT_KEYS:
            grid.addWidget(label(tr(f"sn.al.{k}"), "desc"))
            sp = QSpinBox()
            lo, hi = S.LIMIT_RANGE[k]
            sp.setRange(lo, hi)
            sp.setSuffix(" °C")
            sp.setValue(self.limits[k])
            sp.valueChanged.connect(lambda _v: self.save_timer.start())
            grid.addWidget(sp)
            self.spins[k] = sp
            grid.addSpacing(6)
        grid.addStretch()
        self.btn_defaults = button(tr("sn.al.defaults"), "ghost", self._defaults)
        grid.addWidget(self.btn_defaults)
        cv.addLayout(grid)
        self.save_timer = QTimer(self)  # налаштування — не на кожен крок стрілки лічильника
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(600)
        self.save_timer.timeout.connect(self._save_limits)
        return c

    def _defaults(self):
        for k, sp in self.spins.items():
            sp.setValue(S.DEFAULT_LIMITS[k])
        self._save_limits()

    def _save_limits(self):
        d = {"on": self.al_on.isChecked(), **{k: sp.value() for k, sp in self.spins.items()}}
        F.CFG["sensor_alerts"] = d
        self.limits = S.load_limits(F.CFG)
        if not self.limits["on"]:
            self.alerts.reset()

    # ── опитування ──
    def _active(self) -> bool:
        return self.rec is not None or (self.isVisible() and not self.window().isMinimized())

    def _resume(self) -> None:
        if not self.timer.isActive() and self._active():
            self.timer.start()
            self._tick()

    def showEvent(self, e):
        super().showEvent(e)
        win = self.window()
        if win is not self and win is not self._win:
            # 7.2: згорнуте вікно лишає isVisible() — сам таймер не мав би тікати; стан вікна чуємо фільтром
            if self._win is not None:
                self._win.removeEventFilter(self)
            self._win = win
            win.installEventFilter(self)
        self._resume()

    def hideEvent(self, e):
        super().hideEvent(e)
        if self.rec is None:
            self.timer.stop()

    def eventFilter(self, obj, e):
        if obj is self._win and e.type() == QEvent.Type.WindowStateChange:
            if self._win.isMinimized():
                if self.rec is None:
                    self.timer.stop()
            elif self.isVisible():
                self._resume()
        return False

    def _tick(self) -> None:
        if not self._active():
            if self.rec is None:
                self.timer.stop()
            return
        if not self._hw_seen and self.page.main.hw:  # залізо визначилось після відкриття розділу
            self._hw_seen = True
            self._restart = True
        if self._job is not None and self._job.is_alive():
            return  # попереднє читання ще йде (повільне джерело) — пропускаємо такт, а не множимо потоки
        if self._restart:
            self._restart_hub()
        self._job = threading.Thread(target=self._read, daemon=True, name="optimax-sensors")
        self._job.start()

    def _restart_hub(self) -> None:
        """Лише коли фонового читання немає (див. _tick): Hub не закривається посеред читання."""
        self._restart = False
        self.hub.close()
        self.hub = S.Hub(self.page.main.hw or {})

    def _read(self) -> None:
        hub = self.hub
        try:
            res = hub.read()
        except Exception as e:  # noqa: BLE001 — не мовчимо: у журнал, а таблиця лишається «—»
            res = e
        try:
            self.got.emit((hub, res))
        except RuntimeError:
            pass  # панель уже знищено (вихід із програми)

    def _consume(self, item) -> None:
        hub, res = item
        if hub is not self.hub:
            return
        if isinstance(res, Exception):
            LOG.write(f"[!] {tr('sn.title')}: {type(res).__name__}: {res}"[:200])
            return
        rows = self.hub.feed(res)
        now = time.time()
        if self.limits["on"]:
            raised, cleared = self.alerts.update(rows, self.limits)
            for r, lim in raised:
                msg = tr("sn.al.raised", what=f"{r['gtitle']} — {S.name_text(r)}", v=S.fmt(r["value"], "c"), lim=lim)
                LOG.write(f"[!] {msg}")
                self.page.main.toast(msg, "bad")
            for r in cleared:
                LOG.write(tr("sn.al.cleared", what=f"{r['gtitle']} — {S.name_text(r)}", v=S.fmt(r["value"], "c")))
        if self.rec is not None:
            self._write_record(now)
        if self.isVisible() and not self.window().isMinimized():
            self._render(rows)

    def _render(self, rows: list) -> None:
        hot = set(self.alerts.active) if self.limits["on"] else set()
        self.table.set(S.group_rows(rows), self.hub.stats, hot)
        if hot:
            what = [f"{r['gtitle']} — {S.fmt(r['value'], 'c')} °C" for r in rows if r["id"] in hot]
            self.banner.setText(tr("sn.al.banner", what="; ".join(what)))
        self.banner.setVisible(bool(hot))
        cpu_t = next((r for r in rows if r["id"] == "cpu.temp"), None)
        st = self.hub.stats.get("cpu.temp")
        no_temp = cpu_t is not None and cpu_t["value"] is None and not (st and st.n)
        self.note.setText(tr("sn.note.cpu_temp") if no_temp else "")
        self.note.setVisible(no_temp)

    # ── кнопки ──
    def reset(self) -> None:
        self.hub.reset()
        self._render(self.hub.rows)
        LOG.write(tr("sn.log.reset"))

    def toggle_record(self) -> None:
        if self.rec is not None:
            self.stop_record()
            return
        if not self.hub.rows:
            Ask.info(self, tr("sn.title"), tr("sn.rec_wait"))
            return
        name = time.strftime("OptimaX-sensors-%Y%m%d-%H%M%S.csv")
        path, _ = QFileDialog.getSaveFileName(self, tr("sn.rec"), name, "CSV (*.csv)")
        if not path:
            return
        cols = [(r["id"], r["gtitle"], S.name_text(r), r["unit"]) for r in self.hub.rows]
        try:
            self.rec = S.CsvLog(path, cols)
        except PermissionError:
            Ask.info(self, tr("sn.rec"), tr("sn.rec_refused"))
            return
        except OSError as e:
            Ask.info(self, tr("sn.rec"), tr("sn.rec_err", err=str(e)))
            return
        LOG.write(tr("sn.log.rec_on", path=path))
        self.btn_rec.setText(tr("sn.rec_stop"))
        self.btn_rec.setObjectName("danger")
        self.btn_rec.style().polish(self.btn_rec)
        self._rec_label()

    def _write_record(self, ts: float) -> None:
        try:
            self.rec.write(ts, {r["id"]: r["value"] for r in self.hub.rows})
        except OSError as e:  # диск заповнено / флешку вийняли — кажемо, а не пишемо «записано»
            LOG.write(tr("sn.rec_err", err=str(e)))
            self.page.main.toast(tr("sn.rec_err", err=str(e))[:120], "bad")
            self.stop_record(failed=True)
            return
        self._rec_label()

    def _rec_label(self) -> None:
        if self.rec is not None:
            self.rec_state.setText(tr("sn.rec_on", file=os.path.basename(self.rec.path), n=self.rec.rows))

    def stop_record(self, failed: bool = False) -> None:
        rec, self.rec = self.rec, None
        if rec is None:
            return
        try:
            rec.close()
        except OSError as e:
            failed = True
            LOG.write(tr("sn.rec_err", err=str(e)))
        if not failed:
            LOG.write(tr("sn.log.rec_off", path=rec.path, n=rec.rows))
            self.page.main.toast(tr("sn.rec_saved", n=rec.rows))
        self.btn_rec.setText(tr("sn.rec"))
        self.btn_rec.setObjectName("primary")
        self.btn_rec.style().polish(self.btn_rec)
        self.rec_state.setText("")
        if not self._active():  # сховано чи згорнуто — без запису опитування не потрібне
            self.timer.stop()

    def shutdown(self) -> None:
        self.timer.stop()
        self.stop_record()
        if self._job is not None and self._job.is_alive():
            self._job.join(2.0)
        self.hub.close()  # читання ще йде — джерела закриє сам потік, коли дочитає (Hub.close)
