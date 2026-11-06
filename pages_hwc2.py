"""
OptimaX — розділи Hardware Center: фонові процеси, перевірка перед покупкою, звіти, FPS-оверлей.

Будуються сторінкою pages_hwcenter.HwCenterPage, коли розділ уперше відкривають; логіка — procmon.py, inspection.py,
hwreport.py, overlay.py, perfdiag.py.
"""
from __future__ import annotations

import os
import time
import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QFrame, QLineEdit, QFileDialog, QMenu

import engine as E
import features as F
import hwtests as HT
from i18n import tr
from ui_kit import (T, label, button, vbox, hbox, badge, style_badge, dot, clear_layout, section_card, Segmented, Switch,
                    Ask, LOG, Check)


def _row(parent_layout, title: str, sub: str = "", right=()):
    row = QFrame()
    row.setObjectName("row")
    h = hbox(row, (14, 8, 14, 8), 10)
    col = vbox(spacing=2)
    col.addWidget(label(title, "rowTitle"))
    if sub:
        col.addWidget(label(sub, "desc", wrap=True))
    h.addLayout(col, 1)
    for w in right:
        h.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)
    parent_layout.addWidget(row)
    return row


# ───────────────────────── Фонові процеси ─────────────────────────
def build_procs(page, v):
    import pages_hwcenter as PH
    c, cv = page.section(v, tr("pm.title"), tr("pm.sub"))
    r = hbox(margins=(14, 4, 14, 4), spacing=10)
    page.pm_auto = Switch()
    page.pm_auto.setChecked(bool(F.CFG["pm_auto"]))
    page.pm_auto.toggled.connect(lambda on: F.CFG.__setitem__("pm_auto", bool(on)))
    r.addWidget(page.pm_auto)
    r.addWidget(label(tr("pm.auto"), "desc"), 1)
    page.pm_rec_btn = button(tr("pm.record"), "primary", lambda: record_now(page))
    r.addWidget(page.pm_rec_btn)
    cv.addLayout(r)
    cv.addWidget(page._note(tr("pm.note")))
    prog, view = page.test_area(cv, ("procs",))
    page.pm_box = page.make_box(prog, view, page.pm_rec_btn)
    page.pm_view = view
    hc, hcv = page.section(v, tr("pm.hist"), tr("pm.hist_sub"))
    page.pm_list = vbox(spacing=0)
    hcv.addLayout(page.pm_list)
    ac, acv = page.section(v, tr("pm.adv"), tr("pm.adv_sub"))
    page.pm_adv = vbox(spacing=0)
    acv.addLayout(page.pm_adv)
    dc, dcv = page.section(v, tr("pd.title"), tr("pd.sub"))
    page.pd_box = vbox(spacing=6)
    dcv.addLayout(page.pd_box)
    uc, ucv = page.section(v, tr("uv.title"), tr("uv.sub"))
    page.uv_box = vbox(margins=(14, 2, 14, 8), spacing=6)
    ucv.addLayout(page.uv_box)


def show_procs(page):
    fill_sessions(page)
    fill_diag(page)
    fill_undervolt(page)


class _Recording:
    """Ручний запис фону на 60 с — як «тест» для TestBox."""

    def __init__(self, seconds: int = 60):
        import procmon as PM
        self.rec = PM.Recorder(manual=True)
        self.seconds = seconds
        self.t0 = time.time()
        self.stopped = False
        self.next = 0.0
        self.session = None

    def poll(self) -> dict:
        import procmon as PM
        el = time.time() - self.t0
        if not self.stopped and el < self.seconds:
            if time.time() >= self.next:
                self.next = time.time() + (PM.INTERVAL if E.IS_WIN else 0.05)
                self.rec.sample()
            return dict(state="running", t=round(el, 1))
        if self.session is None:
            self.session = self.rec.finish(None)
        return dict(state="cancelled" if self.stopped and el < 5 else "done", t=round(el, 1), session=self.session)

    def stop(self) -> None:
        self.stopped = True

    def cleanup(self) -> None:
        pass


def record_now(page):
    import procmon as PM
    if page.pm_box.busy:
        return
    seconds = 60 if E.IS_WIN else 4
    run = _Recording(seconds)

    def describe(states, s):
        st = states.get("rec") or {}
        return tr("pm.p", t=int(st.get("t") or 0), d=seconds), st.get("t") or 0, seconds

    def finish(states, samples, danger):
        sess = (states.get("rec") or {}).get("session")
        if not sess:
            return None
        PM.save_session(F.CFG, sess)
        fill_sessions(page)
        return PM.session_result(sess)
    page.pm_box.start({"rec": run}, finish, describe, sensors=False)


def fill_sessions(page):
    import procmon as PM
    clear_layout(page.pm_list)
    sess = list(reversed(F.CFG["pm_sessions"] or []))[:10]
    if not sess:
        page.pm_list.addWidget(page._note(tr("pm.none")))
        clear_layout(page.pm_adv)
        return
    for s in sess:
        res = PM.session_result(s)
        b = button(tr("gb.details"), "ghost", lambda r=res: page.pm_view.set(r))
        title = f"{time.strftime('%d.%m %H:%M', time.localtime(s.get('start') or 0))} · {s.get('game') or tr('pm.manual')}"
        sub = ", ".join(f"{p['name']} {p['avg_cpu']}%" for p in (s.get("processes") or [])[:3]) or tr("pm.clean")
        _row(page.pm_list, title, sub, (badge(tr(f"hwc.st.{res['status']}"),
                                              {"pass": "ok", "warn": "warn"}.get(res["status"], "muted")), b))
        # рекомендації під кожним процесом — у «Деталях»: page.pm_view показує знахідки
    last = sess[0]
    detail = PM.session_result(last)
    page.pm_view.set(detail)
    advice_rows(page, last)


def advice_rows(page, sess: dict):
    """Що можна зробити з кожним процесом — лише варіанти для людини, без автоматичних дій."""
    box = page.pm_adv
    clear_layout(box)
    if not sess.get("processes"):
        box.addWidget(page._note(tr("pm.clean")))
    for p in (sess.get("processes") or [])[:8]:
        acts = " · ".join(tr(f"pm.a.{a}") for a in p.get("advice") or [])
        sub = tr("pm.line", cpu=p["avg_cpu"], mx=p["max_cpu"], ram=p["ram_mb"], io=p["io_mb"]) + \
            (f" · {tr('pm.overlap', p=round(p['overlap'] * 100))}" if p.get("overlap") else "")
        _row(box, f"{p['name']} · {tr('pm.k.' + p['kind'])}", f"{sub}\n{tr('pm.can')}: {acts}")


def fill_diag(page):
    import perfdiag as PD
    clear_layout(page.pd_box)
    sessions = F.CFG["overlay_sessions"] or []
    hist = F.CFG["diag_last"]
    items = []
    if sessions:
        import overlay as OV
        try:
            import json
            with open(sessions[-1]["path"], encoding="utf-8") as f:
                rep = json.load(f)
            items = rep.get("diag") or []
        except (OSError, ValueError, KeyError):
            items = []
    if not items:
        page.pd_box.addWidget(page._note(tr("pd.none")))
        bh = hbox(margins=(14, 0, 14, 6), spacing=8)
        bh.addWidget(button(tr("pd.lag"), None, lambda: page.main.go("diagnose")))
        bh.addWidget(button(tr("pd.overlay"), None, lambda: page.show_section("overlay")))
        bh.addStretch()
        page.pd_box.addLayout(bh)
        return
    for it in items:
        ex = PD.explain(it)
        c = QFrame()
        c.setObjectName("row")
        cv = vbox(c, (14, 8, 14, 8), 3)
        h = hbox(spacing=8)
        h.addWidget(label(ex["title"], "rowTitle"), 1)
        h.addWidget(badge(ex["conf"], {"high": "ok", "medium": "acc"}.get(it["conf"], "muted")))
        cv.addLayout(h)
        for txt in [ex["what"]] + [f"• {e}" for e in ex["evidence"]] + [f"{tr('pd.do')}: {ex['do']}",
                                                                          f"{tr('pd.gain')}: {ex['gain']}",
                                                                          f"{tr('pd.risk')}: {ex['risk']}"]:
            cv.addWidget(label(txt, "desc", wrap=True))
        page.pd_box.addWidget(c)


def fill_undervolt(page):
    import perfdiag as PD
    clear_layout(page.uv_box)
    hw = page.main.hw or {}
    cpu = page.last("cpu_stress") or page.last("cpu_multi")
    gpu = page.last("stress_combined") or {}
    a = PD.undervolt_advice(hw, cpu or None, gpu or None)
    page.uv_box.addWidget(label(tr(f"uv.state.{a['state']}"), "h3"))
    for k in a["reasons"]:
        page.uv_box.addWidget(label("• " + tr(k), "desc", wrap=True))
    for i, k in enumerate(a["steps"], 1):
        page.uv_box.addWidget(label(f"{i}. {tr(k)}", "desc", wrap=True))
    page.uv_box.addWidget(label(tr(a["gpu"]), "desc", wrap=True))
    if a["gpu_tool"]:
        page.uv_box.addWidget(label(tr(a["gpu_tool"]), "desc", wrap=True))
    bh = hbox(spacing=8)
    bh.addWidget(button(tr("uv.verify_cpu"), None, lambda: page.show_section("cpu")))
    bh.addWidget(button(tr("uv.verify_gpu"), None, lambda: page.main.go("bench")))
    bh.addStretch()
    page.uv_box.addLayout(bh)
    page.uv_box.addWidget(label(tr("uv.never"), "muted", wrap=True))


# ───────────────────────── Перевірка перед покупкою ─────────────────────────
def build_inspect(page, v):
    import inspection as IN
    c, cv = page.section(v, tr("insp.title"), tr("insp.sub"))
    top = hbox(margins=(14, 4, 14, 6), spacing=8)
    page.insp_state = label("", "desc", wrap=True)
    top.addWidget(page.insp_state, 1)
    top.addWidget(button(tr("insp.new"), None, lambda: new_inspection(page)))
    top.addWidget(button(tr("hwc.ov.report"), "primary", lambda: page.show_section("reports")))
    cv.addLayout(top)
    page.insp_rows = vbox(spacing=0)
    cv.addLayout(page.insp_rows)
    cc, ccv = page.section(v, tr("insp.claimed"), tr("insp.claimed_sub"))
    page.claim_edits = {}
    sess = F.CFG["inspect"] or {}
    for key in ("cpu", "gpu", "ram", "disk"):
        h = hbox(margins=(14, 2, 14, 2), spacing=10)
        lb = label(tr(f"insp.c.{key}"), "desc")
        lb.setFixedWidth(160)
        h.addWidget(lb)
        e = QLineEdit((sess.get("claimed") or {}).get(key, ""))
        e.setPlaceholderText(tr(f"insp.c.{key}_ph"))
        e.editingFinished.connect(lambda: save_claimed(page))
        page.claim_edits[key] = e
        h.addWidget(e, 1)
        ccv.addLayout(h)
    page.claim_kv = __import__("pages_hwcenter").KV(1)
    ccv.addWidget(page.claim_kv)
    if not F.CFG["inspect"]:
        IN.new_session(F.CFG)
    page._show_inspect = lambda: fill_inspect(page)
    fill_inspect(page)


def new_inspection(page):
    import inspection as IN
    if not Ask.ask(page, tr("insp.new"), tr("insp.new_q"), tr("insp.new")):
        return
    IN.new_session(F.CFG)
    for e in page.claim_edits.values():
        e.setText("")
    fill_inspect(page)


def save_claimed(page):
    s = dict(F.CFG["inspect"] or {})
    s["claimed"] = {k: e.text().strip() for k, e in page.claim_edits.items()}
    F.CFG["inspect"] = s
    fill_inspect(page)


def inspect_statuses(page) -> dict:
    import gpuselect as GS
    import inspection as IN
    hw = page.main.hw or {}
    sess = F.CFG["inspect"] or {}
    last = F.CFG["hwc_last"] or {}
    ads = GS.adapters(GS.cached_probe() or {})
    out = {}
    hints = {}
    for sid, _kind in IN.STEPS:
        st, hint = IN.step_status(sid, sess, last, hw, F.CFG["bench"] or [], ads)
        out[sid] = st
        hints[sid] = hint
    return out, hints


def fill_inspect(page):
    import inspection as IN
    clear_layout(page.insp_rows)
    sts, hints = inspect_statuses(page)
    sess = F.CFG["inspect"] or {}
    done, total = IN.progress(sts)
    over = IN.overall(sts)
    page.insp_state.setText(tr("insp.state", d=done, t=total, when=time.strftime("%d.%m %H:%M",
                                                                                 time.localtime(sess.get("ts") or 0)))
                            + " · " + tr(IN.verdict_key(over, total - done)))
    for i, (sid, kind) in enumerate(IN.STEPS, 1):
        st = sts.get(sid) if sid != "summary" else (over if done == total else None)
        right = [badge(tr(f"hwc.st.{st}"), {"pass": "ok", "warn": "warn", "fail": "bad"}.get(st, "muted")) if st
                 else badge(tr("hwc.ov.not_run"), "muted")]
        if sid == "gpu":
            right.append(button(tr("insp.gpu.d"), None, lambda: gpu_run(page, "dgpu")))
            right.append(button(tr("insp.gpu.i"), "ghost", lambda: gpu_run(page, "igpu")))
        elif sid == "summary":
            right.append(button(tr("hwc.ov.report"), None, lambda: page.show_section("reports")))
        elif sid == "claimed":
            pass
        elif kind == "manual":
            right.append(button(tr("hwc.disp.mark"), None, lambda s=sid: mark_step(page, s)))
            if IN.SECTION.get(sid):
                right.append(button(tr("hwc.ov.open"), "ghost", lambda s=sid: page.show_section(IN.SECTION[s])))
        else:
            right.append(button(tr("hwc.ov.open"), None, lambda s=sid: page.show_section(IN.SECTION.get(s, "overview"))))
        if sid not in ("summary", "specs"):
            right.append(button(tr("insp.skip"), "ghost", lambda s=sid: skip_step(page, s)))
        sub = tr(f"insp.d.{sid}") + ((" " + tr(hints[sid])) if hints.get(sid) else "")
        _row(page.insp_rows, f"{i}. {tr('insp.s.' + sid)}", sub, right)
    rows = []
    for field, claimed, actual, st in IN.compare_claimed(sess.get("claimed") or {}, page.main.hw or {}):
        rows.append((tr(f"insp.c.{field}"), f"{tr('hwc.st.' + st)} · {claimed or '—'} → {actual or tr('hwc.na')}"))
    page.claim_kv.set(rows)


def gpu_run(page, kind: str):
    """Перевірка відеокарти перед покупкою: тест на дискретній і окремо на вбудованій (гібридний ноутбук)."""
    import gpuselect as GS
    ads = GS.adapters(GS.cached_probe() or {})
    pick = [a for a in ads if (a["kind"] in ("dgpu", "mining")) == (kind == "dgpu")]
    if pick:
        F.CFG["bench_gpu"] = pick[0]["key"]
    elif kind == "igpu":
        Ask.info(page, tr("insp.s.gpu"), tr("insp.gpu.no_igpu"))
        return
    bench = page.main.pages.get("bench")
    page.main.go("bench")
    if bench is not None:
        bench.sync_gpu()
        bench.start()


def mark_step(page, sid: str):
    m = QMenu(page)
    for st in (HT.PASS, HT.WARN, HT.FAIL, HT.SKIPPED):
        a = m.addAction(tr(f"hwc.mark.{st}"))
        a.triggered.connect(lambda _=False, s=st: _set_manual(page, sid, s))
    m.exec(page.cursor().pos())
    page.menu = m


def _set_manual(page, sid: str, st: str):
    s = dict(F.CFG["inspect"] or {})
    man = dict(s.get("manual") or {})
    man[sid] = st
    s["manual"] = man
    F.CFG["inspect"] = s
    fill_inspect(page)


def skip_step(page, sid: str):
    s = dict(F.CFG["inspect"] or {})
    sk = list(s.get("skipped") or [])
    if sid in sk:
        sk.remove(sid)
    else:
        sk.append(sid)
    s["skipped"] = sk
    F.CFG["inspect"] = s
    fill_inspect(page)


# ───────────────────────── Звіти ─────────────────────────
def build_reports(page, v):
    c, cv = page.section(v, tr("rep.title"), tr("rep.sub"))
    r = hbox(margins=(14, 4, 14, 4), spacing=10)
    page.rep_name = Check()
    r.addWidget(page.rep_name)
    r.addWidget(label(tr("rep.name"), "desc"), 1)
    cv.addLayout(r)
    bh = hbox(margins=(14, 4, 14, 8), spacing=8)
    for fmt in ("html", "pdf", "json"):
        bh.addWidget(button(tr(f"rep.save_{fmt}"), "primary" if fmt == "html" else None,
                            lambda f=fmt: save_report(page, f)))
    bh.addWidget(button(tr("rep.view"), None, lambda: view_report(page)))
    bh.addStretch()
    cv.addLayout(bh)
    cv.addWidget(page._note(tr("rep.privacy")))
    hc, hcv = page.section(v, tr("rep.hist"), tr("rep.hist_sub"))
    page.rep_list = vbox(spacing=0)
    hcv.addLayout(page.rep_list)
    cb = hbox(margins=(14, 4, 14, 8), spacing=8)
    cb.addWidget(button(tr("rep.compare"), None, lambda: compare_reports(page)))
    cb.addStretch()
    hcv.addLayout(cb)
    page.rep_pick = []


def show_reports(page):
    clear_layout(page.rep_list)
    hist = list(reversed(F.CFG["hwc_reports"] or []))
    if not hist:
        page.rep_list.addWidget(page._note(tr("rep.none")))
        return
    page.rep_pick = []
    for h in hist[:15]:
        ch = Check()
        ch.toggled.connect(lambda on, j=h["json"]: (page.rep_pick.append(j) if on else
                                                     page.rep_pick.remove(j) if j in page.rep_pick else None))
        st = h.get("status") or HT.NA
        when = time.strftime("%d.%m.%Y %H:%M", time.localtime(h.get("ts") or 0))
        _row(page.rep_list, when, os.path.basename(h.get("path") or ""),
             (badge(tr(f"hwc.st.{st}"), {"pass": "ok", "warn": "warn", "fail": "bad"}.get(st, "muted")), ch,
              button(tr("rep.open"), "ghost", lambda p=h.get("path"): open_file(p))))


def current_report(page) -> dict:
    import hwreport as HR
    info = page.cache.get("info")
    insp = None
    try:
        sts, _h = inspect_statuses(page)
        if any(sts.values()):
            insp = dict(ts=(F.CFG["inspect"] or {}).get("ts"), steps=sts)
    except Exception:
        insp = None
    return HR.build(page.main.hw or {}, info, F.CFG["hwc_last"] or {}, F.CFG["bench"] or [], insp,
                    include_name=page.rep_name.isChecked())


def pdf_writer(html_text: str, path: str) -> None:
    """HTML -> PDF засобами Qt (QTextDocument + QPdfWriter), без нових залежностей."""
    from PyQt6.QtGui import QPdfWriter, QTextDocument, QPageSize
    doc = QTextDocument()
    doc.setHtml(html_text)
    w = QPdfWriter(path)
    w.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    w.setResolution(110)
    doc.setPageSize(__import__("PyQt6.QtCore", fromlist=["QSizeF"]).QSizeF(w.width(), w.height()))
    doc.print(w)


def save_report(page, fmt: str):
    import hwreport as HR
    rep = current_report(page)
    default = os.path.join(HR.reports_dir(), time.strftime("OptimaX-report-%Y%m%d-%H%M%S.") + fmt)
    os.makedirs(HR.reports_dir(), exist_ok=True)
    path, _ = QFileDialog.getSaveFileName(page, tr(f"rep.save_{fmt}"), default, f"{fmt.upper()} (*.{fmt})")
    if not path:
        return
    try:
        out = HR.save(F.CFG, rep, fmt, path, pdf_writer if fmt == "pdf" else None)
    except Exception as e:  # noqa: BLE001
        Ask.info(page, tr("rep.title"), tr("e.err", err=f"{type(e).__name__}: {e}"))
        return
    LOG.write(tr("rep.saved", path=out))
    page.main.toast(tr("rep.saved", path=os.path.basename(out)))
    show_reports(page)


def view_report(page):
    """Переглянути поточний звіт у OptimaX: HTML у тимчасовий файл і в браузер за замовчуванням."""
    import tempfile
    import hwreport as HR
    path = os.path.join(tempfile.gettempdir(), "OptimaX-report-preview.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(HR.to_html(current_report(page)))
    open_file(path)


def compare_reports(page):
    import tempfile
    import hwreport as HR
    if len(page.rep_pick) != 2:
        Ask.info(page, tr("rep.compare"), tr("rep.pick_two"))
        return
    try:
        a, b = (HR.load(p) for p in page.rep_pick)
    except (OSError, ValueError) as e:
        Ask.info(page, tr("rep.compare"), tr("e.err", err=e))
        return
    if (a.get("created") or 0) > (b.get("created") or 0):
        a, b = b, a
    path = os.path.join(tempfile.gettempdir(), "OptimaX-report-compare.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(HR.compare_html(a, b))
    open_file(path)


def open_file(path: str):
    if not path:
        return
    if not E.IS_WIN:
        LOG.write(f"  [demo] {path}")
        return
    try:
        os.startfile(path)  # noqa: лише Windows
    except OSError:
        webbrowser.open("file:///" + path.replace("\\", "/"))


# ───────────────────────── FPS-оверлей ─────────────────────────
def build_overlay(page, v):
    import overlay as OV
    c, cv = page.section(v, tr("ov.title"), tr("ov.sub"))
    cfg = dict(F.CFG["overlay"] or {})
    r = hbox(margins=(14, 4, 14, 4), spacing=10)
    page.ov_on = Switch()
    page.ov_on.setChecked(bool(cfg.get("enabled")))
    page.ov_on.toggled.connect(lambda on: overlay_toggle(page, on))
    r.addWidget(page.ov_on)
    r.addWidget(label(tr("ov.enable"), "rowTitle"), 1)
    cv.addLayout(r)
    for key, items, cur in (("mode", [tr(f"ov.m.{m}") for m in OV.MODES], OV.MODES.index(cfg.get("mode", "standard"))
                             if cfg.get("mode", "standard") in OV.MODES else 1),
                            ("corner", [tr(f"ov.c.{x}") for x in OV.CORNERS], OV.CORNERS.index(cfg.get("corner", "tl"))
                             if cfg.get("corner", "tl") in OV.CORNERS else 0),
                            ("size", ["80%", "100%", "125%", "150%"], [80, 100, 125, 150].index(cfg.get("size", 100))
                             if cfg.get("size", 100) in (80, 100, 125, 150) else 1),
                            ("opacity", ["60%", "85%", "100%"], [60, 85, 100].index(cfg.get("opacity", 85))
                             if cfg.get("opacity", 85) in (60, 85, 100) else 1),
                            ("hotkey", [f"{p[0]} / {p[3]}" for p in OV.HOTKEY_PRESETS], int(cfg.get("hotkey") or 0))):
        h = hbox(margins=(14, 2, 14, 2), spacing=10)
        lb = label(tr(f"ov.o.{key}"), "desc")
        lb.setFixedWidth(170)
        h.addWidget(lb)
        seg = Segmented(items)
        seg.select(cur)
        seg.changed.connect(lambda i, k=key: overlay_set(page, k, i))
        h.addWidget(seg)
        h.addStretch()
        cv.addLayout(h)
    for key in ("white", "black"):
        h = hbox(margins=(14, 2, 14, 2), spacing=10)
        lb = label(tr(f"ov.o.{key}"), "desc")
        lb.setFixedWidth(170)
        h.addWidget(lb)
        e = QLineEdit(", ".join(cfg.get(key) or []))
        e.setPlaceholderText("game.exe, other.exe")
        e.editingFinished.connect(lambda k=key, ed=e: overlay_list(page, k, ed.text()))
        h.addWidget(e, 1)
        cv.addLayout(h)
    page.ov_state = label("", "desc", wrap=True)
    page.ov_state.setContentsMargins(14, 4, 14, 4)
    cv.addWidget(page.ov_state)
    cv.addWidget(page._note(tr("ov.note")))
    bh = hbox(margins=(14, 2, 14, 8), spacing=8)
    page.ov_pm_btn = button(tr("ov.get_pm"), None, lambda: get_presentmon(page))
    bh.addWidget(page.ov_pm_btn)
    bh.addStretch()
    cv.addLayout(bh)
    sc, scv = page.section(v, tr("ov.sessions"), tr("ov.sessions_sub"))
    page.ov_list = vbox(spacing=0)
    scv.addLayout(page.ov_list)
    page._show_overlay = lambda: sync_overlay(page)
    sync_overlay(page)


def overlay_toggle(page, on: bool):
    ctl = getattr(page.main, "overlay", None)
    if ctl is None:
        return
    busy = ctl.set_enabled(bool(on))
    LOG.write(tr("ov.on") if on else tr("ov.off"))
    if busy:
        page.main.toast(tr("ov.hk_busy", keys=", ".join(busy)), "warn")
    sync_overlay(page)


def overlay_set(page, key: str, i: int):
    import overlay as OV
    c = dict(F.CFG["overlay"] or {})
    c[key] = {"mode": OV.MODES, "corner": OV.CORNERS, "size": (80, 100, 125, 150), "opacity": (60, 85, 100)}.get(
        key, range(len(OV.HOTKEY_PRESETS)))[i]
    F.CFG["overlay"] = c
    ctl = getattr(page.main, "overlay", None)
    if ctl is not None:
        if key == "hotkey" and c.get("enabled"):
            ctl.start_hotkeys()
        if ctl.win is not None and ctl.win.isVisible() and ctl.game:
            ctl.show_on(ctl.game)


def overlay_list(page, key: str, text: str):
    c = dict(F.CFG["overlay"] or {})
    c[key] = [x.strip().lower() for x in text.replace(";", ",").split(",") if x.strip().lower().endswith(".exe")]
    F.CFG["overlay"] = c


def sync_overlay(page):
    import fpstest as FT
    import overlay as OV
    cfg = F.CFG["overlay"] or {}
    pm = FT.find_presentmon()
    ctl = getattr(page.main, "overlay", None)
    if not hasattr(ctl, "cpu_self"):
        ctl = None
    i = int(cfg.get("hotkey") or 0) % len(OV.HOTKEY_PRESETS)
    parts = [tr("ov.keys", a=OV.HOTKEY_PRESETS[i][0], b=OV.HOTKEY_PRESETS[i][3])]
    parts.append(tr("ov.pm_ok") if pm else tr("ov.pm_missing"))
    if ctl is not None and ctl.cpu_self is not None:
        parts.append(tr("ov.cost", p=ctl.cpu_self))
    page.ov_state.setText("\n".join(parts))
    page.ov_pm_btn.setVisible(not pm)
    clear_layout(page.ov_list)
    sess = list(reversed(F.CFG["overlay_sessions"] or []))[:12]
    if not sess:
        page.ov_list.addWidget(page._note(tr("ov.no_sessions")))
    for s in sess:
        st = s.get("stats") or {}
        when = time.strftime("%d.%m %H:%M", time.localtime(s.get("ts") or 0))
        _row(page.ov_list, f"{when} · {s.get('game') or '?'}",
             tr("ov.sess_line", fps=st.get("avg", "—"), low=st.get("low1", "—"), low01=st.get("low01", "—"),
                st=st.get("stutters", 0), s=st.get("seconds", 0)),
             (button(tr("rep.open"), "ghost", lambda p=s.get("path"): open_file(p)),))


def get_presentmon(page):
    import fpstest as FT
    if not Ask.ask(page, tr("ov.get_pm"), tr("ov.get_pm_q"), tr("btn.continue")):
        return
    page.main.run_quick(tr("ov.get_pm"), lambda log, p: {"path": FT.download_presentmon(log)},
                        busy=page.ov_pm_btn, on_done=lambda _r: sync_overlay(page))
