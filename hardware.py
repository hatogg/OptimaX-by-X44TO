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
from i18n import tr

LAPTOP_CHASSIS = {8, 9, 10, 14, 30, 31, 32}
VIRTUAL_GPU = r"Parsec|Virtual|Remote|Indirect|Microsoft Basic|RDP|SpaceDesk|Moonlight|Sunshine|AnyDesk|TeamViewer|VNC|Citrix|Meta"
DDR = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}


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
HW_SCRIPT = r"""
$c=@(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed)
$m=@(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed,SMBIOSMemoryType)
$o=Get-CimInstance Win32_OperatingSystem | Select-Object Caption,BuildNumber
$g=@(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,@{n='DriverDate';e={if($_.DriverDate){$_.DriverDate.ToString('yyyy-MM-dd')}}},DriverVersion)
$e=@(Get-CimInstance Win32_SystemEnclosure | ForEach-Object { $_.ChassisTypes })
$disk=$null
try {
  $n=(Get-Partition -DriveLetter $env:SystemDrive[0] -ErrorAction Stop | Get-Disk -ErrorAction Stop).Number
  $disk=Get-PhysicalDisk -ErrorAction Stop | Where-Object { $_.DeviceId -eq [string]$n } | Select-Object -First 1 MediaType,BusType,FriendlyName
} catch {}
$vbs=$null
try { $dg=Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard -ErrorAction Stop; $vbs=[int]$dg.VirtualizationBasedSecurityStatus } catch {}
$cs=Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model
$na=@(Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Select-Object InterfaceDescription,NdisPhysicalMedium)
$pd=@(); try { foreach ($d in Get-PhysicalDisk -ErrorAction Stop) {
  $rc=$null; try { $rc = $d | Get-StorageReliabilityCounter -ErrorAction Stop } catch {}
  $pd += @{id=[string]$d.DeviceId; name=$d.FriendlyName; media=[string]$d.MediaType; bus=[string]$d.BusType;
           health=[string]$d.HealthStatus; size=[double]$d.Size; wear=$(if($rc){$rc.Wear}); temp=$(if($rc){$rc.Temperature})}
} } catch {}
$pt=@(); try { $pt=@(Get-Partition -ErrorAction Stop | Where-Object { $_.DriveLetter } | ForEach-Object { @{l=[string]$_.DriveLetter; d=[string]$_.DiskNumber} }) } catch {}
@{cpu=$c;ram=$m;os=$o;gpu=$g;chassis=$e;disk=$disk;vbs=$vbs;cs=$cs;net=$na;disks=$pd;parts=$pt} | ConvertTo-Json -Depth 4 -Compress
"""

GPU_PCI_SCRIPT = r"""
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
    return hw


def _from_demo(name: str) -> dict:
    d = DEMO_HW.get(name, DEMO_HW["gaming"])
    total = sum(m[0] for m in d["ram"])
    hw = dict(cpu=d["cpu"], cores=d["cores"], threads=d["threads"], mhz=d["mhz"], p_cores=d["p_cores"],
              e_cores=d["e_cores"], gpus=d["gpus"], ram_gb=float(total), ram_modules=len(d["ram"]),
              ram_max_speed=max(m[1] for m in d["ram"]), ram_speed=max(m[2] for m in d["ram"]),
              ram_type=DDR.get(d["ram"][0][3], ""), chassis=d["chassis"], disk_type=d["disk"][0],
              disk_bus=d["disk"][1], disk_name=d["disk"][2], battery=d["battery"], lid=d["lid"],
              modern_standby=d["aoac"], refresh=d["refresh"], vbs_running=d["vbs"] == 2, os=d["os"][0],
              build=int(d["os"][1]), vendor=d["vendor"], wifi=d["wifi"], ethernet=d["ethernet"],
              display_gpu=d["display_gpu"], thermal=dict(d["thermal"]), **d["topo"])
    hw["disks"] = [dict(id=x[0], name=x[1], media=x[2], bus=x[3], health=x[4], size_gb=x[5], wear=x[6], temp=x[7],
                        letters=x[8]) for x in d["disks"]]
    hw["gpu_pci"] = [dict(name=x[0], cw=x[1], mw=x[2], cs=x[3], ms=x[4], bar_mb=x[5]) for x in d["pci"]]
    return _finish(hw)


def detect_hw() -> dict:
    if not E.IS_WIN:
        return _from_demo(E.DEMO)
    data = E.ps_json(HW_SCRIPT, 60) or {}
    cpus = E.as_list(data.get("cpu"))
    c = cpus[0] if cpus else {}
    hw = dict(cpu=str(c.get("Name") or "").strip() or tr("hw.unknown"), cores=int(c.get("NumberOfCores") or 0),
              threads=int(c.get("NumberOfLogicalProcessors") or 0), mhz=int(c.get("MaxClockSpeed") or 0))
    try:
        p, e = _efficiency_classes()
        hw["p_cores"], hw["e_cores"] = (p, e) if e else (hw["cores"], 0)
    except Exception:
        hw["p_cores"], hw["e_cores"] = hw["cores"], 0
    mods = E.as_list(data.get("ram"))
    hw["ram_gb"] = sum(int(m.get("Capacity") or 0) for m in mods) / 2**30
    if not hw["ram_gb"]:
        try:
            hw["ram_gb"] = E.mem_status().ullTotalPhys / 2**30
        except Exception:
            hw["ram_gb"] = 0.0
    hw["ram_modules"] = len(mods)
    hw["ram_max_speed"] = max((int(m.get("Speed") or 0) for m in mods), default=0)
    hw["ram_speed"] = max((int(m.get("ConfiguredClockSpeed") or m.get("Speed") or 0) for m in mods), default=0)
    hw["ram_type"] = DDR.get(int((mods[0].get("SMBIOSMemoryType") if mods else 0) or 0), "")
    gpus = []
    for g in E.as_list(data.get("gpu")):
        name = str(g.get("Name") or "").strip()
        if not name or re.search(VIRTUAL_GPU, name, re.I):
            continue
        vram = (int(g.get("AdapterRAM") or 0) & 0xFFFFFFFF) / 2**30
        gpus.append([name, vram, g.get("DriverDate") or ""])
    for i, (name, vram, date) in enumerate(gpus):  # AdapterRAM обрізається до 4 ГБ — уточнюємо з реєстру
        better = _vram_from_registry(name)
        if better:
            gpus[i][1] = better
    hw["gpus"] = [tuple(g) for g in gpus] or [(tr("hw.unknown"), 0.0, "")]
    hw["chassis"] = [int(x) for x in E.as_list(data.get("chassis")) if str(x).isdigit()]
    disk = data.get("disk") or {}
    media = str(disk.get("MediaType") or "")
    hw["disk_type"] = {"4": "SSD", "3": "HDD", "SSD": "SSD", "HDD": "HDD"}.get(media, "?")
    hw["disk_bus"] = {"17": "NVMe", "11": "SATA", "7": "USB", "NVMe": "NVMe", "SATA": "SATA"}.get(
        str(disk.get("BusType") or ""), str(disk.get("BusType") or ""))
    if hw["disk_bus"] == "NVMe":
        hw["disk_type"] = "NVMe"
    hw["disk_name"] = str(disk.get("FriendlyName") or "")
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
    osd = data.get("os") or {}
    hw["os"] = str(osd.get("Caption") or "Windows").replace("Microsoft ", "")
    hw["build"] = int(osd.get("BuildNumber") or E.win_build())
    cs = data.get("cs") or {}
    hw["vendor"], hw["model"] = str(cs.get("Manufacturer") or ""), str(cs.get("Model") or "")
    nets = [n for n in E.as_list(data.get("net")) if isinstance(n, dict)]
    wifi_re = re.compile(r"Wi-?Fi|Wireless|WLAN|802\.11", re.I)
    hw["wifi"] = any(n.get("NdisPhysicalMedium") == 9 or wifi_re.search(str(n.get("InterfaceDescription") or ""))
                     for n in nets)
    hw["ethernet"] = any(n.get("NdisPhysicalMedium") == 14 and not wifi_re.search(str(n.get("InterfaceDescription") or ""))
                         for n in nets)
    parts = [p for p in E.as_list(data.get("parts")) if isinstance(p, dict)]
    hw["disks"] = []
    for d in E.as_list(data.get("disks")):
        if not isinstance(d, dict):
            continue
        bus = {"17": "NVMe", "11": "SATA", "7": "USB"}.get(str(d.get("bus")), str(d.get("bus") or ""))
        media = {"4": "SSD", "3": "HDD"}.get(str(d.get("media")), str(d.get("media") or "?"))
        if bus == "NVMe":
            media = "NVMe"
        hw["disks"].append(dict(id=str(d.get("id")), name=str(d.get("name") or "").strip(), media=media, bus=bus,
                                health=str(d.get("health") or ""), size_gb=round((d.get("size") or 0) / 1e9),
                                wear=d.get("wear"), temp=d.get("temp"),
                                letters=sorted(p["l"] for p in parts if p.get("d") == str(d.get("id")))))
    try:
        hw.update(cpu_topology())
    except Exception:
        pass
    try:
        hw["display_gpu"] = display_adapter()
    except Exception:
        hw["display_gpu"] = ""
    hw["gpu_pci"] = []
    for g in E.as_list(E.ps_json(GPU_PCI_SCRIPT, 60)):
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
    else:
        add("xmp", "ok", cur=cur or "?")
    if hw.get("ram_modules") == 1:
        add("channel", "info" if hw.get("laptop") else "warn")
    else:
        add("channel", "ok", n=hw.get("ram_modules", 0))
    rc, rm = hw.get("refresh") or (0, 0)
    if rm and rc and rm > rc + 1:
        add("refresh", "warn", ("settings", "ms-settings:display-advanced"), cur=rc, max=rm)
    else:
        add("refresh", "ok", cur=rc or "?")
    disks = hw.get("disks") or []
    ssd = next((d for d in disks if d.get("media") in ("SSD", "NVMe")), None)
    if hw.get("hdd") and ssd:
        add("disk", "info", ("hint", "move_ssd"), ssd=ssd["name"])
    elif hw.get("hdd"):
        add("disk", "warn")
    else:
        add("disk", "ok", type=hw.get("disk_type", "?"))
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
    for name, _vram, date in hw.get("gpus", []):
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
    if hw.get("dgpu") and hw.get("build", 0) >= 19041 and (not hags or hags[1] != 2) and E.IS_WIN:
        add("hags", "info", ("tweak", "gpu_hw_scheduling"))
    if hw.get("vbs_running"):
        add("vbs", "info", ("tweak", "disable_vbs"))
    if hw.get("x3d_dual"):
        add("x3d", "info")
    # монітор під'єднано до материнської плати
    shown = hw.get("display_gpu") or ""
    gpus = hw.get("gpus", [])
    dgpus = [n for n, vr, _ in gpus if not is_integrated(n, vr)]
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
