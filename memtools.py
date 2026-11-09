"""
OptimaX — сторінка «Пам'ять» (6.13): скільки RAM реально зайнято, хто її тримає, і чесне звільнення.

Що робить «Звільнити пам'ять» і чого не робить:
  1. Стискає робочі набори лише програм, що СПЛЯТЬ у фоні: за останні секунди майже не брали процесор, не активне
     вікно, не гра, не системний процес Windows, не антивірус і не звук. Їхні сторінки Windows переносить у кеш
     (standby) або в чергу на запис — потрібне вони підвантажать самі, коли прокинуться.
  2. Очищує кеш standby (як RAMMap/ISLC) — це вже було в OptimaX.
  3. Міряє «до» і «після» так само, як «Диспетчер завдань» («Використовується» = усього − доступно), а через хвилину
     міряє ще раз і чесно показує, скільки Windows забрала назад.
Гру й активні програми не чіпаємо ніколи: примусове стискання ВСІХ процесів дає велику цифру «звільнено», але гра
потім добирає пам'ять із диска — і це фризи.
"""
from __future__ import annotations

import ctypes
import math
import os
import random
import time

import engine as E
from i18n import tr

MIN_TRIM_MB = 40           # менші процеси не варті стискання
IDLE_SHARE = 0.003         # < 0,3 % усього процесора за вимір — «спить»
ACTIVE_SHARE = 0.02        # > 2 % — «активна»
REBOUND_AFTER = 60         # через скільки секунд перевіряти, що повернулося
NEVER = {"system", "registry", "secure system", "memory compression", "smss.exe", "csrss.exe", "wininit.exe",
         "winlogon.exe", "services.exe", "lsass.exe", "lsaiso.exe", "dwm.exe", "fontdrvhost.exe", "audiodg.exe",
         "msmpeng.exe", "nissrv.exe", "mpdefendercoreservice.exe", "securityhealthservice.exe", "sgrmbroker.exe",
         "explorer.exe", "sihost.exe", "ctfmon.exe", "textinputhost.exe", "startmenuexperiencehost.exe",
         "searchhost.exe", "shellexperiencehost.exe", "optimax.exe", "python.exe", "pythonw.exe", "presentmon.exe",
         "avp.exe", "avastsvc.exe", "ekrn.exe", "bdservicehost.exe", "mbamservice.exe", "wudfhost.exe",
         "conhost.exe", "idle", "system idle process",
         # служби Windows (серед них і служба звуку) — не «програми, що сплять»: їх не стискаємо
         "svchost.exe", "spoolsv.exe", "wmiprvse.exe", "runtimebroker.exe", "taskhostw.exe"}
FRIENDLY = {"chrome.exe": "Google Chrome", "msedge.exe": "Microsoft Edge", "firefox.exe": "Firefox",
            "opera.exe": "Opera", "browser.exe": "Yandex Browser", "discord.exe": "Discord", "telegram.exe": "Telegram",
            "steamwebhelper.exe": "Steam", "steam.exe": "Steam", "epicgameslauncher.exe": "Epic Games",
            "spotify.exe": "Spotify", "code.exe": "Visual Studio Code", "obs64.exe": "OBS Studio",
            "msmpeng.exe": "Microsoft Defender", "onedrive.exe": "OneDrive", "teams.exe": "Microsoft Teams",
            "ms-teams.exe": "Microsoft Teams", "nvcontainer.exe": "NVIDIA", "radeonsoftware.exe": "AMD Software",
            # компоненти Windows — перекладені назви (lang_v613.py)
            "svchost.exe": "@mem.app.services", "explorer.exe": "@mem.app.explorer",
            "memory compression": "@mem.app.compression", "searchindexer.exe": "@mem.app.search",
            "dwm.exe": "@mem.app.dwm", "phoneexperiencehost.exe": "@mem.app.phone", "widgets.exe": "@mem.app.widgets"}


def friendly(name: str) -> str:
    n = (name or "").lower()
    if n in FRIENDLY:
        v = FRIENDLY[n]
        return tr(v[1:]) if v.startswith("@") else v
    base = name[:-4] if n.endswith(".exe") else name
    return base[:1].upper() + base[1:]


# ───────────────────────── демо поза Windows ─────────────────────────
_demo = {"t0": time.time(), "clean": None}  # clean: (час, звільнено МБ)
DEMO_PROCS = [("chrome.exe", 14, 3120, 0.004), ("Discord.exe", 5, 860, 0.0008), ("steamwebhelper.exe", 7, 740, 0.0004),
              ("svchost.exe", 71, 1480, 0.006), ("Code.exe", 9, 1130, 0.03), ("Telegram.exe", 1, 410, 0.0002),
              ("MsMpEng.exe", 1, 380, 0.004), ("OneDrive.exe", 1, 160, 0.0001), ("explorer.exe", 1, 210, 0.008)]


def _demo_used() -> float:
    t = time.time() - _demo["t0"]
    used = 13720 + 160 * math.sin(t / 7) + random.uniform(-40, 40)
    if _demo["clean"]:
        ts, freed = _demo["clean"]
        age = time.time() - ts
        used -= freed * (1 - 0.28 * min(1.0, age / REBOUND_AFTER))
    return used


# ───────────────────────── знімок ─────────────────────────
def snapshot() -> dict:
    """-> {total, used, avail, free, standby (МБ), load (0…1)} — «used» як «Використовується» в Диспетчері."""
    if not E.IS_WIN:
        total = 32768
        used = _demo_used()
        standby = 9400 if not _demo["clean"] else 2100 + min(5000, (time.time() - _demo["clean"][0]) * 60)
        avail = total - used
        return dict(total=total, used=used, avail=avail, free=max(0.0, avail - standby), standby=standby,
                    load=used / total)
    import hardware as H
    st = E.mem_status()
    total = st.ullTotalPhys / 2**20
    avail = st.ullAvailPhys / 2**20
    ml = H.memory_lists()
    return dict(total=total, used=total - avail, avail=avail, free=float(ml.get("free_mb", 0)),
                standby=float(ml.get("standby_mb", 0)), load=(total - avail) / total if total else 0.0)


# ───────────────────────── хто займає ─────────────────────────
class _PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def _ws(h) -> int:
    pm = _PMC()
    pm.cb = ctypes.sizeof(pm)
    psapi = ctypes.windll.psapi
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMC), ctypes.c_ulong]
    return pm.WorkingSetSize if psapi.GetProcessMemoryInfo(h, ctypes.byref(pm), pm.cb) else 0


def _open(pid: int, access: int):
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    return k32.OpenProcess(access, False, pid)


def _close(h) -> None:
    k32 = ctypes.windll.kernel32
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.CloseHandle(h)


def protected_names() -> set:
    """Ігри (з бібліотеки й зі Steam/Epic/GOG), які не стискаються ніколи."""
    import features as F
    names = set()
    for g in F.CFG["games"] or []:
        p = (g.get("path") or "").replace("/", "\\")
        if p:
            names.add(p.rsplit("\\", 1)[-1].lower())
    names.update(n.lower() for n in ((F.CFG["game_exes"] or {}).get("names") or []))
    return names


class Watcher:
    """Заміри процесів для списку «Хто займає пам'ять»: робочий набір і частка процесора між викликами."""

    def __init__(self):
        self.sampler = None
        if E.IS_WIN:
            import monitor as M
            self.sampler = M.ProcSampler()
            self.sampler.sample()
        self.last = {}  # pid -> (name, частка процесора)

    def processes(self) -> list:
        """-> [{pid, name, mb, share}] — усі процеси з робочим набором."""
        if not E.IS_WIN:
            out = []
            for i, (name, n, mb, share) in enumerate(DEMO_PROCS):
                k = 1.0
                if _demo["clean"] and share / n < IDLE_SHARE and name.lower() not in NEVER:
                    k = 0.3 + 0.25 * min(1.0, (time.time() - _demo["clean"][0]) / REBOUND_AFTER)
                for j in range(n):
                    out.append(dict(pid=1000 + i * 100 + j, name=name, mb=mb / n * k * random.uniform(0.97, 1.03),
                                    share=share / n))
            return out
        self.last = self.sampler.sample()
        out = []
        for pid, (name, share) in self.last.items():
            h = _open(pid, 0x1000)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                continue
            try:
                ws = _ws(h)
            finally:
                _close(h)
            if ws:
                out.append(dict(pid=pid, name=name, mb=ws / 2**20, share=share))
        return out

    def consumers(self, top: int = 8) -> list:
        """-> [{name, title, count, mb, share, state}] за спаданням пам'яті; state: active | background | idle."""
        fg = 0
        if E.IS_WIN:
            import monitor as M
            fg = M.foreground_pid()
        groups = {}
        for pr in self.processes():
            n = pr["name"]
            g = groups.setdefault(n.lower(), dict(name=n, title=friendly(n), count=0, mb=0.0, share=0.0, fg=False))
            g["count"] += 1
            g["mb"] += pr["mb"]
            g["share"] += pr["share"]
            g["fg"] = g["fg"] or pr["pid"] == fg
        res = sorted(groups.values(), key=lambda g: -g["mb"])[:top]
        for g in res:
            g["state"] = ("active" if g["fg"] or g["share"] >= ACTIVE_SHARE else
                          "idle" if g["share"] < IDLE_SHARE * max(1, g["count"]) else "background")
        return res


# ───────────────────────── звільнення ─────────────────────────
def free_memory(watcher: Watcher, log, progress) -> dict:
    """Чесне звільнення (див. опис модуля). progress(крок, усього, текст); крок 0 — стискання, 1 — кеш, 2 — замір.
    -> {before, after, freed, cache, trimmed: [(назва, МБ)], skipped}"""
    before = snapshot()
    trimmed, skipped = {}, 0
    progress(0, 3, tr("mem.step.trim"))
    if not E.IS_WIN:
        time.sleep(0.9)
        freed = before["used"] * 0.21
        for name, n, mb, share in DEMO_PROCS:
            if share / n < IDLE_SHARE and name.lower() not in NEVER:
                trimmed[friendly(name)] = mb * 0.7
        _demo["clean"] = (time.time(), freed)
        log(tr("mem.log.trimmed", n=len(trimmed), mb=f"{sum(trimmed.values()):.0f}"))
    else:
        keep = NEVER | protected_names()
        fg = 0
        try:
            import monitor as M
            fg = M.foreground_pid()
        except Exception:
            pass
        procs = watcher.processes()
        cand = [pr for pr in procs if pr["mb"] >= MIN_TRIM_MB and pr["share"] < IDLE_SHARE and pr["pid"] != fg
                and pr["pid"] != os.getpid() and (pr["name"] or "").lower() not in keep]
        skipped = len(procs) - len(cand)
        if E.DRY_RUN:
            log(tr("mem.log.dry", n=len(cand)))
        else:
            E.enable_privilege("SeDebugPrivilege")
            k32 = ctypes.windll.kernel32
            k32.K32EmptyWorkingSet.argtypes = [ctypes.c_void_p]
            for pr in cand:
                if E.CANCEL.is_set():
                    break
                h = _open(pr["pid"], 0x1000 | 0x0100)  # QUERY_LIMITED_INFORMATION | SET_QUOTA
                if not h:
                    continue
                try:
                    was = _ws(h)
                    if k32.K32EmptyWorkingSet(h):
                        got = max(0, was - _ws(h)) / 2**20
                        t = friendly(pr["name"])
                        trimmed[t] = trimmed.get(t, 0.0) + got
                finally:
                    _close(h)
            log(tr("mem.log.trimmed", n=len(trimmed), mb=f"{sum(trimmed.values()):.0f}"))
    progress(1, 3, tr("mem.step.cache"))
    if E.IS_WIN and not E.DRY_RUN:
        ok = E.purge_standby()
        log(tr("mem.log.cache_ok") if ok else tr("mem.log.cache_fail"))
    else:
        time.sleep(0.6)
        log(tr("mem.log.cache_ok"))
    progress(2, 3, tr("mem.step.measure"))
    time.sleep(0.5)
    after = snapshot()
    return dict(before=before, after=after, freed=max(0.0, before["used"] - after["used"]),
                cache=max(0.0, before["standby"] - after["standby"]),
                trimmed=sorted(trimmed.items(), key=lambda x: -x[1]), skipped=skipped, ts=time.time())


def rebound(res: dict) -> dict:
    """Через хвилину після звільнення: скільки втрималося і скільки Windows забрала назад."""
    now = snapshot()
    kept = max(0.0, min(res["freed"], res["before"]["used"] - now["used"]))
    return dict(now=now, kept=kept, back=max(0.0, res["freed"] - kept))
