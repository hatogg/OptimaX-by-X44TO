"""
OptimaX — PawnIO: безкоштовний підписаний драйвер ядра (pawnio.eu, github.com/namazso/PawnIO), через який програми на
кшталт CPU-Z читають регістри процесора (MSR) і шину SMBus (SPD модулів пам'яті).

OptimaX свого драйвера не має й PawnIO сам не встановлює. Є PawnIO — у «Процесорі» з'являються множник, напруга (VID),
шина й таймінги з SPD; немає — ці поля чесно показують «потрібен PawnIO».

Ліцензія. PawnIO — GPL 2 з винятком для незалежних програм, що спілкуються з ним «лише через інтерфейс керування
пристроєм». OptimaX саме так і працює: тільки DeviceIoControl, без PawnIOLib і без власного коду на Pawn. Модулі
(IntelMSR, AMDFamily17, SmbusI801, SmbusPIIX4) — офіційні підписані збірки PawnIO.Modules під LGPL 2.1; збірка кладе їх
у теку pawnio\\ поруч із програмою разом із текстом ліцензії.

Безпека.
• Версія модулів зафіксована (MODULES_TAG), а перед завантаженням у драйвер OptimaX звіряє SHA-256 вмісту файлу з
  MODULE_SHA256 — вже прочитаного в пам'ять, тож підмінити файл у %TEMP% (портативна збірка) між перевіркою й
  завантаженням не вийде.
• Модулі дають читати лише перелічені в них регістри. OptimaX у MSR нічого не пише.
• Записи на шину SMBus — лише вибір сторінки SPD (DDR4: адреси 0x36 / 0x37, DDR5: регістр MR11 концентратора) і, на
  AMD, вибір порту контролера. Це тимчасові регістри, а не налаштування системи (скидаються з вимкненням), тому вони
  не йдуть через журнал. Після читання повертаємо як було; не вдалося — кажемо про це (spd_error), а не мовчимо.
  У саму пам'ять SPD (дані модуля) не пишемо ніколи.
• Шину ділимо з іншими програмами через загальний м'ютекс Access_SMBUS.HTP.Method.
"""
from __future__ import annotations

import hashlib
import math
import os
import struct
import sys

import engine as E

SITE = "https://pawnio.eu"
DEVICE = "\\\\?\\GLOBALROOT\\Device\\PawnIO"
_TYPE = 41394


def _ctl(fn: int) -> int:
    return (_TYPE << 16) | (fn << 2)  # METHOD_BUFFERED, FILE_ANY_ACCESS


IOCTL_LOAD, IOCTL_EXEC = _ctl(0x821), _ctl(0x841)
FN_LEN = 32
MODULES = ("IntelMSR", "AMDFamily17", "SmbusI801", "SmbusPIIX4")
# 7.1: офіційний реліз PawnIO.Modules, який кладе в збірку CI (.github/workflows/ci.yml звіряє ці ж хеші)
MODULES_TAG = "0.2.11"
MODULE_SHA256 = {
    "IntelMSR": "d6ed85d65ab17a22f813ef98207d6d537155ee2ded5976a21cb48413c9b92e5f",
    "AMDFamily17": "dae74615761b78bdf064dfb3e136252ddcc6fc727d88f14738d0e5800d427a91",
    "SmbusI801": "a0f7d066e7efda28c0e754c1f52dbd8dc280d388ba8575b514a80cb67490530c",
    "SmbusPIIX4": "91f9b4b1c39e3d399ce48477a89d8f6bd3e58a2241064a4daec3a1513dff56e5",
}


def module_dir() -> str:
    """Теку модулів кладе збірка (PyInstaller: _MEIPASS або _internal); під час розробки — pawnio\\ у репозиторії."""
    here = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(
        os.path.abspath(__file__))
    return os.path.join(getattr(sys, "_MEIPASS", here), "pawnio")


def pack_call(name: str, ins=()) -> bytes:
    """Вхід IOCTL_PIO_EXECUTE_FN: ім'я функції (32 байти з нулем у кінці), далі вхідні значення по 8 байтів."""
    raw = name.encode("ascii")
    if len(raw) >= FN_LEN:
        raise ValueError(name)
    return raw.ljust(FN_LEN, b"\0") + struct.pack(f"<{len(ins)}Q", *[int(v) & (2**64 - 1) for v in ins])


class Driver:
    """Один «виконавець» PawnIO = один завантажений модуль."""

    def __init__(self, handle):
        self.h, self.name = handle, None

    @staticmethod
    def open():
        if not E.IS_WIN:
            return None
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        h = k32.CreateFileW(DEVICE, 0xC0000000, 7, None, 3, 0, None)  # GENERIC_READ|WRITE, усі share, OPEN_EXISTING
        if not h or h == 2**64 - 1 or h == -1:
            return None
        d = Driver(h)
        d.k32 = k32
        k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                        wintypes.LPVOID]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        return d

    def _ioctl(self, code: int, data: bytes, n_out: int):
        import ctypes
        from ctypes import wintypes
        inb = ctypes.create_string_buffer(data, len(data))
        outb = ctypes.create_string_buffer(max(8, n_out * 8))
        got = wintypes.DWORD(0)
        ok = self.k32.DeviceIoControl(self.h, code, inb, len(data), outb if n_out else None, n_out * 8,
                                      ctypes.byref(got), None)
        if not ok:
            return None
        return list(struct.unpack_from(f"<{got.value // 8}Q", outb.raw)) if n_out else []

    def load(self, blob: bytes) -> bool:
        return self._ioctl(IOCTL_LOAD, blob, 0) is not None

    def call(self, fn: str, ins=(), n_out: int = 0):
        """-> список виходів або None, якщо модуль відмовив (не той процесор, заборонений регістр, NACK шини)."""
        return self._ioctl(IOCTL_EXEC, pack_call(fn, ins), n_out)

    def close(self) -> None:
        if self.h:
            self.k32.CloseHandle(self.h)
            self.h = None


def module_path(name: str) -> str:
    return os.path.join(module_dir(), f"{name}.bin")


def status() -> str:
    """«ok» — драйвер є й модулі на місці; «absent» — PawnIO не встановлено; «no_modules» — у збірці немає модулів."""
    if not E.IS_WIN:
        return "demo" if E.DEMO in ("gaming", "x3d") else "absent"
    d = Driver.open()
    if not d:
        return "absent"
    d.close()
    return "ok" if any(os.path.isfile(module_path(m)) for m in MODULES) else "no_modules"


def open_module(names):
    """Перший модуль зі списку, який драйвер погодився завантажити (модуль сам перевіряє процесор / чипсет)."""
    for name in names:
        try:
            with open(module_path(name), "rb") as f:
                blob = f.read()
        except OSError:
            continue
        if hashlib.sha256(blob).hexdigest() != MODULE_SHA256.get(name):  # не той файл — у драйвер не передаємо
            continue
        d = Driver.open()
        if not d:
            return None
        if d.load(blob):
            d.name = name
            return d
        d.close()
    return None


# ───────────────────────── процесор: MSR ─────────────────────────
def intel_perf_status(v: int) -> tuple:
    """IA32_PERF_STATUS (0x198) -> (поточний множник, напруга ядра В або None). Напруга — біти 47:32, крок 1/8192 В
    (Sandy Bridge і новіші)."""
    vid = v >> 32 & 0xFFFF
    return v >> 8 & 0xFF, round(vid / 8192, 3) if vid else None


# Atom / E-ядерні Celeron і Pentium: напругу в IA32_PERF_STATUS не віддають (або віддають інакше)
INTEL_ATOM = {0x1C, 0x26, 0x27, 0x35, 0x36, 0x37, 0x4A, 0x4C, 0x4D, 0x5A, 0x5C, 0x5D, 0x5F, 0x7A, 0x86, 0x96, 0x9C,
              0xBE}


def intel_volts_ok(family: int, model: int) -> bool:
    """Напруга в бітах 47:32 IA32_PERF_STATUS — лише Core від Sandy Bridge (сім. 6, модель ≥ 0x2A), не Atom."""
    return family == 6 and model >= 0x2A and model not in INTEL_ATOM


def intel_platform_info(v: int) -> tuple:
    """MSR_PLATFORM_INFO (0xCE) -> (базовий множник, мінімальний множник)."""
    return v >> 8 & 0xFF, v >> 40 & 0xFF


def amd_svi2(family: int, model: int) -> bool:
    """Формулу VID -> вольти знаємо напевно лише для SVI2: Zen, Zen+, Zen 2 і Zen 3 (Vermeer, Cezanne, Milan)."""
    return family == 0x17 or (family == 0x19 and (model < 0x10 or 0x20 <= model < 0x30 or 0x50 <= model < 0x60))


def amd_pstate(v: int, family: int, model: int) -> tuple:
    """HwPstateStatus (0xC0010293) або P-стан (0xC0010064+) -> (МГц, напруга VID або None)."""
    vid = v >> 14 & 0xFF
    if family >= 0x1A:  # Zen 5: FID 12 бітів, крок 5 МГц
        mhz = (v & 0xFFF) * 5
    else:
        fid, dfs = v & 0xFF, v >> 8 & 0x3F
        mhz = round(fid / dfs * 200) if dfs else 0
    volts = round(1.55 - vid * 0.00625, 4) if amd_svi2(family, model) and vid else None
    return mhz or None, volts


class CpuLive:
    """Множник, напруга й шина з регістрів процесора. Читаємо з ядра 0 (як CPU-Z за замовчуванням)."""

    def __init__(self, vendor: str, family: int, model: int, reg_mhz: int):
        self.vendor, self.family, self.model, self.reg_mhz = vendor, family, model, reg_mhz
        self.drv, self.base_ratio, self.min_ratio, self.max_ratio = None, None, None, None
        if vendor == "Intel" and family == 6 and model >= 0x1A:  # Nehalem і новіші: є MSR_PLATFORM_INFO
            self.drv = open_module(("IntelMSR",))
        elif vendor == "AMD" and 0x17 <= family <= 0x1A:
            self.drv = open_module(("AMDFamily17",))
        if not self.drv:
            return
        if vendor == "Intel":
            pi = self.msr(0xCE)
            if pi is not None:
                self.base_ratio, self.min_ratio = intel_platform_info(pi)
            trl = self.msr(0x1AD)
            self.max_ratio = (trl & 0xFF) or None if trl is not None else None
        else:
            p0 = self.msr(0xC0010064)
            if p0 is not None and p0 >> 63:
                mhz, _v = amd_pstate(p0, family, model)
                self.base_ratio = round(mhz / 100, 2) if mhz else None

    @property
    def ok(self) -> bool:
        return self.drv is not None

    def msr(self, reg: int):
        out = self._on_core0(lambda: self.drv.call("ioctl_read_msr", [reg], 1))
        return out[0] if out else None

    def _on_core0(self, fn):
        """Перший логічний процесор поточної групи (на ПК до 64 потоків — справді ядро 0)."""
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentThread.restype = ctypes.c_void_p
        k32.SetThreadAffinityMask.restype = ctypes.c_size_t
        k32.SetThreadAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        th = k32.GetCurrentThread()
        old = k32.SetThreadAffinityMask(th, 1)
        try:
            return fn()
        finally:
            if old:
                k32.SetThreadAffinityMask(th, old)

    def bus(self):
        """Опорна частота = базова частота з реєстру / базовий множник (100 МГц ± похибка генератора)."""
        if self.base_ratio and self.reg_mhz:
            return round(self.reg_mhz / self.base_ratio, 2)
        return None

    def read(self) -> dict:
        if not self.drv:
            return {}
        bus = self.bus()
        if self.vendor == "Intel":
            v = self.msr(0x198)
            if v is None:
                return {}
            ratio, volts = intel_perf_status(v)
            if not intel_volts_ok(self.family, self.model):  # 7.1: Core 2 / Nehalem / Atom — не вигадувати вольти
                volts = None
        else:
            v = self.msr(0xC0010293)
            if v is None:
                return {}
            mhz, volts = amd_pstate(v, self.family, self.model)
            ratio = round(mhz / (bus or 100), 1) if mhz else None
        return dict(ratio=ratio or None, volts=volts, bus=bus,
                    mhz=round(ratio * bus) if ratio and bus else None,
                    lo=self.min_ratio, hi=self.max_ratio)

    def close(self) -> None:
        if self.drv:
            self.drv.close()
            self.drv = None


# ───────────────────────── пам'ять: SPD через SMBus ─────────────────────────
READ, WRITE = 1, 0
BYTE, BYTE_DATA, PROC_CALL = 1, 2, 4


class BusLock:
    """Загальний м'ютекс шини SMBus (ним користуються HWiNFO, CPU-Z, LibreHardwareMonitor, OpenRGB)."""

    def __enter__(self):
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.ReleaseMutex.argtypes = k32.CloseHandle.argtypes = [ctypes.c_void_p]
        self.k32 = k32
        self.h = k32.CreateMutexW(None, False, "Global\\Access_SMBUS.HTP.Method")
        self.held = bool(self.h) and k32.WaitForSingleObject(self.h, 3000) in (0, 0x80)
        return self

    def __exit__(self, *a):
        if self.h:
            if self.held:
                self.k32.ReleaseMutex(self.h)
            self.k32.CloseHandle(self.h)


class SpdError(Exception):
    """Причина, чому SPD не прочитано (показуємо в «Пам'яті», а не мовчимо)."""


class Smbus:
    def __init__(self):
        self.drv = open_module(("SmbusI801", "SmbusPIIX4"))
        self.old_port, self.protected = None, False
        if not self.drv:
            return
        if self.drv.name == "SmbusPIIX4":  # SPD сидить на порту 0 контролера AMD
            out = self.drv.call("ioctl_piix4_port_sel", [0], 1)
            self.old_port = out[0] if out else None
        else:  # нові чипсети Intel забороняють запис у SPD — тоді сторінку DDR5 міняють через PROC_CALL
            out = self.drv.call("ioctl_write_protection", [], 1)
            self.protected = bool(out and out[0])

    def read(self, addr: int, cmd: int):
        out = self.drv.call("ioctl_smbus_xfer", [addr, READ, cmd, BYTE_DATA], 1)
        return out[0] & 0xFF if out else None

    def ack(self, addr: int) -> bool:
        """Чи відповідає пристрій на адресі (читання одного байта без команди)."""
        return self.drv.call("ioctl_smbus_xfer", [addr, READ, 0, BYTE], 1) is not None

    def write(self, addr: int, cmd: int, val: int) -> bool:
        return self.drv.call("ioctl_smbus_xfer", [addr, WRITE, cmd, BYTE_DATA, val], 0) is not None

    def close(self) -> bool:
        """-> чи повернули порт PIIX4 як був."""
        ok = True
        if self.drv:
            if self.old_port not in (None, 0, 2**64 - 1):
                ok = self.drv.call("ioctl_piix4_port_sel", [self.old_port], 1) is not None
            self.drv.close()
            self.drv = None
        return ok


# 7.1: лише байти, які розбирає parse_spd (~170 замість 512 транзакцій — менше тримаємо м'ютекс шини)
DDR4_BYTES = (range(0, 128), range(320, 350), range(384, 387))  # таймінги; виробник, дата, партномер; XMP
DDR5_PAGES = {0: range(0, 64), 4: range(512, 551), 5: range(640, 642), 6: range(832, 836)}


def _ddr4(bus: Smbus, addr: int, warn: list):
    # Частина модулів міняє сторінку без ACK на команду (ee1004.c, RAMSPDToolkit) — результат запису не
    # перевіряємо, а сторінку визначаємо так: 0x36 відповідає лише на сторінці 0.
    bus.write(0x36, 0, 0)
    if not bus.ack(0x36) or bus.read(addr, 2) != 0x0C:
        return None
    raw = bytearray(512)
    try:
        for rng in DDR4_BYTES:
            page = rng[0] >> 8
            if page:
                bus.write(0x37, 0, 0)
                if bus.ack(0x36):  # досі сторінка 0
                    return None
            for i in rng:
                b = bus.read(addr, i & 0xFF)
                if b is None:
                    return None
                raw[i] = b
    finally:
        bus.write(0x36, 0, 0)  # сторінка 0 — як після ввімкнення ПК
        if not bus.ack(0x36):
            warn.append("DDR4: page 0 not restored")
    return bytes(raw)


def _ddr5_page(bus: Smbus, addr: int, page: int) -> bool:
    if bus.protected:  # Intel із захистом запису: PROC_CALL (як RAMSPDToolkit)
        bus.drv.call("ioctl_smbus_xfer", [addr, READ, 0x0B, PROC_CALL, page], 1)
    else:
        bus.write(addr, 0x0B, page)
    cur = bus.read(addr, 0x0B)
    return cur is not None and cur & 0x0F == page


def _ddr5(bus: Smbus, addr: int, warn: list):
    if bus.read(addr, 0) != 0x51 or bus.read(addr, 1) != 0x18:  # концентратор SPD5118
        return None
    old = bus.read(addr, 0x0B)
    if old is None or old & 0x08:  # 2-байтова адресація — не наш режим, нічого не чіпаємо
        return None
    raw = bytearray(1024)
    try:
        for page, rng in DDR5_PAGES.items():
            if not _ddr5_page(bus, addr, page):
                return None if page == 0 else bytes(raw)
            for i in rng:
                b = bus.read(addr, 0x80 | (i & 0x7F))
                if b is None:
                    return None
                raw[i] = b
    finally:
        if not _ddr5_page(bus, addr, old & 0x0F):
            warn.append(f"DDR5 0x{addr:02X}: MR11 not restored")
    return bytes(raw) if raw[2] == 0x12 else None


def read_spd(mem_type: str, warn: list = None) -> list:
    """[(адреса, сирий SPD)] для кожного модуля. Лише DDR4 / DDR5 і лише якщо тип збігається зі SMBIOS.
    Не вдалося взагалі — SpdError з причиною; недоліки по дорозі (не повернули сторінку) — у warn."""
    warn = [] if warn is None else warn
    if not E.IS_WIN or mem_type not in ("DDR4", "DDR5"):
        return []
    out = []
    with BusLock() as lock:
        if not lock.held:
            raise SpdError("SMBus busy (Access_SMBUS.HTP.Method)")
        bus = Smbus()
        if not bus.drv:
            raise SpdError("no PawnIO SMBus module for this chipset")
        try:
            for addr in range(0x50, 0x58):
                raw = _ddr4(bus, addr, warn) if mem_type == "DDR4" else _ddr5(bus, addr, warn)
                if raw:
                    out.append((addr, raw))
        finally:
            if not bus.close():
                warn.append("PIIX4 port not restored")
    if not out:
        raise SpdError(f"no {mem_type} SPD answered on SMBus")
    return out


# ───────────────────────── розбір SPD (без заліза) ─────────────────────────
SPEEDS = {"DDR4": (1600, 1866, 2133, 2400, 2666, 2933, 3200),
          "DDR5": (4000, 4400, 4800, 5200, 5600, 6000, 6400, 6800, 7200, 7600, 8000, 8400, 8800)}


def _s8(b: int) -> int:
    return b - 256 if b > 127 else b


def _nck(t_ps: float, tck: float, kind: str = "DDR4") -> int:
    """Час -> такти з допуском JEDEC. DDR5: (t × 0.997 / tCK) з відкиданням + 1 (JESD400-5); DDR4: 2.5 %.
    SPD зберігає tCK округленим донизу (312.5 -> 312 пс), тож без допуску DDR5-6400 давав непарний CL53."""
    if kind == "DDR5":
        return max(1, (int(t_ps) * 997 // int(tck) + 1000) // 1000)
    return max(1, math.ceil(t_ps / tck - 0.025))


def _speed(tck: float, kind: str) -> int:
    mt = 2_000_000 / tck
    near = min(SPEEDS[kind], key=lambda s: abs(s - mt))
    return near if abs(near - mt) / mt < 0.02 else round(mt)


def _ascii(b: bytes) -> str:
    return b.decode("ascii", "replace").replace("\x00", " ").strip()


def _bcd(b: int):
    return (b >> 4) * 10 + (b & 0xF) if (b >> 4) < 10 and (b & 0xF) < 10 else None


def parse_spd(raw: bytes) -> dict:
    """Сирий SPD DDR4 (512 байтів) або DDR5 (сторінки 0, 4, 5, 6) -> тип, виробник, партномер, JEDEC, XMP / EXPO."""
    import hwinfo as HI
    if not raw or len(raw) < 512:
        return {}
    kind = {0x0C: "DDR4", 0x12: "DDR5"}.get(raw[2])
    if kind == "DDR4":
        tck = raw[18] * 125 + _s8(raw[125])
        if tck <= 0:
            return {}
        t = dict(aa=raw[24] * 125 + _s8(raw[123]), rcd=raw[25] * 125 + _s8(raw[122]),
                 rp=raw[26] * 125 + _s8(raw[121]), ras=((raw[27] & 0x0F) << 8 | raw[28]) * 125)
        cl_mask, cl_base, cl_step = int.from_bytes(raw[20:24], "little"), 7, 1
        if cl_mask >> 31:
            cl_mask, cl_base = cl_mask & 0x7FFFFFFF, 23
        mfr, part, year, week = raw[320:322], raw[329:349], raw[323], raw[324]
        xmp = raw[384:386] == b"\x0C\x4A"
        profiles = bin(raw[386] & 3).count("1") if xmp else 0
        expo = False
        ranks = (raw[12] >> 3 & 7) + 1
    elif kind == "DDR5":
        u16 = (lambda o: raw[o] | raw[o + 1] << 8)
        tck = u16(20)
        if not tck:
            return {}
        t = dict(aa=u16(30), rcd=u16(32), rp=u16(34), ras=u16(36))
        cl_mask, cl_base, cl_step = int.from_bytes(raw[24:29], "little"), 20, 2
        mfr, part, year, week = raw[512:514], raw[521:551], raw[515], raw[516]
        xmp = raw[640:642] == b"\x0C\x4A"
        profiles = 0
        expo = raw[832:836] == b"EXPO"  # 0x340, сторінка 6
        ranks = None  # байт 234 — на сторінці 1, яку не читаємо; ранг є в SMBIOS
    else:
        return {}
    cl = _nck(t["aa"], tck, kind)
    supported = [cl_base + i * cl_step for i in range(cl_mask.bit_length()) if cl_mask >> i & 1]
    cl = next((c for c in supported if c >= cl), cl)
    timings = (cl, _nck(t["rcd"], tck, kind), _nck(t["rp"], tck, kind), _nck(t["ras"], tck, kind))
    yy, ww = _bcd(year), _bcd(week)
    return dict(kind=kind, speed=_speed(tck, kind), mhz=round(1_000_000 / tck, 1), timings=timings,
                vendor=HI.JEDEC.get((mfr[0] & 0x7F, mfr[1] & 0x7F)), part=_ascii(part) or None, ranks=ranks,
                date=f"{ww}/{2000 + yy}" if yy is not None and ww else None, xmp=xmp, xmp_profiles=profiles,
                expo=expo)


def timings_text(s: dict) -> str:
    cl, rcd, rp, ras = s["timings"]
    return f"{cl}-{rcd}-{rp}-{ras} @ {s['speed']} MT/s"


def make_ddr4_spd(tck_mtb=5, aa=110, rcd=110, rp=110, ras=256, mfr=(0x01, 0x98), part="KF432C16BB/16",
                  xmp=True) -> bytes:
    """Синтетичний SPD DDR4 (для демо й тестів): типово DDR4-3200, 13.75 нс -> CL22-22-22-52, Kingston."""
    b = bytearray(512)
    b[2], b[12], b[18] = 0x0C, 1 << 3, tck_mtb
    b[20:24] = (0b111111111111111111 << 3).to_bytes(4, "little")  # CL10..CL27
    b[24], b[25], b[26] = aa, rcd, rp
    b[27], b[28] = ras >> 8 & 0x0F, ras & 0xFF
    b[320], b[321], b[323], b[324] = mfr[0], mfr[1], 0x23, 0x14
    b[329:349] = part.encode().ljust(20)
    if xmp:
        b[384:387] = b"\x0C\x4A\x03"
    return bytes(b)
