"""
OptimaX — визначення заліза без PowerShell: таблиці SMBIOS, реєстр, SetupAPI та запити до дисків.

Працює, навіть коли PowerShell заблокований антивірусом чи політикою, WMI зламаний або відповідає
надто довго (старі ПК із HDD, щойно після входу в систему). Кожна функція лише читає стан системи
й повертає порожній результат замість винятку. Розбір SMBIOS — чистий Python, його перевіряють тести.
"""
from __future__ import annotations

import ctypes
import re
import struct
import sys

IS_WIN = sys.platform == "win32"

# SMBIOS: тип модуля пам'яті (структура 17, поле Memory Type)
MEM_TYPES = {18: "DDR", 19: "DDR2", 20: "DDR2", 24: "DDR3", 26: "DDR4", 27: "LPDDR", 28: "LPDDR2", 29: "LPDDR3",
             30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}

# STORAGE_BUS_TYPE
BUS_TYPES = {1: "SCSI", 2: "ATAPI", 3: "ATA", 4: "1394", 6: "Fibre", 7: "USB", 8: "RAID", 9: "iSCSI", 10: "SAS",
             11: "SATA", 12: "SD", 13: "eMMC", 14: "Virtual", 15: "Virtual", 16: "Spaces", 17: "NVMe", 18: "SCM",
             19: "UFS"}

DISPLAY_CLASS = "{4d36e968-e325-11ce-bfc1-08002be10318}"
CLASS_ROOT = r"SYSTEM\CurrentControlSet\Control\Class"


# ───────────────────────── SMBIOS ─────────────────────────
def parse_smbios(raw: bytes):
    """RawSMBIOSData (як повертає GetSystemFirmwareTable 'RSMB') -> ([(тип, дескриптор, форматована частина, рядки)], версія)."""
    if len(raw) < 8:
        return [], (0, 0)
    ver = (raw[1], raw[2])
    length = struct.unpack_from("<I", raw, 4)[0]
    data = raw[8:8 + length]
    out, off = [], 0
    while off + 4 <= len(data):
        typ, ln = data[off], data[off + 1]
        handle = struct.unpack_from("<H", data, off + 2)[0]
        if ln < 4 or off + ln > len(data):
            break
        fmt = data[off:off + ln]
        p = off + ln
        end = data.find(b"\x00\x00", p)
        if end < 0:
            break
        strings = [s.decode("utf-8", "replace").strip() for s in data[p:end].split(b"\x00")] if end > p else []
        out.append((typ, handle, fmt, strings))
        if typ == 127:  # кінець таблиці
            break
        off = end + 2
    return out, ver


def _byte(fmt: bytes, o: int):
    return fmt[o] if len(fmt) > o else None


def _word(fmt: bytes, o: int):
    return struct.unpack_from("<H", fmt, o)[0] if len(fmt) >= o + 2 else None


def _dword(fmt: bytes, o: int):
    return struct.unpack_from("<I", fmt, o)[0] if len(fmt) >= o + 4 else None


OEM_JUNK = re.compile(r"(?i)(to be filled by o\.?e\.?m\.?|default string|system (manufacturer|product name|"
                      r"version|serial number)|not specified|not applicable|none|n/?a|o\.?e\.?m\.?|"
                      r"type1productconfigid|unknown|\.+|x+|0+|-+)?")


def clean_oem(s) -> str:
    """Порожні «заглушки» виробників плат («To be filled by O.E.M.», «Default string») -> ''."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return "" if OEM_JUNK.fullmatch(s) else s


def _str(strings: list, idx) -> str:
    if not idx or idx > len(strings):
        return ""
    return clean_oem(strings[idx - 1])


def smbios_info(raw: bytes) -> dict:
    """Пам'ять, корпус, виробник і модель, кількість процесорів із таблиць SMBIOS."""
    structs, _ver = parse_smbios(raw)
    arrays = {}
    for typ, handle, fmt, _s in structs:
        if typ == 16:  # Physical Memory Array: Use = 3 — системна пам'ять
            arrays[handle] = _byte(fmt, 0x05)
    mods = []
    info = {}
    sockets = 0
    for typ, handle, fmt, strings in structs:
        if typ == 17:
            arr = _word(fmt, 0x04)
            if arrays and arrays.get(arr, 3) != 3:
                continue  # флеш BIOS чи пам'ять відеокарти
            size = _word(fmt, 0x0C)
            if not size or size == 0xFFFF:
                continue  # порожній слот або невідомий розмір
            if size == 0x7FFF:
                ext = _dword(fmt, 0x1C)
                mb = (ext or 0) & 0x7FFFFFFF
            else:
                mb = (size & 0x7FFF) // 1024 if size & 0x8000 else size  # біт 15 — розмір у КБ
            if mb <= 0:
                continue
            speed = _word(fmt, 0x15) or 0
            if speed == 0xFFFF:
                speed = _dword(fmt, 0x54) or 0
            conf = _word(fmt, 0x20) or 0
            if conf == 0xFFFF:
                conf = _dword(fmt, 0x58) or 0
            mods.append(dict(mb=mb, type=_byte(fmt, 0x12) or 0, speed=speed, conf=conf,
                             vendor=_str(strings, _byte(fmt, 0x17)), part=_str(strings, _byte(fmt, 0x1A)).strip()))
        elif typ == 4:
            status = _byte(fmt, 0x18) or 0
            if _byte(fmt, 0x05) in (3, None) and status & 0x40:  # центральний процесор, сокет зайнятий
                sockets += 1
        elif typ == 3 and "chassis" not in info:
            ch = _byte(fmt, 0x05)
            if ch:
                info["chassis"] = [ch & 0x7F]
        elif typ == 1 and "vendor" not in info:
            info["vendor"] = _str(strings, _byte(fmt, 0x04))
            info["model"] = _str(strings, _byte(fmt, 0x05))
        elif typ == 2 and "board" not in info:
            info["board"] = (_str(strings, _byte(fmt, 0x04)), _str(strings, _byte(fmt, 0x05)))
    if mods:
        info["ram_modules"] = len(mods)
        info["ram_gb"] = sum(m["mb"] for m in mods) / 1024
        info["ram_type"] = next((MEM_TYPES[m["type"]] for m in mods if m["type"] in MEM_TYPES), "")
        info["ram_max_speed"] = max(m["speed"] for m in mods)
        info["ram_speed"] = max((m["conf"] or m["speed"]) for m in mods)
    if sockets:
        info["sockets"] = sockets
    # плати з Китаю (X99 тощо) часто не заповнюють виробника системи — тоді беремо виробника плати
    b = info.pop("board", None)
    if b and not info.get("vendor") and b[0]:
        info["vendor"], info["model"] = b[0], b[1] or info.get("model", "")
    elif b and not info.get("model") and b[1]:
        info["model"] = b[1]
    return info


def smbios_raw() -> bytes:
    if not IS_WIN:
        return b""
    k32 = ctypes.windll.kernel32
    k32.GetSystemFirmwareTable.restype = ctypes.c_uint
    k32.GetSystemFirmwareTable.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    sig = 0x52534D42  # 'RSMB'
    n = k32.GetSystemFirmwareTable(sig, 0, None, 0)
    if not n:
        return b""
    buf = ctypes.create_string_buffer(n)
    got = k32.GetSystemFirmwareTable(sig, 0, buf, n)
    return buf.raw[:got] if got else b""


# ───────────────────────── процесор, пам'ять, Windows ─────────────────────────
def _reg(path: str, name: str, hive=None):
    import winreg
    try:
        with winreg.OpenKey(hive or winreg.HKEY_LOCAL_MACHINE, path, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def cpu_counts() -> dict:
    """Ядра, потоки й процесори (сокети) з усіх груп процесорів."""
    k32 = ctypes.windll.kernel32
    size = ctypes.c_ulong(0)
    k32.GetLogicalProcessorInformationEx(0xFFFF, None, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if not k32.GetLogicalProcessorInformationEx(0xFFFF, buf, ctypes.byref(size)):
        return {}
    raw, off, cores, packages = buf.raw, 0, 0, 0
    while off < size.value:
        rel = int.from_bytes(raw[off:off + 4], "little")
        sz = int.from_bytes(raw[off + 4:off + 8], "little")
        if not sz:
            break
        cores += rel == 0
        packages += rel == 3
        off += sz
    k32.GetActiveProcessorCount.restype = ctypes.c_ulong
    threads = k32.GetActiveProcessorCount(0xFFFF)
    return {k: v for k, v in (("cores", cores), ("threads", threads), ("sockets", packages)) if v}


def cpu_name() -> tuple:
    """-> (назва, базова частота МГц) з реєстру."""
    p = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
    name = re.sub(r"\s+", " ", str(_reg(p, "ProcessorNameString") or "")).strip()
    mhz = _reg(p, "~MHz") or 0
    mhz = int(mhz) if isinstance(mhz, int) else 0
    if mhz % 100 <= 15 or mhz % 100 >= 85:  # виміряна частота: 2394 -> 2400
        mhz = round(mhz / 100) * 100
    return name, mhz


def installed_ram_gb() -> float:
    kb = ctypes.c_ulonglong(0)
    if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kb)):
        return kb.value / 2**20
    return 0.0


def os_name(build: int) -> str:
    """Назва Windows з реєстру. ProductName на Windows 11 досі каже «Windows 10» — виправляємо за номером збірки."""
    name = str(_reg(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName") or "Windows")
    if build >= 22000:
        name = name.replace("Windows 10", "Windows 11")
    return clean_os(name)


def clean_os(name: str) -> str:
    return re.sub(r"^(Microsoft|Майкрософт)\s+", "", str(name or "").strip()) or "Windows"


# ───────────────────────── відеокарти (SetupAPI + реєстр драйвера) ─────────────────────────
class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]


class _SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("ClassGuid", _GUID), ("DevInst", ctypes.c_ulong),
                ("Reserved", ctypes.c_size_t)]


def _guid(s: str) -> _GUID:
    h = s.strip("{}").replace("-", "")
    g = _GUID()
    g.Data1, g.Data2, g.Data3 = int(h[0:8], 16), int(h[8:12], 16), int(h[12:16], 16)
    for i in range(8):
        g.Data4[i] = int(h[16 + i * 2:18 + i * 2], 16)
    return g


def present_devices(class_guid: str) -> list:
    """Присутні пристрої класу -> [{name, driver, instance}] (driver — підключ у Control\\Class)."""
    sa = ctypes.windll.setupapi
    sa.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    sa.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(_GUID), ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_ulong]
    sa.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_SP_DEVINFO_DATA)]
    sa.SetupDiGetDeviceRegistryPropertyW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_SP_DEVINFO_DATA), ctypes.c_ulong,
                                                     ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p, ctypes.c_ulong,
                                                     ctypes.POINTER(ctypes.c_ulong)]
    sa.SetupDiGetDeviceInstanceIdW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_SP_DEVINFO_DATA), ctypes.c_wchar_p,
                                               ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    sa.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    g = _guid(class_guid)
    h = sa.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x2)  # DIGCF_PRESENT
    if not h or h == ctypes.c_void_p(-1).value:
        return []
    out = []
    try:
        i = 0
        while i < 64:
            dd = _SP_DEVINFO_DATA()
            dd.cbSize = ctypes.sizeof(dd)
            if not sa.SetupDiEnumDeviceInfo(h, i, ctypes.byref(dd)):
                break
            i += 1

            def prop(code):
                buf = ctypes.create_unicode_buffer(512)
                if sa.SetupDiGetDeviceRegistryPropertyW(h, ctypes.byref(dd), code, None, buf,
                                                        ctypes.sizeof(buf), None):
                    return buf.value.strip()
                return ""
            inst = ctypes.create_unicode_buffer(512)
            sa.SetupDiGetDeviceInstanceIdW(h, ctypes.byref(dd), inst, 512, None)
            out.append(dict(name=prop(12) or prop(0), driver=prop(9), instance=inst.value))  # FRIENDLYNAME/DEVICEDESC/DRIVER
    finally:
        sa.SetupDiDestroyDeviceInfoList(h)
    return out


def _mem_value(v) -> int:
    if isinstance(v, (bytes, bytearray)):
        v = int.from_bytes(bytes(v)[:8], "little")
    try:
        return abs(int(v))
    except (TypeError, ValueError):
        return 0


def driver_info(driver_key: str) -> dict:
    """Відеопам'ять, дата й версія драйвера з Control\\Class\\{…}\\NNNN."""
    if not driver_key:
        return {}
    key = CLASS_ROOT + "\\" + driver_key
    mem = 0
    for vn in ("HardwareInformation.qwMemorySize", "HardwareInformation.MemorySize"):
        mem = _mem_value(_reg(key, vn))
        if mem:
            break
    date = str(_reg(key, "DriverDate") or "")
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", date)
    return dict(desc=str(_reg(key, "DriverDesc") or ""), vram=mem / 2**30,
                date=f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else "",
                version=str(_reg(key, "DriverVersion") or ""))


def driver_key_for(pnp_id: str) -> str:
    """PNPDeviceID (з WMI) -> підключ драйвера в Control\\Class."""
    if not pnp_id:
        return ""
    return str(_reg(r"SYSTEM\CurrentControlSet\Enum" + "\\" + pnp_id, "Driver") or "")


def gpus() -> list:
    """-> [{name, vram, date, instance, driver}] для присутніх відеоадаптерів."""
    res = []
    for d in present_devices(DISPLAY_CLASS):
        di = driver_info(d["driver"])
        name = d["name"] or di.get("desc", "")
        if name:
            res.append(dict(name=name, vram=di.get("vram", 0.0), date=di.get("date", ""), instance=d["instance"],
                            driver=d["driver"]))
    return res


# ───────────────────────── диски (IOCTL) ─────────────────────────
GENERIC_NONE, SHARE_RW, OPEN_EXISTING = 0, 3, 3
IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400
IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x560000
IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x700A0


def _k32():
    k = ctypes.windll.kernel32
    k.CreateFileW.restype = ctypes.c_void_p
    k.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                              ctypes.c_ulong, ctypes.c_void_p]
    k.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                                  ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    return k


def _open(path: str):
    k = _k32()
    h = k.CreateFileW(path, GENERIC_NONE, SHARE_RW, None, OPEN_EXISTING, 0, None)
    if not h or h == ctypes.c_void_p(-1).value:
        return None
    return h


def _ioctl(h, code: int, inp: bytes = b"", out_size: int = 1024) -> bytes:
    k = _k32()
    ib = ctypes.create_string_buffer(inp, len(inp)) if inp else None
    ob = ctypes.create_string_buffer(out_size)
    ret = ctypes.c_ulong(0)
    if not k.DeviceIoControl(h, code, ib, len(inp), ob, out_size, ctypes.byref(ret), None):
        return b""
    return ob.raw[:ret.value]


def parse_device_descriptor(b: bytes) -> dict:
    """STORAGE_DEVICE_DESCRIPTOR -> {bus, vendor, product}."""
    if len(b) < 32:
        return {}

    def s(off):
        o = struct.unpack_from("<I", b, off)[0]
        if not o or o >= len(b):
            return ""
        end = b.find(b"\x00", o)
        return b[o:end if end >= 0 else len(b)].decode("ascii", "replace").strip()
    bus = struct.unpack_from("<I", b, 28)[0]
    return dict(bus=BUS_TYPES.get(bus, ""), vendor=s(12), product=s(16))


def disk_name(vendor: str, product: str) -> str:
    """Виробник у дескрипторі часто порожній, «ATA» чи «NVMe» або вже є в назві моделі."""
    vendor, product = (vendor or "").strip(), (product or "").strip()
    if not vendor or vendor.upper() in ("ATA", "NVME", "SCSI", "USB") or vendor.lower() in product.lower():
        return product or vendor
    return f"{vendor} {product}".strip()


def disk_props(num: int) -> dict:
    """Фізичний диск N -> {bus, name, seek (True — HDD), size_gb}."""
    h = _open(rf"\\.\PhysicalDrive{num}")
    if h is None:
        return {}
    try:
        res = parse_device_descriptor(_ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, struct.pack("<II4x", 0, 0)))
        sp = _ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, struct.pack("<II4x", 7, 0), 64)  # StorageDeviceSeekPenaltyProperty
        if len(sp) >= 9:
            res["seek"] = bool(sp[8])
        geo = _ioctl(h, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, b"", 256)
        if len(geo) >= 32:
            res["size_gb"] = round(struct.unpack_from("<q", geo, 24)[0] / 1e9)
        res["name"] = disk_name(res.pop("vendor", ""), res.pop("product", ""))
        return res
    finally:
        _k32().CloseHandle(h)


def volume_disk(letter: str):
    """Буква диска -> номер фізичного диска (перший екстент)."""
    h = _open(rf"\\.\{letter[0]}:")
    if h is None:
        return None
    try:
        b = _ioctl(h, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, b"", 256)
        if len(b) >= 12 and struct.unpack_from("<I", b, 0)[0] >= 1:
            return struct.unpack_from("<I", b, 8)[0]
        return None
    finally:
        _k32().CloseHandle(h)


def media_of(p: dict) -> str:
    bus = p.get("bus", "")
    if bus == "NVMe":
        return "NVMe"
    if bus in ("eMMC", "UFS", "SD"):
        return bus
    if "seek" in p:
        return "HDD" if p["seek"] else "SSD"
    return "?"


def disks() -> list:
    """-> [{id, name, media, bus, size_gb, letters}] для дисків 0…15."""
    import string
    letters = {}
    drives = ctypes.windll.kernel32.GetLogicalDrives()
    for i, ch in enumerate(string.ascii_uppercase):
        if drives & (1 << i) and ctypes.windll.kernel32.GetDriveTypeW(f"{ch}:\\") == 3:  # DRIVE_FIXED
            n = volume_disk(ch)
            if n is not None:
                letters.setdefault(n, []).append(ch)
    out = []
    for n in range(16):
        p = disk_props(n)
        if not p:
            continue
        out.append(dict(id=str(n), name=p.get("name", ""), media=media_of(p), bus=p.get("bus", ""), health="",
                        size_gb=p.get("size_gb", 0), wear=None, temp=None, letters=sorted(letters.get(n, []))))
    return out


# ───────────────────────── мережа ─────────────────────────
def net_kinds() -> dict:
    """{wifi, ethernet} за GetAdaptersAddresses (без віртуальних адаптерів)."""
    ip = ctypes.windll.iphlpapi
    size = ctypes.c_ulong(16384)
    for _ in range(3):
        buf = ctypes.create_string_buffer(size.value)
        r = ip.GetAdaptersAddresses(0, 0x0001 | 0x0002 | 0x0004 | 0x0008, None, buf, ctypes.byref(size))
        if r == 0:
            break
        if r != 111:  # ERROR_BUFFER_OVERFLOW
            return {}
    else:
        return {}
    virt = re.compile(r"virtual|vpn|tap|tun|hyper-v|vmware|virtualbox|loopback|bluetooth|wan miniport|wintun|"
                      r"zerotier|tailscale|wireguard|radmin|hamachi", re.I)
    wifi = eth = False
    addr = ctypes.addressof(buf)
    while addr:
        nxt = ctypes.c_void_p.from_address(addr + 8).value
        desc_p = ctypes.c_void_p.from_address(addr + 64).value
        iftype = ctypes.c_ulong.from_address(addr + 100).value
        desc = ctypes.wstring_at(desc_p) if desc_p else ""
        if not virt.search(desc):
            wifi |= iftype == 71
            eth |= iftype == 6
        addr = nxt
    return dict(wifi=wifi, ethernet=eth)


# ───────────────────────── усе разом ─────────────────────────
def collect() -> dict:
    """Усе, що вдалося визначити без PowerShell. Відсутні ключі — не вдалося."""
    if not IS_WIN:
        return {}
    res, errors = {}, []

    def step(name, fn):
        try:
            v = fn()
            if v:
                res.update(v) if isinstance(v, dict) else res.__setitem__(name, v)
        except Exception as e:  # noqa: BLE001 — кожен крок окремо, решта мають спрацювати
            errors.append(f"{name}: {type(e).__name__}: {e}")
    step("smbios", lambda: smbios_info(smbios_raw()))
    step("cpu", lambda: dict(zip(("cpu", "mhz"), cpu_name())))
    step("counts", cpu_counts)
    step("installed_gb", installed_ram_gb)
    step("gpus", gpus)
    step("disks", lambda: {"disks": disks()})
    step("net", net_kinds)
    try:
        b = sys.getwindowsversion().build
        res["build"] = b
        res["os"] = os_name(b)
    except Exception as e:  # noqa: BLE001
        errors.append(f"os: {e}")
    if errors:
        res["errors"] = errors
    return res
