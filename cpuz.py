"""
OptimaX Hardware Center — процесор, кеш, плата, пам'ять і слоти, як у CPU-Z. Лише читання, без драйвера.

Джерела:
• CPUID — інструкція процесора (вісім байтів машинного коду в пам'яті «лише виконання», як у py-cpuinfo):
  виробник, рядок моделі, сімейство / модель / степінг, набір інструкцій. Кодове ім'я й техпроцес — з таблиці нижче.
• GetLogicalProcessorInformationEx — ядра, потоки, кеш L1 / L2 / L3 (розмір, асоціативність, скільки екземплярів).
• Лічильник «% Processor Performance» (PDH) — поточна частота, як у Диспетчері задач.
• SMBIOS — плата, BIOS, роз'єм процесора, частота шини за BIOS, кожен модуль пам'яті (ранг, напруга).
• PnP — чипсет за назвою контролера LPC / eSPI.

Чого без драйвера ядра не прочитати: напруга ядра, справжні множник і шина, таймінги з SPD (CL, tRCD, tRP, tRAS, XMP).
Якщо користувач встановив безкоштовний підписаний драйвер PawnIO, ці поля читає pawnio.py; ні — вони NEEDS_DRIVER
(«потрібен PawnIO»), а не вигадане число.
"""
from __future__ import annotations

import ctypes
import re
import struct

import engine as E
import hwnative as HN
import pawnio as PIO
from i18n import tr

# ───────────────────────── CPUID ─────────────────────────
# Windows x64: rcx = leaf, rdx = subleaf, r8 = куди записати eax, ebx, ecx, edx.
_CPUID_CODE = bytes([
    0x53,                          # push rbx
    0x89, 0xC8,                    # mov eax, ecx
    0x89, 0xD1,                    # mov ecx, edx
    0x0F, 0xA2,                    # cpuid
    0x41, 0x89, 0x00,              # mov [r8], eax
    0x41, 0x89, 0x58, 0x04,        # mov [r8+4], ebx
    0x41, 0x89, 0x48, 0x08,        # mov [r8+8], ecx
    0x41, 0x89, 0x50, 0x0C,        # mov [r8+12], edx
    0x5B,                          # pop rbx
    0xC3])                         # ret
_cpuid_fn = None


def _make_cpuid():
    """Код CPUID у пам'яті: спершу записуємо (RW), потім робимо лише виконуваною (RX) — без RWX-сторінок."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.VirtualAlloc.restype = ctypes.c_void_p
    k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    k32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    mem = k32.VirtualAlloc(None, 4096, 0x3000, 0x04)  # MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    if not mem:
        return None
    ctypes.memmove(mem, _CPUID_CODE, len(_CPUID_CODE))
    old = ctypes.c_uint32(0)
    if not k32.VirtualProtect(mem, 4096, 0x20, ctypes.byref(old)):  # PAGE_EXECUTE_READ
        return None
    proto = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32 * 4))
    return proto(mem)


def cpuid(leaf: int, sub: int = 0):
    """(eax, ebx, ecx, edx) або None поза Windows x64."""
    global _cpuid_fn
    if not E.IS_WIN or struct.calcsize("P") != 8:
        return None
    if _cpuid_fn is None:
        try:
            _cpuid_fn = _make_cpuid() or False
        except Exception:
            _cpuid_fn = False
    if not _cpuid_fn:
        return None
    out = (ctypes.c_uint32 * 4)()
    _cpuid_fn(leaf, sub, ctypes.byref(out))
    return tuple(out)


def read_cpuid_dump() -> dict:
    """Потрібні листки CPUID: {(leaf, sub): (eax, ebx, ecx, edx)}."""
    r0 = cpuid(0)
    if not r0:
        return {}
    dump = {(0, 0): r0}
    for leaf in range(1, min(r0[0], 7) + 1):
        dump[(leaf, 0)] = cpuid(leaf)
    if r0[0] >= 7:
        dump[(7, 1)] = cpuid(7, 1)
    e0 = cpuid(0x80000000)
    dump[(0x80000000, 0)] = e0
    for leaf in range(0x80000001, min(e0[0], 0x80000008) + 1):
        dump[(leaf, 0)] = cpuid(leaf)
    return dump


def _regs_str(*regs) -> str:
    return b"".join(struct.pack("<I", r) for r in regs).decode("ascii", "ignore").strip("\x00 ")


# (біт, назва): leaf 1 edx / ecx, leaf 7 ebx / ecx / edx, leaf 7.1 eax, 0x80000001 ecx / edx
FEATURES = (
    ((1, 0, 3), 23, "MMX"), ((1, 0, 3), 25, "SSE"), ((1, 0, 3), 26, "SSE2"), ((1, 0, 2), 0, "SSE3"),
    ((1, 0, 2), 9, "SSSE3"), ((1, 0, 2), 19, "SSE4.1"), ((1, 0, 2), 20, "SSE4.2"),
    ((0x80000001, 0, 2), 6, "SSE4A"), ((0x80000001, 0, 3), 29, "x86-64"), ((1, 0, 2), 5, "VT-x"),
    ((0x80000001, 0, 2), 2, "AMD-V"), ((1, 0, 2), 25, "AES"), ((1, 0, 2), 28, "AVX"), ((7, 0, 1), 5, "AVX2"),
    ((7, 1, 0), 4, "AVX-VNNI"), ((7, 0, 1), 16, "AVX512F"), ((7, 0, 1), 17, "AVX512DQ"), ((7, 0, 1), 28, "AVX512CD"),
    ((7, 0, 1), 30, "AVX512BW"), ((7, 0, 1), 31, "AVX512VL"), ((7, 0, 2), 11, "AVX512_VNNI"),
    ((7, 0, 3), 23, "AVX512_FP16"), ((1, 0, 2), 12, "FMA3"), ((0x80000001, 0, 2), 16, "FMA4"),
    ((7, 0, 1), 29, "SHA"), ((7, 0, 2), 8, "GFNI"), ((7, 0, 2), 9, "VAES"))


def parse_cpuid(dump: dict) -> dict:
    """Сирі регістри CPUID -> виробник, назва, сімейство / модель / степінг, інструкції."""
    if not dump or (0, 0) not in dump:
        return {}
    r0 = dump[(0, 0)]
    vendor = _regs_str(r0[1], r0[3], r0[2])
    d = dict(vendor_id=vendor, vendor={"GenuineIntel": "Intel", "AuthenticAMD": "AMD"}.get(vendor, vendor))
    if all((x, 0) in dump for x in (0x80000002, 0x80000003, 0x80000004)):
        d["spec"] = re.sub(r"\s+", " ", _regs_str(*dump[(0x80000002, 0)], *dump[(0x80000003, 0)],
                                                   *dump[(0x80000004, 0)])).strip()
    eax = (dump.get((1, 0)) or (0, 0, 0, 0))[0]
    fam, mod, step = eax >> 8 & 0xF, eax >> 4 & 0xF, eax & 0xF
    efam, emod = eax >> 20 & 0xFF, eax >> 16 & 0xF
    d.update(family=fam, model=mod, stepping=step, ext_family=fam + efam if fam == 0xF else fam,
             ext_model=(emod << 4) + mod if fam in (6, 0xF) else mod)
    feats = []
    for (leaf, sub, reg), bit, name in FEATURES:
        r = dump.get((leaf, sub))
        if r and r[reg] >> bit & 1:
            feats.append(name)
    if d["vendor"] == "Intel" and "x86-64" in feats:
        feats[feats.index("x86-64")] = "EM64T"
    d["instructions"] = feats
    return d


# Кодові імена й техпроцес: (виробник, сімейство, модель) -> (ім'я, техпроцес). Загальновідомі дані виробників.
CODENAMES = {
    ("Intel", 6, 0x0F): ("Merom", "65 nm"), ("Intel", 6, 0x17): ("Penryn", "45 nm"),
    ("Intel", 6, 0x1A): ("Bloomfield", "45 nm"), ("Intel", 6, 0x1E): ("Lynnfield", "45 nm"),
    ("Intel", 6, 0x25): ("Clarkdale", "32 nm"), ("Intel", 6, 0x2C): ("Gulftown", "32 nm"),
    ("Intel", 6, 0x2A): ("Sandy Bridge", "32 nm"), ("Intel", 6, 0x2D): ("Sandy Bridge-E", "32 nm"),
    ("Intel", 6, 0x3A): ("Ivy Bridge", "22 nm"), ("Intel", 6, 0x3E): ("Ivy Bridge-E", "22 nm"),
    ("Intel", 6, 0x3C): ("Haswell", "22 nm"), ("Intel", 6, 0x45): ("Haswell-ULT", "22 nm"),
    ("Intel", 6, 0x46): ("Haswell", "22 nm"), ("Intel", 6, 0x3F): ("Haswell-E", "22 nm"),
    ("Intel", 6, 0x3D): ("Broadwell", "14 nm"), ("Intel", 6, 0x47): ("Broadwell", "14 nm"),
    ("Intel", 6, 0x4F): ("Broadwell-E/EP", "14 nm"), ("Intel", 6, 0x4E): ("Skylake", "14 nm"),
    ("Intel", 6, 0x5E): ("Skylake", "14 nm"), ("Intel", 6, 0x55): ("Skylake-X/SP", "14 nm"),
    ("Intel", 6, 0x8E): ("Kaby/Whiskey/Amber Lake", "14 nm"), ("Intel", 6, 0x9E): ("Kaby/Coffee Lake", "14 nm"),
    ("Intel", 6, 0xA5): ("Comet Lake", "14 nm"), ("Intel", 6, 0xA6): ("Comet Lake", "14 nm"),
    ("Intel", 6, 0xA7): ("Rocket Lake", "14 nm"), ("Intel", 6, 0x7D): ("Ice Lake", "10 nm"),
    ("Intel", 6, 0x7E): ("Ice Lake", "10 nm"), ("Intel", 6, 0x8C): ("Tiger Lake", "10 nm SuperFin"),
    ("Intel", 6, 0x8D): ("Tiger Lake", "10 nm SuperFin"), ("Intel", 6, 0x97): ("Alder Lake", "Intel 7"),
    ("Intel", 6, 0x9A): ("Alder Lake", "Intel 7"), ("Intel", 6, 0xBE): ("Alder Lake-N", "Intel 7"),
    ("Intel", 6, 0xB7): ("Raptor Lake", "Intel 7"), ("Intel", 6, 0xBA): ("Raptor Lake", "Intel 7"),
    ("Intel", 6, 0xBF): ("Raptor Lake", "Intel 7"), ("Intel", 6, 0xAA): ("Meteor Lake", "Intel 4"),
    ("Intel", 6, 0xAC): ("Meteor Lake", "Intel 4"), ("Intel", 6, 0xBD): ("Lunar Lake", "TSMC N3B"),
    ("Intel", 6, 0xC5): ("Arrow Lake", "TSMC N3B"), ("Intel", 6, 0xC6): ("Arrow Lake", "TSMC N3B"),
    ("Intel", 6, 0x37): ("Bay Trail", "22 nm"), ("Intel", 6, 0x4C): ("Braswell/Cherry Trail", "14 nm"),
    ("Intel", 6, 0x5C): ("Apollo Lake", "14 nm"), ("Intel", 6, 0x7A): ("Gemini Lake", "14 nm"),
    ("Intel", 6, 0x9C): ("Jasper Lake", "10 nm"), ("Intel", 6, 0x96): ("Elkhart Lake", "10 nm"),
    ("AMD", 0x15, 0x01): ("Zambezi (Bulldozer)", "32 nm"), ("AMD", 0x15, 0x02): ("Vishera (Piledriver)", "32 nm"),
    ("AMD", 0x15, 0x10): ("Trinity (Piledriver)", "32 nm"), ("AMD", 0x15, 0x13): ("Richland (Piledriver)", "32 nm"),
    ("AMD", 0x15, 0x30): ("Kaveri (Steamroller)", "28 nm"), ("AMD", 0x15, 0x38): ("Godavari (Steamroller)", "28 nm"),
    ("AMD", 0x15, 0x60): ("Carrizo (Excavator)", "28 nm"), ("AMD", 0x15, 0x65): ("Bristol Ridge (Excavator)", "28 nm"),
    ("AMD", 0x15, 0x70): ("Stoney Ridge (Excavator)", "28 nm"), ("AMD", 0x16, 0x00): ("Kabini (Jaguar)", "28 nm"),
    ("AMD", 0x16, 0x30): ("Beema/Mullins (Puma)", "28 nm"),
    ("AMD", 0x17, 0x01): ("Summit Ridge (Zen)", "14 nm"), ("AMD", 0x17, 0x08): ("Pinnacle Ridge (Zen+)", "12 nm"),
    ("AMD", 0x17, 0x11): ("Raven Ridge (Zen)", "14 nm"), ("AMD", 0x17, 0x18): ("Picasso (Zen+)", "12 nm"),
    ("AMD", 0x17, 0x20): ("Dali (Zen)", "14 nm"), ("AMD", 0x17, 0x31): ("Castle Peak/Rome (Zen 2)", "7 nm"),
    ("AMD", 0x17, 0x60): ("Renoir (Zen 2)", "7 nm"), ("AMD", 0x17, 0x68): ("Lucienne (Zen 2)", "7 nm"),
    ("AMD", 0x17, 0x71): ("Matisse (Zen 2)", "7 nm"), ("AMD", 0x17, 0x90): ("Van Gogh (Zen 2)", "7 nm"),
    ("AMD", 0x17, 0xA0): ("Mendocino (Zen 2)", "6 nm"), ("AMD", 0x19, 0x01): ("Milan (Zen 3)", "7 nm"),
    ("AMD", 0x19, 0x08): ("Chagall (Zen 3)", "7 nm"), ("AMD", 0x19, 0x21): ("Vermeer (Zen 3)", "7 nm"),
    ("AMD", 0x19, 0x40): ("Rembrandt (Zen 3+)", "6 nm"), ("AMD", 0x19, 0x44): ("Rembrandt-R (Zen 3+)", "6 nm"),
    ("AMD", 0x19, 0x50): ("Cezanne (Zen 3)", "7 nm"), ("AMD", 0x19, 0x11): ("Genoa (Zen 4)", "5 nm"),
    ("AMD", 0x19, 0x18): ("Storm Peak (Zen 4)", "5 nm"), ("AMD", 0x19, 0x61): ("Raphael (Zen 4)", "5 nm"),
    ("AMD", 0x19, 0x74): ("Phoenix (Zen 4)", "4 nm"), ("AMD", 0x19, 0x75): ("Hawk Point (Zen 4)", "4 nm"),
    ("AMD", 0x19, 0x78): ("Phoenix 2 (Zen 4)", "4 nm"), ("AMD", 0x1A, 0x24): ("Strix Point (Zen 5)", "4 nm"),
    ("AMD", 0x1A, 0x44): ("Granite Ridge (Zen 5)", "4 nm"), ("AMD", 0x1A, 0x60): ("Krackan Point (Zen 5)", "4 nm"),
    ("AMD", 0x1A, 0x70): ("Strix Halo (Zen 5)", "4 nm"),
}


def codename(vendor: str, family: int, model: int, stepping: int = 0, brand: str = "") -> tuple:
    """(кодове ім'я, техпроцес) або (None, None). Kaby/Coffee Lake розрізняє степінг."""
    if vendor == "Intel" and family == 6 and model == 0x9E:
        return ("Kaby Lake", "14 nm") if stepping <= 9 else ("Coffee Lake", "14 nm")
    if vendor == "Intel" and family == 6 and model == 0x8E and stepping >= 11:
        return "Whiskey/Comet Lake-U", "14 nm"
    return CODENAMES.get((vendor, family, model), (None, None))


def short_name(spec: str) -> str:
    """«13th Gen Intel(R) Core(TM) i7-13700K» -> «Intel Core i7-13700K», як «Name» у CPU-Z."""
    s = re.sub(r"\((R|TM|tm|r)\)|®|™", "", spec or "")
    s = re.sub(r"^\d+(st|nd|rd|th) Gen\s+", "", s)
    s = re.sub(r"\s*@.*$", "", s)
    s = re.sub(r"\s+\d+-Core\b.*$", "", s)
    s = re.sub(r"\b(CPU|Processor|with Radeon Graphics)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


# ───────────────────────── кеш (Windows) ─────────────────────────
CACHE_TYPE = {0: "unified", 1: "inst", 2: "data", 3: "trace"}


def parse_cache_relations(raw: bytes) -> list:
    """Буфер GetLogicalProcessorInformationEx(RelationCache) -> [(рівень, тип, розмір КБ, асоціативність, рядок)]."""
    out, off = [], 0
    while off + 8 <= len(raw):
        rel, size = struct.unpack_from("<II", raw, off)
        if not size:
            break
        if rel == 2 and off + 20 <= len(raw):
            level, assoc, line, csize, ctype = struct.unpack_from("<BBHII", raw, off + 8)
            out.append((level, CACHE_TYPE.get(ctype, "unified"), csize // 1024, assoc, line))
        off += size
    return out


def cache_summary(rel: list) -> list:
    """[(ключ мови, «8 x 48 KB + 8 x 32 KB», «12-way»)] — L1 дані, L1 інструкції, L2, L3, як «Caches» у CPU-Z."""
    groups = {}
    for level, kind, kb, assoc, _line in rel:
        groups.setdefault((level, kind), {}).setdefault((kb, assoc), 0)
        groups[(level, kind)][(kb, assoc)] += 1
    out = []
    for key, lk in (((1, "data"), "cz.l1d"), ((1, "inst"), "cz.l1i"), ((2, "unified"), "cz.l2"),
                    ((3, "unified"), "cz.l3")):
        g = groups.get(key)
        if not g:
            continue
        parts = sorted(g.items(), key=lambda x: -x[0][0])
        size = " + ".join(f"{n} x {_kb(kb)}" if n > 1 else _kb(kb) for (kb, _a), n in parts)
        ways = " + ".join(dict.fromkeys(f"{a}-way" if a not in (0, 0xFF) else "fully assoc."
                                        for (_kb_, a), _n in parts))
        out.append((lk, size, ways))
    return out


def _kb(kb: int) -> str:
    return f"{kb // 1024} MB" if kb >= 1024 and kb % 1024 == 0 else f"{kb} KB"


def read_cache_raw() -> bytes:
    if not E.IS_WIN:
        return b""
    k32 = ctypes.windll.kernel32
    size = ctypes.c_ulong(0)
    k32.GetLogicalProcessorInformationEx(2, None, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if not size.value or not k32.GetLogicalProcessorInformationEx(2, buf, ctypes.byref(size)):
        return b""
    return buf.raw[:size.value]


# ───────────────────────── поточна частота (PDH, як Диспетчер задач) ─────────────────────────
class ClockMeter:
    """Поточна частота = базова × «% Processor Performance» / 100. Перше читання — через ~1 с після створення."""
    COUNTER = r"\Processor Information(_Total)\% Processor Performance"

    def __init__(self, base_mhz: int):
        self.base, self.q, self.c = base_mhz, None, None
        if not E.IS_WIN or not base_mhz:
            return
        try:
            pdh = ctypes.WinDLL("pdh")
            q, c = ctypes.c_void_p(), ctypes.c_void_p()
            if pdh.PdhOpenQueryW(None, None, ctypes.byref(q)) == 0 and \
                    pdh.PdhAddEnglishCounterW(q, self.COUNTER, None, ctypes.byref(c)) == 0:
                pdh.PdhCollectQueryData(q)
                self.pdh, self.q, self.c = pdh, q, c
        except Exception:
            self.q = None

    def mhz(self):
        if not self.q:
            return None

        class Val(ctypes.Structure):
            _fields_ = [("status", ctypes.c_uint32), ("pad", ctypes.c_uint32), ("value", ctypes.c_double)]
        v = Val()
        if self.pdh.PdhCollectQueryData(self.q) != 0:
            return None
        if self.pdh.PdhGetFormattedCounterValue(self.c, 0x200, None, ctypes.byref(v)) != 0 or v.status not in (0, 1):
            return None
        return round(self.base * v.value / 100) if v.value > 0 else None

    def close(self):
        if self.q:
            self.pdh.PdhCloseQuery(self.q)
            self.q = None


# ───────────────────────── SMBIOS: процесор, пам'ять ─────────────────────────
def smbios_cpu_mem(raw: bytes) -> dict:
    """Роз'єм і частота шини за BIOS (тип 4), ранг і напруга модулів (тип 17)."""
    if not raw:
        return {}
    structs, _ver = HN.parse_smbios(raw)
    out = dict(mods=[])
    for typ, _h, fmt, strings in structs:
        if typ == 4 and "socket" not in out:
            out["socket"] = HN._str(strings, HN._byte(fmt, 0x04)) or None
            out["bus_bios"] = HN._word(fmt, 0x12) or None
        elif typ == 17 and (HN._word(fmt, 0x0C) or 0) not in (0, 0xFFFF):
            attr = HN._byte(fmt, 0x1B)
            mv = HN._word(fmt, 0x26)
            out["mods"].append(dict(rank=(attr & 0x0F) or None if attr is not None else None,
                                    mv=mv or None, width=HN._word(fmt, 0x0A) or None))
    return out


def socket_name(s) -> str:
    """Лише справжня назва роз'єму: «LGA1700», «AM5», «FCLGA1700», «BGA1744» — не «CPU 1» чи «U3E1»."""
    s = (s or "").strip()
    return s if re.search(r"\b(?:FC)?LGA\s?\d+|\bAM[2-5]\+?\b|\bFM2\+?\b|\bBGA\s?\d+|\bsTR[X\d]*|\bSP\d\b|Socket",
                          s, re.I) else ""


def channels(modules: list) -> str:
    """Кількість каналів за назвами слотів («ChannelA-DIMM0», «DIMM_A1», «P0 CHANNEL B»); інакше None."""
    seen = set()
    for m in modules:
        name = f"{m.get('slot') or ''} {m.get('bank') or ''}"
        mt = re.search(r"channel\s*([A-H])\b|channel([A-H])-|\bDIMM_?([A-H])\d", name, re.I)
        if mt:
            seen.add((mt.group(1) or mt.group(2) or mt.group(3)).upper())
    return len(seen) or None


# ───────────────────────── чипсет (PnP) ─────────────────────────
CHIPSET_SCRIPT = r"""
$n=@(Get-CimInstance Win32_PnPEntity -Filter "PNPClass='System'" -EA SilentlyContinue |
  Where-Object { $_.DeviceID -like 'PCI\*' -and $_.Name -match 'LPC|eSPI|ISA|SMBus|Chipset|FCH' } |
  ForEach-Object { [string]$_.Name }); $n | ConvertTo-Json -Compress
"""


def chipset_from_names(names: list):
    """«Intel(R) Z790 Chipset LPC/eSPI Controller - 7A04» -> «Intel Z790»; AMD — «AMD FCH» з назви SMBus/LPC."""
    for n in names or []:
        m = re.search(r"Intel\S*\s+(?:\(R\)\s*)?([A-Z]{1,2}\d{2,3}[A-Z]?)\s+(?:Chipset|LPC|Express|eSPI)", n)
        if m:
            return f"Intel {m.group(1)}"
    for n in names or []:
        if re.search(r"\bAMD\b", n) and re.search(r"FCH|SMBus|LPC", n):
            return "AMD FCH"
    return None


# ───────────────────────── усе разом ─────────────────────────
DEMO = {
    "gaming": dict(cpuid=dict(vendor="Intel", family=6, model=7, stepping=1, ext_family=6, ext_model=0xB7,
                              spec="13th Gen Intel(R) Core(TM) i7-13700K",
                              instructions=["MMX", "SSE", "SSE2", "SSE3", "SSSE3", "SSE4.1", "SSE4.2", "EM64T", "VT-x",
                                            "AES", "AVX", "AVX2", "AVX-VNNI", "FMA3", "SHA"]),
                   caches=[(1, "data", 48, 12, 64)] * 8 + [(1, "data", 32, 8, 64)] * 8 + [(1, "inst", 32, 8, 64)] * 8
                   + [(1, "inst", 64, 8, 64)] * 8 + [(2, "unified", 2048, 16, 64)] * 8
                   + [(2, "unified", 4096, 16, 64)] * 2 + [(3, "unified", 30720, 12, 64)],
                   socket="LGA1700", bus_bios=100, chipset="Intel Z790",
                   mods=[dict(rank=2, mv=1350, width=64)] * 2, clock=5276),
    "x3d": dict(cpuid=dict(vendor="AMD", family=0xF, model=1, stepping=2, ext_family=0x19, ext_model=0x61,
                           spec="AMD Ryzen 9 7950X3D 16-Core Processor",
                           instructions=["MMX", "SSE", "SSE2", "SSE3", "SSSE3", "SSE4.1", "SSE4.2", "SSE4A", "x86-64",
                                         "AMD-V", "AES", "AVX", "AVX2", "AVX512F", "AVX512DQ", "AVX512CD", "AVX512BW",
                                         "AVX512VL", "AVX512_VNNI", "FMA3", "SHA"]),
                caches=[(1, "data", 32, 8, 64)] * 16 + [(1, "inst", 32, 8, 64)] * 16
                + [(2, "unified", 1024, 8, 64)] * 16
                + [(3, "unified", 98304, 16, 64), (3, "unified", 32768, 16, 64)],
                socket="AM5", bus_bios=100, chipset="AMD FCH", mods=[dict(rank=1, mv=1350, width=64)] * 2,
                clock=5012),
    "old": dict(cpuid=dict(vendor="Intel", family=6, model=0xC, stepping=4, ext_family=6, ext_model=0x4C,
                           spec="Intel(R) Celeron(R) CPU N3060 @ 1.60GHz",
                           instructions=["MMX", "SSE", "SSE2", "SSE3", "SSSE3", "SSE4.1", "SSE4.2", "EM64T", "VT-x",
                                         "AES"]),
                caches=[(1, "data", 24, 6, 64)] * 2 + [(1, "inst", 32, 8, 64)] * 2 + [(2, "unified", 1024, 16, 64)],
                socket="BGA1170", bus_bios=80, chipset=None, mods=[dict(rank=1, mv=1350, width=64)], clock=2480),
}
DEMO["laptop"] = dict(DEMO["gaming"], cpuid=dict(DEMO["gaming"]["cpuid"], ext_model=0xBA, stepping=2,
                                                  spec="13th Gen Intel(R) Core(TM) i5-13500H"),
                      socket="BGA1744", chipset=None, clock=4100)


def collect(hw: dict, info: dict = None) -> dict:
    """Усі вкладки разом. info — hwinfo.collect(hw) (плата, BIOS, модулі, відеокарти), щоб не читати двічі.
    Повільне (PowerShell для чипсету) — тут, тож викликати у фоновому потоці."""
    import hwinfo as HI
    hw = hw or {}
    info = info if info is not None else HI.collect(hw)
    if E.IS_WIN:
        cid = parse_cpuid(read_cpuid_dump())
        caches = parse_cache_relations(read_cache_raw())
        sm = smbios_cpu_mem(HN.smbios_raw())
        try:
            names = E.as_list(E.ps_json(CHIPSET_SCRIPT, 30))
        except Exception:
            names = []
        chipset = chipset_from_names([n for n in names if isinstance(n, str)])
    else:
        dm = DEMO.get(E.DEMO, DEMO["gaming"])
        cid, caches, chipset = dict(dm["cpuid"]), list(dm["caches"]), dm["chipset"]
        sm = dict(socket=dm["socket"], bus_bios=dm["bus_bios"], mods=dm["mods"])
    spec = cid.get("spec") or hw.get("cpu") or ""
    code, tech = codename(cid.get("vendor") or "", cid.get("ext_family") or 0, cid.get("ext_model") or 0,
                          cid.get("stepping") or 0, spec)
    cpu = dict(name=short_name(spec) or None, codename=code, technology=tech, package=socket_name(sm.get("socket")),
               spec=spec or None, family=cid.get("family"), model=cid.get("model"), stepping=cid.get("stepping"),
               ext_family=cid.get("ext_family"), ext_model=cid.get("ext_model"),
               instructions=cid.get("instructions") or [], base_mhz=hw.get("mhz") or None,
               bus_bios=sm.get("bus_bios"), cores=hw.get("cores"), threads=hw.get("threads"),
               p_cores=hw.get("p_cores"), e_cores=hw.get("e_cores") or None, voltage=None)
    ram = info.get("ram") or {}
    mods = list(ram.get("modules") or [])
    for m, extra in zip([m for m in mods if m.get("mb")], sm.get("mods") or []):
        m.update(rank=extra.get("rank"), mv=extra.get("mv"))
    gpu_links = {g.get("name"): g for g in hw.get("gpu_pci") or []}
    # 7.1: PawnIO — множник, напруга й шина з MSR, таймінги з SPD; без драйвера ці поля NEEDS_DRIVER
    drv, live, spd, spd_error = PIO.status(), None, [], None
    if drv == "ok":
        live = PIO.CpuLive(cid.get("vendor") or "", cid.get("ext_family") or 0, cid.get("ext_model") or 0,
                           int(HN._reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "~MHz") or 0))
        if not live.ok:
            live = None
        try:
            spd = [PIO.parse_spd(raw) for _a, raw in PIO.read_spd(ram.get("type") or "")]
        except Exception as e:  # покажемо в примітці, а не сховаємо
            spd_error = f"{type(e).__name__}: {e}"
    elif drv == "demo":
        spd = [PIO.parse_spd(PIO.make_ddr4_spd()) for m in mods if m.get("mb")]
    for m, s in zip([m for m in mods if m.get("mb")], [s for s in spd if s]):
        m["spd"] = s
    return dict(cpu=cpu, caches=cache_summary(caches), board=dict(info.get("board") or {}, chipset=chipset),
                bios=info.get("bios") or {}, ram=dict(ram, channels=channels(mods), modules=mods),
                gpus=[dict(g, link=gpu_links.get(g.get("name"))) for g in info.get("gpus") or []], driver=drv,
                live=live, spd_error=spd_error,
                demo_clock=None if E.IS_WIN else DEMO.get(E.DEMO, DEMO["gaming"]).get("clock"))


def demo_live(d: dict, clock) -> dict:
    """Демо: як виглядає «Процесор» із PawnIO (поза Windows драйвера немає)."""
    if d.get("driver") != "demo" or not clock:
        return {}
    intel = (d.get("cpu") or {}).get("spec", "").find("Intel") >= 0
    return dict(ratio=round(clock / 99.8), bus=99.8, mhz=clock, volts=1.284 if intel else None,
                lo=8 if intel else None, hi=54 if intel else None)


# ───────────────────────── вкладки як рядки (для інтерфейсу й звіту) ─────────────────────────
NEEDS_DRIVER = object()  # поле, яке без драйвера ядра не прочитати (напруга, справжня шина, таймінги)


def _n(v, unit=""):
    return None if v in (None, "", 0) else f"{v}{unit}"


def _drv(d: dict, value, spd: bool = False):
    """Значення з PawnIO; драйвера немає — NEEDS_DRIVER; драйвер є, але регістр не дав відповіді — None («----»).
    spd=True: SPD читаємо лише з DDR4 / DDR5 — для DDR3 і старіших PawnIO не допоможе, тож там просто «----»."""
    if value is not None:
        return value
    if spd and ((d.get("ram") or {}).get("type") or "") not in ("DDR4", "DDR5"):
        return None
    return None if d.get("driver") in ("ok", "demo") else NEEDS_DRIVER


def cpu_rows(d: dict, clock=None, live: dict = None) -> list:
    """live — CpuLive.read() (або demo_live): множник, напруга, шина; тоді частота = множник × шина, як у CPU-Z."""
    c, lv = d.get("cpu") or {}, live or {}
    hexf = (lambda v: None if v is None else f"{v:X}")
    cores = c.get("cores")
    if c.get("e_cores"):
        cores = f"{c['cores']} ({c['p_cores']}P + {c['e_cores']}E)"
    clock = lv.get("mhz") or clock
    mult = None
    if lv.get("ratio"):
        mult = f"x{lv['ratio']:g}" + (f" ({lv['lo']} – {lv['hi']})" if lv.get("lo") and lv.get("hi") else "")
    bus = f"{lv['bus']:.2f} MHz" if lv.get("bus") else None
    if bus is None and d.get("driver") not in ("ok", "demo") and c.get("bus_bios"):
        bus = f"{c['bus_bios']} MHz ({tr('cz.by_bios')})"
    volts = f"{lv['volts']:.3f} V" if lv.get("volts") else None
    return [("cz.name", c.get("name")), ("cz.codename", c.get("codename")), ("cz.package", c.get("package")),
            ("cz.technology", c.get("technology")), ("cz.voltage", _drv(d, volts)), ("cz.spec", c.get("spec")),
            ("cz.family", hexf(c.get("family"))), ("cz.model", hexf(c.get("model"))),
            ("cz.stepping", hexf(c.get("stepping"))), ("cz.ext_family", hexf(c.get("ext_family"))),
            ("cz.ext_model", hexf(c.get("ext_model"))), ("cz.instructions", ", ".join(c.get("instructions") or [])),
            ("cz.clock", f"{clock} MHz" if clock else None),
            ("cz.multiplier", mult or (f"≈ x{clock / 100:.1f}" if clock and d.get("driver") not in ("ok", "demo")
                                       else _drv(d, None))),
            ("cz.bus", bus or _drv(d, None)),
            ("cz.base", _n(c.get("base_mhz"), " MHz")), ("cz.cores", cores), ("cz.threads", c.get("threads"))]


def cache_rows(d: dict) -> list:
    return [(k, f"{size}   {ways}") for k, size, ways in d.get("caches") or []]


def board_rows(d: dict) -> list:
    b, bi = d.get("board") or {}, d.get("bios") or {}
    gfx = next((g.get("link") for g in d.get("gpus") or [] if g.get("link")), None)
    link = None
    if gfx and gfx.get("mw"):
        link = f"PCI-Express x{gfx['mw']}" + (f" ({tr('cz.current')} x{gfx['cw']})" if gfx.get("cw") else "")
    return [("cz.board_vendor", b.get("vendor")), ("cz.board_model", b.get("model")),
            ("cz.board_rev", b.get("version")), ("cz.chipset", b.get("chipset")),
            ("cz.bios_brand", bi.get("vendor")), ("cz.bios_version", bi.get("version")),
            ("cz.bios_date", bi.get("date")), ("cz.firmware", bi.get("type")),
            ("cz.secure_boot", None if bi.get("secure_boot") is None
             else tr("hwc.yes" if bi["secure_boot"] else "hwc.no")),
            ("cz.gfx_link", link)]


def memory_rows(d: dict) -> list:
    r = d.get("ram") or {}
    mods = [m for m in r.get("modules") or [] if m.get("mb")]
    conf = max((m.get("conf") or 0 for m in mods), default=0) or r.get("speed")
    ch = r.get("channels")
    spd = next((m["spd"] for m in mods if m.get("spd")), None)
    return [("cz.mem_type", r.get("type")), ("cz.mem_size", _n(r.get("total_gb"), " GB")),
            ("cz.channels", f"{ch} x 64-bit" if ch else None), ("cz.modules", f"{len(mods)} / {r.get('slots') or '?'}"
                                                                 if mods else None),
            ("cz.dram_freq", f"{conf / 2:.1f} MHz" if conf else None), ("cz.effective", _n(conf, " MT/s")),
            ("cz.max_speed", _n(r.get("max_speed"), " MT/s")),
            ("cz.jedec", _drv(d, PIO.timings_text(spd) if spd else None, True)),
            ("cz.profiles", _drv(d, profiles_text(spd) if spd else None, True))]


def profiles_text(s: dict) -> str:
    out = []
    if s.get("xmp"):
        out.append(f"XMP ({s['xmp_profiles']})" if s.get("xmp_profiles") else "XMP")
    if s.get("expo"):
        out.append("EXPO")
    return ", ".join(out) or tr("cz.no_profiles")


def slot_rows(m: dict, d: dict = None) -> list:
    s = m.get("spd") or {}
    d = d or {}
    return [("cz.slot", m.get("slot")), ("cz.mod_size", f"{m['mb'] // 1024} GB" if m.get("mb") else None),
            ("cz.mem_type", " ".join(x for x in (m.get("type"), m.get("form")) if x) or None),
            ("cz.max_speed", _n(m.get("speed"), " MT/s")), ("cz.effective", _n(m.get("conf"), " MT/s")),
            ("cz.mod_vendor", m.get("vendor")), ("cz.part", m.get("part")),
            ("cz.rank", {1: "Single", 2: "Dual", 4: "Quad"}.get(m.get("rank"), _n(m.get("rank")))),
            ("cz.mod_voltage", f"{m['mv'] / 1000:.2f} V" if m.get("mv") else None),
            ("cz.mfg_date", s.get("date")),
            ("cz.jedec", _drv(d, PIO.timings_text(s) if s else None, True)),
            ("cz.profiles", _drv(d, profiles_text(s) if s else None, True))]


def gpu_rows(g: dict) -> list:
    link = g.get("link") or {}
    pcie = f"PCI-Express x{link['cw']} / x{link['mw']}" if link.get("cw") and link.get("mw") else None
    return [("cz.gpu_name", g.get("name")), ("cz.gpu_vendor", g.get("vendor")),
            ("cz.vram", f"{g['vram_gb']:g} GB" if g.get("vram_gb") else None), ("cz.driver_date", g.get("driver_date")),
            ("cz.gfx_link", pcie)]


def report_text(d: dict, clock=None, live: dict = None) -> str:
    """Текстовий звіт, як «Save report» у CPU-Z."""
    def block(title, rows):
        out = [title, "-" * 60]
        for k, v in rows:
            v = tr("cz.needs_driver") if v is NEEDS_DRIVER else ("----" if v in (None, "") else v)
            out.append(f"  {tr(k):<26}: {v}")
        return out + [""]
    lines = [f"OptimaX {E.VERSION} — {tr('cz.title')}", ""]
    lines += block(tr("cz.tab.cpu"), cpu_rows(d, clock, live))
    lines += block(tr("cz.tab.caches"), cache_rows(d))
    lines += block(tr("cz.tab.board"), board_rows(d))
    lines += block(tr("cz.tab.memory"), memory_rows(d))
    for m in [m for m in (d.get("ram") or {}).get("modules") or [] if m.get("mb")]:
        lines += block(f"{tr('cz.tab.spd')}: {m.get('slot') or '?'}", slot_rows(m, d))
    for g in d.get("gpus") or []:
        lines += block(f"{tr('cz.tab.gpu')}: {g.get('name') or '?'}", gpu_rows(g))
    return "\n".join(lines)
