"""Профілі ігор (gameprof.py) на фальшивій Windows: гра запустилася → схема живлення, пріоритет, режим гри й
налаштування «Графіка» через журнал; гра закрилася → усе як було. Дві ігри одночасно (різні схеми, закриваються в
різному порядку), чужий процес з тим самим ім'ям exe, аварія посеред гри → наступний запуск і OptimaX-Rescue.cmd,
підмінений settings.json.

Запуск: FAKE_TARGET=tests/scripts/gameprof_fake.py python tests/scripts/fake_windows.py --out DIR"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import gameprof as GP  # noqa: E402
import rescue as RS  # noqa: E402

import types  # noqa: E402

FW = types.SimpleNamespace(**E.run.__globals__)  # стан фальшивої Windows (E.run підмінено її fake_run)
assert "PW" in E.run.__globals__, "run me via tests/scripts/fake_windows.py"

R = {}
LOG = []
log = LOG.append
BALANCED = FW.BALANCED
HIGH = E.HIGH_PERF

# ── «система»: процеси, їхні шляхи й пріоритети ──
PROCS = {}  # pid -> (ім'я, шлях)
PRIO = {}


def procs():
    return [(pid, n) for pid, (n, _p) in PROCS.items()]


GP._procs = procs
E.processes = procs  # режим гри теж дивиться на процеси
GP._path = lambda pid: (PROCS.get(pid) or (None, None))[1]
GP._get_prio = lambda pid: PRIO.get(pid, 0) if pid in PROCS else 0
SET_FAIL = set()


def set_prio(pid, cls):
    if pid not in PROCS or pid in SET_FAIL:
        return False
    PRIO[pid] = cls
    return True


GP._set_prio = set_prio


def start(pid, name, path, prio=0x20):
    PROCS[pid] = (name, path)
    PRIO[pid] = prio


def stop(pid):
    PROCS.pop(pid, None)


def lib_game(name, folder, exe):
    return dict(key=folder.lower(), name=name, store="mine", dir=folder, exes=[exe.lower()],
                main=folder + "\\bin\\" + exe, appid="", epic="", ubi="", risk="", anticheat="")


A = lib_game("Alpha", r"C:\Games\Alpha", "alpha.exe")
B = lib_game("Beta", r"D:\Games\Beta", "beta.exe")
F.CFG["library"] = {"ts": 9e12, "games": [A, B]}
F.CFG["booster"] = dict(F.CFG["booster"], services=False, kill=False, purge=False, timer=False, dnd=False,
                        power=True, auto=False)
DX = E.DX_PREF


def pref(path):
    v = E.reg_get(DX, path)
    return v[1] if v else None


def plan():
    return FW.PW["active"]


def ids():
    return sorted(t for t in E.JOURNAL.newest_first() if t.startswith("gprof:"))


GP.MANAGER.ready = True

# ── 1. профіль: «Графіка» одразу через журнал; валідація даних ──
FW.reg_set(DX, A["main"], 1, "SwapEffectUpgradeEnable=1;")  # чужий параметр у тому самому рядку лишається
GP.save(A, {"power": "high", "gpu": "high", "prio": "high", "boost": True}, log)
R["saved"] = {"pref": pref(A["main"]), "ids": ids(), "cfg": F.CFG["game_profiles"]}

# ── 2. гра A: запуск → застосовано; чужий alpha.exe з іншої папки не чіпаємо ──
start(100, "alpha.exe", A["main"])
start(101, "alpha.exe", r"C:\Users\x\Downloads\alpha.exe")
R["needs_before"] = GP.MANAGER.needs_sync()
r1 = GP.MANAGER.sync(log)
R["a_on"] = {"res": r1, "plan": plan(), "prio": [PRIO[100], PRIO[101]], "boost": F.BOOSTER.active,
             "boost_plan": (F.CFG["booster_state"] or {}).get("plan"), "ids": ids(),
             "state": F.CFG["game_profile_state"], "needs_after": GP.MANAGER.needs_sync()}

# ── 3. гра B (Ultimate) поверх A: схема — найсильніша, початкова лишається тією самою ──
GP.save(B, {"power": "ultimate", "prio": "above"}, log)
start(200, "beta.exe", B["main"])
GP.MANAGER.sync(log)
R["b_on"] = {"plan": FW.SCHEMES.get(plan()), "prio": PRIO[200], "undo": E.JOURNAL.get(GP.POWER_ID)["undo"]}
# A закривається першою: схема лишається Ultimate (B ще грає), режим гри A — вимикається (B його не просив)
stop(100)
GP.MANAGER.sync(log)
R["a_off"] = {"plan": FW.SCHEMES.get(plan()), "boost": F.BOOSTER.active, "active": sorted(GP.MANAGER.active_keys())}
stop(200)
GP.MANAGER.sync(log)
R["b_off"] = {"plan": plan(), "ids": ids(), "state": F.CFG["game_profile_state"],
              "schemes": sorted(FW.SCHEMES.values()), "hist": sorted(GP.hist_all())}

# ── 4. навпаки: B першою, закривається першою — схема переходить на потрібну A, а потім — початкова ──
start(201, "beta.exe", B["main"])
GP.MANAGER.sync(log)
start(102, "alpha.exe", A["main"])
GP.MANAGER.sync(log)
stop(201)
GP.MANAGER.sync(log)
R["swap_mid"] = {"plan": FW.SCHEMES.get(plan()), "prio_a": PRIO[102]}
stop(102)
GP.MANAGER.sync(log)
R["swap_end"] = {"plan": plan(), "ids": ids(), "boost": F.BOOSTER.active}

# ── 5. режим гри вже ввімкнений (своя схема): профіль схему не чіпає, режим гри не вимикає ──
F.BOOSTER.start(log)
R["booster_before"] = plan()
start(103, "alpha.exe", A["main"])
GP.MANAGER.sync(log)
R["with_booster"] = {"plan": plan(), "ids": ids(), "ours": GP.MANAGER.booster_ours}
stop(103)
GP.MANAGER.sync(log)
R["with_booster_end"] = {"active": F.BOOSTER.active}
F.BOOSTER.stop(log)
R["with_booster_stop"] = plan()

# ── 6. пріоритет не вдався (античит) — чесно «fail» ──
SET_FAIL.add(104)
start(104, "alpha.exe", A["main"])
r = GP.MANAGER.sync(log)
R["prio_fail"] = {"fail": r["fail"], "prio": PRIO[104]}
stop(104)
GP.MANAGER.sync(log)
SET_FAIL.clear()

# ── 7. аварія посеред гри → наступний запуск ──
start(105, "alpha.exe", A["main"])
GP.MANAGER.sync(log)
crash_state = json.loads(json.dumps(F.CFG["game_profile_state"]))
R["crash_mid"] = {"plan": plan(), "prio": PRIO[105], "state_prio": crash_state.get("prio")}
GP.MANAGER = GP.Manager()  # новий процес OptimaX: пам'яті про сесію немає
F.BOOSTER.stop(log)  # режим гри відновлюється своїм механізмом (optimizer: booster_state)
R["needs_recovery"] = GP.needs_recovery()
R["sync_before_recover"] = GP.MANAGER.needs_sync()  # до відновлення нічого не застосовуємо
rr = GP.MANAGER.recover(log)
R["recovered"] = {"res": rr, "plan": plan(), "prio": PRIO[105], "ids": ids(), "state": F.CFG["game_profile_state"]}
GP.MANAGER.sync(log)  # гра ще працює — профіль застосовується знову
R["reapplied"] = {"plan": plan(), "prio": PRIO[105]}
GP.MANAGER.stop_all(log)  # OptimaX закривається
R["closed"] = {"plan": plan(), "prio": PRIO[105], "ids": ids(), "boost": F.BOOSTER.active}
stop(105)

# ── 8. аварія → OptimaX-Rescue.cmd /all (без Python) ──
start(106, "alpha.exe", A["main"])
GP.MANAGER.sync(log)
R["rescue_before"] = plan()
F.BOOSTER.stop(log)
RS.write_rescue()
subprocess.run(["cmd", "/c", RS.rescue_path(), "/all"])
RS.sync()
R["rescue_after"] = {"plan": plan(), "ids": [i for i in ids() if i == GP.POWER_ID]}
stop(106)
GP.MANAGER = GP.Manager()
GP.MANAGER.recover(log)

# ── 9. підмінений settings.json: realtime, чужі шляхи, сміття ──
PROCS.clear()
F.CFG["game_profiles"] = {A["key"]: {"power": "powercfg -h off", "gpu": 3, "prio": "realtime", "boost": "yes"},
                          B["key"]: ["junk"], 5: {}}
F.CFG["library"] = {"games": [A, dict(B, dir="C:\\Windows\\System32", key="evil", exes=["lsass.exe"]),
                              dict(B, key="root", dir="C:\\", exes=["x.exe"]),
                              dict(B, key="bad", exes=["..\\cmd.exe", "explorer.exe"])]}
F.CFG["game_profiles"] = dict(F.CFG["game_profiles"], evil={"prio": "high"}, root={"prio": "high"},
                              bad={"prio": "high"})
R["tampered"] = {"profiles": GP.profiles(), "watched": sorted(GP.watched())}
F.CFG["game_profile_state"] = {"prio": [[300, "lsass.exe", 0x20, 0x80], [301, "alpha.exe", 0x100, 0x80],
                                        "junk", [302, "alpha.exe", 0x20, 0x100]]}
start(300, "lsass.exe", r"C:\Windows\System32\lsass.exe", 0x80)
start(301, "alpha.exe", A["main"], 0x80)
start(302, "alpha.exe", A["main"], 0x100)
GP.MANAGER = GP.Manager()
GP.MANAGER.recover(log)
R["tampered_state"] = [PRIO[300], PRIO[301], PRIO[302]]

# ── 10. профіль прибрали — «Графіка» як до OptimaX (чужий параметр лишився) ──
F.CFG["library"] = {"games": [A, B]}
GP.save(A, {"gpu": "high"}, log)
GP.remove(A, log)
GP.remove(B, log)
R["removed"] = {"pref": pref(A["main"]), "ids": ids(), "cfg": F.CFG["game_profiles"]}

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "roundtrip.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
