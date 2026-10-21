"""
OptimaX — сторонні бенчмарки: встановлення через winget і запуск в один клік.

FurMark 2 запускається з командного рядка, а результат (бали, FPS, температура) OptimaX читає сам із файлів,
які пише FurMark. Інші програми просто відкриваються — результат видно в їхньому вікні
(автоматичний режим Superposition є лише в платній версії Pro).
"""
from __future__ import annotations

import csv
import glob
import io
import os
import re
import subprocess
import tempfile
import time
import webbrowser

import apps as A
import engine as E
from i18n import tr

try:
    import winreg
except ImportError:
    winreg = None

PF = os.environ.get("ProgramFiles", r"C:\Program Files")
PF86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
LAPP = os.environ.get("LOCALAPPDATA", "")

# id, назва, пакет winget, тип, сайт, де шукати exe, як шукати в «Програмах», додаткові ключі winget
CATALOG = [
    dict(id="furmark", name="FurMark 2", pkg="Geeks3D.FurMark.2", kind="gpu", auto=True,
         url="https://geeks3d.com/furmark/", wg_extra=["--installer-type", "inno"],
         paths=[PF + r"\Geeks3D\FurMark2_x64\FurMark_GUI.exe", LAPP + r"\Microsoft\WinGet\Links\FurMark_GUI.exe"],
         reg=r"FurMark\s*2", exe="FurMark_GUI.exe"),
    dict(id="superposition", name="Unigine Superposition", pkg="Unigine.SuperpositionBenchmark", kind="gpu",
         url="https://benchmark.unigine.com/superposition",
         paths=[PF + r"\Unigine\Superposition Benchmark 1.1\Superposition.exe",
                PF + r"\Unigine\Superposition Benchmark\Superposition.exe"],
         reg=r"Superposition", exe="Superposition.exe"),
    dict(id="cinebench", name="Cinebench R23", pkg="Maxon.CinebenchR23", kind="cpu", url="https://www.maxon.net/cinebench",
         paths=[LAPP + r"\Microsoft\WinGet\Links\Cinebench.exe"], pkgdir="Maxon.CinebenchR23", exe="Cinebench.exe"),
    dict(id="occt", name="OCCT", pkg="OCBase.OCCT.Personal", kind="stab", url="https://www.ocbase.com/",
         paths=[LAPP + r"\Microsoft\WinGet\Links\OCCT.exe", PF + r"\WinGet\Links\OCCT.exe"],
         pkgdir="OCBase.OCCT.Personal", exe="OCCT.exe"),
    dict(id="cdm", name="CrystalDiskMark", pkg="CrystalDewWorld.CrystalDiskMark", kind="disk",
         url="https://crystalmark.info/en/software/crystaldiskmark/",
         paths=[PF + r"\CrystalDiskMark9\DiskMark64.exe", PF + r"\CrystalDiskMark8\DiskMark64.exe"],
         reg=r"CrystalDiskMark", exe="DiskMark64.exe"),
    dict(id="3dmark", name="3DMark", pkg=None, kind="gpu", url="https://store.steampowered.com/app/223850/3DMark/",
         steam=223850),
]
BY_ID = {c["id"]: c for c in CATALOG}
DEMO_INSTALLED = {"furmark", "cinebench"}

FURMARK_PRESETS = {"1080p": "--p1080", "1440p": "--p1440", "4k": "--p2160"}


# ───────────────────────── пошук встановлених ─────────────────────────
def _uninstall_entries():
    if winreg is None:
        return
    roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for hive, path in roots:
        try:
            k = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                try:
                    with winreg.OpenKey(k, winreg.EnumKey(k, i)) as sk:
                        vals = {}
                        for name in ("DisplayName", "InstallLocation", "DisplayIcon"):
                            try:
                                vals[name] = str(winreg.QueryValueEx(sk, name)[0])
                            except OSError:
                                vals[name] = ""
                        yield vals
                except OSError:
                    continue


def _from_registry(item: dict):
    pat = item.get("reg")
    if not pat:
        return None
    rx = re.compile(pat, re.I)
    for v in _uninstall_entries():
        if not rx.search(v["DisplayName"]):
            continue
        cands = []
        if v["InstallLocation"]:
            cands.append(os.path.join(v["InstallLocation"].strip('"'), item["exe"]))
            cands += glob.glob(os.path.join(v["InstallLocation"].strip('"'), "**", item["exe"]), recursive=True)[:3]
        icon = v["DisplayIcon"].split(",")[0].strip('"')
        if icon.lower().endswith(".exe"):
            cands.append(os.path.join(os.path.dirname(icon), item["exe"]))
            cands.append(icon)
        for c in cands:
            if c and os.path.isfile(c):
                return c
    return None


def find_exe(item: dict):
    """Шлях до програми або None."""
    if not E.IS_WIN:
        return f"C:\\Demo\\{item.get('exe', item['id'])}" if item["id"] in DEMO_INSTALLED else None
    if item.get("steam"):
        return None
    for p in item.get("paths", []):
        if p and os.path.isfile(p):
            return p
    if item.get("pkgdir") and LAPP:
        for base in (LAPP + r"\Microsoft\WinGet\Packages", PF + r"\WinGet\Packages"):
            hits = glob.glob(os.path.join(base, item["pkgdir"] + "*", "**", item["exe"]), recursive=True)
            if hits:
                return hits[0]
    return _from_registry(item)


def steam_installed() -> bool:
    if not E.IS_WIN or winreg is None:
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return bool(winreg.QueryValueEx(k, "SteamExe")[0])
    except OSError:
        return False


def status() -> dict:
    """-> {id: шлях або None}."""
    return {c["id"]: find_exe(c) for c in CATALOG}


# ───────────────────────── встановлення й запуск ─────────────────────────
def install(item: dict, log, progress=None) -> dict:
    wg = A.winget_path()
    if not wg:
        raise RuntimeError(tr("apps.no_winget"))
    if progress:
        progress(0, 1, item["name"])
    log(f"[►] {item['name']}")
    cmd = [wg, "install", "-e", "--id", item["pkg"]] + item.get("wg_extra", []) + A.WG_FLAGS
    rc, out = E.run(cmd, 1800, log, enc="utf-8")
    if not E.IS_WIN:
        DEMO_INSTALLED.add(item["id"])
    lines = [x.strip() for x in out.replace("\r", "\n").splitlines()
             if x.strip() and not re.fullmatch(r"[\s█▒░\-\\|/.0-9%KMGBkmgb]+", x.strip())]
    for x in lines[-3:]:
        log(f"  {x[:110]}")
    ok = rc in (0, -1978335189)
    log(tr("e.done") if ok else tr("apps.fail_code", rc=rc))
    if progress:
        progress(1, 1, tr("e.finished"))
    return {"ok": ok, "path": find_exe(item)}


def launch(item: dict) -> bool:
    if item.get("steam"):
        url = f"steam://run/{item['steam']}" if steam_installed() else item["url"]
        if E.IS_WIN:
            os.startfile(url)  # noqa: лише Windows
        return E.IS_WIN
    path = find_exe(item)
    if not path or not E.IS_WIN:
        return False
    subprocess.Popen([path], cwd=os.path.dirname(path))
    return True


def open_site(item: dict) -> None:
    webbrowser.open(item["url"])


# ───────────────────────── FurMark 2: автоматичний бенчмарк ─────────────────────────
def _furmark_cli(gui_path: str):
    d = os.path.dirname(gui_path)
    for name in ("furmark.exe", "FurMark.exe"):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def _num(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def parse_scores(text: str, since: float = 0) -> dict:
    """Останній рядок _scores.csv FurMark. Назви колонок у різних версіях різні, тому шукаємо за змістом."""
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if len(rows) < 2:
        return {}
    head = [h.strip().lower() for h in rows[0]]
    last = rows[-1]

    def col(*keys, avoid=()):
        for i, h in enumerate(head):
            if all(k in h for k in keys) and not any(a in h for a in avoid) and i < len(last):
                return last[i].strip()
        return None
    res = dict(score=_num(col("score")), avg=_num(col("fps", avoid=("min", "max"))) or _num(col("avg")),
               min=_num(col("min", "fps")), max=_num(col("max", "fps")), gpu=col("gpu") or col("renderer"),
               resolution=col("resolution") or col("preset"), duration=_num(col("duration")))
    if res["score"] is not None:
        res["score"] = int(res["score"])
    return {k: v for k, v in res.items() if v not in (None, "")}


def parse_gpu_log(text: str) -> dict:
    """Максимальна температура й частота з CSV моніторингу FurMark (перша відеокарта)."""
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if len(rows) < 2:
        return {}
    head = [h.strip().lower() for h in rows[0]]
    ti = next((i for i, h in enumerate(head) if "temp" in h and "hot" not in h), None)
    ci = next((i for i, h in enumerate(head) if "core" in h and "clock" in h), None) or \
        next((i for i, h in enumerate(head) if "clock" in h and "mem" not in h), None)
    pi = next((i for i, h in enumerate(head) if "power" in h and "%" not in h), None)
    out = {}
    for key, idx in (("temp_max", ti), ("clock_max", ci), ("power_max", pi)):
        if idx is None:
            continue
        vals = [_num(r[idx]) for r in rows[1:] if idx < len(r)]
        vals = [v for v in vals if v is not None and v > 0]
        if vals:
            out[key] = round(max(vals), 1) if key == "power_max" else int(max(vals))
    return out


def run_furmark(preset: str, log, progress=None) -> dict:
    """Бенчмарк FurMark 2 (≈1 хв) і розбір результату."""
    item = BY_ID["furmark"]
    if not E.IS_WIN:
        log(f"[►] FurMark 2 · {preset}")
        for i in range(10):
            if progress:
                progress(i, 10, tr("gb.fm_running", s=60 - i * 6))
            time.sleep(0.02)
        base = {"gaming": 13950, "laptop": 7420, "old": 2310, "x3d": 21480, "xeon": 9120}.get(E.DEMO, 9000)
        k = {"1080p": 1.0, "1440p": 0.6, "4k": 0.29}.get(preset, 1.0)
        score = int(base * k)
        return dict(ok=True, kind="furmark", preset=preset, mode="bench", score=score, avg=round(score / 60, 1),
                    temp_max=71 if E.DEMO in ("gaming", "xeon") else 79 if E.DEMO == "laptop" else None,
                    gpu="NVIDIA GeForce RTX 4070" if E.DEMO == "gaming" else None)
    gui = find_exe(item)
    cli = _furmark_cli(gui) if gui else None
    if not cli:
        raise RuntimeError(tr("gb.fm_missing"))
    work = os.path.dirname(cli)
    scores = os.path.join(work, "_scores.csv")
    before = os.path.getmtime(scores) if os.path.exists(scores) else 0
    gpu_csv = os.path.join(tempfile.gettempdir(), f"optimax-furmark-{int(time.time())}.csv")
    cmd = [cli, "--demo", "furmark-gl", "--benchmark", FURMARK_PRESETS.get(preset, "--p1080"), "--no-score-box",
           "--log-gpu-data", "--log-gpu-data-filename", gpu_csv]
    log(f"[►] FurMark 2 · {preset}")
    log("  " + subprocess.list2cmdline([os.path.basename(cli)] + cmd[1:]))
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=work, creationflags=E.CREATE_NO_WINDOW)
    while p.poll() is None:
        if E.CANCEL.is_set():
            p.terminate()
            raise RuntimeError(tr("e.stopped").strip())
        el = time.time() - t0
        if progress:
            progress(min(int(el), 70), 70, tr("gb.fm_running", s=max(0, int(70 - el))))
        time.sleep(0.5)
        if el > 600:
            p.terminate()
            raise RuntimeError(tr("gb.fm_timeout"))
    res = dict(ok=True, kind="furmark", preset=preset, mode="bench", exit_code=p.returncode)
    try:
        if os.path.exists(scores) and os.path.getmtime(scores) > before:
            with open(scores, encoding="utf-8", errors="replace") as f:
                res.update(parse_scores(f.read()))
    except OSError:
        pass
    try:
        if os.path.exists(gpu_csv):
            with open(gpu_csv, encoding="utf-8", errors="replace") as f:
                res.update(parse_gpu_log(f.read()))
            os.remove(gpu_csv)
    except OSError:
        pass
    if res.get("score"):
        log(tr("gb.fm_result", score=res["score"], fps=res.get("avg", "—")))
    else:
        log(tr("gb.fm_noscore"))
    return res
