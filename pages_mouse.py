"""
OptimaX — Hardware Center, розділ «Миша». Логіка — у mousetools.py; тут інтерфейс: тест частоти опитування (Raw Input
через фільтр нативних подій Qt, у демо — імітований потік), налаштування вказівника Windows із рекомендацією для ігор
і перерахунок чутливості між іграми. Змінюється система лише твіком disable_mouse_accel через журнал відкату.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer, QAbstractNativeEventFilter, QCoreApplication
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import QDialog, QGridLayout, QSpinBox, QComboBox, QLineEdit

import engine as E
import mousetools as MT
from i18n import tr
from ui_kit import T, label, button, vbox, hbox, badge, style_badge, Ask, Ring, clear_layout, dot


# ───────────────────────── тест частоти опитування ─────────────────────────
class _RawFilter(QAbstractNativeEventFilter):
    """WM_INPUT з черги повідомлень Qt → RawMouse. Помилку не ховаємо: її покаже результат тесту."""

    def __init__(self, raw: MT.RawMouse):
        super().__init__()
        import ctypes.wintypes as W
        self.raw = raw
        self.MSG = W.MSG

    def nativeEventFilter(self, event_type, message):
        try:
            if bytes(event_type) == b"windows_generic_MSG" and message:
                m = self.MSG.from_address(int(message))
                if m.message == MT.WM_INPUT:
                    self.raw.on_input(m.lParam or 0)
        except Exception as e:  # виняток у віртуальному методі Qt закрив би програму — записуємо в результат
            self.raw.error = self.raw.error or f"{type(e).__name__}: {e}"
        return False, 0


class PollDialog(QDialog):
    """Тест триває SECONDS від першого руху; далі — статистика mousetools.poll_stats()."""

    SECONDS = 5.0
    MAX_WAIT = 30.0  # без руху довше — завершити з чесним «замало подій»
    SPEED = 1.0  # демо: прискорення віртуального часу (тести інтерфейсу)

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("mouse.poll.dlg"))
        self.setModal(True)
        self.setMinimumSize(520, 280)
        v = vbox(self, (24, 22, 24, 18), 12)
        v.addWidget(label(tr("mouse.poll.dlg"), "h2"))
        v.addWidget(label(tr("mouse.poll.hint", s=int(self.SECONDS)), "sub", wrap=True))
        self.state = label(tr("mouse.poll.wait"), "h3")
        v.addWidget(self.state, 1)
        h = hbox(spacing=8)
        h.addStretch()
        h.addWidget(button(tr("mouse.poll.stop"), "primary", self.accept))
        v.addLayout(h)
        self.demo = not E.IS_WIN
        self.res = None
        self.opened = time.perf_counter()
        self.t0 = None
        self.raw = None
        self.flt = None
        self.times = []
        if self.demo:
            self.stream = MT.demo_stream(MT.demo_rate(), self.SECONDS + 0.5)
            self.t0 = self.opened
        else:
            self.raw = MT.RawMouse()
            if self.raw.start(int(self.winId())):
                self.flt = _RawFilter(self.raw)
                QCoreApplication.instance().installNativeEventFilter(self.flt)
        self.timer = QTimer(self)
        self.timer.setInterval(100)  # лише підпис; події рахує фільтр — частіше оновлювати нема чого
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _elapsed(self) -> float:
        return (time.perf_counter() - self.t0) * (self.SPEED if self.demo else 1.0) if self.t0 else 0.0

    def _tick(self) -> None:
        if self.res is not None:
            return
        if self.demo:
            self._feed_demo()
            n = len(self.times)
        else:
            if self.raw.error and not self.raw.registered:
                self.accept()
                return
            n = self.raw.count()
            if n and self.t0 is None:
                self.t0 = time.perf_counter()
        if self.t0 is None:
            if time.perf_counter() - self.opened > self.MAX_WAIT:
                self.accept()
            return
        left = self.SECONDS - self._elapsed()
        self.state.setText(tr("mouse.poll.live", n=n, s=max(0, round(left, 1))))
        if left <= 0:
            self.accept()

    def finish(self) -> dict:
        """Зупинити збір і порахувати (повторний виклик повертає той самий результат)."""
        if self.res is not None:
            return self.res
        self.timer.stop()
        if self.demo:
            self._feed_demo()
            self.res = dict(MT.poll_stats(self.times), demo=True, devices=1)
            return self.res
        if self.flt is not None:
            QCoreApplication.instance().removeNativeEventFilter(self.flt)
            self.flt = None
        self.raw.stop()
        if not self.raw.devices and self.raw.error:
            self.res = {"ok": False, "reason": "noraw", "error": self.raw.error}
        elif not self.raw.devices and self.raw.absolute:
            self.res = {"ok": False, "reason": "absolute"}
        else:
            self.res = dict(MT.poll_stats(self.raw.main_stream()), devices=len(self.raw.devices),
                            error=self.raw.error)  # збій розбору частини подій — показати поруч із цифрою
        return self.res

    def _feed_demo(self) -> None:
        el = self._elapsed()
        self.times = [t for t in self.stream if t <= el]

    def done(self, r):
        self.finish()  # Esc / закриття вікна: реєстрацію Raw Input знімаємо завжди
        super().done(r)


def run_poll(page) -> None:
    dlg = PollDialog(page)
    dlg.exec()
    show_poll(page, dlg.finish())


def show_poll(page, res: dict) -> None:
    ms = page.ms
    ms["poll"] = res
    clear_layout(ms["poll_notes"])
    ms["poll_btn"].setText(tr("mouse.poll.again"))
    notes = []
    if res.get("ok"):
        ms["poll_hz"].setText(tr("mouse.poll.hz", hz=res["median_hz"]))
        style_badge(ms["poll_badge"], tr("mouse.poll.nearest", hz=res["nearest"]),
                    "warn" if res.get("low") or res["stability"] < 70 else "ok")
        ms["poll_badge"].show()
        ms["poll_ring"].set_value(res["stability"] / 100.0, T["acc"])
        ms["poll_ring"].show()
        rows = [(tr("mouse.poll.median"), tr("mouse.poll.hz", hz=res["median_hz"])),
                (tr("mouse.poll.avg"), tr("mouse.poll.hz", hz=res["avg_hz"])),
                (tr("mouse.poll.stability"), tr("mouse.poll.stability_v", p=res["stability"])),
                (tr("mouse.poll.events"), str(res["events"])),
                (tr("mouse.poll.active"), tr("mouse.poll.active_v", s=round(res["active_s"], 1))),
                (tr("mouse.poll.devices"), str(res.get("devices") or 1))]
        if res.get("low"):
            notes.append(("warn", tr("mouse.poll.low", hz=res["nearest"])))
        if res["stability"] < 70:
            notes.append(("warn", tr("mouse.poll.unstable")))
        if res["nearest"] >= 4000:
            notes.append(("sub", tr("mouse.poll.high")))
        if res.get("error"):
            notes.append(("warn", tr("mouse.poll.noraw", err=res["error"])))
    else:
        ms["poll_hz"].setText("—")
        ms["poll_badge"].hide()
        ms["poll_ring"].hide()
        rows = []
        if res.get("reason") == "noraw":
            notes.append(("bad", tr("mouse.poll.noraw", err=res.get("error") or "?")))
        elif res.get("reason") == "absolute":
            notes.append(("warn", tr("mouse.poll.absolute")))
        else:
            notes.append(("warn", tr("mouse.poll.few", n=res.get("events", 0),
                                     s=round(res.get("active_s") or 0, 1))))
    if res.get("demo"):
        notes.append(("sub", tr("mouse.poll.demo")))
    _kv(ms["poll_kv"], rows)
    for kind, text in notes:
        r = hbox(spacing=8)
        r.addWidget(dot(T[kind]), 0, Qt.AlignmentFlag.AlignTop)
        r.addWidget(label(text, "desc", wrap=True), 1)
        ms["poll_notes"].addLayout(r)


def _kv(grid: QGridLayout, rows) -> None:
    for i in range(grid.count()):
        w = grid.itemAt(i).widget()
        if w is not None:
            w.hide()  # deleteLater спрацює лише в циклі подій — старі рядки не мають просвічувати до того
    clear_layout(grid)
    for i, (k, v) in enumerate(rows):
        r, c = divmod(i, 2)
        grid.addWidget(label(k, "muted"), r, c * 2)
        grid.addWidget(label(v, "rowTitle"), r, c * 2 + 1)


# ───────────────────────── налаштування Windows ─────────────────────────
def sync_settings(page) -> None:
    ms = page.ms
    s = MT.read_settings()
    ms["settings"] = s
    if s["speed"]:
        sp = tr("mouse.win.speed_v", v=s["speed"], n=s["notch"], m=f"{s['mult']:.2f}")
    else:
        sp = tr("hwc.na")
    if s["accel"] is None:
        ac = tr("hwc.na")
    elif s["accel"]:
        ac = tr("mouse.win.accel_on", s=s["mouse_speed"], a=s["t1"] if s["t1"] is not None else "?",
                b=s["t2"] if s["t2"] is not None else "?")
    else:
        ac = tr("mouse.win.accel_off")
    ms["speed_v"].setText(sp)
    ms["accel_v"].setText(ac)
    style_badge(ms["speed_b"], tr("mouse.win.ok" if s["speed_ok"] else "mouse.win.differs"),
                "ok" if s["speed_ok"] else "warn")
    style_badge(ms["accel_b"], tr("mouse.win.ok" if s["accel_ok"] else "mouse.win.differs"),
                "ok" if s["accel_ok"] else "warn")
    applied = E.JOURNAL.has(MT.ACCEL_TWEAK)
    ms["applied"].setVisible(applied)
    ms["undo_btn"].setVisible(applied)
    ms["apply_btn"].setEnabled(not s["ok"])


def apply_rec(page) -> None:
    t = E.BY_ID[MT.ACCEL_TWEAK]
    if not Ask.ask(page, t.title, tr("mouse.win.apply_q"), tr("btn.apply")):
        return
    hw = page.main.hw or {}
    page.main.run_quick(t.title, lambda log, p: E.apply_tweaks([t], log, header=False, hw=hw),
                        busy=page.ms["apply_btn"], on_done=lambda _r: sync_settings(page))


def undo_rec(page) -> None:
    t = E.BY_ID[MT.ACCEL_TWEAK]
    page.main.run_quick(t.title, lambda log, p: E.undo_or_default(t, log), busy=page.ms["undo_btn"],
                        on_done=lambda _r: sync_settings(page), ok_msg=tr("toast.off", what=t.title))


# ───────────────────────── перерахунок чутливості ─────────────────────────
def fmt_sens(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") if x else "0"


def _float(text: str) -> float:
    try:
        return float(text.replace(",", ".").strip())
    except ValueError:
        return 0.0


def update_conv(page) -> None:
    ms = page.ms
    dpi = ms["dpi"].value()
    sens = _float(ms["sens"].text())
    src, dst = ms["from"].currentData(), ms["to"].currentData()
    if dpi <= 0 or sens <= 0 or not src or not dst:
        ms["conv_out"].setText(tr("mouse.conv.bad"))
        _kv(ms["conv_kv"], [])
        return
    r = MT.convert(dpi, sens, src, dst)
    ms["conv_out"].setText(tr("mouse.conv.result", s=fmt_sens(r["sens"])))
    _kv(ms["conv_kv"], [(tr("mouse.conv.cm"), f"{r['cm360']:.1f}"), (tr("mouse.conv.in"), f"{r['in360']:.1f}"),
                        (tr("mouse.conv.edpi", game=MT.GAMES[src][0]), f"{r['edpi']:g}"),
                        (tr("mouse.conv.edpi", game=MT.GAMES[dst][0]), f"{r['dst_edpi']:.0f}")])
    ms["conv"] = r


def _grid() -> QGridLayout:
    g = QGridLayout()
    g.setContentsMargins(14, 4, 14, 6)
    g.setHorizontalSpacing(18)
    g.setVerticalSpacing(6)
    for c in (1, 3):
        g.setColumnStretch(c, 1)
    return g


# ───────────────────────── розділ ─────────────────────────
def build(page, v) -> None:
    ms = page.ms = {}
    # частота опитування
    c, cv = page.section(v, tr("mouse.poll.title"), tr("mouse.poll.sub"))
    head = hbox(margins=(14, 4, 14, 4), spacing=14)
    ms["poll_ring"] = Ring(T["acc"], 64, 6, 14)
    ms["poll_ring"].hide()
    head.addWidget(ms["poll_ring"])
    col = vbox(spacing=4)
    ms["poll_hz"] = label(tr("mouse.poll.none"), "h2")
    col.addWidget(ms["poll_hz"])
    ms["poll_badge"] = badge("", "muted")
    ms["poll_badge"].hide()
    col.addWidget(ms["poll_badge"])
    head.addLayout(col)
    head.addStretch(1)
    ms["poll_btn"] = button(tr("mouse.poll.run"), "primary", lambda: run_poll(page))
    head.addWidget(ms["poll_btn"], 0, Qt.AlignmentFlag.AlignVCenter)
    cv.addLayout(head)
    ms["poll_kv"] = _grid()
    cv.addLayout(ms["poll_kv"])
    ms["poll_notes"] = vbox(margins=(14, 2, 14, 4), spacing=4)
    cv.addLayout(ms["poll_notes"])

    # налаштування Windows
    c, cv = page.section(v, tr("mouse.win.title"), tr("mouse.win.sub"))
    for key in ("speed", "accel"):
        row = vbox(margins=(14, 4, 14, 4), spacing=2)
        h = hbox(spacing=10)
        h.addWidget(label(tr(f"mouse.win.{key}"), "rowTitle"))
        h.addStretch()
        ms[f"{key}_v"] = label("", "mono")
        h.addWidget(ms[f"{key}_v"])
        ms[f"{key}_b"] = badge("", "muted")
        h.addWidget(ms[f"{key}_b"])
        row.addLayout(h)
        row.addWidget(label(tr(f"mouse.win.{key}_d"), "desc", wrap=True))
        cv.addLayout(row)
    cv.addWidget(page._note(tr("mouse.win.rec")))
    ms["applied"] = page._note(tr("mouse.win.applied"))
    cv.addWidget(ms["applied"])
    br = hbox(margins=(14, 4, 14, 4), spacing=8)
    br.addStretch()
    ms["undo_btn"] = button(tr("mouse.win.undo"), "ghost", lambda: undo_rec(page))
    br.addWidget(ms["undo_btn"])
    ms["apply_btn"] = button(tr("mouse.win.apply"), "primary", lambda: apply_rec(page))
    br.addWidget(ms["apply_btn"])
    cv.addLayout(br)
    sync_settings(page)

    # перерахунок чутливості
    c, cv = page.section(v, tr("mouse.conv.title"), tr("mouse.conv.sub"))
    g = _grid()
    ms["dpi"] = QSpinBox()
    ms["dpi"].setRange(50, 64000)
    ms["dpi"].setSingleStep(50)
    ms["dpi"].setValue(800)
    ms["sens"] = QLineEdit("1")
    ms["sens"].setValidator(QDoubleValidator(0.0, 1000.0, 4))
    ms["from"], ms["to"] = QComboBox(), QComboBox()
    for cb in (ms["from"], ms["to"]):
        for gid, (name, _yaw) in MT.GAMES.items():
            cb.addItem(name, gid)
    ms["to"].setCurrentIndex(list(MT.GAMES).index("valorant"))
    for i, (key, w) in enumerate((("dpi", ms["dpi"]), ("sens", ms["sens"]), ("from", ms["from"]),
                                  ("to", ms["to"]))):
        r, cc = divmod(i, 2)
        g.addWidget(label(tr(f"mouse.conv.{key}"), "muted"), r, cc * 2)
        g.addWidget(w, r, cc * 2 + 1)
    cv.addLayout(g)
    ms["conv_out"] = label("", "h3")
    ms["conv_out"].setContentsMargins(14, 6, 14, 0)
    cv.addWidget(ms["conv_out"])
    ms["conv_kv"] = _grid()
    cv.addLayout(ms["conv_kv"])
    ms["dpi"].valueChanged.connect(lambda _v: update_conv(page))
    ms["sens"].textChanged.connect(lambda _t: update_conv(page))
    ms["from"].currentIndexChanged.connect(lambda _i: update_conv(page))
    ms["to"].currentIndexChanged.connect(lambda _i: update_conv(page))
    update_conv(page)


def show(page) -> None:
    if getattr(page, "ms", None):
        sync_settings(page)  # налаштування могли змінити в Панелі керування, поки розділ був закритий
