"""
OptimaX — сторінка «Пам'ять» (6.13): живе кільце й графік зайнятої RAM, хто її тримає, і кнопка «Звільнити пам'ять»
зі скляним вікном прогресу, результатом «до → після» і чесною перевіркою через хвилину (memtools.py).
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QFont, QLinearGradient
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QProgressBar

import engine as E
import features as F
import memtools as MT
import ui_kit as UK
import ui_motion as UM
from i18n import tr
from ui_kit import (T, qc, label, button, card, vbox, hbox, scroller, page_header, make_font, Switch, Worker, LOG)


def gb(mb: float, digits: int = 1) -> str:
    return tr("u.gb", v=f"{mb / 1024:.{digits}f}")


class Stat(QWidget):
    """Підпис дрібними великими літерами і значення під ним."""

    def __init__(self, caption: str, color_key: str = None):
        super().__init__()
        v = vbox(self, spacing=2)
        self.cap = label(caption.upper(), "micro")
        v.addWidget(self.cap)
        self.val = UM.CountLabel(lambda x: gb(x), ms=700)
        self.val.setStyleSheet("font-size: 19px; font-weight: 700;")
        self.color_key = color_key
        v.addWidget(self.val)
        self.retheme()

    def retheme(self):
        if self.color_key:
            self.val.setStyleSheet(f"font-size: 19px; font-weight: 700; color: {T[self.color_key]};")


class ConsumerRow(QWidget):
    """Рядок «хто займає»: кольорова смуга за станом, ініціал, назва, скільки процесів, частка пам'яті."""
    STATE = {"active": "acc", "background": "pink", "idle": "mute"}

    def __init__(self):
        super().__init__()
        self.setFixedHeight(54)
        self.g = None
        self.top = 1.0
        self.k = 0.0
        self.anim = UM.Anim(self, self._set, 600)

    def _set(self, k):
        self.k = k
        self.update()

    def set_data(self, g: dict, top_mb: float, animate: bool) -> None:
        first = self.g is None
        self.g, self.top = g, max(1.0, top_mb)
        if first and animate:
            self.anim.to(1.0, 0.0)
        else:
            self.anim.set(1.0)
        self.update()

    def paintEvent(self, _):
        if not self.g:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = self.g
        key = self.STATE.get(g["state"], "mute")
        r = QRectF(self.rect()).adjusted(0, 3, 0, -3)
        grad = QLinearGradient(r.topLeft(), r.topRight())
        grad.setColorAt(0, qc(key, 46 if UK.is_dark() else 30))
        grad.setColorAt(0.6, qc(key, 8))
        grad.setColorAt(1, qc(key, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(r, 12, 12)
        p.setBrush(QColor(T[key]))
        p.drawRoundedRect(QRectF(r.left(), r.top() + 10, 3, r.height() - 20), 1.5, 1.5)
        # ініціал у колі
        c = QPointF(r.left() + 30, r.center().y())
        p.setBrush(qc(key, 60))
        p.drawEllipse(c, 15, 15)
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(13, QFont.Weight.Bold))
        p.drawText(QRectF(c.x() - 15, c.y() - 15, 30, 30), Qt.AlignmentFlag.AlignCenter, (g["title"] or "?")[:1])
        x = r.left() + 56
        right_w = max(260, int(r.width() * 0.42))
        p.setFont(make_font(14, QFont.Weight.DemiBold))
        p.drawText(QRectF(x, r.top() + 7, r.width() - x - right_w, 20), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(g["title"], Qt.TextElideMode.ElideRight, int(r.width() - x - right_w)))
        p.setPen(QColor(T["mute"]))
        f = make_font(10, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.7)
        p.setFont(f)
        sub = tr(f"mem.state.{g['state']}").upper() + " · " + tr("mem.procs", n=g["count"]).upper()
        p.drawText(QRectF(x, r.top() + 27, r.width() - x - right_w, 16), Qt.AlignmentFlag.AlignVCenter, sub)
        # частка
        bar = QRectF(r.right() - right_w + 16, r.center().y() - 3, right_w - 110, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T["line"]))
        p.drawRoundedRect(bar, 3, 3)
        fill = QRectF(bar.left(), bar.top(), bar.width() * min(1.0, g["mb"] / self.top) * self.k, bar.height())
        bg = QLinearGradient(fill.topLeft(), fill.topRight())
        bg.setColorAt(0, QColor(T["acc"]))
        bg.setColorAt(1, QColor(T[key if key != "mute" else "acc_h"]))
        p.setBrush(bg)
        p.drawRoundedRect(fill, 3, 3)
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(14, QFont.Weight.DemiBold))
        p.drawText(QRectF(r.right() - 84, r.top(), 72, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, gb(g["mb"] * self.k))


class BeforeAfter(QWidget):
    """Смуга «було → стало»: заповнення стискається від «було» до «стало»."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(46)
        self.before = self.after = 0.0
        self.t = 0.0
        self.anim = UM.Anim(self, self._set, 1100)

    def _set(self, t):
        self.t = t
        self.update()

    def play(self, before: float, after: float) -> None:
        self.before, self.after = before, after
        self.anim.to(1.0, 0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        bar = QRectF(r.left(), 6, r.width(), 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T["line"]))
        p.drawRoundedRect(bar, 3, 3)
        if self.before > 0:
            frac = UM.lerp(1.0, self.after / self.before, self.t)
            fill = QRectF(bar.left(), bar.top(), bar.width() * frac, bar.height())
            g = QLinearGradient(fill.topLeft(), fill.topRight())
            g.setColorAt(0, QColor(T["acc"]))
            g.setColorAt(1, QColor(T["ok"]))
            p.setBrush(g)
            p.drawRoundedRect(fill, 3, 3)
        p.setFont(make_font(11))
        p.setPen(QColor(T["mute"]))
        p.drawText(QRectF(r.left(), 18, r.width() / 2, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   tr("mem.was", v=gb(self.before)))
        p.setPen(QColor(T["ok"]))
        p.setFont(make_font(11, QFont.Weight.DemiBold))
        p.drawText(QRectF(r.center().x(), 18, r.width() / 2, 22),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, tr("mem.now", v=gb(self.after)))


class StepRow(QWidget):
    """Крок у вікні звільнення: очікує → виконується (кільце) → готово (галочка)."""

    def __init__(self, text: str):
        super().__init__()
        h = hbox(self, spacing=10)
        self.ico = QWidget()
        self.ico.setFixedSize(20, 20)
        self.spin = UM.Spinner(18)
        self.spin.hide()
        self.done_mark = QLabel()
        self.done_mark.setFixedSize(20, 20)
        self.done_mark.hide()
        self.dot = QLabel()
        self.dot.setFixedSize(20, 20)
        h.addWidget(self.dot)
        h.addWidget(self.spin)
        h.addWidget(self.done_mark)
        self.text = label(text, "rowTitle")
        h.addWidget(self.text, 1)
        self.val = label("", "desc")
        h.addWidget(self.val)
        self.state = "wait"
        self.retheme()

    def retheme(self):
        self.dot.setPixmap(_circle_pixmap(T["line3"]))
        self.done_mark.setPixmap(_check_pixmap())

    def set_state(self, st: str) -> None:
        self.state = st
        self.dot.setVisible(st == "wait")
        self.spin.setVisible(st == "run")
        (self.spin.start if st == "run" else self.spin.stop)()
        self.done_mark.setVisible(st == "done")
        self.text.setObjectName("rowTitle" if st != "wait" else "desc")
        self.text.style().unpolish(self.text)
        self.text.style().polish(self.text)


def _circle_pixmap(color: str):
    pm, p = UK._canvas(20)
    p.setPen(QPen(QColor(color), 1.6))
    p.drawEllipse(QRectF(3, 3, 14, 14))
    p.end()
    return pm


def _check_pixmap():
    pm, p = UK._canvas(20)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(T["ok"]))
    p.drawEllipse(QRectF(1, 1, 18, 18))
    pen = QPen(QColor(T["bg"] if UK.is_dark() else "#FFFFFF"), 2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawPolyline([QPointF(6, 10.2), QPointF(8.8, 13), QPointF(14, 7.4)])
    p.end()
    return pm


class CleanSheet(UM.GlassSheet):
    """Вікно «Звільняю пам'ять…»: кроки з живими значеннями, потім — результат."""

    def __init__(self, page):
        super().__init__(page.window(), 470, closable=False)
        self.page = page
        b = self.body
        top = hbox(spacing=10)
        self.head_spin = UM.Spinner(20)
        top.addWidget(self.head_spin)
        self.title = label(tr("mem.sheet.title"), "h2")
        top.addWidget(self.title, 1)
        self.btn_x = button("✕", "ghost", self.close_sheet)
        self.btn_x.setEnabled(False)
        top.addWidget(self.btn_x)
        b.addLayout(top)
        self.sub = label(tr("mem.sheet.sub"), "desc", wrap=True)
        b.addWidget(self.sub)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setRange(0, 300)
        self.bar_anim = UM.Anim(self, lambda v: self.bar.setValue(int(v)), 600)
        b.addWidget(self.bar)
        self.steps = [StepRow(tr("mem.step.trim")), StepRow(tr("mem.step.cache")), StepRow(tr("mem.step.measure"))]
        self.steps_box = QWidget()
        sv = vbox(self.steps_box, (0, 6, 0, 0), 10)
        for s in self.steps:
            sv.addWidget(s)
        b.addWidget(self.steps_box)
        # результат
        self.res = QWidget()
        rv = vbox(self.res, (0, 4, 0, 0), 6)
        self.burst = UM.CheckBurst(70)
        rv.addWidget(self.burst, 0, Qt.AlignmentFlag.AlignHCenter)
        self.big = UM.CountLabel(lambda v: gb(v), ms=1100)
        self.big.setStyleSheet("font-size: 34px; font-weight: 700;")
        self.big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rv.addWidget(self.big)
        self.big_cap = label(tr("mem.freed").upper(), "micro")
        self.big_cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rv.addWidget(self.big_cap)
        rv.addSpacing(6)
        self.ba = BeforeAfter()
        rv.addWidget(self.ba)
        self.res_detail = label("", "desc", wrap=True)
        rv.addWidget(self.res_detail)
        self.res_note = label(tr("mem.res.note"), "muted", wrap=True)
        rv.addWidget(self.res_note)
        bh = hbox(spacing=8)
        bh.addStretch()
        self.btn_done = button(tr("btn.done"), "primary", self.close_sheet)
        bh.addWidget(self.btn_done)
        rv.addSpacing(4)
        rv.addLayout(bh)
        self.res.hide()
        b.addWidget(self.res)
        self.head_spin.start()
        self.steps[0].set_state("run")

    def progress(self, i: int, total: int, text: str) -> None:
        for j, s in enumerate(self.steps):
            s.set_state("done" if j < i else "run" if j == i else "wait")
        self.bar_anim.to(100.0 * (i + 0.6))

    def step_value(self, i: int, text: str) -> None:
        self.steps[i].val.setText(text)

    def show_result(self, res: dict) -> None:
        self.bar_anim.to(300.0, ms=300)
        for s in self.steps:
            s.set_state("done")
        self.head_spin.stop()
        self.head_spin.hide()
        self.btn_x.setEnabled(True)
        self.closable = True
        self.title.setText(tr("mem.sheet.done"))
        self.sub.hide()
        self.steps_box.hide()
        self.res.show()
        self._place()
        freed = res["freed"]
        self.big.set_value(freed)
        self.burst.play()
        self.ba.play(res["before"]["used"], res["after"]["used"])
        parts = []
        if res["trimmed"]:
            parts.append(tr("mem.res.trimmed", n=len(res["trimmed"]),
                            names=", ".join(n for n, _ in res["trimmed"][:3])))
        if res["cache"] >= 64:
            parts.append(tr("mem.res.cache", v=gb(res["cache"])))
        if freed < 128:
            parts.append(tr("mem.res.little"))
        self.res_detail.setText(" ".join(parts))
        self.btn_done.setFocus()


class MemoryPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.watcher = MT.Watcher()
        self.running = False
        self.sheet = None
        self.last = None  # останній результат звільнення
        outer = vbox(self)
        body = QWidget()
        v = vbox(body, (32, 0, 32, 24), 16)
        v.addWidget(page_header(tr("mem.title"), tr("mem.sub")))
        v.itemAt(0).widget().layout().setContentsMargins(0, 24, 0, 0)

        # головна картка: кільце, живий графік, кнопка
        hero = card("cardAccent")
        hh = hbox(hero, (26, 22, 26, 22), 26)
        left = vbox(spacing=10)
        self.gauge = UM.Gauge(184, tr("mem.in_use"))
        left.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignHCenter)
        self.level = UK.badge("…", "ok")
        left.addWidget(self.level, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addStretch()
        hh.addLayout(left)
        right = vbox(spacing=10)
        live = hbox(spacing=8)
        self.live_dot = QLabel()
        self.live_dot.setFixedSize(8, 8)
        live.addWidget(self.live_dot)
        live.addWidget(label(tr("mem.live").upper(), "micro"))
        live.addStretch()
        right.addLayout(live)
        stats = hbox(spacing=26)
        self.st_used = Stat(tr("mem.st.used"), "acc_h")
        self.st_avail = Stat(tr("mem.st.avail"))
        self.st_cache = Stat(tr("mem.st.cache"))
        self.st_total = Stat(tr("mem.st.total"))
        for s in (self.st_used, self.st_avail, self.st_cache, self.st_total):
            stats.addWidget(s)
        stats.addStretch()
        right.addLayout(stats)
        self.graph = UM.LiveGraph(60, 96, "acc")
        right.addWidget(self.graph, 1)
        act = hbox(spacing=14)
        self.btn = button(tr("mem.free_btn"), "primary", self.start_clean)
        self.btn.setMinimumWidth(200)
        act.addWidget(self.btn)
        self.btn_note = label(tr("mem.free_note"), "desc", wrap=True)
        act.addWidget(self.btn_note, 1)
        right.addLayout(act)
        hh.addLayout(right, 1)
        v.addWidget(hero)

        # підсумок останнього звільнення
        self.result = QFrame()
        self.result.setObjectName("bannerInfo")
        rh = hbox(self.result, (18, 12, 18, 12), 12)
        self.result_ico = QLabel()
        self.result_ico.setPixmap(_check_pixmap())
        rh.addWidget(self.result_ico, 0, Qt.AlignmentFlag.AlignTop)
        self.result_text = label("", "sub", wrap=True)
        rh.addWidget(self.result_text, 1)
        self.result.hide()
        v.addWidget(self.result)

        # хто займає пам'ять
        cons = card()
        cv = vbox(cons, (22, 18, 22, 16), 6)
        ch = hbox(spacing=10)
        chv = vbox(spacing=2)
        chv.addWidget(label(tr("mem.who"), "h2"))
        self.who_sub = label("", "desc")
        chv.addWidget(self.who_sub)
        ch.addLayout(chv, 1)
        legend = hbox(spacing=14)
        for st, key in (("active", "acc"), ("background", "pink"), ("idle", "mute")):
            d = UK.dot(T[key], 8)
            legend.addWidget(d)
            legend.addWidget(label(tr(f"mem.state.{st}"), "muted"))
        ch.addLayout(legend)
        cv.addLayout(ch)
        cv.addSpacing(4)
        self.rows = [ConsumerRow() for _ in range(8)]
        for r in self.rows:
            r.hide()
            cv.addWidget(r)
        self.who_note = label(tr("mem.who_note"), "muted", wrap=True)
        cv.addWidget(self.who_note)
        v.addWidget(cons)

        # автоматичне очищення кешу (те саме налаштування, що й на сторінці «Ігри»)
        auto = card()
        ah = hbox(auto, (22, 16, 22, 16), 14)
        self.auto_sw = Switch()
        self.auto_sw.set_quiet(bool(F.CFG["cleaner"].get("enabled")))
        self.auto_sw.clicked.connect(self._auto)
        ah.addWidget(self.auto_sw)
        av = vbox(spacing=2)
        av.addWidget(label(tr("mem.auto"), "rowTitle"))
        self.auto_d = label("", "desc", wrap=True)
        av.addWidget(self.auto_d)
        ah.addLayout(av, 1)
        ah.addWidget(button(tr("mem.auto_cfg"), "ghost", lambda: main.go("games")))
        v.addWidget(auto)
        v.addStretch()
        outer.addWidget(scroller(body), 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.who_timer = QTimer(self)
        self.who_timer.timeout.connect(self.refresh_who)
        self.blink = 0
        self._first_who = True
        self.retheme()
        self.tick()

    # ── тема ──
    def retheme(self):
        self.live_dot.setStyleSheet(f"background:{T['ok']};border-radius:4px;")
        self.result_ico.setPixmap(_check_pixmap())

    # ── показ сторінки ──
    def on_show(self):
        c = F.CFG["cleaner"] or {}
        self.auto_sw.set_quiet(bool(c.get("enabled")))
        self.auto_d.setText(tr("mem.auto_d", standby=gb(c.get("standby_mb", 1024)), free=gb(c.get("free_mb", 1024))))
        self.tick()
        self.refresh_who()

    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start(1000)
        self.who_timer.start(3000)

    def hideEvent(self, e):
        super().hideEvent(e)
        if not self.running:
            self.timer.stop()
            self.who_timer.stop()

    def tick(self):
        s = MT.snapshot()
        frac = s["used"] / s["total"] if s["total"] else 0.0
        self.gauge.set_value(frac, ms=800)
        if not self.graph.vals:  # перший замір — лінія одразу на всю ширину, далі вона «їде»
            self.graph.set_values([frac] * (self.graph.n + 1))
        self.graph.push(frac)
        self.st_used.val.set_value(s["used"])
        self.st_avail.val.set_value(s["avail"])
        self.st_cache.val.set_value(s["standby"])
        self.st_total.val.set_value(s["total"], animate=False)
        kind, key = (("bad", "mem.lvl.full") if frac >= 0.9 else ("warn", "mem.lvl.high") if frac >= 0.8
                     else ("ok", "mem.lvl.ok"))
        UK.style_badge(self.level, tr(key), kind)
        self.blink ^= 1
        self.live_dot.setVisible(bool(self.blink) or not UK.MOTION["on"])
        return s

    def refresh_who(self):
        if self.running:
            return
        try:
            groups = self.watcher.consumers(8)
        except Exception:
            groups = []
        top = groups[0]["mb"] if groups else 1.0
        total = sum(g["mb"] for g in groups)
        for r, g in zip(self.rows, groups + [None] * 8):
            if g:
                r.set_data(g, top, self._first_who)
                r.show()
            else:
                r.hide()
        self._first_who = False
        self.who_sub.setText(tr("mem.who_sub", n=len(groups), v=gb(total)))

    def _auto(self, on: bool):
        c = F.CFG["cleaner"]
        c["enabled"] = bool(on)
        F.CFG["cleaner"] = c
        games = self.main.pages.get("games") if hasattr(self.main, "pages") else None
        if games is not None and hasattr(games, "mc_sw"):
            games.mc_sw.set_quiet(bool(on))
        self.main.toast(tr("mc.on") if on else tr("mc.off"))

    # ── звільнення ──
    def start_clean(self):
        if self.running:
            return
        self.running = True
        E.CANCEL.clear()
        self.btn.setEnabled(False)
        self.timer.start(700)  # під час звільнення кільце оновлюється частіше
        self.sheet = CleanSheet(self)
        self.sheet.closed.connect(self._sheet_closed)
        self.sheet.open()
        w = Worker(lambda log, prog: MT.free_memory(self.watcher, log, prog))
        w.log.connect(LOG.write)
        w.progress.connect(self._progress)
        w.result.connect(self._done)
        self._worker = w
        self.main._workers.add(w) if hasattr(self.main, "_workers") else None
        w.start()

    def _progress(self, i, total, text):
        if self.sheet:
            self.sheet.progress(i, total, text)

    def _done(self, res):
        self._worker.wait()
        if hasattr(self.main, "_workers"):
            self.main._workers.discard(self._worker)
        self.running = False
        self.btn.setEnabled(True)
        self.timer.start(1000)
        if not isinstance(res, dict) or "freed" not in res:
            if self.sheet:
                self.sheet.close_sheet()
            self.main.toast(tr("mem.fail"), "bad")
            return
        self.last = res
        self.tick()
        if self.sheet:
            self.sheet.show_result(res)
        self._show_result(res, None)
        QTimer.singleShot(MT.REBOUND_AFTER * 1000, lambda r=res: self._rebound(r))

    def _sheet_closed(self):
        self.sheet = None
        self.refresh_who()

    def _show_result(self, res: dict, rb):
        when = time.strftime("%H:%M", time.localtime(res["ts"]))
        text = tr("mem.res.line", v=gb(res["freed"]), when=when, was=gb(res["before"]["used"]),
                  now=gb(res["after"]["used"]))
        if rb is not None:
            text += " " + tr("mem.res.rebound", kept=gb(rb["kept"]), back=gb(rb["back"]))
        else:
            text += " " + tr("mem.res.wait")
        self.result_text.setText(text)
        self.result.show()

    def _rebound(self, res: dict):
        if self.last is not res:
            return
        try:
            rb = MT.rebound(res)
        except Exception:
            return
        self._show_result(res, rb)
        self.main.toast(tr("mem.toast.rebound", kept=gb(rb["kept"]), freed=gb(res["freed"])))
