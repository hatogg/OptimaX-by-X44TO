"""
OptimaX — Hardware Center, розділ «Кулери й андервольт» відеокарти. Логіка й безпека — у gputune.py; тут лише
інтерфейс: що вміє карта (і чому ні), живі показники, вентилятори, потужність і андервольт, перевірка стабільності
й автопідбір. Нічого не змінюється без «Застосувати».
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QSpinBox, QSlider, QGridLayout

import engine as E
import features as F
import gputune as GT
from i18n import tr
from ui_kit import label, button, vbox, hbox, Segmented, Switch, Ask, LOG, clear_layout, badge

FAN_MODES = ("auto", "curve", "fixed")
PRESETS = ("quiet", "balanced", "cool", "custom")
VERIFY_SECONDS = 300


def build(page, v):
    page.gt = dict(run=None, kind="", tune=None, loading=False, started=0.0)
    c, cv = page.section(v, tr("gt.title"), tr("gt.sub"))
    # 6.15: тестовий режим — що це означає, і перемикач; поки вимкнено, драйвер відеокарти не чіпаємо взагалі
    page.gt_test = QWidget()
    tv = vbox(page.gt_test, (14, 2, 14, 6), 6)
    tb = hbox(spacing=10)
    tb.addWidget(badge(tr("gt.test_badge"), "warn"))
    tb.addStretch()
    tv.addLayout(tb)
    tv.addWidget(label(tr("gt.test_note"), "desc", wrap=True))
    er = hbox(spacing=10)
    page.gt_enable = Switch()
    page.gt_enable.setChecked(GT.enabled(F.CFG))
    page.gt_enable.toggled.connect(lambda on: _set_enabled(page, on))
    er.addWidget(page.gt_enable)
    er.addWidget(label(tr("gt.test_enable"), "desc", wrap=True), 1)
    tv.addLayout(er)
    page.gt_test.setVisible(GT.TEST_MODE)
    cv.addWidget(page.gt_test)
    head = hbox(margins=(14, 4, 14, 2), spacing=10)
    page.gt_name = label(tr("gt.loading"), "h3", wrap=True)
    head.addWidget(page.gt_name, 1)
    page.gt_badge = badge("", "muted")
    head.addWidget(page.gt_badge)
    cv.addLayout(head)
    page.gt_live = label("", "desc", wrap=True)
    page.gt_live.setContentsMargins(14, 0, 14, 0)
    cv.addWidget(page.gt_live)
    page.gt_caps = vbox(margins=(14, 4, 14, 4), spacing=2)
    cv.addLayout(page.gt_caps)
    page.gt_admin = label(tr("gt.admin"), "muted", wrap=True)
    page.gt_admin.setContentsMargins(14, 0, 14, 4)
    page.gt_admin.setVisible(E.IS_WIN and not E.is_admin())
    cv.addWidget(page.gt_admin)
    cv.addWidget(page._note(tr("gt.safety")))

    # ── вентилятори ──
    page.gt_fan_card, fcv = page.section(v, tr("gt.fan.title"), tr("gt.fan.sub"))
    r = hbox(margins=(14, 4, 14, 4), spacing=10)
    r.addWidget(label(tr("gt.fan.mode"), "desc"))
    page.gt_fan_mode = Segmented([tr(f"gt.fan.{m}") for m in FAN_MODES])
    page.gt_fan_mode.changed.connect(lambda i: _fan_mode(page, i))
    r.addWidget(page.gt_fan_mode)
    r.addStretch()
    fcv.addLayout(r)
    page.gt_curve_w = QWidget()
    cw = vbox(page.gt_curve_w, (14, 0, 14, 0), 6)
    pr = hbox(spacing=10)
    pr.addWidget(label(tr("gt.fan.preset"), "desc"))
    page.gt_preset = Segmented([tr(f"gt.preset.{p}") for p in PRESETS])
    page.gt_preset.changed.connect(lambda i: _preset(page, i))
    pr.addWidget(page.gt_preset)
    pr.addStretch()
    cw.addLayout(pr)
    grid = QGridLayout()
    grid.setHorizontalSpacing(10)
    grid.addWidget(label(tr("gt.fan.temp"), "muted"), 0, 0)
    grid.addWidget(label(tr("gt.fan.speed"), "muted"), 1, 0)
    page.gt_pts = []
    for i in range(5):
        t, s = QSpinBox(), QSpinBox()
        t.setRange(20, 100)
        t.setSuffix(" °C")
        s.setRange(0, 100)
        s.setSuffix(" %")
        t.valueChanged.connect(lambda _v: _custom(page))
        s.valueChanged.connect(lambda _v: _custom(page))
        grid.addWidget(t, 0, i + 1)
        grid.addWidget(s, 1, i + 1)
        page.gt_pts.append((t, s))
    cw.addLayout(grid)
    fcv.addWidget(page.gt_curve_w)
    page.gt_fixed_w = QWidget()
    xw = hbox(page.gt_fixed_w, (14, 0, 14, 0), 10)
    xw.addWidget(label(tr("gt.fan.fixed_l"), "desc"))
    page.gt_fixed = QSlider(Qt.Orientation.Horizontal)
    page.gt_fixed.setRange(GT.FAN_MIN_SAFE, 100)
    page.gt_fixed.setValue(60)
    page.gt_fixed_v = label("60 %", "rowTitle")
    page.gt_fixed.valueChanged.connect(lambda x: page.gt_fixed_v.setText(f"{x} %"))
    xw.addWidget(page.gt_fixed, 1)
    xw.addWidget(page.gt_fixed_v)
    fcv.addWidget(page.gt_fixed_w)
    fb = hbox(margins=(14, 4, 14, 6), spacing=8)
    page.gt_fan_apply = button(tr("gt.apply"), "primary", lambda: apply_fans(page))
    fb.addWidget(page.gt_fan_apply)
    page.gt_fan_state = label("", "muted", wrap=True)
    fb.addWidget(page.gt_fan_state, 1)
    fcv.addLayout(fb)
    page.gt_fan_note = page._note("")
    fcv.addWidget(page.gt_fan_note)

    # ── потужність і андервольт ──
    page.gt_uv_card, ucv = page.section(v, tr("gt.uv.title"), tr("gt.uv.sub"))
    g = QGridLayout()
    g.setContentsMargins(14, 4, 14, 4)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    page.gt_power_l = label(tr("gt.power"), "desc")
    page.gt_power = QSlider(Qt.Orientation.Horizontal)
    page.gt_power_v = label("", "rowTitle")
    page.gt_power.valueChanged.connect(lambda _x: _power_text(page))
    g.addWidget(page.gt_power_l, 0, 0)
    g.addWidget(page.gt_power, 0, 1)
    g.addWidget(page.gt_power_v, 0, 2)
    page.gt_cap_l = label(tr("gt.cap"), "desc")
    page.gt_cap_on = Switch()
    page.gt_cap = QSpinBox()
    page.gt_cap.setSuffix(" MHz")
    page.gt_cap.setSingleStep(15)
    capw = QWidget()
    ch = hbox(capw, spacing=8)
    ch.addWidget(page.gt_cap_on)
    ch.addWidget(page.gt_cap, 1)
    g.addWidget(page.gt_cap_l, 1, 0)
    g.addWidget(capw, 1, 1, 1, 2)
    page.gt_off_l = label(tr("gt.offset"), "desc")
    page.gt_off = QSpinBox()
    page.gt_off.setSuffix(" MHz")
    page.gt_off.setSingleStep(15)
    g.addWidget(page.gt_off_l, 2, 0)
    g.addWidget(page.gt_off, 2, 1, 1, 2)
    page.gt_mf_l = label(tr("gt.maxfreq"), "desc")
    page.gt_mf = QSpinBox()
    page.gt_mf.setSuffix(" MHz")
    g.addWidget(page.gt_mf_l, 3, 0)
    g.addWidget(page.gt_mf, 3, 1, 1, 2)
    page.gt_v_l = label(tr("gt.voltage"), "desc")
    page.gt_v = QSpinBox()
    page.gt_v.setSuffix(" mV")
    page.gt_v.setSingleStep(5)
    g.addWidget(page.gt_v_l, 4, 0)
    g.addWidget(page.gt_v, 4, 1, 1, 2)
    g.setColumnStretch(1, 1)
    ucv.addLayout(g)
    ub = hbox(margins=(14, 4, 14, 4), spacing=8)
    page.gt_apply = button(tr("gt.apply"), "primary", lambda: apply_uv(page))
    page.gt_verify = button(tr("gt.verify"), None, lambda: start_verify(page))
    page.gt_tune = button(tr("gt.autotune"), None, lambda: start_tune(page))
    page.gt_reset = button(tr("gt.reset"), "ghost", lambda: reset(page))
    for b in (page.gt_apply, page.gt_verify, page.gt_tune):
        ub.addWidget(b)
    ub.addStretch()
    ub.addWidget(page.gt_reset)
    ucv.addLayout(ub)
    sr = hbox(margins=(14, 2, 14, 4), spacing=10)
    page.gt_start = Switch()
    page.gt_start.toggled.connect(lambda on: _on_start(page, on))
    sr.addWidget(page.gt_start)
    page.gt_start_l = label(tr("gt.on_start"), "desc", wrap=True)
    sr.addWidget(page.gt_start_l, 1)
    ucv.addLayout(sr)
    page.gt_progress = label("", "desc", wrap=True)
    page.gt_progress.setContentsMargins(14, 0, 14, 0)
    ucv.addWidget(page.gt_progress)
    page.gt_stop = button(tr("run.stop"), "ghost", lambda: stop_run(page))
    page.gt_stop.hide()
    sb = hbox(margins=(14, 0, 14, 4))
    sb.addWidget(page.gt_stop)
    sb.addStretch()
    ucv.addLayout(sb)
    page.gt_result = vbox(margins=(14, 2, 14, 8), spacing=3)
    ucv.addLayout(page.gt_result)
    ucv.addWidget(page._note(tr("gt.uv.note")))
    page.gt_timer = QTimer(page)
    page.gt_timer.timeout.connect(lambda: _tick(page))
    _enable(page, False)
    if GT.enabled(F.CFG):
        _load(page)
    else:
        _off(page)


def _off(page) -> None:
    """Розділ вимкнено (тестовий режим): ні карти, ні показників, ні налаштувань."""
    page.gt_name.setText(tr("gt.test_off"))
    page.gt_badge.hide()
    page.gt_live.setText("")
    clear_layout(page.gt_caps)
    page.gt_fan_card.hide()
    page.gt_uv_card.hide()
    page.gt_timer.stop()


def _set_enabled(page, on: bool) -> None:
    st = GT.state(F.CFG)
    if on:
        if not Ask.ask(page, tr("gt.test_badge"), tr("gt.test_ask"), tr("gt.test_on_btn")):
            page.gt_enable.blockSignals(True)
            page.gt_enable.setChecked(False)
            page.gt_enable.blockSignals(False)
            return
        st["enabled"] = True
        GT.save_state(F.CFG, st)
        LOG.write(tr("gt.log.test_on"))
        _load(page)
        page.gt_timer.start(1000)
        return
    if page.gt.get("run"):  # спершу зупинити перевірку чи підбір
        stop_run(page)
    t = _tuner()
    if t is not None and st.get("active"):  # вимикаючи розділ, не лишаємо змін, якими вже ніде керувати
        GT.SESSION.stop_fans()
        GT.restore_original(F.CFG, t)
    GT.SESSION.close()
    st = GT.state(F.CFG)
    st.update(enabled=False, on_start=False)
    GT.save_state(F.CFG, st)
    LOG.write(tr("gt.log.test_off"))
    _off(page)


def _load(page) -> None:
    """Відкрити карту у фоні: NVML / ADLX ініціалізуються від частки секунди до секунди."""
    if page.gt["loading"]:
        return
    page.gt["loading"] = True
    name = (page.gpu_plan() or {}).get("name") or ""

    def done(t):
        page.gt["loading"] = False
        _fill(page, t if isinstance(t, GT.Tuner) else GT.SESSION.tuner)
    page.run_bg(lambda log, p: GT.SESSION.open(name), done)


def show(page) -> None:
    if not GT.enabled(F.CFG):
        _off(page)
        return
    if GT.SESSION.tuner is None:
        _load(page)
    else:
        _fill(page, GT.SESSION.tuner)
    page.gt_timer.start(1000)


def sync(page) -> None:
    """Стан змінився поза сторінкою (запуск програми, відкат журналу)."""
    if GT.SESSION.tuner is not None and GT.enabled(F.CFG):
        _fill(page, GT.SESSION.tuner)


def _tuner():
    t = GT.SESSION.tuner
    return t if t is not None and t.ok() else None


def _fill(page, t) -> None:
    clear_layout(page.gt_caps)
    if t is None or not t.ok():
        page.gt_name.setText(tr("gt.none"))
        page.gt_badge.hide()
        for k, have, why in GT.describe_caps(t or GT.Tuner()):
            page.gt_caps.addWidget(label(f"• {tr('gt.part.' + k)}: {why}", "muted", wrap=True))
        page.gt_fan_card.hide()
        page.gt_uv_card.hide()
        return
    page.gt_name.setText(t.name)
    page.gt_badge.setText(GT.VENDOR_NAMES.get(t.vendor, t.vendor))
    page.gt_badge.show()
    for k, have, why in GT.describe_caps(t):
        page.gt_caps.addWidget(label(f"{'✓' if have else '—'} {tr('gt.part.' + k)}" + ("" if have else f": {why}"),
                                     "desc" if have else "muted", wrap=True))
    st = GT.state(F.CFG)
    prof = st.get("profile") or {}
    mine = prof.get("gpu") == t.key
    fan = t.caps.get("fan")
    page.gt_fan_card.setVisible(bool(fan))
    if fan:
        f = (prof.get("fan") or {}) if mine else {}
        mode = f.get("mode") or "auto"
        page.gt_fan_mode.select(FAN_MODES.index(mode) if mode in FAN_MODES else 0)
        pts = f.get("curve") or GT.CURVE_PRESETS["balanced"]
        _set_points(page, pts)
        preset = next((p for p in PRESETS[:-1] if [list(x) for x in GT.CURVE_PRESETS[p]] == [list(x) for x in pts]),
                      "custom")
        page.gt_preset.select(PRESETS.index(preset))
        page.gt_fixed.setRange(max(GT.FAN_MIN_SAFE, fan.get("min", 0)), fan.get("max", 100))
        page.gt_fixed.setValue(int(f.get("fixed") or 60))
        page.gt_fan_note.setText(tr("gt.fan.note_native" if fan.get("mode") == "native" else "gt.fan.note_nv",
                                    t=GT.FAN_FORCE_TEMP, m=GT.FAN_MIN_SAFE))
        _fan_mode(page, FAN_MODES.index(mode) if mode in FAN_MODES else 0)
    has_uv = any(k in t.caps for k in ("power", "clock", "offset", "maxfreq", "voltage"))
    page.gt_uv_card.setVisible(has_uv)
    p = t.caps.get("power")
    for w in (page.gt_power_l, page.gt_power, page.gt_power_v):
        w.setVisible(bool(p))
    if p:
        page.gt_power.setRange(p["min"], p["max"])
        page.gt_power.setValue(int(prof.get("power") if mine and prof.get("power") is not None else
                                   (p.get("cur") if p.get("cur") is not None else p["default"])))
        _power_text(page)
    c = t.caps.get("clock")
    for w in (page.gt_cap_l, page.gt_cap_on, page.gt_cap):
        w.setVisible(bool(c))
    if c:
        page.gt_cap.setRange(c["min"], c["max"])
        page.gt_cap.setValue(int(prof.get("clock") or c["max"]) if mine else c["max"])
        page.gt_cap_on.setChecked(bool(mine and prof.get("clock")))
    o = t.caps.get("offset")
    for w in (page.gt_off_l, page.gt_off):
        w.setVisible(bool(o))
    if o:
        page.gt_off.setRange(max(o["min"], -300), min(o["max"], 300))
        page.gt_off.setValue(int(prof.get("offset") or 0) if mine else int(o.get("cur") or 0))
    mf = t.caps.get("maxfreq")
    for w in (page.gt_mf_l, page.gt_mf):
        w.setVisible(bool(mf))
    if mf:
        page.gt_mf.setRange(mf["min"], mf["max"])
        page.gt_mf.setValue(int(prof.get("maxfreq") or mf.get("cur") or mf["max"]) if mine else
                            int(mf.get("cur") or mf["max"]))
    vv = t.caps.get("voltage")
    for w in (page.gt_v_l, page.gt_v):
        w.setVisible(bool(vv))
    if vv:
        page.gt_v.setRange(vv["min"], vv["max"])
        page.gt_v.setSingleStep(max(1, vv.get("step") or 5))
        page.gt_v.setValue(int(prof.get("voltage") or vv.get("cur") or vv["max"]) if mine else
                           int(vv.get("cur") or vv["max"]))
    page.gt_tune.setVisible(GT.AutoTune(F.CFG, t, None).supported)
    _sync_start(page)
    _enable(page, not (E.IS_WIN and not E.is_admin()))


def _sync_start(page) -> None:
    st = GT.state(F.CFG)
    prof = st.get("profile") or {}
    t = _tuner()
    verified = bool(t and prof.get("gpu") == t.key and prof.get("verified"))
    page.gt_start.blockSignals(True)
    page.gt_start.setChecked(bool(st.get("on_start") and verified))
    page.gt_start.blockSignals(False)
    page.gt_start.setEnabled(verified and not page.gt["run"])
    page.gt_start_l.setText(tr("gt.on_start") if verified else tr("gt.on_start_need"))


def _enable(page, on: bool) -> None:
    busy = bool(page.gt["run"])
    for b in (page.gt_apply, page.gt_verify, page.gt_tune, page.gt_reset, page.gt_fan_apply):
        b.setEnabled(on and not busy)
    page.gt_stop.setVisible(busy)


def _fan_mode(page, i: int) -> None:
    mode = FAN_MODES[i]
    page.gt_curve_w.setVisible(mode == "curve")
    page.gt_fixed_w.setVisible(mode == "fixed")


def _set_points(page, pts) -> None:
    for (ts, ss), (t, s) in zip(page.gt_pts, list(pts)[:5]):
        for w, val in ((ts, t), (ss, s)):
            w.blockSignals(True)
            w.setValue(int(val))
            w.blockSignals(False)


def _preset(page, i: int) -> None:
    if PRESETS[i] != "custom":
        _set_points(page, GT.CURVE_PRESETS[PRESETS[i]])


def _custom(page) -> None:
    page.gt_preset.select(PRESETS.index("custom"))


def _points(page) -> list:
    return [(t.value(), s.value()) for t, s in page.gt_pts]


def _power_text(page) -> None:
    t = _tuner()
    p = (t.caps.get("power") if t else None) or {}
    val = page.gt_power.value()
    if p.get("unit") == "W":
        pct = round(100 * val / p["default"]) if p.get("default") else 100
        page.gt_power_v.setText(f"{val} W ({pct} %)")
    else:
        page.gt_power_v.setText(f"{val:+d} %")


def _profile(page) -> dict:
    """Профіль з того, що зараз на сторінці (без вентиляторів NVIDIA — їх тримає крива в програмі)."""
    t = _tuner()
    prof = dict(GT.state(F.CFG).get("profile") or {})
    if prof.get("gpu") != t.key:
        prof = {}
    if "power" in t.caps:
        prof["power"] = page.gt_power.value()
    if "clock" in t.caps:
        prof["clock"] = page.gt_cap.value() if page.gt_cap_on.isChecked() else None
    if "offset" in t.caps:
        prof["offset"] = page.gt_off.value()
    if "maxfreq" in t.caps:
        prof["clock"] = page.gt_mf.value()
    if "voltage" in t.caps:
        prof["voltage"] = page.gt_v.value()
    prof.pop("verified", None)  # змінене треба перевірити знову
    return prof


def apply_fans(page) -> None:
    t = _tuner()
    if not t:
        return
    mode = FAN_MODES[[b.isChecked() for b in page.gt_fan_mode.btns].index(True)]
    curve = None
    if mode == "curve":
        try:
            curve = GT.curve_normalize(_points(page))
        except ValueError:
            Ask.info(page, tr("gt.fan.title"), tr("gt.fan.bad_curve"))
            return
    fixed = page.gt_fixed.value() if mode == "fixed" else None
    try:
        ok = GT.SESSION.set_fans(F.CFG, mode, curve, fixed)
    except Exception as e:
        ok = False
        t.last_error = str(e)
    st = GT.state(F.CFG)
    prof = dict(st.get("profile") or {}) if (st.get("profile") or {}).get("gpu") == t.key else {"gpu": t.key}
    old = prof.get("fan") or {}
    prof["fan"] = dict(mode=mode, curve=[list(p) for p in curve] if curve else old.get("curve"),
                       fixed=fixed or old.get("fixed"))
    st["profile"] = prof
    if mode != "auto":
        st["active"] = True
    GT.save_state(F.CFG, st)
    LOG.write(tr("gt.log.fans", mode=tr(f"gt.fan.{mode}"), st=tr("gt.ok" if ok else "gt.fail")))
    page.main.toast(tr("gt.fan.applied") if ok else tr("gt.fail_d", e=t.last_error or "?"), "ok" if ok else "bad")
    _tick(page)


def apply_uv(page) -> None:
    t = _tuner()
    if not t:
        return
    prof = _profile(page)
    risky = prof.get("offset") or prof.get("voltage") is not None and "voltage" in t.caps and \
        prof.get("voltage") < (t.caps["voltage"].get("cur") or t.caps["voltage"]["max"])
    if risky and not Ask.ask(page, tr("gt.uv.title"), tr("gt.uv.ask"), tr("gt.apply")):
        return
    try:
        res = GT.apply_profile(F.CFG, t, prof, LOG.write)
    except Exception as e:
        page.main.toast(tr("gt.fail_d", e=e), "bad")
        return
    bad = [k for k, ok in res.items() if not ok]
    page.main.toast(tr("gt.applied") if not bad else tr("gt.partial", what=", ".join(tr(f"gt.part.{k}") for k in bad)),
                    "ok" if not bad else "warn")
    _fill(page, t)


def reset(page) -> None:
    t = _tuner()
    if not t:
        return
    GT.SESSION.stop_fans()
    ok = GT.restore_original(F.CFG, t)
    st = GT.state(F.CFG)
    st["on_start"] = False
    if ok:
        prof = st.get("profile") or {}
        if prof.get("gpu") == t.key:
            st["profile"] = None
    GT.save_state(F.CFG, st)
    LOG.write(tr("gt.log.reset", st=tr("gt.ok" if ok else "gt.fail")))
    page.main.toast(tr("gt.reset_done") if ok else tr("gt.fail_d", e=t.last_error or "?"), "ok" if ok else "bad")
    _clear_result(page)
    _fill(page, t)


def _on_start(page, on: bool) -> None:
    st = GT.state(F.CFG)
    st["on_start"] = bool(on)
    GT.save_state(F.CFG, st)


# ── перевірка стабільності й автопідбір ──
def _plan_for(page, t):
    """7.1.1: стрес-тест — на тій карті, яку налаштовуємо (t), а не на вибраній для тестів у налаштуваннях: інакше
    андервольт однієї карти «перевірявся» навантаженням іншої."""
    import gpubench as GB
    plan = page.gpu_plan() or {}
    want = GB.gpu_key(getattr(t, "name", "") or "")
    if not want or GB.gpu_key(plan.get("name") or "") == want:
        return plan or None
    try:
        import gpuselect as GS
        hit = next((a for a in GS.adapters(GS.cached_probe()) if GB.gpu_key(a.get("name") or "") == want), None)
        if hit:
            p = GS.selection(page.main.hw or {}, choice=hit["key"])
            if p.get("name"):
                return p
    except Exception:
        pass
    return plan or None  # карту не знайшли серед адаптерів — перевірка «хто малював» (wrong_gpu) зупинить підбір


def _run_fn(page, t=None):
    import gpubench as GB
    plan = _plan_for(page, t)

    def run(seconds: int):
        return GB.start("1080p", "stress", max(1, seconds // 60), seconds=seconds, adapter=plan)
    return run


def start_verify(page) -> None:
    """Стрес-тест VERIFY_SECONDS із поточними налаштуваннями: пройшов — профіль «перевірений» (можна застосовувати
    під час запуску); ні — заводські значення."""
    t = _tuner()
    if not t or page.gt["run"]:
        return
    if not Ask.ask(page, tr("gt.verify"), tr("gt.verify_q", m=VERIFY_SECONDS // 60), tr("hwc.start")):
        return
    GT.mark_pending(F.CFG, t, "verify")
    st = GT.state(F.CFG)
    st["tuning"] = dict(key=t.key, ts=int(time.time()))  # поки йде перевірка, позначка не знімається за часом
    GT.save_state(F.CFG, st)
    page.gt.update(run=_run_fn(page, t)(VERIFY_SECONDS), kind="verify", started=time.time(), samples=[])
    _enable(page, True)
    page.gt_progress.setText(tr("gt.verify_run", t=0, d=VERIFY_SECONDS))


def start_tune(page) -> None:
    t = _tuner()
    if not t or page.gt["run"]:
        return
    tune = GT.AutoTune(F.CFG, t, _run_fn(page, t), LOG.write)
    if not tune.supported:
        return
    mins = round((GT.TUNE_STEP_SECONDS * 6 + GT.TUNE_VERIFY_SECONDS) / 60)
    if not Ask.ask(page, tr("gt.autotune"), tr("gt.tune_q", m=mins), tr("hwc.start"), "danger"):
        return
    GT.SESSION.stop_fans()
    try:
        tune.start()
    except Exception as e:
        page.main.toast(tr("gt.fail_d", e=e), "bad")
        return
    page.gt.update(run=tune, kind="tune", started=time.time(), tune=tune)
    _enable(page, True)
    _clear_result(page)


def stop_run(page) -> None:
    r = page.gt.get("run")
    if r is not None:
        r.stop()


def _tick(page) -> None:
    t = _tuner()
    if t is None:
        return
    if not page.gt.get("run"):
        # 7.1.1: живі показники (NVML / ADLX раз на секунду) — лише поки їх видно. Розділ закрили чи вікно сховали —
        # таймер зупиняється (знову запуститься show() з HwCenterPage.on_show / showEvent); згорнуте вікно — без
        # читання датчиків. Перевірку й автопідбір таймер веде далі за будь-яких умов.
        if not page.isVisible() or getattr(page, "current", "gputune") != "gputune":
            page.gt_timer.stop()
            return
        if page.window().isMinimized():
            return
    try:
        r = t.read()
    except Exception:
        r = {}
    parts = []
    if r.get("temp") is not None:
        parts.append(tr("gt.live.temp", v=r["temp"]))
    if r.get("fan") is not None:
        parts.append(tr("gt.live.fan", v=r["fan"]) + (f" · {r['rpm']} RPM" if r.get("rpm") else ""))
    elif r.get("rpm"):
        parts.append(f"{r['rpm']} RPM")
    if r.get("power") is not None:
        parts.append(tr("gt.live.power", v=r["power"]))
    if r.get("clock") is not None:
        parts.append(tr("gt.live.clock", v=r["clock"]))
    page.gt_live.setText(" · ".join(parts) if parts else tr("gt.live.none"))
    fans = GT.SESSION.fans
    if fans is not None and fans.running:
        page.gt_fan_state.setText(tr("gt.fan.running"))
    elif fans is not None and fans.error:
        page.gt_fan_state.setText(tr("gt.fan.stopped", e=fans.error))
    else:
        page.gt_fan_state.setText(tr("gt.fan.driver") if r.get("fan_auto", True) else "")
    run = page.gt.get("run")
    if run is None:
        return
    if page.gt["kind"] == "tune":
        phase = run.tick()
        page.gt_progress.setText(tr("gt.tune_run", phase=tr(f"gt.phase.{phase}"),
                                    v=run._label(run.value) if run.kind else "",
                                    t=int(time.time() - page.gt["started"])))
        if phase in ("done", "failed", "cancelled"):
            _finish_tune(page, run)
        return
    page.gt.setdefault("samples", []).append(r)
    st = run.poll()
    el = int(time.time() - page.gt["started"])
    if st.get("state") in ("starting", "running", "warmup"):
        page.gt_progress.setText(tr("gt.verify_run", t=el, d=VERIFY_SECONDS))
        return
    try:
        run.cleanup()
    except Exception:
        pass
    ok, why = GT.run_ok(st)  # 7.1.1: і «малювала інша карта» — не перевірка цієї
    gst = GT.state(F.CFG)
    gst.pop("tuning", None)
    GT.save_state(F.CFG, gst)
    if st.get("state") == "cancelled":
        GT.clear_pending(F.CFG)
        page.gt_progress.setText(tr("gt.verify_cancel"))
    elif ok:
        GT.clear_pending(F.CFG)
        gst = GT.state(F.CFG)
        prof = dict(gst.get("profile") or {})
        if prof.get("gpu") == t.key:
            prof["verified"] = int(time.time())
            gst["profile"] = prof
            GT.save_state(F.CFG, gst)
        page.gt_progress.setText(tr("gt.verify_ok", w=GT._avg(page.gt["samples"], "power") or "—",
                                    t=GT._max(page.gt["samples"], "temp") or "—"))
        page.main.toast(tr("gt.verify_ok_t"), "ok")
    else:
        GT.restore_original(F.CFG, t)
        page.gt_progress.setText(tr("gt.verify_bad") + (f" {tr(why)}" if why else ""))
        page.main.toast(tr("gt.verify_bad"), "bad")
    page.gt.update(run=None, kind="")
    _fill(page, t)


def _finish_tune(page, tune) -> None:
    page.gt.update(run=None, kind="", tune=None)
    r = tune.result or {}
    _clear_result(page)
    how = r.get("how")
    page.gt_progress.setText(tr(f"gt.tune.end.{how}") + (f" {tr(r['why'])}" if r.get("why") else ""))
    if how == "done":
        rows = [(tr("gt.r.value"), tune._label(r["value"])),
                (tr("gt.r.power"), _ba(r.get("power_before"), r.get("power_after"), " W")),
                (tr("gt.r.temp"), _ba(r.get("temp_before"), r.get("temp_after"), " °C")),
                (tr("gt.r.score"), _ba(r.get("score_before"), r.get("score_after"), ""))]
        for k, val in rows:
            page.gt_result.addWidget(label(f"{k}: {val}", "desc"))
        page.main.toast(tr("gt.tune.end.done"), "ok")
    else:
        page.main.toast(tr(f"gt.tune.end.{how}"), "warn" if how == "cancelled" else "bad")
    _fill(page, tune.t)


def _ba(a, b, unit: str) -> str:
    if a is None or b is None:
        return tr("hwc.na")
    return f"{a}{unit} → {b}{unit}"


def _clear_result(page) -> None:
    clear_layout(page.gt_result)
