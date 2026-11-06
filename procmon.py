"""
OptimaX — Smart Background Process Monitor: які процеси забирали ресурси під час гри.

Поки працює гра з бібліотеки (library.Tracker) або під час ручного запису, раз на 2 секунди знімаємо по кожному процесу:
частку процесора, робочий набір пам'яті, швидкість читання й запису диска (GetProcessIoCounters), 3D-навантаження
відеокарти (лічильники «GPU Engine» за PID, лише WDDM 2.0+), а також мережу всієї системи (по процесах Windows без ETW
її не дає — так і пишемо). Після гри — підсумок: хто навантажував систему, скільки, чи були піки диска, чи збігалися
піки фону з падіннями FPS (якщо в цей час писалися кадри PresentMon) і хто з них може бути причиною фризів.

Чого модуль не робить ніколи: не називає процес шкідливим чи непотрібним за навантаженням, не завершує процеси сам.
Рекомендації — лише варіанти для людини: залишити, закрити вручну, вимкнути автозапуск, додати виняток (антивірус),
перевірити програму детальніше. Системні процеси Windows — лише «залишити» чи «виняток».
"""
from __future__ import annotations

import ctypes
import time

import engine as E
from i18n import tr

INTERVAL = 2.0
KEEP_SESSIONS = 20
MAX_SAMPLES = 3600  # 2 години по 2 секунди
HEAVY_AVG = 4.0       # % усього процесора в середньому
SPIKE_CPU = 20.0      # % усього процесора за вимір — пік
SPIKE_IO_MBS = 40.0   # МБ/с диска за вимір — пік
HEAVY_RAM_MB = 1500
CRITICAL = {"system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe",
            "svchost.exe", "dwm.exe", "fontdrvhost.exe", "msmpeng.exe", "audiodg.exe", "memory compression",
            "secure system", "conhost.exe", "sihost.exe", "ctfmon.exe", "spoolsv.exe", "wudfhost.exe",
            "searchindexer.exe", "nissrv.exe", "securityhealthservice.exe", "explorer.exe"}
ANTIVIRUS = {"msmpeng.exe", "nissrv.exe", "avp.exe", "avastsvc.exe", "ekrn.exe", "bdservicehost.exe", "mbamservice.exe"}
SKIP = {"idle", "system idle process", "optimax.exe", "python.exe", "pythonw.exe", "presentmon.exe"}
DEMO_BG = {"laptop": [("MsMpEng.exe", 9.0, 6.0, 410), ("OneDrive.exe", 3.5, 14.0, 220), ("chrome.exe", 4.2, 0.4, 1650)],
           "gaming": [("chrome.exe", 3.1, 0.2, 1900), ("Discord.exe", 1.6, 0.1, 420), ("steamwebhelper.exe", 1.1, 0.0, 380)],
           "old": [("MsMpEng.exe", 14.0, 9.0, 300), ("SearchIndexer.exe", 6.5, 22.0, 120), ("OneDrive.exe", 5.0, 18.0, 180)]}


class _IO(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes",
                                                  "OtherBytes")]


class _PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def _proc_counters(pid: int):
    """-> (робочий набір, байтів прочитано, байтів записано) або None (захищений процес)."""
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.GetProcessIoCounters.argtypes = [ctypes.c_void_p, ctypes.POINTER(_IO)]
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        io = _IO()
        pm = _PMC()
        pm.cb = ctypes.sizeof(pm)
        ws = 0
        try:
            psapi = ctypes.windll.psapi
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMC), ctypes.c_ulong]
            if psapi.GetProcessMemoryInfo(h, ctypes.byref(pm), pm.cb):
                ws = pm.WorkingSetSize
        except Exception:
            pass
        if not k32.GetProcessIoCounters(h, ctypes.byref(io)):
            return ws, 0, 0
        return ws, io.ReadBytes, io.WriteBytes
    finally:
        k32.CloseHandle(h)


class Recorder:
    """Запис фону: start(exe гри) — далі sample() раз на INTERVAL — finish() -> сесія для звіту."""

    def __init__(self, game: str = "", manual: bool = False):
        self.game = (game or "").lower()
        self.manual = manual
        self.t0 = time.time()
        self.samples = []  # [{t, procs: {name: (cpu%, ram_mb, io_mbs, gpu%)}, net_kbs, game_cpu}]
        self.prev_io = {}
        self.prev_t = None
        self.cpu = None
        self.pdh = None
        self.i = 0
        if E.IS_WIN:
            import monitor as M
            self.cpu = M.ProcSampler()
            self.cpu.sample()
            self.pdh = M.Pdh(None, {"net": r"\Network Interface(*)\Bytes Total/sec",
                                    "eng": r"\GPU Engine(*engtype_3D)\Utilization Percentage"})

    def sample(self) -> dict:
        self.i += 1
        if not E.IS_WIN:
            s = _demo_sample(self.game, self.i)
        else:
            s = self._real()
        s["t"] = round(time.time() - self.t0, 1)
        if len(self.samples) < MAX_SAMPLES:
            self.samples.append(s)
        return s

    def _real(self) -> dict:
        import gpuinfo as GI
        now = time.perf_counter()
        cpu = self.cpu.sample()  # {pid: (name, частка 0…1)}
        d = self.pdh.collect() if self.pdh else {}
        gpu = {}
        for inst, val in (d.get("eng") or {}).items():
            m = GI.ENGINE_RE.search(inst or "")
            if m:
                gpu[int(m.group(1))] = gpu.get(int(m.group(1)), 0.0) + float(val or 0)
        span = (now - self.prev_t) if self.prev_t else None
        procs = {}
        game_cpu = 0.0
        cur_io = {}
        for pid, (name, share) in cpu.items():
            n = (name or "").lower()
            if n in SKIP:
                continue
            c = _proc_counters(pid)
            ws = rd = wr = 0
            if c:
                ws, rd, wr = c
                cur_io[pid] = (n, rd + wr)
            io = 0.0
            old = self.prev_io.get(pid)
            if span and old and old[0] == n and c:
                io = max(0.0, (rd + wr - old[1]) / span / 2**20)
            p = procs.setdefault(n, [0.0, 0.0, 0.0, 0.0])
            p[0] += share * 100
            p[1] += ws / 2**20
            p[2] += io
            p[3] += gpu.get(pid, 0.0)
            if n == self.game:
                game_cpu += share * 100
        self.prev_io, self.prev_t = cur_io, now
        net = sum((d.get("net") or {}).values()) / 1024 if d.get("net") else None
        return dict(procs={k: tuple(round(x, 2) for x in v) for k, v in procs.items() if any(v)}, net_kbs=net,
                    game_cpu=round(game_cpu, 1))

    def close(self) -> None:
        if self.pdh:
            self.pdh.close()

    def finish(self, fps_series: list = None) -> dict:
        self.close()
        return analyze(self.samples, self.game, fps_series, manual=self.manual, start=int(self.t0),
                       startup=startup_names())


def _demo_sample(game: str, i: int) -> dict:
    import math
    import random
    rnd = random.Random(i * 13)
    procs = {(game or "cs2.exe"): (38.0 + rnd.uniform(-4, 4), 5200.0, 1.0, 92.0)}
    for name, cpu, io, ram in DEMO_BG.get(E.DEMO, DEMO_BG["gaming"]):
        spike = 4.0 if (name.lower() in ("msmpeng.exe", "onedrive.exe") and i % 15 in (7, 8)) else 1.0
        procs[name.lower()] = (round(cpu * spike * (1 + 0.2 * math.sin(i)), 2), float(ram), round(io * spike, 2), 0.0)
    return dict(procs=procs, net_kbs=120.0 + rnd.uniform(0, 40), game_cpu=procs[(game or "cs2.exe")][0])


def kind_of(name: str, startup: set = None) -> str:
    n = (name or "").lower()
    if n in ANTIVIRUS:
        return "antivirus"
    if n in CRITICAL:
        return "system"
    if startup and n in startup:
        return "startup"
    return "app"


def advice_for(kind: str, heavy_reason: str) -> list:
    """Варіанти для людини — ключі pm.a.*. Нічого не виконується автоматично."""
    if kind == "system":
        return ["keep"]
    if kind == "antivirus":
        return ["keep", "exclude"]
    if kind == "startup":
        return ["close", "autostart", "inspect"]
    return ["close", "inspect"] if heavy_reason else ["keep"]


def _drops(fps: list) -> set:
    """Секунди (індекси), де FPS упав нижче 70% медіани."""
    vals = [v for v in fps or [] if v]
    if len(vals) < 10:
        return set()
    med = sorted(vals)[len(vals) // 2]
    return {i for i, v in enumerate(fps) if v and v < med * 0.7}


def analyze(samples: list, game: str = "", fps_series: list = None, manual: bool = False, start: int = 0,
            startup: set = None) -> dict:
    """Підсумок сесії: {processes: [{name, kind, avg_cpu, max_cpu, spikes, ram_mb, io_mb, io_spikes, gpu, overlap,
    suspect, reason, advice}], seconds, game, net_avg_kbs}."""
    n = len(samples)
    stats = {}
    for i, s in enumerate(samples):
        for name, (cpu, ram, io, gpu) in (s.get("procs") or {}).items():
            st = stats.setdefault(name, dict(cpu=[], ram=[], io=0.0, gpu=[], spikes=set(), io_spikes=set()))
            st["cpu"].append(cpu)
            st["ram"].append(ram)
            st["io"] += io * INTERVAL
            st["gpu"].append(gpu)
            if cpu >= SPIKE_CPU:
                st["spikes"].add(i)
            if io >= SPIKE_IO_MBS:
                st["io_spikes"].add(i)
    # кадри PresentMon (FPS по секундах) -> вимір кожні INTERVAL секунд
    drops = set()
    if fps_series:
        per = max(1, int(INTERVAL))
        coarse = [min(fps_series[j:j + per]) for j in range(0, len(fps_series), per)]
        drops = _drops(coarse)
    out = []
    for name, st in stats.items():
        if name == (game or "").lower():
            continue
        avg = sum(st["cpu"]) / max(1, n)
        ram = max(st["ram"] or [0])
        reason = ""
        if avg >= HEAVY_AVG:
            reason = "cpu"
        elif len(st["spikes"]) >= 3:
            reason = "spikes"
        elif len(st["io_spikes"]) >= 2:
            reason = "disk"
        elif ram >= HEAVY_RAM_MB:
            reason = "ram"
        if not reason:
            continue
        overlap = 0.0
        busy = st["spikes"] | st["io_spikes"]
        if drops and busy:
            overlap = round(len(busy & drops) / len(drops), 2)
        kind = kind_of(name, startup)
        suspect = overlap >= 0.3 and len(busy & drops) >= 2
        out.append(dict(name=name, kind=kind, avg_cpu=round(avg, 1), max_cpu=round(max(st["cpu"] or [0]), 1),
                        spikes=len(st["spikes"]), ram_mb=round(ram), io_mb=round(st["io"]), io_spikes=len(st["io_spikes"]),
                        gpu=round(sum(st["gpu"]) / max(1, n), 1), overlap=overlap, suspect=suspect, reason=reason,
                        advice=advice_for(kind, reason)))
    out.sort(key=lambda p: (not p["suspect"], -(p["avg_cpu"] + p["spikes"] * 2 + p["io_spikes"] * 2)))
    nets = [s["net_kbs"] for s in samples if s.get("net_kbs") is not None]
    return dict(game=game, manual=manual, start=start or int(time.time()), seconds=round(n * INTERVAL),
                processes=out[:15], drops=len(drops), net_avg_kbs=round(sum(nets) / len(nets), 1) if nets else None,
                fps=bool(fps_series))


def save_session(cfg, sess: dict) -> list:
    hist = list(cfg["pm_sessions"] or [])
    hist.append(sess)
    cfg["pm_sessions"] = hist[-KEEP_SESSIONS:]
    return hist


def startup_names() -> set:
    """exe програм з автозапуску (ключі Run у реєстрі) — щоб порадити «вимкнути автозапуск», а не «закрити».
    Лише реєстр: швидко, без PowerShell (виклик — наприкінці гри, у потоці інтерфейсу)."""
    if not E.IS_WIN:
        return {"onedrive.exe", "discord.exe"}
    try:
        import features as F
        import ntpath
        out = set()
        for hive, path, _sub, _src in F.RUN_SOURCES:
            for name, val, _t in E.reg_values(f"{hive}\\{path}"):
                exe = ntpath.basename(F._exe_from_cmd(str(val))).lower()
                if exe:
                    out.add(exe)
        return out
    except Exception:
        return set()


def session_result(sess: dict) -> dict:
    import hwtests as HT
    procs = sess.get("processes") or []
    sus = [p for p in procs if p["suspect"]]
    f = []
    for p in procs[:6]:
        key = "pm.f.suspect" if p["suspect"] else f"pm.f.{p['reason']}"
        f.append((HT.WARN if p["suspect"] else "info", key, dict(name=p["name"], cpu=p["avg_cpu"], mx=p["max_cpu"],
                                                                 ram=p["ram_mb"], io=p["io_mb"], ov=round(p["overlap"] * 100))))
    if not sess.get("fps"):
        f.append(("info", "pm.f.no_fps", {}))
    f.append(("info", "pm.f.net", {}))
    st = HT.WARN if sus else HT.PASS
    rows = [("pm.r.game", sess.get("game") or tr("pm.manual")), ("hwc.r.duration", f"{sess.get('seconds', 0)} {tr('hwc.u.s')}"),
            ("pm.r.heavy", len(procs)), ("pm.r.suspects", len(sus)), ("pm.r.drops", sess.get("drops") if sess.get("fps") else None),
            ("pm.r.net", f"{sess['net_avg_kbs']} KB/s" if sess.get("net_avg_kbs") is not None else None)]
    return HT.result("procs", st, tr(f"pm.sum.{st}", n=len(procs), s=len(sus)), rows=rows, findings=f, session=sess)
