"""7.2.1: портативні консолі на Windows (ROG Ally, Legion Go, MSI Claw, Steam Deck): розпізнавання за моделлю і
свій план — без змін, що «розганяють» процесор APU чи ламають оверлеї й фонові завантаження."""
import json
import subprocess
import sys

from _util import ROOT, env_for

CODE = r"""
import json, sys
sys.argv = ["x", "--dry-run", "--lang=en"]
import features as F, hardware as H, modes as MD
R = {}
R["detect"] = {f"{v}|{m}": H.is_handheld(v, m) for v, m in [
    ("ASUSTeK COMPUTER INC.", "ROG Ally RC71L_RC71L"), ("ASUSTeK COMPUTER INC.", "ROG Ally X RC72LA_RC72LA"),
    ("ASUSTeK COMPUTER INC.", "ROG Xbox Ally X RC73XA"), ("LENOVO", "83E1"), ("Valve", "Jupiter"),
    ("Valve", "Galileo"), ("Micro-Star International Co., Ltd.", "Claw A1M"),
    ("ASUSTeK COMPUTER INC.", "ROG Strix G614JV_G614JV"), ("LENOVO", "82JW"), ("HP", "Victus by HP Laptop"),
    ("", ""), (None, None)]}
base = H._from_demo("laptop")
ally = H._finish(dict(base, vendor="ASUSTeK COMPUTER INC.", model="ROG Ally RC71L_RC71L"))
nobat = H._finish(dict(base, vendor="ASUSTeK COMPUTER INC.", model="ROG Ally RC71L_RC71L", battery=False,
                       lid=False, chassis=[3]))
R["ally"] = {k: ally[k] for k in ("device", "handheld", "laptop", "profile")}
R["nobat_device"] = nobat["device"]
R["laptop_device"] = base["device"]
R["defaults"] = F.wizard_defaults(ally)
R["recommended"] = MD.recommended(dict(ally, ram_gb=8.0))
R["hot"] = F.HOT
R["skip"] = F.HANDHELD_SKIP
plans = {}
for goal in ("fps", "latency", "quiet"):
    for usage in ("games", "work"):
        ans = dict(F.wizard_defaults(ally), goal=goal, usage=usage)
        plans[f"handheld/{usage}-{goal}"] = F.build_plan(ans, ally)
        plans[f"laptop/{usage}-{goal}"] = F.build_plan(dict(ans, device="laptop"), ally)
R["plans"] = plans
R["mode_gaming"] = MD.plan("gaming", ally, {}, {})["ids"]
print("RESULT " + json.dumps(R))
"""

_CACHE = {}


def result() -> dict:
    if "r" not in _CACHE:
        p = subprocess.run([sys.executable, "-c", CODE], cwd=ROOT, env=env_for("laptop"), capture_output=True,
                           timeout=180)
        out = (p.stdout + p.stderr).decode("utf-8", "replace")
        line = next((ln for ln in out.splitlines() if ln.startswith("RESULT ")), None)
        assert p.returncode == 0 and line, out[-3000:]
        _CACHE["r"] = json.loads(line[7:])
    return _CACHE["r"]


def test_known_handhelds_are_detected_and_laptops_are_not():
    d = result()["detect"]
    for key, want in d.items():
        expect = not any(x in key for x in ("Strix", "82JW", "Victus")) and key != "|" and key != "None|None"
        assert want is expect, key


def test_handheld_keeps_laptop_base_but_its_own_device():
    r = result()
    assert r["ally"] == {"device": "handheld", "handheld": True, "laptop": True, "profile": "T"}
    assert r["nobat_device"] != "handheld", "без батареї — не консоль (захист від хибного збігу назви)"
    assert r["laptop_device"] == "laptop"
    assert r["defaults"]["device"] == "handheld" and r["defaults"]["usage"] == "games"
    assert r["recommended"] == "gaming", "8 ГБ видимої пам'яті через відеокарту APU — не «слабкий ПК»"


def test_handheld_plan_never_pushes_the_cpu_or_breaks_overlays():
    r = result()
    bad = set(r["hot"]) | set(r["skip"])
    for name, ids in r["plans"].items():
        if name.startswith("handheld/"):
            assert not set(ids) & bad, (name, set(ids) & bad)
            assert ("windowed_opt" in ids) == ("games" in name), name
    assert not set(r["mode_gaming"]) & bad
    assert "windowed_opt" in r["mode_gaming"]
    # ноутбук не змінився
    assert "laptop_ac_max" in r["plans"]["laptop/games-fps"]
