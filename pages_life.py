"""
OptimaX — картки «Чому впав комп?», «Монітор на телефоні», «Перенесення налаштувань», вікна «Що нового» і звіту
про помилку. Логіка — crashlog.py, phonemon.py, transfer.py, whatsnew.py, bugreport.py.
"""
from __future__ import annotations

import os
import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPixmap, QGuiApplication
from PyQt6.QtWidgets import QFrame, QLabel, QFileDialog

import crashlog as CL
import engine as E
import features as F
import phonemon as PH
import transfer as TR
import whatsnew as WN
from i18n import tr
from ui_kit import T, label, button, vbox, hbox, dot, clear_layout, section_card, Switch, Ask

LEVEL = {"bsod": "bad", "power": "warn", "button": "acc"}


def when(ts) -> str:
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(int(ts or 0)))


def row(level: str, title: str, desc: str = "", btns=()) -> QFrame:
    r = QFrame()
    r.setObjectName("row")
    h = hbox(r, (14, 10, 14, 10), 12)
    h.addWidget(dot(T[{"bad": "bad", "warn": "warn", "ok": "ok"}.get(level, "acc")], 10), 0, Qt.AlignmentFlag.AlignTop)
    v = vbox(spacing=2)
    v.addWidget(label(title, "rowTitle", wrap=True))
    if desc:
        v.addWidget(label(desc, "desc", wrap=True))
    h.addLayout(v, 1)
    for b in btns:
        h.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
    return r


# ───────────────────────── «Чому впав комп?» ─────────────────────────
class CrashCard:
    """Картка на сторінці «Діагностика»."""

    def __init__(self, main, lay):
        self.main = main
        self.card, v = section_card(tr("crash.title"), tr("crash.sub"))
        bh = hbox(margins=(14, 2, 14, 6), spacing=8)
        self.btn = button(tr("crash.check"), "primary", self.check)
        bh.addWidget(self.btn)
        self.btn_mem = button(tr("crash.memtest"), None, self.memtest)
        bh.addWidget(self.btn_mem)
        self.btn_dumps = button(tr("crash.dumps"), "ghost", self.open_dumps)
        bh.addWidget(self.btn_dumps)
        bh.addStretch()
        v.addLayout(bh)
        self.head = label("", "desc", wrap=True)
        self.head.setContentsMargins(14, 0, 14, 4)
        v.addWidget(self.head)
        self.box = vbox(spacing=2)
        v.addLayout(self.box)
        lay.addWidget(self.card)
        last = F.CFG["crash_last"]
        if isinstance(last, dict) and last.get("incidents") is not None:
            self.show(last)

    def check(self):
        hw = self.main.hw or {}

        def job(log, p):
            return CL.analyze(sessions=None, mining=bool(hw.get("mining_gpu")))
        self.main.run_quick(tr("crash.title"), job, busy=self.btn, silent=True, on_done=self._done)

    def _done(self, res):
        if not isinstance(res, dict) or "incidents" not in res:
            return
        F.CFG["crash_last"] = res
        incs = res["incidents"]
        if incs:
            F.CFG["crash_seen"] = max(i["ts"] for i in incs)
        self.show(res)

    def show(self, res: dict):
        clear_layout(self.box)
        incs = res.get("incidents") or []
        self.head.setText(tr("crash.head", n=len(incs), days=res.get("days", CL.DAYS), when=when(res.get("ts"))))
        mining = bool((self.main.hw or {}).get("mining_gpu"))
        for inc in incs[:6]:
            title, text = CL.explain(inc)
            adv = "\n".join("• " + tr(f"crash.a.{a}", game=inc.get("game") or "") for a in inc.get("advice") or [])
            btns = []
            if inc.get("game_exe") and mining:
                b = button(tr("crash.original"), None)
                b.clicked.connect(lambda _=False, exe=inc["game_exe"]: self.to_original(exe))
                btns.append(b)
            self.box.addWidget(row(LEVEL.get(inc["kind"], "warn"), title, text + ("\n" + adv if adv else ""), btns))
        if not incs:
            self.box.addWidget(row("ok", tr("crash.none", days=res.get("days", CL.DAYS))))
        g = res.get("gpu") or {}
        if g:
            self.box.addWidget(row("warn", tr("crash.tdr", n=g["n"], driver=g.get("driver") or "?"),
                                   tr("crash.tdr_d", when=when(g.get("last")))))
        w = res.get("whea") or {}
        if w:
            self.box.addWidget(row("bad" if w.get("fatal") else "warn", tr("crash.whea", n=w["n"]),
                                   tr("crash.whea_d", when=when(w.get("last")))))
        m = res.get("memtest") or {}
        if m:
            key = "ok" if m.get("ok") else "bad" if m.get("ok") is False else "unknown"
            self.box.addWidget(row("ok" if m.get("ok") else "bad" if m.get("ok") is False else "warn",
                                   tr(f"crash.mem.{key}", when=when(m.get("ts"))), m.get("msg") or ""))
        d = res.get("dumps") or []
        self.btn_dumps.setVisible(bool(d))
        if d:
            codes = ", ".join(sorted({f"0x{x['code']:X}" for x in d if x.get("code")})) or "—"
            self.box.addWidget(row("acc", tr("crash.dumps_n", n=len(d), codes=codes)))

    def to_original(self, exe: str):
        card = self.main.pages["games"].mining
        if card:
            r = card.find_row(exe)
            if r:
                self.main.go("games")
                card.choose_mode(r, "original")
                return
        self.main.toast(tr("gr.not_listed", exe=exe), "warn")

    def memtest(self):
        if not Ask.ask(self.card, tr("crash.memtest"), tr("crash.memtest_q"), tr("crash.memtest")):
            return
        self.main.run_quick(tr("crash.memtest"), lambda log, p: CL.start_memtest(log), silent=True)

    def open_dumps(self):
        if E.IS_WIN and not E.DRY_RUN and os.path.isdir(CL.DUMP_DIR):
            os.startfile(CL.DUMP_DIR)  # noqa: лише Windows


# ───────────────────────── «Монітор на телефоні» ─────────────────────────
def qr_pixmap(text: str, px: int = 200) -> QPixmap:
    m = PH.qr_matrix(text)
    n = len(m) + 8  # «тиха зона» по 4 модулі
    img = QImage(n, n, QImage.Format.Format_RGB32)
    img.fill(QColor("#FFFFFF"))
    dark = QColor("#000000").rgb()
    for y, r in enumerate(m):
        for x, v in enumerate(r):
            if v:
                img.setPixel(x + 4, y + 4, dark)
    scale = max(1, px // n)
    return QPixmap.fromImage(img.scaled(n * scale, n * scale, Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.FastTransformation))


class PhoneCard:
    def __init__(self, main, lay):
        self.main = main
        self.card, v = section_card(tr("ph.title"), tr("ph.sub"))
        r = hbox(margins=(14, 4, 14, 4), spacing=12)
        self.sw = Switch()
        self.sw.set_quiet(PH.MONITOR.running)
        self.sw.clicked.connect(self.toggle)
        r.addWidget(self.sw)
        r.addWidget(label(tr("ph.enable"), "rowTitle"), 1)
        self.btn_new = button(tr("ph.new_code"), "ghost", self.new_code)
        r.addWidget(self.btn_new)
        v.addLayout(r)
        body = hbox(margins=(14, 4, 14, 10), spacing=16)
        self.qr = QLabel()
        self.qr.setFixedSize(200, 200)
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self.qr)
        tv = vbox(spacing=6)
        self.url = label("", "mono", wrap=True)
        self.url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tv.addWidget(self.url)
        self.hint = label("", "desc", wrap=True)
        tv.addWidget(self.hint)
        bh = hbox(spacing=8)
        self.btn_copy = button(tr("ph.copy"), "ghost", self.copy)
        bh.addWidget(self.btn_copy)
        bh.addStretch()
        tv.addLayout(bh)
        tv.addStretch()
        body.addLayout(tv, 1)
        self.body_w = QFrame()
        self.body_w.setLayout(body)
        v.addWidget(self.body_w)
        lay.addWidget(self.card)
        self.sync()

    def toggle(self, on: bool):
        if on:
            self.main.run_quick(tr("ph.title"), lambda log, p: PH.MONITOR.start(log), silent=True, on_done=self._started)
        else:
            self.main.run_quick(tr("ph.title"), lambda log, p: PH.MONITOR.stop(log), silent=True,
                                on_done=lambda _r: self.sync())

    def _started(self, res):
        if isinstance(res, dict) and res.get("error"):
            self.main.toast(tr("ph.fail", err=res["error"][:80]), "bad")
        self.sync(res.get("public") if isinstance(res, dict) else False)

    def sync(self, public: bool = False):
        on = PH.MONITOR.running
        self.sw.set_quiet(on)
        self.body_w.setVisible(on)
        self.btn_new.setVisible(on)
        if not on:
            return
        u = PH.MONITOR.url()
        self.url.setText(u)
        self.qr.setPixmap(qr_pixmap(u))
        hint = tr("ph.hint")
        if public:
            hint += "\n\n" + tr("ph.public")
        if PH.MONITOR.ip.startswith("127."):
            hint += "\n\n" + tr("ph.no_lan")
        self.hint.setText(hint)

    def copy(self):
        QGuiApplication.clipboard().setText(PH.MONITOR.url())
        self.main.toast(tr("ph.copied"))

    def new_code(self):
        PH.new_token()
        PH.MONITOR.token = PH.settings()["token"]
        self.sync()
        self.main.toast(tr("ph.new_done"))


# ───────────────────────── перенесення налаштувань ─────────────────────────
class TransferCard:
    def __init__(self, main, lay):
        self.main = main
        self.card, v = section_card(tr("tr.title"), tr("tr.sub"))
        bh = hbox(margins=(14, 4, 14, 10), spacing=8)
        self.btn_exp = button(tr("tr.export"), None, self.export)
        bh.addWidget(self.btn_exp)
        self.btn_imp = button(tr("tr.import"), None, self.import_)
        bh.addWidget(self.btn_imp)
        bh.addStretch()
        v.addLayout(bh)
        lay.addWidget(self.card)

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self.card, tr("tr.export"), "optimax-settings.json", "JSON (*.json)")
        if not path:
            return
        try:
            n = TR.export(path)
            self.main.toast(tr("tr.exported", n=n["tweaks"], g=n["games"]))
        except OSError as e:
            self.main.toast(str(e)[:100], "bad")

    def import_(self):
        path, _ = QFileDialog.getOpenFileName(self.card, tr("tr.import"), "", "JSON (*.json)")
        if not path:
            return
        try:
            data = TR.load(path)
        except (OSError, ValueError) as e:
            self.main.toast(tr("tr.bad", err=str(e)[:80]), "bad")
            return
        p = TR.plan(data, self.main.hw or {})
        text = tr("tr.summary", ver=data.get("version", "?"), new=len(p["tweaks"]), done=len(p["done"]),
                  blocked=len(p["blocked"]), unknown=len(p["unknown"]), games=len(p["games"]),
                  missing=len(p["missing"]))
        if not Ask.ask(self.card, tr("tr.import"), text, tr("tr.go")):
            return
        res = TR.apply_settings(data)
        opts = TR.game_options(data)
        main = self.main
        if opts:
            def job(log, prog):
                for path_, opt in opts:
                    F.set_game_option(path_, opt, True, log)
                    F.update_game(path_, **{opt: True})
                return {"ok": len(opts)}
            main.run_quick(tr("tr.import"), job, silent=True)
        main.pages["games"].reload()
        main.toast(tr("tr.imported", keys=len(res["keys"]), games=len(res["games"])))
        if p["tweaks"]:
            main.go("optimize")
            main.pages["optimize"].show_review(p["tweaks"], "import")


# ───────────────────────── «Що нового» і звіт про помилку ─────────────────────────
def show_whats_new(parent, version: str = None) -> None:
    keys = WN.notes(version)
    if not keys:
        return
    text = "\n\n".join("• " + tr(k) for k in keys)
    Ask.info(parent, tr("wn.title", v=version or E.VERSION), text)
    WN.mark_seen()


_ASKING = []  # вікно звіту вже відкрите — друге поверх нього не відкриваємо


def ask_report(main, trace: str, native: bool = False) -> None:
    import bugreport as BR
    from ui_kit import LOG
    if _ASKING or getattr(main, "quitting", False):
        return
    title_key, text_key = ("bug.native_t", "bug.native_d") if native else ("bug.crash_t", "bug.crash_d")
    _ASKING.append(1)
    try:
        if not Ask.ask(main, tr(title_key), tr(text_key), tr("bug.send")):
            return
    finally:
        _ASKING.clear()
    t, body = BR.build("native" if native else "crash", trace, hw=main.hw, log_tail=LOG.history[-25:])
    url = BR.open_issue(t, body)
    if not E.IS_WIN or E.DRY_RUN:
        main.toast(tr("bug.preview", n=len(url)))


def manual_report(main) -> None:
    import bugreport as BR
    from ui_kit import LOG
    t, body = BR.build("manual", hw=main.hw, log_tail=LOG.history[-25:])
    url = BR.open_issue(t, body)
    if not E.IS_WIN or E.DRY_RUN:
        main.toast(tr("bug.preview", n=len(url)))
