"""
OptimaX — живий моніторинг: лічильники Windows (PDH), діагностика «Чому лагає?», балансувальник
фонових процесів під час гри та прив'язка ігор до потрібних ядер процесора.

Лічильники додаються англійськими назвами (PdhAddEnglishCounterW), тому працюють у будь-якій мові Windows.
"""
from __future__ import annotations

import ctypes
import random
import time
from collections import Counter, defaultdict

import engine as E
from i18n import tr

PDH_FMT_DOUBLE = 0x00000200
PDH_FMT_NOCAP100 = 0x00008000
PDH_MORE_DATA = 0x800007D2


class _FMT(ctypes.Structure):
    _fields_ = [("CStatus", ctypes.c_ulong), ("_pad", ctypes.c_ulong), ("value", ctypes.c_double)]


class _ITEM(ctypes.Structure):
    _fields_ = [("name", ctypes.c_wchar_p), ("fmt", _FMT)]


class Pdh:
    """Запит лічильників продуктивності. single — одне значення, array — значення для всіх екземплярів (*)."""

    def __init__(self, single: dict = None, array: dict = None):
        self.ok = False
        self.single, self.array = {}, {}
        if not E.IS_WIN:
            return
        self.pdh = ctypes.windll.pdh
        self.q = ctypes.c_void_p()
        if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.q)) != 0:
            return
        for store, src in ((self.single, single or {}), (self.array, array or {})):
            for key, path in src.items():
                h = ctypes.c_void_p()
                if self.pdh.PdhAddEnglishCounterW(self.q, path, None, ctypes.byref(h)) == 0:
                    store[key] = h
        self.ok = True
        self.pdh.PdhCollectQueryData(self.q)  # перший збір — база для лічильників-швидкостей

    def collect(self) -> dict:
        res = {}
        if not self.ok or self.pdh.PdhCollectQueryData(self.q) != 0:
            return res
        flags = PDH_FMT_DOUBLE | PDH_FMT_NOCAP100
        for key, h in self.single.items():
            v = _FMT()
            if self.pdh.PdhGetFormattedCounterValue(h, flags, None, ctypes.byref(v)) == 0 and v.CStatus in (0, 1):
                res[key] = v.value
        for key, h in self.array.items():
            size, count = ctypes.c_ulong(0), ctypes.c_ulong(0)
            rc = self.pdh.PdhGetFormattedCounterArrayW(h, flags, ctypes.byref(size), ctypes.byref(count), None)
            if (rc & 0xFFFFFFFF) != PDH_MORE_DATA or not size.value:
                continue
            buf = ctypes.create_string_buffer(size.value)
            if self.pdh.PdhGetFormattedCounterArrayW(h, flags, ctypes.byref(size), ctypes.byref(count), buf) != 0:
                continue
            items = ctypes.cast(buf, ctypes.POINTER(_ITEM))
            res[key] = {items[i].name: items[i].fmt.value for i in range(count.value) if items[i].fmt.CStatus in (0, 1)}
        return res

    def close(self) -> None:
        if self.ok:
            self.pdh.PdhCloseQuery(self.q)
            self.ok = False


def _zone_c(vals) -> list:
    """Температури теплових зон ACPI у °C (Windows віддає кельвіни)."""
    out = []
    for v in (vals or {}).values():
        c = v - 273.15 if v > 200 else v
        if 15 < c < 120:
            out.append(c)
    return out


def quick_thermal() -> dict:
    """Короткий замір у простої: найгарячіша теплова зона, пасивне обмеження та ліміт продуктивності."""
    q = Pdh({"perf": r"\Processor Information(_Total)\% Performance Limit"},
            {"temp": r"\Thermal Zone Information(*)\Temperature", "passive": r"\Thermal Zone Information(*)\% Passive Limit"})
    if not q.ok:
        return {}
    time.sleep(1.0)
    d = q.collect()
    q.close()
    zones = _zone_c(d.get("temp"))
    passive = [v for v in (d.get("passive") or {}).values() if 0 < v <= 100]
    return dict(zone=round(max(zones)) if zones else None, passive=round(min(passive)) if passive else None,
                perf=round(d["perf"]) if "perf" in d else None)


# ───────────────────────── процеси ─────────────────────────
PQL = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
PSET = 0x0200  # PROCESS_SET_INFORMATION


class _FT(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]


def _proc_time(pid: int):
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
    h = k32.OpenProcess(PQL, False, pid)
    if not h:
        return None
    try:
        a, b, kt, ut = _FT(), _FT(), _FT(), _FT()
        if k32.GetProcessTimes(h, ctypes.byref(a), ctypes.byref(b), ctypes.byref(kt), ctypes.byref(ut)):
            return ((kt.hi << 32) | kt.lo) + ((ut.hi << 32) | ut.lo)
    finally:
        k32.CloseHandle(h)
    return None


def cpu_count() -> int:
    import os
    return os.cpu_count() or 1


class ProcSampler:
    """Частка процесорного часу кожного процесу між двома викликами sample() (0…1 від усього процесора)."""

    def __init__(self):
        self.prev, self.t = {}, None

    def sample(self) -> dict:
        now = time.perf_counter()
        cur = {}
        for pid, name in E.processes():
            if pid in (0, 4):
                continue
            t = _proc_time(pid) if E.IS_WIN else None
            if t is not None:
                cur[pid] = (name, t)
        res = {}
        if self.t is not None:
            span = (now - self.t) * 1e7 * cpu_count()
            for pid, (name, t) in cur.items():
                old = self.prev.get(pid)
                if old and old[0] == name and span > 0:
                    res[pid] = (name, max(0.0, (t - old[1]) / span))
        self.prev, self.t = cur, now
        return res


def foreground_process() -> str:
    """Ім'я exe активного вікна."""
    if not E.IS_WIN:
        return ""
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    pid = ctypes.c_ulong(0)
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    path = E.process_path(pid.value) or ""
    return path.replace("/", "\\").rsplit("\\", 1)[-1]


IGNORE_PROCS = {"idle", "system", "registry", "secure system", "memory compression", "optimax.exe", "python.exe",
                "pythonw.exe", "dwm.exe", "csrss.exe", "audiodg.exe", "explorer.exe", "searchhost.exe",
                "shellexperiencehost.exe", "startmenuexperiencehost.exe", "textinputhost.exe", "applicationframehost.exe"}

# ───────────────────────── «Чому лагає?» ─────────────────────────
DIAG_SINGLE = {
    "cpu": r"\Processor Information(_Total)\% Processor Utility",
    "perf": r"\Processor Information(_Total)\% Processor Performance",
    "limit": r"\Processor Information(_Total)\% Performance Limit",
    "avail_mb": r"\Memory\Available MBytes",
    "pages_in": r"\Memory\Pages Input/sec",
    "disk_idle": r"\PhysicalDisk(_Total)\% Idle Time",
}
DIAG_ARRAY = {
    "cores": r"\Processor Information(*)\% Processor Utility",
    "gpu3d": r"\GPU Engine(*engtype_3D)\Utilization Percentage",
    "vram": r"\GPU Adapter Memory(*)\Dedicated Usage",
    "temp": r"\Thermal Zone Information(*)\Temperature",
    "passive": r"\Thermal Zone Information(*)\% Passive Limit",
}


def _demo_sample(hw: dict, i: int) -> dict:
    rnd = random.Random(1000 + i)
    dev = E.DEMO
    base = {
        "gaming": dict(cpu=63, core_max=97, gpu=72, avail_mb=9800, pages_in=12, disk=9, temp=68, passive=100,
                       limit=100, vram_used=9.1, gpu_t=71, bg=("chrome.exe", 0.13)),
        "laptop": dict(cpu=55, core_max=82, gpu=88, avail_mb=4200, pages_in=40, disk=14, temp=94, passive=78,
                       limit=80, vram_used=5.6, gpu_t=86, bg=("MsMpEng.exe", 0.06)),
        "old": dict(cpu=96, core_max=100, gpu=70, avail_mb=260, pages_in=650, disk=97, temp=81, passive=100,
                    limit=100, vram_used=0.0, gpu_t=None, bg=("MsMpEng.exe", 0.21)),
        "x3d": dict(cpu=38, core_max=71, gpu=98, avail_mb=21000, pages_in=4, disk=5, temp=62, passive=100,
                    limit=100, vram_used=15.2, gpu_t=66, bg=("Discord.exe", 0.02)),
        "xeon": dict(cpu=41, core_max=99, gpu=58, avail_mb=6100, pages_in=30, disk=11, temp=55, passive=100,
                     limit=100, vram_used=5.9, gpu_t=74, bg=("steamwebhelper.exe", 0.04)),
    }.get(dev, {})
    j = lambda v, k=0.08: max(0.0, v * (1 + rnd.uniform(-k, k)))  # noqa: E731
    return dict(cpu=min(100.0, j(base["cpu"])), core_max=min(100.0, j(base["core_max"], 0.03)),
                gpu=min(100.0, j(base["gpu"], 0.05)), avail_mb=j(base["avail_mb"], 0.04),
                pages_in=j(base["pages_in"], 0.4), disk=min(100.0, j(base["disk"], 0.2)), temp=j(base["temp"], 0.02),
                passive=min(100.0, j(base["passive"], 0.02)), limit=min(100.0, j(base["limit"], 0.02)),
                vram_used=j(base["vram_used"], 0.02), gpu_t=j(base["gpu_t"], 0.02) if base["gpu_t"] else None,
                fg="cs2.exe", bg={base["bg"][0]: j(base["bg"][1], 0.2)})


def lag_diagnosis(hw: dict, seconds: int, log, progress, gpu_temp=None, game: str = None) -> dict:
    """Збирає показники раз на секунду, поки ви граєте, і пояснює, що саме гальмує."""
    hw = hw or {}
    q = Pdh(DIAG_SINGLE, DIAG_ARRAY) if E.IS_WIN else None
    sampler = ProcSampler() if E.IS_WIN else None
    if sampler:
        sampler.sample()
    samples = []
    fg_count = Counter()
    bg_share = defaultdict(float)
    for i in range(seconds):
        if E.CANCEL.is_set():
            break
        if progress:
            progress(i, seconds, tr("diag.collecting", s=seconds - i))
        if q is None:
            s = _demo_sample(hw, i)
            if not E.DRY_RUN:
                time.sleep(1.0)
            else:
                time.sleep(0.01)
        else:
            time.sleep(1.0)
            d = q.collect()
            cores = [v for k, v in (d.get("cores") or {}).items() if "_Total" not in k]
            zones = _zone_c(d.get("temp"))
            passive = [v for v in (d.get("passive") or {}).values() if 0 < v <= 100]
            s = dict(cpu=min(100.0, d.get("cpu", 0.0)), core_max=min(100.0, max(cores) if cores else 0.0),
                     gpu=min(100.0, sum((d.get("gpu3d") or {}).values())), avail_mb=d.get("avail_mb", 0.0),
                     pages_in=d.get("pages_in", 0.0), disk=max(0.0, 100 - d.get("disk_idle", 100.0)),
                     temp=max(zones) if zones else None, passive=min(passive) if passive else None,
                     limit=d.get("limit"), vram_used=max((d.get("vram") or {0: 0}).values()) / 2**30,
                     gpu_t=gpu_temp() if gpu_temp and i % 3 == 0 else None, fg=foreground_process(), bg={})
            if i % 2 == 1 and sampler:
                for _pid, (name, share) in sampler.sample().items():
                    s["bg"][name] = s["bg"].get(name, 0.0) + share
        samples.append(s)
        if s.get("fg"):
            fg_count[s["fg"].lower()] += 1
    if q:
        q.close()
    if progress:
        progress(seconds, seconds, tr("diag.analyzing"))
    game_exe = (game or "").lower() or next((n for n, _ in fg_count.most_common() if n not in IGNORE_PROCS), "")
    for s in samples:
        for name, share in (s.get("bg") or {}).items():
            if name.lower() != game_exe and name.lower() not in IGNORE_PROCS:
                bg_share[name] += share
    n_bg = max(1, len([s for s in samples if s.get("bg")]))
    res = summarize(samples, hw, game_exe, {k: v / n_bg for k, v in bg_share.items()})
    log(tr("diag.done_log", n=len(samples), game=game_exe or "—"))
    return res


def _avg(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else None


def summarize(samples: list, hw: dict, game_exe: str, bg: dict) -> dict:
    """Перетворює заміри на висновки простими словами."""
    if not samples:
        return {"findings": [], "stats": {}, "game": game_exe, "n": 0}
    av = {k: _avg([s.get(k) for s in samples]) for k in ("cpu", "core_max", "gpu", "avail_mb", "pages_in", "disk",
                                                          "temp", "passive", "limit", "vram_used", "gpu_t")}
    mx = {k: max([s.get(k) for s in samples if isinstance(s.get(k), (int, float))] or [0])
          for k in ("temp", "gpu_t", "disk", "vram_used")}
    total_mb = (hw.get("ram_gb") or 16) * 1024
    vram_total = max([vr for n, vr, _ in hw.get("gpus", []) if vr >= 1] or [0])
    f = []

    def add(key, level, fix=None, **kw):
        f.append(dict(key=key, level=level, fix=fix, kw=kw))

    hot_cpu = (av["passive"] is not None and av["passive"] < 95) or (mx["temp"] or 0) >= 90
    if hot_cpu:
        add("thermal", "bad", ("hint", "thermal"), t=round(mx["temp"] or 0), pct=round(av["passive"] or 100))
    if (mx["gpu_t"] or 0) >= 87:
        add("gpu_hot", "bad", ("hint", "thermal"), t=round(mx["gpu_t"]))
    if not hot_cpu and av["limit"] is not None and av["limit"] < 90:
        fix = ("tweak", "laptop_ac_max") if hw.get("laptop") else ("tweak", "ultimate_power")
        add("power_limit", "warn", fix, pct=round(av["limit"]))
    if av["avail_mb"] is not None and (av["avail_mb"] < 0.08 * total_mb or (av["pages_in"] or 0) > 300):
        add("ram", "bad", ("page", "games"), free=f"{av['avail_mb'] / 1024:.1f}", total=f"{total_mb / 1024:.0f}")
    if vram_total and av["vram_used"] and av["vram_used"] >= 0.93 * vram_total:
        add("vram", "warn", None, used=f"{av['vram_used']:.1f}", total=f"{vram_total:.0f}")
    hog = max(bg.items(), key=lambda kv: kv[1]) if bg else None
    if hog and hog[1] >= 0.10:
        add("bg_hog", "warn", ("booster", "balance"), name=hog[0], pct=round(hog[1] * 100))
    if (av["disk"] or 0) >= 85:
        add("disk", "bad" if hw.get("hdd") else "warn", ("page", "cleanup"), pct=round(av["disk"]))
    gpu, cpu, core = av["gpu"] or 0, av["cpu"] or 0, av["core_max"] or 0
    if gpu < 80 and (cpu >= 85 or core >= 95):
        add("cpu_bound", "warn", ("page", "games"), gpu=round(gpu), cpu=round(cpu), core=round(core))
    elif gpu >= 95:
        add("gpu_bound", "info", None, gpu=round(gpu))
    if not f:
        add("none", "ok")
    order = {"bad": 0, "warn": 1, "info": 2, "ok": 3}
    f.sort(key=lambda x: order[x["level"]])
    stats = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in av.items()}
    stats.update(temp_max=mx["temp"], gpu_t_max=mx["gpu_t"], vram_total=vram_total, ram_total=total_mb / 1024,
                 top_bg=sorted(((n, round(v * 100, 1)) for n, v in bg.items() if v >= 0.01),
                               key=lambda x: -x[1])[:5])
    return {"findings": f, "stats": stats, "game": game_exe, "n": len(samples), "ts": int(time.time())}


# ───────────────────────── балансувальник фону ─────────────────────────
BELOW_NORMAL = 0x4000
PROTECTED = IGNORE_PROCS | {"smss.exe", "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe", "svchost.exe",
                            "fontdrvhost.exe", "sihost.exe", "ctfmon.exe", "obs64.exe", "obs32.exe",
                            "streamlabs obs.exe", "nvcontainer.exe", "nvidia share.exe", "radeonsoftware.exe",
                            "amdrsserv.exe", "vgc.exe", "vgtray.exe", "easyanticheat.exe", "easyanticheat_eos.exe",
                            "beservice.exe", "faceit.exe", "faceitclient.exe", "discord.exe", "rtsshooksloader64.exe",
                            "msiafterburner.exe"}


class Balancer:
    """Як ProBalance: на час гри знижує пріоритет фонових процесів, що раптово навантажують процесор."""
    HIGH, LOW = 0.15, 0.04

    def __init__(self):
        self.sampler = ProcSampler()
        self.lowered = {}  # pid -> [ім'я, початковий клас, тихих тиків]
        self._demo = 0

    def tick(self, games: set, log) -> None:
        if not E.IS_WIN:
            self._demo += 1
            if self._demo == 1:
                self.lowered[4242] = ["chrome.exe", 0x20, 0]
                log(tr("bal.lowered", name="chrome.exe", pct=18))
            return
        shares = self.sampler.sample()
        for pid, (name, share) in shares.items():
            low = name.lower()
            if pid in self.lowered:
                rec = self.lowered[pid]
                rec[2] = rec[2] + 1 if share < self.LOW else 0
                if rec[2] >= 3:
                    self._restore(pid, log)
                continue
            if share >= self.HIGH and low not in PROTECTED and low not in games:
                old = _get_priority(pid)
                if old and old not in (BELOW_NORMAL, 0x40) and _set_priority(pid, BELOW_NORMAL):
                    self.lowered[pid] = [name, old, 0]
                    log(tr("bal.lowered", name=name, pct=round(share * 100)))
        for pid in [p for p in self.lowered if p not in shares]:
            self.lowered.pop(pid, None)

    def _restore(self, pid: int, log) -> None:
        name, old, _ = self.lowered.pop(pid)
        if E.IS_WIN:
            _set_priority(pid, old)
        log(tr("bal.restored", name=name))

    def restore_all(self, log) -> None:
        for pid in list(self.lowered):
            self._restore(pid, log)


def _open(pid: int, access: int):
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    return k32.OpenProcess(access, False, pid)


def _get_priority(pid: int) -> int:
    k32 = ctypes.windll.kernel32
    h = _open(pid, PQL)
    if not h:
        return 0
    try:
        k32.GetPriorityClass.argtypes = [ctypes.c_void_p]
        return k32.GetPriorityClass(h)
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


def _set_priority(pid: int, cls: int) -> bool:
    if E.DRY_RUN:
        return True
    k32 = ctypes.windll.kernel32
    h = _open(pid, PSET | PQL)
    if not h:
        return False
    try:
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        return bool(k32.SetPriorityClass(h, cls))
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


# ───────────────────────── ядра для ігор ─────────────────────────
def core_mask(hw: dict):
    mode = (hw or {}).get("cores_mode")
    return mode, {"vcache": hw.get("vcache_mask"), "numa": hw.get("numa_mask"), "pcores": hw.get("p_mask")}.get(mode)


def mask_text(mask: int) -> str:
    bits = [i for i in range(64) if mask >> i & 1]
    if not bits:
        return "—"
    if bits == list(range(bits[0], bits[-1] + 1)):
        return f"{bits[0]}–{bits[-1]}"
    return ", ".join(map(str, bits[:12])) + ("…" if len(bits) > 12 else "")


def set_affinity(pid: int, mask: int) -> bool:
    if E.DRY_RUN or not E.IS_WIN:
        return True
    k32 = ctypes.windll.kernel32
    h = _open(pid, PSET | PQL)
    if not h:
        return False
    try:
        k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        return bool(k32.SetProcessAffinityMask(h, mask))
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


class GameCores:
    """Коли запускається гра з позначкою «Ядра», прив'язує її до найкращих ядер цього процесора."""

    def __init__(self):
        self.done = set()

    def tick(self, games: list, hw: dict, log) -> int:
        mode, mask = core_mask(hw)
        if not mask:
            return 0
        wanted = {g["path"].replace("/", "\\").rsplit("\\", 1)[-1].lower(): g for g in games if g.get("cores")}
        if not wanted:
            return 0
        n = 0
        alive = set()
        for pid, name in E.processes():
            low = name.lower()
            if low not in wanted:
                continue
            alive.add(pid)
            if pid in self.done:
                continue
            self.done.add(pid)
            if set_affinity(pid, mask):
                n += 1
                log(tr("cores.applied", game=name, mode=tr(f"cores.mode.{mode}"), cpus=mask_text(mask)))
            else:
                log(tr("cores.failed", game=name))
        self.done &= alive
        return n
