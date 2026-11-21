"""7.1.1 (аудит, група measure): фризи в статистиці FPS, обірваний замір, кілька ланцюжків показу в CSV, хибні винні
в розумній оптимізації, відновлення сесії з settings.json, секунди DPC/ISR, покоління Intel, знімок реєстру."""
import json
import os
import random
import sys
import tempfile

from _util import IS_WIN, ROOT, skip

sys.path.insert(0, ROOT)
import abtest as AB  # noqa: E402
import baseline as BL  # noqa: E402
import engine as E  # noqa: E402
import fpstest as FT  # noqa: E402
import latencytest as LT  # noqa: E402
import perfdiag as PD  # noqa: E402


# ── E1: фризи ≥ 1 с лишаються в статистиці ──
def test_long_frames_count_as_freezes():
    smooth = [8.0] * 3000
    frozen = smooth[:1500] + [1500.0] + smooth[1500:] + [2500.0]
    a, b = FT.stats(smooth), FT.stats(frozen)
    assert b["frames"] == a["frames"] + 2
    assert b["stutters"] == a["stutters"] + 2
    assert b["avg"] < a["avg"] * 0.9 and b["low01"] < a["low01"] / 10 and b["low1"] < a["low1"]
    assert b["gaps"] == 0


def test_pauses_beyond_limit_are_dropped_but_counted():
    st = FT.stats([8.0] * 3000 + [60_000.0])
    assert st["frames"] == 3000 and st["gaps"] == 1 and st["stutters"] == 0


# ── E3: «Зупинити» — не результат ──
def test_cancelled_capture_is_not_a_result():
    if IS_WIN:
        skip("demo branch exists only outside Windows")
    tok = E.CancelToken()
    tok.set()
    E.bind_cancel(tok)
    try:
        try:
            FT.capture("cs2.exe", 5, lambda *_: None, None)
            raise AssertionError("cancelled capture returned a result")
        except RuntimeError as e:
            assert "⚠" in str(e) or str(e)
        try:
            FT.capture_runs("cs2.exe", 5, 3, lambda *_: None, None)
            raise AssertionError("cancelled series returned a result")
        except RuntimeError:
            pass
    finally:
        E.bind_cancel(None)


# ── E6: кілька процесів / ланцюжків показу ──
def test_parse_csv_keeps_main_swapchain():
    d = tempfile.mkdtemp(prefix="oxpm_")
    path = os.path.join(d, "c.csv")
    rows = ["Application,ProcessID,SwapChainAddress,MsBetweenPresents"]
    for i in range(1440):
        rows.append(f"game.exe,100,0xA,{1000 / 144:.3f}")
        if i % 5 == 0:
            rows.append(f"game.exe,100,0xB,{1000 / 30:.3f}")
            rows.append(f"game.exe,200,0xC,{1000 / 30:.3f}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    ft = FT.parse_csv(path)
    assert len(ft) == 1440 and round(FT.stats(ft)["avg"]) == 144


def test_parse_csv_without_ids_reads_all():
    d = tempfile.mkdtemp(prefix="oxpm_")
    path = os.path.join(d, "c.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("MsBetweenPresents\n" + "\n".join(["8.0"] * 50) + "\n")
    assert len(FT.parse_csv(path)) == 50


# ── E4: нешкідлива зміна рідше стає «винною» ──
def _session(seed, n_live=8, sa=0.02, sl=0.05):
    rnd = random.Random(seed)
    s = AB.Session([f"t{i}" for i in range(n_live)], [], [], mode="new")
    applied = set()
    for _ in range(400):
        a = s.next()
        if a["do"] == "done":
            break
        if a["do"] == "measure":
            s.feed({"avg": 200 * (1 + rnd.gauss(0, sa)), "low1": 150 * (1 + rnd.gauss(0, sl))})
        elif a["do"] == "apply":
            applied |= set(a["ids"])
            s.ok(applied=sorted(applied))
        elif a["do"] == "undo":
            applied -= set(a["ids"])
            s.ok()
        else:
            s.ok()
    return s.summary()


def test_zero_effect_tweaks_rarely_blamed():
    """Змін немає, FPS «гуляє» на 2%, 1% low — на 5%: до 7.1.1 винну знаходили в ~11% сесій, тепер ~4%."""
    n = 400
    blamed = sum(bool(_session(seed)["removed"]) for seed in range(n))
    assert blamed <= n * 0.07, blamed


def test_culprit_needs_two_checks():
    s = AB.Session(["a"], [], [], mode="new")
    s.stage, s.base, s.overall = "confirm", [{"avg": 100, "low1": 80}] * 3, "same"
    s.current, s.half = {"avg": 100, "low1": 80, "low01": 70}, ["a"]
    assert s.next()["label"] == "check"
    s.feed({"avg": 110, "low1": 88})
    assert not s.removed and s.stage == "confirm" and s.next()["label"] == "check"
    s.feed({"avg": 105, "low1": 84})  # другий замір теж кращий, медіана двох — +7.5% (поріг 3%)
    assert s.removed == ["a"]
    s2 = AB.Session(["a"], [], [], mode="new")
    s2.stage, s2.base, s2.overall = "confirm", [{"avg": 100, "low1": 80}] * 3, "same"
    s2.current, s2.half = {"avg": 100, "low1": 80, "low01": 70}, ["a"]
    s2.next()
    s2.feed({"avg": 110, "low1": 88})
    s2.next()
    s2.feed({"avg": 99, "low1": 80})  # другий замір не підтвердив: підозру знято
    assert not s2.removed and s2.stage == "restore"


# ── E5: сесія з settings.json ──
class _T:
    def __init__(self, group="perf", reboot=False, risky="", p="F", retired="", custom=False):
        self.group, self.reboot, self.risky, self.p = group, reboot, risky, p
        self.retired, self.custom = retired, custom
        self.reversible = True


CAT = {"ok1": _T(), "ok2": _T(), "boot1": _T(reboot=True), "priv": _T(group="privacy"),
       "vbs": _T(risky="security", p=""), "manual": _T(p=""), "old": _T(retired="dup")}


def test_from_dict_drops_forged_ids_and_pending():
    d = AB.Session(["ok1", "ok2"], ["boot1"], ["priv"]).to_dict()
    d.update(other=["priv", "vbs", "manual", "old", "nope"], pending={"do": "apply", "ids": ["vbs"], "why": "apply"},
             stage="apply", evil=1)
    s = AB.Session.from_dict(json.loads(json.dumps(d)), tweaks=CAT)
    assert s.other == ["priv"] and s.pending is None and not hasattr(s, "evil")
    assert s.next()["ids"] == ["priv", "ok1", "ok2", "boot1"]


def test_from_dict_keeps_valid_pending():
    d = AB.Session(["ok1", "ok2"], [], []).to_dict()
    d.update(stage="reapply", half=["ok1"], pending={"do": "apply", "ids": ["ok1"], "why": "reapply"})
    s = AB.Session.from_dict(json.loads(json.dumps(d)), tweaks=CAT)
    assert s.pending == {"do": "apply", "ids": ["ok1"], "why": "reapply"}


def test_from_dict_rejects_bad_types():
    d = AB.Session(["ok1"], [], []).to_dict()
    d.update(stage="pwn")
    try:
        AB.Session.from_dict(d, tweaks=CAT)
        raise AssertionError("bad stage accepted")
    except ValueError:
        pass
    d.update(stage="base", live="ok1", rounds="x", pending={"do": "apply", "ids": "ok1"})
    s = AB.Session.from_dict(d, tweaks=CAT)
    assert s.live == [] and s.rounds == 0 and s.pending is None


# ── E8: запізнілі події ETW не створюють фантомних секунд ──
def test_exec_stats_seconds_only_forward():
    s = LT.ExecStats(1_000_000)  # 1 тік = 1 мкс
    for sec in (0, 1, 0, 1, 0, 2):
        t = sec * 1_000_000 + 100
        s.add(False, t, t - 50, 0x1000, 0)
    s.finish()
    assert len(s.series_max) == 3 and len(s.series_pct) == 3


# ── E9: покоління Intel ──
def test_intel_generation():
    want = {"i5-1135G7": (11, "locked_likely"), "i7-1255U": (12, "locked_likely"), "i7-1360P": (13, "locked_likely"),
            "i3-1005G1": (10, "locked_likely"), "i7-10750H": (10, "locked_likely"), "i7-8565U": (8, "possible"),
            "i9-13900K": (13, "bios")}
    for m, (gen, state) in want.items():
        f = PD.cpu_family(f"Intel(R) Core(TM) {m} CPU @ 2.40GHz")
        assert (f["gen"], f["state"]) == (gen, state), (m, f)


# ── E11: знімок реєстру ──
def test_baseline_base_validation():
    types = BL.reg_types()
    dword = next(k for k, v in types.items() if v == {4})
    assert BL.base_ok(dword, [4, 1], types) and BL.base_ok(dword, None, types)
    assert not BL.base_ok(dword, [1, "cmd.exe /c calc"], types)  # тип, яким каталог цей параметр не пише
    assert not BL.base_ok(dword, [4, "1; calc"], types)
    assert not BL.base_ok(dword, [4, 2 ** 40], types)
    assert not BL.base_ok("HKLM\\Nope|X", [4, 1], types)

