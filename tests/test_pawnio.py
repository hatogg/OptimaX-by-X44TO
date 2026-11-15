"""OptimaX 7.1 — PawnIO: формат виклику IOCTL, розбір MSR (Intel / AMD), SPD DDR4 і DDR5 (таймінги JEDEC, виробник,
XMP / EXPO) і логіка сторінок SPD на шині — на фальшивій шині, бо справжнього драйвера в CI немає. Головне: сторінка
SPD після читання повертається як була, а на шині без SPD нічого не пишемо в чужі адреси."""
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
import pawnio as PIO  # noqa: E402


def test_ioctl_layout():
    assert PIO.IOCTL_LOAD == 0xA1B2_2084 and PIO.IOCTL_EXEC == 0xA1B2_2104  # CTL_CODE(41394, 0x821/0x841, 0, 0)
    raw = PIO.pack_call("ioctl_read_msr", [0x198])
    assert len(raw) == 40 and raw[:14] == b"ioctl_read_msr" and raw[14:32] == bytes(18)
    assert struct.unpack_from("<Q", raw, 32)[0] == 0x198
    assert PIO.pack_call("ioctl_smbus_xfer", [0x50, 1, 2, 2])[32:] == struct.pack("<4Q", 0x50, 1, 2, 2)
    try:
        PIO.pack_call("x" * 32)
        assert False
    except ValueError:
        pass


def test_msr_decoding():
    # i7-13700K: множник 53, VID 0x2900 / 8192 = 1.281 В
    assert PIO.intel_perf_status(0x2900 << 32 | 53 << 8) == (53, 1.281)
    assert PIO.intel_perf_status(36 << 8) == (36, None)
    assert PIO.intel_platform_info(8 << 40 | 34 << 8) == (34, 8)
    # Zen 3 (Vermeer, сім. 19h модель 21h): FID 0x94=148, DFS 8 -> 3700 МГц; VID 0x38 -> 1.2 В (SVI2)
    assert PIO.amd_pstate(0x38 << 14 | 8 << 8 | 0x94, 0x19, 0x21) == (3700, 1.2)
    # Zen 4 (Raphael): частоту знаємо, вольти — ні (SVI3)
    assert PIO.amd_pstate(0x38 << 14 | 8 << 8 | 0xBC, 0x19, 0x61) == (4700, None)
    # Zen 5: FID 12 бітів по 5 МГц
    assert PIO.amd_pstate(940, 0x1A, 0x44) == (4700, None)
    assert PIO.amd_svi2(0x17, 0x71) and not PIO.amd_svi2(0x19, 0x61)
    # напруга з IA32_PERF_STATUS — лише Core від Sandy Bridge, не Atom і не Core 2
    assert PIO.intel_volts_ok(6, 0xB7) and PIO.intel_volts_ok(6, 0x2A)
    assert not PIO.intel_volts_ok(6, 0x17) and not PIO.intel_volts_ok(6, 0x4C) and not PIO.intel_volts_ok(6, 0xBE)


def ddr5_spd(tck=416, aa=16640, rcd=16640, rp=16640, ras=32000, xmp=True, expo=True) -> bytes:
    b = bytearray(1024)
    b[2], b[234] = 0x12, 1 << 3
    for o, v in ((20, tck), (30, aa), (32, rcd), (34, rp), (36, ras)):
        b[o:o + 2] = struct.pack("<H", v)
    b[24:29] = (0b1111111111111).to_bytes(5, "little")  # CL20..CL44
    b[512:514], b[515], b[516] = b"\x80\x2C", 0x24, 0x07  # Micron, 7 тиждень 2024
    b[521:551] = b"CT16G48C40U5.M8A1".ljust(30)
    if xmp:
        b[640:642] = b"\x0C\x4A"
    if expo:
        b[832:836] = b"EXPO"
    return bytes(b)


def test_spd_parsing():
    s = PIO.parse_spd(PIO.make_ddr4_spd())
    assert (s["kind"], s["speed"], s["timings"], s["vendor"]) == ("DDR4", 3200, (22, 22, 22, 52), "Kingston")
    assert s["part"] == "KF432C16BB/16" and s["date"] == "14/2023" and s["xmp"] and s["xmp_profiles"] == 2
    assert s["ranks"] == 2 and PIO.timings_text(s) == "22-22-22-52 @ 3200 MT/s"
    # DDR4-2666: tCK 0.75 нс = 6 MTB + fine -0.25... тут 750 пс = 6*125
    s = PIO.parse_spd(PIO.make_ddr4_spd(tck_mtb=6, aa=105, rcd=105, rp=105, ras=256, xmp=False))
    assert s["speed"] == 2666 and s["timings"] == (18, 18, 18, 43) and not s["xmp"]
    s = PIO.parse_spd(ddr5_spd())
    assert (s["kind"], s["speed"], s["timings"], s["vendor"]) == ("DDR5", 4800, (40, 40, 40, 77), "Micron")
    assert s["part"] == "CT16G48C40U5.M8A1" and s["date"] == "7/2024" and s["xmp"] and s["expo"]
    # SPD зберігає tCK округленим донизу: DDR5-6400 (312 пс) JEDEC CL52, DDR5-6000 (333 пс) — CL48, без непарних CL
    s = PIO.parse_spd(ddr5_spd(tck=312, aa=16250, rcd=16250, rp=16250, ras=32000, xmp=False, expo=False))
    assert s["speed"] == 6400 and s["timings"] == (52, 52, 52, 103)
    s = PIO.parse_spd(ddr5_spd(tck=333, aa=16000, rcd=16000, rp=16000, ras=32000))
    assert s["speed"] == 6000 and s["timings"][:3] == (48, 48, 48)
    assert PIO.parse_spd(b"") == {} and PIO.parse_spd(bytes(512)) == {}


class FakeBus:
    """Шина з одним DDR4-модулем на 0x50 або одним DDR5 (SPD5118) на 0x51. Записує, хто й що писав."""

    def __init__(self, kind: str, raw: bytes, name="SmbusI801"):
        self.kind, self.raw, self.page, self.writes, self.reads = kind, raw, 0, [], 0
        self.drv = type("D", (), {"name": name, "call": lambda *a, **k: None})()
        self.addr = 0x50 if kind == "DDR4" else 0x51
        self.protected = False

    def ack(self, addr):
        return self.kind == "DDR4" and addr == 0x36 and self.page == 0

    def read(self, addr, cmd):
        self.reads += 1
        if addr != self.addr:
            return None  # NACK
        if self.kind == "DDR4":
            return self.raw[self.page * 256 + cmd]
        if cmd < 0x80:
            return {0: 0x51, 1: 0x18, 0x0B: self.page}.get(cmd, 0)
        return self.raw[self.page * 128 + (cmd & 0x7F)]

    def write(self, addr, cmd, val):
        self.writes.append((addr, cmd, val))
        if self.kind == "DDR4" and addr in (0x36, 0x37):
            self.page = addr - 0x36
            return True
        if self.kind == "DDR5" and addr == self.addr and cmd == 0x0B:
            self.page = val
            return True
        return False


def test_spd_paging_restores_state():
    warn = []
    bus = FakeBus("DDR4", PIO.make_ddr4_spd())
    assert PIO._ddr4(bus, 0x51, warn) is None  # порожній слот
    bus.reads = 0
    raw = PIO._ddr4(bus, 0x50, warn)
    assert PIO.parse_spd(raw) == PIO.parse_spd(PIO.make_ddr4_spd()) and bus.page == 0 and not warn
    assert bus.reads < 200, "лише потрібні байти — менше тримаємо м'ютекс шини"
    assert {a for a, _c, _v in bus.writes} <= {0x36, 0x37}  # у самі модулі нічого не пишемо
    bus = FakeBus("DDR5", ddr5_spd())
    bus.page = 3  # BIOS лишив сторінку 3 — так і має лишитися
    assert PIO._ddr5(bus, 0x50, warn) is None and not bus.writes  # на чужій адресі навіть не пробуємо
    raw = PIO._ddr5(bus, 0x51, warn)
    assert PIO.parse_spd(raw)["speed"] == 4800 and bus.page == 3 and not warn
    assert all(a == 0x51 and c == 0x0B for a, c, _v in bus.writes)  # лише регістр сторінки MR11


def test_module_hash_is_checked_before_loading(tmp_path=None):
    """Модуль, чий SHA-256 не збігається з MODULE_SHA256, у драйвер не передається (підміна в %TEMP%)."""
    import tempfile
    from test_undo_guarantees import patched
    d = tempfile.mkdtemp()
    open(os.path.join(d, "IntelMSR.bin"), "wb").write(b"not the signed module" * 10)
    opened = []
    with patched(PIO, module_dir=lambda: d, Driver=type("Drv", (), {"open": staticmethod(
            lambda: opened.append(1))})):
        assert PIO.open_module(("IntelMSR",)) is None and not opened
    assert set(PIO.MODULE_SHA256) == set(PIO.MODULES) and PIO.MODULES_TAG


def test_status_off_windows():
    from test_undo_guarantees import patched
    with patched(E, IS_WIN=False, DEMO="old"):
        assert PIO.status() == "absent" and PIO.read_spd("DDR4") == []
    with patched(E, IS_WIN=False, DEMO="gaming"):
        assert PIO.status() == "demo"


def test_real_windows_without_driver():
    """CI windows-2022/2025: PawnIO там не встановлено — відповідь «absent», без винятків і зависань."""
    if not IS_WIN:
        skip("потрібна справжня Windows")
    assert PIO.status() in ("absent", "ok", "no_modules")
    if PIO.status() == "absent":
        assert PIO.open_module(PIO.MODULES) is None
