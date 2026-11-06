"""Hardware Center: тести процесора, пам'яті й диска в окремих процесах (справжні процеси й на Linux), розбір SMART і
NVMe, висновки з датчиків (тротлінг, ліміт потужності, перегрів), перевірка відеопам'яті на справжньому OpenGL."""
import json
import os
import subprocess
import struct
import sys
import tempfile

from _util import ROOT, run_script, skip, tail

sys.path.insert(0, ROOT)
import hwtests as HT  # noqa: E402
import storagehealth as SH  # noqa: E402
import vramtest as VT  # noqa: E402


def child(*args, env: dict = None, timeout: int = 120) -> dict:
    out = os.path.join(tempfile.mkdtemp(prefix="oxhw_"), "s.json")
    e = dict(os.environ, APPDATA=tempfile.mkdtemp(prefix="oxt_"), **(env or {}))
    p = subprocess.run([sys.executable, os.path.join(ROOT, "optimizer.py"), *args, f"--out={out}"], cwd=ROOT, env=e,
                       capture_output=True, timeout=timeout)
    assert p.returncode == 0, p.stdout + p.stderr
    with open(out, encoding="utf-8") as f:
        return json.load(f)


# ── процесор ──
def test_cpu_child_loads_threads_and_checks_itself():
    st = child("--hw-test=cpu", "--threads=2", "--seconds=4")
    assert st["state"] == "done" and st["threads"] == 2 and st["errors"] == 0, st
    assert st["score"] > 0 and st["per_thread"] > 0 and len(st["series"]) >= 3


def test_cpu_wrong_answer_is_an_error_not_a_pass():
    st = child("--hw-test=cpu", "--threads=1", "--seconds=3", env={"OPTIMAX_TEST_CPU_FAULT": "1"})
    assert st["errors"] == 1 and st["first_error"]["thread"] == 0, st
    r = HT.cpu_result(st, [], {"mhz": 3000}, "multi")
    assert r["status"] == HT.FAIL and any(k == "hwc.f.cpu_errors" for _, k, _ in r["findings"])


def test_cpu_reference_is_majority_vote():
    data = b"x" * (1 << 20)
    ref = HT.cpu_reference(data)
    assert ref == HT.cpu_unit(data) and len(ref) == 3 and ref[2] != -1


def _load(n, mhz, limit=100.0, passive=100.0, temp=70.0):
    return [dict(util=99.0, mhz=m, perf=None, limit=limit, passive=passive, temp=temp) for m in mhz] if \
        isinstance(mhz, list) else [dict(util=99.0, mhz=mhz, limit=limit, passive=passive, temp=temp)] * n


def test_findings_thermal_power_and_unstable_clock():
    keys = lambda f: {k for _, k, _ in f}  # noqa: E731
    steady = _load(20, 4500)
    assert keys(HT.cpu_findings(steady)) == set()
    drop = _load(0, [4500] * 6 + [3800] * 14, passive=90.0, temp=94.0)
    k = keys(HT.cpu_findings(drop))
    assert {"hwc.f.clock_drop", "hwc.f.thermal", "hwc.f.cpu_hot"} <= k and "hwc.f.power_limit" not in k, k
    power = _load(20, 3600, limit=78.0, temp=72.0)
    assert "hwc.f.power_limit" in keys(HT.cpu_findings(power)), "a firmware limit without heat is Power Limit"
    jumpy = _load(0, [4500, 2200] * 10)
    assert "hwc.f.clock_unstable" in keys(HT.cpu_findings(jumpy))
    no_temp = [dict(util=99.0, mhz=4000, limit=100.0, passive=None, temp=None)] * 10
    assert "hwc.f.no_cpu_temp" in keys(HT.cpu_findings(no_temp)), "missing sensor is said, not invented"
    assert HT.cpu_findings([dict(util=5.0)] * 30) == [], "idle samples prove nothing"


def test_emergency_stop_needs_several_hot_seconds():
    hot = dict(temp=HT.CPU_TEMP_STOP + 1)
    assert HT.danger([hot, hot]) == ""
    assert HT.danger([dict(temp=50)] * 5 + [hot] * HT.HOT_SECONDS) == "cpu"
    assert HT.danger([dict(gpu_temp=HT.GPU_TEMP_STOP)] * HT.HOT_SECONDS) == "gpu"
    assert HT.danger([hot, dict(temp=60), hot]) == ""


def test_worst_status():
    assert HT.worst([HT.PASS, HT.WARN, HT.NA]) == HT.WARN
    assert HT.worst([HT.PASS, HT.FAIL, HT.WARN]) == HT.FAIL
    assert HT.worst([HT.SKIPPED, HT.NA]) == HT.SKIPPED
    assert HT.worst([]) == HT.NA


# ── пам'ять ──
def test_ram_child_patterns_and_flipped_bit():
    st = child("--hw-test=ram", "--mb=128")
    assert st["state"] == "done" and st["errors"] == 0 and st["mb"] == 128, st
    assert st["done_mb"] == st["total_mb"] == 128 * 2 * len(HT.ram_patterns())
    bad = child("--hw-test=ram", "--mb=128", env={"OPTIMAX_TEST_RAM_FAULT": "random:1:5"})
    assert bad["errors"] == 1 and bad["bad_bytes"] == 1 and bad["log"][0]["chunk"] == 1, bad
    r = HT.ram_result(bad, {"ram_gb": 16}, 9000)
    assert r["status"] == HT.FAIL


def test_ram_plan_leaves_room_for_windows():
    assert HT.ram_plan(8000, 50) == 3968
    assert HT.ram_plan(2000, 75) == 448, "only what is above the reserve"
    assert HT.ram_plan(1200, 75) == 0
    assert all(HT.ram_plan(a, p) % 64 == 0 for a in (3000, 12345, 64000) for p in HT.RAM_CHOICES)


# ── диск ──
def test_disk_benchmark_uses_only_its_own_file_and_cleans_up():
    base = tempfile.mkdtemp(prefix="oxdisk_")
    folder = os.path.join(base, HT.DISK_DIR)
    keep = os.path.join(base, "user.txt")
    with open(keep, "w") as f:
        f.write("user data")
    st = child("--hw-test=disk", f"--dir={folder}", "--mb=32", "--rand_seconds=1")
    assert st["state"] == "done", st
    r = st["result"]
    assert r["seq_read"] > 0 and r["seq_write"] > 0 and r["rand_read"]["iops"] > 0 and r["rand_write"]["iops"] > 0
    assert st["cleaned"] and not os.path.exists(folder), "the test folder and file must be gone"
    assert open(keep).read() == "user data" and os.listdir(base) == ["user.txt"]
    res = HT.disk_result(st, {"media": "SSD", "name": "X"})
    assert res["status"] in (HT.PASS, HT.WARN) and res["bench"] == r


def test_disk_refuses_when_space_is_short():
    assert not HT.disk_size_ok(3000, 1024)
    assert HT.disk_size_ok(10000, 1024)
    st = HT.disk_result(dict(state="error", error="space"), {})
    assert st["status"] == HT.NA and st["findings"][0][1] == "hwc.f.disk_space"


def test_remove_own_never_touches_other_files():
    base = tempfile.mkdtemp(prefix="oxdisk_")
    folder = os.path.join(base, HT.DISK_DIR)
    os.makedirs(folder)
    other = os.path.join(folder, "notes.txt")
    open(other, "w").close()
    HT._remove_own(other, folder)
    assert os.path.exists(other), "only bench-*.tmp files are ever deleted"
    HT._remove_own(os.path.join(folder, "bench-1.tmp"), folder)
    assert os.path.exists(folder), "a non-empty folder stays"


# ── SMART / NVMe ──
def nvme_log(**kw) -> bytes:
    b = bytearray(512)
    b[0] = kw.get("warn", 0)
    struct.pack_into("<H", b, 1, kw.get("temp_k", 315))
    b[3], b[4], b[5] = kw.get("spare", 100), kw.get("spare_thr", 10), kw.get("used", 4)
    for off, key in ((48, "written"), (112, "cycles"), (128, "hours"), (144, "unsafe"), (160, "media")):
        b[off:off + 16] = int(kw.get(key, 0)).to_bytes(16, "little")
    return bytes(b)


def test_nvme_health_parsing():
    d = SH.parse_nvme_health(nvme_log(written=40_000_000, hours=3120, cycles=812, unsafe=21))
    assert d["temperature"] == 42 and d["spare"] == 100 and d["percentage_used"] == 4
    assert d["tb_written"] == 20.48 and d["power_on_hours"] == 3120 and d["unsafe_shutdowns"] == 21
    assert d["warnings"] == [] and d["media_errors"] == 0
    bad = SH.parse_nvme_health(nvme_log(warn=0b1001, spare=3, media=2))
    assert bad["warnings"] == ["spare", "read_only"]
    a = SH.assess(dict(media="NVMe", nvme=bad))
    assert a["status"] == HT.FAIL
    assert SH.assess(dict(media="NVMe", nvme=d))["status"] == HT.PASS


def ata_pages(attrs: dict, thr: dict) -> tuple:
    v, t = bytearray(512), bytearray(512)
    for i, (aid, (cur, raw)) in enumerate(attrs.items()):
        o = 2 + 12 * i
        v[o], v[o + 3], v[o + 4] = aid, cur, cur
        v[o + 5:o + 11] = raw.to_bytes(6, "little")
        t[o], t[o + 1] = aid, thr.get(aid, 0)
    return bytes(v), bytes(t)


def test_ata_smart_parsing_and_verdicts():
    v, t = ata_pages({5: (100, 0), 9: (90, 21840), 12: (95, 3911), 194: (56, 44), 197: (100, 0), 199: (200, 0),
                      241: (99, 2_000_000_000)}, {5: 36, 197: 0})
    s = SH.ata_summary(SH.parse_ata_smart(v, t))
    assert s["power_on_hours"] == 21840 and s["temperature"] == 44 and s["tb_written"] == 1.02 and s["failing"] == []
    assert SH.assess(dict(media="HDD", ata=s))["status"] == HT.PASS
    v2, t2 = ata_pages({5: (100, 8), 197: (100, 2), 199: (200, 3)}, {})
    s2 = SH.ata_summary(SH.parse_ata_smart(v2, t2))
    keys = {k for _, k, _ in SH.assess(dict(media="HDD", ata=s2))["findings"]}
    assert {"sh.f.reallocated", "sh.f.pending", "sh.f.crc"} <= keys
    v3, t3 = ata_pages({5: (30, 1200)}, {5: 36})
    s3 = SH.ata_summary(SH.parse_ata_smart(v3, t3))
    assert s3["failing"] == ["reallocated"] and SH.assess(dict(ata=s3))["status"] == HT.FAIL


def test_unknown_disk_is_na_not_pass():
    assert SH.assess({})["status"] == HT.NA
    rows = dict(SH.rows({}))
    assert rows["sh.r.temp"] is None and rows["sh.r.hours"] is None, "nothing reported means N/A, not zero"
    win_only = SH.assess(dict(media="SSD", health="Healthy", wear=3, temp=38))
    assert win_only["status"] == HT.PASS and any(k == "sh.f.no_smart" for _, k, _ in win_only["findings"])


# ── відеопам'ять ──
def test_vram_plan():
    assert VT.plan_mb(6000, 8192, 50, False) == 2944, "half of the free memory, in whole 64 MB buffers"
    assert VT.plan_mb(0, 8192, 75, False) == 6144, "without a free-memory figure the card size is used"
    assert VT.plan_mb(600, 1024, 75, False) == 192, "small free memory: half of what is free"
    assert VT.plan_mb(7000, 0, 75, True) == VT.IGPU_MAX_MB, "integrated graphics: its 'VRAM' is system RAM"


def test_vram_on_real_opengl_finds_a_flipped_byte():
    rc, out, r = run_script("vram_gl.py", timeout=600)
    assert rc == 0 and r, tail(out)
    if r.get("skip"):
        skip(r["skip"])
    assert r["clean"] == dict(errors=0, mb=192, done=36, total=36, state="done"), r["clean"]
    assert r["found"] == 1 and r["bad_bytes"] == 1 and r["log"][0]["block"] == 3, r
    assert r["gl_error"] == 0
