"""Режими оптимізації (6.4): план під конкретний ПК — залізо, головне обмеження, докази розумної оптимізації."""
import json
import subprocess
import sys

from _util import ROOT, env_for

CODE = r"""
import json, sys
sys.argv = ["x", "--dry-run", "--lang=en"]
import hardware as H, modes as MD, engine as E, features as F
import os
hw = H._from_demo(os.environ["OPTIMAX_DEMO"])
R = {"rec": MD.recommended(hw)}
for m in MD.MODES:
    p = MD.plan(m, hw, {}, {})
    R[m] = {"n": len(p["ids"]), "ids": p["ids"], "smart": p["smart"],
            "why": sorted({e["why"] for e in p["excluded"]})}
gpu = MD.plan("gaming", hw, {"main": "gpu", "share": 90}, {})
R["gpu"] = {"ids": gpu["ids"], "limit": gpu["limit"], "excluded": [e["id"] for e in gpu["excluded"] if e["why"] == "limit"]}
hot = MD.plan("gaming", hw, {"main": "thermal", "share": 70}, {})
R["hot"] = {"ids": hot["ids"], "dropped": [e["id"] for e in hot["excluded"] if e["why"] == "hot"]}
weak = MD.plan("gaming", hw, {"main": "gpu", "share": 30}, {})
R["weak_limit"] = weak["limit"]
ev = {"core_parking": {"harm": 1}, "rt_boost": {"none": 2}, "cpu_scheduling": {"help": 1}}
e = MD.plan("gaming", hw, {}, ev)
R["ev"] = {"ids": e["ids"], "why": {x["id"]: x["why"] for x in e["excluded"]}, "proven": e["proven"]}
R["ev_safe_harm"] = "game_mode_on" in MD.plan("safe", hw, {}, {"game_mode_on": {"harm": 2, "help": 1}})["ids"]
ram = MD.plan("lowend", hw, {"main": "ram", "share": 80}, {})
R["lowend_ram"] = ram["ids"]
R["safe_props"] = all(E.BY_ID[i].impact == "safe" and E.BY_ID[i].reversible and not E.BY_ID[i].risky for i in R["safe"]["ids"])
R["compat_ok"] = all(E.compat(E.BY_ID[i], hw)[0] not in ("na", "block") for m in ("safe", "gaming", "lowend") for i in R[m]["ids"])
R["no_conflicts"] = all(not E.resolve_conflicts(R[m]["ids"], [])[1] for m in ("safe", "gaming", "lowend"))
F.CFG["diag_last"] = {"ts": 100, "bottleneck": {"main": "cpu", "share": 80}}
F.CFG["fps_tests"] = {"cs2.exe": {"after": {"ts": 200, "bottleneck": {"main": "gpu", "share": 90}}}}
R["latest"] = MD.latest_bottleneck()["main"]
print("RESULT " + json.dumps(R))
"""


def run(demo):
    env = env_for(demo)
    p = subprocess.run([sys.executable, "-c", CODE], cwd=ROOT, env=env, capture_output=True, timeout=120)
    out = (p.stdout + p.stderr).decode("utf-8", "replace")
    line = next((ln for ln in out.splitlines() if ln.startswith("RESULT ")), None)
    assert p.returncode == 0 and line, out[-3000:]
    return json.loads(line[7:])


def test_plans_on_a_gaming_pc():
    r = run("gaming")
    assert r["rec"] == "gaming"
    assert r["manual"]["n"] == 0 and r["gaming"]["smart"] and not r["safe"]["smart"]
    assert 10 <= r["safe"]["n"] < r["gaming"]["n"], (r["safe"]["n"], r["gaming"]["n"])
    assert r["safe_props"], "Safe mode: only low-risk, reversible changes"
    assert r["compat_ok"] and r["no_conflicts"]


def test_gpu_bound_pc_skips_cpu_tweaks():
    r = run("gaming")
    assert r["gpu"]["limit"] == "gpu"
    assert "core_parking" in r["gpu"]["excluded"] and "core_parking" not in r["gpu"]["ids"]
    assert "gpu_hw_scheduling" in r["gpu"]["ids"] and "game_mode_on" in r["gpu"]["ids"]
    assert "disable_telemetry" in r["gpu"]["ids"], "privacy and background changes stay whatever the limit"
    assert r["weak_limit"] is None, "a limit seen only 30% of the time is not trusted"


def test_overheating_pc_gets_nothing_that_heats():
    r = run("gaming")
    assert r["hot"]["dropped"] and not set(r["hot"]["ids"]) & {"ultimate_power", "turbo_aggressive", "core_parking"}


def test_evidence_from_smart_optimization():
    r = run("gaming")
    assert r["ev"]["why"].get("core_parking") == "harmful" and "core_parking" not in r["ev"]["ids"]
    assert r["ev"]["why"].get("rt_boost") == "no_effect"
    assert "cpu_scheduling" in r["ev"]["proven"]
    assert not r["ev_safe_harm"], "harmful on this PC is never offered, in any mode"


def test_low_end_pc():
    r = run("old")
    assert r["rec"] == "lowend" and r["lowend"]["n"] > 10
    assert "disable_search_index" in r["lowend"]["ids"] or "memory_compression" in r["lowend_ram"]
    assert r["compat_ok"]


def test_latest_bottleneck_prefers_the_newest_measurement():
    assert run("gaming")["latest"] == "gpu"
