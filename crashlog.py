"""
OptimaX — «Чому впав комп?»: розбір аварійних перезавантажень і синіх екранів із журналу Windows.

Джерела (лише читання):
• Kernel-Power 41 — система перезавантажилася без нормального вимкнення; BugcheckCode ≠ 0 — був синій екран,
  0 — живлення зникло або система зависла намертво (часто блок живлення, перегрів, збій заліза); PowerButtonTimestamp —
  кнопку живлення тримали, щоб вимкнути.
• BugCheck 1001 (WER-SystemErrorReporting) — код синього екрана і де лежить дамп.
• EventLog 6008 — попереднє вимкнення було неочікуваним.
• Display 4101, nvlddmkm 13 / 14 / 153 — відеодрайвер завис і перезапустився (без перезавантаження).
• WHEA-Logger — апаратні помилки (процесор, пам'ять, PCIe), зокрема виправлені.
• MemoryDiagnostics-Results 1101 / 1201 — результат перевірки пам'яті Windows.
• C:\\Windows\\Minidump\\*.dmp — коди з заголовків дампів (без символів, тож «винний драйвер» не вгадуємо).

Що було запущено в момент збою, OptimaX знає зі свого журналу ігрових сесій (library.sessions): сесія, яка не
закрилася нормально, а остання позначка «гра ще працює» — перед перезавантаженням.
"""
from __future__ import annotations

import os
import re
import struct
import time

import engine as E
from i18n import tr

DAYS = 30
PAIR_GAP = 900  # 41, 1001 і 6008 пишуться під час завантаження після збою — одна подія, якщо поруч
SESSION_GAP = 30 * 60  # гра «працювала під час збою», якщо її остання позначка — до 30 хв перед перезавантаженням

# код синього екрана -> (назва, категорія). Категорії: gpu, memory, driver, hardware, cpu, disk, power, system
BUGCHECKS = {
    0x0A: ("IRQL_NOT_LESS_OR_EQUAL", "driver"), 0xD1: ("DRIVER_IRQL_NOT_LESS_OR_EQUAL", "driver"),
    0x1E: ("KMODE_EXCEPTION_NOT_HANDLED", "driver"), 0x3B: ("SYSTEM_SERVICE_EXCEPTION", "driver"),
    0x7E: ("SYSTEM_THREAD_EXCEPTION_NOT_HANDLED", "driver"), 0x8E: ("KERNEL_MODE_EXCEPTION_NOT_HANDLED", "driver"),
    0xC2: ("BAD_POOL_CALLER", "driver"), 0x19: ("BAD_POOL_HEADER", "driver"),
    0x133: ("DPC_WATCHDOG_VIOLATION", "driver"), 0x9F: ("DRIVER_POWER_STATE_FAILURE", "driver"),
    0x139: ("KERNEL_SECURITY_CHECK_FAILURE", "driver"), 0xC4: ("DRIVER_VERIFIER_DETECTED_VIOLATION", "driver"),
    0x1A: ("MEMORY_MANAGEMENT", "memory"), 0x50: ("PAGE_FAULT_IN_NONPAGED_AREA", "memory"),
    0x4E: ("PFN_LIST_CORRUPT", "memory"), 0x12B: ("FAULTY_HARDWARE_CORRUPTED_PAGE", "memory"),
    0x116: ("VIDEO_TDR_FAILURE", "gpu"), 0x117: ("VIDEO_TDR_TIMEOUT_DETECTED", "gpu"),
    0x119: ("VIDEO_SCHEDULER_INTERNAL_ERROR", "gpu"), 0x10E: ("VIDEO_MEMORY_MANAGEMENT_INTERNAL", "gpu"),
    0x113: ("VIDEO_DXGKRNL_FATAL_ERROR", "gpu"), 0x141: ("VIDEO_ENGINE_TIMEOUT_DETECTED", "gpu"),
    0x124: ("WHEA_UNCORRECTABLE_ERROR", "hardware"), 0x101: ("CLOCK_WATCHDOG_TIMEOUT", "cpu"),
    0x7A: ("KERNEL_DATA_INPAGE_ERROR", "disk"), 0x77: ("KERNEL_STACK_INPAGE_ERROR", "disk"),
    0x154: ("UNEXPECTED_STORE_EXCEPTION", "disk"), 0xEF: ("CRITICAL_PROCESS_DIED", "system"),
    0xF4: ("CRITICAL_OBJECT_TERMINATION", "disk"), 0x7B: ("INACCESSIBLE_BOOT_DEVICE", "disk"),
}
CATEGORIES = ("gpu", "memory", "driver", "hardware", "cpu", "disk", "power", "button", "system", "unknown")

# «Подій не знайдено» і «такого джерела немає» Get-WinEvent видає як EventLogException, яку SilentlyContinue
# не глушить (на чистій Windows немає nvlddmkm і подій WHEA), — тому кожен запит окремо в try/catch.
EVENTS_PS = r"""
$t=(Get-Date).AddDays(-{days})
$q=@(
 @{{LogName='System'; Id=41,6008,1001,4101; StartTime=$t}},
 @{{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'; StartTime=$t}},
 @{{LogName='System'; ProviderName='Microsoft-Windows-MemoryDiagnostics-Results'; StartTime=$t}},
 @{{LogName='System'; ProviderName='nvlddmkm'; StartTime=$t}}
)
$ev=foreach($x in $q){{ try {{ Get-WinEvent -FilterHashtable $x -MaxEvents 80 -ErrorAction Stop }} catch {{}} }}
@($ev | ForEach-Object {{
  $m=''; try {{ $m=(($_.Message -split "`n")[0]).Trim() }} catch {{}}
  @{{id=$_.Id; prov=$_.ProviderName; ts=([DateTimeOffset]$_.TimeCreated).ToUnixTimeSeconds();
     props=@($_.Properties | ForEach-Object {{ "$($_.Value)" }}); msg=$m}}
}}) | ConvertTo-Json -Compress -Depth 4
"""


def _now() -> int:
    return int(time.time())


DEMO_EVENTS = [
    dict(id=41, prov="Microsoft-Windows-Kernel-Power", ts=-36000, props=["0", "0", "0", "0", "0", "0", "0"], msg=""),
    dict(id=6008, prov="EventLog", ts=-35990, props=["2:13:55", "31.10.2026"], msg=""),
    dict(id=41, prov="Microsoft-Windows-Kernel-Power", ts=-3 * 86400,
         props=["278", "18446603336221196304", "0", "0", "0", "0", "0"], msg=""),
    dict(id=1001, prov="Microsoft-Windows-WER-SystemErrorReporting", ts=-3 * 86400 + 20,
         props=["0x00000116 (0xffff8a0f4c2e5010, 0xfffff8017d4d1234, 0xffffffffc000009a, 0x0000000000000004)",
                r"C:\Windows\MEMORY.DMP", "5a1b"], msg=""),
    dict(id=4101, prov="Display", ts=-5 * 86400, props=["nvlddmkm", ""], msg=""),
    dict(id=4101, prov="Display", ts=-5 * 86400 + 600, props=["nvlddmkm", ""], msg=""),
    dict(id=19, prov="Microsoft-Windows-WHEA-Logger", ts=-6 * 86400, props=[], msg="A corrected hardware error has "
                                                                                    "occurred."),
]


def read_events(days: int = DAYS) -> list:
    if not E.IS_WIN:
        now = _now()
        return [dict(e, ts=now + e["ts"]) for e in DEMO_EVENTS] if E.DEMO else []
    data = E.ps_json(EVENTS_PS.format(days=int(days)), 60)
    return [d for d in E.as_list(data) if isinstance(d, dict)]


def _int(s, default=0) -> int:
    try:
        s = str(s).strip()
        return int(s, 16) if s.lower().startswith("0x") else int(s)
    except (TypeError, ValueError):
        return default


CODE_RE = re.compile(r"0x([0-9a-fA-F]{1,8})\b")


def bugcheck_from_1001(props: list) -> int:
    m = CODE_RE.search(str(props[0]) if props else "")
    return int(m.group(1), 16) if m else 0


def describe_code(code: int) -> tuple:
    """-> (назва, категорія) для коду синього екрана."""
    if not code:
        return "", "power"
    return BUGCHECKS.get(code, (f"0x{code:X}", "unknown"))


def incidents(events: list) -> list:
    """Події журналу -> аварійні перезавантаження: [{ts, kind: bsod|power|button, code, name, category, dump}], від
    найновішого. Події 41, 1001 і 6008 одного збою пишуться під час наступного завантаження й поруч у часі."""
    evs = sorted((e for e in events if e.get("id") in (41, 1001, 6008)), key=lambda e: int(e.get("ts") or 0))
    out: list = []
    for e in evs:
        eid, prov, ts, props = int(e.get("id") or 0), str(e.get("prov") or ""), int(e.get("ts") or 0), \
            list(e.get("props") or [])
        if eid == 41 and "Kernel-Power" not in prov:
            continue
        if eid == 1001 and "SystemErrorReporting" not in prov and "BugCheck" not in prov:
            continue
        inc = next((i for i in out if abs(i["ts"] - ts) <= PAIR_GAP), None)
        if inc is None:
            inc = dict(ts=ts, kind="power", code=0, name="", category="power", dump="", button=False, events=[])
            out.append(inc)
        inc["events"].append(eid)
        if eid == 41:
            inc["ts"] = min(inc["ts"], ts)
            code = _int(props[0]) if props else 0
            if code and not inc["code"]:
                inc["code"] = code
            if len(props) > 6 and _int(props[6]):  # PowerButtonTimestamp: кнопку живлення тримали
                inc["button"] = True
        elif eid == 1001:
            code = bugcheck_from_1001(props)
            if code:
                inc["code"] = code
            if len(props) > 1 and str(props[1]).lower().endswith(".dmp"):
                inc["dump"] = str(props[1])
    for inc in out:
        if inc["code"]:
            inc["kind"] = "bsod"
            inc["name"], inc["category"] = describe_code(inc["code"])
        elif inc["button"]:
            inc["kind"], inc["category"] = "button", "button"
    return sorted(out, key=lambda i: -i["ts"])


def gpu_resets(events: list) -> dict:
    """Відеодрайвер завис і перезапустився (без синього екрана): {n, last, driver}."""
    tdr = [e for e in events if (e.get("id") == 4101 and "Display" in str(e.get("prov") or "")) or
           (str(e.get("prov") or "").lower() == "nvlddmkm" and e.get("id") in (13, 14, 153))]
    if not tdr:
        return {}
    last = max(tdr, key=lambda e: int(e.get("ts") or 0))
    drv = next((str((e.get("props") or [""])[0]) for e in tdr if e.get("id") == 4101 and e.get("props")), "")
    return dict(n=len(tdr), last=int(last.get("ts") or 0), driver=drv)


def hardware_errors(events: list) -> dict:
    whea = [e for e in events if "WHEA-Logger" in str(e.get("prov") or "")]
    if not whea:
        return {}
    fatal = [e for e in whea if e.get("id") in (1, 18, 20, 46)]
    last = max(whea, key=lambda e: int(e.get("ts") or 0))
    return dict(n=len(whea), fatal=len(fatal), last=int(last.get("ts") or 0), msg=str(last.get("msg") or "")[:200])


def memory_test(events: list) -> dict:
    """Остання перевірка пам'яті Windows: {ts, ok: True|False|None}."""
    res = [e for e in events if "MemoryDiagnostics" in str(e.get("prov") or "")]
    if not res:
        return {}
    last = max(res, key=lambda e: int(e.get("ts") or 0))
    eid = int(last.get("id") or 0)
    return dict(ts=int(last.get("ts") or 0), ok=True if eid == 1101 else False if eid == 1201 else None,
                msg=str(last.get("msg") or "")[:200])


# ───────────────────────── дампи ─────────────────────────
DUMP_DIR = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Minidump")


def dump_code(path: str) -> int:
    """Код синього екрана із заголовка дампу ядра (PAGEDU64 — 64 біти, PAGEDUMP — 32)."""
    try:
        with open(path, "rb") as f:
            head = f.read(0x60)
    except OSError:
        return 0
    if head[:8] == b"PAGEDU64" and len(head) >= 0x3C:
        return struct.unpack_from("<I", head, 0x38)[0]
    if head[:8] == b"PAGEDUMP" and len(head) >= 0x2C:
        return struct.unpack_from("<I", head, 0x28)[0]
    return 0


def dumps(folder: str = DUMP_DIR) -> list:
    out = []
    try:
        names = os.listdir(folder)
    except OSError:
        return out
    for n in names:
        if not n.lower().endswith(".dmp"):
            continue
        p = os.path.join(folder, n)
        try:
            st = os.stat(p)
        except OSError:
            continue
        out.append(dict(name=n, ts=int(st.st_mtime), size=st.st_size, code=dump_code(p)))
    return sorted(out, key=lambda d: -d["ts"])[:20]


# ───────────────────────── що було запущено ─────────────────────────
def running_at(inc: dict, sessions: list) -> dict:
    """Гра, яка працювала, коли комп упав: сесія не закрилася нормально, а її остання позначка — незадовго до
    завантаження після збою (inc["ts"] — час першої події після перезавантаження)."""
    best = None
    for s in sessions or []:
        if s.get("end") and not s.get("lost"):
            continue  # гру закрили як звичайно — до збою вона непричетна
        last = int(s.get("last") or s.get("start") or 0)
        if last <= inc["ts"] and inc["ts"] - last <= SESSION_GAP:
            if best is None or last > int(best.get("last") or 0):
                best = s
    return best or {}


# ───────────────────────── поради ─────────────────────────
def advice(inc: dict, game: dict, mining: bool) -> list:
    """Ключі порад crash.a.* для збою (від найважливішої)."""
    cat = inc.get("category")
    out = []
    if game and mining and cat in ("gpu", "power", "driver"):
        out.append("game_mining")
    out += {"gpu": ["gpu_driver", "gpu_heat", "gpu_oc"], "memory": ["memtest", "xmp"], "driver": ["drivers", "memtest"],
            "hardware": ["oc_off", "heat", "psu"], "cpu": ["oc_off", "heat"], "disk": ["disk_check", "sata"],
            "power": ["psu", "heat", "hang"], "button": ["button"], "system": ["sfc", "disk_check"],
            "unknown": ["drivers", "memtest"]}.get(cat, [])
    return out


def analyze(days: int = DAYS, sessions: list = None, mining: bool = False) -> dict:
    """Повний розбір: {incidents: [...], gpu: {...}, whea: {...}, memtest: {...}, dumps: [...], ts}."""
    if sessions is None:
        import library as LB
        sessions = LB.sessions()
    events = read_events(days)
    incs = incidents(events)
    for inc in incs:
        g = running_at(inc, sessions)
        inc["game"] = g.get("name") or g.get("exe") or ""
        inc["game_exe"] = g.get("exe") or ""
        inc["advice"] = advice(inc, g, mining)
    return dict(ts=_now(), days=days, incidents=incs, gpu=gpu_resets(events), whea=hardware_errors(events),
                memtest=memory_test(events), dumps=dumps() if E.IS_WIN else [])


def explain(inc: dict) -> tuple:
    """-> (заголовок, пояснення) простими словами."""
    when = time.strftime("%d.%m %H:%M", time.localtime(inc["ts"]))
    kind = inc["kind"]
    if kind == "bsod":
        title = tr("crash.t.bsod", when=when, name=inc.get("name") or f"0x{inc['code']:X}")
    else:
        title = tr(f"crash.t.{kind}", when=when)
    text = tr(f"crash.cat.{inc.get('category') or 'unknown'}")
    if inc.get("game"):
        text += " " + tr("crash.game", game=inc["game"])
    return title, text


# ───────────────────────── перевірка пам'яті ─────────────────────────
def start_memtest(log) -> dict:
    """Засіб перевірки пам'яті Windows: користувач сам вибирає «перезавантажити зараз» чи «наступного разу»."""
    if not E.IS_WIN or E.DRY_RUN:
        log("  [dry-run] mdsched.exe")
        return {"ok": 1}
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "mdsched.exe")
    try:
        os.startfile(exe)  # noqa: лише Windows
        return {"ok": 1}
    except OSError as e:
        return {"error": str(e)}


def new_since(res: dict, seen_ts: int) -> list:
    return [i for i in res.get("incidents") or [] if i["ts"] > (seen_ts or 0)]
