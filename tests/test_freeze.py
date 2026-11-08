"""OptimaX 6.12: «Чому зависає?» — вартовий, чорна скринька, журнал, вердикт, TPM, профіль WPR, процес-ловець."""
import json
import os
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET

from _util import IS_WIN, ROOT, skip

sys.path.insert(0, ROOT)
import freezecatch as FZ  # noqa: E402
import i18n  # noqa: E402


# ── вартовий ──
class FakeTime:
    """Годинник і сон для Watchdog: кожен сон рухає час на тривалість сну плюс заплановані «зупинки системи»."""

    def __init__(self):
        self.t = 0.0
        self.stalls = {}  # номер кроку -> на скільки секунд «зависла» система

    def clock(self):
        return self.t

    def sleep(self, d):
        self.n = getattr(self, "n", 0) + 1
        self.t += d + self.stalls.get(self.n, 0.0)


def test_watchdog_catches_stalls_but_not_warmup_jitter_or_sleep():
    ft = FakeTime()
    ft.stalls = {5: 2.0,          # під час розігріву (перші 10 с) — не фриз
                 400: 0.3,        # коротше за поріг — звичайне планування
                 600: 3.2,        # фриз
                 800: 0.51,       # ледь довше за поріг — фриз
                 1000: 900.0}     # 15 хвилин — сон чи modern standby, а не фриз
    dog = FZ.Watchdog(ft.clock, ft.sleep)
    got = [(i + 1, round(r, 2)) for i, r in enumerate(dog.step() for _ in range(1100)) if r is not None]
    assert got == [(600, 3.2), (800, 0.51)], got


# ── чорна скринька ──
def test_box_sample_picks_the_hottest_core():
    raw = {"dpc": 3.04, "isr": 0.5, "cpu": 21.0, "didle": 97.0, "avail_mb": 8123.4,
           "core_dpc": {"0": 40.0, "1": 1.0, "_Total": 5.0}, "core_isr": {"0": 12.5, "1": 0.2, "_Total": 2.0}}
    s = FZ.box_sample(raw, t=100.0, ts=1_800_000_000.0, top=("chrome.exe", 0.123))
    assert s["core"] == "0" and s["core_max"] == 52.5, s
    assert s["dpc"] == 3.0 and s["avail_mb"] == 8123.4 and s["top"] == "chrome.exe" and s["top_share"] == 12


def test_during_finds_the_sample_that_spans_the_freeze():
    box = [dict(t=float(t), core_max=1.0) for t in range(90, 101)]   # щосекунди до фризу
    box.append(dict(t=104.1, core_max=60.0))                         # перший збір після фризу 101.0–104.0
    box.append(dict(t=105.1, core_max=1.0))
    d = FZ.during(box, 101.0, 104.0)
    assert d["core_max"] == 60.0 and d["win"] == 4.1 and d["full"], d
    assert FZ.during(box, 120.0, 125.0) == {}, "no sample after the freeze — no data, not a random one"
    assert FZ.during([dict(t=110.0)], 101.0, 104.0) == {}, "a sample too long after isn't the freeze"


# ── журнал ──
def ev(eid, prov, level=3, msg=""):
    return dict(id=eid, prov=prov, level=level, ts=1_800_000_000, msg=msg)


def test_event_kinds():
    assert FZ.event_kind(ev(129, "stornvme")) == "disk"
    assert FZ.event_kind(ev(153, "disk")) == "disk"
    assert FZ.event_kind(ev(4101, "Display")) == "gpu"
    assert FZ.event_kind(ev(14, "nvlddmkm", 2)) == "gpu"
    assert FZ.event_kind(ev(19, "Microsoft-Windows-WHEA-Logger")) == "whea"
    assert FZ.event_kind(ev(5002, "Netwtw10")) == "net"
    assert FZ.event_kind(ev(1, "USBHUB3", 2)) == "usb"
    assert FZ.event_kind(ev(13, "ACPI")) == "acpi"
    assert FZ.event_kind(ev(42, "Microsoft-Windows-Kernel-Power", 4)) == "sleep"
    assert FZ.event_kind(ev(1, "Microsoft-Windows-Power-Troubleshooter", 4)) == "sleep"
    assert FZ.event_kind(ev(1, "Microsoft-Windows-Kernel-General", 4)) == "", "same id, another source, not an error"
    assert FZ.event_kind(ev(10016, "Microsoft-Windows-DistributedCOM")) == "", "DCOM 10016 is noise"
    assert FZ.event_kind(ev(7, "SomeVendorDriver", 2)) == "other"
    assert FZ.is_sleep([ev(10016, "DistributedCOM"), ev(507, "Microsoft-Windows-Kernel-Power", 4)])
    assert not FZ.is_sleep([ev(129, "stornvme")])


def test_events_script_formats():
    s = FZ.EVENTS_PS.format(a=100, b=200)
    assert "FromUnixTimeSeconds(100)" in s and "FromUnixTimeSeconds(200)" in s and "Level=1,2,3" in s
    assert "WHEA-Logger" in s and "Id=1,42,107,506,507" in s


# ── вердикт ──
QUIET = dict(core_max=2.0, core="0", cpu=12.0, win=4.0, didle=96.0, dq=0.0, avail_mb=9000.0, pages_in=3.0)


def test_classify_names_the_cause():
    cat = lambda *a, **k: FZ.classify(*a, **k)[0]  # noqa: E731
    assert cat(3.0, QUIET, [ev(19, "Microsoft-Windows-WHEA-Logger")]) == "hardware"
    assert cat(3.0, QUIET, [ev(129, "stornvme", msg="Reset to device")]) == "disk"
    assert cat(3.0, QUIET, [ev(4101, "Display")]) == "gpu"
    hot = dict(QUIET, core_max=70.0)
    assert cat(3.0, hot, []) == "dpc"
    assert cat(3.0, hot, [ev(5002, "Netwtw10")]) == "net"
    assert cat(3.0, hot, [ev(43, "USBXHCI")]) == "usb"
    assert cat(3.0, dict(QUIET, didle=0.0, dq=12.0), []) == "io"
    assert cat(3.0, dict(QUIET, avail_mb=150.0), []) == "memory"
    assert cat(3.0, dict(QUIET, cpu=100.0), []) == "cpu"
    assert cat(3.0, QUIET, [], {"amd_ftpm": True}) == "ftpm"
    assert cat(3.0, QUIET, []) == "firmware", "nothing visible to Windows — firmware or hardware"
    assert cat(3.0, {}, []) == "unknown", "no counters and no events — don't guess"
    assert cat(3.0, QUIET, [ev(10016, "DistributedCOM")]) == "firmware", "noise doesn't change the verdict"
    assert cat(3.0, hot, [ev(129, "stornvme")]) == "disk", "a drive reset outranks the DPC spike it causes"


def test_classify_evidence_is_specific():
    c, e = FZ.classify(3.0, dict(QUIET, core_max=70.0, core="2"), [], {}, "game.exe")
    assert c == "dpc" and ["dpc", {"pct": 70, "core": "2"}] in [[k, p] for k, p in e]
    assert ("app", {"app": "game.exe"}) in e
    c, e = FZ.classify(3.0, QUIET, [ev(129, "stornvme", msg="Reset to device, \\Device\\RaidPort0, was issued.")])
    assert e[0] == ("event", {"src": "stornvme", "id": 129, "msg": "Reset to device, \\Device\\RaidPort0, was issued."})
    c, e = FZ.classify(3.0, QUIET, [], {"amd_ftpm": True})
    assert [k for k, _ in e] == ["quiet", "ftpm"]


def test_dpc_threshold_follows_the_freeze_share_of_the_sample():
    # фриз 3 с у зборі 4 с: якби весь фриз був DPC, ядро показало б ~75% — 20% замало
    assert FZ._hot(dict(core_max=20.0, win=4.0), 3.0)[2] is False
    assert FZ._hot(dict(core_max=40.0, win=4.0), 3.0)[2] is True
    # фриз 0,6 с у зборі 1,6 с: очікувані ~37% — достатньо 16%
    assert FZ._hot(dict(core_max=16.0, win=1.6), 0.6)[2] is True
    assert FZ._hot({}, 3.0) == (0, "", False)


def test_summary_and_advice():
    fr = [dict(end=10, dur=3.0, cat="ftpm"), dict(end=9, dur=1.0, cat="ftpm"), dict(end=8, dur=4.6, cat="disk"),
          dict(end=7, dur=0.8, cat="unknown")]
    s = FZ.summary(fr)
    assert (s["n"], s["cat"], s["kind"], s["share"], s["longest"], s["last"]) == (4, "ftpm", "firmware", 50, 4.6, 10)
    assert s["tied"] == []
    tie = FZ.summary(fr[1:3])
    assert tie["cat"] == "disk" and tie["tied"] == ["disk", "ftpm"], "a tie goes to the more serious cause"
    assert FZ.summary([dict(end=1, cat="unknown")])["cat"] == "unknown"
    assert FZ.summary([]) == {"n": 0}
    assert "gpu_hybrid" in FZ.advice("gpu", {"laptop": True}) and "gpu_hybrid" not in FZ.advice("gpu", {"laptop": False})
    assert FZ.advice("nonsense") == FZ.ADVICE["unknown"]


def test_record_and_append_keep_the_newest():
    d = tempfile.mkdtemp(prefix="oxfz_")
    path = os.path.join(d, "freezes.json")
    for i in range(7):
        rec = FZ.record(1_800_000_000 + i * 60, 2.5, "dpc", [("dpc", {"pct": 50, "core": "0"})],
                        dict(QUIET, core_max=50.0), [ev(5002, "Netwtw10"), ev(10016, "DistributedCOM")], "x.exe")
        FZ.append(rec, path, keep=5)
    data = json.load(open(path, encoding="utf-8"))
    assert len(data) == 5 and data[0]["ts"] == 1_800_000_000 + 6 * 60, "newest first, oldest dropped"
    r = data[0]
    assert r["kind"] == "driver" and r["dur"] == 2.5 and r["end"] == r["ts"] + 2 and r["app"] == "x.exe"
    assert [e["prov"] for e in r["events"]] == ["Netwtw10"], "noise events aren't stored"
    assert r["ev"] == [["dpc", {"pct": 50, "core": "0"}]] and r["during"]["core_max"] == 50.0


# ── TPM ──
def test_parse_tpm():
    amd = FZ.parse_tpm({"present": True, "vendor": "AMD\x00", "version": "3.87.0.5", "enabled": True},
                       {"version": "F.21", "date": "03/12/2021"})
    assert amd["amd_ftpm"] and amd["bios_date"] == "03/12/2021" and amd["vendor"] == "AMD"
    assert not FZ.parse_tpm({"present": True, "vendor": "INTC"})["amd_ftpm"], "Intel PTT"
    assert not FZ.parse_tpm({"present": True, "vendor": "IFX"})["amd_ftpm"], "discrete Infineon chip"
    assert not FZ.parse_tpm({"present": True, "vendor": "AMD", "enabled": False})["amd_ftpm"], "disabled"
    assert FZ.parse_tpm(None) == dict(present=False, vendor="", amd_ftpm=False, version="", bios="", bios_date="")


# ── WPR ──
def test_wpr_profile_is_valid_and_small():
    root = ET.fromstring(FZ.WPRP)
    prof = root.find("./Profiles/Profile")
    assert prof.get("Name") == FZ.PROFILE_NAME and prof.get("LoggingMode") == "Memory"
    assert prof.get("Id") == f"{prof.get('Name')}.{prof.get('DetailLevel')}.{prof.get('LoggingMode')}", \
        "WPR requires Id = Name.DetailLevel.LoggingMode"
    coll = root.find("./Profiles/SystemCollector")
    kb = int(coll.find("BufferSize").get("Value")) * int(coll.find("Buffers").get("Value"))
    assert kb <= 64 * 1024, f"ring buffer {kb} KB"
    keys = {k.get("Value") for k in root.findall("./Profiles/SystemProvider/Keywords/Keyword")}
    assert {"DPC", "Interrupt", "Loader"} <= keys, keys
    ref = prof.find("./Collectors/SystemCollectorId")
    assert ref.get("Value") == coll.get("Id") and ref.find("SystemProviderId").get("Value") == \
        root.find("./Profiles/SystemProvider").get("Id")


def test_prune_etl_keeps_the_newest():
    d = tempfile.mkdtemp(prefix="oxfz_")
    names = [f"freeze-202611{day:02d}-120000.etl" for day in range(1, 7)] + ["other.etl"]
    for n in names:
        open(os.path.join(d, n), "w").close()
    for day in (1, 6):  # теки NGEN PDB, які WPR кладе поруч із записом
        os.makedirs(os.path.join(d, f"freeze-202611{day:02d}-120000.etl.NGENPDB", "x"))
    FZ.prune_etl(d, keep=3)
    assert sorted(os.listdir(d)) == ["freeze-20261104-120000.etl", "freeze-20261105-120000.etl",
                                     "freeze-20261106-120000.etl", "freeze-20261106-120000.etl.NGENPDB",
                                     "other.etl"]


# ── тексти ──
def test_every_cause_and_hint_has_text():
    evidence = {"event", "dpc", "quiet", "disk", "mem", "cpu", "ftpm", "nodata", "app", "etl"}
    keys = [f"fz.cat.{c}" for c in FZ.KIND] + [f"fz.short.{c}" for c in FZ.KIND] + \
        [f"fz.kind.{k}" for k in set(FZ.KIND.values())] + \
        [f"fz.a.{a}" for v in FZ.ADVICE.values() for a in v] + [f"fz.e.{e}" for e in evidence]
    missing = [k for k in keys if k not in i18n.STR]
    assert not missing, missing
    assert set(FZ.ORDER) == set(FZ.KIND), "every category has a priority"
    # усе, що може видати classify, має текст
    for args in ((3.0, QUIET, [ev(129, "stornvme")]), (3.0, dict(QUIET, core_max=70.0), [ev(43, "USBXHCI")]),
                 (3.0, dict(QUIET, didle=0.0, dq=9.0), []), (3.0, dict(QUIET, avail_mb=10.0), []),
                 (3.0, dict(QUIET, cpu=99.0), []), (3.0, QUIET, [], {"amd_ftpm": True}), (3.0, {}, [])):
        for k, _p in FZ.classify(*args)[1]:
            assert k in evidence, k


def test_demo_records_render():
    for f in FZ.load():
        assert f["cat"] in FZ.KIND and f["kind"] == FZ.KIND[f["cat"]]
        for k, p in f["ev"]:
            text = i18n.tr(f"fz.e.{k}", **p)
            assert "{" not in text, text


# ── процес-ловець від початку до кінця (без Windows: лічильників і журналу немає, вартовий і файли — справжні) ──
def test_watcher_records_a_freeze_and_stops_on_request():
    if IS_WIN:
        skip("on Windows the watcher would read the real event log; covered by the self-test there")
    d = tempfile.mkdtemp(prefix="oxfz_")
    t0 = time.monotonic()
    jumped = []

    def clock():  # через 0,6 с годинник «перескакує» на 2,5 с — так вартовий бачить зупинку системи
        now = time.monotonic() - t0
        if now > 0.6 and not jumped:
            jumped.append(1)
        return now + (2.5 if jumped else 0.0)

    w = FZ.Watcher(folder=d, parent=os.getpid(), clock=clock, warmup=0.3, settle=0.3)
    th = threading.Thread(target=w.run, daemon=True)
    th.start()
    path = os.path.join(d, "freezes.json")
    deadline = time.time() + 15
    while time.time() < deadline and not os.path.exists(path):
        time.sleep(0.1)
    assert os.path.exists(path), "the freeze was not recorded"
    data = json.load(open(path, encoding="utf-8"))
    assert len(data) == 1 and 2.3 <= data[0]["dur"] <= 2.7, data
    assert data[0]["cat"] in ("ftpm", "unknown")  # демо-TPM — AMD fTPM; лічильників поза Windows немає
    open(os.path.join(d, "stop"), "w").close()
    th.join(10)
    assert not th.is_alive(), "the watcher must exit when asked"
    st = json.load(open(os.path.join(d, "status.json"), encoding="utf-8"))
    assert st["stopped"] and st["caught"] == 1 and st["pid"] == os.getpid()
    assert not os.path.exists(os.path.join(d, "stop")), "the stop request is cleaned up"
