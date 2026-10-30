"""
OptimaX — вікно «Розумна оптимізація»: заміри до і після, застосування, пошук змін, які шкодять саме цьому ПК.

Логіка — в abtest.Session; тут лише виконання дій (GPU-тест або гра, застосування/відкат твіків,
перезавантаження) і показ ходу. Стан зберігається після кожного кроку, тож після перезавантаження
OptimaX продовжує з того ж місця.
"""
from __future__ import annotations

import subprocess
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QProgressBar, QPlainTextEdit, QWidget

import abtest as AB
import engine as E
import features as F
import gpubench as GB
import rescue as RS
from i18n import tr
from ui_kit import (T, label, button, vbox, hbox, badge, style_badge, Ask, Worker, LOG, append_log, make_font,
                    dark_titlebar, card, Segmented)

SMART_TASK = "OptimaX Smart"
GAME_SECONDS = 45
STEP_KEYS = ("base", "apply", "after", "search", "done")
STAGE_STEP = {"init": 0, "base": 0, "apply": 1, "reboot": 1, "after": 2, "scan": 3, "search": 3, "probe": 3,
              "reapply": 3, "confirm": 3, "restore": 3, "done": 4}
RESULT_KIND = {"better": "ok", "same": "acc", "fixed": "ok", "unexplained": "warn"}


def perf_applied() -> list:
    """Уже застосовані зміни продуктивності, що діють без перезавантаження (для перевірки «чи допомагають»)."""
    out = []
    for tid in E.JOURNAL.newest_first():
        t = E.BY_ID.get(tid)
        if t and t.group in AB.PERF_GROUPS and t.reversible and not t.custom and not t.reboot:
            out.append(tid)
    return out


def new_session(ids=(), mode: str = "new") -> AB.Session:
    pref = F.CFG["smart_pref"] or {}
    prov, game = pref.get("provider", "gpu"), pref.get("game")
    if prov == "game" and not game:
        prov = "gpu"
    if mode == "audit":
        return AB.Session(perf_applied(), [], [], mode="audit", provider=prov, game=game)
    live, boot, other = AB.split_plan(ids, E.BY_ID)
    return AB.Session(live, boot, other, mode="new", provider=prov, game=game)


def set_resume_task(on: bool, log=lambda *_: None) -> None:
    if not E.IS_WIN or E.DRY_RUN:
        return
    if on:
        cmd = subprocess.list2cmdline(F._self_command() + ["--smart"])
        E.run(["schtasks", "/Create", "/TN", SMART_TASK, "/TR", cmd, "/SC", "ONLOGON", "/RL", "HIGHEST", "/IT",
               "/DELAY", "0000:20", "/F"], 20, log)
    else:
        E.run(["schtasks", "/Delete", "/TN", SMART_TASK, "/F"], 20)


class SmartDialog(QDialog):
    def __init__(self, main, session: AB.Session, restore_point: bool = False):
        super().__init__(main)
        self.main = main
        self.s = session
        self.rp = restore_point
        self.run = None
        self.worker = None
        self.started = False
        self.stopping = False
        self.finished_ok = False
        self.setWindowTitle(f"{E.APP_TITLE} — {tr('sm.title')}")
        self.setModal(True)
        self.resize(900, 640)
        v = vbox(self, (24, 22, 24, 20), 12)
        top = hbox()
        top.addWidget(label(tr("sm.title") + (" · " + tr("sm.audit_t") if session.mode == "audit" else ""), "h2"))
        top.addStretch()
        self.state = badge(tr("run.running"), "acc")
        top.addWidget(self.state)
        v.addLayout(top)
        v.addWidget(label(tr("sm.how_game", s=GAME_SECONDS) if session.provider == "game" else tr("sm.how_gpu"),
                          "desc", wrap=True))
        steps = hbox(spacing=14)
        self.step_dots, self.step_lbls = [], []
        for i, key in enumerate(STEP_KEYS):
            s = hbox(spacing=8)
            n = label(str(i + 1), "stepNum")
            n.setFixedSize(24, 24)
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.addWidget(n)
            lb = label(tr(f"sm.step.{key}"), "desc")
            s.addWidget(lb)
            steps.addLayout(s)
            self.step_dots.append(n)
            self.step_lbls.append(lb)
        steps.addStretch()
        v.addLayout(steps)
        self.status = label(tr("run.prepare"), "rowTitle", wrap=True)
        v.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setRange(0, 0)
        v.addWidget(self.bar)

        self.res = card()
        rv = vbox(self.res, (22, 16, 22, 16), 6)
        rh = hbox(spacing=20)
        self.res_big = label("", "display")
        rh.addWidget(self.res_big)
        rt = vbox(spacing=3)
        self.res_t = label("", "h3", wrap=True)
        self.res_d = label("", "desc", wrap=True)
        rt.addWidget(self.res_t)
        rt.addWidget(self.res_d)
        rh.addLayout(rt, 1)
        rv.addLayout(rh)
        self.res_removed = label("", "desc", wrap=True)
        rv.addWidget(self.res_removed)
        self.res.hide()
        v.addWidget(self.res)

        self.logw = QPlainTextEdit()
        self.logw.setObjectName("log")
        self.logw.setReadOnly(True)
        self.logw.setFont(make_font(12, mono=True))
        v.addWidget(self.logw, 1)
        bh = hbox(spacing=8)
        self.btn_share = button(tr("sc.share"), "good", self.share)
        self.btn_share.hide()
        bh.addWidget(self.btn_share)
        self.btn_revert = button(tr("sm.revert_all"), "danger", self.revert_all)
        self.btn_revert.hide()
        bh.addWidget(self.btn_revert)
        bh.addStretch()
        self.btn_main = button(tr("run.stop"), None, self._main_clicked)
        bh.addWidget(self.btn_main)
        v.addLayout(bh)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self._sync_steps()

    # ── службове ──
    def showEvent(self, e):
        dark_titlebar(self)
        super().showEvent(e)
        if not self.started:
            self.started = True
            QTimer.singleShot(250, self.step)

    def log(self, text: str):
        append_log(self.logw, text)
        LOG.write(text)

    def save(self):
        F.CFG["smart"] = self.s.to_dict() if self.s.stage != "done" else None

    def _sync_steps(self):
        cur = STAGE_STEP.get(self.s.stage, 0)
        for i, (n, lb) in enumerate(zip(self.step_dots, self.step_lbls)):
            col = T["ok"] if i < cur or self.s.stage == "done" else T["acc_h"] if i == cur else T["mute"]
            n.setStyleSheet(f"color:{col}; border-color:{col};")
            lb.setStyleSheet(f"color:{T['text'] if i == cur else T['sub']};")

    # ── хід ──
    def step(self):
        if self.stopping:
            self._stopped()
            return
        a = self.s.next()
        self.save()
        self._sync_steps()
        do = a["do"]
        if do == "measure":
            self._measure(a)
        elif do in ("apply", "undo"):
            self._job(a)
        elif do == "reboot":
            self._reboot()
        elif do == "done":
            self._done()

    def _measure(self, a: dict):
        self.status.setText(tr(f"sm.m.{a['label']}", n=a.get("n", 1)))
        self.log(f"[►] {self.status.text()}")
        if self.s.provider == "game":
            self._measure_game()
            return
        try:
            self.run = GB.start("ab", "bench", quality="ab", seconds=GB.AB_SECONDS)
        except Exception as e:
            self._fail(str(e))
            return
        self.bar.setRange(0, 0)
        self.timer.start(400)

    def _measure_game(self):
        import fpstest as FT
        game = self.s.game
        if not FT.find_presentmon():
            self._fail(tr("fps.pm_missing"))
            return
        if not Ask.ask(self, tr("sm.game_t"), tr("sm.game_q", game=F.game_name(game), s=GAME_SECONDS), tr("fps.start")):
            self.stop()
            return
        import ntpath
        exe = ntpath.basename(game)
        self.bar.setRange(0, GAME_SECONDS)

        def job(log, prog):
            return FT.capture(exe, GAME_SECONDS, log, prog)
        self._start_worker(job, self._game_done)

    def _game_done(self, res):
        if isinstance(res, dict) and res.get("avg"):
            self._fed({"avg": res["avg"], "low1": res.get("low1") or res["avg"]})
        elif self.stopping:
            self._stopped()
        else:
            self._fail((res or {}).get("error") if isinstance(res, dict) else tr("fps.no_frames"))

    def _poll(self):
        if not self.run:
            self.timer.stop()
            return
        st = self.run.poll()
        s = st.get("state")
        if s in ("starting", "warmup", "running"):
            if s == "running":
                self.bar.setRange(0, int(st.get("duration") or GB.AB_SECONDS))
                self.bar.setValue(int(st.get("t") or 0))
            return
        self.timer.stop()
        run, self.run = self.run, None
        run.cleanup()
        res = st.get("result") or {}
        if s == "done" and res.get("avg"):
            self._fed({"avg": res["avg"], "low1": res.get("low1") or res["avg"]})
        elif s == "cancelled" and self.stopping:
            self._stopped()
        elif s == "error":
            self._fail(st.get("error") or "?")
        else:
            self._fail(tr("gb.v.crash.t") if s in ("crash", "lost") else tr("gb.cancelled"))

    def _fed(self, m: dict):
        self.log(tr("sm.l.measured", avg=f"{m['avg']:.1f}", low=f"{m['low1']:.1f}"))
        self.s.feed(m)
        self._log_events()
        self.save()
        QTimer.singleShot(300, self.step)

    def _log_events(self):
        for key, kw in self.s.events[getattr(self, "_ev_seen", 0):]:
            if key in ("sm.ev_culprit", "sm.ev_false"):
                kw = dict(kw, title=E.entry_title(kw.get("id", "")))
            self.log(tr(key, **kw))
        self._ev_seen = len(self.s.events)

    def _start_worker(self, job, on_done):
        w = Worker(job)
        self.worker = w
        w.log.connect(self.log)
        w.progress.connect(lambda i, n, t: (self.bar.setRange(0, max(n, 1)), self.bar.setValue(min(i, n))))

        def done(res):
            self.worker = None
            on_done(res)
        w.result.connect(done)
        self.main._workers.add(w)
        w.finished.connect(lambda: self.main._workers.discard(w))
        w.start()

    def _job(self, a: dict):
        ids, why = list(a["ids"]), a["why"]
        self.status.setText(tr(f"sm.j.{a['do']}_{why}", n=len(ids)))
        self.log(f"[►] {self.status.text()}")
        hw = self.main.hw or {}
        first = a["do"] == "apply" and why == "apply"
        before = set(E.JOURNAL.data["applied"])
        rp = self.rp and first
        E.CANCEL.clear()

        def job(log, prog):
            if a["do"] == "apply":
                items = [E.BY_ID[i] for i in ids if i in E.BY_ID]
                return E.apply_tweaks(items, log, prog, header=False, hw=hw, restore_point=rp, by="smart")
            return E.undo_ids(ids, log, prog, by="smart")

        def done(res):
            if first:
                RS.record_batch(before, "smart")
            if a["do"] == "apply":
                self.s.ok(applied=[i for i in ids if E.JOURNAL.has(i)])
            else:
                self.s.ok()
            self._log_events()
            self.save()
            QTimer.singleShot(300, self.step)
        self._start_worker(job, done)

    def _reboot(self):
        self.save()
        self.status.setText(tr("sm.reboot_t"))
        self.log(tr("sm.reboot_log"))
        if not E.IS_WIN or E.DRY_RUN:  # перегляд: перезавантаження лише позначаємо
            self.log("  [dry-run] shutdown /r /t 10")
            self.s.ok()
            self.save()
            QTimer.singleShot(300, self.step)
            return
        set_resume_task(True, self.log)
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        style_badge(self.state, tr("sm.wait_reboot"), "warn")
        self.btn_main.setText(tr("btn.close"))
        self.finished_ok = True
        if Ask.ask(self, tr("sm.reboot_t"), tr("sm.reboot_q"), tr("run.reboot")):
            E.run(["shutdown", "/r", "/t", "10", "/c", "OptimaX"], 15, self.log)
            self.main.quit_app()

    def _done(self):
        sm = self.s.summary()
        F.CFG["smart_last"] = sm
        F.CFG["smart"] = None
        set_resume_task(False)
        self.finished_ok = True
        self.timer.stop()
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self._sync_steps()
        res = sm["result"]
        style_badge(self.state, tr(f"sm.r.{res}.badge"), RESULT_KIND.get(res, "acc"))
        d = sm.get("delta") or {}
        self.res.show()
        self.res_big.setText(f"{d.get('avg', 0):+.1f}%" if d else "—")
        good = (d.get("avg") or 0) >= -0.5
        self.res_big.setStyleSheet(f"color:{T['ok'] if good else T['warn']};")
        self.res_t.setText(tr(f"sm.r.{res}.t", n=len(sm["removed"])))
        self.res_d.setText(tr("sm.r.detail", avg0=f"{(sm.get('base') or {}).get('avg', 0):.0f}",
                              avg1=f"{(sm.get('final') or {}).get('avg', 0):.0f}",
                              low=f"{d.get('low1', 0):+.1f}", n=sm["measures"]) + " " + tr(f"sm.r.{res}.d"))
        if sm["removed"]:
            self.res_removed.setText(tr("sm.removed", items=", ".join(E.entry_title(i) for i in sm["removed"])))
            self.res_removed.show()
        else:
            self.res_removed.hide()
        self.status.setText(tr("sm.done_status", kept=len(sm["kept"])))
        self.log(tr("sm.done_log", res=tr(f"sm.r.{res}.badge"), d=f"{d.get('avg', 0):+.1f}"))
        self.btn_share.show()
        self.btn_revert.setVisible(res == "unexplained")
        self._finish_buttons()
        self.main.refresh_all()

    def _finish_buttons(self):
        self.btn_main.setText(tr("btn.close"))
        self.btn_main.setObjectName("primary")
        self.btn_main.style().unpolish(self.btn_main)
        self.btn_main.style().polish(self.btn_main)

    # ── зупинка й помилки ──
    def _restore_consistent(self, then):
        """Після зупинки посеред пошуку частина змін могла бути тимчасово відкочена — повертаємо їх."""
        missing = []
        if STAGE_STEP.get(self.s.stage, 0) >= 3:
            missing = [i for i in self.s.applied_live() if not E.JOURNAL.has(i)]
        F.CFG["smart"] = None
        set_resume_task(False)
        if not missing:
            then()
            return
        hw = self.main.hw or {}
        E.CANCEL.clear()
        self._start_worker(lambda log, p: E.apply_tweaks([E.BY_ID[i] for i in missing if i in E.BY_ID], log, p,
                                                         header=False, hw=hw, by="smart"), lambda _r: then())

    def _stopped(self):
        def then():
            self.finished_ok = True
            self.bar.setRange(0, 1)
            style_badge(self.state, tr("run.stopped"), "warn")
            self.status.setText(tr("sm.stopped"))
            self.log(tr("sm.stopped"))
            self._finish_buttons()
            self.main.refresh_all()
        self._restore_consistent(then)

    def _fail(self, err: str):
        def then():
            self.finished_ok = True
            self.bar.setRange(0, 1)
            style_badge(self.state, tr("run.error"), "bad")
            self.status.setText(tr("sm.failed", err=err))
            self.log(tr("e.err", err=err))
            self._finish_buttons()
            self.main.refresh_all()
        self._restore_consistent(then)

    def stop(self):
        if self.finished_ok:
            return
        self.stopping = True
        self.status.setText(tr("run.stopping_text"))
        if self.run:
            self.run.stop()
        elif self.worker is None:
            self._stopped()

    def _main_clicked(self):
        if self.finished_ok:
            self.accept()
        else:
            self.stop()

    def reject(self):
        if self.finished_ok:
            super().reject()
        else:
            self.stop()

    def closeEvent(self, e):
        if not self.finished_ok:
            e.ignore()
            self.stop()
            return
        super().closeEvent(e)

    # ── після завершення ──
    def revert_all(self):
        ids = [i for i in self.s.live + self.s.boot if E.JOURNAL.has(i)]
        if not ids or not Ask.ask(self, tr("sm.revert_all"), tr("sm.revert_all_q", n=len(ids)), tr("bk.undo"), "danger"):
            return
        self._start_worker(lambda log, p: E.undo_ids(ids, log, p),
                           lambda _r: (self.btn_revert.hide(), self.main.refresh_all(),
                                       self.main.toast(tr("sm.reverted", n=len(ids)))))

    def share(self):
        import sharecard as SC
        SC.ShareDialog(self.main).exec()


class SmartCard(QWidget):
    """Картка на сторінці «Бенчмарки»: що міряти, перевірити застосовані зміни, останній результат."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        c = card("cardAccent")
        outer = vbox(self)
        outer.addWidget(c)
        v = vbox(c, (24, 20, 24, 20), 10)
        v.addWidget(label(tr("sm.title"), "h1"))
        v.addWidget(label(tr("sm.card_d"), "sub", wrap=True))
        steps = hbox(spacing=18)
        for i in (1, 2, 3):
            s = hbox(spacing=8)
            n = label(str(i), "stepNum")
            n.setFixedSize(24, 24)
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.addWidget(n, 0, Qt.AlignmentFlag.AlignTop)
            s.addWidget(label(tr(f"sm.card_s{i}"), "desc", wrap=True), 1)
            steps.addLayout(s, 1)
        v.addLayout(steps)
        r = hbox(spacing=10)
        r.addWidget(label(tr("sm.measure_by"), "desc"))
        self.seg = Segmented([tr("sm.by_gpu"), tr("sm.by_game")])
        self.seg.changed.connect(self._provider)
        r.addWidget(self.seg)
        self.btn_game = button(tr("fps.pick_game"), None, self.pick_game)
        r.addWidget(self.btn_game)
        r.addStretch()
        v.addLayout(r)
        b = hbox(spacing=10)
        self.last = label("", "desc", wrap=True)
        b.addWidget(self.last, 1)
        self.btn_audit = button(tr("sm.audit_btn"), None, main.smart_audit)
        b.addWidget(self.btn_audit)
        self.btn_new = button(tr("sm.new_btn"), "primary", main.open_smart_plan)
        b.addWidget(self.btn_new)
        v.addLayout(b)
        self.sync()

    def _provider(self, i: int):
        pref = dict(F.CFG["smart_pref"] or {})
        pref["provider"] = ("gpu", "game")[i]
        F.CFG["smart_pref"] = pref
        self.sync()

    def pick_game(self):
        from PyQt6.QtWidgets import QMenu
        m = QMenu(self)
        games = F.CFG["games"] or []
        run = F.running_apps()
        for g in games:
            m.addAction(F.game_name(g["path"])).triggered.connect(lambda _=False, p=g["path"]: self._set_game(p))
        if run:
            m.addSeparator()
            for name, path in run[:20]:
                m.addAction(f"{name}    {path}").triggered.connect(lambda _=False, p=path: self._set_game(p))
        if not (games or run):
            Ask.info(self, tr("games.running_none_t"), tr("fps.no_games"))
            return
        m.exec(self.btn_game.mapToGlobal(self.btn_game.rect().bottomLeft()))
        self.menu = m

    def _set_game(self, path: str):
        pref = dict(F.CFG["smart_pref"] or {})
        pref.update(provider="game", game=path)
        F.CFG["smart_pref"] = pref
        self.sync()

    def sync(self):
        pref = F.CFG["smart_pref"] or {}
        game = pref.get("provider") == "game"
        self.seg.select(1 if game else 0)
        self.btn_game.setVisible(game)
        self.btn_game.setText(tr("fps.game", name=F.game_name(pref["game"])) if pref.get("game") else tr("fps.pick_game"))
        self.btn_audit.setEnabled(bool(perf_applied()))
        sm = F.CFG["smart_last"] or {}
        if sm.get("result"):
            d = sm.get("delta") or {}
            self.last.setText(tr("sm.last", when=time.strftime("%d.%m %H:%M", time.localtime(sm.get("ts", 0))),
                                 res=tr(f"sm.r.{sm['result']}.badge"), d=f"{d.get('avg', 0):+.1f}",
                                 n=len(sm.get("removed") or [])))
        else:
            self.last.setText(tr("sm.never"))
