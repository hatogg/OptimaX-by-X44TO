"""Тест затримки системи: розбір подій ядра (DPC / ISR / модулі), статистика й висновок, справжній вимір зупинок
програми на Windows і (з правами адміністратора — у CI) справжня сесія журналу подій ядра."""
import json
import os
import struct
import subprocess
import sys
import tempfile
import uuid

from _util import ROOT, IS_WIN, skip

sys.path.insert(0, ROOT)
import hwtests as HT  # noqa: E402
import latencytest as LT  # noqa: E402


def child(*args, timeout: int = 120) -> dict:
    out = os.path.join(tempfile.mkdtemp(prefix="oxlat_"), "s.json")
    e = dict(os.environ, APPDATA=tempfile.mkdtemp(prefix="oxt_"))
    p = subprocess.run([sys.executable, os.path.join(ROOT, "optimizer.py"), *args, f"--out={out}"], cwd=ROOT, env=e,
                       capture_output=True, timeout=timeout)
    assert p.returncode == 0, p.stdout + p.stderr
    with open(out, encoding="utf-8") as f:
        return json.load(f)


# ── розбір подій ──
def _record(ts: int, cls: bytes, opcode: int, cpu: int, ulen: int, uptr: int, flags: int = 0) -> bytes:
    rec = bytearray(112)
    struct.pack_into("<H", rec, 4, flags)
    struct.pack_into("<q", rec, 16, ts)
    rec[24:40] = cls
    rec[45] = opcode
    rec[80] = cpu
    struct.pack_into("<H", rec, 86, ulen)
    struct.pack_into("<Q", rec, 96, uptr)
    return bytes(rec)


def test_decode_event_record_header():
    rec = _record(123456789, LT.PERFINFO_GUID, 68, 5, 16, 0xDEADBEEF)
    ts, cls, op, cpu, flags, ulen, uptr = LT.decode_header(rec)
    assert (ts, cls, op, cpu, flags, ulen, uptr) == (123456789, LT.PERFINFO_GUID, 68, 5, 0, 16, 0xDEADBEEF)
    # клас подій — GUID у порядку байтів Windows (bytes_le), як у EVENT_HEADER.ProviderId
    assert LT.PERFINFO_GUID == uuid.UUID("ce1dbfb4-137e-4da6-87b0-3f59aa102cbc").bytes_le


def test_decode_dpc_and_image_payloads():
    assert LT.decode_exec(struct.pack("<qQ", 1000, 0xFFFFF80012345678)) == (1000, 0xFFFFF80012345678)
    assert LT.decode_exec(struct.pack("<qI", 7, 0x8123), ptr32=True) == (7, 0x8123)
    name = "\\SystemRoot\\System32\\drivers\\ndis.sys".encode("utf-16-le") + b"\x00\x00"
    data = struct.pack("<QQIIIIQIIII", 0xFFFFF80000000000, 0x100000, 0, 0, 0, 0, 0, 0, 0, 0, 0) + name
    assert LT.decode_image(data) == (0xFFFFF80000000000, 0x100000, 0, "\\SystemRoot\\System32\\drivers\\ndis.sys")


def test_driver_map_and_kinds():
    m = LT.DriverMap([(0x1000, "ntoskrnl.exe"), (0x9000, r"\SystemRoot\system32\drivers\ndis.sys", 0x1000)])
    assert m.lookup(0x1500) == "ntoskrnl.exe"
    assert m.lookup(0x9800) == "ndis.sys"
    assert m.lookup(0xA800) == ""          # за межами відомого розміру — не вгадуємо
    assert m.lookup(0x10) == ""
    m.add(0x9000, "ndis.sys", 0x4000)      # той самий модуль із ETW — нічого не дублюється
    assert len(m) == 2
    assert LT.driver_kind("Netwtw10.sys") == "net"
    assert LT.driver_kind("nvlddmkm.sys") == "gpu"
    assert LT.driver_kind("HDAudBus.sys") == "audio"
    assert LT.driver_kind("Wdf01000.sys") == "wdf"
    assert LT.driver_kind("storport.sys") == "storage"
    assert LT.driver_kind("ntoskrnl.exe") == "system"
    assert LT.driver_kind("mystery.sys") == "other"
    assert set(LT.KINDS) >= {"net", "gpu", "audio", "storage", "usb", "power", "security", "wdf", "system", "other"}


def test_exec_stats_per_routine_per_second_and_bad_values():
    freq = 10_000_000  # 0.1 мкс на тік
    s = LT.ExecStats(freq)
    t = 1_000_000_000
    s.add(False, t + 1000, t, 0xA000, 0)              # DPC 100 мкс
    s.add(True, t + 500, t + 100, 0xB000, 1)          # ISR 40 мкс
    s.add(False, t + 30_000, t + 5_000, 0xA010, 0)    # DPC 2500 мкс тієї ж процедури-драйвера
    s.add(False, t + 15_000_000, t + 14_999_000, 0xA000, 0)  # через 1.5 с
    s.add(False, t, t + 10, 0xA000, 0)                # від'ємна тривалість — пропуск
    s.finish()
    assert s.bad == 1
    assert s.count == {"isr": 1, "dpc": 3}
    assert round(s.max["dpc"]) == 2500 and round(s.max["isr"]) == 40
    assert s.series_max[0] == 2500.0 and len(s.series_max) == 2
    assert s.series_pct[0] > 0
    d = s.drivers(LT.DriverMap([(0xA000, "ndis.sys", 0x100), (0xB000, "HDAudBus.sys", 0x100)]))
    assert d[0]["name"] == "ndis.sys" and d[0]["kind"] == "net" and d[0]["dpc_n"] == 3 and d[0]["dpc_max"] == 2500.0
    assert d[1]["name"] == "HDAudBus.sys" and d[1]["isr_n"] == 1
    assert sum(s.hist["dpc"]) == 3 and s.hist["dpc"][LT.bucket(2500)] == 1


def test_bursts_join_back_to_back_and_nested_events_per_core():
    s = LT.ExecStats(10_000_000)  # 0.1 мкс на тік
    t = 5_000_000_000
    s.add(True, t + 3_000, t + 2_000, 0xB000, 0)       # ISR 100 мкс усередині DPC (записується першим)
    s.add(False, t + 8_000, t, 0xA000, 0)              # DPC 800 мкс
    s.add(False, t + 14_000, t + 8_100, 0xA000, 0)     # одразу за ним (через 10 мкс) — 590 мкс
    s.add(False, t + 50_000, t + 45_000, 0xA000, 0)    # окремо, через 3.1 мс
    s.add(False, t + 9_000, t + 1_000, 0xC000, 1)      # інше ядро — своя серія
    assert round(s.burst_max) == 1400 and round(s.core_burst[0]) == 1400 and round(s.core_burst[1]) == 800
    assert round(s.max["dpc"]) == 800                  # найдовший окремий DPC — менший за серію


def test_stall_stats_per_second_and_core():
    s = LT.StallStats(4)
    for us, core in ((15.0, 0), (1500.0, 0), (40.0, 1)):
        s.add(us, core)
    s.second(1_000_000.0)
    s.add(300.0, 2)
    s.second(1_000_000.0)
    st = s.state()
    assert st["max_us"] == 1500.0 and st["over"] == 1 and st["stalls"] == 4
    assert st["series"] == [1500.0, 300.0] and st["core_max"] == [1500.0, 40.0, 300.0, 0.0]
    assert st["lost_pct"] == round(100 * 1855.0 / 2_000_000.0, 3) and sum(st["hist"]) == 4
    assert LT.StallStats(2).state()["lost_pct"] is None


# ── висновок ──
def _timer(max_us, over=0):
    return dict(state="done", max_us=max_us, over=over, stalls=500, lost_pct=0.05, t=60.0, cores=8,
                core_max=[max_us] * 8, series=[max_us] * 60)


def _etw(drivers, lost=0):
    mx = max([max(d["dpc_max"], d["isr_max"]) for d in drivers] or [0])
    return dict(state="done", isr_n=100, dpc_n=5000, isr_max=max((d["isr_max"] for d in drivers), default=0),
                dpc_max=max((d["dpc_max"] for d in drivers), default=0), drivers=drivers, events_lost=lost,
                series_max=[mx] * 60, series_pct=[0.5] * 60, t=60.0)


def _drv(name, dpc=0.0, isr=0.0):
    return dict(name=name, kind=LT.driver_kind(name), dpc_n=10, dpc_max=dpc, dpc_sum=1, isr_n=5, isr_max=isr,
                isr_sum=1)


def test_result_pass_warn_fail():
    ok = LT.latency_result({"stall": _timer(300), "etw": _etw([_drv("nvlddmkm.sys", 200), _drv("ACPI.sys", 0, 40)])})
    assert ok["status"] == HT.PASS and not [f for f in ok["findings"] if f[0] in (HT.WARN, HT.FAIL)]
    assert ok["series"]["lat"] and ok["series"]["dpc"]
    warn = LT.latency_result({"stall": _timer(1500, over=3), "etw": _etw([_drv("ndis.sys", 1200)])})
    assert warn["status"] == HT.WARN
    keys = [f[1] for f in warn["findings"]]
    assert "lat.f.stall" in keys and "lat.f.driver" in keys and "lat.adv.net" in keys
    assert "lat.adv.stall_other" not in keys      # зупинка пояснюється довгим DPC мережі
    bad = LT.latency_result({"stall": _timer(800), "etw": _etw([_drv("storport.sys", 5200)], lost=12)})
    assert bad["status"] == HT.FAIL and bad["top_driver"] == "storport.sys"
    assert "lat.f.lost" in [f[1] for f in bad["findings"]]
    other = LT.latency_result({"stall": _timer(3000, over=2), "etw": _etw([_drv("ndis.sys", 300)])})
    assert "lat.adv.stall_other" in [f[1] for f in other["findings"]]  # драйвери короткі — винне щось інше
    chain = LT.latency_result({"stall": _timer(3000, over=2), "etw": dict(_etw([_drv("ACPI.sys", 1800)]),
                                                                           burst_max=2600.0)})
    assert "lat.adv.stall_other" not in [f[1] for f in chain["findings"]]  # зупинку пояснює серія DPC поспіль
    assert dict(chain["rows"])["lat.r.burst"]
    for r in (ok, warn, bad, other):
        for f in r["findings"]:
            assert HT.finding_str(f)  # кожен висновок перекладено й підстановки збігаються


def test_result_without_admin_or_with_busy_log_is_honest():
    r = LT.latency_result({"stall": _timer(400)}, admin=False)
    assert r["status"] == HT.PASS and "lat.f.no_admin" in [f[1] for f in r["findings"]]
    assert dict(r["rows"])["lat.r.dpc_max"] is None  # не вимірювали — не показуємо нуль
    busy = LT.latency_result({"stall": _timer(400), "etw": dict(state="error", error="busy")})
    assert "lat.f.etw_busy" in [f[1] for f in busy["findings"]]
    none = LT.latency_result({"stall": dict(state="crash", exit_code=1)}, admin=False)
    assert none["status"] == HT.NA and "lat.f.stall_err" in [f[1] for f in none["findings"]]


def test_demo_states_feed_the_result():
    for demo in ("gaming", "old"):
        old, LT.E.DEMO = LT.E.DEMO, demo
        try:
            st = {"stall": LT.demo_state("latency_stall", 60, 60, True),
                  "etw": LT.demo_state("latency_etw", 60, 60, True)}
        finally:
            LT.E.DEMO = old
        r = LT.latency_result(st)
        assert r["status"] == (HT.PASS if demo == "gaming" else HT.WARN), (demo, r["findings"])
        text, done, total = LT.describe(dict(st, etw=dict(st["etw"], state="running")), 60)
        assert total == 60 and "{" not in text


# ── справжній вимір на Windows ──
def test_stall_child_measures_every_core_on_windows():
    if not IS_WIN:
        skip("вимір зупинок — лише Windows (прив'язка потоку до ядра)")
    st = child("--hw-test=latency_stall", "--seconds=3")
    assert st["state"] == "done" and len(st["series"]) == 3, st     # щосекунди — точка графіка
    assert st["cores"] == max(1, min(64, os.cpu_count() or 1)) and len(st["core_max"]) == st["cores"], st
    assert 0 <= st["max_us"] < 1e6 and st["stalls"] == sum(st["hist"]), st
    assert st["lost_pct"] is not None and 0 <= st["lost_pct"] < 50, st


def test_etw_child_without_admin_says_so():
    if not IS_WIN:
        skip("журнал подій ядра — лише Windows")
    import engine as E
    if E.is_admin():
        skip("процес має права адміністратора")
    st = child("--hw-test=latency_etw", "--seconds=2")
    assert st["state"] == "error" and st["error"] == "admin", st


def test_etw_child_records_dpc_and_isr_with_drivers():
    """Справжня сесія журналу подій ядра (лише з правами адміністратора — у CI на Windows Server). Лише читає
    події; сесія зупиняється наприкінці, тож після тесту її не лишається."""
    if not IS_WIN:
        skip("журнал подій ядра — лише Windows")
    import engine as E
    if not E.is_admin():
        skip("потрібні права адміністратора (працює в CI)")
    st = child("--hw-test=latency_etw", "--seconds=4")
    assert st["state"] == "done", st
    assert st["events"] > 0 and st["dpc_n"] > 0, st                 # таймерні DPC є на будь-якій системі
    assert st["modules"] > 20, st                                   # модулі ядра відомі
    assert st["drivers"] and any(d["name"] != "?" for d in st["drivers"]), st["drivers"]
    assert 0 < st["dpc_max"] < 1e6 and st["bad"] < max(10, st["dpc_n"] // 100), st
    assert not LT.stop_leftover(), "сесія «OptimaX Latency» лишилася після тесту"
    r = LT.latency_result({"stall": _timer(300), "etw": st})
    assert r["status"] in (HT.PASS, HT.WARN, HT.FAIL) and r["drivers"]
