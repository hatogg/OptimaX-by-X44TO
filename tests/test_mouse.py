"""«Миша» (Hardware Center): статистика частоти опитування, перерахунок чутливості через см/360°, розбір налаштувань
вказівника з реєстру і рекомендація «швидкість 10 + без прискорення» — лише через твік із журналом відкату."""
import json
import random
import subprocess
import sys

from _util import ROOT, env_for, tail

sys.path.insert(0, ROOT)


def _mt():
    import mousetools as MT
    return MT


# ───────────── частота опитування ─────────────
def test_poll_rate_of_standard_mice():
    MT = _mt()
    for rate in MT.STANDARD[:5]:  # 125–2000 Гц: тремтіння 4 % і дві паузи
        r = MT.poll_stats(MT.demo_stream(rate, 6.0, seed=rate))
        assert r["ok"] and r["nearest"] == rate, (rate, r)
        assert abs(r["median_hz"] - rate) <= rate * 0.03 and abs(r["avg_hz"] - rate) <= rate * 0.03, r
        assert r["stability"] >= 90 and not r["low"], r
        assert r["idle"] == 2, "both pauses are dropped, not averaged in"


def test_idle_gaps_do_not_lower_the_rate():
    MT = _mt()
    ts, t = [], 0.0
    for _burst in range(5):  # 5 ривків по 0.4 с на 1000 Гц, між ними миша стоїть по секунді
        for _ in range(400):
            ts.append(t)
            t += 0.001
        t += 1.0
    r = MT.poll_stats(ts)
    assert r["ok"] and r["nearest"] == 1000 and 990 <= r["median_hz"] <= 1010, r
    assert r["idle"] == 4 and abs(r["active_s"] - 5 * 0.399) < 0.01, r


def test_too_few_events_is_said_honestly():
    MT = _mt()
    assert MT.poll_stats([])["ok"] is False
    short = MT.poll_stats([i * 0.001 for i in range(120)])  # 0.12 с руху — замало
    assert short == {"ok": False, "reason": "few", "events": 120, "active_s": short["active_s"], "idle": 0}
    sparse = MT.poll_stats([i * 0.05 for i in range(500)])  # кожна подія — після «паузи»: руху немає зовсім
    assert not sparse["ok"] and sparse["active_s"] == 0 and sparse["idle"] == 499


def test_unstable_and_slow_movement_are_flagged():
    MT = _mt()
    rnd = random.Random(3)
    ts, t = [], 0.0
    for _ in range(4000):  # 1000 Гц, що «плаває» між 500 і 1000 вікнами по 0.1 с
        ts.append(t)
        t += 0.001 if int(t * 10) % 2 else 0.002 * (1 + rnd.uniform(-0.01, 0.01))
    r = MT.poll_stats(ts)
    assert r["ok"] and r["stability"] <= 60, r
    slow = MT.poll_stats([i / 700 for i in range(3000)])  # 700 Гц: найближче 500/1000 за відношенням — 500
    assert slow["nearest"] == 500 and not slow["low"]
    low = MT.poll_stats([i / 750 for i in range(3000)])
    assert low["nearest"] == 1000 and low["low"], "below 80 % of the standard — move faster"


def test_nearest_standard():
    MT = _mt()
    assert [MT.nearest_standard(x) for x in (0, 120, 170, 260, 990, 1500, 3000, 7900, 20000)] == \
        [0, 125, 125, 250, 1000, 2000, 4000, 8000, 8000]


# ───────────── см/360° ─────────────
def test_cm360_math_and_round_trip():
    MT = _mt()
    # 800 DPI, CS2 1.0: 360 / (0.022 · 1 · 800) дюйма = 20.4545… дюйма = 51.95 см
    assert abs(MT.cm360(800, 1.0, 0.022) - 51.95454) < 1e-4
    assert MT.cm360(0, 1, 0.022) == 0 and MT.cm360(800, 0, 0.022) == 0
    r = MT.convert(800, 2.0, "cs2", "valorant")
    assert abs(r["sens"] - 2.0 * 0.022 / 0.07) < 1e-9 and r["edpi"] == 1600
    assert abs(MT.convert(800, 1.0, "cs2", "ow2")["sens"] - 0.022 / 0.0066) < 1e-9
    for src in MT.GAMES:
        for dst in MT.GAMES:
            there = MT.convert(1600, 0.85, src, dst)
            back = MT.convert(1600, there["sens"], dst, src)
            assert abs(back["sens"] - 0.85) < 1e-9 and abs(back["cm360"] - there["cm360"]) < 1e-9, (src, dst)
    other_dpi = MT.convert(400, 2.0, "cs2", "cs2", dst_dpi=800)
    assert abs(other_dpi["sens"] - 1.0) < 1e-9 and abs(other_dpi["dst_edpi"] - 800) < 1e-9
    assert abs(MT.sens_for_cm(800, MT.cm360(800, 0.4, 0.07), 0.07) - 0.4) < 1e-12


def test_only_known_yaw_constants():
    MT = _mt()
    yaws = {k: y for k, (_n, y) in MT.GAMES.items()}
    assert yaws == {"cs2": 0.022, "csgo": 0.022, "apex": 0.022, "tf2": 0.022, "quake": 0.022, "valorant": 0.07,
                    "ow2": 0.0066}


# ───────────── налаштування Windows ─────────────
def test_registry_parsing():
    MT = _mt()
    d = MT.parse_settings({"MouseSensitivity": "10", "MouseSpeed": "1", "MouseThreshold1": "6",
                           "MouseThreshold2": "10"})  # Windows за замовчуванням: «Підвищена точність» увімкнена
    assert (d["speed"], d["notch"], d["mult"], d["accel"], d["t1"], d["t2"]) == (10, 6, 1.0, True, 6, 10)
    assert d["speed_ok"] and not d["accel_ok"] and not d["ok"]
    ok = MT.parse_settings({"MouseSensitivity": " 10 ", "MouseSpeed": "0", "MouseThreshold1": "0",
                            "MouseThreshold2": "0"})
    assert ok["ok"] and ok["accel"] is False
    assert MT.parse_settings({"MouseSensitivity": 14, "MouseSpeed": 2})["mult"] == 2.0
    bad = MT.parse_settings({"MouseSensitivity": "abc", "MouseSpeed": None})
    assert bad["speed"] is None and bad["accel"] is None and not bad["ok"]
    assert MT.parse_settings({"MouseSensitivity": "25"})["speed"] is None, "outside 1–20 is not a pointer speed"
    assert [MT.speed_multiplier(v) for v in (1, 2, 3, 6, 10, 11, 20)] == [1 / 32, 1 / 16, 1 / 8, 0.5, 1.0, 1.25, 3.5]
    assert [MT.notch(v) for v in (1, 2, 10, 20)] == [1, 2, 6, 11]


def test_recommendation_is_the_catalog_tweak_with_undo():
    """Швидкість 10 і вимкнене прискорення записує лише disable_mouse_accel: повні операції з відкатом, застосування
    без виходу з системи, жоден інший твік не володіє цими значеннями (MouseDataQueueSize — ніколи)."""
    import engine as E
    MT = _mt()
    t = E.BY_ID[MT.ACCEL_TWEAK]
    regs = {(op[1], op[2]): op[3] for op in t.ops if op[0] == "reg"}
    assert regs == {(MT.MOUSE_KEY, "MouseSpeed"): "0", (MT.MOUSE_KEY, "MouseThreshold1"): "0",
                    (MT.MOUSE_KEY, "MouseThreshold2"): "0", (MT.MOUSE_KEY, "MouseSensitivity"): str(MT.REC_SPEED)}
    assert ("live", "mouse") in t.ops, "applied right away (SystemParametersInfo), like the rollback"
    others = [x.id for x in E.TWEAKS if x.id != t.id and any(op[0] == "reg" and op[1] == MT.MOUSE_KEY for op in x.ops)]
    assert not others, others
    assert not any("mousedataqueuesize" in repr(x.ops).lower() for x in E.TWEAKS)


CODE = r"""
import json, sys
sys.argv = ["x", "--dry-run", "--lang=en"]
import engine as E, mousetools as MT
t = E.BY_ID[MT.ACCEL_TWEAK]
logs = []
R = {"before": MT.read_settings()["ok"]}
R["apply"] = E.apply_tweaks([t], logs.append, header=False)
rec = E.JOURNAL.get(t.id) or {}
R["undo_names"] = sorted(u.get("n") for u in rec.get("undo") or [] if u.get("t") == "reg")
R["valid"] = all(E.valid_undo(u) for u in rec.get("undo") or [])
R["after"] = MT.read_settings()["ok"]
R["undone"] = E.undo_or_default(t, logs.append)
R["journal_after"] = E.JOURNAL.has(t.id)
R["final"] = MT.read_settings()["ok"]
print("RESULT " + json.dumps(R, default=str))
"""


def test_apply_and_roll_back_through_the_journal():
    p = subprocess.run([sys.executable, "-c", CODE], cwd=ROOT, env=env_for("old"), capture_output=True, timeout=180)
    out = (p.stdout + p.stderr).decode("utf-8", "replace")
    line = next((ln for ln in out.splitlines() if ln.startswith("RESULT ")), None)
    assert p.returncode == 0 and line, tail(out)
    r = json.loads(line[7:])
    assert r["before"] is False and r["apply"]["ok"] == 1 and not r["apply"].get("fail"), r
    assert r["undo_names"] == ["MouseSensitivity", "MouseSpeed", "MouseThreshold1", "MouseThreshold2"], r
    assert r["valid"] and r["after"] is True, r
    assert r["undone"]["undone"] == 1 and not r["journal_after"] and r["final"] is False, r
