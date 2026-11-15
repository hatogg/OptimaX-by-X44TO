"""OptimaX 7.1 — «Процесор» як у CPU-Z: розбір CPUID (виробник, назва, сімейство / модель / степінг, інструкції),
кодові імена, кеш з GetLogicalProcessorInformationEx, чипсет, роз'єм, канали пам'яті, вкладки й звіт. Поля, які без
драйвера не прочитати, — «потрібен PawnIO», а не вигадане число."""
import os
import struct
import sys
import tempfile

from _util import IS_WIN, ROOT, skip

sys.path.insert(0, ROOT)
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
import cpuz as CZ  # noqa: E402
import hardware as H  # noqa: E402
from test_undo_guarantees import patched  # noqa: E402


def regs(s: str) -> tuple:
    b = s.encode().ljust(16, b"\0")
    return struct.unpack("<4I", b)


def dump_13700k() -> dict:
    v = struct.unpack("<3I", b"GenuineIntel")
    brand = "13th Gen Intel(R) Core(TM) i7-13700K".ljust(48, "\0")
    d = {(0, 0): (0x20, v[0], v[2], v[1]),           # ebx, edx, ecx = «Genu», «ineI», «ntel»
         (1, 0): (0x000B0671, 0, 1 << 0 | 1 << 9 | 1 << 19 | 1 << 20 | 1 << 25 | 1 << 28 | 1 << 12 | 1 << 5,
                  1 << 23 | 1 << 25 | 1 << 26),
         (7, 0): (0, 1 << 5 | 1 << 29, 0, 0), (7, 1): (1 << 4, 0, 0, 0),
         (0x80000000, 0): (0x80000008, 0, 0, 0), (0x80000001, 0): (0, 0, 0, 1 << 29)}
    for i, leaf in enumerate((0x80000002, 0x80000003, 0x80000004)):
        d[(leaf, 0)] = regs(brand[i * 16:(i + 1) * 16])
    return d


def test_cpuid_parsing():
    c = CZ.parse_cpuid(dump_13700k())
    assert c["vendor"] == "Intel" and c["spec"] == "13th Gen Intel(R) Core(TM) i7-13700K"
    assert (c["family"], c["model"], c["stepping"], c["ext_family"], c["ext_model"]) == (6, 7, 1, 6, 0xB7)
    assert c["instructions"] == ["MMX", "SSE", "SSE2", "SSE3", "SSSE3", "SSE4.1", "SSE4.2", "EM64T", "VT-x", "AES",
                                 "AVX", "AVX2", "AVX-VNNI", "FMA3", "SHA"]
    assert CZ.parse_cpuid({}) == {}


def test_codenames_and_names():
    assert CZ.codename("Intel", 6, 0xB7) == ("Raptor Lake", "Intel 7")
    assert CZ.codename("Intel", 6, 0x9E, 9) == ("Kaby Lake", "14 nm")
    assert CZ.codename("Intel", 6, 0x9E, 12) == ("Coffee Lake", "14 nm")
    assert CZ.codename("AMD", 0x19, 0x61) == ("Raphael (Zen 4)", "5 nm")
    assert CZ.codename("AMD", 0x1A, 0x44) == ("Granite Ridge (Zen 5)", "4 nm")
    assert CZ.codename("Intel", 6, 0x01) == (None, None)
    assert CZ.short_name("13th Gen Intel(R) Core(TM) i7-13700K") == "Intel Core i7-13700K"
    assert CZ.short_name("AMD Ryzen 9 7950X3D 16-Core Processor") == "AMD Ryzen 9 7950X3D"
    assert CZ.short_name("Intel(R) Celeron(R) CPU N3060 @ 1.60GHz") == "Intel Celeron N3060"
    assert CZ.short_name("Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz") == "Intel Xeon E5-2680 v4"
    assert CZ.short_name("AMD Ryzen 7 5700U with Radeon Graphics") == "AMD Ryzen 7 5700U"


def cache_rel(level, ctype, kb, assoc, line=64) -> bytes:
    body = struct.pack("<BBHII", level, assoc, line, kb * 1024, ctype) + bytes(20) + bytes(16)
    return struct.pack("<II", 2, 8 + len(body)) + body


def test_caches_from_windows():
    raw = b"".join([cache_rel(1, 2, 48, 12)] * 8 + [cache_rel(1, 2, 32, 8)] * 8 + [cache_rel(1, 1, 32, 8)] * 16
                   + [cache_rel(2, 0, 2048, 16)] * 8 + [cache_rel(2, 0, 4096, 16)] * 2 + [cache_rel(3, 0, 30720, 12)])
    rel = CZ.parse_cache_relations(raw)
    assert len(rel) == 43
    s = {k: (size, ways) for k, size, ways in CZ.cache_summary(rel)}
    assert s["cz.l1d"] == ("8 x 48 KB + 8 x 32 KB", "12-way + 8-way")
    assert s["cz.l1i"] == ("16 x 32 KB", "8-way")
    assert s["cz.l2"] == ("2 x 4 MB + 8 x 2 MB", "16-way")
    assert s["cz.l3"] == ("30 MB", "12-way")


def test_board_memory_helpers():
    assert CZ.chipset_from_names(["Intel(R) Z790 Chipset LPC/eSPI Controller - 7A04", "Intel(R) SMBus - 7A23"]) \
        == "Intel Z790"
    assert CZ.chipset_from_names(["AMD SMBus"]) == "AMD FCH"
    assert CZ.chipset_from_names(["PCI standard host CPU bridge"]) is None
    assert CZ.socket_name("LGA1700") == "LGA1700" and CZ.socket_name("AM5") == "AM5"
    assert CZ.socket_name("CPU 1") == "" and CZ.socket_name("U3E1") == ""
    assert CZ.channels([dict(slot="Controller0-ChannelA-DIMM0"), dict(slot="Controller0-ChannelB-DIMM0")]) == 2
    assert CZ.channels([dict(slot="DIMM_A1"), dict(slot="DIMM_A2")]) == 1
    assert CZ.channels([dict(slot="DIMM 1", bank="P0 CHANNEL A"), dict(slot="DIMM 2", bank="P0 CHANNEL B")]) == 2
    assert CZ.channels([dict(slot="DIMM 1")]) is None


def test_demo_tabs_and_report():
    with patched(E, DEMO="gaming", IS_WIN=False):
        hw = H._from_demo("gaming")
        d = CZ.collect(hw)
    live = CZ.demo_live(d, 5289)
    cpu = dict(CZ.cpu_rows(d, 5276, live))
    assert cpu["cz.name"] == "Intel Core i7-13700K" and cpu["cz.codename"] == "Raptor Lake"
    assert cpu["cz.package"] == "LGA1700" and cpu["cz.voltage"] == "1.284 V"
    assert cpu["cz.multiplier"] == "x53 (8 – 54)" and cpu["cz.bus"] == "99.80 MHz" and cpu["cz.clock"] == "5289 MHz"
    assert cpu["cz.cores"] == "16 (8P + 8E)"
    mem = dict(CZ.memory_rows(d))
    assert mem["cz.channels"] == "2 x 64-bit" and mem["cz.jedec"] == "22-22-22-52 @ 3200 MT/s"
    assert mem["cz.profiles"] == "XMP (2)"
    slot = dict(CZ.slot_rows(d["ram"]["modules"][0], d))
    assert slot["cz.mfg_date"] == "14/2023" and slot["cz.jedec"].startswith("22-")
    assert dict(CZ.board_rows(d))["cz.chipset"] == "Intel Z790"
    text = CZ.report_text(d, 5276, live)
    assert "Raptor Lake" in text and "L1" in text and "1.284 V" in text and "PawnIO" not in text
    # без драйвера — чесне «потрібен PawnIO», а не число
    with patched(E, DEMO="old", IS_WIN=False):
        d = CZ.collect(H._from_demo("old"))
    cpu = dict(CZ.cpu_rows(d, 2480, CZ.demo_live(d, 2480)))
    assert cpu["cz.voltage"] is CZ.NEEDS_DRIVER and cpu["cz.multiplier"] == "≈ x24.8"
    assert cpu["cz.bus"] == "80 MHz (per BIOS)"
    assert dict(CZ.memory_rows(d))["cz.jedec"] is None  # DDR3: PawnIO тут не допоможе — «----», а не обіцянка
    assert "PawnIO" in CZ.report_text(d, 2480)
    with patched(E, DEMO="x3d", IS_WIN=False):
        d = CZ.collect(H._from_demo("x3d"))
    assert dict(CZ.cpu_rows(d))["cz.codename"] == "Raphael (Zen 4)"
    assert dict(CZ.cache_rows(d))["cz.l3"].startswith("96 MB + 32 MB")


def test_real_windows_cpuid_and_clock():
    """CI windows-2022/2025: справжній CPUID (сервер Xeon / EPYC у хмарі), кеш з Windows, частота з PDH."""
    if not IS_WIN:
        skip("потрібна справжня Windows")
    c = CZ.parse_cpuid(CZ.read_cpuid_dump())
    assert c["vendor"] in ("Intel", "AMD") and "SSE2" in c["instructions"] and c["spec"]
    rows = CZ.cache_summary(CZ.parse_cache_relations(CZ.read_cache_raw()))
    assert any(k == "cz.l1d" for k, *_ in rows) and any(k == "cz.l2" for k, *_ in rows)
    d = CZ.collect(H.detect_hw())
    assert d["cpu"]["name"] and d["cpu"]["instructions"]
    import time
    m = CZ.ClockMeter(d["cpu"]["base_mhz"] or 2000)
    time.sleep(1.1)
    mhz = m.mhz()
    m.close()
    assert mhz is None or 300 < mhz < 8000
