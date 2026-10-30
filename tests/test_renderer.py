"""Universal GPU Renderer (OptimaX 6.5): що бачать DirectX і Vulkan, на якій карті малює гра (лічильники й драйвер
процесу), режими рендерингу з профілями й відкатом, аналізатори (PCIe, пам'ять, фризи, кеш шейдерів), база
сумісності й Game Booster 2.0."""
import json
import os
import struct
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, SCRIPTS, skip, tail

sys.path.insert(0, ROOT)
import gpudiag as GD  # noqa: E402
import gpuinfo as GI  # noqa: E402

NV = "0x00000000_0x0000D6B5"
IG = "0x00000000_0x0000C2E1"


# ── gpuinfo: розбір того, що повертають Windows і Vulkan ──
def test_luid_and_vulkan_properties():
    assert GI.luid_key(0, 0xD6B5) == NV
    assert GI.luid_key(-1, 1) == "0xFFFFFFFF_0x00000001"
    buf = bytearray(1024)
    api = (1 << 22) | (4 << 12) | 303
    drv = (582 << 22) | (78 << 14)
    struct.pack_into("<IIIII", buf, 0, api, drv, 0x10DE, 0x1C07, 2)
    buf[20:20 + 27] = b"NVIDIA GeForce GTX 1060 6GB"
    d = GI.parse_vk_props(bytes(buf))
    assert d == dict(name="NVIDIA GeForce GTX 1060 6GB", ven=0x10DE, dev=0x1C07, type="discrete", api="1.4.303",
                     driver="582.78"), d


def test_probe_summary_finds_the_card_without_outputs():
    s = GI.summary(GI.DEMO_PROBE["mining"])
    assert s["gpu"] == "NVIDIA GeForce GTX 1060 6GB" and s["luid"] == NV and s["dx12"] is True
    assert s["vulkan"] and s["vk_api"] == "1.4.303" and s["driver"] == "582.78"
    assert s["display"] == "Intel(R) HD Graphics 4000"
    assert GI.summary({"dxgi": [], "vulkan": []})["gpu"] == ""


def test_engine_counters_per_process_and_adapter():
    c = {f"pid_10_luid_{NV}_phys_0_eng_0_engtype_3D": 55.0, f"pid_10_luid_{NV}_phys_0_eng_5_engtype_Copy": 12.0,
         f"pid_10_luid_{IG}_phys_0_eng_0_engtype_3D": 2.0, f"pid_99_luid_{NV}_phys_0_eng_0_engtype_3D": 30.0}
    sp = GI.engine_split(c, {10})
    assert sp[NV] == {"3d": 55.0, "copy": 12.0, "other": 0.0} and sp[IG]["3d"] == 2.0
    samples = [{"fg": True, "eng": sp, "vram": {NV: 3 << 30}, "shared": {NV: 200 << 20}}] * 3
    v = GI.verdict(samples, NV)
    assert v["verdict"] == "mining" and v["vram_mb"] == 3072 and v["shared_mb"] == 200
    # HD 4000 (WDDM 1.3) лічильників не має: гра на передньому плані, а на майнінговій карті 3D немає — вбудована
    assert GI.verdict([{"fg": True, "eng": {}, "vram": {}}] * 3, NV)["verdict"] == "igpu"
    assert GI.verdict([{"fg": False, "eng": {}, "vram": {}}] * 3, NV)["verdict"] == "idle"
    assert GI.verdict([], NV)["verdict"] == "none"


def test_render_path_from_loaded_libraries():
    sysd = os.environ.get("SystemRoot", r"C:\Windows") + r"\System32"
    game = r"D:\Games\CSS"
    dxvk = [("hl2.exe", game + r"\hl2.exe"), ("d3d9.dll", game + r"\d3d9.dll"), ("vulkan-1.dll", sysd + r"\vulkan-1.dll"),
            ("nvoglv32.dll", r"C:\Windows\System32\DriverStore\nv\nvoglv32.dll")]
    p = GI.render_path(dxvk, game)
    assert p["layer"] == "dxvk" and "dx9" in p["apis"] and p["drivers"] == {"nvidia": ["gl"]}
    assert GI.path_verdict(p) == "mining"
    assert "DXVK" in GI.describe_path(p) and "NVIDIA" in GI.describe_path(p)
    native9 = [("hl2.exe", game + r"\hl2.exe"), ("d3d9.dll", sysd + r"\d3d9.dll"),
               ("igdumdim32.dll", r"C:\Windows\System32\DriverStore\ig\igdumdim32.dll")]
    p = GI.render_path(native9, game)
    assert p["layer"] == "" and p["drivers"] == {"intel": ["dx9"]} and GI.path_verdict(p) == "igpu"
    gl = [("hl.exe", game + r"\hl.exe"), ("opengl32.dll", sysd + r"\opengl32.dll"), ("ig7icd32.dll", "x\\ig7icd32.dll")]
    assert GI.path_verdict(GI.render_path(gl, game)) == "igpu"
    mesa = [("hl.exe", game + r"\hl.exe"), ("opengl32.dll", game + r"\opengl32.dll"),
            ("libgallium_wgl.dll", game + r"\libgallium_wgl.dll"), ("d3d12.dll", sysd + r"\d3d12.dll"),
            ("dxil.dll", game + r"\dxil.dll"), ("nvwgf2umx.dll", "x\\nvwgf2umx.dll")]
    p = GI.render_path(mesa, game)
    assert p["layer"] == "mesa-d3d12" and GI.path_verdict(p) == "mining"
    zink = [m for m in mesa if m[0] not in ("d3d12.dll", "dxil.dll", "nvwgf2umx.dll")] + \
        [("vulkan-1.dll", sysd + r"\vulkan-1.dll"), ("nvoglv64.dll", "x\\nvoglv64.dll")]
    assert GI.render_path(zink, game)["layer"] == "mesa-zink"
    both = [("g.exe", "g.exe"), ("d3d11.dll", sysd + r"\d3d11.dll"), ("nvwgf2umx.dll", "a"), ("igd10iumd64.dll", "b")]
    assert GI.path_verdict(GI.render_path(both, game)) == "", "two drivers — the counters decide"
    warp = [("g.exe", "g.exe"), ("d3d11.dll", sysd + r"\d3d11.dll"), ("d3d10warp.dll", "w")]
    assert GI.path_verdict(GI.render_path(warp, game)) == "warp"
    assert GI.path_verdict(GI.render_path([], game)) == ""


def test_check_outside_windows_is_labelled_as_demo_and_explained():
    if IS_WIN:
        skip("demo check exists only outside Windows")
    res = GI.check({"hl2.exe"}, NV)
    assert res["verdict"] == "mining" and res["path_text"]
    for v in ("mining", "igpu", "warp", "idle", "none"):
        assert GI.explain(dict(res, verdict=v), "P106-100")


# ── аналізатори ──
def test_pcie_link_under_load():
    idle = [dict(util=2, pcie_gen=1, pcie_width=16, pcie_max_gen=3, pcie_max_width=16, pcie_tx=0, pcie_rx=0)]
    ev = GD.pcie_eval(idle)
    assert ev["n"] == 0 and "load_gen" not in ev, "idle cards drop the generation — no verdict at idle"
    assert GD.pcie_findings(ev, {"mining_gpu": "P106-100"}) == []
    load = [dict(util=95, pcie_gen=1, pcie_width=4, pcie_max_gen=1, pcie_max_width=16, pcie_tx=600 * 1024,
                 pcie_rx=250 * 1024)] * 5
    ev = GD.pcie_eval(load)
    assert ev["load_gen"] == 1 and ev["load_width"] == 4 and ev["link_mbps"] == 1000 and ev["share"] == 85
    keys = [f["key"] for f in GD.pcie_findings(ev, {"mining_gpu": "P106-100"}, fps=60)]
    assert keys[:2] == ["pcie_narrow", "pcie_full"] and "pcie_copy" in keys, keys
    assert GD.frame_copy_mbps(1920, 1080, 60) == 475


def test_vram_spill_and_shared_memory():
    nv = [dict(vram_used=6000, vram_total=6144)]
    keys = [f["key"] for f in GD.memory_findings(nv, {"shared_mb": 900}, {"ram_gb": 8}, avail_mb=500)]
    assert keys == ["vram_full", "vram_spill", "ram_shared"], keys
    assert GD.memory_findings([dict(vram_used=2000, vram_total=6144)], {"shared_mb": 100}, {}) == []


def test_stutter_causes_line_up_with_system_samples():
    ft = [10.0] * 2000
    for i in (300, 900, 1500):  # фризи на ~3-й, 9-й і 15-й секунді
        ft[i] = 80.0
    sp = GD.spike_times(ft)
    assert len(sp) == 3 and 2.9 < sp[0] < 3.2
    samples = [dict(pages_in=0, disk=10, core_max=50) for _ in range(25)]
    samples[9]["pages_in"] = 900
    samples[15]["disk"] = 99
    causes = GD.spike_causes(sp, samples)
    assert causes == {"shader": 1, "ram": 1, "disk": 1}, causes
    f = GD.stutter_findings(dict(stutters=3, stutters_pm=9.0, smooth=60, low1=40, avg=95), causes)
    assert f and f[0]["key"].startswith("stutter_")
    assert GD.stutter_findings(dict(stutters=0, stutters_pm=0.0, smooth=95), {}) == []


def test_driver_report_for_a_mining_pc():
    hw = {"mining": [{"name": "NVIDIA GeForce GTX 1060 6GB", "model": "P106-100"}], "mining_gpu": "P106-100"}
    rep = GD.driver_report(hw, GI.DEMO_PROBE["mining"])
    keys = [k for _, k, _ in rep["rows"]]
    assert "pci_name" in keys and "dx12" in keys and "vulkan" in keys and "display" in keys, keys
    assert GD.driver_findings(hw, GI.DEMO_PROBE["mining"]) == []
    broken = {"dxgi": [dict(name="Microsoft Basic Display Adapter", ven=0x1414, outputs=1)], "vulkan": []}
    keys = [f["key"] for f in GD.driver_findings(hw, broken)]
    assert "gd_no_dxgi" in keys and "gd_igpu_basic" in keys, keys
    assert GD.driver_findings(hw, None) == [] and GD.driver_findings(hw, {}) == [], "no probe yet — no claims"
    novk = json.loads(json.dumps(GI.DEMO_PROBE["mining"]))
    novk["vulkan"] = []
    assert [f["key"] for f in GD.driver_findings(hw, novk)] == ["gd_no_vulkan"]


def test_bottleneck_history_and_regression():
    h = [dict(game="cs2.exe", avg=200, low1=120), dict(game="cs2.exe", avg=210, low1=125),
         dict(game="other.exe", avg=60), dict(game="cs2.exe", avg=150, low1=118)]
    r = GD.regression(h)
    assert r["metric"] == "avg" and r["pct"] == 27, r
    assert GD.regression(h[:2]) == {}


def test_shader_advice():
    keys = [k for _, k, _ in GD.shader_advice(dict(empty=5, driver_changed=True, total=9 << 30, driver="582.78",
                                                   prev_driver="576.02"))]
    assert keys == ["damaged", "driver", "huge"]
    assert [k for _, k, _ in GD.shader_advice(dict(empty=0, total=1 << 30))] == ["fine"]


# ── «Чому лагає?» з даними майнінгової карти ──
def test_lag_summary_with_render_frames_and_pcie():
    import monitor as M
    hw = {"mining_gpu": "P106-100", "ram_gb": 16, "gpus": [("NVIDIA GeForce GTX 1060 6GB", 6.0, "")]}
    samples = [dict(cpu=60, core_max=80, gpu=95, avail_mb=6000, pages_in=10, disk=5, temp=60, passive=100, limit=100,
                    vram_used=5.0, gpu_t=70, fg="hl2.exe", bg={}) for _ in range(30)]
    ft = [8.0] * 3000
    extra = dict(render={"verdict": "igpu", "path": {"apis": ["dx9"], "drivers": {"intel": ["dx9"]}},
                         "path_text": "DirectX 9 · driver: Intel"}, frametimes=ft,
                 nvml=[dict(util=95, pcie_gen=1, pcie_width=4, pcie_max_gen=1, pcie_max_width=16,
                            pcie_tx=700 * 1024, pcie_rx=200 * 1024, vram_used=3000, vram_total=6144)] * 30)
    res = M.summarize(samples, hw, "hl2.exe", {}, extra=extra)
    keys = [f["key"] for f in res["findings"]]
    assert keys[0] == "render_igpu_dx9" and res["findings"][0]["fix"] == ("mining", "hl2.exe"), keys
    assert "pcie_narrow" in keys and "pcie_full" in keys, keys
    assert res["frames"]["avg"] == 125.0 and res["render"]["verdict"] == "igpu"
    ok = M.summarize(samples, hw, "hl2.exe", {}, extra=dict(render={"verdict": "mining", "mining_3d": 80,
                                                                       "path_text": "x"}))
    assert [f["key"] for f in ok["findings"]] == ["gpu_bound", "render_ok"], ok["findings"]
    plain = M.summarize(samples, {"ram_gb": 16}, "game.exe", {})
    assert "render_ok" not in [f["key"] for f in plain["findings"]] and plain["frames"] == {}


# ── Game Booster 2.0 ──
def test_booster_profiles_are_presets_of_existing_switches():
    import features as F
    old = dict(F.CFG["booster"]), list(F.CFG["games"] or [])
    try:
        b = dict(F.CFG["booster"], profile="custom", kill=True, prio=False)
        F.CFG["booster"] = b
        assert F.boost_profile() == "custom" and F.boost_options()["kill"] is True
        F.CFG["booster"] = dict(b, profile="stable")
        o = F.boost_options()
        assert o["kill"] is False and o["prio"] is False and o["purge"] is True
        F.CFG["games"] = [{"path": r"C:\G\game.exe", "profile": "latency"}]
        assert F.boost_profile(r"c:\g\GAME.exe") == "latency" and F.boost_options(r"C:\G\game.exe")["prio"] is True
        assert set(F.BOOST_PROFILES["latency"]) == set(F.BOOST_KEYS) | {"prio"}
    finally:
        F.CFG["booster"], F.CFG["games"] = old


def test_fso_is_blocked_on_mining_pcs():
    import engine as E
    t = E.BY_ID["fso_global"]
    assert E.compat(t, {"mining_display": "P106-100"})[0] == "block"
    assert E.compat(t, {})[0] == "ok"


# ── режими рендерингу на фальшивій Windows ──
_CACHE = {}


def fake() -> dict:
    if IS_WIN:
        skip("fake Windows runs only outside Windows")
    if "r" not in _CACHE:
        out = tempfile.mkdtemp(prefix="oxgr_")
        env = dict(os.environ, FAKE_HW="gaming", FAKE_TARGET=os.path.join(SCRIPTS, "renderer_fake.py"),
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fake_windows.py"), "--out", out], cwd=ROOT,
                           env=env, capture_output=True, timeout=600)
        text = (p.stdout + p.stderr).decode("utf-8", "replace")
        path = os.path.join(out, "renderer.json")
        assert p.returncode == 0 and os.path.exists(path), tail(text)
        with open(path, encoding="utf-8") as f:
            _CACHE["r"] = json.load(f)
    return _CACHE["r"]


def test_api_bitness_and_anticheat_detection():
    r = fake()
    assert r["apis"] == {"Arena": ["dx9:x86"], "Classic": ["dx9:x86"], "Quake": ["gl:x86"], "Racer": ["dx11:x64"]}
    assert r["anticheat"]["Arena"] == "EasyAntiCheat" and not r["anticheat"]["Classic"]


def test_compatibility_is_checked_before_any_change():
    r = fake()
    assert r["compat"] == {"classic": [], "arena": ["anticheat"], "racer_dx11": [], "racer_dx9": ["arch"]}
    assert r["compat_novk"] == ["no_vulkan"] and r["plan_novk"] == [["dxvk", ["no_vulkan"]]]
    assert r["arena_auto"] == {"blocked": [["dxvk", ["anticheat"]]], "files": [], "pref": None, "mode": "auto"}, \
        "no DLL next to an anti-cheat game, and DirectX 9 without DXVK is not assigned"


def test_auto_puts_only_dx9_libraries_of_the_right_bitness():
    r = fake()
    c = r["classic_auto"]
    assert c["files"] == ["d3d8.dll", "d3d9.dll"] and c["d3d9"] == "dxvk x86 d3d9.dll", c
    assert c["pref"] == "GpuPreference=2;" and c["mode"] == "auto" and c["status"] is True and not c["fail"]
    assert r["classic_rescue"] == 2, "every copied library has an OptimaX-Rescue.cmd line"


def test_dxvk_for_dx11_backs_up_and_restores_the_games_files():
    r = fake()
    d = r["racer_dxvk"]
    assert d["files"] == ["d3d10core.dll", "d3d11.dll", "dxgi.dll"] and d["dxgi"] == "dxvk x64 dxgi.dll"
    assert d["bak"] == "the game's own dxgi" and d["mode"] == "dxvk" and d["prev"] == "native" and d["status"]
    b = r["racer_back"]
    assert b == {"files": ["dxgi.dll"], "dxgi": "the game's own dxgi", "bak": False, "pref": "GpuPreference=2;",
                 "undone": 1}, b


def test_failed_change_returns_the_previous_mode():
    f = fake()["racer_fail"]
    assert f["rolled_back"] is True and f["mode"] == "native" and f["dxvk_ids"] == []
    assert f["dxgi"] == "the game's own dxgi" and f["pref"] == "GpuPreference=2;"


def test_mesa_zink_switch_and_original_mode():
    r = fake()
    assert r["quake_gl"]["files"] == ["libgallium_wgl.dll", "opengl32.dll"] and r["quake_gl"]["env"] == "NVIDIA"
    assert r["zink"] == "zink" and r["zink_off"] is None
    assert r["quake_original"] == {"files": [], "pref": None, "env": None, "mode": "original"}
    assert r["assign_original"] == {"original": 1, "pref": None}, "background assignment skips Original games"


def test_profiles_database_reset_and_new_games():
    r = fake()
    assert r["db"] == {"classic": "auto", "classic_src": "user", "racer_bad": ["dxvk"], "verified": "mining"}
    assert r["classic_reset"] == {"files": [], "pref": None, "profile": {}}
    assert r["exported"] >= 3 and r["imported"] == r["exported"] and r["imported_mode"] == "auto"
    assert r["new_first"] == 0 and len(r["new_second"]) == 1
    assert r["left"] == [] and r["racer_final"] == {"files": ["dxgi.dll"], "dxgi": "the game's own dxgi"}


def test_release_packs_the_same_dxvk_libraries_the_app_expects():
    sys.path.insert(0, os.path.join(ROOT, "packaging"))
    import mining as MG
    import release as REL
    assert tuple(REL.DXVK_FILES) == tuple(MG.DXVK_FILES)
    assert {n for s in MG.DXVK_SETS.values() for n in s} == set(MG.DXVK_FILES)
