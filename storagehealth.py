"""
OptimaX Hardware Center — стан накопичувачів: SMART (SATA / ATA), журнал здоров'я NVMe, лічильники надійності Windows.

Лише читання. Джерела, від найдетальнішого:
• NVMe — журнал Health Information (log page 02h) через IOCTL_STORAGE_QUERY_PROPERTY
  (StorageDeviceProtocolSpecificProperty, ProtocolTypeNvme): критичні попередження, температура, запас резервних блоків,
  знос (Percentage Used), записано / прочитано даних, години роботи, увімкнення, аварійні вимкнення, помилки цілісності
  даних (Media and Data Integrity Errors).
• SATA / ATA — атрибути SMART і пороги (SMART_RCV_DRIVE_DATA): перепризначені сектори (05), нестабільні (C5),
  невиправні (C6), помилки інтерфейсу CRC (C7), години (09), увімкнення (0C), температура (C2), записано (F1)…
• Windows Storage (Get-PhysicalDisk / Get-StorageReliabilityCounter) — стан, знос, температура, години, помилки
  читання/запису; для USB-дисків і контролерів, що не пропускають запити SMART.

Що диск каже про себе (SMART) і що OptimaX підтвердила сама (швидкість тестом диска, читання поверхні) — різні речі:
диск із «Healthy» може читатися з помилками, а «Warning» від Windows буває через один параметр. Тому висновок містить
обидві частини, а невідоме лишається невідомим.
"""
from __future__ import annotations

import ctypes
import struct

import engine as E
from i18n import tr

IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
SMART_RCV_DRIVE_DATA = 0x0007C088
SMART_GET_VERSION = 0x00074080
STORAGE_DEVICE_PROTOCOL_SPECIFIC = 50
PROTOCOL_NVME, NVME_LOG_PAGE, NVME_HEALTH = 3, 2, 2

ATA_NAMES = {1: "read_error_rate", 5: "reallocated", 9: "power_on_hours", 12: "power_cycles", 177: "wear_leveling",
             187: "reported_uncorrectable", 188: "command_timeout", 194: "temperature", 196: "reallocation_events",
             197: "pending", 198: "offline_uncorrectable", 199: "crc_errors", 202: "life_used_pct", 231: "life_left",
             233: "media_wearout", 241: "lbas_written", 242: "lbas_read", 246: "host_writes_sectors"}
NVME_WARN_BITS = {0: "spare", 1: "temperature", 2: "reliability", 3: "read_only", 4: "backup", 5: "pmr_read_only"}


# ───────────────────────── розбір (чистий Python, перевіряють тести) ─────────────────────────
def _u128(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 16], "little")


def parse_nvme_health(b: bytes) -> dict:
    """512 байтів журналу NVMe Health Information -> словник показників."""
    if len(b) < 192:
        return {}
    warn = b[0]
    temp_k = struct.unpack_from("<H", b, 1)[0]
    d = dict(critical_warning=warn, warnings=[n for bit, n in NVME_WARN_BITS.items() if warn & (1 << bit)],
             temperature=(temp_k - 273) if 200 < temp_k < 400 else None, spare=b[3], spare_threshold=b[4],
             percentage_used=b[5], data_read=_u128(b, 32), data_written=_u128(b, 48), host_reads=_u128(b, 64),
             host_writes=_u128(b, 80), busy_minutes=_u128(b, 96), power_cycles=_u128(b, 112),
             power_on_hours=_u128(b, 128), unsafe_shutdowns=_u128(b, 144), media_errors=_u128(b, 160),
             error_log_entries=_u128(b, 176))
    if len(b) >= 200:
        d["warn_temp_minutes"], d["crit_temp_minutes"] = struct.unpack_from("<II", b, 192)
    # одиниця даних NVMe — 1000 блоків по 512 байтів
    d["tb_written"] = round(d["data_written"] * 512000 / 1e12, 2)
    d["tb_read"] = round(d["data_read"] * 512000 / 1e12, 2)
    return d


def parse_ata_smart(values: bytes, thresholds: bytes = b"") -> dict:
    """Сторінки READ ATTRIBUTE VALUES / READ THRESHOLDS (по 512 байтів) -> {id: {name, current, worst, raw, threshold}}."""
    thr = {}
    for i in range(30):
        o = 2 + 12 * i
        if thresholds and o + 2 <= len(thresholds) and thresholds[o]:
            thr[thresholds[o]] = thresholds[o + 1]
    attrs = {}
    for i in range(30):
        o = 2 + 12 * i
        if o + 12 > len(values):
            break
        aid = values[o]
        if not aid:
            continue
        raw = int.from_bytes(values[o + 5:o + 11], "little")
        attrs[aid] = dict(id=aid, name=ATA_NAMES.get(aid, f"attr_{aid}"), current=values[o + 3], worst=values[o + 4],
                          raw=raw, threshold=thr.get(aid))
    return attrs


def ata_summary(attrs: dict, sector: int = 512) -> dict:
    """Зведення атрибутів SMART у ті самі поля, що й NVMe."""
    def raw(aid, mask=None):
        a = attrs.get(aid)
        if not a:
            return None
        return a["raw"] & mask if mask else a["raw"]
    d = dict(reallocated=raw(5), pending=raw(197), offline_uncorrectable=raw(198), crc_errors=raw(199),
             reported_uncorrectable=raw(187), power_on_hours=raw(9, 0xFFFFFFFF), power_cycles=raw(12, 0xFFFFFFFF),
             temperature=raw(194, 0xFF), reallocation_events=raw(196))
    life = attrs.get(231) or attrs.get(233) or attrs.get(177)
    if life:
        d["life_left"] = life["current"] if life["current"] <= 100 else None
    if 202 in attrs and attrs[202]["raw"] <= 100:
        d["life_left"] = 100 - attrs[202]["raw"]
    lbas = raw(241) or raw(246)
    if lbas:
        d["tb_written"] = round(lbas * sector / 1e12, 2)
    d["failing"] = sorted(a["name"] for a in attrs.values()
                          if a.get("threshold") and a["current"] and a["current"] <= a["threshold"])
    return d


def assess(info: dict) -> dict:
    """Висновок про диск: {status, findings: [(рівень, ключ, підстановки)], reported: [...], unknown: [...]}.
    info — {media, bus, health (Windows), wear, temp, nvme: {...}, ata: {...}, rel: {...}}."""
    import hwtests as HT
    f = []
    nv, ata, rel = info.get("nvme") or {}, info.get("ata") or {}, info.get("rel") or {}
    health = (info.get("health") or "").lower()
    if health in ("unhealthy", "2"):
        f.append((HT.FAIL, "sh.f.win_unhealthy", {}))
    elif health in ("warning", "1"):
        f.append((HT.WARN, "sh.f.win_warning", {}))
    if nv:
        w = nv.get("warnings") or []
        if "read_only" in w or "reliability" in w:
            f.append((HT.FAIL, "sh.f.nvme_critical", dict(what=", ".join(tr(f"sh.w.{x}") for x in w))))
        elif w:
            f.append((HT.WARN, "sh.f.nvme_warning", dict(what=", ".join(tr(f"sh.w.{x}") for x in w))))
        if nv.get("spare") is not None and nv.get("spare_threshold") and nv["spare"] <= nv["spare_threshold"]:
            f.append((HT.FAIL, "sh.f.spare", dict(s=nv["spare"], t=nv["spare_threshold"])))
        used = nv.get("percentage_used")
        if used is not None and used >= 100:
            f.append((HT.FAIL, "sh.f.worn", dict(p=used)))
        elif used is not None and used >= 80:
            f.append((HT.WARN, "sh.f.wear_high", dict(p=used)))
        if nv.get("media_errors"):
            f.append((HT.WARN, "sh.f.media_errors", dict(n=nv["media_errors"])))
    if ata:
        if ata.get("failing"):
            f.append((HT.FAIL, "sh.f.smart_failing", dict(what=", ".join(ata["failing"]))))
        if ata.get("pending"):
            f.append((HT.FAIL, "sh.f.pending", dict(n=ata["pending"])))
        if ata.get("offline_uncorrectable"):
            f.append((HT.FAIL, "sh.f.uncorrectable", dict(n=ata["offline_uncorrectable"])))
        re_ = ata.get("reallocated") or 0
        if re_ > 50:
            f.append((HT.FAIL, "sh.f.reallocated_many", dict(n=re_)))
        elif re_:
            f.append((HT.WARN, "sh.f.reallocated", dict(n=re_)))
        if ata.get("crc_errors"):
            f.append((HT.WARN, "sh.f.crc", dict(n=ata["crc_errors"])))
        life = ata.get("life_left")
        if life is not None and life <= 10:
            f.append((HT.FAIL, "sh.f.worn", dict(p=100 - life)))
        elif life is not None and life <= 20:
            f.append((HT.WARN, "sh.f.wear_high", dict(p=100 - life)))
    if not nv and not ata:
        wear = info.get("wear") if info.get("wear") is not None else rel.get("wear")
        if wear is not None and wear >= 80:
            f.append((HT.WARN, "sh.f.wear_high", dict(p=wear)))
        unc = (rel.get("read_uncorrected") or 0) + (rel.get("write_uncorrected") or 0)
        if unc:
            f.append((HT.WARN, "sh.f.rel_errors", dict(n=unc)))
    temp = nv.get("temperature") or ata.get("temperature") or info.get("temp") or rel.get("temp")
    hot = 70 if info.get("media") in ("SSD", "NVMe") or nv else 55
    if temp and temp >= hot:
        f.append((HT.WARN, "sh.f.hot", dict(t=temp)))
    known = bool(nv or ata or rel or health or info.get("wear") is not None)
    if not (nv or ata):
        f.append(("info", "sh.f.no_smart", {}))
    status = HT.status_of(f) if known else HT.NA
    return dict(status=status, findings=f, temperature=temp)


def rows(info: dict) -> list:
    """Рядки «що повідомляє диск» для інтерфейсу й звіту (None — диск цього не повідомляє: N/A)."""
    nv, ata, rel = info.get("nvme") or {}, info.get("ata") or {}, info.get("rel") or {}

    def first(*vals):
        return next((v for v in vals if v is not None), None)
    hours = first(nv.get("power_on_hours"), ata.get("power_on_hours"), rel.get("hours"))
    cycles = first(nv.get("power_cycles"), ata.get("power_cycles"), rel.get("starts"))
    tbw = first(nv.get("tb_written"), ata.get("tb_written"))
    life = 100 - nv["percentage_used"] if nv.get("percentage_used") is not None else ata.get("life_left")
    if life is None and info.get("wear") is not None:
        life = 100 - info["wear"]
    temp = first(nv.get("temperature"), ata.get("temperature"), info.get("temp"), rel.get("temp"))
    out = [("sh.r.health", tr(f"sh.h.{(info.get('health') or 'unknown').lower()}") if info.get("health") else None),
           ("sh.r.temp", f"{temp} °C" if temp is not None else None),
           ("sh.r.life", f"{max(0, life)}%" if life is not None else None),
           ("sh.r.hours", f"{hours:,}".replace(",", " ") if hours is not None else None),
           ("sh.r.cycles", cycles), ("sh.r.tbw", f"{tbw} TB" if tbw is not None else None)]
    if nv:
        out += [("sh.r.spare", f"{nv.get('spare')}% / {nv.get('spare_threshold')}%"),
                ("sh.r.unsafe", nv.get("unsafe_shutdowns")), ("sh.r.media_errors", nv.get("media_errors")),
                ("sh.r.nvme_warn", ", ".join(tr(f"sh.w.{x}") for x in nv.get("warnings") or []) or tr("hwc.no"))]
    if ata:
        out += [("sh.r.reallocated", ata.get("reallocated")), ("sh.r.pending", ata.get("pending")),
                ("sh.r.uncorrectable", ata.get("offline_uncorrectable")), ("sh.r.crc", ata.get("crc_errors"))]
    if rel and not (nv or ata):
        out += [("sh.r.read_err", rel.get("read_errors")), ("sh.r.write_err", rel.get("write_errors"))]
    return out


# ───────────────────────── читання з Windows ─────────────────────────
def _open(num) -> int:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = ctypes.c_void_p
    k32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                ctypes.c_uint32, ctypes.c_void_p]
    h = k32.CreateFileW(f"\\\\.\\PhysicalDrive{int(num)}", 0x80000000 | 0x40000000, 3, None, 3, 0, None)
    return h if h and h != ctypes.c_void_p(-1).value else 0


def _ioctl(h, code: int, inp: bytes, out_size: int) -> bytes:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
                                    ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    ib = ctypes.create_string_buffer(inp, len(inp)) if inp else None
    ob = ctypes.create_string_buffer(out_size)
    n = ctypes.c_uint32(0)
    if not k32.DeviceIoControl(h, code, ib, len(inp), ob, out_size, ctypes.byref(n), None):
        return b""
    return ob.raw[:n.value]


def read_nvme(num) -> dict:
    if not E.IS_WIN:
        return {}
    h = _open(num)
    if not h:
        return {}
    try:
        q = struct.pack("<II", STORAGE_DEVICE_PROTOCOL_SPECIFIC, 0)
        q += struct.pack("<10I", PROTOCOL_NVME, NVME_LOG_PAGE, NVME_HEALTH, 0, 40, 512, 0, 0, 0, 0)
        buf = q + bytes(512)
        out = _ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, buf, len(buf))
        if len(out) < 48 + 192:
            return {}
        off, length = struct.unpack_from("<II", out, 8 + 16)  # ProtocolDataOffset, ProtocolDataLength у дескрипторі
        start = 8 + (off or 40)
        return parse_nvme_health(out[start:start + (length or 512)])
    finally:
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(h))


def _smart_cmd(h, feature: int, drive: int) -> bytes:
    regs = struct.pack("<8B", feature, 1, 1, 0x4F, 0xC2, 0xA0 | ((drive & 1) << 4), 0xB0, 0)
    inp = struct.pack("<I", 512) + regs + struct.pack("<B3x4I", drive, 0, 0, 0, 0) + b"\0"
    out = _ioctl(h, SMART_RCV_DRIVE_DATA, inp, 16 + 512)
    return out[16:16 + 512] if len(out) >= 16 + 362 else b""


def read_ata(num) -> dict:
    if not E.IS_WIN:
        return {}
    h = _open(num)
    if not h:
        return {}
    try:
        if not _ioctl(h, SMART_GET_VERSION, b"", 24):
            return {}
        vals = _smart_cmd(h, 0xD0, int(num))
        if not vals:
            return {}
        thr = _smart_cmd(h, 0xD1, int(num))
        attrs = parse_ata_smart(vals, thr)
        if not attrs:
            return {}
        d = ata_summary(attrs)
        d["attrs"] = {str(k): {kk: vv for kk, vv in v.items() if kk != "id"} for k, v in attrs.items()}
        return d
    finally:
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(h))


REL_SCRIPT = r"""
$r=@(); foreach ($d in @(Get-PhysicalDisk)) {
  $c=$null; try { $c = $d | Get-StorageReliabilityCounter -ErrorAction Stop } catch {}
  if ($c) { $r += @{id=[string]$d.DeviceId; hours=$c.PowerOnHours; starts=$c.StartStopCycleCount; temp=$c.Temperature;
    tmax=$c.TemperatureMax; wear=$c.Wear; read_errors=$c.ReadErrorsTotal; read_uncorrected=$c.ReadErrorsUncorrected;
    write_errors=$c.WriteErrorsTotal; write_uncorrected=$c.WriteErrorsUncorrected} }
}; $r | ConvertTo-Json -Compress
"""


def reliability() -> dict:
    """Лічильники надійності Windows по номеру диска (PowerShell, з таймаутом)."""
    if not E.IS_WIN:
        return {}
    try:
        data = E.ps_json(REL_SCRIPT, 40)
    except Exception:
        return {}
    out = {}
    for x in E.as_list(data):
        if isinstance(x, dict) and x.get("id") is not None:
            out[str(x["id"])] = {k: v for k, v in x.items() if k != "id" and v is not None}
    return out


DEMO = {
    "gaming": dict(nvme=dict(critical_warning=0, warnings=[], temperature=41, spare=100, spare_threshold=10,
                             percentage_used=3, tb_written=18.4, tb_read=25.1, power_on_hours=3120, power_cycles=812,
                             unsafe_shutdowns=21, media_errors=0, error_log_entries=0)),
    "laptop": dict(nvme=dict(critical_warning=0, warnings=[], temperature=47, spare=100, spare_threshold=10,
                             percentage_used=3, tb_written=9.7, tb_read=14.0, power_on_hours=1890, power_cycles=1460,
                             unsafe_shutdowns=37, media_errors=0, error_log_entries=2)),
    "old": dict(ata=dict(reallocated=8, pending=0, offline_uncorrectable=0, crc_errors=0, reported_uncorrectable=0,
                         power_on_hours=21840, power_cycles=3911, temperature=44, failing=[])),
}


def disk_health(disk: dict, rel: dict = None) -> dict:
    """Повна картина одного диска з hardware.detect_hw()['disks']: SMART / NVMe / Windows і висновок."""
    info = dict(name=disk.get("name"), media=disk.get("media"), bus=disk.get("bus"), health=disk.get("health"),
                wear=disk.get("wear"), temp=disk.get("temp"), size_gb=disk.get("size_gb"), id=disk.get("id"),
                letters=disk.get("letters") or [])
    if not E.IS_WIN:
        hdd = disk.get("media") == "HDD"
        demo = DEMO["old"] if hdd else DEMO.get(E.DEMO, DEMO["gaming"])
        if hdd and E.DEMO != "old":
            demo = dict(ata=dict(DEMO["old"]["ata"], reallocated=0, power_on_hours=9120, power_cycles=1210))
        info.update(demo)
    else:
        num = disk.get("id")
        if num is not None and str(num).isdigit():
            if (disk.get("bus") or "").upper() == "NVME" or disk.get("media") == "NVMe":
                info["nvme"] = read_nvme(num)
            if not info.get("nvme"):
                info["ata"] = read_ata(num)
        info["rel"] = (rel or {}).get(str(num), {})
    info["assess"] = assess(info)
    info["rows"] = rows(info)
    return info


def check_all(hw: dict) -> list:
    rel = reliability()
    return [disk_health(d, rel) for d in (hw or {}).get("disks") or []]


def health_result(disks: list) -> dict:
    import hwtests as HT
    st = HT.worst([d["assess"]["status"] for d in disks]) if disks else HT.NA
    f = [x for d in disks for x in d["assess"]["findings"]]
    rws = [(d.get("name") or "?", tr(f"hwc.st.{d['assess']['status']}")) for d in disks]
    return HT.result("storage_health", st, tr(f"sh.sum.{st}", n=len(disks)), rows=rws, findings=f,
                     disks=[{k: v for k, v in d.items() if k not in ("rows",)} for d in disks])
