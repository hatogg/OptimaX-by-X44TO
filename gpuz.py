"""
OptimaX Hardware Center — паспорт відеокарти, як у GPU-Z. Лише читання, без драйвера ядра.

Для кожного адаптера (їх буває кілька: HD 4000 з монітором + майнінгова P106-100 без виходів, ноутбук з Optimus):
• SetupAPI (ctypes) — ідентифікатори VEN / DEV / SUBSYS / REV з Instance ID, розташування на шині, PDO-ім'я,
  стан лінії PCIe: DEVPKEY_PciDevice_CurrentLinkSpeed / Width і MaxLinkSpeed / Width (максимум — те, що вміє карта;
  поточне — що зараз узгоджено зі слотом).
• Розділ драйвера в Control\\Class — версія й дата драйвера, обсяг пам'яті (HardwareInformation.*), рядок
  відео-BIOS і тип пам'яті, лише якщо драйвер їх записав (інакше «—», без здогадок).
• NVML — спільний сеанс з hardware.gpu_temp (7.1.1, без повторного nvmlInit): відео-BIOS, ширина шини пам'яті, поточні
  й максимальні частоти, температура, завантаження, лінія PCIe під навантаженням. Карти NVML зіставляються з PnP за
  номером шини PCI — дві однакові P106 не плутаються.
• Resizable BAR — найбільше вікно пам'яті з карти ресурсів PnP (логіка 7.0.1 з hardware.py).
• DirectX 12 і Vulkan — лише з перевірки gpuinfo.probe (окремий процес), OpenGL — з останнього GPU-тесту на цій карті.
Кількість шейдерів, ROP і TMU не показуємо: без бази даних моделей надійного джерела для них немає.
"""
from __future__ import annotations

import copy
import ctypes
import random
import re
import struct

import engine as E
import hwnative as HN
from i18n import tr

# ───────────────────────── PCIe ─────────────────────────
# Поле Link Speed регістрів PCIe (так його й віддає Windows): 1 — 2.5 GT/s (Gen1), 2 — 5, 3 — 8, 4 — 16, 5 — 32, 6 — 64
PCIE_GT = {1: "2.5", 2: "5", 3: "8", 4: "16", 5: "32", 6: "64"}
PCIE_GEN = {1: "1.1", 2: "2.0", 3: "3.0", 4: "4.0", 5: "5.0", 6: "6.0"}


def _int(v):
    try:
        return int(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def link_gen(code) -> str:
    """Код швидкості лінії -> «3.0»; невідомий код — None."""
    return PCIE_GEN.get(_int(code))


def fmt_link(code, width):
    """(3, 16) -> «PCIe 3.0 x16 · 8 GT/s»; без ширини — None; невідома швидкість — лише ширина."""
    code, width = _int(code), _int(width)
    if not width:
        return None
    gen = link_gen(code)
    return f"PCIe {gen} x{width} · {PCIE_GT[code]} GT/s" if gen else f"PCIe x{width}"


def current_link(a: dict, live: dict = None) -> dict:
    """Поточна лінія: NVML під час живого читання (свіжіше), інакше — те, що прочитано з PnP."""
    lk, lv = dict(a.get("link") or {}), live or {}
    if lv.get("pcie_gen") and lv.get("pcie_width"):
        lk.update(cs=lv["pcie_gen"], cw=lv["pcie_width"])
        lk.setdefault("ms", lv.get("pcie_max_gen"))
        lk.setdefault("mw", lv.get("pcie_max_width"))
    return lk


def live_link(live: dict) -> bool:
    """Чи поточна лінія — з живого читання NVML (а не з DEVPKEY, який може показувати стан на момент старту)."""
    return bool((live or {}).get("pcie_gen") and (live or {}).get("pcie_width"))


def link_state(link: dict, util=None) -> str:
    """unknown | narrow (менше ліній, ніж уміє карта) | slow_idle (нижче покоління в простої — енергозбереження) |
    slow_load (нижче покоління під навантаженням) | full."""
    cs, cw, ms, mw = (_int((link or {}).get(k)) for k in ("cs", "cw", "ms", "mw"))
    if not cw or not mw:
        return "unknown"
    if cw < mw:
        return "narrow"
    if cs and ms and cs < ms:
        return "slow_load" if util is not None and util >= 50 else "slow_idle"
    return "full"


# ───────────────────────── розбір ідентифікаторів і реєстру ─────────────────────────
VENDORS = {0x10DE: "NVIDIA", 0x1002: "AMD", 0x1022: "AMD", 0x8086: "Intel", 0x1414: "Microsoft", 0x1A03: "ASPEED",
           0x102B: "Matrox", 0x15AD: "VMware", 0x80EE: "VirtualBox", 0x1234: "QEMU", 0x1AF4: "Red Hat (virtio)"}
# Виробники плат (підсистема PCI) — загальновідомі ідентифікатори PCI-SIG
SUBVENDORS = {**VENDORS, **{
    0x1043: "ASUS", 0x1458: "Gigabyte", 0x1462: "MSI", 0x3842: "EVGA", 0x19DA: "Zotac", 0x1569: "Palit",
    0x10B0: "Gainward", 0x1DA2: "Sapphire", 0x148C: "PowerColor", 0x1682: "XFX", 0x1849: "ASRock", 0x7377: "Colorful",
    0x1B4C: "Galax / KFA2", 0x196E: "PNY", 0x17AA: "Lenovo", 0x103C: "HP", 0x1028: "Dell", 0x1025: "Acer",
    0x144D: "Samsung", 0x1179: "Toshiba", 0x104D: "Sony", 0x1558: "Clevo", 0x152D: "Quanta", 0x1D05: "Tongfang"}}

_INST_RE = re.compile(r"VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})(?:&SUBSYS_([0-9A-F]{8}))?(?:&REV_([0-9A-F]{2}))?", re.I)


def parse_instance_id(inst: str) -> dict:
    """«PCI\\VEN_10DE&DEV_1C07&SUBSYS_11D710DE&REV_A1\\4&…» -> ven, dev, sub (32 біти, як SubSysId у DXGI), rev."""
    m = _INST_RE.search(inst or "")
    if not m:
        return {}
    return dict(ven=int(m.group(1), 16), dev=int(m.group(2), 16),
                sub=int(m.group(3), 16) if m.group(3) else None, rev=m.group(4).upper() if m.group(4) else None)


def device_id_text(a: dict):
    """GPU-Z: «10DE 1C07 - 10DE 11D7» (виробник і пристрій — виробник і модель плати)."""
    if a.get("ven") is None or a.get("dev") is None:
        return None
    s = f"{a['ven']:04X} {a['dev']:04X}"
    if a.get("sub"):
        s += f" - {a['sub'] & 0xFFFF:04X} {a['sub'] >> 16:04X}"
    return s


def subvendor(a: dict):
    sub = a.get("sub")
    if not sub:
        return None
    sv = sub & 0xFFFF
    return f"{SUBVENDORS.get(sv, '?')} ({sv:04X})" if sv in SUBVENDORS else f"{sv:04X}"


def parse_location(text: str):
    """«PCI bus 1, device 0, function 0» (у локалізованій Windows — іншими словами) -> (1, 0, 0) або None."""
    nums = re.findall(r"\d+", text or "")
    return tuple(int(x) for x in nums) if len(nums) == 3 else None


def fmt_location(loc):
    return f"{loc[0]:02X}:{loc[1]:02X}.{loc[2]}" if loc and len(loc) == 3 else None


def decode_reg_string(v):
    """Рядок з розділу драйвера: REG_SZ або REG_BINARY (часто UTF-16 LE з нулями). Не текст — None."""
    if isinstance(v, (bytes, bytearray)):
        b = bytes(v)
        if len(b) >= 2 and len(b) % 2 == 0 and b[1:2] == b"\0":
            s = b.decode("utf-16-le", "ignore")
        else:
            s = b.decode("latin-1", "ignore")
    elif isinstance(v, str):
        s = v
    else:
        return None
    s = re.sub(r"\s+", " ", s.replace("\0", " ")).strip()
    if not s or sum(ch.isprintable() for ch in s) < len(s) or not re.search(r"[0-9A-Za-z]", s):
        return None
    return s


_MEMTYPE_RE = re.compile(r"\b(GDDR\d[XW]?|LPDDR\d[X]?|DDR\d|HBM\d?E?)\b", re.I)


def mem_type_from_reg(v):
    """Тип пам'яті — лише рядок, у якому прямо названо тип (GDDR6, HBM2…). Число (код виробника) — невідомо (None)."""
    m = _MEMTYPE_RE.search(decode_reg_string(v) or "")
    if not m:
        return None
    t = m.group(1).upper()
    return t[:-1] + "e" if t.startswith("HBM") and t.endswith("E") else t


def nv_driver_version(win_ver: str):
    """Версія драйвера Windows «31.0.15.8278» -> версія NVIDIA «582.78» (останні 5 цифр двох останніх груп)."""
    parts = str(win_ver or "").split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts) or len(parts[3]) != 4:
        return None
    s = parts[2][-1:] + parts[3]
    return f"{int(s[:3])}.{s[3:]}"


def decode_devprop(typ: int, raw: bytes):
    """Значення SetupDiGetDevicePropertyW за DEVPROPTYPE; непідтримуваний тип — None."""
    try:
        if typ == 0x03:  # BYTE
            return raw[0]
        if typ == 0x05:  # UINT16
            return struct.unpack_from("<H", raw)[0]
        if typ in (0x06, 0x07):  # INT32 / UINT32
            return struct.unpack_from("<i" if typ == 0x06 else "<I", raw)[0]
        if typ in (0x08, 0x09, 0x10):  # INT64 / UINT64 / FILETIME
            return struct.unpack_from("<q" if typ == 0x08 else "<Q", raw)[0]
        if typ == 0x11:  # BOOLEAN: 0 — ні, 0xFF — так
            return raw[0] != 0
        if typ == 0x12:  # STRING
            return raw.decode("utf-16-le", "ignore").split("\0", 1)[0]
        if typ == 0x2012:  # STRING_LIST
            return [s for s in raw.decode("utf-16-le", "ignore").split("\0") if s]
        if typ == 0x1003:  # BINARY
            return bytes(raw)
    except (struct.error, IndexError):
        return None
    return None


def parse_nvml_pci(raw: bytes) -> dict:
    """nvmlPciInfo_t (v1–v3 однакові на початку): busIdLegacy[16], domain, bus, device, pciDeviceId, pciSubSystemId."""
    try:
        _bid, domain, bus, device, pci_id, subsys = struct.unpack_from("<16s5I", raw, 0)
    except struct.error:
        return {}
    return dict(domain=domain, bus=bus, device=device, ven=pci_id & 0xFFFF, dev=pci_id >> 16, sub=subsys)


# ───────────────────────── SetupAPI (Windows) ─────────────────────────
_PCI = "{3ab22e31-8264-4b4e-9af5-a8d2d8e33e62}"  # DEVPKEY_PciDevice_*
_DEV = "{a45c254e-df1c-4efd-8020-67d146a850e0}"  # DEVPKEY_Device_*
PROPS = {"cs": (_PCI, 9), "cw": (_PCI, 10), "ms": (_PCI, 11), "mw": (_PCI, 12), "desc": (_DEV, 2), "driver": (_DEV, 11),
         "name": (_DEV, 14), "location": (_DEV, 15), "pdo": (_DEV, 16), "bus": (_DEV, 23), "addr": (_DEV, 30)}


class _DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", HN._GUID), ("pid", ctypes.c_ulong)]


def pnp_adapters() -> list:
    """Присутні відеоадаптери на шині PCI: [{instance, name, driver, cs, cw, ms, mw, loc, pdo}]."""
    if not E.IS_WIN:
        return []
    sa = ctypes.WinDLL("setupapi", use_last_error=True)  # власний екземпляр — argtypes не чіпають hwnative
    sa.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    sa.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(HN._GUID), ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_ulong]
    sa.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(HN._SP_DEVINFO_DATA)]
    sa.SetupDiGetDeviceInstanceIdW.argtypes = [ctypes.c_void_p, ctypes.POINTER(HN._SP_DEVINFO_DATA), ctypes.c_wchar_p,
                                               ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    sa.SetupDiGetDevicePropertyW.argtypes = [ctypes.c_void_p, ctypes.POINTER(HN._SP_DEVINFO_DATA),
                                             ctypes.POINTER(_DEVPROPKEY), ctypes.POINTER(ctypes.c_ulong),
                                             ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                             ctypes.c_ulong]
    sa.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    keys = {}
    for k, (fmt, pid) in PROPS.items():
        keys[k] = _DEVPROPKEY(HN._guid(fmt), pid)
    g = HN._guid(HN.DISPLAY_CLASS)
    h = sa.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x2)  # DIGCF_PRESENT
    if not h or h == ctypes.c_void_p(-1).value:
        return []
    out = []
    try:
        for i in range(64):
            dd = HN._SP_DEVINFO_DATA()
            dd.cbSize = ctypes.sizeof(dd)
            if not sa.SetupDiEnumDeviceInfo(h, i, ctypes.byref(dd)):
                break
            inst = ctypes.create_unicode_buffer(512)
            if not sa.SetupDiGetDeviceInstanceIdW(h, ctypes.byref(dd), inst, 512, None) or \
                    not inst.value.upper().startswith("PCI\\"):
                continue  # Microsoft Basic Display, віддалені й віртуальні дисплеї — не на шині PCI
            d = dict(instance=inst.value)
            for k, key in keys.items():
                typ, buf, need = ctypes.c_ulong(0), ctypes.create_string_buffer(1024), ctypes.c_ulong(0)
                if sa.SetupDiGetDevicePropertyW(h, ctypes.byref(dd), ctypes.byref(key), ctypes.byref(typ), buf, 1024,
                                                ctypes.byref(need), 0):
                    d[k] = decode_devprop(typ.value, buf.raw[:need.value])
            addr = d.pop("addr", None)
            if isinstance(d.get("bus"), int) and isinstance(addr, int):
                d["loc"] = (d["bus"], addr >> 16, addr & 0xFFFF)  # для PCI Address = (пристрій << 16) | функція
            else:
                d["loc"] = parse_location(d.get("location") if isinstance(d.get("location"), str) else "")
            d["name"] = d.get("name") or d.get("desc") or ""
            out.append(d)
    finally:
        sa.SetupDiDestroyDeviceInfoList(h)
    return out


def registry_extras(driver_key: str) -> dict:
    """Версія й дата драйвера, обсяг пам'яті, відео-BIOS і тип пам'яті з розділу драйвера (те, що драйвер записав)."""
    if not driver_key:
        return {}
    di = HN.driver_info(driver_key)
    key = HN.CLASS_ROOT + "\\" + driver_key
    return dict(driver_version=di.get("version") or None, driver_date=di.get("date") or None,
                vram_mb=round(di["vram"] * 1024) if di.get("vram") else None,
                vbios=decode_reg_string(HN._reg(key, "HardwareInformation.BiosString")),
                mem_type=mem_type_from_reg(HN._reg(key, "HardwareInformation.MemoryType")))


# ───────────────────────── NVML (спільний сеанс з hardware.gpu_temp) ─────────────────────────
def _session():
    """Відкритий сеанс NVML з кешу hardware (7.1.1). Викликати під hardware._NV_LOCK."""
    import gpubench as GB
    import hardware as H
    nv = H._NV_CACHE.get("")
    if nv is None or not nv.ok:
        nv = GB.Nvml("")
        if not nv.ok:
            return None
        H._NV_CACHE[""] = nv
    return nv


def _view(nv, index: int, uuid: str = ""):
    """Копія сеансу, що дивиться на іншу карту: той самий nvml.dll і nvmlInit, інший дескриптор. Не закривати."""
    v = copy.copy(nv)
    return v if v.select_index(index, uuid) else None


def nv_static(lib, h) -> dict:
    """Те, що не змінюється: максимальні частоти, ширина шини пам'яті, відео-BIOS, адреса на шині PCI."""
    out, v = {}, ctypes.c_uint(0)

    def call(name, *args):
        fn = getattr(lib, name, None)
        try:
            return fn is not None and fn(h, *args) == 0
        except Exception:
            return False
    if call("nvmlDeviceGetMaxClockInfo", 0, ctypes.byref(v)):  # NVML_CLOCK_GRAPHICS
        out["max_clock"] = int(v.value)
    if call("nvmlDeviceGetMaxClockInfo", 2, ctypes.byref(v)):  # NVML_CLOCK_MEM
        out["max_mem_clock"] = int(v.value)
    if call("nvmlDeviceGetMemoryBusWidth", ctypes.byref(v)) and v.value:
        out["bus_width"] = int(v.value)
    buf = ctypes.create_string_buffer(64)
    if call("nvmlDeviceGetVbiosVersion", buf, 64):
        out["vbios"] = buf.value.decode("ascii", "replace") or None
    raw = ctypes.create_string_buffer(256)
    for fn in ("nvmlDeviceGetPciInfo_v3", "nvmlDeviceGetPciInfo_v2", "nvmlDeviceGetPciInfo"):
        if call(fn, raw):
            out["pci"] = parse_nvml_pci(raw.raw)
            break
    return out


def nvml_devices() -> list:
    """[{index, uuid, name, mem_total (МБ), max_clock, max_mem_clock, bus_width, vbios, pci}] усіх карт NVIDIA."""
    if not E.IS_WIN:
        return []
    import hardware as H
    out = []
    try:
        with H._NV_LOCK:
            nv = _session()
            if nv is None:
                return []
            for idx, name, total in nv.devices():
                v = _view(nv, idx)
                if v is None:
                    continue
                d = dict(index=idx, uuid=v.uuid(), name=name, mem_total=total // 2**20 if total else None)
                d.update(nv_static(v.lib, v.h))
                out.append(d)
    except Exception:
        return out
    return out


def match_nvml(adapters: list, nvs: list) -> None:
    """Кожній карті NVIDIA — її пристрій NVML (a["nv"]): за шиною й пристроєм PCI, далі за унікальним VEN/DEV/SUBSYS,
    далі — одна карта NVIDIA й один пристрій NVML. Не зіставилось — без NVML (датчики «—»), а не чужі датчики."""
    free = list(nvs or [])
    nvidia = [a for a in adapters if a.get("ven") == 0x10DE]
    for a in nvidia:
        loc = a.get("loc")
        hit = next((n for n in free if loc and (n.get("pci") or {}).get("bus") == loc[0]
                    and (n.get("pci") or {}).get("device") == loc[1]), None)
        if hit:
            a["nv"] = hit
            free.remove(hit)
    for a in [a for a in nvidia if "nv" not in a]:
        same = [n for n in free if (n.get("pci") or {}).get("dev") == a.get("dev")
                and (n.get("pci") or {}).get("sub") == a.get("sub")]
        twins = [x for x in nvidia if "nv" not in x and x.get("dev") == a.get("dev") and x.get("sub") == a.get("sub")]
        if len(same) == 1 and len(twins) == 1:
            a["nv"] = same[0]
            free.remove(same[0])
    left = [a for a in nvidia if "nv" not in a]
    if len(left) == 1 and len(free) == 1 and len(nvidia) == len(nvs or []):
        left[0]["nv"] = free[0]


# ───────────────────────── усе разом ─────────────────────────
def _dxgi_for(a: dict, dxgi: list, used: set) -> dict:
    for i, d in enumerate(dxgi or []):
        if i in used or d.get("software"):
            continue
        if d.get("ven") == a.get("ven") and d.get("dev") == a.get("dev") and \
                (not a.get("sub") or not d.get("sub") or (d["sub"] & 0xFFFFFFFF) == a["sub"]):
            used.add(i)
            return d
    return {}


def _gl_for(name: str, bench: list):
    """OpenGL — з останнього GPU-тесту, який справді малювала ця карта (GL_RENDERER збігся з назвою)."""
    import gpubench as GB
    k = GB.gpu_key(name)
    for b in reversed(bench or []):
        r = GB.gpu_key(b.get("renderer") or "")
        if k and r and (r == k or k in r or r in k) and b.get("gl"):
            return str(b["gl"])
    return None


def assemble(pnps: list, nvs: list, probe: dict, bench: list = None, hw: dict = None) -> list:
    """Сирі дані PnP + реєстру, NVML, gpuinfo.probe і GPU-тестів -> паспорти адаптерів (порядок — як на шині)."""
    import gpuinfo as GI
    import gpuselect as GS
    import hardware as H
    hw = hw or {}
    probe = probe or {}
    pci_hw = {g.get("name"): g for g in hw.get("gpu_pci") or []}
    disp = GI.display_adapter(probe) if probe.get("dxgi") else {}
    used, out = set(), []
    for p in pnps:
        if re.search(H.VIRTUAL_GPU, p.get("name") or "", re.I):
            continue
        a = dict(parse_instance_id(p.get("instance") or ""), name=p.get("name") or "", loc=p.get("loc"),
                 link={k: p.get(k) for k in ("cs", "cw", "ms", "mw") if _int(p.get(k))})
        for k in ("driver_version", "driver_date", "vram_mb", "vbios", "mem_type", "bar_mb", "bar_known"):
            a[k] = p.get(k)
        a["vbios_src"] = "reg" if a.get("vbios") else None
        out.append(a)
    match_nvml(out, nvs)
    for a in out:
        nv = a.get("nv") or {}
        if nv:  # NVML надійніший за реєстр: справжній обсяг і рядок відео-BIOS з самої карти
            a.update(nv_index=nv.get("index"), nv_uuid=nv.get("uuid") or "", max_clock=nv.get("max_clock"),
                     max_mem_clock=nv.get("max_mem_clock"), bus_width=nv.get("bus_width"))
            if nv.get("mem_total"):
                a["vram_mb"] = nv["mem_total"]
            if nv.get("vbios"):
                a["vbios"], a["vbios_src"] = nv["vbios"], "nvml"
        a["vendor"] = VENDORS.get(a.get("ven"))
        a["nv_driver"] = nv_driver_version(a.get("driver_version")) if a.get("ven") == 0x10DE else None
        dx = _dxgi_for(a, probe.get("dxgi"), used)
        a["probed"] = bool(probe.get("dxgi"))
        a["dx12"] = dx.get("dx12") if dx else None
        a["shared_mb"] = dx.get("shared_mb") if dx else None
        if not a.get("vram_mb") and dx.get("vram_mb"):
            a["vram_mb"] = dx["vram_mb"]
        a["display"] = bool(dx and disp and dx.get("luid") == disp.get("luid")) or \
            (not disp and bool(hw.get("display_gpu")) and hw.get("display_gpu") == a["name"])
        vk = GI.vulkan_for(probe, dx) if dx else {}
        a["vk_api"], a["vk_driver"] = vk.get("api"), vk.get("driver")
        a["gl"] = _gl_for(a["name"], bench)
        a["kind"] = GS.kind_of(dict(ven=a.get("ven"), dev=a.get("dev"), name=a["name"], vram_mb=a.get("vram_mb") or 0))
        if a.get("bar_mb") is None and pci_hw.get(a["name"]):  # карта ресурсів не прочиталась — з detect_hw
            g = pci_hw[a["name"]]
            a["bar_mb"], a["bar_known"] = g.get("bar_mb"), g.get("bar_known", True)
        if not a["link"] and pci_hw.get(a["name"]):
            g = pci_hw[a["name"]]
            a["link"] = {k: g.get(k) for k in ("cs", "cw", "ms", "mw") if _int(g.get(k))}
        a.pop("nv", None)
    return out


def collect(hw: dict = None) -> dict:
    """Усі адаптери. Повільне (реєстр, NVML) — викликати у фоновому потоці."""
    import features as F
    import gpuselect as GS
    hw = hw or {}
    bench = F.CFG["bench"] or []
    if E.IS_WIN:
        import hardware as H
        pnps = pnp_adapters()
        for p in pnps:
            p.update({k: v for k, v in registry_extras(p.get("driver") or "").items() if v is not None})
            big = H.resource_map_max_mem(p.get("pdo"))
            if big is not None:
                p["bar_mb"], p["bar_known"] = round(big / 2**20), True
        nvs = nvml_devices() if any(parse_instance_id(p["instance"]).get("ven") == 0x10DE for p in pnps) else []
        probe = GS.cached_probe()
    else:
        pnps, nvs = demo_raw()
        import gpuinfo as GI
        probe = GS.cached_probe() or dict(GI.DEMO_PROBE.get(E.DEMO) or {})
    return dict(adapters=assemble(pnps, nvs, probe, bench, hw), probed=bool(probe.get("dxgi")))


def live(a: dict) -> dict:
    """Поточні показники карти NVIDIA (температура, частоти, завантаження, лінія PCIe). Інші карти — {}."""
    if not E.IS_WIN:
        d = DEMO_LIVE.get((E.DEMO, a.get("name")))
        if not d:
            return {}
        d = dict(d)
        for k in ("clock", "mem_clock"):
            if d.get(k):
                d[k] += random.choice((-13, 0, 0, 13))
        d["temp"] = (d.get("temp") or 0) + random.choice((-1, 0, 0, 1)) if d.get("temp") is not None else None
        return d
    if a.get("nv_index") is None:
        return {}
    import hardware as H
    try:
        with H._NV_LOCK:
            nv = _session()
            v = _view(nv, a["nv_index"], a.get("nv_uuid") or "") if nv else None
            return v.read() if v else {}
    except Exception:
        return {}


# ───────────────────────── демо (поза Windows) ─────────────────────────
def _d(name, inst, ver, date, loc, link=None, vram=None, vbios=None, bar=None, nv=None):
    p = dict(instance=inst, name=name, driver_version=ver, driver_date=date, loc=loc, vram_mb=vram, vbios=vbios)
    if link:
        p.update(cs=link[0], cw=link[1], ms=link[2], mw=link[3])
    if bar:
        p["bar_mb"], p["bar_known"] = bar, True
    return p, nv


_RTX4070 = _d("NVIDIA GeForce RTX 4070", r"PCI\VEN_10DE&DEV_2786&SUBSYS_51361458&REV_A1\4&2B6C1A3&0&0008",
              "32.0.15.8157", "2024-02-10", (1, 0, 0), (1, 16, 4, 16), 12282, None, 256,
              dict(max_clock=3105, max_mem_clock=10501, bus_width=192, vbios="95.04.31.00.4B", mem_total=12282))
DEMO = {
    "gaming": [_RTX4070],
    "laptop": [_d("Intel(R) Iris(R) Xe Graphics", r"PCI\VEN_8086&DEV_A7A0&SUBSYS_1E1F1043&REV_04\3&11583659&0&10",
                  "31.0.101.6130", "2025-03-01", (0, 2, 0), vram=128),
               _d("NVIDIA GeForce RTX 4050 Laptop GPU", r"PCI\VEN_10DE&DEV_28A1&SUBSYS_1E1F1043&REV_A1\4&3A1C2E&0&0008",
                  "32.0.15.8157", "2025-03-01", (1, 0, 0), (1, 8, 4, 8), 6141, None, 6144,
                  dict(max_clock=2580, max_mem_clock=8001, bus_width=96, vbios="95.07.36.00.2D", mem_total=6141))],
    "old": [_d("Intel(R) HD Graphics 400", r"PCI\VEN_8086&DEV_22B1&SUBSYS_8231103C&REV_35\3&11583659&0&10",
               "20.19.15.5107", "2019-05-12", (0, 2, 0))],
    # майнінгова P106-100 через райзер x1: монітор — на HD 4000, кожен кадр гри йде шиною x1
    "mining": [_d("Intel(R) HD Graphics 4000", r"PCI\VEN_8086&DEV_0162&SUBSYS_01621849&REV_09\3&11583659&0&10",
                  "10.18.10.4358", "2015-11-10", (0, 2, 0), vram=32),
               _d("NVIDIA P106-100", r"PCI\VEN_10DE&DEV_1C07&SUBSYS_11D710DE&REV_A1\4&1F0A5C3&0&00E4",
                  "31.0.15.8278", "2023-04-12", (3, 0, 0), (1, 1, 3, 16), 6144, None, 256,
                  dict(max_clock=1911, max_mem_clock=4004, bus_width=192, vbios="86.06.3C.00.A8", mem_total=6144))],
    "x3d": [_d("AMD Radeon RX 7900 XTX", r"PCI\VEN_1002&DEV_744C&SUBSYS_471E1DA2&REV_C8\6&2E1A4B7&0&00000019",
               "32.0.12033.1030", "2025-01-20", (3, 0, 0), (4, 16, 4, 16), 24560, "113-D7020100-102", 24576),
            _d("AMD Radeon(TM) Graphics", r"PCI\VEN_1002&DEV_164E&SUBSYS_88771043&REV_C1\6&1B2C3D4&0&00000041",
               "32.0.12033.1030", "2025-01-20", (16, 0, 0), vram=512)],
    "xeon": [_d("NVIDIA GeForce GTX 1660 SUPER", r"PCI\VEN_10DE&DEV_21C4&SUBSYS_13051462&REV_A1\4&9C1D2E&0&0010",
                "31.0.15.3161", "2023-06-01", (2, 0, 0), (3, 4, 3, 16), 6144, None, 256,
                dict(max_clock=2100, max_mem_clock=7001, bus_width=192, vbios="90.16.48.00.8C", mem_total=6144))],
}
DEMO_LIVE = {
    ("gaming", "NVIDIA GeForce RTX 4070"): dict(temp=38, clock=210, mem_clock=405, util=2, power=12.4, fan=0,
                                                vram_used=812, vram_total=12282, pcie_gen=1, pcie_width=16),
    ("laptop", "NVIDIA GeForce RTX 4050 Laptop GPU"): dict(temp=46, clock=210, mem_clock=405, util=0, power=3.1,
                                                           vram_used=96, vram_total=6141, pcie_gen=1, pcie_width=8),
    ("mining", "NVIDIA P106-100"): dict(temp=47, clock=139, mem_clock=405, util=0, power=6.2, fan=30, vram_used=84,
                                        vram_total=6144, pcie_gen=1, pcie_width=1),
    ("xeon", "NVIDIA GeForce GTX 1660 SUPER"): dict(temp=41, clock=300, mem_clock=405, util=1, power=9.8, fan=33,
                                                    vram_used=402, vram_total=6144, pcie_gen=3, pcie_width=4),
}


def demo_raw(name: str = None) -> tuple:
    """Демо-залізо як сирі дані PnP і NVML — через ті самі assemble / match_nvml, що й на Windows."""
    pnps, nvs = [], []
    for p, nv in DEMO.get(name or E.DEMO, DEMO["gaming"]):
        pnps.append(dict(p))
        if nv:
            ids = parse_instance_id(p["instance"])
            nvs.append(dict(nv, index=len(nvs), uuid=f"GPU-demo-{len(nvs)}", name=p["name"],
                            pci=dict(bus=p["loc"][0], device=p["loc"][1], ven=ids["ven"], dev=ids["dev"],
                                     sub=ids["sub"])))
    return pnps, nvs


# ───────────────────────── рядки (для інтерфейсу й звіту) ─────────────────────────
def _u(v, unit=""):
    return None if v in (None, "") else f"{v}{unit}"


def rebar_text(a: dict):
    """Увімкнено (BAR ≈ уся пам'ять), вимкнено (лише коли прочитано всю карту ресурсів), інакше None."""
    bar = a.get("bar_mb")
    if a.get("kind") == "igpu" or not bar:
        return None
    if bar > 300:
        return tr("gz.rebar_on", mb=bar)
    return tr("gz.rebar_off", mb=bar) if a.get("bar_known") else None


def role_text(a: dict) -> str:
    parts = [tr(f"gz.kind.{a.get('kind') or 'dgpu'}")]
    if a.get("display"):
        parts.append(tr("gz.display"))
    return " · ".join(parts)


def device_rows(a: dict) -> list:
    drv = a.get("driver_version")
    if drv and a.get("nv_driver"):
        drv = f"{drv} (NVIDIA {a['nv_driver']})"
    vb = a.get("vbios")
    if vb and a.get("vbios_src") == "reg":
        vb = f"{vb} ({tr('gz.src_reg')})"
    return [("gz.name", a.get("name")), ("gz.vendor", a.get("vendor")), ("gz.subvendor", subvendor(a)),
            ("gz.device_id", device_id_text(a)), ("gz.revision", a.get("rev")), ("gz.role", role_text(a)),
            ("gz.driver", drv), ("gz.driver_date", a.get("driver_date")), ("gz.vbios", vb),
            ("gz.location", fmt_location(a.get("loc")))]


def bus_rows(a: dict, live: dict = None) -> list:
    lk = current_link(a, live)
    cur = fmt_link(lk.get("cs"), lk.get("cw"))
    if cur and not live_link(live):
        cur = f"{cur} ({tr('gz.src_win')})"
    return [("gz.bus_cur", cur), ("gz.bus_max", fmt_link(lk.get("ms"), lk.get("mw"))),
            ("gz.rebar", rebar_text(a))]


def memory_rows(a: dict, live: dict = None) -> list:
    lv = live or {}
    size = _u(a.get("vram_mb"), " MB")
    if size and a.get("kind") == "igpu" and a.get("shared_mb"):
        size = tr("gz.mem_shared", mb=a["vram_mb"], shared=a["shared_mb"])
    used = f"{lv['vram_used']} / {lv.get('vram_total') or a.get('vram_mb') or '?'} MB" \
        if lv.get("vram_used") is not None else None
    return [("gz.mem_size", size), ("gz.mem_type", a.get("mem_type")),
            ("gz.bus_width", _u(a.get("bus_width"), "-bit")), ("gz.mem_used", used)]


def sensor_rows(a: dict, live: dict = None) -> list:
    lv = live or {}
    return [("gz.clock", _u(lv.get("clock"), " MHz")), ("gz.clock_max", _u(a.get("max_clock"), " MHz")),
            ("gz.mem_clock", _u(lv.get("mem_clock"), " MHz")), ("gz.mem_clock_max", _u(a.get("max_mem_clock"), " MHz")),
            ("gz.temp", _u(lv.get("temp"), " °C")), ("gz.load", _u(lv.get("util"), " %")),
            ("gz.power", _u(lv.get("power"), " W")), ("gz.fan", _u(lv.get("fan"), " %"))]


def api_rows(a: dict) -> list:
    dx = None if a.get("dx12") is None else tr("gz.dx12_yes" if a["dx12"] else "gz.dx12_no")
    vk = None
    if a.get("vk_api"):
        vk = a["vk_api"] + (f" ({tr('gz.drv')} {a['vk_driver']})" if a.get("vk_driver") else "")
    return [("gz.dx12", dx), ("gz.vulkan", vk), ("gz.opengl", a.get("gl"))]


GROUPS = (("gz.g.device", lambda a, lv: device_rows(a)), ("gz.g.bus", bus_rows), ("gz.g.memory", memory_rows),
          ("gz.g.sensors", sensor_rows), ("gz.g.api", lambda a, lv: api_rows(a)))
LIVE_KEYS = {"gz.bus_cur", "gz.mem_used", "gz.clock", "gz.mem_clock", "gz.temp", "gz.load", "gz.power", "gz.fan"}


def findings(a: dict, live: dict = None) -> list:
    """[(рівень ok | info | warn, текст)]: лінія PCIe, Resizable BAR, звідки датчики."""
    import hardware as H
    lv = live or {}
    lk = current_link(a, lv)
    st = link_state(lk, lv.get("util"))
    out = []
    if st == "narrow":
        out.append(("warn", tr("gz.f.narrow", cur=lk["cw"], max=lk["mw"])))
    elif st in ("slow_idle", "slow_load"):
        kw = dict(cur=link_gen(lk.get("cs")) or "?", max=link_gen(lk.get("ms")) or "?")
        if not live_link(lv):
            # 7.2: поточна швидкість лише з DEVPKEY — Windows могла записати її при старті пристрою й не оновлювати,
            # тож ні «під навантаженням», ні «натисніть «Оновити»» тут не обіцяємо
            out.append(("info", tr("gz.f.slow_pnp", **kw)))
        else:
            out.append(("info", tr("gz.f.slow_idle", **kw)) if st == "slow_idle" else
                       ("warn", tr("gz.f.slow_load", util=lv.get("util"), **kw)))
    elif st == "full":
        out.append(("ok", tr("gz.f.full", link=fmt_link(lk.get("cs"), lk.get("cw")))))
    elif a.get("kind") == "igpu":
        out.append(("info", tr("gz.f.igpu_bus")))
    else:
        out.append(("info", tr("gz.f.no_link")))
    if a.get("kind") != "igpu" and a.get("bar_known") and (a.get("bar_mb") or 0) <= 300 and a.get("bar_mb"):
        rel = H.rebar_relevance(a.get("name") or "")
        if rel:
            out.append(("warn" if rel == "critical" else "info", tr("gz.f.rebar_off")))
    if a.get("kind") == "mining":
        out.append(("info", tr("gz.f.mining")))
    if a.get("ven") == 0x10DE and a.get("nv_index") is None:
        out.append(("info", tr("gz.f.no_nvml")))
    elif a.get("ven") != 0x10DE:
        out.append(("info", tr("gz.f.sensors_other")))
    if not a.get("probed"):
        out.append(("info", tr("gz.f.no_probe")))
    return out


def report_text(d: dict, lives: dict = None) -> str:
    """Текстовий звіт про всі відеокарти (як «Save report» у CPU-Z / GPU-Z)."""
    lives = lives or {}
    ads = d.get("adapters") or []
    lines = [f"OptimaX {E.VERSION} — {tr('gz.title')}", ""]
    for i, a in enumerate(ads):
        lv = lives.get(i) or {}
        lines += [f"[{i + 1}/{len(ads)}] {a.get('name') or '?'}", "=" * 60]
        for gk, fn in GROUPS:
            lines.append(tr(gk))
            for k, v in fn(a, lv):
                lines.append(f"  {tr(k):<26}: {v if v not in (None, '') else '—'}")
        lines.append(tr("gz.g.notes"))
        for lvl, text in findings(a, lv):
            lines.append(f"  [{lvl}] {text}")
        lines.append("")
    if not ads:
        lines.append(tr("gz.none"))
    return "\n".join(lines)
