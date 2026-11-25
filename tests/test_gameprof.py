"""Профілі ігор (Game Booster 2.0, gameprof.py): перевірка даних із settings.json, застосування й повернення через
журнал на фальшивій Windows, дві гри одночасно, аварія → наступний запуск і OptimaX-Rescue.cmd, історія FPS гри,
вікно «Профіль»."""
import json
import os
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, SCRIPTS, env_for, has_qt, skip, tail

DEMO_CODE = r"""
import json, sys, threading, time
sys.argv = ["x", "--dry-run", "--lang=en"]
import engine as E
E.IS_WIN = False  # демо-поведінка й на справжній Windows (CI): демо-бібліотека, нічого не змінюється
E.DRY_RUN = True
import features as F, gameprof as GP, library as LB
R = {}
# ── сміття в профілі: лише білі списки, ніколи realtime ──
junk = [None, 5, "x", [], {"power": "powercfg -h off", "gpu": 2, "prio": "realtime", "boost": "yes", "enabled": 0},
        {"power": "ultimate", "gpu": "saving", "prio": "above", "boost": True, "enabled": False, "evil": "cmd"}]
R["clean"] = [GP.clean(j) for j in junk]
R["prio_values"] = sorted(GP.PRIO_CLASS.values())
g = dict(key="c:\\games\\a", name="A", dir="C:\\Games\\A", exes=["a.exe"], main="C:\\Games\\A\\a.exe")
bad = [dict(g, dir="C:\\"), dict(g, dir="C:\\Windows\\System32"), dict(g, dir="relative\\x"),
       dict(g, exes=["..\\cmd.exe", "explorer.exe", "a.dll", 5]), dict(g, key=7), "junk",
       dict(g, key="k" * 500)]
R["sane_bad"] = [GP.sane_game(b) for b in bad]
R["sane_main"] = GP.sane_game(dict(g, main="C:\\Windows\\notepad.exe"))["main"]
R["sane_ok"] = GP.sane_game(g)
F.CFG["game_profiles"] = "junk"
R["profiles_junk"] = GP.profiles()

# ── режим гри: одночасний запуск із двох потоків — один стан; skip і схема, яку тримає профіль ──
F.CFG["booster"] = dict(F.CFG["booster"], services=True, kill=False, purge=False, timer=False, dnd=False, power=True)
logs = []
orig = E.active_scheme
def slow():
    time.sleep(0.2)
    return orig()
E.active_scheme = slow
ts = [threading.Thread(target=lambda: F.BOOSTER.start(logs.append)) for _ in range(2)]
[t.start() for t in ts]
[t.join() for t in ts]
E.active_scheme = orig
R["boost_once"] = sum(1 for x in logs if x == E.tr("g.boost_on"))
F.BOOSTER.stop(logs.append)
logs.clear()
F.BOOSTER.start(logs.append, skip=("power",))
R["skip_power"] = F.CFG["booster_state"]["plan"]
F.BOOSTER.stop(logs.append)

# ── демо: бібліотека, профіль, запуск і закриття гри ──
items = LB.refresh()
cs = next(x for x in items if x["exes"] == ["cs2.exe"])
GP.save(cs, {"power": "high", "prio": "high", "boost": True}, print)
GP.MANAGER.ready = True
procs = [(4242, "cs2.exe")]
GP._procs = lambda: procs + E.processes()
R["needs"] = GP.MANAGER.needs_sync()
r = GP.MANAGER.sync(print)
R["on"] = {"started": r["started"], "power": E.JOURNAL.has(GP.POWER_ID), "boost": F.BOOSTER.active,
           "keys": sorted(GP.MANAGER.active_keys()), "busy": GP.MANAGER.busy(), "holds": GP.MANAGER.holds_booster()}
# FPS: тест «до/після» з «Діагностики» і фоновий запис під час профілю
F.CFG["fps_tests"] = {cs["main"].lower(): {"before": {"avg": 200.0, "low1": 150.0, "ts": 100},
                                           "after": {"avg": 230.0, "low1": 170.0, "ts": 200}},
                      "c:\\other\\x.exe": {"before": {"avg": 1, "ts": 999}}}
LB.add_fps("cs2.exe", {"avg": 240.0, "low1": 180.0})
procs.clear()
r = GP.MANAGER.sync(print)
R["off"] = {"ended": r["ended"], "power": E.JOURNAL.has(GP.POWER_ID), "boost": F.BOOSTER.active,
            "state": GP.load_state(), "busy": GP.MANAGER.busy()}
info = GP.fps_info(cs)
R["fps"] = {"before": info["before"].get("avg"), "after": info["after"].get("avg"),
            "verdict": info["cmp"].get("verdict"), "rows": [(x["avg"], x["prof"]) for x in info["rows"]]}
F.CFG["fps_tests"] = {cs["main"].lower(): {"before": {"avg": "lots", "ts": "x"}, "after": "junk"}}
F.CFG["game_profile_hist"] = {cs["key"]: [["a", 1], [1, 2, 3]], 5: []}
R["fps_junk"] = GP.fps_info(cs)["before"]
R["summary"] = GP.summary(GP.profile(cs))
R["has"] = GP.has_profile(cs)
GP.remove(cs, print)
R["removed"] = GP.has_profile(cs)
print("RESULT " + json.dumps(R))
"""

UI_CODE = r"""
import json, sys
sys.argv = ["x", "--dry-run", "--lang=uk"]
import engine as E
E.IS_WIN = False  # демо-бібліотека й на справжній Windows
E.DRY_RUN = True
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
import features as F, gameprof as GP, library as LB, pages_gameprof as PG
items = LB.refresh()
cs = next(x for x in items if x["exes"] == ["cs2.exe"])
F.CFG["game_profiles"] = {cs["key"]: {"power": "ultimate", "prio": "realtime", "boost": True}}
F.CFG["fps_tests"] = {cs["main"].lower(): {"before": {"avg": 200.0, "low1": 150.0, "ts": 100}}}
d = PG.ProfileDialog(None, cs, {}, on_fps=lambda: None)
R = {"profile": d.profile(), "fps": [lb.text() for lb in d.fps_labels], "remove": d.btn_remove.isVisible() or
     not d.btn_remove.isHidden()}
seg, values = d.segs["prio"]
seg.select(3, True)
d.sw_on.setChecked(False)
R["changed"] = d.profile()
print("RESULT " + json.dumps(R, ensure_ascii=False))
"""


def _run(code: str, demo: str = "gaming") -> dict:
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env_for(demo), capture_output=True, timeout=300)
    out = (p.stdout + p.stderr).decode("utf-8", "replace")
    line = next((x for x in reversed(out.splitlines()) if x.startswith("RESULT ")), None)
    assert p.returncode == 0 and line, tail(out)
    return json.loads(line[7:])


_CACHE = {}


def demo() -> dict:
    if "d" not in _CACHE:
        _CACHE["d"] = _run(DEMO_CODE)
    return _CACHE["d"]


def test_untrusted_profile_data_is_whitelisted():
    r = demo()
    default = {"enabled": True, "power": "keep", "gpu": "keep", "prio": "keep", "boost": False}
    assert r["clean"][:5] == [default] * 5
    assert r["clean"][5] == {"enabled": False, "power": "ultimate", "gpu": "saving", "prio": "above", "boost": True}
    assert 0x100 not in r["prio_values"], "never realtime"
    assert r["profiles_junk"] == {}


def test_library_game_must_be_a_real_game_folder():
    r = demo()
    assert r["sane_bad"] == [{}] * 7, "drive root, Windows, relative dir, no valid exe, bad key — not a game"
    assert r["sane_main"] == "", "the main exe must live in the game folder"
    assert r["sane_ok"]["exes"] == ["a.exe"]


def test_booster_start_is_serialized_and_respects_profile():
    r = demo()
    assert r["boost_once"] == 1, "two threads must not both turn game mode on"
    assert r["skip_power"] is None


def test_demo_session_and_fps_history():
    r = demo()
    assert r["needs"] is True
    assert r["on"] == {"started": ["Counter-Strike 2"], "power": True, "boost": True,
                       "keys": [r["on"]["keys"][0]], "busy": True, "holds": True}
    assert r["off"] == {"ended": ["Counter-Strike 2"], "power": False, "boost": False, "state": None, "busy": False}
    assert r["fps"]["before"] == 200.0 and r["fps"]["after"] == 230.0
    assert r["fps"]["verdict"] in ("better", "same")
    assert r["fps"]["rows"] == [[240.0, True]], "a capture made while the profile was active is marked"
    assert r["fps_junk"] == {}, "junk FPS data is not shown as numbers"
    assert r["has"] is True and r["removed"] is False
    assert "High performance" in r["summary"]


def test_profile_dialog():
    if not has_qt():
        skip("PyQt6 is not installed")
    r = _run(UI_CODE)
    assert r["profile"] == {"enabled": True, "power": "ultimate", "gpu": "keep", "prio": "keep", "boost": True}
    assert any("200" in t for t in r["fps"])
    assert r["changed"]["prio"] == "high" and r["changed"]["enabled"] is False


# ── фальшива Windows: журнал, схема живлення, пріоритети, Rescue ──
def fake_report() -> dict:
    if IS_WIN:
        skip("fake Windows runs only outside Windows")
    if "f" not in _CACHE:
        out = tempfile.mkdtemp(prefix="oxgpf_")
        env = dict(os.environ, FAKE_HW="gaming", FAKE_TARGET=os.path.join(SCRIPTS, "gameprof_fake.py"),
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fake_windows.py"), "--out", out], cwd=ROOT,
                           env=env, capture_output=True, timeout=600)
        text = (p.stdout + p.stderr).decode("utf-8", "replace")
        path = os.path.join(out, "roundtrip.json")
        assert p.returncode == 0 and os.path.exists(path), tail(text)
        with open(path, encoding="utf-8") as f:
            _CACHE["f"] = json.load(f)
    return _CACHE["f"]


BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
HIGH = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


def test_fake_apply_exit_restore():
    r = fake_report()
    assert r["saved"]["pref"] == "SwapEffectUpgradeEnable=1;GpuPreference=2;", "only GpuPreference is changed"
    assert r["needs_before"] is True
    on = r["a_on"]
    assert on["res"]["started"] == ["Alpha"] and on["res"]["fail"] == 0
    assert on["plan"] == HIGH
    assert on["prio"] == [0x80, 0x20], "a same-named exe outside the game folder is not touched"
    assert on["boost"] is True and on["boost_plan"] is None, "game mode leaves the plan to the profile"
    assert "gprof:power" in on["ids"]
    assert on["state"]["prio"] == [[100, "alpha.exe", 0x20, 0x80]]
    assert on["needs_after"] is False
    assert r["b_off"]["plan"] == BALANCED and r["b_off"]["state"] is None
    assert "gprof:power" not in r["b_off"]["ids"]
    assert r["b_off"]["schemes"] == ["Balanced", "High performance"], "the Ultimate plan OptimaX created is removed"


def test_fake_two_games_overlap():
    r = fake_report()
    assert r["b_on"]["plan"] == "Ultimate Performance" and r["b_on"]["prio"] == 0x8000
    assert r["b_on"]["undo"][-1]["c"] == f"powercfg -setactive {BALANCED}", "the original plan is kept once"
    assert r["a_off"] == {"plan": "Ultimate Performance", "boost": False, "active": ["d:\\games\\beta"]}
    assert r["swap_mid"] == {"plan": "High performance", "prio_a": 0x80}
    assert r["swap_end"]["plan"] == BALANCED and r["swap_end"]["boost"] is False
    assert "gprof:power" not in r["swap_end"]["ids"]


def test_fake_booster_already_on():
    r = fake_report()
    assert r["with_booster"]["plan"] == r["booster_before"], "game mode's plan is not overwritten"
    assert "gprof:power" not in r["with_booster"]["ids"] and r["with_booster"]["ours"] is False
    assert r["with_booster_end"]["active"] is True, "a game mode the profile did not start is not stopped"
    assert r["with_booster_stop"] == BALANCED


def test_fake_honest_priority_failure():
    r = fake_report()
    assert r["prio_fail"] == {"fail": 1, "prio": 0x20}


def test_fake_crash_recovery():
    r = fake_report()
    assert r["crash_mid"]["plan"] == HIGH and r["crash_mid"]["prio"] == 0x80
    assert r["needs_recovery"] is True and r["sync_before_recover"] is False
    rec = r["recovered"]
    assert rec["res"]["did"] is True and rec["res"]["fail"] == 0
    assert rec["plan"] == BALANCED and rec["prio"] == 0x20 and rec["state"] is None
    assert "gprof:power" not in rec["ids"]
    assert r["reapplied"] == {"plan": HIGH, "prio": 0x80}
    assert r["closed"]["plan"] == BALANCED and r["closed"]["prio"] == 0x20 and r["closed"]["boost"] is False


def test_fake_rescue_cmd_restores_power_plan():
    r = fake_report()
    assert r["rescue_before"] == HIGH
    assert r["rescue_after"] == {"plan": BALANCED, "ids": []}


def test_fake_tampered_settings():
    r = fake_report()
    profs = r["tampered"]["profiles"]
    assert all(p["prio"] in ("keep", "normal", "above", "high") for p in profs.values())
    assert profs["c:\\games\\alpha"]["power"] == "keep"
    assert r["tampered"]["watched"] == [], "system folders, drive roots and bad exe names are never watched"
    assert r["tampered_state"] == [0x80, 0x80, 0x100, 0x80, 0x20, 0x80, 0x20], \
        "only a verified in-folder process with our above/high priority is restored; settings.json is ignored"


def test_fake_state_in_protected_folder():
    r = fake_report()
    assert r["state_file"] is True, "session state lives in %ProgramData%\\OptimaX\\state, not settings.json"


def test_fake_close_after_stop_all_restores_power():
    r = fake_report()
    assert r["closed"]["plan"] == BALANCED and "gprof:power" not in r["closed"]["ids"], \
        "E.stop_all() (closeEvent) must not block the profile's cleanup"


def test_fake_failed_power_undo_is_retried():
    r = fake_report()
    assert r["retry_fail"] == {"fail": 1, "held": True, "plan": HIGH, "needs_now": False}
    assert r["retry_due"] is True
    assert r["retry_ok"] == {"held": False, "plan": BALANCED, "needs": False}
    assert r["removed"]["pref"] == "SwapEffectUpgradeEnable=1;" and r["removed"]["ids"] == []
