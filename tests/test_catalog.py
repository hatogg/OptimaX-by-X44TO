"""Каталог оптимізацій (6.9): одне налаштування — одна оптимізація, прибрані зміни не пропонуються, параметри
спільного рядка реєстру (KV) відкочуються поодинці, «доведено» — лише для змін, заміряних окремо."""
import json
import subprocess
import sys

from _util import ROOT, env_for

sys.path.insert(0, ROOT)
import abtest as AB  # noqa: E402  (чиста логіка без системи)

CODE = r"""
import base64, collections, json, os, sys
sys.argv = ["x", "--dry-run", "--lang=en"]
import engine as E, modes as MD, features as F, guard as G, hardware as H, rescue as RS


def keys(t):
    out, ops, i = set(), list(t.ops), 0
    while i < len(ops):
        op = ops[i]
        i += 1
        k = op[0]
        if k in ("reg", "regdel"):
            out.add(("reg", op[1].lower(), op[2].lower()))
        elif k == "kv":
            out.add(("kv", op[1].lower(), op[2].lower(), op[3].lower()))
        elif k == "cmd":
            out.add(("cmd", op[1].strip().lower()))
        elif k == "pw":
            out.add(("pw", op[1], op[2], op[4]))
        elif k == "svc":
            out.add(("svc", op[1].lower()))
        elif k == "dyn":
            ops += list(op[1](E.Ctx(lambda *_: None)) or [])
        elif k == "fn" and op[1] is E.f_services:
            out |= {("svc", n.lower()) for n in E.FORCE_OFF}
    return out


R = {}
own = collections.defaultdict(set)
for t in E.TWEAKS:
    if not t.retired:
        for k in keys(t):
            own[k].add(t.id)
R["overlaps"] = [[sorted(v), list(k)] for k, v in own.items()
                 if len(v) > 1 and not all(b in E.conflicts_of(a) for a in v for b in v if a != b)]

retired = [t for t in E.TWEAKS if t.retired]
R["retired"] = [t.id for t in retired]
R["retired_ok"] = all(not t.p and E.compat(t, {"build": 26100})[0] == "na" and not G.guarded(t.id) and
                      "retired" not in t.desc and t.desc and t.badges() for t in retired)
plans = {}
for demo in ("gaming", "laptop", "old", "x3d", "xeon"):
    hw = H._from_demo(demo)
    for m in ("safe", "gaming", "lowend"):
        plans[f"{demo}/{m}"] = MD.plan(m, hw, {}, {})["ids"]
    for goal in ("fps", "latency", "quiet"):
        ans = dict(F.wizard_defaults(hw), goal=goal, usage="games")
        plans[f"{demo}/wizard-{goal}"] = F.build_plan(ans, hw)
R["plans"] = plans
logs = []
res = E.apply_tweaks([E.BY_ID["rt_boost"], E.BY_ID["game_mode_on"]], logs.append)
R["apply_retired"] = {"skipped": res["skipped"], "log": "\n".join(logs)}

# KV: застосування й відкат одного параметра, коли в рядку вже є чужі
R["kv_set"] = [E.kv_set("A=1;B=2;", "A", "5"), E.kv_set("A=1;B=2;", "C", "1"), E.kv_set("A=1;B=2;", "A", None),
               E.kv_set("", "A", None), E.kv_get("A=1;B=2;", "B"), E.kv_get("A=1;", "B")]
R["kv_restored"] = [E.kv_restored("X=1;VRROptimizeEnable=1;", {"kv": "VRROptimizeEnable", "kvold": None,
                                                               "old": [1, "X=1;"]}),
                    E.kv_restored("VRROptimizeEnable=1;", {"kv": "VRROptimizeEnable", "kvold": None, "old": None}),
                    E.kv_restored("VRROptimizeEnable=1;Y=2;", {"kv": "VRROptimizeEnable", "kvold": "0",
                                                               "old": [1, "VRROptimizeEnable=0;"]})]
base = {"t": "reg", "p": E.DX_PREF, "n": E.DX_GLOBAL, "old": None, "kv": "AutoHDREnable", "kvold": None}
R["kv_valid"] = [E.valid_undo(base), E.valid_undo(dict(base, kvold="1")),
                 E.valid_undo(dict(base, kv="A';calc;'")), E.valid_undo(dict(base, kvold="1' ; rm"))]
line = RS.undo_lines(base)
R["kv_rescue"] = line
R["kv_rescue_code"] = base64.b64decode(line[0].rsplit(" ", 1)[1]).decode("utf-16-le") if line else ""
R["appx"] = E.parse_appx("OK|Microsoft.ZuneMusic\nMISS|Microsoft.People\nERR|Microsoft.XboxApp|0x80073CFA blocked\nnoise")
print("RESULT " + json.dumps(R))
"""

_CACHE = {}


def result() -> dict:
    if "r" not in _CACHE:
        p = subprocess.run([sys.executable, "-c", CODE], cwd=ROOT, env=env_for("gaming"), capture_output=True,
                           timeout=180)
        out = (p.stdout + p.stderr).decode("utf-8", "replace")
        line = next((ln for ln in out.splitlines() if ln.startswith("RESULT ")), None)
        assert p.returncode == 0 and line, out[-3000:]
        _CACHE["r"] = json.loads(line[7:])
    return _CACHE["r"]


def test_every_setting_has_one_owner():
    # дві оптимізації одного значення ламали відкат: друга записувала як «початкове» значення першої
    assert result()["overlaps"] == []


def test_retired_changes_are_never_offered_or_applied():
    r = result()
    assert set(r["retired"]) >= {"rt_boost", "registry_boost", "disable_defender", "hpet_tsc", "optimize_network",
                                 "network_stack_boost", "network_packet_opt"}
    assert r["retired_ok"], "no profile, compat 'na', not guarded, explained in the description, badge shown"
    for name, ids in r["plans"].items():
        assert not set(ids) & set(r["retired"]), name
    assert r["apply_retired"]["skipped"] == 1 and "removed from OptimaX in 6.9" in r["apply_retired"]["log"]


def test_default_plans_skip_irreversible_and_habit_changes():
    off = {"clean_registry", "memory_clean", "optimize_pagefile", "disable_nagle", "network_throttling"}
    for name, ids in result()["plans"].items():
        assert not set(ids) & off, (name, set(ids) & off)
        if "latency" not in name:
            assert "disable_mouse_accel" not in ids, name
    assert any("disable_mouse_accel" in ids for n, ids in result()["plans"].items() if "latency" in n)


def test_kv_changes_only_its_own_part():
    r = result()
    assert r["kv_set"] == ["A=5;B=2;", "A=1;B=2;C=1;", "B=2;", "", "2", None], "order of the rest is kept"
    # чужий параметр лишається; значення, якого не було до OptimaX, прибирається; старе значення повертається
    assert r["kv_restored"] == ["X=1;", None, "VRROptimizeEnable=0;Y=2;"]
    assert r["kv_valid"] == [True, True, False, False], "names and values from the journal can't become a command"


def test_rescue_script_restores_a_kv_part():
    r = result()
    assert len(r["kv_rescue"]) == 1 and r["kv_rescue"][0].startswith("powershell -NoProfile")
    code = r["kv_rescue_code"]
    assert "Registry::HKEY_CURRENT_USER\\Software\\Microsoft\\DirectX\\UserGpuPreferences" in code
    assert "$key='AutoHDREnable'" in code and "$old=$null" in code and "$had=$false" in code


def test_store_apps_output_is_parsed():
    assert result()["appx"] == {"Microsoft.ZuneMusic": ["ok", ""], "Microsoft.People": ["miss", ""],
                                "Microsoft.XboxApp": ["err", "0x80073CFA blocked"]}


def test_proven_only_when_measured_alone():
    batch = {"result": "better", "significant": True, "delta": {"avg": 0.06}, "measured": ["a", "b", "c"]}
    ev = AB.update_evidence({}, batch, now=1)
    assert {k: AB.evidence_state(v) for k, v in ev.items()} == {"a": "pack", "b": "pack", "c": "pack"}
    ev = AB.update_evidence(ev, dict(batch, measured=["b"]), now=2)
    assert AB.evidence_state(ev["b"]) == "proven" and AB.evidence_state(ev["a"]) == "pack"
    assert AB.evidence_state({"help": 3}) == "pack", "a pre-6.9 batch gain is not proof"
    assert AB.evidence_state({"harm": 1, "pack": 1}) == "harmful"
    assert AB.evidence_state({"none": 2}) == "no_effect"
    ev = AB.update_evidence({}, {"result": "same", "measured": ["a", "b"], "removed": ["c"]}, now=3)
    assert ev["a"]["none"] == 1 and ev["c"]["harm"] == 1
