"""
OptimaX — вікно «Профіль гри» (Game Booster 2.0) для картки гри в «Бібліотеці» (логіка — gameprof.py).
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame

import gameprof as GP
from i18n import tr
from ui_kit import (T, label, button, vbox, hbox, badge, style_badge, Switch, Segmented, Ask, dark_titlebar,
                    fade_in_window)


def _f(v) -> str:
    return f"{v:.0f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else "—"


def _when(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d.%m %H:%M")
    except (TypeError, ValueError, OverflowError, OSError):
        return "—"


def fps_lines(info: dict) -> list:
    """Рядки панелі FPS: [(текст, стиль, колір або None)] — лише з наявних замірів."""
    out = []
    b, a, cmp_ = info.get("before") or {}, info.get("after") or {}, info.get("cmp") or {}
    for what, r in (("gprof.fps_before", b), ("gprof.fps_after", a)):
        if r:
            out.append((tr("gprof.fps_side", what=tr(what), avg=_f(r.get("avg")), low=_f(r.get("low1")),
                           when=_when(r.get("ts"))), "rowTitle", None))
    if cmp_.get("verdict") in ("better", "same", "worse"):
        col = {"better": T["ok"], "same": T["sub"], "worse": T["bad"]}[cmp_["verdict"]]
        out.append((tr(f"gprof.fps_v.{cmp_['verdict']}", d=f"{cmp_.get('d_avg') or 0:+.1f}"), "desc", col))
    rows = info.get("rows") or []
    if rows:
        out.append((tr("gprof.fps_bg"), "muted", None))
        for r in reversed(rows):
            text = tr("gprof.fps_row", when=_when(r["ts"]), avg=_f(r.get("avg")), low=_f(r.get("low1")))
            if r.get("prof"):
                text += "  · " + tr("gprof.fps_prof")
            out.append((text, "desc", T["acc"] if r.get("prof") else None))
    return out


class ProfileDialog(QDialog):
    """Профіль однієї гри. Після exec(): action — "save" / "remove" / None, profile() — вибрані значення."""
    WIDTH = 640

    def __init__(self, parent, g: dict, hw: dict = None, on_fps=None):
        super().__init__(parent)
        self.g = g
        self.action = None
        self.setWindowTitle(tr("gprof.title", game=g.get("name", "")))
        self.setModal(True)
        self.setFixedWidth(self.WIDTH)
        p = GP.profile(g)
        v = vbox(self, (26, 22, 26, 20), 10)
        top = hbox(spacing=8)
        top.addWidget(label(tr("gprof.title", game=g.get("name", "")), "h2", wrap=True), 1)
        self.state = badge("", "muted")
        top.addWidget(self.state, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(top)
        v.addWidget(label(tr("gprof.sub"), "sub", wrap=True))

        r, rv, _c = self._row(tr("gprof.enabled"), tr("gprof.enabled_d"))
        self.sw_on = Switch()
        self.sw_on.set_quiet(p["enabled"])
        r.insertWidget(0, self.sw_on, 0, Qt.AlignmentFlag.AlignTop)
        v.addWidget(rv)

        self.segs = {}
        gpu_d = tr("gprof.gpu_d")
        try:
            import mining as MG
            if hw and MG.active(hw):
                gpu_d += " " + tr("gprof.gpu_d_mining", gpu=MG.model(hw))
        except Exception:  # noqa: BLE001 — підказка про майнінгову карту не обов'язкова
            pass
        for key, values, title, desc in (("power", GP.POWER, "gprof.power_t", tr("gprof.power_d")),
                                         ("gpu", GP.GPU, "gprof.gpu_t", gpu_d),
                                         ("prio", GP.PRIO, "gprof.prio_t", tr("gprof.prio_d"))):
            _r, box, col = self._row(tr(title), desc)
            seg = Segmented([tr(f"gprof.{key}.{x}") for x in values])
            seg.select(values.index(p[key]))
            seg.idx = values.index(p[key])
            seg.changed.connect(lambda i, s=seg: setattr(s, "idx", i))
            col.addWidget(seg, 0, Qt.AlignmentFlag.AlignLeft)
            self.segs[key] = (seg, values)
            v.addWidget(box)

        r, rv, _c = self._row(tr("gprof.boost_t"), tr("gprof.boost_d"))
        self.sw_boost = Switch()
        self.sw_boost.set_quiet(p["boost"])
        r.insertWidget(0, self.sw_boost, 0, Qt.AlignmentFlag.AlignTop)
        v.addWidget(rv)

        # FPS цієї гри — лише справжні заміри
        fh = hbox(spacing=8)
        fh.addWidget(label(tr("gprof.fps_t"), "h3"), 1)
        if on_fps:
            fh.addWidget(button(tr("gprof.fps_open"), "ghost", lambda: (self.reject(), on_fps())))
        v.addLayout(fh)
        lines = fps_lines(GP.fps_info(g))
        self.fps_labels = []
        for text, obj, col in lines or [(tr("gprof.fps_none"), "desc", None)]:
            lb = label(text, obj, wrap=True)
            if col:
                lb.setStyleSheet(f"color:{col};")
            v.addWidget(lb)
            self.fps_labels.append(lb)

        v.addSpacing(8)
        h = hbox(spacing=8)
        self.btn_remove = button(tr("gprof.remove"), "ghost", self._remove)
        self.btn_remove.setVisible(GP.is_set(p) or (g.get("key") in GP.profiles()))
        h.addWidget(self.btn_remove)
        h.addStretch()
        h.addWidget(button(tr("btn.cancel"), None, self.reject))
        ok = button(tr("gprof.save"), "primary", self._save)
        ok.setDefault(True)
        h.addWidget(ok)
        v.addLayout(h)
        self.sync_state()

    def _row(self, title: str, desc: str):
        f = QFrame()
        f.setObjectName("row")
        h = hbox(f, (14, 10, 14, 10), 12)
        col = vbox(spacing=4)
        head = hbox(spacing=10)
        head.addWidget(label(title, "rowTitle"), 1)
        col.addLayout(head)
        col.addWidget(label(desc, "desc", wrap=True))
        h.addLayout(col, 1)
        return h, f, col

    def sync_state(self):
        key = self.g.get("key")
        since = GP.MANAGER.since(key)
        if since:
            style_badge(self.state, tr("gprof.badge_on"), "ok")
            self.state.setToolTip(tr("gprof.active_since", when=_when(since)))
        elif GP.has_profile(self.g):
            style_badge(self.state, tr("gprof.badge_set"), "acc")
        else:
            self.state.hide()

    def profile(self) -> dict:
        p = {k: values[seg.idx] for k, (seg, values) in self.segs.items()}
        p.update(enabled=self.sw_on.isChecked(), boost=self.sw_boost.isChecked())
        return GP.clean(p)

    def _save(self):
        self.action = "save"
        self.accept()

    def _remove(self):
        if not Ask.ask(self, tr("gprof.remove"), tr("gprof.remove_q", game=self.g.get("name", "")),
                       tr("gprof.remove"), "danger"):
            return
        self.action = "remove"
        self.accept()

    def showEvent(self, e):
        dark_titlebar(self)
        fade_in_window(self)
        super().showEvent(e)
