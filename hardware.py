"""
OptimaX — залізо: визначення компонентів, аналіз системи, перевірка збірки, MSI Mode,
батарея, пам'ять, заміри «до/після». Усе тут лише читає стан системи.
"""
from __future__ import annotations

import ctypes
import os
import re
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import engine as E
import hwnative as HN
from i18n import tr

LAPTOP_CHASSIS = {8, 9, 10, 14, 30, 31, 32}
VIRTUAL_GPU = r"Parsec|Virtual|Remote|Indirect|Microsoft Basic|RDP|SpaceDesk|Moonlight|Sunshine|AnyDesk|TeamViewer|VNC|Citrix|Meta"


# ───────────────────────── ctypes-запити ─────────────────────────
def _efficiency_classes():
    """-> (кількість P-ядер, кількість E-ядер) через GetLogicalProcessorInformationEx."""
    k32 = ctypes.windll.kernel32
    size = ctypes.c_ulong(0)
    k32.GetLogicalProcessorInformationEx(0, None, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if not k32.GetLogicalProcessorInformationEx(0, buf, ctypes.byref(size)):
        return 0, 0
    raw, off, classes = buf.raw, 0, []
    while off < size.value:
        rel = int.from_bytes(raw[off:off + 4], "little")
        sz = int.from_bytes(raw[off + 4:off + 8], "little")
        if rel == 0 and sz:  # RelationProcessorCore: EfficiencyClass лежить у байті 9
            classes.append(raw[off + 9])
        if not sz:
            break
        off += sz
    if not classes or len(set(classes)) < 2:
        return len(classes), 0
    top = max(classes)
    return sum(c == top for c in classes), sum(c != top for c in classes)


def _power_caps():
    """-> (кришка ноутбука є, Modern Standby) через CallNtPowerInformation(SystemPowerCapabilities)."""
    buf = ctypes.create_string_buffer(256)
    if ctypes.windll.powrprof.CallNtPowerInformation(4, None, 0, buf, 256) != 0:
        return False, False
    raw = buf.raw
    return bool(raw[2]), bool(raw[20])


def _battery() -> bool:
    class SPS(ctypes.Structure):
        _fields_ = [("AC", ctypes.c_ubyte), ("Flag", ctypes.c_ubyte), ("Pct", ctypes.c_ubyte),
                    ("Saver", ctypes.c_ubyte), ("Life", ctypes.c_ulong), ("Full", ctypes.c_ulong)]
    s = SPS()
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
        return s.Flag not in (128, 255)
    return False


def cpu_topology() -> dict:
    """Маски логічних процесорів (група 0): P-ядра, кристал із 3D V-Cache, перший NUMA-вузол."""
    k32 = ctypes.windll.kernel32
    size = ctypes.c_ulong(0)
    k32.GetLogicalProcessorInformationEx(0xFFFF, None, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if not k32.GetLogicalProcessorInformationEx(0xFFFF, buf, ctypes.byref(size)):
        return {}
    raw, off = buf.raw, 0
    u = lambda a, b: int.from_bytes(raw[off + a:off + b], "little")  # noqa: E731
    cores, l3, numa = [], [], []
    while off < size.value:
        rel, sz = u(0, 4), u(4, 8)
        if not sz:
            break
        if rel == 0 and u(40, 42) == 0:  # RelationProcessorCore
            cores.append((raw[off + 9], u(32, 40)))
        elif rel == 2 and raw[off + 8] == 3 and u(48, 50) == 0:  # RelationCache, L3
            l3.append((u(12, 16), u(40, 48)))
        elif rel == 1 and u(40, 42) == 0:  # RelationNumaNode
            numa.append(u(32, 40))
        off += sz
    res = {}
    if cores and len({e for e, _ in cores}) > 1:
        top = max(e for e, _ in cores)
        res["p_mask"] = sum(m for e, m in cores if e == top)
    if len(l3) >= 2 and len({c for c, _ in l3}) > 1:
        res["vcache_mask"] = max(l3)[1]
    if len(numa) >= 2:
        res["numa_mask"], res["numa_nodes"] = numa[0], len(numa)
    return res


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("DeviceName", ctypes.c_wchar * 32), ("DeviceString", ctypes.c_wchar * 128),
                ("StateFlags", ctypes.c_ulong), ("DeviceID", ctypes.c_wchar * 128), ("DeviceKey", ctypes.c_wchar * 128)]


def display_adapter() -> str:
    """Назва відеоадаптера, до якого під'єднано основний монітор."""
    u = ctypes.windll.user32
    i = 0
    while i < 16:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(dd)
        if not u.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        if dd.StateFlags & 0x4:  # DISPLAY_DEVICE_PRIMARY_DEVICE
            return dd.DeviceString
        i += 1
    return ""


class DEVMODEW(ctypes.Structure):
    _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", ctypes.c_ushort),
                ("dmDriverVersion", ctypes.c_ushort), ("dmSize", ctypes.c_ushort), ("dmDriverExtra", ctypes.c_ushort),
                ("dmFields", ctypes.c_ulong), ("dmUnion", ctypes.c_byte * 16), ("dmColor", ctypes.c_short),
                ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
                ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_wchar * 32), ("dmLogPixels", ctypes.c_ushort),
                ("dmBitsPerPel", ctypes.c_ulong), ("dmPelsWidth", ctypes.c_ulong), ("dmPelsHeight", ctypes.c_ulong),
                ("dmDisplayFlags", ctypes.c_ulong), ("dmDisplayFrequency", ctypes.c_ulong),
                ("dmICMMethod", ctypes.c_ulong), ("dmICMIntent", ctypes.c_ulong), ("dmMediaType", ctypes.c_ulong),
                ("dmDitherType", ctypes.c_ulong), ("dmReserved1", ctypes.c_ulong), ("dmReserved2", ctypes.c_ulong),
                ("dmPanningWidth", ctypes.c_ulong), ("dmPanningHeight", ctypes.c_ulong)]


def refresh_rates():
    """-> (поточна частота, максимальна для поточної роздільності) основного монітора."""
    u = ctypes.windll.user32
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(dm)
    if not u.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
        return 0, 0
    cur, w, h = dm.dmDisplayFrequency, dm.dmPelsWidth, dm.dmPelsHeight
    best, i = cur, 0
    m = DEVMODEW()
    m.dmSize = ctypes.sizeof(m)
    while u.EnumDisplaySettingsW(None, i, ctypes.byref(m)) and i < 2000:
        if m.dmPelsWidth == w and m.dmPelsHeight == h:
            best = max(best, m.dmDisplayFrequency)
        i += 1
    return cur, best


# ───────────────────────── визначення заліза ─────────────────────────
# Запити розбито на незалежні частини, що виконуються одночасно: служба сховища (Get-PhysicalDisk) на частині ПК
# відповідає хвилинами — раніше через неї спливав тайм-аут усього скрипту, і програма показувала «Не визначено» замість
# процесора й пам'яті. Помилки окремих команд не мають ламати JSON, тому вони приглушені.
PS_QUIET = "$ErrorActionPreference='SilentlyContinue';$WarningPreference='SilentlyContinue';"

CORE_SCRIPT = PS_QUIET + r"""
$c=@(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed)
$m=@(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed,SMBIOSMemoryType)
$o=Get-CimInstance Win32_OperatingSystem | Select-Object Caption,BuildNumber
$g=@(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,PNPDeviceID,@{n='DriverDate';e={if($_.DriverDate){$_.DriverDate.ToString('yyyy-MM-dd')}}},DriverVersion)
$e=@(Get-CimInstance Win32_SystemEnclosure | ForEach-Object { $_.ChassisTypes })
$vbs=$null
try { $dg=Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard -ErrorAction Stop; $vbs=[int]$dg.VirtualizationBasedSecurityStatus } catch {}
$cs=Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model
$na=@(Get-NetAdapter -Physical | Select-Object InterfaceDescription,NdisPhysicalMedium)
@{cpu=$c;ram=$m;os=$o;gpu=$g;chassis=$e;vbs=$vbs;cs=$cs;net=$na} | ConvertTo-Json -Depth 4 -Compress
"""

STORAGE_SCRIPT = PS_QUIET + r"""
$pd=@(); foreach ($d in @(Get-PhysicalDisk)) {
  $rc=$null; try { $rc = $d | Get-StorageReliabilityCounter -ErrorAction Stop } catch {}
  $pd += @{id=[string]$d.DeviceId; name=$d.FriendlyName; media=[string]$d.MediaType; bus=[string]$d.BusType;
           health=[string]$d.HealthStatus; size=[double]$d.Size; wear=$(if($rc){$rc.Wear}); temp=$(if($rc){$rc.Temperature})}
}
$pt=@(Get-Partition | Where-Object { $_.DriveLetter } | ForEach-Object { @{l=[string]$_.DriveLetter; d=[string]$_.DiskNumber} })
@{disks=$pd;parts=$pt} | ConvertTo-Json -Depth 4 -Compress
"""

GPU_PCI_SCRIPT = PS_QUIET + r"""
$r=@(); foreach ($d in Get-PnpDevice -PresentOnly -Class Display -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'PCI\*' }) {
  $h=@{}; foreach ($x in (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName DEVPKEY_PciDevice_CurrentLinkWidth,DEVPKEY_PciDevice_MaxLinkWidth,DEVPKEY_PciDevice_CurrentLinkSpeed,DEVPKEY_PciDevice_MaxLinkSpeed -ErrorAction SilentlyContinue)) { $h[$x.KeyName]=$x.Data }
  $bar=0
  try { $e=Get-CimInstance Win32_PnPEntity -Filter ("DeviceID='" + ($d.InstanceId -replace '\\','\\') + "'") -ErrorAction Stop
        foreach ($m in ($e | Get-CimAssociatedInstance -ResultClassName Win32_DeviceMemoryAddress -ErrorAction Stop)) {
          $z=[double]$m.EndingAddress - [double]$m.StartingAddress + 1; if ($z -gt $bar) { $bar=$z } } } catch {}
  $r += @{name=$d.FriendlyName; cw=$h['DEVPKEY_PciDevice_CurrentLinkWidth']; mw=$h['DEVPKEY_PciDevice_MaxLinkWidth'];
          cs=$h['DEVPKEY_PciDevice_CurrentLinkSpeed']; ms=$h['DEVPKEY_PciDevice_MaxLinkSpeed']; bar=$bar}
}; $r | ConvertTo-Json -Compress
"""

DEMO_HW = {
    "gaming": dict(cpu="Intel(R) Core(TM) i7-13700K", cores=16, threads=24, mhz=3400, p_cores=8, e_cores=8,
                   gpus=[("NVIDIA GeForce RTX 4070", 12.0, "2024-02-10")], ram=[(16, 3200, 2133, 26)] * 2,
                   chassis=[3], disk=("SSD", "NVMe", "Samsung SSD 980"), battery=False, lid=False, aoac=False,
                   refresh=(60, 165), vbs=2, os=("Windows 11 Pro", "22631"), vendor="Micro-Star International Co., Ltd.",
                   wifi=True, ethernet=True, display_gpu="NVIDIA GeForce RTX 4070",
                   disks=[("0", "Samsung SSD 980 1TB", "NVMe", "NVMe", "Healthy", 1000, 12, 41, ["C"]),
                          ("1", "ST2000DM008-2FR102", "HDD", "SATA", "Healthy", 2000, None, 36, ["D"])],
                   pci=[("NVIDIA GeForce RTX 4070", 16, 16, 1, 4, 256)], topo={"p_mask": 0xFFFF},
                   thermal=dict(zone=41, passive=100, perf=100, gpu=38)),
    "laptop": dict(cpu="13th Gen Intel(R) Core(TM) i5-13500H", cores=12, threads=16, mhz=2600, p_cores=4, e_cores=8,
                   gpus=[("Intel(R) Iris(R) Xe Graphics", 0.1, "2025-03-01"),
                         ("NVIDIA GeForce RTX 4050 Laptop GPU", 6.0, "2025-03-01")],
                   ram=[(16, 5200, 5200, 34)], chassis=[10], disk=("SSD", "NVMe", "WD PC SN740"),
                   battery=True, lid=True, aoac=True, refresh=(144, 144), vbs=2, os=("Windows 11 Home", "22631"),
                   vendor="ASUSTeK COMPUTER INC.", wifi=True, ethernet=False, display_gpu="Intel(R) Iris(R) Xe Graphics",
                   disks=[("0", "WD PC SN740 512GB", "NVMe", "NVMe", "Healthy", 512, 3, 45, ["C"])],
                   pci=[("NVIDIA GeForce RTX 4050 Laptop GPU", 8, 8, 1, 4, 6144)], topo={"p_mask": 0xFF},
                   thermal=dict(zone=64, passive=100, perf=100, gpu=None)),
    "old": dict(cpu="Intel(R) Celeron(R) CPU N3060 @ 1.60GHz", cores=2, threads=2, mhz=1600, p_cores=2, e_cores=0,
                gpus=[("Intel(R) HD Graphics 400", 0.0, "2019-05-12")], ram=[(4, 1600, 1600, 24)], chassis=[10],
                disk=("HDD", "SATA", "WDC WD5000LPCX"), battery=True, lid=True, aoac=False, refresh=(60, 60),
                vbs=0, os=("Windows 10 Home", "19045"), vendor="HP", wifi=True, ethernet=True,
                display_gpu="Intel(R) HD Graphics 400",
                disks=[("0", "WDC WD5000LPCX-24C6HT0", "HDD", "SATA", "Healthy", 500, None, 47, ["C"])], pci=[], topo={},
                thermal=dict(zone=78, passive=100, perf=100, gpu=None)),
    "x3d": dict(cpu="AMD Ryzen 9 7950X3D 16-Core Processor", cores=16, threads=32, mhz=4200, p_cores=16, e_cores=0,
                gpus=[("AMD Radeon RX 7900 XTX", 24.0, "2025-01-20"), ("AMD Radeon(TM) Graphics", 0.5, "2025-01-20")],
                ram=[(16, 6000, 6000, 34)] * 2, chassis=[3], disk=("SSD", "NVMe", "Samsung SSD 990 PRO"),
                battery=False, lid=False, aoac=False, refresh=(240, 240), vbs=0, os=("Windows 11 Pro", "26100"),
                vendor="ASUSTeK COMPUTER INC.", wifi=False, ethernet=True, display_gpu="AMD Radeon(TM) Graphics",
                disks=[("0", "Samsung SSD 990 PRO 2TB", "NVMe", "NVMe", "Healthy", 2000, 2, 38, ["C"])],
                pci=[("AMD Radeon RX 7900 XTX", 16, 16, 4, 4, 24576)], topo={"vcache_mask": 0xFFFF},
                thermal=dict(zone=45, passive=100, perf=100, gpu=None)),
    "xeon": dict(cpu="Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz", cores=14, threads=28, mhz=2400, p_cores=14,
                 e_cores=0, gpus=[("NVIDIA GeForce GTX 1660 SUPER", 6.0, "2023-06-01")],
                 ram=[(16, 2400, 2133, 26)] * 1, chassis=[3], disk=("SSD", "SATA", "Kingston A400"), battery=False,
                 lid=False, aoac=False, refresh=(75, 75), vbs=0, os=("Windows 10 Pro", "19045"), vendor="HUANANZHI",
                 wifi=False, ethernet=True, display_gpu="NVIDIA GeForce GTX 1660 SUPER",
                 disks=[("0", "KINGSTON SA400S37240G", "SSD", "SATA", "Healthy", 240, 61, 39, ["C"])],
                 pci=[("NVIDIA GeForce GTX 1660 SUPER", 4, 16, 3, 3, 256)], topo={},
                 thermal=dict(zone=52, passive=100, perf=100, gpu=None)),
    # майнінгова P106-100 без відеовиходів: монітор у материнській платі, картинку виводить HD 4000
    "mining": dict(cpu="Intel(R) Core(TM) i5-3570 CPU @ 3.40GHz", cores=4, threads=4, mhz=3400, p_cores=4, e_cores=0,
                   gpus=[("Intel(R) HD Graphics 4000", 2.0, "2015-11-10"), ("NVIDIA P106-100", 6.0, "2023-04-12")],
                   ram=[(8, 1600, 1600, 24)] * 2, chassis=[3], disk=("SSD", "SATA", "Kingston A400"), battery=False,
                   lid=False, aoac=False, refresh=(60, 60), vbs=0, os=("Windows 10 Pro", "19045"), vendor="ASRock",
                   wifi=False, ethernet=True, display_gpu="Intel(R) HD Graphics 4000",
                   disks=[("0", "KINGSTON SA400S37480G", "SSD", "SATA", "Healthy", 480, 18, 35, ["C"])],
                   pci=[("NVIDIA P106-100", 1, 16, 1, 3, 256)], topo={},
                   thermal=dict(zone=48, passive=100, perf=100, gpu=None)),
}


def _gpu_vendor(name: str) -> str:
    n = name.lower()
    if any(w in n for w in ("nvidia", "geforce", "rtx", "gtx", "quadro")):
        return "nvidia"
    if any(w in n for w in ("amd", "radeon")):
        return "amd"
    if "intel" in n:
        return "intel"
    return "other"


def _finish(hw: dict) -> dict:
    """Похідні ознаки та рекомендований профіль."""
    cpu = hw["cpu"]
    hw["cpu_vendor"] = "intel" if "intel" in cpu.lower() else "amd" if ("amd" in cpu.lower() or "ryzen" in cpu.lower()) \
        else "other"
    hw["hybrid"] = hw.get("e_cores", 0) > 0
    hw["x3d"] = "X3D" in cpu
    hw["x3d_dual"] = bool(re.search(r"\b(79[05]0|99[05]0)X3D", cpu))
    hw["xeon"] = "xeon" in cpu.lower()
    vendors = [_gpu_vendor(n) for n, _, _ in hw["gpus"]]
    hw["nvidia"] = "nvidia" in vendors
    hw["amd_gpu"] = any(v == "amd" and vr >= 1 for v, (_, vr, _) in zip(vendors, hw["gpus"]))
    hw["dgpu"] = any(v in ("nvidia", "amd", "intel") and not is_integrated(n, vr) and (vr >= 1 or ARC_DGPU.search(n))
                     for v, (n, vr, _) in zip(vendors, hw["gpus"]))
    hw["multi_gpu"] = len(hw["gpus"]) >= 2
    hw["laptop"] = bool(hw.get("battery") or hw.get("lid") or set(hw.get("chassis", [])) & LAPTOP_CHASSIS)
    hw["ssd"] = hw.get("disk_type") in ("SSD", "NVMe") or hw.get("disk_bus") == "NVMe"
    hw["hdd"] = hw.get("disk_type") == "HDD"
    weak_cpu = bool(re.search(r"Celeron|Pentium|Atom|Athlon|A[46]-\d|E[12]-\d", cpu, re.I)) or hw["cores"] <= 2
    hw["old"] = hw["ram_gb"] <= 4.5 or weak_cpu or (hw["hdd"] and hw["ram_gb"] <= 8 and hw["cores"] <= 4)
    if hw["old"]:
        hw["profile"] = "O"
    elif hw["xeon"]:
        hw["profile"] = "X"
    elif hw["laptop"]:
        hw["profile"] = "T"
    else:
        hw["profile"] = "M"
    hw["device"] = {"O": "old", "X": "xeon", "T": "laptop", "M": "gaming"}[hw["profile"]]
    hw["big_ram"] = hw["ram_gb"] >= 30
    hw["cores_mode"] = ("vcache" if hw.get("vcache_mask") else "numa" if hw.get("numa_mask") else
                        "pcores" if hw.get("p_mask") else None)
    hw.setdefault("disks", [])
    hw.setdefault("gpu_pci", [])
    hw.setdefault("thermal", {})
    # майнінгові карти: за PCI-ідентифікатором (detect_hw) або за назвою, якщо стоїть звичайний драйвер
    mining = [m for m in hw.get("mining") or [] if isinstance(m, dict) and m.get("model")]
    for n, _, _ in hw["gpus"]:
        model = mining_model("", n)
        if model and not any(m["name"] == n for m in mining):
            mining.append(dict(name=n, model=model))
    hw["mining"] = mining
    hw["mining_gpu"] = mining[0]["model"] if mining else ""  # картинку виводить інша відеокарта — виходів у карти немає
    return hw


def _from_demo(name: str) -> dict:
    d = DEMO_HW.get(name, DEMO_HW["gaming"])
    total = sum(m[0] for m in d["ram"])
    hw = dict(cpu=d["cpu"], cores=d["cores"], threads=d["threads"], mhz=d["mhz"], p_cores=d["p_cores"],
              e_cores=d["e_cores"], gpus=d["gpus"], ram_gb=float(total), ram_modules=len(d["ram"]),
              ram_max_speed=max(m[1] for m in d["ram"]), ram_speed=max(m[2] for m in d["ram"]),
              ram_type=HN.MEM_TYPES.get(d["ram"][0][3], ""), chassis=d["chassis"], disk_type=d["disk"][0],
              disk_bus=d["disk"][1], disk_name=d["disk"][2], battery=d["battery"], lid=d["lid"],
              modern_standby=d["aoac"], refresh=d["refresh"], vbs_running=d["vbs"] == 2, os=d["os"][0],
              build=int(d["os"][1]), vendor=d["vendor"], wifi=d["wifi"], ethernet=d["ethernet"],
              display_gpu=d["display_gpu"], thermal=dict(d["thermal"]), **d["topo"])
    hw["disks"] = [dict(id=x[0], name=x[1], media=x[2], bus=x[3], health=x[4], size_gb=x[5], wear=x[6], temp=x[7],
                        letters=x[8]) for x in d["disks"]]
    hw["gpu_pci"] = [dict(name=x[0], cw=x[1], mw=x[2], cs=x[3], ms=x[4], bar_mb=x[5]) for x in d["pci"]]
    return _finish(hw)


MEDIA_NAMES = {"3": "HDD", "4": "SSD", "5": "SCM", "HDD": "HDD", "SSD": "SSD", "SCM": "SCM"}
HEALTH_NAMES = {"0": "Healthy", "1": "Warning", "2": "Unhealthy", "5": "", "Unknown": ""}


def _bus_name(v) -> str:
    v = str(v if v is not None else "").strip()
    if v.isdigit():
        return HN.BUS_TYPES.get(int(v), "")
    return "" if v.lower() in ("unknown", "0") else v


def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _clean_name(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def ram_speed_fix(speed: int, conf: int) -> int:
    """Старі BIOS (SMBIOS до 3.1) пишуть у «налаштовану швидкість» реальну частоту, тобто половину МТ/с:
    DDR4-3200 показувалася як 1600 МГц, а перевірка збірки радила вмикати XMP, який уже ввімкнено."""
    if speed and conf and abs(conf * 2 - speed) <= speed * 0.03:
        return speed
    return conf or speed


def merge_disks(ps_disks: list, parts: list, native: list) -> list:
    """Диски з PowerShell (назва, стан, знос, температура) + запити до драйвера (шина, SSD чи HDD, букви).
    Кожне джерело може бути порожнім."""
    out = {}
    for d in native or []:
        if isinstance(d, dict) and d.get("id") not in (None, ""):
            out[str(d["id"])] = dict(d, letters=list(d.get("letters") or []))
    for d in ps_disks or []:
        if not isinstance(d, dict) or d.get("id") in (None, ""):
            continue
        i = str(d["id"])
        cur = out.setdefault(i, dict(id=i, name="", media="?", bus="", health="", size_gb=0, wear=None, temp=None,
                                     letters=[]))
        name = _clean_name(d.get("name"))
        if name:
            cur["name"] = name
        bus = _bus_name(d.get("bus"))
        if bus and not (bus in ("RAID", "Spaces", "SCSI") and cur.get("bus")):  # RAID/Spaces приховують справжню шину
            cur["bus"] = bus
        media = MEDIA_NAMES.get(str(d.get("media") or "").strip(), "")
        if media:
            cur["media"] = media
        health = str(d.get("health") if d.get("health") is not None else "").strip()
        cur["health"] = HEALTH_NAMES.get(health, health)
        if d.get("size"):
            cur["size_gb"] = round(float(d["size"]) / 1e9)
        for k in ("wear", "temp"):
            if isinstance(d.get(k), (int, float)):
                cur[k] = d[k]
    for p in parts or []:
        if isinstance(p, dict) and str(p.get("d")) in out and p.get("l"):
            letters = out[str(p["d"])]["letters"]
            if str(p["l"]).upper() not in letters:
                letters.append(str(p["l"]).upper())
    res = []
    for i in sorted(out, key=lambda x: _int(x)):
        d = out[i]
        if d.get("bus") == "NVMe":
            d["media"] = "NVMe"
        elif d.get("media") in ("", None):
            d["media"] = "?"
        d["letters"] = sorted(d["letters"])
        res.append(d)
    return res


def _parallel(jobs: dict, timeout: int) -> dict:
    """{назва: функція} -> {назва: результат}; функції виконуються одночасно, збій однієї не зачіпає інших."""
    from concurrent.futures import ThreadPoolExecutor
    res = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(f) for k, f in jobs.items()}
        for k, fut in futs.items():
            try:
                res[k] = fut.result(timeout=timeout + 15)
            except Exception as e:  # noqa: BLE001
                res[k] = None
                res.setdefault("_errors", []).append(f"{k}: {type(e).__name__}: {e}")
    return res


def detect_hw() -> dict:
    if not E.IS_WIN:
        return _from_demo(E.DEMO)
    got = _parallel({"core": lambda: E.ps_json(CORE_SCRIPT, 45), "storage": lambda: E.ps_json(STORAGE_SCRIPT, 45),
                     "pci": lambda: E.ps_json(GPU_PCI_SCRIPT, 45), "native": HN.collect}, 45)
    data = got.get("core") if isinstance(got.get("core"), dict) else {}
    st = got.get("storage") if isinstance(got.get("storage"), dict) else {}
    nat = got.get("native") if isinstance(got.get("native"), dict) else {}
    hw = {"sources": dict(ps_core=bool(data), ps_storage=bool(st), native=sorted(k for k in nat if k != "errors"),
                          errors=(nat.get("errors") or []) + (got.get("_errors") or []))}

    # процесор: Win32_Processor — по одному запису на кожен фізичний процесор (двопроцесорні Xeon)
    cpus = [c for c in E.as_list(data.get("cpu")) if isinstance(c, dict)]
    hw["cpu"] = next((_clean_name(c.get("Name")) for c in cpus if _clean_name(c.get("Name"))), "") or \
        _clean_name(nat.get("cpu")) or tr("hw.unknown")
    hw["cores"] = sum(_int(c.get("NumberOfCores")) for c in cpus) or _int(nat.get("cores"))
    hw["threads"] = sum(_int(c.get("NumberOfLogicalProcessors")) for c in cpus) or _int(nat.get("threads"))
    if not hw["threads"]:
        hw["threads"] = os.cpu_count() or 0
    hw["cores"] = hw["cores"] or hw["threads"]
    hw["sockets"] = len(cpus) or _int(nat.get("sockets")) or 1
    hw["mhz"] = next((_int(c.get("MaxClockSpeed")) for c in cpus if _int(c.get("MaxClockSpeed"))), 0) or \
        _int(nat.get("mhz"))
    try:
        p, e = _efficiency_classes()
        hw["p_cores"], hw["e_cores"] = (p, e) if e else (hw["cores"], 0)
    except Exception:
        hw["p_cores"], hw["e_cores"] = hw["cores"], 0

    # пам'ять: Win32_PhysicalMemory, а якщо WMI не відповів — ті самі таблиці SMBIOS напряму
    mods = [m for m in E.as_list(data.get("ram")) if isinstance(m, dict) and _int(m.get("Capacity"))]
    hw["ram_gb"] = sum(_int(m.get("Capacity")) for m in mods) / 2**30 or float(nat.get("ram_gb") or 0) or \
        float(nat.get("installed_gb") or 0)
    if not hw["ram_gb"]:
        try:
            hw["ram_gb"] = E.mem_status().ullTotalPhys / 2**30
        except Exception:
            hw["ram_gb"] = 0.0
    hw["ram_modules"] = len(mods) or _int(nat.get("ram_modules"))
    speed = max((_int(m.get("Speed")) for m in mods), default=0) or _int(nat.get("ram_max_speed"))
    conf = max((_int(m.get("ConfiguredClockSpeed")) for m in mods), default=0) or _int(nat.get("ram_speed"))
    hw["ram_max_speed"] = speed
    hw["ram_speed"] = ram_speed_fix(speed, conf)
    hw["ram_type"] = next((HN.MEM_TYPES[_int(m.get("SMBIOSMemoryType"))] for m in mods
                           if _int(m.get("SMBIOSMemoryType")) in HN.MEM_TYPES), "") or nat.get("ram_type", "")

    # відеокарти: обсяг пам'яті — з розділу драйвера саме цього пристрою (AdapterRAM обрізається до 4 ГБ)
    gpus = []
    for g in E.as_list(data.get("gpu")):
        if not isinstance(g, dict):
            continue
        name = _clean_name(g.get("Name"))
        if not name or re.search(VIRTUAL_GPU, name, re.I):
            continue
        di = {}
        try:
            di = HN.driver_info(HN.driver_key_for(str(g.get("PNPDeviceID") or "")))
        except Exception:
            pass
        vram = di.get("vram") or 0.0
        if not vram:
            try:
                vram = _vram_from_registry(name)
            except Exception:
                vram = 0.0
        if not vram:
            vram = (_int(g.get("AdapterRAM")) & 0xFFFFFFFF) / 2**30
        gpus.append((name, vram, str(g.get("DriverDate") or di.get("date") or "")))
        model = mining_model(str(g.get("PNPDeviceID") or ""), name)
        if model:
            hw.setdefault("mining", []).append(dict(name=name, model=model))
    if not gpus:
        gpus = [(g["name"], g.get("vram") or 0.0, g.get("date") or "") for g in nat.get("gpus") or []
                if g.get("name") and not re.search(VIRTUAL_GPU, g["name"], re.I)]
    hw["gpus"] = gpus or [(tr("hw.unknown"), 0.0, "")]

    hw["chassis"] = [int(x) for x in E.as_list(data.get("chassis")) if str(x).isdigit()] or list(nat.get("chassis") or [])

    # диски
    hw["disks"] = merge_disks(E.as_list(st.get("disks")), E.as_list(st.get("parts")), nat.get("disks") or [])
    sys_letter = (os.environ.get("SystemDrive") or "C:")[0].upper()
    sysd = next((d for d in hw["disks"] if sys_letter in d.get("letters", [])), None)
    if sysd is None and len(hw["disks"]) == 1:
        sysd = hw["disks"][0]
    sysd = sysd or {}
    hw["disk_type"] = sysd.get("media") or "?"
    hw["disk_bus"] = sysd.get("bus") or ""
    hw["disk_name"] = sysd.get("name") or ""

    try:
        hw["battery"] = _battery()
        hw["lid"], hw["modern_standby"] = _power_caps()
    except Exception:
        hw["battery"] = hw["lid"] = hw["modern_standby"] = False
    try:
        hw["refresh"] = refresh_rates()
    except Exception:
        hw["refresh"] = (0, 0)
    hw["vbs_running"] = data.get("vbs") == 2
    osd = data.get("os") if isinstance(data.get("os"), dict) else {}
    hw["os"] = HN.clean_os(osd.get("Caption")) if osd.get("Caption") else (nat.get("os") or "Windows")
    hw["build"] = _int(osd.get("BuildNumber")) or _int(nat.get("build")) or E.win_build()
    cs = data.get("cs") if isinstance(data.get("cs"), dict) else {}
    hw["vendor"] = HN.clean_oem(cs.get("Manufacturer")) or nat.get("vendor", "")
    hw["model"] = HN.clean_oem(cs.get("Model")) or nat.get("model", "")
    if data:
        nets = [n for n in E.as_list(data.get("net")) if isinstance(n, dict)]
        wifi_re = re.compile(r"Wi-?Fi|Wireless|WLAN|802\.11", re.I)
        hw["wifi"] = any(n.get("NdisPhysicalMedium") == 9 or wifi_re.search(str(n.get("InterfaceDescription") or ""))
                         for n in nets)
        hw["ethernet"] = any(n.get("NdisPhysicalMedium") == 14 and
                             not wifi_re.search(str(n.get("InterfaceDescription") or "")) for n in nets)
    else:
        hw["wifi"], hw["ethernet"] = bool(nat.get("wifi")), bool(nat.get("ethernet"))
    try:
        hw.update(cpu_topology())
    except Exception:
        pass
    try:
        hw["display_gpu"] = display_adapter()
    except Exception:
        hw["display_gpu"] = ""
    hw["gpu_pci"] = []
    for g in E.as_list(got.get("pci")):
        if isinstance(g, dict) and g.get("name"):
            hw["gpu_pci"].append(dict(name=g["name"], cw=g.get("cw"), mw=g.get("mw"), cs=g.get("cs"), ms=g.get("ms"),
                                      bar_mb=round((g.get("bar") or 0) / 2**20)))
    try:
        import monitor as M
        hw["thermal"] = M.quick_thermal()
    except Exception:
        hw["thermal"] = {}
    hw["thermal"]["gpu"] = gpu_temp()
    return _finish(hw)


# ───────────────────────── підписи для інтерфейсу й звітів ─────────────────────────
def fmt_gb(v) -> str:
    """15.98 -> «16», 1.5 -> «1.5»."""
    v = float(v or 0)
    return f"{v:.0f}" if abs(v - round(v)) < 0.06 or v >= 10 else f"{v:.1f}"


def vram_text(v) -> str:
    v = float(v or 0)
    if v <= 0:
        return ""
    if v < 0.95:
        return tr("hw.vram_mb", mb=int(round(v * 1024 / 64) * 64) or int(v * 1024))
    return tr("hw.vram", gb=fmt_gb(v))


def cpu_sub(hw: dict) -> str:
    parts = []
    if hw.get("cores"):
        s = tr("hw.cores", c=hw["cores"], t=hw.get("threads") or hw["cores"])
        if hw.get("hybrid"):
            s += " " + tr("hw.pe", p=hw.get("p_cores"), e=hw.get("e_cores"))
        parts.append(s)
    if (hw.get("sockets") or 1) > 1:
        parts.append(tr("hw.sockets", n=hw["sockets"]))
    if hw.get("mhz"):
        parts.append(tr("hw.ghz", f=f"{hw['mhz'] / 1000:.2f}"))
    return ", ".join(parts)


def ram_sub(hw: dict) -> str:
    parts = [hw.get("ram_type") or ""]
    if hw.get("ram_speed"):
        parts.append(tr("hw.mhz", v=hw["ram_speed"]))
    if hw.get("ram_modules"):
        parts.append(tr("hw.modules", n=hw["ram_modules"]))
    return ", ".join(p for p in parts if p)


def ram_line(hw: dict) -> str:
    """«16 ГБ DDR4, 3200 МГц» без порожніх частин."""
    if not hw.get("ram_gb"):
        return tr("hw.unknown")
    head = tr("u.gb", v=fmt_gb(hw["ram_gb"])) + (f" {hw['ram_type']}" if hw.get("ram_type") else "")
    return head + (", " + tr("hw.mhz", v=hw["ram_speed"]) if hw.get("ram_speed") else "")


def disk_kind(hw: dict) -> str:
    t, bus = hw.get("disk_type") or "?", hw.get("disk_bus") or ""
    parts = [x for x in (t if t != "?" else "", bus if bus != t else "") if x]
    return " ".join(parts) or tr("hw.unknown")


def disk_line(hw: dict) -> str:
    kind = disk_kind(hw)
    name = hw.get("disk_name") or ""
    return f"{kind} {name}".strip() if kind != tr("hw.unknown") or not name else name


def _vram_from_registry(name: str) -> float:
    for sub in E.reg_subkeys(E.GPU_CLASS):
        if not sub.isdigit():
            continue
        key = E.GPU_CLASS + "\\" + sub
        desc = E.reg_get(key, "DriverDesc")
        if not desc or str(desc[1]).strip().lower() != name.lower():
            continue
        for vn in ("HardwareInformation.qwMemorySize", "HardwareInformation.MemorySize"):
            v = E.reg_get(key, vn)
            if v:
                val = v[1]
                if isinstance(val, (bytes, bytearray)):
                    val = int.from_bytes(bytes(val)[:8], "little")
                try:
                    return abs(int(val)) / 2**30
                except (TypeError, ValueError):
                    pass
    return 0.0


# ───────────────────────── аналіз (як у BoosterX) ─────────────────────────
def analyze(hw: dict) -> dict:
    """Рівень оптимізації, приватності, потенціал прискорення, найслабше місце."""
    prof = hw.get("profile", "M")
    rec = [t for t in E.TWEAKS if prof in t.p and t.reversible and E.compat(t, hw)[0] in ("ok", "warn")]
    applied = [t for t in rec if E.probe(t)]
    priv = [t for t in E.TWEAKS if t.group == "privacy"]
    priv_on = [t for t in priv if E.probe(t)]
    opt = round(100 * len(applied) / len(rec)) if rec else 100
    left = len(rec) - len(applied)
    potential = "high" if left > 15 else "mid" if left > 5 else "low"
    if hw.get("ram_gb", 16) < 7.5:
        neck = "ram"
    elif hw.get("hdd"):
        neck = "disk"
    elif hw.get("ram_modules") == 1 and not hw.get("laptop"):
        neck = "channel"
    elif hw.get("dgpu") is False and not hw.get("laptop") and hw.get("cores", 8) >= 4:
        neck = "gpu"
    elif hw.get("cores", 8) < 4:
        neck = "cpu"
    else:
        neck = "none"
    return dict(opt=opt, privacy=round(100 * len(priv_on) / len(priv)) if priv else 100, potential=potential,
                left=left, neck=neck, recommended=[t.id for t in rec])


# ───────────────────────── перевірка збірки ─────────────────────────
def _driver_age_days(date: str) -> int:
    try:
        return (datetime.now() - datetime.strptime(date[:10], "%Y-%m-%d")).days
    except Exception:
        return -1


DRIVER_URLS = {"nvidia": "https://www.nvidia.com/Download/index.aspx",
               "amd": "https://www.amd.com/en/support/download/drivers.html",
               "intel": "https://www.intel.com/content/www/us/en/support/detect.html"}


ARC_DGPU = re.compile(r"arc(\(tm\))?\s*[ab]\d{3}", re.I)

# Майнінгові карти NVIDIA без відеовиходів. Пропатчені драйвери (dartraiden/NVIDIA-patcher) показують їх як звичайні
# GeForce (P106-100 — «GTX 1060 6GB»), тому розпізнаємо за ідентифікатором пристрою PCI, а не лише за назвою.
MINING_GPUS = {"1C07": "P106-100", "1C09": "P106-090", "1B87": "P104-100", "1BC7": "P104-101", "1B07": "P102-100",
               "2189": "CMP 30HX", "1F0B": "CMP 40HX", "1E09": "CMP 50HX", "248A": "CMP 70HX", "220D": "CMP 90HX",
               "20C2": "CMP 170HX", "2082": "CMP 170HX"}
MINING_NAME = re.compile(r"\b(P10[246]-\d{3}|CMP\s*\d{2,3}\s*HX)\b", re.I)


def mining_model(pnp_id: str = "", name: str = "") -> str:
    """Модель майнінгової карти за PNPDeviceID (PCI\\VEN_10DE&DEV_1C07…) або за назвою зі стандартного драйвера."""
    m = re.search(r"VEN_10DE&DEV_([0-9A-F]{4})", pnp_id or "", re.I)
    if m and m.group(1).upper() in MINING_GPUS:
        return MINING_GPUS[m.group(1).upper()]
    n = MINING_NAME.search(name or "")
    return re.sub(r"^CMP", "CMP ", re.sub(r"\s+", "", n.group(1).upper())) if n else ""  # «CMP 30HX», «P106-100»


def is_integrated(name: str, vram: float = 0.0) -> bool:
    """Вбудована графіка: Intel UHD/Iris/Arc Graphics у Core Ultra, AMD Radeon Graphics/Vega в APU."""
    n = (name or "").lower()
    if ARC_DGPU.search(n):
        return False
    if "intel" in n:
        return True
    if re.search(r"radeon\(tm\) (graphics|vega)|vega \d+ graphics|^amd radeon graphics|\d{3}m graphics", n):
        return True
    return bool(vram and vram < 1)


def rebar_relevance(name: str):
    """Для яких відеокарт Resizable BAR важливий: critical (Intel Arc), useful (RTX 30+/RX 6000+) або None."""
    n = (name or "").lower()
    if ARC_DGPU.search(n):
        return "critical"
    if re.search(r"rtx\s*(30|40|50)\d\d", n) or re.search(r"rx\s*(6|7|9)\d{3}", n):
        return "useful"
    return None


def build_check(hw: dict, games=None) -> list:
    """-> [{id, level (ok|warn|info), title, detail, fix: (тип, значення) | None}]"""
    res = []

    def add(cid, level, fix=None, **kw):
        res.append(dict(id=cid, level=level, title=tr(f"bc.{cid}.{level}.t", **kw),
                        detail=tr(f"bc.{cid}.{level}.d", **kw), fix=fix))

    cur, mx = hw.get("ram_speed", 0), hw.get("ram_max_speed", 0)
    rtype = hw.get("ram_type", "")
    if mx and cur and mx > cur + 100:
        add("xmp", "warn", ("hint", "bios"), cur=cur, max=mx)
    elif not hw.get("laptop") and ((rtype == "DDR4" and 0 < cur <= 2666) or (rtype == "DDR5" and 0 < cur <= 4800)):
        add("xmp", "info", ("hint", "bios"), cur=cur, type=rtype)
    elif cur:
        add("xmp", "ok", cur=cur)
    if hw.get("ram_modules") == 1:
        add("channel", "info" if hw.get("laptop") else "warn")
    elif hw.get("ram_modules"):  # кількість модулів невідома — краще промовчати, ніж показати «модулів: 0»
        add("channel", "ok", n=hw["ram_modules"])
    rc, rm = hw.get("refresh") or (0, 0)
    if rm and rc and rm > rc + 1:
        add("refresh", "warn", ("settings", "ms-settings:display-advanced"), cur=rc, max=rm)
    elif rc:
        add("refresh", "ok", cur=rc)
    disks = hw.get("disks") or []
    ssd = next((d for d in disks if d.get("media") in ("SSD", "NVMe")), None)
    if hw.get("hdd") and ssd:
        add("disk", "info", ("hint", "move_ssd"), ssd=ssd["name"])
    elif hw.get("hdd"):
        add("disk", "warn")
    elif hw.get("disk_type") not in (None, "", "?"):
        add("disk", "ok", type=disk_kind(hw))
    # здоров'я дисків (SMART)
    worst = None
    for d in disks:
        h = (d.get("health") or "").lower()
        wear, temp = d.get("wear"), d.get("temp")
        if h and h not in ("healthy", "0", "здоровий", "исправен"):
            worst = worst or ("warn", "health_bad", dict(name=d["name"], state=d.get("health")))
        elif isinstance(wear, (int, float)) and wear >= 80:
            worst = worst or ("warn", "wear_high", dict(name=d["name"], wear=int(wear)))
        elif isinstance(temp, (int, float)) and temp >= 70:
            worst = worst or ("warn", "hot", dict(name=d["name"], temp=int(temp)))
        elif isinstance(wear, (int, float)) and wear >= 50:
            worst = worst or ("info", "wear_mid", dict(name=d["name"], wear=int(wear)))
    if worst:
        lvl, kind, kw = worst
        res.append(dict(id="health", level=lvl, title=tr(f"bc.health.{kind}.t", **kw),
                        detail=tr(f"bc.health.{kind}.d", **kw), fix=("hint", "backup")))
    elif disks:
        add("health", "ok", n=len(disks))
    # ігри на HDD, коли є SSD
    if games and ssd:
        hdd_letters = {l.upper() for d in disks if d.get("media") == "HDD" for l in d.get("letters", [])}
        slow = [g for g in games if g.get("path", "")[:1].upper() in hdd_letters]
        if slow:
            import ntpath
            names = ", ".join(ntpath.splitext(ntpath.basename(g["path"]))[0] for g in slow[:4])
            add("games_hdd", "info", ("hint", "move_ssd"), games=names, ssd=ssd["name"])
    if hw.get("ssd"):
        if trim_disabled():
            add("trim", "warn", ("action", "trim_on"))
        else:
            add("trim", "ok")
    mining = {m["name"]: m["model"] for m in hw.get("mining") or []}
    for name, _vram, date in hw.get("gpus", []):
        if name in mining:  # звичайний драйвер з nvidia.com вимкне 3D на майнінговій карті — оновлюють лише пропатчений
            continue
        age = _driver_age_days(date or "")
        vendor = _gpu_vendor(name)
        if age > 365 and vendor in DRIVER_URLS:
            add("driver", "warn", ("url", DRIVER_URLS[vendor]), gpu=name, months=age // 30)
            break
    else:
        add("driver", "ok")
    try:
        u = shutil.disk_usage((os.environ.get("SystemDrive", "C:") + "\\") if E.IS_WIN else "/")
        free_gb, pct = u.free / 2**30, u.free / u.total
        if pct < 0.10 or free_gb < 15:
            add("space", "warn", ("page", "cleanup"), free=f"{free_gb:.0f}")
        else:
            add("space", "ok", free=f"{free_gb:.0f}")
    except Exception:
        pass
    if E.IS_WIN and E.active_scheme() == E.POWER_SAVER and not hw.get("battery"):
        add("power", "warn", ("tweak", "ultimate_power"))
    gm = E.reg_get(r"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled")
    if gm and gm[1] == 0:
        add("gamemode", "info", ("tweak", "game_mode_on"))
    hags = E.reg_get(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode")
    if hw.get("dgpu") and not mining and hw.get("build", 0) >= 19041 and (not hags or hags[1] != 2) and E.IS_WIN:
        add("hags", "info", ("tweak", "gpu_hw_scheduling"))
    if hw.get("vbs_running"):
        add("vbs", "info", ("tweak", "disable_vbs"))
    if hw.get("x3d_dual"):
        add("x3d", "info")
    # монітор під'єднано до материнської плати. Майнінгова карта виходів не має: монітор у материнській платі — це
    # правильно, тож замість «перекиньте кабель» пояснюємо, як на ній грати.
    shown = hw.get("display_gpu") or ""
    gpus = hw.get("gpus", [])
    if mining:
        m_name, m_model = next(iter(mining.items()))
        add("mining", "info", ("hint", "mining"), model=m_model, gpu=m_name, shown=shown or "?")
    dgpus = [n for n, vr, _ in gpus if not is_integrated(n, vr) and n not in mining]
    shown_vram = next((vr for n, vr, _ in gpus if n == shown), 0)
    if shown and dgpus and not hw.get("laptop") and is_integrated(shown, shown_vram):
        add("display", "warn", ("hint", "display_cable"), igpu=shown, dgpu=dgpus[0])
    elif shown and dgpus and not hw.get("laptop"):
        add("display", "ok", gpu=shown)
    # лінія PCIe та Resizable BAR
    for g in hw.get("gpu_pci") or []:
        if is_integrated(g.get("name", "")):
            continue
        cw, mw = g.get("cw") or 0, g.get("mw") or 0
        if mw >= 8 and cw and cw < mw:
            add("pcie", "warn", ("hint", "pcie"), gpu=g["name"], cur=cw, max=mw)
        elif cw:
            add("pcie", "ok", gpu=g["name"], cur=cw)
        rel = rebar_relevance(g.get("name", ""))
        bar = g.get("bar_mb") or 0
        if rel and bar:
            if bar > 300:
                add("rebar", "ok", gpu=g["name"])
            else:
                add("rebar", "warn" if rel == "critical" else "info", ("hint", "rebar"), gpu=g["name"])
        break
    # температура в простої
    th = hw.get("thermal") or {}
    zone, passive, gpu_t = th.get("zone"), th.get("passive"), th.get("gpu")
    if isinstance(passive, (int, float)) and passive < 100:
        add("thermal", "warn", ("page", "diagnose"), pct=int(passive))
    elif isinstance(zone, (int, float)) and zone >= 75:
        add("thermal", "hot", ("hint", "thermal"), t=int(zone))
    elif isinstance(zone, (int, float)) and zone >= 60:
        add("thermal", "info", ("hint", "thermal"), t=int(zone))
    elif isinstance(gpu_t, (int, float)) and gpu_t >= 60:
        add("thermal", "gpu", ("hint", "thermal"), t=int(gpu_t))
    elif isinstance(zone, (int, float)):
        add("thermal", "ok", t=int(zone))
    for c in res:  # «hot» і «gpu» — це попередження та порада з власними текстами
        if c["id"] == "thermal" and c["level"] in ("hot", "gpu"):
            c["level"] = "warn" if c["level"] == "hot" else "info"
    return res


def trim_disabled() -> bool:
    if not E.IS_WIN:
        return False
    _, out = E.run("fsutil behavior query DisableDeleteNotify", 10, ro=True)
    m = re.search(r"NTFS DisableDeleteNotify\s*=\s*(\d)", out)
    return bool(m and m.group(1) == "1")


# ───────────────────────── MSI Mode ─────────────────────────
# Лише відеокарти, мережа і звук. Контролери дисків (HDC, SCSIAdapter: SATA, NVMe) і USB прибрано: змінений
# режим переривань на них може зробити Windows такою, що не завантажується, або вимкнути USB-клавіатуру й мишу.
MSI_CLASSES = ("Display", "Net", "MEDIA")


def msi_devices() -> list:
    """-> [{id, name, cls, msi: True | False | None (значення за замовчуванням драйвера)}]"""
    res = []
    for d in E.pnp_devices(MSI_CLASSES):
        v = E.reg_get(E.msi_key(d["id"]), "MSISupported")
        msi = None if v is None else bool(v[1])
        if E.JOURNAL.has("msi:" + d["id"]) and not E.IS_WIN:
            msi = True
        res.append(dict(d, msi=msi))
    order = {c: i for i, c in enumerate(MSI_CLASSES)}
    return sorted(res, key=lambda d: (order.get(d["cls"], 9), d["name"]))


def msi_tweak(dev: dict, on: bool) -> E.Tweak:
    t = E.Tweak("msi:" + dev["id"], "msi", [E.R(E.msi_key(dev["id"]), "MSISupported", 1 if on else 0)], reboot=True)
    t._title = f"MSI Mode: {dev['name']}"
    return t


# ───────────────────────── батарея ─────────────────────────
BAT_NS = "{http://schemas.microsoft.com/battery/2012}"


def battery_report() -> list:
    """-> [{name, design, full, cycles, wear}] у мВт·год."""
    if not E.IS_WIN:
        return [dict(name="DEMO 5B10W13930", design=57000, full=48450, cycles=312, wear=15.0)] \
            if E.DEMO in ("laptop", "old") else []
    path = os.path.join(tempfile.gettempdir(), "optimax_battery.xml")
    rc, _ = E.run(["powercfg", "/batteryreport", "/xml", "/output", path], 40, ro=True)
    if rc != 0 or not os.path.exists(path):
        return []
    res = []
    try:
        root = ET.parse(path).getroot()
        for b in root.iter(BAT_NS + "Battery"):
            def val(tag):
                el = b.find(BAT_NS + tag)
                return el.text.strip() if el is not None and el.text else ""
            design, full = int(val("DesignCapacity") or 0), int(val("FullChargeCapacity") or 0)
            wear = max(0.0, 100 * (1 - full / design)) if design else 0.0
            res.append(dict(name=" ".join(x for x in (val("Manufacturer"), val("Id")) if x) or tr("hw.battery"),
                            design=design, full=full, cycles=int(val("CycleCount") or 0), wear=wear))
    except Exception:
        pass
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return res


def battery_html_report() -> str:
    path = os.path.join(tempfile.gettempdir(), "optimax_battery.html")
    E.run(["powercfg", "/batteryreport", "/output", path], 40, ro=True)
    return path


# ───────────────────────── пам'ять ─────────────────────────
class MEMLIST(ctypes.Structure):
    _fields_ = [("ZeroPageCount", ctypes.c_size_t), ("FreePageCount", ctypes.c_size_t),
                ("ModifiedPageCount", ctypes.c_size_t), ("ModifiedNoWritePageCount", ctypes.c_size_t),
                ("BadPageCount", ctypes.c_size_t), ("PageCountByPriority", ctypes.c_size_t * 8),
                ("RepurposedPagesByPriority", ctypes.c_size_t * 8), ("ModifiedPageCountPageFile", ctypes.c_size_t)]


_demo_tick = [0]


def memory_lists() -> dict:
    """-> {standby_mb, free_mb, total_mb, load}"""
    if not E.IS_WIN:
        _demo_tick[0] += 1
        return dict(standby_mb=2600 + 40 * (_demo_tick[0] % 10), free_mb=900, total_mb=32768, load=42)
    st = E.mem_status()
    res = dict(standby_mb=0, free_mb=st.ullAvailPhys // 2**20, total_mb=st.ullTotalPhys // 2**20, load=st.dwMemoryLoad)
    try:
        E.enable_privilege("SeProfileSingleProcessPrivilege")
        ml = MEMLIST()
        nt = ctypes.windll.ntdll
        if nt.NtQuerySystemInformation(80, ctypes.byref(ml), ctypes.sizeof(ml), None) == 0:
            page = 4096
            res["standby_mb"] = sum(ml.PageCountByPriority) * page // 2**20
            res["free_mb"] = (ml.ZeroPageCount + ml.FreePageCount) * page // 2**20
    except Exception:
        pass
    return res


# ───────────────────────── живі показники ─────────────────────────
class FILETIME(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]


_last_cpu: list = [None]


def sys_stats() -> dict:
    d = {"cpu": 0.0, "ram": 0.0, "ram_total": 0.0, "disk_free": 0.0, "disk_total": 0.0}
    if not E.IS_WIN:
        d.update(cpu=0.18, ram=0.42, ram_total=32.0)
    else:
        try:
            s = E.mem_status()
            d["ram"], d["ram_total"] = s.dwMemoryLoad / 100, s.ullTotalPhys / 2**30
            idle, kern, user = FILETIME(), FILETIME(), FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
            ft = lambda f: (f.hi << 32) | f.lo  # noqa: E731
            i, t = ft(idle), ft(kern) + ft(user)
            if _last_cpu[0]:
                di, dt = i - _last_cpu[0][0], t - _last_cpu[0][1]
                if dt > 0:
                    d["cpu"] = max(0.0, min(1.0, 1 - di / dt))
            _last_cpu[0] = (i, t)
        except Exception:
            pass
    try:
        u = shutil.disk_usage((os.environ.get("SystemDrive", "C:") + "\\") if E.IS_WIN else "/")
        d["disk_free"], d["disk_total"] = u.free / 2**30, u.total / 2**30
    except Exception:
        pass
    return d


def gpu_temp():
    """Температура першої відеокарти NVIDIA через NVML, °C, або None."""
    if not E.IS_WIN:
        return 54 if E.DEMO in ("gaming", "laptop", "xeon") else None
    for path in ("nvml.dll", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll"):
        try:
            nvml = ctypes.WinDLL(path)
            init = getattr(nvml, "nvmlInit_v2", None) or nvml.nvmlInit
            if init() != 0:
                continue
            h = ctypes.c_void_p()
            get = getattr(nvml, "nvmlDeviceGetHandleByIndex_v2", None) or nvml.nvmlDeviceGetHandleByIndex
            t = ctypes.c_uint(0)
            ok = get(0, ctypes.byref(h)) == 0 and nvml.nvmlDeviceGetTemperature(h, 0, ctypes.byref(t)) == 0
            nvml.nvmlShutdown()
            if ok:
                return int(t.value)
        except Exception:
            continue
    return None


# ───────────────────────── заміри «до/після» ─────────────────────────
METRICS_SCRIPT = r"""
$b=$null; $bt=$null
try {
  $e=Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational';Id=100} -MaxEvents 1 -ErrorAction Stop
  $x=[xml]$e.ToXml(); $b=[int](($x.Event.EventData.Data | Where-Object {$_.Name -eq 'BootTime'}).'#text'); $bt=$e.TimeCreated.ToString('o')
} catch {}
$s=(Get-Service | Where-Object {$_.Status -eq 'Running'}).Count
@{boot=$b; boot_at=$bt; services=$s} | ConvertTo-Json -Compress
"""


def collect_metrics(startup_enabled: int = None) -> dict:
    if not E.IS_WIN:
        n = E.JOURNAL.count()
        return dict(boot_ms=max(9000, 21000 - 300 * n), processes=max(110, 190 - 2 * n), services=max(70, 112 - n),
                    ram_used_gb=max(2.4, 4.6 - 0.04 * n), startup=startup_enabled if startup_enabled is not None else 9,
                    disk_free_gb=30.0, ts=int(time.time()))
    data = E.ps_json(METRICS_SCRIPT, 60) or {}
    st = E.mem_status()
    try:
        u = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        free = u.free / 2**30
    except Exception:
        free = 0.0
    return dict(boot_ms=data.get("boot"), processes=len(E.processes()), services=data.get("services"),
                ram_used_gb=(st.ullTotalPhys - st.ullAvailPhys) / 2**30, startup=startup_enabled,
                disk_free_gb=free, ts=int(time.time()))
