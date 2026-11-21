"""Кулери й андервольт відеокарти (gputune.py) на демо-карті: крива й запобіжники, сторож вентиляторів, заводські
значення й журнал, збій після зміни, автопідбір NVIDIA й AMD. Справжні NVML / ADLX тут не викликаються — на машині
без карт NVIDIA / AMD перевіряється лише чесне «не знайдено» без збою."""
import ctypes
import os
import subprocess
import sys
import tempfile
import time

from _util import ROOT, IS_WIN, skip

sys.path.insert(0, ROOT)
import engine as E  # noqa: E402
import gputune as GT  # noqa: E402


class Cfg:
    def __init__(self):
        self.data = {"gpu_tune": {"profile": None, "orig": {}, "active": False, "on_start": False}}

    def __getitem__(self, k):
        return self.data.get(k)

    def __setitem__(self, k, v):
        self.data[k] = v


class _Env:
    """Тимчасовий журнал замість справжнього й увімкнений запис (не режим перегляду) — на час тесту."""

    def __enter__(self):
        self.j, self.dry = E.JOURNAL, E.DRY_RUN
        E.JOURNAL = E.Journal(os.path.join(tempfile.mkdtemp(prefix="oxgt_"), "back.json"))
        E.DRY_RUN = False
        GT.SESSION.tuner, GT.SESSION.fans = None, None
        return E.JOURNAL

    def __exit__(self, *a):
        E.JOURNAL, E.DRY_RUN = self.j, self.dry
        GT.SESSION.tuner, GT.SESSION.fans = None, None


# ── крива ──
def test_curve_validation_and_interpolation():
    assert GT.curve_normalize([(70, 60), (40, 30)]) == [(40, 30), (70, 60)]
    for bad in ([(40, 30)], [(40, 30), (40, 50)], [(40, 60), (70, 30)], [(10, 30), (70, 60)], [(40, 30), (70, 120)],
                [("x", 1), (50, 2)]):
        try:
            GT.curve_normalize(bad)
            assert False, bad
        except ValueError:
            pass
    pts = [(40, 30), (60, 50), (80, 90)]
    assert GT.curve_speed(pts, 30) == 30 and GT.curve_speed(pts, 50) == 40 and GT.curve_speed(pts, 95) == 90


def test_fan_curve_guards_and_hysteresis():
    c = GT.FanCurve([(40, 10), (60, 40), (80, 70)], lo=0, hi=100)
    assert c.update(35) == GT.FAN_MIN_SAFE            # нижче FAN_MIN_SAFE крива не опускається
    assert c.update(60) == 40
    assert c.update(59) is None                        # дрібна зміна не надсилається
    assert c.update(58.5) is None                      # охололо менше ніж на FAN_HYST — тримаємо швидкість
    assert c.update(55) == 32                          # охололо на 5 °C — знижуємо (32.5 % -> 32)
    assert c.update(GT.FAN_FORCE_TEMP) == 100          # від FAN_FORCE_TEMP — на повну, хоч крива каже 70
    assert c.update(None) is None or c.speed == 100    # датчик мовчить — максимум
    c2 = GT.FanCurve([(40, 50), (70, 80)], lo=0, hi=90)
    assert c2.update(GT.FAN_FORCE_TEMP + 3) == 90      # межа драйвера сильніша за 100 %


def test_resample_for_amd_driver_points():
    temps = GT.spread_temps(25, 95, 5)
    assert temps[0] == 40 and temps[-1] == GT.FAN_FORCE_TEMP and temps == sorted(temps)
    pts = GT.resample([(40, 10), (60, 40), (80, 60)], temps)
    assert len(pts) == 5 and pts[-1][1] == 100 and all(s >= GT.FAN_MIN_SAFE for _, s in pts)
    assert all(b[1] >= a[1] for a, b in zip(pts, pts[1:]))


# ── вентилятори NVIDIA: крива в програмі ──
def test_fan_controller_steps_and_returns_fans_on_errors():
    t = GT.DemoTuner("nvidia")
    t.temp, t.load = 70.0, 0.8
    fc = GT.FanController(t, curve=GT.CURVE_PRESETS["balanced"], watchdog=False)
    fc.step()
    assert t.calls and t.calls[-1][0] == "fan" and t.fan_manual
    fixed = GT.FanController(t, fixed=10, watchdog=False)
    assert fixed.fixed == GT.FAN_MIN_SAFE              # фіксована швидкість теж не нижче FAN_MIN_SAFE
    t.temp = GT.FAN_FORCE_TEMP + 5
    t.read = lambda: dict(temp=GT.FAN_FORCE_TEMP + 5)  # перегрів — 100 % і у фіксованому режимі
    fixed.step()
    assert t.calls[-1] == ("fan", 100)

    class Broken(GT.DemoTuner):
        def fan_set(self, pct):
            self.calls.append(("fan_fail", pct))
            return False
    b = Broken("nvidia")
    old = GT.FAN_TICK
    GT.FAN_TICK = 0.01
    try:
        fc = GT.FanController(b, fixed=50, watchdog=False)
        fc.start()
        fc.thread.join(3)
    finally:
        GT.FAN_TICK = old
    assert not fc.running and ("fan_auto",) in b.calls, b.calls   # FAN_FAILS помилок — вентилятори драйверу
    assert fc.error


# ── заводські значення, журнал, збій ──
def test_profile_apply_restore_and_journal_entry():
    with _Env() as j:
        cfg, t = Cfg(), GT.DemoTuner("nvidia")
        res = GT.apply_profile(cfg, t, dict(power=180, clock=2400, offset=120))
        assert res == {"power": True, "clock": True, "offset": True}
        assert t.state == dict(power=180, offset=120, clock=2400)
        st = GT.state(cfg)
        assert st["active"] and st["pending"]["what"] == "apply" and st["orig"][t.key]["power"] == 200
        tid = GT.journal_id(t)
        rec = j.get(tid)["undo"]
        assert rec[0]["t"] == "ps" and "--gpu-reset" in rec[0]["c"] and "--vendor=nvidia" in rec[0]["c"]
        assert E.valid_undo(rec[0])
        GT.apply_profile(cfg, t, dict(power=150))               # повторна зміна не перезаписує заводські
        assert GT.state(cfg)["orig"][t.key]["power"] == 200
        assert GT.restore_original(cfg, t)
        assert t.state == dict(power=200, offset=0, clock=None) and not j.has(tid)
        st = GT.state(cfg)
        assert not st["active"] and "pending" not in st and t.key not in st["orig"]


def test_crash_after_change_restores_factory_on_next_start():
    with _Env():
        cfg, t = Cfg(), GT.DemoTuner("nvidia")
        GT.apply_profile(cfg, t, dict(offset=150, clock=2600))
        st = GT.state(cfg)
        st.update(on_start=True, profile=dict(st["profile"], verified=1))
        GT.save_state(cfg, st)
        GT.SESSION.tuner = t                                   # «наступний запуск» бачить ту саму карту
        out = GT.startup(cfg)
        assert out["crashed"] and not out["applied"]
        assert t.state["offset"] == 0 and not GT.state(cfg)["on_start"]


def test_start_applies_only_a_verified_profile_and_pending_clears_after_a_while():
    with _Env():
        cfg, t = Cfg(), GT.DemoTuner("amd")
        GT.save_state(cfg, dict(profile=dict(gpu=t.key, voltage=1100), on_start=True, orig={}, enabled=True))
        GT.SESSION.tuner = t
        assert not GT.startup(cfg)["applied"]                  # не перевірений — не застосовуємо
        GT.save_state(cfg, dict(profile=dict(gpu=t.key, voltage=1100, verified=1), on_start=True, orig={},
                                enabled=True))
        assert GT.startup(cfg)["applied"] and t.state["voltage"] == 1100
        st = GT.state(cfg)
        assert st["pending"]
        st["pending"]["ts"] -= GT.CONFIRM_SECONDS + 1
        st["tuning"] = {"key": t.key}
        GT.save_state(cfg, st)
        assert not GT.confirm_stable(cfg)                      # поки йде підбір — позначка лишається
        st.pop("tuning")
        GT.save_state(cfg, st)
        assert GT.confirm_stable(cfg) and "pending" not in GT.state(cfg)


def test_test_mode_section_is_off_until_turned_on():
    import features as F
    assert F.DEFAULTS["gpu_tune"]["enabled"] is False and GT.TEST_MODE
    with _Env():
        cfg, t = Cfg(), GT.DemoTuner("nvidia")
        assert not GT.enabled(cfg)
        GT.save_state(cfg, dict(profile=dict(gpu=t.key, offset=90, verified=1), on_start=True, orig={}))
        GT.SESSION.tuner = t
        out = GT.startup(cfg)                                   # вимкнено — нічого не застосовуємо під час запуску
        assert not out["applied"] and out["tuner"] is None and t.state["offset"] == 0
        st = GT.state(cfg)
        st["enabled"] = True
        GT.save_state(cfg, st)
        assert GT.enabled(cfg) and GT.startup(cfg)["applied"] and t.state["offset"] == 90


def test_rollback_from_journal_clears_active_state():
    with _Env() as j:
        cfg, t = Cfg(), GT.DemoTuner("nvidia")
        GT.apply_profile(cfg, t, dict(power=190))
        assert not GT.sync_with_journal(cfg)                   # запис є — нічого не міняємо
        j.pop(GT.journal_id(t))                                # «відкат усього» / Rescue
        assert GT.sync_with_journal(cfg)
        st = GT.state(cfg)
        assert not st["active"] and not st["on_start"] and st["orig"] == {}


def test_amd_clock_none_never_raises_to_the_driver_maximum():
    t = GT.DemoTuner("amd")
    t.clock_cap(None)
    assert t.state["maxfreq"] == 2430                          # верх діапазону (2600) — це розгін, а не «заводське»


# ── автопідбір ──
class FakeRun:
    def __init__(self, tuner, seconds, polls=2):
        self.ok = tuner.stable()
        self.left = polls
        self.stopped = False
        tuner.load = 1.0

    def poll(self):
        if self.stopped:
            return {"state": "cancelled"}
        self.left -= 1
        if self.left > 0:
            return {"state": "running"}
        return {"state": "done", "result": {"verdict": "stable" if self.ok else "errors",
                                            "errors": 0 if self.ok else 3, "score": 1000}}

    def stop(self):
        self.stopped = True

    def cleanup(self):
        pass


def _tune(t, cfg, stop_after=None):
    runs = []

    def run_fn(seconds):
        r = FakeRun(t, seconds)
        runs.append(r)
        return r
    tune = GT.AutoTune(cfg, t, run_fn, step_s=1, verify_s=1)
    tune.start()
    for i in range(400):
        if stop_after is not None and i == stop_after:
            tune.stop()
        if tune.tick() in ("done", "failed", "cancelled"):
            break
    return tune, runs


def test_autotune_nvidia_finds_offset_with_margin():
    with _Env():
        cfg, t = Cfg(), GT.DemoTuner("nvidia", unstable_at=165)
        tune, runs = _tune(t, cfg)
        assert tune.phase == "done", tune.result
        # 30…150 стабільно, 180 — помилка, перевірка на 2 кроки нижче: 120
        assert tune.result["value"] == 120 and t.state["offset"] == 120 and t.state["clock"] == 2610
        prof = GT.state(cfg)["profile"]
        assert prof["verified"] and prof["offset"] == 120 and "pending" not in GT.state(cfg)
        assert "tuning" not in GT.state(cfg)
        assert tune.result["power_before"] and tune.result["power_after"]


def test_autotune_amd_lowers_voltage():
    with _Env():
        cfg, t = Cfg(), GT.DemoTuner("amd", unstable_at=55)
        tune, _ = _tune(t, cfg)
        assert tune.phase == "done" and tune.result["value"] == 40 and t.state["voltage"] == 1110, tune.result


def test_autotune_failures_restore_factory():
    with _Env():
        cfg, t = Cfg(), GT.DemoTuner("nvidia", unstable_at=20)      # помилка вже на першому кроці
        tune, _ = _tune(t, cfg)
        assert tune.phase == "failed" and tune.result["why"] == "gt.tune.no_margin"
        assert t.state["offset"] == 0 and not GT.state(cfg)["active"]
    with _Env():
        cfg, t = Cfg(), GT.DemoTuner("nvidia", unstable_at=-1)      # нестабільна вже заводська
        tune, _ = _tune(t, cfg)
        assert tune.phase == "failed" and tune.result["why"] == "gt.tune.base_bad"
    with _Env():
        cfg, t = Cfg(), GT.DemoTuner("nvidia", unstable_at=900)
        tune, _ = _tune(t, cfg, stop_after=5)
        assert tune.phase == "cancelled" and t.state["offset"] == 0 and "pending" not in GT.state(cfg)


def test_strings_for_every_state_exist():
    import i18n
    keys = ["gt.part." + k for k in ("fan", "power", "clock", "offset", "voltage")]
    keys += ["gt.phase." + p for p in ("idle", "baseline", "step", "verify", "done", "failed", "cancelled")]
    keys += ["gt.tune.end." + h for h in ("done", "failed", "cancelled")]
    keys += ["gt.fan." + m for m in ("auto", "curve", "fixed")] + ["gt.preset." + p for p in GT.CURVE_PRESETS]
    keys += sorted({v for t in (GT.DemoTuner("nvidia"), GT.DemoTuner("amd")) for v in t.why.values()})
    keys += ["gt.why." + w for w in ("unsupported", "admin", "old_driver", "error", "no_fans", "locked", "amd_old",
                                     "amd_auto", "no_gpu")]
    assert [k for k in keys if k not in i18n.STR] == []


# ── ADLX: виклик методу за номером у таблиці ──
def test_vtable_call_passes_object_and_arguments():
    if not IS_WIN:
        skip("WINFUNCTYPE — лише Windows")
    seen = []
    proto = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int)
    fns = [proto(lambda this, x, i=i: seen.append((i, x)) or i * 10 + x) for i in range(4)]
    vtbl = (ctypes.c_void_p * 4)(*[ctypes.cast(f, ctypes.c_void_p) for f in fns])
    obj = ctypes.c_void_p(ctypes.addressof(vtbl))
    holder = ctypes.pointer(obj)                                    # об'єкт: перше поле — вказівник на таблицю
    ptr = ctypes.cast(holder, ctypes.c_void_p)
    assert GT._vcall(ptr, 2, ctypes.c_int, [ctypes.c_int], 7) == 27 and seen == [(2, 7)]


# ── справжня машина: без карт NVIDIA / AMD — чесне «не знайдено», без зависань ──
def test_no_vendor_gpu_is_reported_honestly():
    if not IS_WIN:
        skip("справжні NVML / ADLX — лише Windows")
    t = GT.open_tuner("")
    try:
        if t.ok():
            skip(f"на цій машині є {t.name} — перевіряє тестер")
        assert t.why and all(t.why[k] == "gt.why.no_gpu" for k in ("fan", "power", "clock"))
        assert [k for k, have, _ in GT.describe_caps(t) if have] == []
    finally:
        t.close()


def test_watchdog_and_reset_child_do_not_hang_without_a_card():
    if not IS_WIN:
        skip("лише Windows")
    t = GT.open_tuner("")
    has = t.ok()
    t.close()
    if has:
        skip("є керована відеокарта — сторож змінив би режим її вентиляторів")
    e = dict(os.environ, APPDATA=tempfile.mkdtemp(prefix="oxt_"))
    t0 = time.time()
    p = subprocess.run([sys.executable, os.path.join(ROOT, "optimizer.py"), "--gpu-watchdog", "--parent=4000000001"],
                       cwd=ROOT, env=e, capture_output=True, timeout=60)
    assert p.returncode == 1 and time.time() - t0 < 30, p.stdout + p.stderr     # батька немає — одразу, карти немає
    p = subprocess.run([sys.executable, os.path.join(ROOT, "optimizer.py"), "--gpu-reset", "--vendor=nvidia",
                        "--index=0"], cwd=ROOT, env=e, capture_output=True, timeout=60)
    assert p.returncode == 2, p.stdout + p.stderr
