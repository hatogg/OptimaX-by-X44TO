"""Майнінгова карта + монітор на другій NVIDIA (P106 + GT 710): EnableMsHybrid з відкатом (mining.hybrid_*), і
перевірка «на якій карті малює гра», яка з двома NVIDIA не може вірити завантаженому драйверу (gpuinfo.path_verdict)."""
import json
import os
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, SCRIPTS, skip, tail

sys.path.insert(0, ROOT)
import gpuinfo as GI  # noqa: E402
import mining as MG  # noqa: E402

GT = dict(name="NVIDIA GeForce GT 710", ven=GI.NVIDIA, dev=0x128B, vram_mb=980, luid="L_GT", software=False,
          outputs=1, dx12=True)
P106 = dict(name="NVIDIA P106-100", ven=GI.NVIDIA, dev=0x1C07, vram_mb=6070, luid="L_P106", software=False, outputs=0,
            dx12=True)
RX = dict(name="AMD Radeon RX 550", ven=GI.AMD, dev=0x699F, vram_mb=4000, luid="L_RX", software=False, outputs=2)


# ── хто «пара»: лише майнінгова карта + карта з монітором того самого виробника ──
def test_pair_only_for_a_second_nvidia_with_the_monitor():
    pair = MG.hybrid_pair({"dxgi": [GT, P106]})
    assert pair["render"]["luid"] == "L_P106" and pair["display"]["luid"] == "L_GT" and pair["vendor"] == "nvidia"
    # порядок у DXGI неважливий
    assert MG.hybrid_pair({"dxgi": [P106, GT]})["display"]["luid"] == "L_GT"
    # монітор на HD 4000: Windows сама вважає вбудовану енергоощадною — налаштовувати нічого
    assert MG.hybrid_pair(GI.DEMO_PROBE["mining"]) == {}
    # монітор на AMD: драйвери різні, EnableMsHybrid NVIDIA тут не про те
    assert MG.hybrid_pair({"dxgi": [RX, P106]}) == {}
    # ноутбук з Optimus: RTX без виходів — не майнінгова карта
    assert MG.hybrid_pair(GI.DEMO_PROBE["laptop"]) == {}
    assert MG.hybrid_pair({}) == {} and MG.hybrid_state({})["state"] == "na"


def test_a_lone_card_with_outputs_is_not_the_mining_card():
    # P106 ще без DirectX: DXGI бачить лише GT 710 — це карта з монітором, а не майнінгова
    assert GI.mining_adapter({"dxgi": [GT]}) == {}
    assert GI.summary({"dxgi": [GT]})["gpu"] == "" and GI.summary({"dxgi": [GT]})["display"] == GT["name"]
    # P106 з «позиченими» виходами вбудованої — і далі майнінгова (за PCI ID)
    hd = dict(name="Intel(R) HD Graphics 4000", ven=GI.INTEL, dev=0x0162, luid="L_HD", outputs=1)
    assert GI.mining_adapter({"dxgi": [hd, dict(P106, outputs=1)]})["luid"] == "L_P106"
    # без реєстру (не Windows) P106 ніде не знайти — пари немає
    assert MG.hybrid_pair({"dxgi": [GT]}, keys=[]) == {}
    keys = [dict(sub="0001", path="x", desc="NVIDIA GeForce GT 710", ven=0x10DE, dev=0x128B, hybrid=None),
            dict(sub="0002", path="y", desc="NVIDIA P106-100", ven=0x10DE, dev=0x1C07, hybrid=None)]
    pair = MG.hybrid_pair({"dxgi": [GT]}, keys=keys)
    assert pair["render"] == dict(name="NVIDIA P106-100", ven=0x10DE, dev=0x1C07, luid="")
    assert pair["display"]["luid"] == "L_GT"


def test_summary_tells_the_monitor_card_vendor():
    assert GI.summary({"dxgi": [GT, P106]})["display_vendor"] == "nvidia"
    assert GI.summary(GI.DEMO_PROBE["mining"])["display_vendor"] == "intel"
    assert GI.summary({})["display_vendor"] == ""


# ── перевірка гри: з двома NVIDIA драйвер у процесі нічого не доводить ──
def test_path_verdict_does_not_trust_the_shared_driver():
    nv = dict(apis=["dx11"], layer="", drivers={"nvidia": ["dx11"]}, known=True)
    assert GI.path_verdict(nv) == "mining", "monitor on Intel: an NVIDIA driver in the game means the mining card"
    assert GI.path_verdict(nv, display_vendor="intel") == "mining"
    assert GI.path_verdict(nv, display_vendor="nvidia") == "", "GT 710 and P106 share the driver: counters decide"
    warp = dict(apis=["dx11"], layer="", drivers={"warp": ["dx11"]}, known=True)
    assert GI.path_verdict(warp, display_vendor="nvidia") == "warp"
    soft = dict(apis=["gl"], layer="mesa-soft", drivers={}, known=True)
    assert GI.path_verdict(soft, display_vendor="nvidia") == "warp"


def test_counters_still_catch_the_monitor_card_rendering():
    # 3D-робота гри на GT 710 (лічильники є: драйвер 472.12 — WDDM 2.x) — висновок «не на P106»
    samples = [{"fg": True, "eng": {"L_GT": {"3d": 55.0, "copy": 1.0, "other": 0.0},
                                     "L_P106": {"3d": 0.0, "copy": 0.0, "other": 0.0}}}] * 3
    assert GI.verdict(samples, "L_P106")["verdict"] == "igpu"


# ── на фальшивій Windows: реєстр, журнал, Rescue ──
_CACHE = {}


def fake_report() -> dict:
    if IS_WIN:
        skip("fake Windows runs only outside Windows")
    if "r" not in _CACHE:
        out = tempfile.mkdtemp(prefix="oxhy_")
        env = dict(os.environ, FAKE_HW="gaming", FAKE_TARGET=os.path.join(SCRIPTS, "hybrid_fake.py"),
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fake_windows.py"), "--out", out], cwd=ROOT,
                           env=env, capture_output=True, timeout=600)
        text = (p.stdout + p.stderr).decode("utf-8", "replace")
        path = os.path.join(out, "roundtrip.json")
        assert p.returncode == 0 and os.path.exists(path), tail(text)
        with open(path, encoding="utf-8") as f:
            _CACHE["r"] = json.load(f)
    return _CACHE["r"]


def test_driver_keys_are_matched_by_pci_id():
    r = fake_report()
    assert r["keys"] == [["0001", "10DE:128B", "NVIDIA GeForce GT 710"], ["0002", "10DE:1C07", "NVIDIA P106-100"]], \
        "the basic Microsoft adapter and service subkeys are not cards"
    assert r["igpu"] == "na" and r["igpu_tweak"] == 0


def test_assign_sets_the_priority_once():
    r = fake_report()
    assert r["before"] == "off"
    assert r["assign1"] == {"hybrid": "pending", "hybrid_applied": True}
    assert r["after"] == {"gt710": 2, "p106": 1, "basic": None}
    assert r["journal"] and r["pending"] == "pending"
    assert r["assign2"] == {"hybrid": "pending", "hybrid_applied": None}
    assert r["journal_same"], "a second run writes nothing"
    assert r["set_again"] is False


def test_state_follows_what_windows_reports():
    r = fake_report()
    assert r["ok"] == "ok", "DXGI gives High performance to the P106"
    assert r["wrong"] == "wrong", "rebooted since, and Windows still picks the GT 710"
    assert r["stale_probe"] == "pending", "a check from before the change proves nothing"
    assert r["no_pref"] == "set", "no EnumAdapterByGpuPreference: OptimaX doesn't claim it works"


def test_revert_removes_only_our_values():
    r = fake_report()
    assert r["rescue"] == 2, "OptimaX-Rescue.cmd must be able to remove both values"
    assert r["reverted"] == {"gt710": None, "p106": None, "basic": None} and r["after_revert"] == "off"
    assert r["manual"] == "pending" and r["manual_assign"] is False
    assert r["manual_kept"] == {"gt710": 2, "p106": 1, "basic": None}, "values the user set by hand stay"
    assert r["partial_ops"] == [["0001", 2]], "only the missing value is written"
    assert r["partial_after"] == {"gt710": 2, "p106": 1, "basic": None}
    assert r["partial_reverted"] == {"gt710": 0, "p106": 1, "basic": None}, "the user's own 0 comes back"


def test_mining_card_hidden_from_directx():
    r = fake_report()
    assert r["hidden"] == {"state": "off", "visible": False, "render": "NVIDIA P106-100", "ops": 2, "summary_gpu": "",
                           "rows": ["pci", "no_dxgi_pair", "display"]}, r["hidden"]
    assert "no_dxgi" not in r["hidden"]["rows"], "not a broken driver: OptimaX fixes this itself"
    assert r["hidden_assign"] is True and r["hidden_vals"] == {"gt710": 2, "p106": 1, "basic": None}
    assert r["hidden_ok"] == "ok", "after the restart DXGI sees the P106 and gives it High performance"
    assert r["hidden_reverted"] == {"gt710": None, "p106": None, "basic": None}


def test_no_admin_and_missing_driver():
    r = fake_report()
    assert r["no_admin"] == "admin" and r["no_admin_vals"] == {"gt710": None, "p106": None, "basic": None}
    assert r["missing"] == "missing" and r["missing_assign"] == "missing" and r["log_missing"]
