"""Майнінгова карта + монітор на другій NVIDIA (P106 + GT 710): офіційний драйвер дає P106 малювати лише з вбудованою
Intel / AMD, тож OptimaX чесно каже, що пара для ігор не працює (mining.nv_pair*), нічого не пишучи в розділи драйверів;
і перевірка «на якій карті малює гра», яка з двома NVIDIA не може вірити завантаженому драйверу (gpuinfo.path_verdict)."""
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
    pair = MG.nv_pair({"dxgi": [GT, P106]})
    assert pair["render"]["luid"] == "L_P106" and pair["display"]["luid"] == "L_GT" and pair["vendor"] == "nvidia"
    # порядок у DXGI неважливий
    assert MG.nv_pair({"dxgi": [P106, GT]})["display"]["luid"] == "L_GT"
    # монітор на HD 4000 — звичайний випадок, пари немає
    assert MG.nv_pair(GI.DEMO_PROBE["mining"]) == {}
    # монітор на AMD: драйвери різні, EnableMsHybrid NVIDIA тут не про те
    assert MG.nv_pair({"dxgi": [RX, P106]}) == {}
    # ноутбук з Optimus: RTX без виходів — не майнінгова карта
    assert MG.nv_pair(GI.DEMO_PROBE["laptop"]) == {}
    assert MG.nv_pair({}) == {} and MG.nv_pair_state({})["state"] == "na"


def test_a_lone_card_with_outputs_is_not_the_mining_card():
    # P106 без DirectX (TCC / код 43): DXGI бачить лише GT 710 — це карта з монітором, а не майнінгова
    assert GI.mining_adapter({"dxgi": [GT]}) == {}
    assert GI.summary({"dxgi": [GT]})["gpu"] == "" and GI.summary({"dxgi": [GT]})["display"] == GT["name"]
    # P106 з «позиченими» виходами вбудованої — і далі майнінгова (за PCI ID)
    hd = dict(name="Intel(R) HD Graphics 4000", ven=GI.INTEL, dev=0x0162, luid="L_HD", outputs=1)
    assert GI.mining_adapter({"dxgi": [hd, dict(P106, outputs=1)]})["luid"] == "L_P106"
    # без реєстру (не Windows) P106 ніде не знайти — пари немає
    assert MG.nv_pair({"dxgi": [GT]}, keys=[]) == {}
    keys = [dict(sub="0001", path="x", desc="NVIDIA GeForce GT 710", ven=0x10DE, dev=0x128B),
            dict(sub="0002", path="y", desc="NVIDIA P106-100", ven=0x10DE, dev=0x1C07)]
    pair = MG.nv_pair({"dxgi": [GT]}, keys=keys)
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


def test_pair_is_reported_as_not_working_for_games():
    r = fake_report()
    h = r["hidden"]
    assert (h["state"], h["visible"], h["render"], h["display"], h["summary_gpu"]) == \
        ("nvpair", False, "NVIDIA P106-100", "NVIDIA GeForce GT 710", "")
    assert h["rows"] == ["pci", "nv_pair", "display"], h["rows"]
    assert "no_dxgi" not in h["rows"], "not a broken driver: don't send the user to reinstall it"
    assert r["findings"] == ["gd_nv_pair"]
    assert r["visible"]["state"] == "nvpair" and "nv_pair" in r["visible"]["rows"]
    assert r["igpu"]["state"] == "na" and "nv_pair" not in r["igpu"]["rows"], "monitor on HD 4000 is the normal case"


def test_scan_warns_and_writes_nothing_to_driver_keys():
    r = fake_report()
    assert r["assign_nvpair"] is True and r["log_nvpair"]
    assert r["assign_igpu"] is False
    assert r["driver_keys_untouched"] and not r["journal_hybrid"]
