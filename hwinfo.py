"""
OptimaX Hardware Center — відомості про залізо: процесор (з набором інструкцій), відеокарти, пам'ять по слотах,
материнська плата й BIOS/UEFI, накопичувачі, мережеві адаптери, монітори (EDID), батарея.

Лише читання й без вигадок: чого датчик чи API не дав, те повертається як None і в інтерфейсі показується «н/д».
Основа — те, що вже визначила hardware.detect_hw(), плюс:
• IsProcessorFeaturePresent — SSE2…AVX-512, віртуалізація, RDRAND;
• таблиці SMBIOS (GetSystemFirmwareTable): плата (тип 2), BIOS (тип 0), кожен модуль пам'яті (тип 17), кількість слотів
  (тип 16); GetFirmwareType — UEFI чи Legacy BIOS; стан Secure Boot з реєстру;
• EDID моніторів із реєстру (лише активні — за WmiMonitorID): виробник, модель, рік, розмір, рідна роздільність,
  діапазон частот, колірне охоплення за координатами основних кольорів (частка трикутника sRGB / DCI-P3);
• Get-NetAdapter -Physical — фізичні мережеві адаптери, швидкість лінії, драйвер (MAC-адреса не збирається).
"""
from __future__ import annotations

import ctypes
import os
import platform
import re

import engine as E
import hwnative as HN
from i18n import tr

PF = {"SSE2": 10, "SSE3": 13, "SSSE3": 36, "SSE4.1": 37, "SSE4.2": 38, "AVX": 39, "AVX2": 40, "AVX-512F": 41,
      "RDRAND": 28, "NX": 12, "VT-x / AMD-V": 21, "SLAT": 20}
DEMO_FEATURES = {"gaming": ["SSE2", "SSE3", "SSSE3", "SSE4.1", "SSE4.2", "AVX", "AVX2", "RDRAND", "NX", "SLAT"],
                 "old": ["SSE2", "SSE3", "SSSE3", "SSE4.1", "SSE4.2", "RDRAND", "NX"]}
SRGB = ((0.640, 0.330), (0.300, 0.600), (0.150, 0.060))
DCI_P3 = ((0.680, 0.320), (0.265, 0.690), (0.150, 0.060))


# ───────────────────────── процесор ─────────────────────────
def cpu_features() -> list:
    if not E.IS_WIN:
        return list(DEMO_FEATURES.get(E.DEMO, DEMO_FEATURES["gaming"]))
    f = ctypes.windll.kernel32.IsProcessorFeaturePresent
    out = []
    for name, code in PF.items():
        try:
            if f(code):
                out.append(name)
        except Exception:
            pass
    return out


def cpu_arch() -> str:
    a = (os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("PROCESSOR_ARCHITECTURE") or platform.machine() or "")
    return {"AMD64": "x64", "X86_64": "x64", "ARM64": "ARM64", "AARCH64": "ARM64", "X86": "x86"}.get(a.upper(), a)


# ───────────────────────── SMBIOS: плата, BIOS, модулі пам'яті ─────────────────────────
MEM_FORM = {9: "DIMM", 13: "SO-DIMM", 11: "RIMM", 12: "SODIMM", 15: "FB-DIMM", 34: "CAMM"}


def smbios_details(raw: bytes) -> dict:
    """Плата, BIOS і кожен слот пам'яті. Серійні номери не беремо — вони не потрібні й ідентифікують ПК."""
    if not raw:
        return {}
    structs, ver = HN.parse_smbios(raw)
    out = dict(modules=[], slots=0)
    for typ, _h, fmt, strings in structs:
        if typ == 0 and "bios" not in out:
            out["bios"] = dict(vendor=HN._str(strings, HN._byte(fmt, 0x04)), version=HN._str(strings, HN._byte(fmt, 0x05)),
                               date=HN._str(strings, HN._byte(fmt, 0x08)))
        elif typ == 2 and "board" not in out:
            out["board"] = dict(vendor=HN.clean_oem(HN._str(strings, HN._byte(fmt, 0x04))),
                                model=HN._str(strings, HN._byte(fmt, 0x05)),
                                version=HN._str(strings, HN._byte(fmt, 0x06)))
        elif typ == 16 and (HN._byte(fmt, 0x05) in (3, None)):
            out["slots"] += HN._word(fmt, 0x0D) or 0
        elif typ == 17:
            size = HN._word(fmt, 0x0C) or 0
            mb = 0
            if size == 0x7FFF:
                mb = (HN._dword(fmt, 0x1C) or 0) & 0x7FFFFFFF
            elif size and size != 0xFFFF:
                mb = (size & 0x7FFF) // 1024 if size & 0x8000 else size
            speed = HN._word(fmt, 0x15) or 0
            conf = HN._word(fmt, 0x20) or 0
            out["modules"].append(dict(
                slot=HN._str(strings, HN._byte(fmt, 0x10)) or HN._str(strings, HN._byte(fmt, 0x11)), mb=mb,
                type=HN.MEM_TYPES.get(HN._byte(fmt, 0x12) or 0, ""), form=MEM_FORM.get(HN._byte(fmt, 0x0E) or 0, ""),
                speed=speed if speed != 0xFFFF else 0, conf=conf if conf != 0xFFFF else 0,
                vendor=HN._str(strings, HN._byte(fmt, 0x17)).strip(), part=HN._str(strings, HN._byte(fmt, 0x1A)).strip()))
    return out


def firmware() -> dict:
    """UEFI чи Legacy BIOS і Secure Boot."""
    if not E.IS_WIN:
        return dict(type="UEFI", secure_boot=E.DEMO != "old")
    out = {}
    try:
        t = ctypes.c_int(0)
        if ctypes.windll.kernel32.GetFirmwareType(ctypes.byref(t)):
            out["type"] = {1: "Legacy BIOS", 2: "UEFI"}.get(t.value)
    except Exception:
        pass
    v = E.reg_get(r"HKLM\SYSTEM\CurrentControlSet\Control\SecureBoot\State", "UEFISecureBootEnabled")
    out["secure_boot"] = None if v is None else bool(v[1])
    return out


# ───────────────────────── EDID ─────────────────────────
def _xy(hi: int, lo2: int) -> float:
    return round(((hi << 2) | lo2) / 1024, 4)


def parse_edid(b: bytes) -> dict:
    """Базовий блок EDID (128 байтів) -> виробник, модель, рік, розмір, рідна роздільність, частоти, кольори."""
    if len(b) < 128 or b[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return {}
    m = (b[8] << 8) | b[9]
    mfr = "".join(chr(((m >> s) & 0x1F) + 64) for s in (10, 5, 0))
    d = dict(manufacturer=mfr, product=f"{b[10] | (b[11] << 8):04X}", year=1990 + b[17] if b[17] else None,
             version=f"{b[18]}.{b[19]}", width_cm=b[21] or None, height_cm=b[22] or None,
             gamma=round((b[23] + 100) / 100, 2) if b[23] != 0xFF else None, digital=bool(b[20] & 0x80))
    if d["width_cm"] and d["height_cm"]:
        d["diag_in"] = round(((d["width_cm"] ** 2 + d["height_cm"] ** 2) ** 0.5) / 2.54, 1)
    lo1, lo2 = b[25], b[26]
    d["red"] = (_xy(b[27], (lo1 >> 6) & 3), _xy(b[28], (lo1 >> 4) & 3))
    d["green"] = (_xy(b[29], (lo1 >> 2) & 3), _xy(b[30], lo1 & 3))
    d["blue"] = (_xy(b[31], (lo2 >> 6) & 3), _xy(b[32], (lo2 >> 4) & 3))
    d["white"] = (_xy(b[33], (lo2 >> 2) & 3), _xy(b[34], lo2 & 3))
    for i in range(4):
        o = 54 + 18 * i
        blk = b[o:o + 18]
        if blk[0] or blk[1]:  # опис режиму (detailed timing)
            if "native" not in d:
                clock = (blk[0] | (blk[1] << 8)) * 10000
                ha, hb = blk[2] | ((blk[4] & 0xF0) << 4), blk[3] | ((blk[4] & 0x0F) << 8)
                va, vb = blk[5] | ((blk[7] & 0xF0) << 4), blk[6] | ((blk[7] & 0x0F) << 8)
                if ha and va and clock:
                    d["native"] = (ha, va)
                    d["native_hz"] = round(clock / ((ha + hb) * (va + vb)), 1)
            continue
        tag = blk[3]
        text = blk[5:18].split(b"\n")[0].decode("cp437", "replace").strip()
        if tag == 0xFC:
            d["name"] = text
        elif tag == 0xFD:
            d["min_hz"], d["max_hz"] = blk[5], blk[6]
    d["srgb"] = round(gamut_cover(d, SRGB) * 100)
    d["p3"] = round(gamut_cover(d, DCI_P3) * 100)
    return d


def _area(poly) -> float:
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def _clip(subject, clip) -> list:
    """Sutherland–Hodgman: частина многокутника subject усередині опуклого clip."""
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

    def cross(p1, p2, a, b):
        dc = (a[0] - b[0], a[1] - b[1])
        dp = (p1[0] - p2[0], p1[1] - p2[1])
        n1 = a[0] * b[1] - a[1] * b[0]
        n2 = p1[0] * p2[1] - p1[1] * p2[0]
        den = dc[0] * dp[1] - dc[1] * dp[0]
        if not den:
            return p2
        return ((n1 * dp[0] - n2 * dc[0]) / den, (n1 * dp[1] - n2 * dc[1]) / den)
    out = list(subject)
    cl = list(clip)
    if _signed(cl) < 0:
        cl.reverse()
    for i in range(len(cl)):
        a, b = cl[i], cl[(i + 1) % len(cl)]
        inp, out = out, []
        if not inp:
            break
        s = inp[-1]
        for e in inp:
            if inside(e, a, b):
                if not inside(s, a, b):
                    out.append(cross(s, e, a, b))
                out.append(e)
            elif inside(s, a, b):
                out.append(cross(s, e, a, b))
            s = e
    return out


def _signed(poly) -> float:
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2


def gamut_cover(d: dict, ref) -> float:
    """Яку частку трикутника ref (у координатах CIE xy) покриває трикутник монітора з EDID. Оцінка за паспортом
    монітора, а не замір колориметром — так і підписуємо."""
    tri = [d.get("red"), d.get("green"), d.get("blue")]
    if not all(tri) or _area(tri) < 1e-4:
        return 0.0
    inter = _clip(tri, ref)
    return min(1.0, _area(inter) / _area(ref)) if len(inter) >= 3 else 0.0


MON_SCRIPT = r"""
@(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID -ErrorAction SilentlyContinue | ForEach-Object { $_.InstanceName }) | ConvertTo-Json -Compress
"""


def monitors() -> list:
    """Активні монітори з EDID. Серійний номер не повертаємо."""
    if not E.IS_WIN:
        return [dict(manufacturer="AUS" if E.DEMO == "gaming" else "BOE", product="27A1", year=2022, version="1.4",
                     width_cm=60 if E.DEMO == "gaming" else 34, height_cm=34 if E.DEMO == "gaming" else 19,
                     diag_in=27.2 if E.DEMO == "gaming" else 15.3, gamma=2.2, digital=True,
                     name="VG27AQ" if E.DEMO == "gaming" else "", native=(2560, 1440) if E.DEMO == "gaming" else (1920, 1080),
                     native_hz=144.0, min_hz=48, max_hz=165 if E.DEMO == "gaming" else 144, srgb=99, p3=74)]
    try:
        names = [x for x in E.as_list(E.ps_json(MON_SCRIPT, 25)) if isinstance(x, str)]
    except Exception:
        names = []
    out = []
    for inst in names:
        path = re.sub(r"_\d+$", "", inst)
        v = E.reg_get(rf"HKLM\SYSTEM\CurrentControlSet\Enum\{path}\Device Parameters", "EDID")
        if v and isinstance(v[1], (bytes, bytearray)):
            d = parse_edid(bytes(v[1]))
            if d:
                out.append(d)
    return out


NET_SCRIPT = r"""
@(Get-NetAdapter -Physical -ErrorAction SilentlyContinue | ForEach-Object { @{name=$_.InterfaceDescription;
  status=[string]$_.Status; speed=[string]$_.LinkSpeed; media=[string]$_.PhysicalMediaType; driver=$_.DriverVersion;
  date=[string]$_.DriverDate} }) | ConvertTo-Json -Compress
"""


def network() -> list:
    if not E.IS_WIN:
        return [dict(name="Intel(R) Ethernet Controller I225-V", status="Up", speed="2.5 Gbps", media="802.3",
                     driver="2.1.4.3", date="2024-03-01")] if E.DEMO == "gaming" else \
            [dict(name="Intel(R) Wi-Fi 6E AX211 160MHz", status="Up", speed="1.2 Gbps", media="Native 802.11",
                  driver="23.40.0.4", date="2025-02-11")]
    try:
        return [x for x in E.as_list(E.ps_json(NET_SCRIPT, 25)) if isinstance(x, dict)]
    except Exception:
        return []


# ───────────────────────── усе разом ─────────────────────────
def collect(hw: dict) -> dict:
    """Повні відомості для розділу Hardware Information і звіту. Повільні частини (PowerShell) — тут, тож викликати у
    фоновому потоці."""
    hw = hw or {}
    import hardware as H
    raw = HN.smbios_raw() if E.IS_WIN else b""
    sm = smbios_details(raw) if raw else _demo_smbios(hw)
    gpus = []
    try:
        import gpuselect as GS
        import gpuinfo as GI
        ads = GS.adapters(GS.cached_probe() or (GI.DEMO_PROBE.get(E.DEMO) if not E.IS_WIN else {}) or {})
    except Exception:
        ads = []
    for name, vram, date in hw.get("gpus") or []:
        ad = next((a for a in ads if a.get("name") == name), {})
        gpus.append(dict(name=name, vram_gb=round(vram, 1) if vram else None, driver_date=date or None,
                         kind=ad.get("kind"), display=ad.get("display"), vendor=ad.get("vendor") or H._gpu_vendor(name)))
    try:
        st = E.mem_status()
        used = round((st.ullTotalPhys - st.ullAvailPhys) / 2**30, 1)
    except Exception:
        used = None
    try:
        bat = H.battery_report()
    except Exception:
        bat = []
    return dict(
        cpu=dict(name=hw.get("cpu"), arch=cpu_arch(), cores=hw.get("cores"), threads=hw.get("threads"),
                 p_cores=hw.get("p_cores"), e_cores=hw.get("e_cores") or None, mhz=hw.get("mhz") or None,
                 sockets=hw.get("sockets") or 1, features=cpu_features()),
        gpus=gpus,
        ram=dict(total_gb=round(hw.get("ram_gb") or 0, 1) or None, used_gb=used, type=hw.get("ram_type") or None,
                 speed=hw.get("ram_speed") or None, max_speed=hw.get("ram_max_speed") or None,
                 modules=sm.get("modules") or [], slots=sm.get("slots") or None),
        board=dict(sm.get("board") or {}, system=" ".join(x for x in (hw.get("vendor"), hw.get("model")) if x) or None),
        bios=dict(sm.get("bios") or {}, **firmware()),
        disks=hw.get("disks") or [],
        net=network(),
        monitors=monitors(),
        battery=bat,
        os=dict(name=hw.get("os"), build=hw.get("build")))


def _demo_smbios(hw: dict) -> dict:
    n = int(hw.get("ram_modules") or 1)
    per = int((hw.get("ram_gb") or 8) * 1024 / max(1, n))
    return dict(board=dict(vendor="ASUSTeK COMPUTER INC.", model="ROG STRIX B760-F GAMING WIFI", version="Rev 1.xx"),
                bios=dict(vendor="American Megatrends Inc.", version="1663", date="09/12/2024"), slots=max(2, n * 2),
                modules=[dict(slot=f"DIMM {i + 1}", mb=per, type=hw.get("ram_type") or "DDR5", form="DIMM",
                              speed=hw.get("ram_max_speed") or 0, conf=hw.get("ram_speed") or 0, vendor="Kingston",
                              part="KF552C40-16") for i in range(n)])


def na(v, unit: str = "") -> str:
    """Значення для показу: None / порожнє -> «н/д»."""
    if v is None or v == "" or v == []:
        return tr("hwc.na")
    return f"{v}{(' ' + unit) if unit else ''}"
