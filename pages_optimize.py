"""
OptimaX — сторінки «Аналіз» і «Оптимізація» (майстер, експертне меню, перегляд змін).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (QWidget, QFrame, QLabel, QLineEdit, QStackedWidget, QGridLayout, QProgressBar)

import engine as E
import features as F
import hardware as H
from i18n import tr
from ui_kit import (T, IMPACT_COLOR, label, button, card, vbox, hbox, badge, style_badge, dot, scroller, page_header,
                    bottom_bar, clear_layout, Switch, Ring, ProfileCard, OptionCard, Segmented, chip, Ask,
                    icon_pixmap, Worker)


# ───────────────────────── рядок оптимізації ─────────────────────────
class TweakRow(QFrame):
    """Назва, позначки, статус, пояснення, «що саме зміниться», перемикач."""
    toggled = pyqtSignal(bool)
    clicked = pyqtSignal(bool)

    def __init__(self, t: E.Tweak, title: str = None, details: bool = True, impact: bool = True):
        super().__init__()
        self.t = t
        self.key = f"{t.title} {t.desc}".lower()
        self.state = "ok"
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        outer = vbox(self, (14, 10, 14, 10), 4)
        top = hbox(spacing=8)
        if impact:
            d = dot(T[IMPACT_COLOR[t.impact]], 8)
            d.setToolTip(tr(f"impact.{t.impact}"))
            top.addWidget(d)
        top.addWidget(label(title or t.title, "rowTitle"))
        for text, kind in t.badges():
            top.addWidget(badge(text, kind))
        self.applied = badge(tr("chip.applied"), "ok")
        self.applied.hide()
        top.addWidget(self.applied)
        top.addStretch()
        self.btn_details = None
        if details and t.ops:
            self.btn_details = button(tr("opt.details"), "ghost", self._toggle_details)
            top.addWidget(self.btn_details)
        self.sw = Switch()
        self.sw.toggled.connect(self.toggled.emit)
        self.sw.clicked.connect(self.clicked.emit)
        top.addWidget(self.sw)
        outer.addLayout(top)
        self.desc = label(t.desc, "desc", wrap=True)
        outer.addWidget(self.desc)
        self.note = label("", "warnNote", wrap=True)
        self.note.setContentsMargins(0, 0, 0, 0)
        self.note.setStyleSheet("padding:0;")
        self.note.hide()
        outer.addWidget(self.note)
        self.details = None

    def _toggle_details(self):
        if self.details is None:
            self.details = label("\n".join(E.describe_ops(self.t)) or "—", "mono", wrap=True)
            self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.layout().addWidget(self.details)
            self.details.hide()
        show = self.details.isHidden()
        self.details.setVisible(show)
        self.btn_details.setText(tr("opt.hide_details") if show else tr("opt.details"))

    def set_compat(self, state: str, reason: str) -> None:
        self.state = state
        blocked = state in ("na", "block")
        self.sw.setEnabled(not blocked)
        if blocked and self.sw.isChecked():
            self.sw.setChecked(False)
        self.note.setVisible(bool(reason))
        color = T["bad"] if state == "block" else T["warn"] if state == "warn" else T["mute"]
        self.note.setStyleSheet(f"padding:0;color:{color};font-size:12px;")
        self.note.setText(("⛔ " if state == "block" else "⚠ " if state == "warn" else "") + reason)
        self.setCursor(Qt.CursorShape.ArrowCursor if blocked else Qt.CursorShape.PointingHandCursor)

    def refresh_applied(self) -> None:
        self.applied.setVisible(self.t.reversible and E.probe(self.t))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()) \
                and self.isEnabled() and self.sw.isEnabled():
            self.sw.click()
        super().mouseReleaseEvent(e)

    def isChecked(self) -> bool:
        return self.sw.isChecked()

    def setChecked(self, on: bool) -> None:
        if self.sw.isEnabled() or not on:
            self.sw.setChecked(on)


class Section(QFrame):
    changed = pyqtSignal()

    def __init__(self, gid: str, tweaks):
        super().__init__()
        self.gid = gid
        self.setObjectName("card")
        v = vbox(self, (8, 14, 8, 8), 2)
        h = hbox(margins=(14, 0, 8, 2), spacing=8)
        h.addWidget(label(tr(f"grp.{gid}"), "h2"))
        self.cnt = label("", "muted")
        h.addWidget(self.cnt)
        h.addStretch()
        self.btn = button(tr("opt.select_all"), "ghost", self._bulk)
        h.addWidget(self.btn)
        v.addLayout(h)
        sub = label(tr(f"grp.{gid}.d"), "desc", wrap=True)
        sub.setContentsMargins(14, 0, 14, 6)
        v.addWidget(sub)
        self.rows = [TweakRow(t) for t in tweaks]
        for r in self.rows:
            r.toggled.connect(self._row_changed)
            v.addWidget(r)
        if gid == "metro":
            v.addWidget(label(tr("opt.metro_note"), "warnNote", wrap=True))
        self.update_count()

    def _row_changed(self, _=None):
        self.update_count()
        self.changed.emit()

    def visible_rows(self):
        return [r for r in self.rows if not r.isHidden() and r.sw.isEnabled()]

    def update_count(self):
        n = sum(r.isChecked() for r in self.rows)
        self.cnt.setText(tr("opt.count", n=n, total=len(self.rows)))
        vis = self.visible_rows()
        self.btn.setText(tr("opt.clear_all") if vis and all(r.isChecked() for r in vis) else tr("opt.select_all"))

    def _bulk(self):
        vis = self.visible_rows()
        on = not all(r.isChecked() for r in vis)
        for r in vis:
            r.setChecked(on)

    def filter(self, q: str) -> int:
        shown = 0
        for r in self.rows:
            m = not q or q in r.key
            r.setHidden(not m)
            shown += m
        self.update_count()
        return shown


# ───────────────────────── експертне меню ─────────────────────────
class ExpertView(QWidget):
    changed = pyqtSignal()

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.profile = None
        self.rows: dict = {}
        self.sections: list = []
        self.group = None
        outer = vbox(self)
        body = QWidget()
        v = vbox(body, (32, 4, 32, 24), 14)
        pr = hbox(spacing=10)
        self.pcards = {}
        for pd in E.PROFILES:
            c = ProfileCard(pd)
            c.clicked.connect(lambda _=False, k=pd["key"]: self.apply_profile(k))
            pr.addWidget(c)
            self.pcards[pd["key"]] = c
        v.addLayout(pr)
        self.pdesc = label(tr("opt.profile_hint"), "note", wrap=True)
        v.addWidget(self.pdesc)
        legend = hbox(spacing=14)
        for imp in ("habits", "medium", "safe"):
            legend.addWidget(dot(T[IMPACT_COLOR[imp]], 8))
            legend.addWidget(label(tr(f"impact.{imp}"), "muted"))
        legend.addStretch()
        v.addLayout(legend)
        self.chips = {}
        groups = [None] + E.GROUP_IDS
        per = 6
        for part in (groups[i:i + per] for i in range(0, len(groups), per)):  # 17 категорій — три рядки
            row = hbox(spacing=6)
            for gid in part:
                c = chip(tr("opt.all") if gid is None else tr(f"grp.{gid}"))
                c.clicked.connect(lambda _=False, g=gid: self.set_group(g))
                row.addWidget(c)
                self.chips[gid] = c
            row.addStretch()
            v.addLayout(row)
        self.chips[None].setChecked(True)
        for gid in E.GROUP_IDS:
            items = [t for t in E.TWEAKS if t.group == gid]
            sec = Section(gid, items)
            sec.changed.connect(self._changed)
            for r in sec.rows:
                self.rows[r.t.id] = r
            self.sections.append(sec)
            v.addWidget(sec)
        self.empty = label(tr("opt.nothing_found"), "sub")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        v.addWidget(self.empty)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        bar, bh = bottom_bar()
        self.count = label("", "sub")
        bh.addWidget(self.count)
        bh.addStretch()
        self.btn_clear = button(tr("opt.clear_all"), None, self.clear)
        bh.addWidget(self.btn_clear)
        self.btn_review = button(tr("opt.review"), "primary", lambda: page.show_review(self.selected(), "expert"))
        bh.addWidget(self.btn_review)
        outer.addWidget(bar)
        self.query = ""
        self.refresh_applied()
        self._changed()

    def selected(self):
        return [tid for tid, r in self.rows.items() if r.isChecked()]

    def set_selected(self, ids) -> None:
        wanted = set(ids)
        for tid, r in self.rows.items():
            r.setChecked(tid in wanted)
        self._changed()

    def _changed(self):
        n = len(self.selected())
        self.count.setText(tr("opt.selected", n=n, total=len(self.rows)))
        self.btn_review.setEnabled(n > 0)
        self.btn_clear.setEnabled(n > 0)
        self.btn_review.setText(tr("opt.review_n", n=n) if n else tr("opt.review"))
        self.changed.emit()

    def clear(self):
        self.profile = None
        for r in self.rows.values():
            r.setChecked(False)
        self._mark_profiles()

    def _mark_profiles(self):
        for k, c in self.pcards.items():
            c.set_active(k == self.profile)
        if self.profile:
            pd = next(p for p in E.PROFILES if p["key"] == self.profile)
            self.pdesc.setText(tr(f"prof.{self.profile}.desc"))
            self.pdesc.setStyleSheet(f"border-left:3px solid {pd['color']};")
        else:
            self.pdesc.setText(tr("opt.profile_hint"))
            self.pdesc.setStyleSheet("")

    def apply_profile(self, key: str):
        if self.profile == key:
            self.clear()
            return
        self.profile = key
        for r in self.rows.values():
            r.setChecked(key in r.t.p and r.state not in ("na", "block"))
        self._mark_profiles()
        self._changed()

    def set_group(self, gid):
        self.group = gid
        for g, c in self.chips.items():
            c.setChecked(g == gid)
        self._apply_filter()

    def filter_text(self, text: str):
        self.query = text.strip().lower()
        self._apply_filter()

    def _apply_filter(self):
        shown = 0
        for sec in self.sections:
            n = sec.filter(self.query)
            vis = n > 0 and (self.group is None or self.group == sec.gid)
            sec.setHidden(not vis)
            shown += n if vis else 0
        self.empty.setVisible(shown == 0)

    def refresh_applied(self):
        for r in self.rows.values():
            r.refresh_applied()

    def set_hw(self, hw: dict):
        for r in self.rows.values():
            r.set_compat(*E.compat(r.t, hw))
        rec = hw.get("profile")
        for k, c in self.pcards.items():
            c.set_recommended(k == rec)
        for sec in self.sections:
            sec.update_count()
        self._changed()


# ───────────────────────── майстер ─────────────────────────
class WizardView(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.ans = F.wizard_defaults({})
        self.i = 0
        outer = vbox(self)
        body = QWidget()
        v = vbox(body, (32, 8, 32, 24), 14)
        top = hbox(spacing=10)
        self.step = label("", "muted")
        top.addWidget(self.step)
        top.addStretch()
        v.addLayout(top)
        self.prog = QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setFixedHeight(6)
        v.addWidget(self.prog)
        v.addSpacing(6)
        self.q = label("", "h1", wrap=True)
        v.addWidget(self.q)
        self.hint = label("", "sub", wrap=True)
        v.addWidget(self.hint)
        v.addSpacing(4)
        self.opts_box = vbox(spacing=10)
        v.addLayout(self.opts_box)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        bar, bh = bottom_bar()
        self.btn_back = button(tr("btn.back"), None, self.back)
        bh.addWidget(self.btn_back)
        bh.addStretch()
        self.btn_next = button(tr("btn.next"), "primary", self.next)
        bh.addWidget(self.btn_next)
        outer.addWidget(bar)
        self.cards = []

    def steps(self):
        res = []
        for q in F.WIZARD:
            cond = q.get("when")
            if cond and self.ans.get(cond[0]) not in cond[1]:
                continue
            res.append(q)
        return res

    def start(self, hw: dict):
        self.ans = F.wizard_defaults(hw or {})
        self.hw = hw or {}
        self.i = 0
        self.render()

    def render(self):
        steps = self.steps()
        self.i = max(0, min(self.i, len(steps) - 1))
        q = steps[self.i]
        qid = q["id"]
        self.step.setText(tr("wz.step", i=self.i + 1, n=len(steps)))
        self.prog.setRange(0, len(steps))
        self.prog.setValue(self.i + 1)
        self.q.setText(tr(f"wz.{qid}.q"))
        hint = tr(f"wz.{qid}.h")
        if qid == "device" and getattr(self, "hw", None):
            hint = tr("wz.device.detected", dev=tr(f"wz.device.{self.hw.get('device', 'gaming')}")) + " " + hint
        self.hint.setText(hint)
        clear_layout(self.opts_box)
        self.cards = []
        multi = q.get("multi", False)
        cur = self.ans.get(qid)
        for opt in q["opts"]:
            c = OptionCard(tr(f"wz.{qid}.{opt}"), tr(f"wz.{qid}.{opt}.d"), multi)
            c.setChecked(opt in (cur or []) if multi else opt == cur)
            c.clicked.connect(lambda _=False, o=opt, m=multi, q_=qid: self.pick(q_, o, m))
            self.opts_box.addWidget(c)
            self.cards.append((opt, c))
        self.btn_back.setEnabled(self.i > 0)
        self.btn_next.setText(tr("wz.make_plan") if self.i == len(steps) - 1 else tr("btn.next"))

    def pick(self, qid: str, opt: str, multi: bool):
        if multi:
            cur = set(self.ans.get(qid) or [])
            cur.symmetric_difference_update({opt})
            self.ans[qid] = sorted(cur)
        else:
            self.ans[qid] = opt
        for o, c in self.cards:
            c.setChecked(o in self.ans[qid] if multi else o == self.ans[qid])

    def back(self):
        self.i -= 1
        self.render()

    def next(self):
        if self.i >= len(self.steps()) - 1:
            self.page.show_review(F.build_plan(self.ans, getattr(self, "hw", {}) or {}), "wizard")
            return
        self.i += 1
        self.render()


# ───────────────────────── перегляд змін ─────────────────────────
class ReviewRow(QFrame):
    def __init__(self, t: E.Tweak, hw: dict):
        super().__init__()
        self.t = t
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        h = hbox(self, (14, 10, 14, 10), 14)
        v = vbox(spacing=3)
        top = hbox(spacing=8)
        top.addWidget(label(t.title, "rowTitle"))
        for text, kind in t.badges():
            top.addWidget(badge(text, kind))
        top.addStretch()
        v.addLayout(top)
        v.addWidget(label(t.desc, "desc", wrap=True))
        state, reason = E.compat(t, hw)
        if reason:
            n = label(("⚠ " if state == "warn" else "") + reason, "desc", wrap=True)
            n.setStyleSheet(f"color:{T['warn']};")
            v.addWidget(n)
        h.addLayout(v, 1)
        self.sw = Switch()
        self.sw.set_quiet(True)
        h.addWidget(self.sw, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.sw.click()
        super().mouseReleaseEvent(e)


class ReviewView(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.source = "expert"
        self.rows = []
        outer = vbox(self)
        body = QWidget()
        v = vbox(body, (32, 4, 32, 24), 14)
        v.addWidget(label(tr("rv.title"), "h2"))
        v.addWidget(label(tr("rv.sub"), "sub", wrap=True))
        self.legend = hbox(spacing=14)
        v.addLayout(self.legend)
        self.sections = {}
        for imp in ("habits", "medium", "safe"):
            c = card()
            cv = vbox(c, (8, 14, 8, 8), 2)
            head = hbox(margins=(14, 0, 14, 6), spacing=10)
            head.addWidget(dot(T[IMPACT_COLOR[imp]], 10))
            head.addWidget(label(tr(f"rv.{imp}"), "h2"))
            head.addStretch()
            cv.addLayout(head)
            sub = label(tr(f"rv.{imp}.d"), "desc", wrap=True)
            sub.setContentsMargins(14, 0, 14, 6)
            cv.addWidget(sub)
            box = vbox(spacing=2)
            cv.addLayout(box)
            v.addWidget(c)
            self.sections[imp] = (c, box)
        opts = card()
        ov = vbox(opts, (22, 16, 22, 16), 10)
        ov.addWidget(label(tr("rv.options"), "h2"))
        r1 = hbox(spacing=12)
        self.sw_rp = Switch()
        self.sw_rp.set_quiet(True)
        r1.addWidget(self.sw_rp)
        r1.addWidget(label(tr("rv.restore_point"), "rowTitle"), 1)
        ov.addLayout(r1)
        r2 = hbox(spacing=12)
        self.sw_sfc = Switch()
        r2.addWidget(self.sw_sfc)
        r2.addWidget(label(tr("rv.sfc"), "rowTitle"), 1)
        ov.addLayout(r2)
        r3 = hbox(spacing=12)
        self.sw_trial = Switch()
        r3.addWidget(self.sw_trial)
        tv = vbox(spacing=1)
        tv.addWidget(label(tr("rv.trial"), "rowTitle"))
        tv.addWidget(label(tr("rv.trial_d"), "desc", wrap=True))
        r3.addLayout(tv, 1)
        ov.addLayout(r3)
        r4 = hbox(spacing=12)
        self.sw_smart = Switch()
        r4.addWidget(self.sw_smart)
        sv = vbox(spacing=1)
        sv.addWidget(label(tr("rv.smart"), "rowTitle"))
        sv.addWidget(label(tr("rv.smart_d"), "desc", wrap=True))
        r4.addLayout(sv, 1)
        ov.addLayout(r4)
        self.sw_smart.toggled.connect(lambda on: on and self.sw_trial.set_quiet(False))
        self.sw_trial.toggled.connect(lambda on: on and self.sw_smart.set_quiet(False))
        ov.addWidget(label(tr("rv.backup_note"), "desc", wrap=True))
        v.addWidget(opts)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        bar, bh = bottom_bar()
        bh.addWidget(button(tr("btn.back"), None, lambda: page.back_from_review()))
        bh.addStretch()
        self.count = label("", "sub")
        bh.addWidget(self.count)
        self.btn_apply = button(tr("rv.apply"), "primary", self.apply)
        bh.addWidget(self.btn_apply)
        outer.addWidget(bar)

    def set_plan(self, ids, source: str, hw: dict):
        self.source = source
        self.rows = []
        for imp, (c, box) in self.sections.items():
            clear_layout(box)
        counts = {"habits": 0, "medium": 0, "safe": 0}
        for tid in ids:
            t = E.BY_ID.get(tid)
            if not t:
                continue
            r = ReviewRow(t, hw)
            r.sw.toggled.connect(lambda _=False: self._count())
            self.sections[t.impact][1].addWidget(r)
            self.rows.append(r)
            counts[t.impact] += 1
        for imp, (c, _box) in self.sections.items():
            c.setVisible(counts[imp] > 0)
        clear_layout(self.legend)
        for imp in ("habits", "medium", "safe"):
            self.legend.addWidget(dot(T[IMPACT_COLOR[imp]], 8))
            self.legend.addWidget(label(f"{tr('rv.' + imp)}: {counts[imp]}", "muted"))
        self.legend.addStretch()
        self._count()

    def selected(self):
        return [r.t.id for r in self.rows if r.sw.isChecked()]

    def _count(self):
        n = len(self.selected())
        self.count.setText(tr("rv.count", n=n))
        self.btn_apply.setEnabled(n > 0)
        self.btn_apply.setText(tr("rv.apply_n", n=n) if n else tr("rv.apply"))

    def apply(self):
        self.page.main.start_apply(self.selected(), self.sw_rp.isChecked(), self.sw_sfc.isChecked(),
                                   trial=self.sw_trial.isChecked(), smart=self.sw_smart.isChecked())


class OptimizePage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        self.seg = Segmented([tr("opt.mode_wizard"), tr("opt.mode_expert")])
        self.seg.changed.connect(self.set_mode)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("opt.search"))
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        right = QWidget()
        rh = hbox(right, spacing=10)
        rh.addWidget(self.search)
        rh.addWidget(self.seg)
        outer.addWidget(page_header(tr("nav.optimize"), tr("opt.sub"), right))
        self.stack = QStackedWidget()
        self.wizard = WizardView(self)
        self.expert = ExpertView(self)
        self.review = ReviewView(self)
        for w in (self.wizard, self.expert, self.review):
            self.stack.addWidget(w)
        outer.addWidget(self.stack, 1)
        self.search.textChanged.connect(self._search)
        self.mode = 0
        self.set_mode(0)

    def _search(self, text: str):
        if text and self.mode != 1:
            self.seg.select(1)
            self.set_mode(1)
        self.expert.filter_text(text)

    def set_mode(self, i: int):
        self.mode = i
        self.seg.select(i)
        self.stack.setCurrentWidget(self.wizard if i == 0 else self.expert)
        self.search.setVisible(i == 1)
        if i == 0:
            self.wizard.start(self.main.hw)

    def show_review(self, ids, source: str):
        if not ids:
            Ask.info(self, tr("rv.empty_t"), tr("rv.empty_d"))
            return
        self.review.set_plan(ids, source, self.main.hw or {})
        self.stack.setCurrentWidget(self.review)
        self.search.hide()

    def back_from_review(self):
        self.set_mode(0 if self.review.source == "wizard" else 1)
        if self.review.source == "wizard":
            self.wizard.i = len(self.wizard.steps()) - 1
            self.wizard.render()

    def open_profile(self, key: str):
        """Відкрити експертне меню з відміченим профілем."""
        self.set_mode(1)
        if self.expert.profile != key:
            self.expert.apply_profile(key)

    def set_hw(self, hw: dict):
        self.expert.set_hw(hw)
        if self.mode == 0 and self.stack.currentWidget() is self.wizard:
            self.wizard.start(hw)

    def refresh(self):
        self.expert.refresh_applied()


# ───────────────────────── сторінка «Аналіз» ─────────────────────────
class Tile(QFrame):
    def __init__(self, caption: str, ring_color: str = None):
        super().__init__()
        self.setObjectName("card")
        h = hbox(self, (16, 14, 16, 14), 12)
        self.ring = Ring(ring_color, 62, 6, 15) if ring_color else None
        if self.ring:
            h.addWidget(self.ring)
        v = vbox(spacing=3)
        v.addStretch()
        self.big = label("—", "big") if not ring_color else None
        if self.big:
            v.addWidget(self.big)
        v.addWidget(label(caption, "h3", wrap=True))
        self.sub = label("", "desc", wrap=True)
        v.addWidget(self.sub)
        v.addStretch()
        h.addLayout(v, 1)


class StatMini(QFrame):
    def __init__(self, caption: str, color: str):
        super().__init__()
        self.setObjectName("card")
        h = hbox(self, (14, 12, 14, 12), 12)
        self.ring = Ring(color, 52, 5, 12)
        h.addWidget(self.ring)
        v = vbox(spacing=2)
        v.addStretch()
        v.addWidget(label(caption, "h3"))
        self.detail = label("", "desc")
        v.addWidget(self.detail)
        v.addStretch()
        h.addLayout(v, 1)


METRIC_ROWS = [("boot_ms", "ba.boot", True), ("processes", "ba.processes", True), ("services", "ba.services", True),
               ("ram_used_gb", "ba.ram", True), ("startup", "ba.startup", True), ("disk_free_gb", "ba.disk", False)]


def fmt_metric(key: str, v) -> str:
    if v is None:
        return "—"
    if key == "boot_ms":
        return tr("u.sec", v=f"{v / 1000:.1f}")
    if key in ("ram_used_gb", "disk_free_gb"):
        return tr("u.gb", v=f"{v:.1f}")
    return str(int(v))


class HomePage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = vbox(self)
        body = QWidget()
        v = vbox(body, (32, 26, 32, 24), 16)

        # сповіщення: пробний режим і сторож налаштувань
        self.banner = QFrame()
        self.banner.setObjectName("bannerWarn")
        bh0 = hbox(self.banner, (18, 12, 18, 12), 12)
        bv0 = vbox(spacing=3)
        self.banner_t = label("", "h3")
        self.banner_d = label("", "desc", wrap=True)
        bv0.addWidget(self.banner_t)
        bv0.addWidget(self.banner_d)
        bh0.addLayout(bv0, 1)
        self.banner_b1 = button("", "primary")
        self.banner_b2 = button("", None)
        bh0.addWidget(self.banner_b1, 0, Qt.AlignmentFlag.AlignVCenter)
        bh0.addWidget(self.banner_b2, 0, Qt.AlignmentFlag.AlignVCenter)
        self.banner.hide()
        self._b1 = self._b2 = None
        self.banner_b1.clicked.connect(lambda _=False: self._b1 and self._b1())
        self.banner_b2.clicked.connect(lambda _=False: self._b2 and self._b2())
        v.addWidget(self.banner)

        # аналіз
        an = card("cardAccent")
        av = vbox(an, (24, 20, 24, 20), 14)
        head = hbox(spacing=12)
        hv = vbox(spacing=3)
        hv.addWidget(label(tr("home.analysis"), "display"))
        self.an_state = label(tr("home.analyzing"), "sub")
        hv.addWidget(self.an_state)
        head.addLayout(hv, 1)
        self.btn_an = button(tr("home.reanalyze"), None, main.run_analysis)
        head.addWidget(self.btn_an, 0, Qt.AlignmentFlag.AlignTop)
        av.addLayout(head)
        tiles = hbox(spacing=12)
        self.t_opt = Tile(tr("home.opt_level"), T["acc"])
        self.t_priv = Tile(tr("home.privacy_level"), T["ok"])
        self.t_pot = Tile(tr("home.potential"))
        self.t_neck = Tile(tr("home.bottleneck"))
        for t in (self.t_opt, self.t_priv, self.t_pot, self.t_neck):
            tiles.addWidget(t)
        av.addLayout(tiles)
        v.addWidget(an)

        # вибір шляху
        v.addWidget(label(tr("home.choose_path"), "h2"))
        paths = hbox(spacing=14)
        for key, ico, cb, obj in (("wizard", "wand", main.open_wizard, "primary"),
                                  ("expert", "sliders", main.open_expert, None)):
            c = card()
            cv = vbox(c, (22, 18, 22, 18), 8)
            top = hbox(spacing=12)
            ic = QLabel()
            ic.setPixmap(icon_pixmap(ico, T["acc_h"], 26))
            top.addWidget(ic)
            top.addWidget(label(tr(f"home.{key}.t"), "h2"), 1)
            cv.addLayout(top)
            cv.addWidget(label(tr(f"home.{key}.d"), "sub", wrap=True))
            cv.addStretch()
            bh = hbox()
            bh.addWidget(button(tr(f"home.{key}.btn"), obj, cb))
            bh.addStretch()
            cv.addLayout(bh)
            paths.addWidget(c, 1)
        v.addLayout(paths)
        self.rec_line = hbox(spacing=10)
        self.rec_label = label("", "sub")
        self.rec_line.addWidget(self.rec_label)
        self.btn_rec = button(tr("home.rec_open"), "ghost",
                              lambda: main.open_profile((self.main.hw or {}).get("profile", "M")))
        self.rec_line.addWidget(self.btn_rec)
        self.rec_line.addStretch()
        v.addLayout(self.rec_line)

        # пристрій і перевірка збірки
        two = hbox(spacing=14)
        dev = card()
        dv = vbox(dev, (22, 18, 22, 18), 8)
        dh = hbox(spacing=10)
        dh.addWidget(label(tr("home.device"), "h2"))
        self.dev_badge = badge("…", "acc")
        dh.addWidget(self.dev_badge)
        dh.addStretch()
        dv.addLayout(dh)
        self.dev_grid = QGridLayout()
        self.dev_grid.setHorizontalSpacing(16)
        self.dev_grid.setVerticalSpacing(8)
        dv.addLayout(self.dev_grid)
        dv.addStretch()
        two.addWidget(dev, 3)
        chk = card()
        cv = vbox(chk, (22, 18, 22, 18), 8)
        ch = hbox(spacing=10)
        ch.addWidget(label(tr("home.build_check"), "h2"))
        self.chk_badge = badge("…", "muted")
        ch.addWidget(self.chk_badge)
        ch.addStretch()
        cv.addLayout(ch)
        self.chk_box = vbox(spacing=6)
        cv.addLayout(self.chk_box)
        cv.addStretch()
        cv.addWidget(button(tr("home.all_checks"), "ghost", lambda: main.go("hardware")), 0,
                     Qt.AlignmentFlag.AlignLeft)
        two.addWidget(chk, 2)
        v.addLayout(two)

        # живі показники
        stats = hbox(spacing=12)
        self.s_cpu = StatMini(tr("home.cpu"), T["acc"])
        self.s_ram = StatMini(tr("home.ram"), "#C07AF0")
        self.s_disk = StatMini(tr("home.disk"), T["warn"])
        self.s_gpu = StatMini(tr("home.gpu_temp"), T["bad"])
        for s in (self.s_cpu, self.s_ram, self.s_disk, self.s_gpu):
            stats.addWidget(s)
        v.addLayout(stats)

        # до і після
        ba = card()
        bv = vbox(ba, (22, 18, 22, 18), 10)
        bh = hbox(spacing=10)
        bh.addWidget(label(tr("ba.title"), "h2"))
        bh.addStretch()
        bh.addWidget(button(tr("ba.refresh"), "ghost", self.refresh_metrics))
        bh.addWidget(button(tr("ba.new_snapshot"), "ghost", self.new_snapshot))
        bh.addWidget(button(tr("sc.share"), "ghost", main.share_result))
        bv.addLayout(bh)
        self.ba_grid = QGridLayout()
        self.ba_grid.setHorizontalSpacing(18)
        self.ba_grid.setVerticalSpacing(8)
        bv.addLayout(self.ba_grid)
        self.ba_note = label(tr("ba.note"), "desc", wrap=True)
        bv.addWidget(self.ba_note)
        v.addWidget(ba)
        v.addStretch()
        outer.addWidget(scroller(body), 1)

        bar, bbh = bottom_bar()
        self.btn_rp = button(tr("home.restore_point"), "good", lambda: main.create_restore_point(self.btn_rp))
        bbh.addWidget(self.btn_rp)
        bbh.addStretch()
        self.btn_boost = button(tr("g.btn_on"), None, main.toggle_booster)
        bbh.addWidget(self.btn_boost)
        self.btn_start = button(tr("home.start"), "primary", main.open_wizard)
        bbh.addWidget(self.btn_start)
        outer.addWidget(bar)

        self.metrics = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1500)
        self.tick()
        self.render_metrics()

    def set_banner(self, kind=None, title="", text="", b1=None, b2=None):
        """kind: None — сховати; trial | guard. b1/b2: (підпис, дія)."""
        self.banner.setVisible(kind is not None)
        if kind is None:
            return
        self.banner.setObjectName("bannerInfo" if kind in ("trial", "update") else
                                  "banner" if kind == "crash" else "bannerWarn")
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)
        self.banner_t.setText(title)
        self.banner_d.setText(text)
        for btn, spec, attr in ((self.banner_b1, b1, "_b1"), (self.banner_b2, b2, "_b2")):
            btn.setVisible(bool(spec))
            if spec:
                btn.setText(spec[0])
                setattr(self, attr, spec[1])

    # ── живі показники ──
    def tick(self):
        s = H.sys_stats()
        self.s_cpu.ring.set_value(s["cpu"])
        self.s_cpu.detail.setText(tr("home.cpu_d"))
        self.s_ram.ring.set_value(s["ram"])
        self.s_ram.detail.setText(tr("home.ram_d", used=f"{s['ram'] * s['ram_total']:.1f}", total=f"{s['ram_total']:.0f}"))
        if s["disk_total"]:
            self.s_disk.ring.set_value(1 - s["disk_free"] / s["disk_total"])
            self.s_disk.detail.setText(tr("home.disk_d", free=f"{s['disk_free']:.0f}"))
        self.update_booster()

    def set_gpu_temp(self, t):
        if t is None:
            self.s_gpu.ring.text = "—"
            self.s_gpu.ring.set_value(0)
            self.s_gpu.detail.setText(tr("home.gpu_na"))
        else:
            self.s_gpu.ring.text = f"{t}°"
            self.s_gpu.ring.set_value(t / 100, T["ok"] if t < 70 else T["warn"] if t < 83 else T["bad"])
            self.s_gpu.detail.setText(tr("home.gpu_d"))

    def update_booster(self):
        on = F.BOOSTER.active
        self.btn_boost.setText(tr("g.btn_off") if on else tr("g.btn_on"))

    # ── аналіз ──
    def set_analyzing(self):
        self.an_state.setText(tr("home.analyzing"))
        self.btn_an.setEnabled(False)

    def set_analysis(self, hw: dict, an: dict, checks: list):
        self.btn_an.setEnabled(True)
        self.an_state.setText(tr("home.analyzed"))
        self.t_opt.ring.set_value(an["opt"] / 100)
        self.t_opt.sub.setText(tr("home.opt_sub", n=an["left"]))
        self.t_priv.ring.set_value(an["privacy"] / 100)
        self.t_priv.sub.setText(tr("home.privacy_sub"))
        col = {"high": T["warn"], "mid": T["acc_h"], "low": T["ok"]}[an["potential"]]
        self.t_pot.big.setText(tr(f"home.pot.{an['potential']}"))
        self.t_pot.big.setStyleSheet(f"color:{col};")
        self.t_pot.sub.setText(tr("home.pot_sub", n=an["left"]))
        self.t_neck.big.setText(tr(f"neck.{an['neck']}"))
        self.t_neck.big.setStyleSheet(f"color:{T['ok'] if an['neck'] == 'none' else T['warn']};")
        self.t_neck.sub.setText(tr(f"neck.{an['neck']}.d"))
        prof = hw.get("profile", "M")
        self.rec_label.setText(tr("home.rec", prof=E.profile_name(prof)))
        style_badge(self.dev_badge, tr(f"dev.{hw.get('device', 'gaming')}"), "acc")
        clear_layout(self.dev_grid)
        gpus = ", ".join(n for n, _, _ in hw.get("gpus", []))
        cpu = hw.get("cpu", "")
        if (hw.get("sockets") or 1) > 1:
            cpu = f"{hw['sockets']} × {cpu}"
        rows = [(tr("hw.cpu"), cpu), (tr("hw.gpu"), gpus), (tr("hw.ram"), H.ram_line(hw)),
                (tr("hw.disk"), H.disk_line(hw)),
                (tr("hw.os"), f"{hw.get('os', '')}" + (f" ({hw['build']})" if hw.get("build") else ""))]
        for i, (k, val) in enumerate(rows):
            self.dev_grid.addWidget(label(k, "desc"), i, 0, Qt.AlignmentFlag.AlignTop)
            lv = label(val, "rowTitle", wrap=True)
            self.dev_grid.addWidget(lv, i, 1)
        self.dev_grid.setColumnStretch(1, 1)
        clear_layout(self.chk_box)
        warns = [c for c in checks if c["level"] == "warn"]
        infos = [c for c in checks if c["level"] == "info"]
        if warns:
            style_badge(self.chk_badge, tr("home.warns", n=len(warns)), "warn")
        elif infos:
            style_badge(self.chk_badge, tr("home.tips", n=len(infos)), "acc")
        else:
            style_badge(self.chk_badge, tr("home.all_ok"), "ok")
        shown = (warns + infos)[:4] or [c for c in checks if c["level"] == "ok"][:4]
        for c in shown:
            r = hbox(spacing=10)
            r.addWidget(dot(T[{"warn": "warn", "info": "acc", "ok": "ok"}[c["level"]]], 8), 0,
                        Qt.AlignmentFlag.AlignVCenter)
            r.addWidget(label(c["title"], "rowTitle", wrap=True), 1)
            self.chk_box.addLayout(r)

    # ── до/після ──
    def refresh_metrics(self):
        self.main.collect_metrics()

    def new_snapshot(self):
        if self.metrics:
            F.CFG["snapshot"] = self.metrics
            self.render_metrics()
            self.main.toast(tr("ba.saved"))
        else:
            self.main.collect_metrics(snapshot=True)

    def set_metrics(self, m: dict):
        self.metrics = m
        self.render_metrics()

    def render_metrics(self):
        clear_layout(self.ba_grid)
        before = F.CFG["snapshot"] or {}
        now = self.metrics or {}
        for j, h in enumerate(("", tr("ba.before"), tr("ba.now"), tr("ba.change"))):
            self.ba_grid.addWidget(label(h, "muted"), 0, j)
        for i, (key, cap, lower_better) in enumerate(METRIC_ROWS, 1):
            b, n = before.get(key), now.get(key)
            self.ba_grid.addWidget(label(tr(cap), "desc"), i, 0)
            self.ba_grid.addWidget(label(fmt_metric(key, b), "rowTitle"), i, 1)
            self.ba_grid.addWidget(label(fmt_metric(key, n), "rowTitle"), i, 2)
            ch = "—"
            col = T["mute"]
            if b not in (None, 0) and n is not None:
                diff = (n - b) / b * 100
                if abs(diff) >= 1:
                    good = diff < 0 if lower_better else diff > 0
                    ch = f"{diff:+.0f}%"
                    col = T["ok"] if good else T["bad"]
            lb = label(ch, "rowTitle")
            lb.setStyleSheet(f"color:{col};")
            self.ba_grid.addWidget(lb, i, 3)
        self.ba_grid.setColumnStretch(0, 1)
        when = before.get("ts")
        if when:
            from datetime import datetime
            self.ba_note.setText(tr("ba.note_when", when=datetime.fromtimestamp(when).strftime("%d.%m.%Y %H:%M")))
