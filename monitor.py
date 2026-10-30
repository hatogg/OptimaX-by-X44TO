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


def foreground_pid() -> int:
    if not E.IS_WIN:
        return 0
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    pid = ctypes.c_ulong(0)
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def foreground_process() -> str:
    """Ім'я exe активного вікна."""
    if not E.IS_WIN:
        return ""
    path = E.process_path(foreground_pid()) or ""
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
    # по процесу: на якій карті малює гра і скільки пам'яті займає (лише драйвери WDDM 2.0+)
    "eng": r"\GPU Engine(*)\Utilization Percentage",
    "pmem": r"\GPU Process Memory(*)\Dedicated Usage",
    "pshared": r"\GPU Process Memory(*)\Shared Usage",
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
        "mining": dict(cpu=71, core_max=98, gpu=93, avail_mb=5200, pages_in=25, disk=8, temp=66, passive=100,
                       limit=100, vram_used=4.8, gpu_t=69, bg=("steamwebhelper.exe", 0.05)),
    }.get(dev, {})
    j = lambda v, k=0.08: max(0.0, v * (1 + rnd.uniform(-k, k)))  # noqa: E731
    return dict(cpu=min(100.0, j(base["cpu"])), core_max=min(100.0, j(base["core_max"], 0.03)),
                gpu=min(100.0, j(base["gpu"], 0.05)), avail_mb=j(base["avail_mb"], 0.04),
                pages_in=j(base["pages_in"], 0.4), disk=min(100.0, j(base["disk"], 0.2)), temp=j(base["temp"], 0.02),
                passive=min(100.0, j(base["passive"], 0.02)), limit=min(100.0, j(base["limit"], 0.02)),
                vram_used=j(base["vram_used"], 0.02), gpu_t=j(base["gpu_t"], 0.02) if base["gpu_t"] else None,
                fg="cs2.exe", bg={base["bg"][0]: j(base["bg"][1], 0.2)})


def _nvml():
    if not E.IS_WIN:
        return None
    try:
        import gpubench as GB
        nv = GB.Nvml()
        return nv if nv.ok() else None
    except Exception:
        return None


def _demo_extra(hw: dict, seconds: int) -> dict:
    """Поза Windows: заміри майнінгової карти (NVML, кадри, на якій карті малює гра) для демо «mining»."""
    if E.DEMO != "mining":
        return {}
    import fpstest as FT
    import gpuinfo as GI
    rnd = random.Random(77)
    nv = [dict(util=90 + rnd.randint(-5, 5), pcie_gen=1, pcie_width=4, pcie_max_gen=1, pcie_max_width=4,
               pcie_tx=rnd.randint(380, 520) * 1024, pcie_rx=rnd.randint(260, 340) * 1024, vram_used=5600 + i * 8,
               vram_total=6144, temp=69, power=112.0) for i in range(seconds)]
    ft = FT._demo_frametimes(seconds)
    render = dict(verdict="mining", mining_3d=91.0, other_3d=0.0, copy=22.0, vram_mb=5200, shared_mb=640,
                  path=dict(GI.DEMO_PATH))
    render["path_text"] = GI.describe_path(render["path"])
    return dict(nvml=nv, frametimes=ft, render=render, frames_offset=0.5)


def lag_diagnosis(hw: dict, seconds: int, log, progress, gpu_temp=None, game: str = None) -> dict:
    """Збирає показники раз на секунду, поки ви граєте, і пояснює, що саме гальмує. Якщо є PresentMon — паралельно
    записує кадри всіх процесів (потім лишаються кадри гри): фризи зіставляються з тим, що відбувалося тієї секунди.
    На ПК з майнінговою картою ще й з'ясовує, на якій карті насправді малює гра (gpuinfo), і стан лінії PCIe (NVML)."""
    import gpuinfo as GI
    hw = hw or {}
    q = Pdh(DIAG_SINGLE, DIAG_ARRAY) if E.IS_WIN else None
    sampler = ProcSampler() if E.IS_WIN else None
    if sampler:
        sampler.sample()
    nv = _nvml()
    frames = None
    try:
        import fpstest as FT
        if E.IS_WIN and FT.find_presentmon():
            frames = FT.start_capture_all(seconds)
    except Exception as e:
        log(f"  PresentMon: {type(e).__name__}: {e}"[:200])
    t0 = time.time()
    samples, nv_samples = [], []
    paths: dict = {}  # exe -> що показали бібліотеки процесу
    fg_count = Counter()
    bg_share = defaultdict(float)
    prev_shared: dict = {}
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
            pid = foreground_pid()
            fg = foreground_process()
            s = dict(cpu=min(100.0, d.get("cpu", 0.0)), core_max=min(100.0, max(cores) if cores else 0.0),
                     gpu=min(100.0, sum((d.get("gpu3d") or {}).values())), avail_mb=d.get("avail_mb", 0.0),
                     pages_in=d.get("pages_in", 0.0), disk=max(0.0, 100 - d.get("disk_idle", 100.0)),
                     temp=max(zones) if zones else None, passive=min(passive) if passive else None,
                     limit=d.get("limit"), vram_used=max((d.get("vram") or {0: 0}).values()) / 2**30,
                     gpu_t=gpu_temp() if gpu_temp and i % 3 == 0 else None, fg=fg, bg={})
            if pid:
                s["eng"] = GI.engine_split(d.get("eng"), {pid})
                s["vram_p"] = GI.process_vram(d.get("pmem"), {pid})
                sh = GI.process_vram(d.get("pshared"), {pid})
                s["shared_p"] = sh
                # приріст спільної пам'яті за секунду (МБ): ресурси переїжджають з відеопам'яті в оперативну
                s["shared_d"] = max([(v - prev_shared.get(k, v)) / 2**20 for k, v in sh.items()] or [0.0])
                prev_shared = sh
                low = (fg or "").lower()
                if low and low not in IGNORE_PROCS and (i == 3 or i % 15 == 0) and len(paths) < 8:
                    try:
                        path = GI.render_path(GI.process_modules(pid))
                        if path.get("apis"):
                            paths[low] = path
                    except Exception:
                        pass
            if i % 2 == 1 and sampler:
                for _pid, (name, share) in sampler.sample().items():
                    s["bg"][name] = s["bg"].get(name, 0.0) + share
        if nv:
            try:
                nv_samples.append(nv.read())
            except Exception:
                pass
        samples.append(s)
        if s.get("fg"):
            fg_count[s["fg"].lower()] += 1
    if q:
        q.close()
    if nv:
        try:
            nv.close()
        except Exception:
            pass
    if progress:
        progress(seconds, seconds, tr("diag.analyzing"))
    game_exe = (game or "").lower() or next((n for n, _ in fg_count.most_common() if n not in IGNORE_PROCS), "")
    for s in samples:
        for name, share in (s.get("bg") or {}).items():
            if name.lower() != game_exe and name.lower() not in IGNORE_PROCS:
                bg_share[name] += share
    n_bg = max(1, len([s for s in samples if s.get("bg")]))
    extra = _demo_extra(hw, len(samples)) if not E.IS_WIN else {"nvml": nv_samples}
    if E.IS_WIN:
        if frames:
            try:
                by_app = FT.finish_capture_all(frames)
                extra["frametimes"] = by_app.get(game_exe) or []
                extra["frames_offset"] = frames.get("t0", t0) - t0
            except Exception as e:
                log(f"  PresentMon: {type(e).__name__}: {e}"[:200])
        if hw.get("mining_gpu") and game_exe:
            try:
                luid = GI.summary(GI.probe()).get("luid") or ""
                mine = [dict(fg=True, eng=s.get("eng") or {}, vram=s.get("vram_p") or {}, shared=s.get("shared_p") or {})
                        for s in samples if (s.get("fg") or "").lower() == game_exe and "eng" in s]
                rd = GI.verdict(mine, luid) if mine and luid else {"verdict": "none"}
                path = paths.get(game_exe) or {}
                if path:
                    rd["path"], rd["path_text"] = path, GI.describe_path(path)
                    pv = GI.path_verdict(path)
                    if pv in ("igpu", "warp") or (pv == "mining" and rd.get("verdict") in ("igpu", "none")):
                        rd["verdict"] = pv
                extra["render"] = rd
            except Exception as e:
                log(f"  GPU: {type(e).__name__}: {e}"[:200])
    res = summarize(samples, hw, game_exe, {k: v / n_bg for k, v in bg_share.items()}, extra=extra)
    log(tr("diag.done_log", n=len(samples), game=game_exe or "—"))
    return res


def _avg(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else None


# ───────────────────────── що саме обмежує продуктивність ─────────────────────────
LIMITS = ("thermal", "ram", "disk", "gpu", "cpu", "power", "none")


def classify(s: dict, total_mb: float) -> str:
    """Що обмежувало FPS у цю секунду. Порядок важливий: перегрів і нестача пам'яті гальмують усе інше,
    тож їх перевіряємо першими; відеокарта на 92%+ — це «впираємося у відеокарту», навіть якщо одне ядро зайняте."""
    passive, temp, gpu_t = s.get("passive"), s.get("temp"), s.get("gpu_t")
    if (passive is not None and passive < 95) or (temp or 0) >= 90 or (gpu_t or 0) >= 87:
        return "thermal"
    avail = s.get("avail_mb")
    if (avail is not None and avail < 0.06 * total_mb) or (s.get("pages_in") or 0) > 400:
        return "ram"
    if (s.get("disk") or 0) >= 90:
        return "disk"
    if (s.get("gpu") or 0) >= 92:
        return "gpu"
    if (s.get("core_max") or 0) >= 95 or (s.get("cpu") or 0) >= 90:
        return "cpu"
    if s.get("limit") is not None and s["limit"] < 90:
        return "power"
    return "none"


def bottleneck(samples: list, hw: dict) -> dict:
    """Головне обмеження за весь замір: частка часу, коли кожен ресурс був «вузьким місцем».
    -> {main, share, shares: {ресурс: %}, second}. main = none — залізо не завантажене повністю (FPS обмежує
    ліміт кадрів, V-Sync чи сама гра); mixed — жоден ресурс не домінує."""
    total_mb = (hw.get("ram_gb") or 16) * 1024
    counts = Counter(classify(s, total_mb) for s in samples)
    n = max(1, len(samples))
    shares = {k: round(100 * counts.get(k, 0) / n) for k in LIMITS if counts.get(k)}
    ranked = sorted(((k, c) for k, c in counts.items() if k != "none"), key=lambda kc: -kc[1])
    main, share = "none", shares.get("none", 0)
    if ranked and ranked[0][1] / n >= 0.3:
        main, share = ranked[0][0], round(100 * ranked[0][1] / n)
    elif counts.get("none", 0) / n < 0.5:
        main, share = "mixed", round(100 * (ranked[0][1] if ranked else 0) / n)
    second = ranked[1][0] if len(ranked) > 1 and ranked[1][1] / n >= 0.2 and main == ranked[0][0] else None
    return {"main": main, "share": share, "shares": shares, "second": second}


def summarize(samples: list, hw: dict, game_exe: str, bg: dict, extra: dict = None) -> dict:
    """Перетворює заміри на висновки простими словами. extra — те, що вдалося виміряти понад лічильники Windows:
    nvml (секундні показники карти NVIDIA), frametimes (кадри гри з PresentMon), render (на якій карті малює гра)."""
    import gpudiag as GD
    import fpstest as FT
    extra = extra or {}
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
    # на якій карті насправді малює гра (майнінгова карта без виходів)
    rd = extra.get("render") or {}
    mining_gpu = hw.get("mining_gpu") or ""
    if mining_gpu and rd.get("verdict") in ("igpu", "warp"):
        apis = set((rd.get("path") or {}).get("apis") or [])
        key = "render_warp" if rd["verdict"] == "warp" else "render_igpu_dx9" if "dx9" in apis else \
            "render_igpu_gl" if "gl" in apis else "render_igpu"
        add(key, "bad", ("mining", game_exe), gpu=mining_gpu, game=game_exe or "?", path=rd.get("path_text") or "?")
    elif mining_gpu and rd.get("verdict") == "mining":
        add("render_ok", "info", None, gpu=mining_gpu, path=rd.get("path_text") or "—",
            d3=f"{rd.get('mining_3d', 0):.0f}")
    # кадри: фризи та їхні причини
    fstats = FT.stats(extra.get("frametimes") or []) if extra.get("frametimes") else {}
    causes = GD.spike_causes(GD.spike_times(extra.get("frametimes") or []), samples, extra.get("frames_offset", 0.0)) \
        if fstats else {}
    for x in GD.stutter_findings(fstats, causes):
        f.append(x)
    # відеопам'ять, лінія PCIe і драйвер карти NVIDIA
    nvs = extra.get("nvml") or []
    for x in GD.memory_findings(nvs, rd, hw, av["avail_mb"]):
        f.append(x)
    pcie = GD.pcie_eval(nvs)
    for x in GD.pcie_findings(pcie, hw, fstats.get("avg") or 0):
        f.append(x)
    if mining_gpu:
        try:
            import features as F
            for x in GD.driver_findings(hw, F.CFG["gpu_probe"] or {}):
                f.append(x)
        except Exception:
            pass
    if not [x for x in f if x["key"] != "render_ok"]:
        add("none", "ok")
    order = {"bad": 0, "warn": 1, "info": 2, "ok": 3}
    f.sort(key=lambda x: order[x["level"]])
    stats = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in av.items()}
    stats.update(temp_max=mx["temp"], gpu_t_max=mx["gpu_t"], vram_total=vram_total, ram_total=total_mb / 1024,
                 top_bg=sorted(((n, round(v * 100, 1)) for n, v in bg.items() if v >= 0.01),
                               key=lambda x: -x[1])[:5])
    nv_last = nvs[-1] if nvs else {}
    stats.update(gpu_power=nv_last.get("power"), gpu_clock=nv_last.get("clock"),
                 nv_vram=nv_last.get("vram_used"), nv_vram_total=nv_last.get("vram_total"))
    frames = {k: fstats.get(k) for k in ("avg", "low1", "low01", "stutters", "stutters_pm", "smooth", "series")} \
        if fstats else {}
    if frames:
        frames["causes"] = causes
    return {"findings": f, "stats": stats, "game": game_exe, "n": len(samples), "ts": int(time.time()),
            "bottleneck": bottleneck(samples, hw), "frames": frames, "pcie": pcie,
            "render": {k: rd.get(k) for k in ("verdict", "path_text", "mining_3d", "vram_mb", "shared_mb")} if rd else {}}


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
