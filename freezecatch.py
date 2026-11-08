"""
OptimaX — «Чому зависає?»: ловець фризів, коли на 1–5 секунд зависає все одразу — картинка, відео й звук.

Як ловимо. Окремий процес без Qt (OptimaX.exe --freeze-watch) з високим пріоритетом: потік із пріоритетом
TIME_CRITICAL прокидається кожні 50 мс і міряє, скільки минуло насправді. Звичайне навантаження (гра, браузер, компіляція)
такий потік не затримує — його зупиняє лише те, що зупиняє всю систему: шторм DPC чи переривань драйвера, режим SMM
прошивки (так виникають фризи AMD fTPM), зависання накопичувача чи відеодрайвера. Час — QueryUnbiasedInterruptTime: він
не йде уві сні й гібернації, тож прокидання ПК не сприймається як фриз. Окремий процес — тому що в самій програмі потік
чекав би на GIL, поки зайнятий інтерфейс, і ловив би «фризи» OptimaX, а не системи.

Чорна скринька: щосекунди лічильники Windows (PDH) — % DPC і переривань (усього й на найгарячішому ядрі), процесор, черга
й зайнятість диска, вільна пам'ять, жорсткі збої сторінок, найактивніший процес — останні 2 хвилини в пам'яті.
Лічильники-швидкості PDH усереднюються між двома зборами, тож перший збір після фризу показує, що робила система саме
під час нього: високі DPC чи переривання — винен драйвер; нічого не видно — систему зупинило щось поза Windows (прошивка
чи залізо).

Через 10 с після фризу (частина подій пишеться пізніше) — журнал System за хвилину до й пів хвилини після: WHEA,
скидання накопичувача (stornvme / storahci 129, disk 153), відеодрайвер (Display 4101, nvlddmkm), USB, ACPI, TPM,
мережеві драйвери, а також інші помилки й попередження. Сон чи modern standby поруч (Kernel-Power 42 / 107 / 506 / 507,
Power-Troubleshooter 1) — це не фриз, такий запис відкидаємо.

Глибокий запис (за бажанням): вбудований у Windows WPR пише DPC, переривання й завантажені драйвери в кільцевий буфер
у пам'яті (64 МБ, профіль OptimaX.wprp), а в момент фризу зберігає .etl. Його відкриває Windows Performance Analyzer:
таблиця DPC/ISR за драйверами показує, хто саме тримав процесор.

Чого OptimaX не вгадує: без глибокого запису конкретний драйвер не називається — лише клас причини й докази.

Результати — %APPDATA%\\OptimaX\\freezes: freezes.json (пише лише процес-ловець), status.json (серцебиття, TPM, стан WPR),
файл stop — прохання програми завершитися (тоді ловець сам зупиняє WPR).
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque

import engine as E

TICK = 0.05          # с: як часто прокидається вартовий
MIN_FREEZE = 0.5     # с: менші запізнення — звичайне планування потоків, а не фриз
MAX_FREEZE = 120.0   # с: довше — майже напевно сон чи modern standby, а не фриз
WARMUP = 10.0        # с після старту: запуск процесу й перший збір лічильників самі дають затримки
SAMPLE_EVERY = 1.0   # с: чорна скринька
BOX_SECONDS = 120
SETTLE = 10.0        # с після фризу до читання журналу
ETL_AFTER = 2.0      # с після фризу до збереження запису WPR (буфер кільцевий — довго чекати не можна)
EV_BEFORE, EV_AFTER = 60, 30
KEEP = 50            # фризів у списку
KEEP_ETL = 3         # записів WPR (кожен — десятки МБ)
BEAT = 10.0          # с між записами status.json
STALE = 45.0         # с без серцебиття — ловець не працює

DIR = os.path.join(E.DATA_DIR, "freezes")
LIST_PATH = os.path.join(DIR, "freezes.json")
STATUS_PATH = os.path.join(DIR, "status.json")
STOP_PATH = os.path.join(DIR, "stop")
PROFILE_NAME = "OptimaXFreeze"
MUTEX = "Local\\OptimaX-FreezeWatch"

# категорія -> рід причини (для підсумку «залізо / драйвер / програма / прошивка»)
KIND = {"hardware": "hw", "disk": "hw", "gpu": "driver", "dpc": "driver", "net": "driver", "usb": "driver",
        "io": "soft", "memory": "soft", "cpu": "soft", "ftpm": "firmware", "firmware": "firmware", "unknown": "unknown"}
# порядок важливості: за рівної кількості фризів у підсумку перемагає раніша категорія
ORDER = ("hardware", "disk", "gpu", "dpc", "net", "usb", "ftpm", "firmware", "memory", "io", "cpu", "unknown")
ADVICE = {
    "hardware": ["whea", "oc_off", "heat"],
    "disk": ["disk_fw", "disk_smart", "disk_aspm"],
    "gpu": ["gpu_driver", "gpu_hybrid"],
    "dpc": ["deep", "drivers", "latencymon"],
    "net": ["net_driver", "drivers"],
    "usb": ["usb_suspend", "usb_port"],
    "io": ["io_proc"],
    "memory": ["ram"],
    "cpu": ["cpu_proc"],
    "ftpm": ["bios", "ftpm_test"],
    "firmware": ["bios", "chipset", "deep"],
    "unknown": ["keep"],
}


# ───────────────────────── час ─────────────────────────
def unbiased_clock():
    """-> функція «секунди без часу сну» (QueryUnbiasedInterruptTime); поза Windows — time.monotonic."""
    if E.IS_WIN:
        try:
            fn = ctypes.windll.kernel32.QueryUnbiasedInterruptTime
            fn.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
            fn.restype = ctypes.c_int

            def clock() -> float:
                v = ctypes.c_ulonglong()  # свій буфер на кожен виклик: годинник читають два потоки
                fn(ctypes.byref(v))
                return v.value / 1e7
            clock()
            return clock
        except (AttributeError, OSError):
            pass
    return time.monotonic


class Watchdog:
    """Вартовий: step() засинає на TICK і повертає, на скільки секунд прокидання запізнилося, якщо це фриз
    (MIN_FREEZE … MAX_FREEZE), інакше None. Годинник і сон підставні — для тестів."""

    def __init__(self, clock=None, sleep=time.sleep, tick: float = TICK, threshold: float = MIN_FREEZE,
                 warmup: float = WARMUP, longest: float = MAX_FREEZE):
        self.clock = clock or unbiased_clock()
        self.sleep, self.tick, self.threshold, self.warmup, self.longest = sleep, tick, threshold, warmup, longest
        self.start = self.last = self.clock()

    def step(self):
        self.sleep(self.tick)
        now = self.clock()
        late = now - self.last - self.tick
        self.last = now
        if now - self.start < self.warmup or late < self.threshold or late > self.longest:
            return None
        return late


# ───────────────────────── чорна скринька ─────────────────────────
BOX_SINGLE = {
    "dpc": r"\Processor(_Total)\% DPC Time",
    "isr": r"\Processor(_Total)\% Interrupt Time",
    "cpu": r"\Processor Information(_Total)\% Processor Utility",
    "dq": r"\PhysicalDisk(_Total)\Current Disk Queue Length",
    "didle": r"\PhysicalDisk(_Total)\% Idle Time",
    "avail_mb": r"\Memory\Available MBytes",
    "pages_in": r"\Memory\Pages Input/sec",
}
BOX_ARRAY = {"core_dpc": r"\Processor(*)\% DPC Time", "core_isr": r"\Processor(*)\% Interrupt Time"}


def box_sample(raw: dict, t: float, ts: float, top: tuple = None) -> dict:
    """Збір PDH -> запис чорної скриньки: загальні значення й найгарячіше за DPC+переривання ядро."""
    s = {"t": t, "ts": ts}
    for k in BOX_SINGLE:
        if raw.get(k) is not None:
            s[k] = round(float(raw[k]), 1)
    dpc, isr = raw.get("core_dpc") or {}, raw.get("core_isr") or {}
    best, name = -1.0, ""
    for core in set(dpc) | set(isr):
        if core == "_Total":
            continue
        v = float(dpc.get(core) or 0) + float(isr.get(core) or 0)
        if v > best:
            best, name = v, core
    if best >= 0:
        s["core_max"], s["core"] = round(best, 1), name
    if top:
        s["top"], s["top_share"] = top[0], round(top[1] * 100)
    return s


def during(samples: list, start_t: float, end_t: float) -> dict:
    """Збір, що охоплює фриз: перший після його кінця (не пізніше ніж за 3 с), з попереднім збором до початку.
    win — скільки секунд усереднено в цьому зборі (фриз + решта інтервалу)."""
    prev = None
    for s in samples:
        if s["t"] < end_t - 0.2:
            prev = s
            continue
        if s["t"] - end_t > 3.0:
            break
        d = dict(s)
        d["win"] = round(s["t"] - prev["t"], 2) if prev else None
        d["full"] = bool(prev and prev["t"] <= start_t + 0.2)
        return d
    return {}


# ───────────────────────── журнал Windows ─────────────────────────
EVENTS_PS = r"""
$s=[DateTimeOffset]::FromUnixTimeSeconds({a}).LocalDateTime
$e=[DateTimeOffset]::FromUnixTimeSeconds({b}).LocalDateTime
$q=@(
 @{{LogName='System'; StartTime=$s; EndTime=$e; Level=1,2,3}},
 @{{LogName='System'; StartTime=$s; EndTime=$e; ProviderName='Microsoft-Windows-WHEA-Logger'}},
 @{{LogName='System'; StartTime=$s; EndTime=$e; Id=1,42,107,506,507}}
)
$ev=foreach($x in $q){{ try {{ Get-WinEvent -FilterHashtable $x -MaxEvents 60 -ErrorAction Stop }} catch {{}} }}
@($ev | ForEach-Object {{
  $m=''; try {{ $m=(($_.Message -split "`n")[0]).Trim() }} catch {{}}
  @{{id=$_.Id; prov=$_.ProviderName; level=[int]$_.Level; ts=([DateTimeOffset]$_.TimeCreated).ToUnixTimeSeconds();
     props=@($_.Properties | Select-Object -First 2 | ForEach-Object {{ "$($_.Value)" }}); msg=$m}}
}}) | ConvertTo-Json -Compress -Depth 4
"""

SLEEP_EVENTS = {("kernel-power", 42), ("kernel-power", 107), ("kernel-power", 506), ("kernel-power", 507),
                ("power-troubleshooter", 1)}
STORAGE_PROVS = ("stornvme", "storahci", "storport", "iastor", "amdsata", "amdnvme", "secnvme", "samsungnvme", "nvme",
                 "disk", "ntfs", "volmgr", "partmgr")
GPU_PROVS = ("display", "nvlddmkm", "amdkmdag", "amdkmdap", "amdwddmg", "igfx", "dxgkrnl")
NET_PROVS = ("netwtw", "e1d", "e1i", "e1r", "e1c", "e2f", "rt640", "rt68", "rtwlan", "rtux", "rtcx", "rtl8", "killer",
             "athw", "qcamain", "mtkwl", "bcmwl", "ndis", "netadaptercx", "ixgbe", "b57nd")
USB_PROVS = ("usbhub", "usbxhci", "ucx", "usb")
NOISE_PROVS = ("distributedcom", "dns client events", "dns-client", "time-service", "schannel", "grouppolicy",
               "eventlog", "service control manager", "winlogon", "user32", "kernel-pnp", "dhcp-client")


def prov_key(e: dict) -> str:
    p = str(e.get("prov") or "").strip().lower()
    return p[len("microsoft-windows-"):] if p.startswith("microsoft-windows-") else p


def event_kind(e: dict) -> str:
    """Подія -> sleep | whea | disk | gpu | net | usb | acpi | tpm | other | "" (шум, який не пояснює фриз)."""
    p, eid = prov_key(e), int(e.get("id") or 0)
    if (p, eid) in SLEEP_EVENTS:
        return "sleep"
    if "whea" in p:
        return "whea"
    if eid in (1, 42, 107, 506, 507) and int(e.get("level") or 4) >= 4:
        return ""  # запит сну захопив той самий id від іншого джерела, і це не помилка — до фризу непричетна
    if p.startswith(STORAGE_PROVS):
        return "disk"
    if p.startswith(GPU_PROVS):
        return "gpu"
    if p.startswith(NET_PROVS):
        return "net"
    if p.startswith(USB_PROVS):
        return "usb"
    if p.startswith("acpi"):
        return "acpi"
    if p.startswith("tpm"):
        return "tpm"
    if p.startswith(NOISE_PROVS):
        return ""
    return "other"


def read_events(a: int, b: int) -> list:
    """Події журналу System за [a; b] (unix-секунди). Лише читання."""
    if not E.IS_WIN:
        return []
    data = E.ps_json(EVENTS_PS.format(a=int(a), b=int(b)), 60)
    seen, out = set(), []
    for d in E.as_list(data):
        if not isinstance(d, dict):
            continue
        key = (d.get("id"), d.get("prov"), d.get("ts"))
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


# ───────────────────────── TPM і BIOS ─────────────────────────
TPM_PS = r"""
$t=$null; try { $t=Get-CimInstance -Namespace root/cimv2/Security/MicrosoftTpm -ClassName Win32_Tpm -ErrorAction Stop } catch {}
if($t){ @{present=$true; vendor="$($t.ManufacturerIdTxt)"; version="$($t.ManufacturerVersion)"; spec="$($t.SpecVersion)";
          enabled=[bool]$t.IsEnabled_InitialValue} | ConvertTo-Json -Compress } else { '{"present":false}' }
"""


def parse_tpm(d: dict, bios: dict = None) -> dict:
    """Win32_Tpm (+ BIOS із SMBIOS) -> {present, vendor, amd_ftpm, version, bios, bios_date}. fTPM процесора AMD
    назвається виробником «AMD»; Intel PTT — «INTC»; окремі чипи — IFX, STM, NTC, NTZ…"""
    d = d if isinstance(d, dict) else {}
    vendor = str(d.get("vendor") or "").strip().strip("\x00")
    present = bool(d.get("present")) and d.get("enabled") is not False
    b = bios or {}
    return dict(present=present, vendor=vendor, amd_ftpm=present and vendor.upper().startswith("AMD"),
                version=str(d.get("version") or ""), bios=str(b.get("version") or ""),
                bios_date=str(b.get("date") or ""))


def tpm_info() -> dict:
    if not E.IS_WIN:
        return parse_tpm({"present": True, "vendor": "AMD", "version": "3.87.0.5", "enabled": True},
                         {"version": "F.21", "date": "03/12/2021"}) if E.DEMO else {}
    d = E.ps_json(TPM_PS, 40)
    bios = {}
    try:
        import hwinfo as HI
        import hwnative as HN
        bios = HI.smbios_details(HN.smbios_raw()).get("bios") or {}
    except Exception:  # noqa: BLE001 — без дати BIOS перевірка TPM однаково корисна
        pass
    return parse_tpm(d, bios)


# ───────────────────────── вердикт ─────────────────────────
def _hot(dr: dict, dur: float) -> tuple:
    """-> (DPC+переривання на найгарячішому ядрі %, ядро, чи це шторм драйвера під час фризу)."""
    if not dr or dr.get("core_max") is None:
        return 0, "", False
    core = float(dr.get("core_max") or 0)
    win = max(float(dr.get("win") or 0) or (dur + SAMPLE_EVERY), dur, 0.1)
    expect = 100.0 * dur / win  # якби весь фриз одне ядро обробляло DPC
    return round(core), str(dr.get("core") or ""), core >= max(15.0, 0.4 * expect)


def classify(dur: float, dr: dict, events: list, tpm: dict = None, app: str = "") -> tuple:
    """Фриз -> (категорія, докази [(ключ, параметри)]). dr — збір чорної скриньки під час фризу (during)."""
    tpm = tpm or {}
    kinds: dict = {}
    for e in events or []:
        k = event_kind(e)
        if k and k != "sleep":
            kinds.setdefault(k, []).append(e)
    ev: list = []

    def add_events(kind, n=2):
        for e in kinds.get(kind, [])[:n]:
            ev.append(("event", dict(src=str(e.get("prov") or "?"), id=int(e.get("id") or 0),
                                     msg=str(e.get("msg") or "")[:140])))

    core, core_name, hot = _hot(dr, dur)
    cpu = dr.get("cpu") if dr else None
    busy = round(100 - dr["didle"]) if dr and dr.get("didle") is not None else None
    if kinds.get("whea"):
        cat = "hardware"
        add_events("whea", 3)
    elif kinds.get("disk"):
        cat = "disk"
        add_events("disk", 3)
    elif kinds.get("gpu"):
        cat = "gpu"
        add_events("gpu", 3)
    elif hot:
        cat = "net" if kinds.get("net") else "usb" if kinds.get("usb") else "dpc"
        ev.append(("dpc", dict(pct=core, core=core_name or "?")))
        add_events(cat if cat != "dpc" else "other", 2)
    elif dr and busy is not None and busy >= 90 and (dr.get("dq") or 0) >= 4:
        cat = "io"
        ev.append(("disk", dict(busy=busy, q=round(dr.get("dq") or 0))))
    elif dr and ((dr.get("avail_mb") is not None and dr["avail_mb"] < 400) or (dr.get("pages_in") or 0) > 3000):
        cat = "memory"
        ev.append(("mem", dict(mb=round(dr.get("avail_mb") or 0), pages=round(dr.get("pages_in") or 0))))
    elif dr and cpu is not None and cpu >= 97:
        cat = "cpu"
        ev.append(("cpu", dict(pct=round(cpu), proc=dr.get("top") or "?")))
    elif tpm.get("amd_ftpm"):
        cat = "ftpm"
        if dr:
            ev.append(("quiet", dict(pct=core, cpu=round(cpu or 0))))
        ev.append(("ftpm", {}))
    elif dr or kinds.get("acpi") or kinds.get("tpm"):
        cat = "firmware"
        if dr:
            ev.append(("quiet", dict(pct=core, cpu=round(cpu or 0))))
        add_events("acpi")
        add_events("tpm")
    else:
        cat = "unknown"
        ev.append(("nodata", {}))
    if cat not in ("hardware", "disk", "gpu") and not any(k == "event" for k, _ in ev):
        add_events("other", 2)  # інші помилки поруч — для повноти, вердикт не змінюють
    if app:
        ev.append(("app", dict(app=app)))
    return cat, ev


def is_sleep(events: list) -> bool:
    return any(event_kind(e) == "sleep" for e in events or [])


def record(start: float, dur: float, cat: str, ev: list, dr: dict, events: list, app: str = "", etl: str = "") -> dict:
    """Запис фризу для freezes.json."""
    keep = ("dpc", "isr", "cpu", "dq", "didle", "avail_mb", "pages_in", "core_max", "core", "top", "top_share", "win",
            "full")
    return dict(id=int((start + dur) * 1000), ts=int(start), end=int(start + dur), dur=round(dur, 2), cat=cat,
                kind=KIND.get(cat, "unknown"), ev=[[k, p] for k, p in ev],
                during={k: dr[k] for k in keep if dr and k in dr},
                events=[dict(id=e.get("id"), prov=e.get("prov"), level=e.get("level"), msg=str(e.get("msg") or "")[:160])
                        for e in (events or []) if event_kind(e)][:8],
                app=app or "", etl=etl or "")


def summary(freezes: list) -> dict:
    """Підсумок за останні 20 фризів: {n, cat, kind, share, by_cat, tied, longest, last}. tied — причини з однаковою
    найбільшою кількістю (від найсерйознішої), якщо їх кілька."""
    fr = sorted(freezes or [], key=lambda f: -int(f.get("end") or 0))[:20]
    if not fr:
        return {"n": 0}
    by: dict = {}
    for f in fr:
        by[f.get("cat") or "unknown"] = by.get(f.get("cat") or "unknown", 0) + 1
    known = {c: n for c, n in by.items() if c != "unknown"} or by
    rank = {c: (known[c], -ORDER.index(c) if c in ORDER else -99) for c in known}
    cat = max(known, key=rank.get)
    # нічия між кількома причинами — «причини різні», а порада — для найсерйознішої з них
    tied = sorted((c for c in known if known[c] == known[cat]), key=lambda c: -rank[c][1])
    return dict(n=len(fr), cat=cat, kind=KIND.get(cat, "unknown"), share=round(100 * by[cat] / len(fr)), by_cat=by,
                tied=tied if len(tied) > 1 else [], longest=max(float(f.get("dur") or 0) for f in fr),
                last=int(fr[0].get("end") or 0))


def advice(cat: str, hw: dict = None) -> list:
    out = list(ADVICE.get(cat, ADVICE["unknown"]))
    if cat == "gpu" and not (hw or {}).get("laptop"):
        out = [a for a in out if a != "gpu_hybrid"]
    return out


# ───────────────────────── глибокий запис (WPR) ─────────────────────────
WPRP = """<?xml version="1.0" encoding="utf-8"?>
<WindowsPerformanceRecorder Version="1.0" Author="OptimaX" Comments="OptimaX freeze catcher: DPC, interrupts and loaded drivers in a 64 MB ring buffer">
  <Profiles>
    <SystemCollector Id="OptimaXCollector" Name="NT Kernel Logger">
      <BufferSize Value="1024"/>
      <Buffers Value="64"/>
    </SystemCollector>
    <SystemProvider Id="OptimaXProvider">
      <Keywords>
        <Keyword Value="ProcessThread"/>
        <Keyword Value="Loader"/>
        <Keyword Value="DPC"/>
        <Keyword Value="Interrupt"/>
      </Keywords>
    </SystemProvider>
    <Profile Id="OptimaXFreeze.Verbose.Memory" Name="OptimaXFreeze" Description="OptimaX freeze catcher" LoggingMode="Memory" DetailLevel="Verbose">
      <Collectors>
        <SystemCollectorId Value="OptimaXCollector">
          <SystemProviderId Value="OptimaXProvider"/>
        </SystemCollectorId>
      </Collectors>
    </Profile>
  </Profiles>
</WindowsPerformanceRecorder>
"""


def wpr_path() -> str:
    if not E.IS_WIN:
        return ""
    try:
        import secfs as SF
        p = os.path.join(SF.system_dir(), "wpr.exe")
    except Exception:  # noqa: BLE001
        p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wpr.exe")
    return p if os.path.isfile(p) else ""


def wpr_available() -> bool:
    return bool(wpr_path()) or (not E.IS_WIN and bool(E.DEMO))


class DeepTrace:
    """Кільцевий запис WPR у пам'яті: start → (фриз) save(etl) → start …; cancel — при зупинці ловця."""

    def __init__(self, folder: str = DIR):
        self.folder = folder
        self.profile = os.path.join(folder, "OptimaX.wprp")
        self.on = False
        self.error = ""

    def _wpr(self, args: list, timeout: int = 60):
        exe = wpr_path()
        if not exe:
            return 1, "wpr.exe not found"
        return E.run([exe] + args, timeout, ro=True)

    def start(self) -> bool:
        if E.DRY_RUN:
            self.error = "dry-run"
            return False
        try:
            os.makedirs(self.folder, exist_ok=True)
            with open(self.profile, "w", encoding="utf-8") as f:
                f.write(WPRP)
        except OSError as e:
            self.error = str(e)[:200]
            return False
        rc, out = self._wpr(["-start", f"{self.profile}!{PROFILE_NAME}"])
        self.on = rc == 0
        self.error = "" if self.on else (E.first_line(out, 200) or f"wpr rc={rc}")
        return self.on

    def save(self, path: str) -> bool:
        if not self.on:
            return False
        rc, out = self._wpr(["-stop", path, "OptimaX freeze"], 180)
        self.on = False
        ok = rc == 0 and os.path.isfile(path)
        if not ok:
            self.error = E.first_line(out, 200) or f"wpr rc={rc}"
        return ok

    def cancel(self) -> None:
        if self.on:
            self._wpr(["-cancel"], 60)
        self.on = False


def prune_etl(folder: str = DIR, keep: int = KEEP_ETL) -> None:
    """Лишає keep найновіших записів freeze-*.etl (кожен — десятки МБ) і прибирає теки .NGENPDB, які WPR створює
    поруч із записом для .NET-програм, — для записів, яких уже немає."""
    import shutil
    try:
        names = os.listdir(folder)
    except OSError:
        return
    etl = sorted((n for n in names if n.startswith("freeze-") and n.endswith(".etl")), reverse=True)
    for n in etl[keep:]:
        try:
            os.remove(os.path.join(folder, n))
        except OSError:
            pass
    for n in names:
        if n.startswith("freeze-") and n.endswith(".NGENPDB") and n[:-len(".NGENPDB")] not in etl[:keep]:
            shutil.rmtree(os.path.join(folder, n), ignore_errors=True)


# ───────────────────────── файли ─────────────────────────
def _write_json(path: str, data) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def _read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def append(rec: dict, path: str = LIST_PATH, keep: int = KEEP) -> list:
    data = [r for r in _read_json(path, []) if isinstance(r, dict) and r.get("id") != rec.get("id")]
    data = sorted(data + [rec], key=lambda r: -int(r.get("end") or 0))[:keep]
    _write_json(path, data)
    return data


def _demo_freezes() -> list:
    now = int(time.time())
    return [
        dict(id=(now - 1500) * 1000, ts=now - 1503, end=now - 1500, dur=3.2, cat="ftpm", kind="firmware",
             ev=[["quiet", {"pct": 2, "cpu": 14}], ["ftpm", {}], ["app", {"app": "chrome.exe"}]],
             during={"dpc": 0.4, "isr": 0.3, "cpu": 14.0, "core_max": 2.1, "core": "0", "win": 4.1, "full": True},
             events=[], app="chrome.exe", etl=""),
        dict(id=(now - 30000) * 1000, ts=now - 30002, end=now - 30000, dur=2.4, cat="dpc", kind="driver",
             ev=[["dpc", {"pct": 61, "core": "0"}], ["app", {"app": "eldenring.exe"}]],
             during={"dpc": 7.9, "isr": 1.2, "cpu": 48.0, "core_max": 61.0, "core": "0", "win": 3.4, "full": True},
             events=[], app="eldenring.exe", etl=""),
        dict(id=(now - 86400) * 1000, ts=now - 86404, end=now - 86400, dur=4.6, cat="disk", kind="hw",
             ev=[["event", {"src": "stornvme", "id": 129, "msg": "Reset to device, \\Device\\RaidPort0, was issued."}]],
             during={"dpc": 0.5, "isr": 0.2, "cpu": 9.0, "didle": 0.0, "dq": 12.0}, events=[
                 dict(id=129, prov="stornvme", level=3, msg="Reset to device, \\Device\\RaidPort0, was issued.")],
             app="", etl=""),
    ]


def load(cleared: int = 0) -> list:
    """Зловлені фризи, від найновішого (без очищених у програмі: cleared — час «Очистити»)."""
    if not E.IS_WIN:
        data = _demo_freezes() if E.DEMO else []
    else:
        data = [r for r in _read_json(LIST_PATH, []) if isinstance(r, dict)]
    return sorted([r for r in data if int(r.get("end") or 0) > int(cleared or 0)], key=lambda r: -int(r.get("end") or 0))


def status() -> dict:
    """status.json ловця: {pid, started, beat, tpm, deep: {on, error}, wpr}. alive — серцебиття свіже."""
    if not E.IS_WIN:
        st = dict(started=int(time.time()) - 3 * 3600, beat=int(time.time()), tpm=tpm_info(), deep={"on": False},
                  wpr=wpr_available()) if E.DEMO else {}
    else:
        st = _read_json(STATUS_PATH, {})
        st = st if isinstance(st, dict) else {}
    st["alive"] = bool(st.get("beat")) and time.time() - float(st.get("beat") or 0) < STALE and not st.get("stopped")
    return st


def list_mtime() -> float:
    try:
        return os.path.getmtime(LIST_PATH)
    except OSError:
        return 0.0


def new_since(freezes: list, seen: int) -> list:
    return [f for f in freezes or [] if int(f.get("end") or 0) > int(seen or 0)]


# ───────────────────────── процес-ловець ─────────────────────────
def _args(argv) -> dict:
    out = {}
    for a in argv:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            out[k] = v
    return out


def _boost_thread() -> None:
    if E.IS_WIN:
        try:
            k32 = ctypes.windll.kernel32
            k32.GetCurrentThread.restype = ctypes.c_void_p
            k32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
            k32.SetThreadPriority(k32.GetCurrentThread(), 15)  # THREAD_PRIORITY_TIME_CRITICAL
        except (AttributeError, OSError):
            pass


def _boost_process() -> None:
    if E.IS_WIN:
        try:
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = ctypes.c_void_p
            k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x80)  # HIGH_PRIORITY_CLASS
        except (AttributeError, OSError):
            pass


_MUTEX = []


def _single_instance(wait: float = 4.0) -> bool:
    """Один ловець на сеанс. Попередній може ще завершуватися (програму щойно перезапустили) — чекаємо до wait с."""
    if not E.IS_WIN:
        return True
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        deadline = time.time() + wait
        while True:
            h = k32.CreateMutexW(None, False, MUTEX)
            if not h:
                return True
            if ctypes.get_last_error() != 183:  # не ERROR_ALREADY_EXISTS — ми перші
                _MUTEX.append(h)
                return True
            k32.CloseHandle(h)
            if time.time() > deadline:
                return False
            time.sleep(0.5)
    except (AttributeError, OSError):
        return True


def _alive(pid: int) -> bool:
    if not pid:
        return True
    if not E.IS_WIN:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    h = k32.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
    if not h:
        return False
    try:
        return k32.WaitForSingleObject(h, 0) == 258  # WAIT_TIMEOUT — ще працює
    finally:
        k32.CloseHandle(h)


class Watcher:
    """Процес-ловець: вартовий, чорна скринька, розбір фризів, серцебиття. run() — до файла stop або смерті програми."""

    def __init__(self, deep: bool = False, parent: int = 0, folder: str = DIR, clock=None, warmup: float = WARMUP,
                 settle: float = SETTLE):
        self.folder = folder
        self.warmup, self.settle = warmup, settle
        self.list_path = os.path.join(folder, "freezes.json")
        self.status_path = os.path.join(folder, "status.json")
        self.stop_path = os.path.join(folder, "stop")
        self.parent = parent
        self.clock = clock or unbiased_clock()
        self.box: deque = deque(maxlen=BOX_SECONDS)
        self.pending: list = []
        self.lock = threading.Lock()
        self.quit = threading.Event()
        self.tpm: dict = {}
        self.deep = DeepTrace(folder) if deep and wpr_path() else None
        self.started = int(time.time())
        self.caught = 0

    # потоки
    def _watch(self) -> None:
        _boost_thread()
        dog = Watchdog(self.clock, warmup=self.warmup)
        while not self.quit.is_set():
            late = dog.step()
            if late is None:
                continue
            end_t, end_wall = dog.last, time.time()
            app = ""
            try:
                import monitor as M
                app = M.foreground_process()
            except Exception:  # noqa: BLE001
                pass
            with self.lock:
                self.pending.append(dict(start_t=end_t - late, end_t=end_t, start=end_wall - late, dur=late,
                                         seen=time.time(), app=app, etl=None))

    def _sample(self) -> None:
        try:
            import monitor as M
            q = M.Pdh(BOX_SINGLE, BOX_ARRAY)
            procs = M.ProcSampler()
        except Exception:  # noqa: BLE001 — без лічильників ловець однаково ловить і читає журнал
            return
        n, top = 0, None
        while not self.quit.wait(SAMPLE_EVERY):
            raw = q.collect()
            n += 1
            if n % 2 == 0:
                try:
                    shares = procs.sample()
                    best = max(((nm, sh) for nm, sh in shares.values() if nm.lower() not in M.IGNORE_PROCS),
                               key=lambda x: x[1], default=None)
                    top = best
                except Exception:  # noqa: BLE001
                    top = None
            if raw:
                s = box_sample(raw, self.clock(), time.time(), top)
                with self.lock:
                    self.box.append(s)
        q.close()

    # розбір
    def _analyze(self, fr: dict) -> None:
        with self.lock:
            samples = list(self.box)
        dr = during(samples, fr["start_t"], fr["end_t"])
        events = read_events(fr["start"] - EV_BEFORE, fr["start"] + fr["dur"] + EV_AFTER)
        if is_sleep(events):
            return
        cat, ev = classify(fr["dur"], dr, events, self.tpm, fr.get("app") or "")
        if fr.get("etl"):
            ev.append(("etl", {}))
        append(record(fr["start"], fr["dur"], cat, ev, dr, events, fr.get("app") or "", fr.get("etl") or ""),
               self.list_path)
        self.caught += 1

    def _save_etl(self, fr: dict) -> None:
        name = time.strftime("freeze-%Y%m%d-%H%M%S.etl", time.localtime(fr["start"]))
        path = os.path.join(self.folder, name)
        fr["etl"] = path if self.deep.save(path) else ""
        prune_etl(self.folder)
        self.deep.start()

    def _beat(self, stopped: bool = False) -> None:
        _write_json(self.status_path, dict(pid=os.getpid(), started=self.started, beat=int(time.time()),
                                           version=E.VERSION, tpm=self.tpm, caught=self.caught, stopped=stopped,
                                           wpr=bool(wpr_path()),
                                           deep=dict(on=bool(self.deep and self.deep.on),
                                                     error=self.deep.error if self.deep else "")))

    def run(self) -> int:
        try:
            self.tpm = tpm_info()
        except Exception:  # noqa: BLE001
            self.tpm = {}
        threading.Thread(target=self._sample, name="freeze-box", daemon=True).start()
        threading.Thread(target=self._watch, name="freeze-watch", daemon=True).start()
        if self.deep:
            self.deep.start()
        last_beat = 0.0
        try:
            while not self.quit.is_set():
                time.sleep(0.5)
                if os.path.exists(self.stop_path) or not _alive(self.parent):
                    break
                now = time.time()
                if now - last_beat >= BEAT:
                    self._beat()
                    last_beat = now
                with self.lock:
                    queue = list(self.pending)
                for fr in queue:
                    if self.deep and fr["etl"] is None and now - fr["seen"] >= ETL_AFTER:
                        self._save_etl(fr)
                    if now - fr["seen"] >= self.settle and (fr["etl"] is not None or not self.deep):
                        with self.lock:
                            self.pending.remove(fr)
                        try:
                            self._analyze(fr)
                        except Exception:  # noqa: BLE001 — один невдалий розбір не зупиняє ловця
                            pass
        finally:
            self.quit.set()
            if self.deep:
                self.deep.cancel()
            self._beat(stopped=True)
            try:
                os.remove(self.stop_path)
            except OSError:
                pass
        return 0


def watch_main(argv) -> int:
    """Точка входу процесу-ловця: OptimaX.exe --freeze-watch --parent=<pid> [--deep=1]."""
    a = _args(argv)
    os.makedirs(DIR, exist_ok=True)
    if not _single_instance():
        return 0
    try:
        os.remove(STOP_PATH)
    except OSError:
        pass
    _boost_process()
    return Watcher(deep=a.get("deep") == "1", parent=int(a.get("parent") or 0)).run()


# ───────────────────────── керування з програми ─────────────────────────
def self_command() -> list:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = sys.executable
    if E.IS_WIN:
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        exe = pyw if os.path.exists(pyw) else exe
    return [exe, os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimizer.py")]


def _cfg() -> dict:
    import features as F
    c = F.CFG["freeze"]
    return dict(c) if isinstance(c, dict) else {}


def _save_cfg(**kw) -> None:
    import features as F
    F.CFG["freeze"] = dict(_cfg(), **kw)


class Catcher:
    """Процес-ловець із боку програми: start / stop, стан. Поза Windows (демо) — лише перемикач."""

    def __init__(self):
        self.proc = None
        self.demo_on = False
        self.started = 0.0  # коли запущено цей ловець: status.json старіший — від попереднього запуску

    @property
    def running(self) -> bool:
        if not E.IS_WIN:
            return self.demo_on
        return self.proc is not None and self.proc.poll() is None

    def start(self, log=lambda *_: None, deep: bool = None) -> dict:
        deep = bool(_cfg().get("deep")) if deep is None else bool(deep)
        _save_cfg(enabled=True, deep=deep)
        if self.running:
            self.stop(log, remember=False)
        self.started = time.time()
        if not E.IS_WIN:
            self.demo_on = True
            log("  [demo] freeze catcher on")
            return {"ok": 1}
        try:
            os.makedirs(DIR, exist_ok=True)
            try:
                os.remove(STOP_PATH)
            except OSError:
                pass
            cmd = self_command() + ["--freeze-watch", f"--parent={os.getpid()}"] + (["--deep=1"] if deep else []) + \
                (["--dry-run"] if E.DRY_RUN else [])
            here = None if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
            self.proc = subprocess.Popen(cmd, cwd=here, creationflags=E.CREATE_NO_WINDOW,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        except OSError as e:
            return {"error": str(e)[:200]}
        log(f"  freeze catcher: pid {self.proc.pid}{' + WPR' if deep else ''}")
        return {"ok": 1, "pid": self.proc.pid}

    def stop(self, log=lambda *_: None, remember: bool = True) -> dict:
        if remember:
            _save_cfg(enabled=False)
        if not E.IS_WIN:
            self.demo_on = False
            return {"ok": 1}
        p, self.proc = self.proc, None
        if p is None or p.poll() is not None:
            return {"ok": 1}
        try:
            os.makedirs(DIR, exist_ok=True)
            open(STOP_PATH, "w").close()  # ловець сам зупинить WPR і допише статус
        except OSError:
            pass
        try:
            p.wait(8)
        except subprocess.TimeoutExpired:
            E.kill_tree(p)
            if _cfg().get("deep") and wpr_path():
                E.run([wpr_path(), "-cancel"], 30, ro=True)  # ловець не встиг — кільцевий запис не лишаємо
        log("  freeze catcher stopped")
        return {"ok": 1}


CATCHER = Catcher()
