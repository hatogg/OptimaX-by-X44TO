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
STORAGE_ADAPTER_PROTOCOL_SPECIFIC = 49
PROTOCOL_NVME, NVME_LOG_PAGE, NVME_HEALTH = 3, 2, 2
NVME_DATA_IDENTIFY, NVME_CNS_CONTROLLER = 1, 1

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


# ───────────────────────── як у CrystalDiskInfo (7.1): паспорт диска й повна таблиця SMART ─────────────────────────
# Назви атрибутів — загальноприйняті (стандарт ATA і документація виробників); вендорські уточнення — нижче.
ATA_ATTR = {
    0x01: "Read Error Rate", 0x02: "Throughput Performance", 0x03: "Spin-Up Time", 0x04: "Start/Stop Count",
    0x05: "Reallocated Sectors Count", 0x06: "Read Channel Margin", 0x07: "Seek Error Rate",
    0x08: "Seek Time Performance", 0x09: "Power-On Hours", 0x0A: "Spin Retry Count",
    0x0B: "Recalibration Retries", 0x0C: "Power Cycle Count", 0x0D: "Soft Read Error Rate",
    0x16: "Current Helium Level", 0x17: "Helium Condition Lower", 0x18: "Helium Condition Upper",
    0xAA: "Available Reserved Space", 0xAB: "Program Fail Count", 0xAC: "Erase Fail Count",
    0xAD: "Wear Leveling Count", 0xAE: "Unexpected Power Loss Count", 0xAF: "Program Fail Count (Worst Die)",
    0xB0: "Erase Fail Count (Chip)", 0xB1: "Wear Leveling Count", 0xB2: "Used Reserved Block Count (Chip)",
    0xB3: "Used Reserved Block Count (Total)", 0xB4: "Unused Reserved Block Count (Total)",
    0xB5: "Program Fail Count (Total)", 0xB6: "Erase Fail Count (Total)", 0xB7: "SATA Downshift Error Count",
    0xB8: "End-to-End Error", 0xBB: "Reported Uncorrectable Errors", 0xBC: "Command Timeout",
    0xBD: "High Fly Writes", 0xBE: "Airflow Temperature", 0xBF: "G-Sense Error Rate",
    0xC0: "Power-off Retract Count", 0xC1: "Load/Unload Cycle Count", 0xC2: "Temperature",
    0xC3: "Hardware ECC Recovered", 0xC4: "Reallocation Event Count", 0xC5: "Current Pending Sector Count",
    0xC6: "Uncorrectable Sector Count", 0xC7: "UltraDMA CRC Error Count", 0xC8: "Write Error Rate",
    0xCA: "Data Address Mark Errors", 0xCB: "Run Out Cancel", 0xCC: "Soft ECC Correction",
    0xCD: "Thermal Asperity Rate", 0xCE: "Flying Height", 0xCF: "Spin High Current", 0xD0: "Spin Buzz",
    0xD1: "Offline Seek Performance", 0xDC: "Disk Shift", 0xDD: "G-Sense Error Rate", 0xDE: "Loaded Hours",
    0xDF: "Load/Unload Retry Count", 0xE0: "Load Friction", 0xE1: "Load/Unload Cycle Count",
    0xE2: "Load-in Time", 0xE3: "Torque Amplification Count", 0xE4: "Power-Off Retract Cycle",
    0xE6: "GMR Head Amplitude", 0xE7: "Temperature", 0xE8: "Available Reserved Space",
    0xE9: "Media Wearout Indicator", 0xEA: "Average Erase Count", 0xEB: "Good Block Count",
    0xF0: "Head Flying Hours", 0xF1: "Total LBAs Written", 0xF2: "Total LBAs Read",
    0xF3: "Total LBAs Written Expanded", 0xF4: "Total LBAs Read Expanded", 0xF9: "NAND Writes (1 GiB)",
    0xFA: "Read Error Retry Rate", 0xFE: "Free Fall Protection",
}
SSD_ATTR = {0xE7: "SSD Life Left", 0xE8: "Endurance Remaining", 0xF1: "Total Host Writes", 0xF2: "Total Host Reads"}
VENDOR_ATTR = {  # виробник -> уточнення назв
    "kingston": {0xA7: "SSD Protect Mode", 0xA8: "SATA PHY Error Count", 0xA9: "Bad Block Rate",
                 0xAA: "Bad Block Count", 0xAD: "Erase Count", 0xE7: "SSD Life Left", 0xE9: "Total NAND Writes (GiB)",
                 0xEA: "Total NAND Reads (GiB)", 0xF1: "Total Host Writes (GiB)", 0xF2: "Total Host Reads (GiB)"},
    "samsung": {0xB1: "Wear Leveling Count", 0xB3: "Used Reserved Block Count", 0xB5: "Program Fail Count",
                0xB6: "Erase Fail Count", 0xB7: "Runtime Bad Block", 0xEB: "POR Recovery Count",
                0xF1: "Total LBAs Written", 0xF2: "Total LBAs Read"},
    "crucial": {0xAA: "Grown Failing Block Count", 0xAD: "Average Block-Erase Count",
                0xB4: "Unused Reserve NAND Blocks", 0xCA: "Percent Lifetime Used", 0xCE: "Write Error Rate",
                0xD2: "Successful RAIN Recovery Count", 0xF6: "Total Host Sector Writes",
                0xF7: "Host Program Page Count", 0xF8: "FTL Program Page Count"},
    "wd": {0xA5: "Total Write/Erase Count", 0xA6: "Min W/E Cycle", 0xA7: "Min Bad Block/Die",
           0xA8: "Maximum Erase Cycle", 0xA9: "Percent Lifetime Remaining", 0xE6: "Media Wearout Indicator",
           0xF4: "Average Erase Count", 0xF5: "Max Erase Count", 0xF6: "Total Erase Count"},
    "intel": {0xE1: "Host Writes (32 MiB)", 0xE2: "Workload Media Wear", 0xE3: "Workload Read/Write Ratio",
              0xE4: "Workload Timer", 0xE9: "Media Wearout Indicator", 0xF1: "Total Host Writes (32 MiB)",
              0xF2: "Total Host Reads (32 MiB)", 0xF9: "Total NAND Writes (GiB)"},
}
NVME_ROWS = (  # (номер рядка як у CrystalDiskInfo, назва, ключ у parse_nvme_health)
    (0x01, "Critical Warning", "critical_warning"), (0x02, "Composite Temperature", "temperature"),
    (0x03, "Available Spare", "spare"), (0x04, "Available Spare Threshold", "spare_threshold"),
    (0x05, "Percentage Used", "percentage_used"), (0x06, "Data Units Read", "data_read"),
    (0x07, "Data Units Written", "data_written"), (0x08, "Host Read Commands", "host_reads"),
    (0x09, "Host Write Commands", "host_writes"), (0x0A, "Controller Busy Time", "busy_minutes"),
    (0x0B, "Power Cycles", "power_cycles"), (0x0C, "Power On Hours", "power_on_hours"),
    (0x0D, "Unsafe Shutdowns", "unsafe_shutdowns"), (0x0E, "Media and Data Integrity Errors", "media_errors"),
    (0x0F, "Number of Error Information Log Entries", "error_log_entries"))
SATA_GEN = {1: "SATA/150", 2: "SATA/300", 3: "SATA/600"}
ATA_MAJOR = ((11, "ACS-4"), (10, "ACS-3"), (9, "ACS-2"), (8, "ATA8-ACS"), (7, "ATA/ATAPI-7"), (6, "ATA/ATAPI-6"),
             (5, "ATA/ATAPI-5"))
SATA_REV = ((11, "SATA 3.5"), (10, "SATA 3.4"), (9, "SATA 3.3"), (8, "SATA 3.2"), (7, "SATA 3.1"), (6, "SATA 3.0"),
            (5, "SATA 2.6"), (4, "SATA 2.5"), (3, "SATA II Ext"), (2, "SATA 1.0a"), (1, "ATA8-AST"))
GOOD, CAUTION, BAD, UNKNOWN = "good", "caution", "bad", "unknown"


def _ata_text(b: bytes, w0: int, w1: int) -> str:
    """Рядок з IDENTIFY: слова по 2 байти з переставленими байтами."""
    s = b[w0 * 2:(w1 + 1) * 2]
    return bytes(x for i in range(0, len(s) - 1, 2) for x in (s[i + 1], s[i])).decode("ascii", "ignore").strip()


def parse_ata_identify(b: bytes) -> dict:
    """512 байтів ATA IDENTIFY DEVICE -> паспорт диска (те, що CrystalDiskInfo показує над таблицею)."""
    if len(b) < 512 or not any(b):
        return {}
    w = struct.unpack("<256H", b[:512])

    def bit(word, n):
        return w[word] not in (0, 0xFFFF) and bool(w[word] >> n & 1)
    d = dict(model=_ata_text(b, 27, 46), serial=_ata_text(b, 10, 19), firmware=_ata_text(b, 23, 26))
    sata = w[76] not in (0, 0xFFFF)
    d["interface"] = "Serial ATA" if sata else "Parallel ATA"
    if sata:
        mx = max((g for g in (1, 2, 3) if w[76] >> g & 1), default=0)
        cur = w[77] >> 1 & 7 if w[77] not in (0, 0xFFFF) else 0
        if mx:
            d["transfer"] = f"{SATA_GEN.get(cur, '----')} | {SATA_GEN[mx]}"
    std = [name for n, name in ATA_MAJOR if bit(80, n)][:1]
    rev = [name for n, name in SATA_REV if w[222] >> 12 in (1,) and w[222] >> n & 1][:1]
    d["standard"] = " | ".join(std + rev)
    feats = [("S.M.A.R.T.", bit(82, 0)), ("APM", bit(83, 3)), ("AAM", bit(83, 9)), ("48bit LBA", bit(83, 10)),
             ("NCQ", sata and bit(76, 8)), ("TRIM", bit(169, 0)), ("DevSleep", sata and bit(78, 8)),
             ("GPL", bit(84, 5)), ("VolatileWriteCache", bit(82, 5))]
    d["features"] = [n for n, on in feats if on]
    rpm = w[217]
    d["rotation"] = "SSD" if rpm == 1 else (rpm if 0x401 <= rpm < 0xFFFF else None)
    return d


def parse_nvme_identify(b: bytes) -> dict:
    """NVMe Identify Controller (4096 байтів) -> модель, серійник, прошивка, версія, функції."""
    if len(b) < 528 or not any(b[4:72]):
        return {}
    ver = struct.unpack_from("<I", b, 80)[0]
    oncs = struct.unpack_from("<H", b, 520)[0]
    d = dict(model=b[24:64].decode("ascii", "ignore").strip(), serial=b[4:24].decode("ascii", "ignore").strip(),
             firmware=b[64:72].decode("ascii", "ignore").strip(), rotation="SSD")
    major, minor = ver >> 16, ver >> 8 & 0xFF
    d["interface"] = "NVM Express"
    d["standard"] = f"NVM Express {major}.{minor}" if major else "NVM Express"
    d["features"] = ["S.M.A.R.T."] + (["TRIM"] if oncs & 4 else []) + (["VolatileWriteCache"] if b[525] & 1 else [])
    return d


def vendor_of(model: str) -> str:
    m = (model or "").upper()
    for key, marks in (("kingston", ("KINGSTON", "SA400", "SUV", "SKC", "SEDC", "SNV", "SNS", "SV300")),
                       ("samsung", ("SAMSUNG", "MZ-", "MZ7")), ("crucial", ("CRUCIAL", "CT", "MICRON", "MTFD")),
                       ("wd", ("WDC WDS", "WD BLUE", "WD GREEN", "WD RED SA", "SANDISK")),
                       ("intel", ("INTEL", "SSDSC"))):
        if any(m.startswith(x) or f" {x}" in m for x in marks):
            return key
    return ""


def attr_name(aid: int, model: str = "", ssd: bool = False) -> str:
    v = VENDOR_ATTR.get(vendor_of(model), {})
    return v.get(aid) or (SSD_ATTR.get(aid) if ssd else None) or ATA_ATTR.get(aid) or "Vendor Specific"


def attr_level(aid: int, a: dict) -> str:
    """Крапка рядка, як у CrystalDiskInfo: поріг — погано; перепризначені / нестабільні / невиправні > 0 — увага."""
    thr, cur = a.get("threshold"), a.get("current")
    if thr and cur is not None and 0 < thr < 0xFE and cur <= thr:
        return BAD
    if aid in (0x05, 0xC5, 0xC6) and (a.get("raw") or 0) & 0xFFFFFFFF:
        return CAUTION
    return GOOD


def host_io(model: str, attrs: dict, sector: int = 512) -> dict:
    """Записано / прочитано хостом і в NAND, ГБ — одиниці залежать від виробника; невідомі — не вигадуємо."""
    v = vendor_of(model)

    def raw(aid):
        a = attrs.get(aid) or attrs.get(str(aid))
        return (a or {}).get("raw")
    gib, lba = 2 ** 30 / 1e9, sector / 1e9
    unit = {"kingston": gib, "intel": 32 * 2 ** 20 / 1e9}.get(v, lba)
    out = {}
    w, r = (raw(0xF6), None) if v == "crucial" else (raw(0xF1), raw(0xF2))
    if v == "crucial":
        unit = lba
    if w:
        out["host_writes_gb"] = round(w * unit)
    if r:
        out["host_reads_gb"] = round(r * unit)
    nand = raw(0xE9) if v == "kingston" else raw(0xF9) if v == "intel" else None
    if nand:
        out["nand_writes_gb"] = round(nand * gib)
    return out


def ata_table(attrs: dict, model: str = "", ssd: bool = False) -> list:
    """Рядки таблиці SMART: (рівень, id, назва, поточне, найгірше, поріг, raw)."""
    out = []
    for k in sorted(attrs, key=lambda x: int(x)):
        a = attrs[k]
        aid = int(k)
        out.append((attr_level(aid, a), aid, attr_name(aid, model, ssd), a.get("current"), a.get("worst"),
                    a.get("threshold"), a.get("raw") or 0))
    return out


def nvme_table(nv: dict) -> list:
    """Журнал здоров'я NVMe рядками, як у CrystalDiskInfo (поточне / найгірше / поріг у NVMe немає)."""
    out = []
    for rid, name, key in NVME_ROWS:
        v = nv.get(key)
        if v is None:
            continue
        lvl = GOOD
        if key == "critical_warning" and v:
            lvl = BAD
        elif key == "spare" and nv.get("spare_threshold") and v <= nv["spare_threshold"]:
            lvl = BAD
        elif key == "percentage_used" and v >= 100:
            lvl = BAD
        elif key == "media_errors" and v:
            lvl = CAUTION
        raw = v + 273 if key == "temperature" else v  # у журналі NVMe температура — у кельвінах
        out.append((lvl, rid, name, None, None, None, raw))
    return out


def health_label(info: dict) -> tuple:
    """(стан як у CrystalDiskInfo: good / caution / bad / unknown, залишок ресурсу % або None)."""
    import hwtests as HT
    st = (info.get("assess") or {}).get("status")
    lab = {HT.PASS: GOOD, HT.WARN: CAUTION, HT.FAIL: BAD}.get(st, UNKNOWN)
    nv, ata = info.get("nvme") or {}, info.get("ata") or {}
    life = 100 - nv["percentage_used"] if nv.get("percentage_used") is not None else ata.get("life_left")
    if life is None and info.get("wear") is not None:
        life = 100 - info["wear"]
    return lab, (max(0, min(100, life)) if life is not None else None)


def details(info: dict) -> list:
    """Паспорт диска: [(ключ мови, значення або None)] — ліва й права колонки, як у CrystalDiskInfo."""
    nv, ata = info.get("nvme") or {}, info.get("ata") or {}
    idf = info.get("identify") or ata.get("identify") or {}
    if nv:
        io = {"host_reads_gb": round(nv["data_read"] * 512000 / 1e9) if nv.get("data_read") is not None else None,
              "host_writes_gb": round(nv["data_written"] * 512000 / 1e9) if nv.get("data_written") is not None
              else None}
    else:
        io = host_io(info.get("name") or idf.get("model") or "", ata.get("attrs") or {})
    hours = nv.get("power_on_hours", ata.get("power_on_hours"))
    cycles = nv.get("power_cycles", ata.get("power_cycles"))

    def gb(v):
        return f"{v:,} GB".replace(",", " ") if v is not None else None
    rot = idf.get("rotation") or ("SSD" if info.get("media") in ("SSD", "NVMe") else None)
    letters = ", ".join(f"{x}:" for x in info.get("letters") or [])
    return [("di.firmware", idf.get("firmware") or info.get("firmware")),
            ("di.serial", idf.get("serial") or info.get("serial")),
            ("di.interface", idf.get("interface") or info.get("bus")),
            ("di.transfer", info.get("link") or idf.get("transfer")),
            ("di.letters", letters or None),
            ("di.standard", idf.get("standard") or None),
            ("di.features", ", ".join(idf.get("features") or []) or None),
            ("di.host_reads", gb(io.get("host_reads_gb"))),
            ("di.host_writes", gb(io.get("host_writes_gb"))),
            ("di.nand_writes", gb(io.get("nand_writes_gb"))),
            ("di.rotation", tr("di.ssd") if rot == "SSD" else f"{rot} RPM" if rot else None),
            ("di.power_count", f"{cycles:,}".replace(",", " ") if cycles is not None else None),
            ("di.power_hours", f"{hours:,}".replace(",", " ") + " " + tr("di.hours") if hours is not None else None)]


def smart_table(info: dict) -> list:
    nv, ata = info.get("nvme") or {}, info.get("ata") or {}
    if nv:
        return nvme_table(nv)
    if ata.get("attrs"):
        return ata_table(ata["attrs"], info.get("name") or "", info.get("media") in ("SSD", "NVMe"))
    return []


def report_text(disks: list) -> str:
    """Текстовий звіт для «Копіювати» — як «Edit → Copy» у CrystalDiskInfo, щоб скинути на форум чи в чат."""
    import hwtests as HT
    lines = [f"OptimaX {E.VERSION} — {tr('di.title')}", ""]
    for d in disks:
        lab, life = health_label(d)
        lines.append(f"({', '.join(f'{x}:' for x in d.get('letters') or []) or '-'}) {d.get('name') or '?'}"
                     f" : {d.get('size_gb') or '?'} GB")
        lines.append("-" * 72)
        lines.append(f"  {tr('di.health'):<22}: {tr(f'di.h.{lab}')}" + (f" ({life} %)" if life is not None else ""))
        t = (d.get("assess") or {}).get("temperature")
        lines.append(f"  {tr('di.temp'):<22}: {f'{t} °C' if t is not None else '----'}")
        for k, v in details(d):
            lines.append(f"  {tr(k):<22}: {v if v is not None else '----'}")
        tab = smart_table(d)
        if tab:
            lines.append("")
            ata = tab[0][3] is not None
            lines.append("  ID " + ("Cur Wor Thr " if ata else "") + "RawValues(6)  Attribute Name")
            for _lvl, aid, name, cur, worst, thr, raw in tab:
                nums = f"{cur:>3} {worst:>3} {thr if thr is not None else 0:>3} " if ata else ""
                lines.append(f"  {aid:02X} {nums}{raw:012X}  {name}")
        for f in (d.get("assess") or {}).get("findings") or []:
            lines.append(f"  * {HT.finding_str(f)}")
        lines.append("")
    return "\n".join(lines)


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


def _ata_cmd(h, regs: bytes, drive: int) -> bytes:
    inp = struct.pack("<I", 512) + regs + struct.pack("<B3x4I", drive, 0, 0, 0, 0) + b"\0"
    out = _ioctl(h, SMART_RCV_DRIVE_DATA, inp, 16 + 512)
    return out[16:16 + 512] if len(out) >= 16 + 362 else b""


def read_nvme_identify(num) -> dict:
    """NVMe Identify Controller (CNS 01h): модель, серійник, прошивка, версія NVMe, TRIM, кеш запису."""
    if not E.IS_WIN:
        return {}
    h = _open(num)
    if not h:
        return {}
    try:
        q = struct.pack("<II", STORAGE_ADAPTER_PROTOCOL_SPECIFIC, 0)
        q += struct.pack("<10I", PROTOCOL_NVME, NVME_DATA_IDENTIFY, NVME_CNS_CONTROLLER, 0, 40, 4096, 0, 0, 0, 0)
        buf = q + bytes(4096)
        out = _ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, buf, len(buf))
        if len(out) < 48 + 528:
            return {}
        off, length = struct.unpack_from("<II", out, 8 + 16)
        start = 8 + (off or 40)
        return parse_nvme_identify(out[start:start + (length or 4096)])
    finally:
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(h))


def _smart_cmd(h, feature: int, drive: int) -> bytes:
    return _ata_cmd(h, struct.pack("<8B", feature, 1, 1, 0x4F, 0xC2, 0xA0 | ((drive & 1) << 4), 0xB0, 0), drive)


def _identify_cmd(h, drive: int) -> bytes:
    """ATA IDENTIFY DEVICE (ECh) — модель, серійник, прошивка, інтерфейс, функції (SMART_RCV_DRIVE_DATA це вміє)."""
    return _ata_cmd(h, struct.pack("<8B", 0, 1, 1, 0, 0, 0xA0 | ((drive & 1) << 4), 0xEC, 0), drive)


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
        d["identify"] = parse_ata_identify(_identify_cmd(h, int(num)))
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


# Прошивка, серійник і лінія PCIe контролера NVMe — для дисків, що не віддали IDENTIFY (USB, RAID), і для «Режиму»
DETAILS_SCRIPT = r"""
$r=@(); foreach ($d in @(Get-CimInstance Win32_DiskDrive)) {
  $o=@{id=[string]$d.Index; fw=[string]$d.FirmwareRevision; sn=([string]$d.SerialNumber).Trim()}
  try { $p=(Get-PnpDeviceProperty -InstanceId $d.PNPDeviceID -KeyName DEVPKEY_Device_Parent -EA Stop).Data
    if ($p -like 'PCI\*') { $h=@{}
      $k='DEVPKEY_PciDevice_CurrentLinkWidth','DEVPKEY_PciDevice_MaxLinkWidth','DEVPKEY_PciDevice_CurrentLinkSpeed',
         'DEVPKEY_PciDevice_MaxLinkSpeed'
      foreach ($x in (Get-PnpDeviceProperty -InstanceId $p -KeyName $k -EA SilentlyContinue)) {
        $h[$x.KeyName]=$x.Data }
      $o.cw=$h['DEVPKEY_PciDevice_CurrentLinkWidth']; $o.mw=$h['DEVPKEY_PciDevice_MaxLinkWidth']
      $o.cs=$h['DEVPKEY_PciDevice_CurrentLinkSpeed']; $o.ms=$h['DEVPKEY_PciDevice_MaxLinkSpeed'] } } catch {}
  $r+=$o }; $r | ConvertTo-Json -Compress
"""
PCIE_GEN = {1: "1.0", 2: "2.0", 3: "3.0", 4: "4.0", 5: "5.0", 6: "6.0"}


def pcie_link(x: dict):
    """«PCIe 4.0 x4 | PCIe 4.0 x4» (зараз | максимум), як у CrystalDiskInfo; невідомо — None."""
    def one(s, w):
        return f"PCIe {PCIE_GEN.get(int(s), '?')} x{int(w)}" if s and w else None
    try:
        cur, mx = one(x.get("cs"), x.get("cw")), one(x.get("ms"), x.get("mw"))
    except (TypeError, ValueError):
        return None
    return " | ".join(v for v in (cur, mx) if v) or None


def disk_details_ps() -> dict:
    if not E.IS_WIN:
        return {}
    try:
        data = E.ps_json(DETAILS_SCRIPT, 40)
    except Exception:
        return {}
    return {str(x["id"]): x for x in E.as_list(data) if isinstance(x, dict) and x.get("id") is not None}


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


def _demo_nvme(temp, used, written_tb, read_tb, hours, cycles, unsafe, errlog):
    unit = 512000  # одиниця даних NVMe
    return dict(critical_warning=0, warnings=[], temperature=temp, spare=100, spare_threshold=10,
                percentage_used=used, data_written=int(written_tb * 1e12 / unit), data_read=int(read_tb * 1e12 / unit),
                tb_written=written_tb, tb_read=read_tb, host_reads=int(read_tb * 1.9e9),
                host_writes=int(written_tb * 2.3e9),
                busy_minutes=hours // 3, power_on_hours=hours, power_cycles=cycles, unsafe_shutdowns=unsafe,
                media_errors=0, error_log_entries=errlog)


def _demo_ata(rows: list) -> dict:
    """[(id, поточне, найгірше, поріг, raw)] -> те, що дає read_ata()."""
    attrs = {aid: dict(id=aid, name=ATA_NAMES.get(aid, f"attr_{aid}"), current=c, worst=w, raw=r, threshold=t)
             for aid, c, w, t, r in rows}
    d = ata_summary(attrs)
    d["attrs"] = {str(k): {kk: vv for kk, vv in v.items() if kk != "id"} for k, v in attrs.items()}
    return d


# демо: правдоподібні диски для показу поза Windows (жодних справжніх серійників)
DEMO_HDD = [(0x01, 117, 99, 6, 158_442_112), (0x03, 97, 97, 0, 0), (0x04, 96, 96, 20, 4_512), (0x05, 100, 100, 10, 0),
            (0x07, 85, 60, 45, 336_778_901), (0x09, 90, 90, 0, 9_120), (0x0A, 100, 100, 97, 0),
            (0x0C, 99, 99, 20, 1_210), (0xB7, 100, 100, 0, 0), (0xB8, 100, 100, 99, 0), (0xBB, 100, 100, 0, 0),
            (0xBC, 100, 100, 0, 0), (0xBD, 100, 100, 0, 0), (0xBE, 64, 55, 40, 0x24_1C_1924), (0xC0, 100, 100, 0, 77),
            (0xC1, 89, 89, 0, 23_870), (0xC2, 36, 45, 0, 36), (0xC5, 100, 100, 0, 0), (0xC6, 100, 100, 0, 0),
            (0xC7, 200, 200, 0, 0), (0xF0, 100, 253, 0, 8_402), (0xF1, 100, 253, 0, 21_470_204_331),
            (0xF2, 100, 253, 0, 43_210_993_812)]
DEMO_OLD_HDD = [(0x01, 200, 200, 51, 3), (0x03, 186, 177, 21, 1_658), (0x04, 96, 96, 0, 4_210),
                (0x05, 199, 199, 140, 8), (0x07, 200, 200, 0, 0), (0x09, 71, 71, 0, 21_840), (0x0A, 100, 100, 0, 0), (0x0B, 100, 100, 0, 0),
                (0x0C, 97, 97, 0, 3_911), (0xC0, 200, 200, 0, 211), (0xC1, 186, 186, 0, 44_612), (0xC2, 103, 91, 0, 44),
                (0xC4, 199, 199, 0, 8), (0xC5, 200, 200, 0, 0), (0xC6, 100, 253, 0, 0), (0xC7, 200, 200, 0, 0),
                (0xC8, 100, 253, 0, 0)]
DEMO_A400 = [(0x01, 100, 100, 0, 0), (0x09, 100, 100, 0, 6_210), (0x0C, 100, 100, 0, 1_482), (0x94, 100, 100, 0, 0),
             (0x95, 100, 100, 0, 0), (0xA7, 100, 100, 0, 0), (0xA8, 100, 100, 0, 0), (0xA9, 100, 100, 0, 4),
             (0xAA, 100, 100, 10, 0), (0xAD, 100, 100, 0, 412), (0xB5, 100, 100, 0, 0), (0xB6, 100, 100, 0, 0),
             (0xC0, 100, 100, 0, 61), (0xC2, 35, 52, 0, 0x0034_000F_0023), (0xC4, 100, 100, 0, 0),
             (0xC7, 100, 100, 0, 0), (0xDA, 100, 100, 0, 0), (0xE7, 82, 82, 0, 82), (0xE9, 100, 100, 0, 29_406),
             (0xEA, 100, 100, 0, 27_133), (0xF1, 100, 100, 0, 24_118), (0xF2, 100, 100, 0, 31_904)]
DEMO_IDENTIFY = {
    "Samsung SSD 980 1TB": dict(model="Samsung SSD 980 1TB", serial="S64ANS0R00000", firmware="3B4QFXO7",
                                interface="NVM Express", standard="NVM Express 1.4", rotation="SSD",
                                features=["S.M.A.R.T.", "TRIM", "VolatileWriteCache"]),
    "Samsung SSD 990 PRO 2TB": dict(model="Samsung SSD 990 PRO 2TB", serial="S73WNJ0W00000", firmware="4B2QJXD7",
                                    interface="NVM Express", standard="NVM Express 2.0", rotation="SSD",
                                    features=["S.M.A.R.T.", "TRIM", "VolatileWriteCache"]),
    "WD PC SN740 512GB": dict(model="WD PC SN740 SDDPNQD-512G-1002", serial="23000000000", firmware="73110000",
                              interface="NVM Express", standard="NVM Express 1.4", rotation="SSD",
                              features=["S.M.A.R.T.", "TRIM", "VolatileWriteCache"]),
}
DEMO_LINK = {"Samsung SSD 980 1TB": "PCIe 3.0 x4 | PCIe 3.0 x4", "Samsung SSD 990 PRO 2TB": "PCIe 4.0 x4 | PCIe 4.0 x4",
             "WD PC SN740 512GB": "PCIe 4.0 x4 | PCIe 4.0 x4"}


def _ata_identify_demo(model, rpm, fw, sn, std="ACS-3 | SATA 3.1", trim=False):
    return dict(model=model, serial=sn, firmware=fw, interface="Serial ATA", transfer="SATA/600 | SATA/600",
                standard=std, rotation=rpm,
                features=["S.M.A.R.T.", "APM", "48bit LBA", "NCQ"] + (["TRIM"] if trim else []) + ["GPL"])


def demo_disk(disk: dict) -> dict:
    name, media = disk.get("name") or "", disk.get("media")
    if media == "NVMe" or disk.get("bus") == "NVMe":
        nv = {"Samsung SSD 980 1TB": _demo_nvme(41, 12, 38.2, 51.7, 6_840, 1_912, 48, 0),
              "Samsung SSD 990 PRO 2TB": _demo_nvme(38, 2, 9.1, 14.6, 1_240, 602, 9, 0),
              "WD PC SN740 512GB": _demo_nvme(45, 3, 9.7, 14.0, 1_890, 1_460, 37, 2)}.get(name) \
            or _demo_nvme(41, 3, 18.4, 25.1, 3_120, 812, 21, 0)
        return dict(nvme=nv, identify=DEMO_IDENTIFY.get(name, {}), link=DEMO_LINK.get(name))
    if name.upper().startswith("KINGSTON"):
        rows = [r if r[0] != 0xE7 else (0xE7, 100 - (disk.get("wear") or 18), 100 - (disk.get("wear") or 18), 0,
                                        100 - (disk.get("wear") or 18)) for r in DEMO_A400]
        return dict(ata=_demo_ata(rows), identify=_ata_identify_demo(name, "SSD", "SBFKK1C3", "50026B7700000000",
                                                                     "ACS-3 | SATA 3.2", trim=True))
    if E.DEMO == "old":
        return dict(ata=_demo_ata(DEMO_OLD_HDD),
                    identify=_ata_identify_demo(name, 5400, "01.01A01", "WX00A00000", "ATA8-ACS | SATA 3.0"))
    return dict(ata=_demo_ata(DEMO_HDD), identify=_ata_identify_demo(name, 7200, "0001", "ZFL00000"))


def disk_health(disk: dict, rel: dict = None, extra: dict = None) -> dict:
    """Повна картина одного диска з hardware.detect_hw()['disks']: SMART / NVMe / Windows і висновок."""
    info = dict(name=disk.get("name"), media=disk.get("media"), bus=disk.get("bus"), health=disk.get("health"),
                wear=disk.get("wear"), temp=disk.get("temp"), size_gb=disk.get("size_gb"), id=disk.get("id"),
                letters=disk.get("letters") or [])
    if not E.IS_WIN:
        info.update(demo_disk(disk))
    else:
        num = disk.get("id")
        if num is not None and str(num).isdigit():
            if (disk.get("bus") or "").upper() == "NVME" or disk.get("media") == "NVMe":
                info["nvme"] = read_nvme(num)
                info["identify"] = read_nvme_identify(num)
            if not info.get("nvme"):
                info["ata"] = read_ata(num)
                info["identify"] = (info["ata"] or {}).pop("identify", {}) or {}
        info["rel"] = (rel or {}).get(str(num), {})
        x = (extra or {}).get(str(num), {})
        info["firmware"], info["serial"], info["link"] = x.get("fw") or None, x.get("sn") or None, pcie_link(x)
    info["assess"] = assess(info)
    info["rows"] = rows(info)
    return info


def check_all(hw: dict) -> list:
    rel, extra = reliability(), disk_details_ps()
    return [disk_health(d, rel, extra) for d in (hw or {}).get("disks") or []]


def health_result(disks: list) -> dict:
    import hwtests as HT
    st = HT.worst([d["assess"]["status"] for d in disks]) if disks else HT.NA
    f = [x for d in disks for x in d["assess"]["findings"]]
    rws = [(d.get("name") or "?", tr(f"hwc.st.{d['assess']['status']}")) for d in disks]
    return HT.result("storage_health", st, tr(f"sh.sum.{st}", n=len(disks)), rows=rws, findings=f,
                     disks=[{k: v for k, v in d.items() if k not in ("rows",)} for d in disks])
