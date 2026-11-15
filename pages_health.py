"""
OptimaX — картка «Здоров'я ПК» на сторінці «Діагностика» і вікно плану «Виправити все безпечне».
Логіка — healthcheck.py.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame, QWidget

import engine as E
import features as F
import healthcheck as HC
import rescue as RS
from i18n import tr
from ui_kit import (T, label, button, vbox, hbox, dot, clear_layout, section_card, Ask, Check, FlowLayout, Ring,
                    RunDialog, dark_titlebar, fade_in_window)

DOT = {HC.BAD: "bad", HC.WARN: "warn", HC.OK: "ok", HC.INFO: "acc", HC.UNKNOWN: "mute"}
OPEN_LABEL = HC.OPEN_LABEL


def when(ts) -> str:
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(int(ts or 0)))


def score_color(s: int) -> str:
    return T["ok"] if s >= 85 else T["warn"] if s >= 60 else T["bad"]


def head_text(c: dict) -> str:
    k, p = c["head"]
    return tr(k, **p)


def detail_text(c: dict) -> str:
    lines = [tr(k, **p) for k, p in c.get("det") or []]
    if c["st"] in (HC.BAD, HC.WARN):
        lines.append(tr("hc.why_l", text=tr(f"hc.why.{c['id']}")))
        lines.append(tr("hc.todo_l", text=tr(f"hc.todo.{c['id']}")))
    if c["st"] != HC.OK:
        lines.append(tr("hc.cmd", cmd=HC.CHECK_CMD.get(c["id"], "")))
    return "\n".join(lines)


class PlanDialog(QDialog):
    """План «Виправити все безпечне»: кожне виправлення з поясненням і командою; будь-що можна зняти."""
    WIDTH = 700
    TEXT_W = WIDTH - 2 * 26 - 2 * 12 - 20 - 12 - 24  # ширина тексту: поля вікна й рядка, позначка, проміжок, запас

    def __init__(self, parent, fids: list, res: dict):
        super().__init__(parent)
        self.setWindowTitle(E.APP_TITLE)
        self.setModal(True)
        # фіксована ширина: інакше Qt рахує висоту перенесених рядків у вкладених рядках до того, як знає ширину,
        # і описи налазять один на одний
        self.setFixedWidth(self.WIDTH)
        v = vbox(self, (26, 24, 26, 20), 10)
        v.addWidget(label(tr("hc.plan.title"), "h2", wrap=True))
        v.addWidget(label(tr("hc.plan.text"), "sub", wrap=True))
        self.checks = {}
        for fid in fids:
            r = QFrame()
            r.setObjectName("row")
            h = hbox(r, (12, 10, 12, 10), 12)
            c = Check()
            c.setChecked(True)
            h.addWidget(c, 0, Qt.AlignmentFlag.AlignTop)
            col = vbox(spacing=2)
            cmd = label(tr("hc.ask.cmd", cmd=HC.fix_command(fid, res)), "muted", wrap=True)
            cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            for lb in (label(tr(f"hc.fix.{fid}"), "rowTitle", wrap=True), label(tr(f"hc.fixd.{fid}"), "desc", wrap=True),
                       cmd):
                lb.ensurePolished()  # шрифт зі стилю — до розрахунку висоти
                lb.setMinimumHeight(lb.heightForWidth(self.TEXT_W))
                col.addWidget(lb)
            h.addLayout(col, 1)
            v.addWidget(r)
            self.checks[fid] = c
        v.addSpacing(8)
        h = hbox(spacing=8)
        h.addStretch()
        h.addWidget(button(tr("btn.cancel"), None, self.reject))
        ok = button(tr("hc.plan.run"), "primary", self.accept)
        ok.setDefault(True)
        h.addWidget(ok)
        v.addLayout(h)

    def showEvent(self, e):
        dark_titlebar(self)
        fade_in_window(self)
        super().showEvent(e)

    def selected(self) -> list:
        return [f for f, c in self.checks.items() if c.isChecked()]


class HealthCard:
    """Картка «Здоров'я ПК»: оцінка, вердикт, картки перевірок і виправлення."""

    def __init__(self, main, lay, page=None):
        self.main = main
        self.page = page
        self.res = None
        self.show_ok = False
        self.card, v = section_card(tr("hc.title"), tr("hc.sub"))
        top = hbox(margins=(14, 4, 14, 6), spacing=16)
        self.ring = Ring(T["acc"], 84, 8, 22)
        self.ring.text = "—"
        top.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignTop)
        col = vbox(spacing=4)
        self.verdict = label(tr("hc.title"), "h3", wrap=True)
        col.addWidget(self.verdict)
        self.summary = label(tr("hc.never"), "desc", wrap=True)
        col.addWidget(self.summary)
        bh = hbox(spacing=8)
        self.btn = button(tr("hc.check"), "primary", self.check)
        bh.addWidget(self.btn)
        self.btn_fix = button(tr("hc.fix_all", n=0), "good", self.fix_all)
        self.btn_fix.hide()
        bh.addWidget(self.btn_fix)
        self.btn_ok = button(tr("hc.show_ok", n=0), "ghost", self.toggle_ok)
        self.btn_ok.hide()
        bh.addWidget(self.btn_ok)
        bh.addStretch()
        col.addLayout(bh)
        top.addLayout(col, 1)
        v.addLayout(top)
        self.admin_note = label(tr("hc.not_admin"), "desc", wrap=True)
        self.admin_note.setContentsMargins(14, 0, 14, 4)
        self.admin_note.setStyleSheet(f"color: {T['warn']};")
        self.admin_note.hide()
        v.addWidget(self.admin_note)
        self.box = vbox(spacing=2)
        v.addLayout(self.box)
        lay.addWidget(self.card)
        last = F.CFG["health_last"]
        if isinstance(last, dict) and last.get("checks"):
            self.show(last)

    # ── перевірка ──
    def check(self):
        hw = self.main.hw or {}

        def job(log, p):
            return HC.run_check(hw, log=log)
        self.main.run_quick(tr("hc.title"), job, busy=self.btn, silent=True, on_done=self._done)

    def _done(self, res):
        if not isinstance(res, dict) or "checks" not in res:
            return
        crash = res.pop("crash", None)
        if isinstance(crash, dict) and "incidents" in crash:  # той самий розбір — і в картку «Чому впав комп?»
            F.CFG["crash_last"] = crash
            card = getattr(self.page, "crash", None)
            if card is not None:
                card.show(crash)
        F.CFG["health_last"] = res
        self.show(res)

    def show(self, res: dict):
        self.res = res
        s = int(res.get("score", 0))
        self.ring.text = str(s)
        self.ring.set_value(s / 100.0, score_color(s))
        n = HC.counts(res)
        self.verdict.setText(tr("hc.verdict.bad") if n[HC.BAD] else tr("hc.verdict.warn") if n[HC.WARN]
                             else tr("hc.verdict.ok"))
        self.summary.setText(tr("hc.summary", bad=n[HC.BAD], warn=n[HC.WARN], ok=n[HC.OK] + n[HC.INFO],
                                when=when(res.get("ts"))))
        self.admin_note.setVisible(not res.get("admin", True))
        safe = HC.safe_fixes(res)
        self.btn_fix.setText(tr("hc.fix_all", n=len(safe)))
        self.btn_fix.setVisible(bool(safe))
        clear_layout(self.box)
        oks = [c for c in res["checks"] if c["st"] == HC.OK]
        for c in res["checks"]:
            if c["st"] != HC.OK or self.show_ok:
                self.box.addWidget(self.row(c))
        self.btn_ok.setVisible(bool(oks))
        self.btn_ok.setText(tr("hc.hide_ok") if self.show_ok else tr("hc.show_ok", n=len(oks)))

    def toggle_ok(self):
        self.show_ok = not self.show_ok
        if self.res:
            self.show(self.res)

    def row(self, c: dict) -> QFrame:
        r = QFrame()
        r.setObjectName("row")
        h = hbox(r, (14, 10, 14, 10), 12)
        h.addWidget(dot(T[DOT.get(c["st"], "acc")], 10), 0, Qt.AlignmentFlag.AlignTop)
        v = vbox(spacing=3)
        v.addWidget(label(f"{tr('hc.c.' + c['id'])} — {head_text(c)}", "rowTitle", wrap=True))
        d = detail_text(c)
        if d:
            lb = label(d, "desc", wrap=True)
            lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.addWidget(lb)
        acts = [f for f in c.get("fixes") or [] if f in HC.FIXES]
        opens = c.get("opens") or []
        if acts or opens:
            w = QWidget()
            fl = FlowLayout(w, 8, 6)
            fl.setContentsMargins(0, 4, 0, 0)
            for fid in acts:
                b = button(tr(f"hc.fix.{fid}"), "primary" if HC.FIXES[fid]["safe"] else None)
                b.clicked.connect(lambda _=False, f=fid: self.fix_one(f))
                fl.addWidget(b)
            for kind, val in opens:
                key = OPEN_LABEL.get(val or kind)
                if not key:
                    continue
                b = button(tr(key), "ghost")
                b.clicked.connect(lambda _=False, k=kind, x=val: self.open(k, x))
                fl.addWidget(b)
            v.addWidget(w)
        h.addLayout(v, 1)
        return r

    # ── дії ──
    def open(self, kind: str, val: str):
        if kind == "settings":
            self.main.do_fix("settings", val)
        elif kind == "page":
            self.main.go(val)
        elif kind == "hwc":
            self.main.open_hwc(val)
        elif kind == "tweak" and val in E.BY_ID:  # зміна з каталогу: питання з її описом, журнал відкату
            self.main.do_fix("tweak", val)
        elif kind == "crash" and self.page is not None:
            self.page.focus_crash()

    def _can_fix(self) -> bool:
        if E.IS_WIN and not E.DRY_RUN and not E.is_admin():
            Ask.info(self.card, tr("hc.title"), tr("hc.not_admin"))
            return False
        return True

    def fix_one(self, fid: str):
        if not self._can_fix():
            return
        fx = HC.FIXES[fid]
        text = tr(f"hc.fixd.{fid}") + "\n\n" + tr("hc.ask.cmd", cmd=HC.fix_command(fid, self.res)) + "\n" + \
            (tr("hc.ask.undo") if fx["kind"] == "tweak" else tr("hc.ask.act")) + \
            (" " + tr("hc.ask.reboot") if fx.get("reboot") else "")
        if Ask.ask(self.card, tr(f"hc.fix.{fid}"), text, tr("hc.plan.run")):
            self.run([fid], tr(f"hc.fix.{fid}"))

    def fix_all(self):
        if not self.res or not self._can_fix():
            return
        fids = HC.safe_fixes(self.res)
        if not fids:
            Ask.info(self.card, tr("hc.plan.title"), tr("hc.plan.none"))
            return
        dlg = PlanDialog(self.card, fids, self.res)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        chosen = dlg.selected()
        if chosen:
            self.run(chosen, tr("hc.plan.title"))

    def run(self, fids: list, title: str):
        hw = self.main.hw or {}
        res = self.res or {}
        rp = not self.main.restore_done and any(HC.FIXES[f]["kind"] == "tweak" for f in fids)
        before = set(E.JOURNAL.data["applied"])

        def job(log, prog):
            out = HC.run_plan(fids, hw, res, log, prog, restore_point=rp)
            RS.record_batch(before, "apply", log)  # зміни налаштувань — окремим пакетом для OptimaX-Rescue.cmd
            return out
        dlg = RunDialog(self.main, title, job)
        dlg.exec()
        out = dlg.res or {}
        if rp and out.get("results"):
            self.main.restore_done = True
        new = out.get("health")
        if isinstance(new, dict) and new.get("checks"):
            new.pop("crash", None)
            F.CFG["health_last"] = new
            self.show(new)
        lines = [f"{tr('hc.out.' + r['outcome'])} — {tr('hc.fix.' + r['fid'])}" for r in out.get("results") or []]
        if lines:
            if out.get("reboot"):
                lines.append("\n" + tr("hc.res.reboot"))
            Ask.info(self.card, tr("hc.res.title"), "\n".join(lines))
        self.main.refresh_all()
