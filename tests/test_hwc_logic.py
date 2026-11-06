"""Hardware Center без інтерфейсу: EDID і колірне охоплення, перевірка перед покупкою, звіти (приватність, HTML, JSON,
порівняння), фонові процеси, FPS-оверлей (кадри, режими показу, яке вікно — гра), діагностика продуктивності,
андервольтинг, розбір !analyze -v."""
import json
import os
import sys
import time

from _util import ROOT

sys.path.insert(0, ROOT)
import dumpanalyzer as DA  # noqa: E402
import hwinfo as HI  # noqa: E402
import hwreport as HR  # noqa: E402
import hwtests as HT  # noqa: E402
import inspection as IN  # noqa: E402
import overlay as OV  # noqa: E402
import perfdiag as PD  # noqa: E402
import procmon as PM  # noqa: E402


# ── EDID ──
def edid(name=b"VG27AQ", w=60, h=34, ha=2560, va=1440, clock=59750, hb=160, vb=41, primaries=None) -> bytes:
    b = bytearray(128)
    b[0:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"
    m = ((ord("A") - 64) << 10) | ((ord("U") - 64) << 5) | (ord("S") - 64)
    b[8], b[9] = m >> 8, m & 0xFF
    b[10], b[11] = 0xA1, 0x27
    b[17], b[18], b[19], b[20], b[21], b[22], b[23] = 32, 1, 4, 0x80, w, h, 120
    pr = primaries or ((0.640, 0.330), (0.300, 0.600), (0.150, 0.060), (0.3127, 0.3290))
    vals = [int(round(c * 1024)) for xy in pr for c in xy]
    b[25] = ((vals[0] & 3) << 6) | ((vals[1] & 3) << 4) | ((vals[2] & 3) << 2) | (vals[3] & 3)
    b[26] = ((vals[4] & 3) << 6) | ((vals[5] & 3) << 4) | ((vals[6] & 3) << 2) | (vals[7] & 3)
    for i, v in enumerate(vals):
        b[27 + i] = v >> 2
    d = 54
    b[d:d + 2] = clock.to_bytes(2, "little")
    b[d + 2], b[d + 3], b[d + 4] = ha & 0xFF, hb & 0xFF, ((ha >> 8) << 4) | (hb >> 8)
    b[d + 5], b[d + 6], b[d + 7] = va & 0xFF, vb & 0xFF, ((va >> 8) << 4) | (vb >> 8)
    d = 72
    b[d + 3] = 0xFC
    b[d + 5:d + 18] = (name + b"\n" + b" " * 13)[:13]
    d = 90
    b[d + 3], b[d + 5], b[d + 6] = 0xFD, 48, 165
    return bytes(b)


def test_edid_parsing():
    d = HI.parse_edid(edid())
    assert d["manufacturer"] == "AUS" and d["product"] == "27A1" and d["year"] == 2022 and d["version"] == "1.4"
    assert d["name"] == "VG27AQ" and d["native"] == (2560, 1440) and 148 < d["native_hz"] < 149
    assert d["min_hz"] == 48 and d["max_hz"] == 165 and d["diag_in"] == 27.2 and d["gamma"] == 2.2
    assert d["srgb"] >= 98, d["srgb"]
    assert 60 <= d["p3"] <= 80, d["p3"]
    assert HI.parse_edid(b"\x00" * 128) == {} and HI.parse_edid(b"") == {}


def test_wide_gamut_monitor_covers_p3():
    wide = HI.parse_edid(edid(primaries=((0.680, 0.320), (0.265, 0.690), (0.150, 0.060), (0.3127, 0.3290))))
    assert wide["p3"] >= 98 and wide["srgb"] >= 98
    narrow = HI.parse_edid(edid(primaries=((0.58, 0.34), (0.33, 0.55), (0.16, 0.10), (0.3127, 0.3290))))
    assert narrow["srgb"] < 75


def test_smbios_modules_and_na():
    assert HI.na(None) == HI.na("") == HI.na([]) and HI.na(5, "GB") == "5 GB"
    assert HI.smbios_details(b"") == {}


# ── перевірка перед покупкою ──
HW = dict(cpu="12th Gen Intel(R) Core(TM) i5-12400F", gpus=[("NVIDIA GeForce RTX 3060", 12.0, "")], ram_gb=15.8,
          disks=[dict(size_gb=512)], laptop=False)


def test_claimed_configuration():
    res = {f: st for f, _c, _a, st in IN.compare_claimed(dict(cpu="i5-12400F", gpu="RTX 3060", ram="16", disk="512 GB"), HW)}
    assert res == dict(cpu=HT.PASS, gpu=HT.PASS, ram=HT.PASS, disk=HT.PASS), res
    bad = {f: st for f, *_x, st in IN.compare_claimed(dict(cpu="i7-12700", gpu="RTX 3070", ram="32", disk="1 TB"), HW)}
    assert bad == dict(cpu=HT.FAIL, gpu=HT.FAIL, ram=HT.FAIL, disk=HT.FAIL), bad
    empty = {f: st for f, *_x, st in IN.compare_claimed({}, HW)}
    assert set(empty.values()) == {HT.SKIPPED}


def test_hybrid_laptop_needs_a_confirmed_discrete_gpu():
    ads = [dict(key="ig", kind="igpu"), dict(key="nv", kind="dgpu")]
    t0 = 1000
    ok_d = dict(ts=2000, adapter_key="nv", verdict="bench", gpu_check={"status": "confirmed"})
    ok_i = dict(ts=2001, adapter_key="ig", verdict="bench", gpu_check={"status": "confirmed"})
    wrong_d = dict(ok_d, gpu_check={"status": "wrong"})
    assert IN.gpu_status([ok_d, ok_i], t0, {}, ads) == (HT.PASS, "")
    assert IN.gpu_status([ok_d], t0, {}, ads) == (None, "insp.gpu.need_igpu")
    assert IN.gpu_status([wrong_d, ok_i], t0, {}, ads)[0] == HT.FAIL, "a dead or disabled dGPU must fail the check"
    assert IN.gpu_status([dict(ok_d, ts=10)], t0, {}, ads) == (None, ""), "runs before the check started don't count"


def test_inspection_steps_and_overall():
    sess = dict(ts=100, claimed={}, manual={"display": HT.PASS}, skipped=["av"])
    last = {"cpu_multi": dict(status=HT.PASS, ts=200), "ram": dict(status=HT.FAIL, ts=50)}
    assert IN.step_status("cpu", sess, last, HW)[0] == HT.PASS
    assert IN.step_status("ram", sess, last, HW)[0] is None, "a result older than the session is ignored"
    assert IN.step_status("display", sess, last, HW)[0] == HT.PASS
    assert IN.step_status("av", sess, last, HW)[0] == HT.SKIPPED
    assert IN.step_status("battery", sess, last, HW)[0] == HT.NA
    sts = {"cpu": HT.PASS, "display": HT.PASS, "disk_bench": HT.WARN}
    assert IN.overall(sts) == HT.WARN and IN.progress(sts) == (3, len(IN.STEPS) - 1)


# ── звіти ──
def test_report_privacy_and_formats():
    os.environ["COMPUTERNAME"] = "IVAN-PC-777"
    os.environ["USERNAME"] = "IvanUser"
    last = {"cpu_multi": HT.result("cpu_multi", HT.PASS, "ok", rows=[("hwc.r.score", 900)],
                                   findings=[(HT.WARN, "hwc.f.cpu_hot", dict(t=91))], note="C:\\Users\\IvanUser\\x"),
            "disk_bench": HT.result("disk_bench", HT.FAIL, "slow")}
    rep = HR.build(dict(cpu="CPU X", gpus=[("GPU Y", 8.0, "")], ram_gb=16, disks=[]), None, last)
    blob = json.dumps(rep)
    assert "IVAN-PC-777" not in blob and "IvanUser" not in blob and rep["computer"] is None
    assert rep["status"] == HT.FAIL and rep["recommendations"]
    named = HR.build({}, None, last, include_name=True)
    assert named["computer"] == "IVAN-PC-777"
    html = HR.to_html(rep)
    assert "<html" in html and "CPU X" in html and "IvanUser" not in html
    pdf_html = HR.to_html(rep, for_pdf=True)
    assert "<svg" not in pdf_html


def test_report_compare_and_save(tmp_path=None):
    a = HR.build({}, None, {"cpu_multi": HT.result("cpu_multi", HT.PASS, "", score=1000)})
    b = HR.build({}, None, {"cpu_multi": HT.result("cpu_multi", HT.WARN, "", score=1100),
                            "ram": HT.result("ram", HT.PASS, "", errors=0)})
    rows = {k: (sa, sb, ch) for k, sa, sb, _va, _vb, ch in HR.compare(a, b)}
    assert rows["cpu_multi"] == (HT.PASS, HT.WARN, 10.0) and rows["ram"][0] is None
    assert "+10.0%" in HR.compare_html(a, b)

    class Cfg(dict):
        def __getitem__(self, k):
            return self.get(k)

    import tempfile
    d = tempfile.mkdtemp(prefix="oxrep_")
    cfg = Cfg()
    p = HR.save(cfg, a, "html", os.path.join(d, "r.html"))
    assert os.path.exists(p) and os.path.exists(os.path.join(d, "r.json")) and cfg["hwc_reports"][0]["json"].endswith("r.json")
    assert HR.load(os.path.join(d, "r.json"))["format"] == HR.FORMAT


# ── фонові процеси ──
def test_background_analysis_never_blames_by_load_alone():
    samples = []
    for i in range(40):
        spike = i % 10 in (4, 5)
        samples.append(dict(procs={"game.exe": (40.0, 4000, 1, 90), "updater.exe": (30.0 if spike else 1.0, 200, 0, 0),
                                   "msmpeng.exe": (6.0, 300, 0.5, 0), "chrome.exe": (0.5, 1800, 0, 0),
                                   "quiet.exe": (0.2, 50, 0, 0)}, net_kbs=50.0))
    fps = [120.0 if (i // 2) % 10 not in (4, 5) else 60.0 for i in range(80)]
    s = PM.analyze(samples, "game.exe", fps)
    by = {p["name"]: p for p in s["processes"]}
    assert "game.exe" not in by and "quiet.exe" not in by
    assert by["updater.exe"]["suspect"] and by["updater.exe"]["overlap"] >= 0.5
    assert by["msmpeng.exe"]["kind"] == "antivirus" and by["msmpeng.exe"]["advice"] == ["keep", "exclude"]
    assert by["chrome.exe"]["reason"] == "ram" and not by["chrome.exe"]["suspect"]
    assert PM.kind_of("svchost.exe") == "system" and PM.advice_for("system", "cpu") == ["keep"]
    assert PM.session_result(s)["status"] == HT.WARN
    assert PM.analyze([], "x")["processes"] == []


# ── FPS-оверлей ──
def test_overlay_window_stats():
    now = 100.0
    frames = [(now - 10 + i * 0.01, 10.0) for i in range(1000)]
    frames[500] = (frames[500][0], 50.0)
    st = OV.window_stats(frames, now)
    assert 95 <= st["fps"] <= 101 and 95 <= st["avg"] <= 100 and st["low1"] < st["avg"] and st["low01"] <= st["low1"]
    assert OV.window_stats([]) == {}


def test_presentmon_stream_rows():
    rows = OV.CsvRows()
    assert rows.feed("Application,ProcessID,SwapChainAddress,PresentRuntime,PresentMode,MsBetweenPresents") is None
    assert rows.feed("cs2.exe,1234,0x1,DXGI,Hardware: Independent Flip,6.94") == (6.94, "Hardware: Independent Flip",
                                                                                  "1234", "cs2.exe")
    assert rows.feed("garbage") is None and rows.feed("") is None
    v2 = OV.CsvRows()
    v2.feed("Application,ProcessID,PresentMode,FrameTime")
    assert v2.feed("game.exe,9,Composed: Flip,16.6")[0] == 16.6


def test_present_modes():
    assert OV.is_exclusive("Hardware: Legacy Flip") and not OV.is_exclusive("Hardware: Independent Flip")
    assert OV.flip_downgrade("Hardware: Independent Flip", "Composed: Flip")
    assert not OV.flip_downgrade("Composed: Flip", "Composed: Flip")
    assert not OV.flip_downgrade("Hardware: Independent Flip", "Hardware Composed: Independent Flip")


def test_which_window_is_a_game():
    cfg = dict(auto=True, white=["tool.exe"], black=["cs2.exe"])
    known = {"cs2.exe", "eldenring.exe"}
    assert OV.is_game(dict(exe="eldenring.exe", full=False), known, cfg)
    assert not OV.is_game(dict(exe="cs2.exe", full=True), known, cfg), "the blacklist wins"
    assert OV.is_game(dict(exe="tool.exe", full=False), known, cfg)
    assert not OV.is_game(dict(exe="chrome.exe", full=True), known, cfg), "never over a browser"
    assert OV.is_game(dict(exe="unknown.exe", full=True), known, cfg)
    assert not OV.is_game(dict(exe="unknown.exe", full=True), known, dict(cfg, auto=False))
    assert not OV.is_game({}, known, cfg)


def test_overlay_lines():
    st = dict(fps=143, avg=140.2, low1=98.0, low01=71.0, ft=6.9)
    s = dict(util=55, temp=71, gpu_util=97, gpu_temp=68, mhz=4800, gpu_clock=2600, vram_used=6144, vram_total=8192,
             ram_used=11.2, ram_total=32, gpu_power=160)
    assert [t for t, _ in OV.overlay_lines("minimal", st, s, {})] == ["143 FPS"]
    std = OV.overlay_lines("standard", st, s, {})
    assert len(std) == 4 and "98" in std[1][0]
    ext = OV.overlay_lines("extended", st, s, dict(gpu="RTX 4060", mode="Composed: Flip"))
    assert any("VRAM 6.0/8.0" in t for t, _ in ext) and ext[-1] == ("Composed: Flip", "warn")
    assert OV.overlay_lines("standard", {}, {}, {})[0][0] == "— FPS"


# ── діагностика продуктивності ──
def test_performance_diagnosis():
    gpu_bound = [dict(util=40, gpu_util=99, temp=60, passive=100, limit=100, ram_used=8, ram_total=32)] * 40
    keys = [d["key"] for d in PD.diagnose(gpu_bound, {"avg": 120})]
    assert keys[0] == "gpu"
    hot = [dict(util=90, gpu_util=60, temp=96, passive=80, limit=80)] * 40
    assert PD.diagnose(hot)[0]["key"] == "thermal"
    full_vram = [dict(util=50, gpu_util=95, vram_used=7990, vram_total=8192)] * 20
    assert "vram" in [d["key"] for d in PD.diagnose(full_vram)]
    igpu = PD.diagnose([], render={"verdict": "igpu", "path_text": "DirectX 11 · Intel"})
    assert igpu[0]["key"] == "igpu" and igpu[0]["conf"] == "high"
    bg = PD.diagnose([], procs={"processes": [dict(name="x.exe", suspect=True)]})
    assert bg[0]["key"] == "background"
    ex = PD.explain(PD.diagnose(gpu_bound)[0])
    assert ex["title"] and ex["do"] and ex["risk"] and ex["evidence"]


def test_undervolt_advice_never_automatic():
    hot = dict(findings=[(HT.WARN, "hwc.f.thermal", {})])
    a = PD.undervolt_advice(dict(cpu="13th Gen Intel(R) Core(TM) i7-13700H"), hot)
    assert a["state"] == "locked_likely" and a["need"] and "uv.s.verify" in a["steps"]
    d = PD.undervolt_advice(dict(cpu="AMD Ryzen 7 7800X3D 8-Core Processor"), dict(findings=[]))
    assert d["state"] == "curve_optimizer" and not d["need"] and "uv.r.fine" in d["reasons"]
    assert PD.undervolt_advice({})["reasons"] == ["uv.r.no_test"]
    assert PD.cpu_family("Intel(R) Core(TM) i7-8750H CPU")["state"] == "possible"


# ── дампи ──
def test_analyze_output_parsing():
    a = DA.parse_analyze(DA.DEMO_ANALYZE)
    assert a["code"] == 0x116 and a["module_name"] == "nvlddmkm" and a["image_name"] == "nvlddmkm.sys"
    assert a["suspect"] == "nvlddmkm.sys" and a["failure_bucket_id"].startswith("0x116") and len(a["stack"]) == 2
    b = DA.parse_analyze("BugCheck 3B, {c0000005, ...}\nProbably caused by : ntkrnlmp.exe ( nt!x )\n")
    assert b["code"] == 0x3B and b["suspect"] == "" and b["probably"] == "ntkrnlmp.exe"
    assert DA.parse_analyze("")["code"] == 0
    assert "Debuggers" in DA.cdb_candidates()[3]
