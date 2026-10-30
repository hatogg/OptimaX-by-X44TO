"""
OptimaX — тест FPS «до і після» через PresentMon (відкритий інструмент Intel, ліцензія MIT).

PresentMon не входить у програму: OptimaX шукає його поруч із собою або завантажує з офіційної сторінки
релізів на GitHub за вашою згодою.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import random
import re
import subprocess
import time
import urllib.request

import engine as E
from i18n import tr

RELEASES_API = "https://api.github.com/repos/GameTechDev/PresentMon/releases/latest"
RELEASES_PAGE = "https://github.com/GameTechDev/PresentMon/releases"
TOOLS_DIR = os.path.join(E.DATA_DIR, "tools")
ASSET_RE = re.compile(r"^PresentMon-[\d.]+-x64\.exe$", re.I)


def _app_dir() -> str:
    import sys
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def find_presentmon():
    if not E.IS_WIN:
        return "PresentMon-demo.exe"
    for folder in (os.path.join(_app_dir(), "tools"), _app_dir(), TOOLS_DIR):
        hits = sorted(glob.glob(os.path.join(folder, "PresentMon*.exe")), reverse=True)
        hits = [h for h in hits if "service" not in h.lower()]
        if hits:
            return hits[0]
    return None


def download_presentmon(log) -> str:
    """Завантажує консольну версію PresentMon з останнього релізу на GitHub."""
    if not E.IS_WIN:
        log("  [dry-run] GitHub: GameTechDev/PresentMon → PresentMon-x64.exe")
        return "PresentMon-demo.exe"
    req = urllib.request.Request(RELEASES_API, headers={"User-Agent": f"{E.APP_NAME}/{E.VERSION}",
                                                        "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        rel = json.load(r)
    asset = next((a for a in rel.get("assets", []) if ASSET_RE.match(a.get("name", ""))), None)
    if not asset:
        raise RuntimeError(tr("fps.no_asset"))
    os.makedirs(TOOLS_DIR, exist_ok=True)
    dest = os.path.join(TOOLS_DIR, asset["name"])
    log(tr("fps.downloading", name=asset["name"], mb=f"{asset.get('size', 0) / 2**20:.1f}"))
    tmp = dest + ".part"
    req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": f"{E.APP_NAME}/{E.VERSION}"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    if os.path.getsize(tmp) < 100_000:
        os.remove(tmp)
        raise RuntimeError(tr("fps.bad_download"))
    # PresentMon запускатиметься з правами адміністратора: сума з GitHub (якщо реліз її публікує) має збігтися,
    # а пошкоджений чи недовірений підпис — ніколи
    import verify as V
    try:
        digest = V.digest_of(asset)
        if digest:
            V.check_file(tmp, digest, publisher="", name=asset["name"])
        elif V.signature(tmp)["status"] == "invalid":
            raise V.VerifyError("vf.sig_invalid", name=asset["name"], code="WinVerifyTrust")
    except V.VerifyError:
        os.remove(tmp)
        raise
    os.replace(tmp, dest)
    log(tr("fps.downloaded"))
    return dest


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def stats(frametimes: list) -> dict:
    """Середній FPS, 1% і 0.1% low, кількість фризів (кадр удвічі з половиною довший за медіану)."""
    ft = [x for x in frametimes if 0.05 < x < 1000]
    if len(ft) < 30:
        return {}
    s = sorted(ft)
    n = len(s)
    worst1 = s[int(n * 0.99):] or s[-1:]
    worst01 = s[int(n * 0.999):] or s[-1:]
    med = _percentile(s, 0.5)
    step = max(1, n // 240)
    return dict(frames=n, seconds=round(sum(ft) / 1000, 1), avg=round(1000 * n / sum(ft), 1),
                low1=round(1000 / (sum(worst1) / len(worst1)), 1), low01=round(1000 / (sum(worst01) / len(worst01)), 1),
                p99=round(_percentile(s, 0.99), 2), stutters=sum(1 for x in ft if x > 2.5 * med),
                series=[round(sum(ft[i:i + step]) / len(ft[i:i + step]), 2) for i in range(0, n, step)][:240])


def parse_csv(path: str) -> list:
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    if not rows:
        return []
    head = [h.strip() for h in rows[0]]
    col = next((head.index(c) for c in ("MsBetweenPresents", "FrameTime", "msBetweenPresents") if c in head), None)
    if col is None:
        return []
    out = []
    for r in rows[1:]:
        try:
            out.append(float(r[col]))
        except (ValueError, IndexError):
            pass
    return out


def _demo_frametimes(seconds: int) -> list:
    """Поза Windows: правдоподібні кадри, що трохи кращають із кожною застосованою оптимізацією."""
    n = E.JOURNAL.count()
    rnd = random.Random(n * 7 + seconds)
    base = {"gaming": 6.9, "laptop": 11.5, "old": 33.0, "x3d": 4.4, "xeon": 9.8}.get(E.DEMO, 8.0)
    base *= max(0.9, 1 - 0.004 * n)
    spikes = 0.006 * max(0.35, 1 - 0.035 * n)
    out, t = [], 0.0
    while t < seconds * 1000:
        x = base * rnd.uniform(0.9, 1.12)
        if rnd.random() < spikes:
            x *= rnd.uniform(2.6, 4.5)
        out.append(x)
        t += x
    return out


def capture(exe: str, seconds: int, log, progress) -> dict:
    """Записує кадри гри exe протягом seconds секунд. Гра має бути запущена."""
    pm = find_presentmon()
    if not pm:
        raise RuntimeError(tr("fps.no_pm"))
    if not E.IS_WIN:
        for i in range(seconds):
            if E.CANCEL.is_set():
                break
            if progress:
                progress(i, seconds, tr("fps.recording", s=seconds - i))
            time.sleep(0.005)
        res = stats(_demo_frametimes(seconds))
        res.update(exe=exe, ts=int(time.time()))
        log(tr("fps.result_log", avg=res["avg"], low=res["low1"]))
        return res
    import verify as V
    if V.signature(pm)["status"] == "invalid":  # файл підмінили після завантаження
        raise RuntimeError(tr("vf.sig_invalid", name=os.path.basename(pm), code="WinVerifyTrust"))
    os.makedirs(TOOLS_DIR, exist_ok=True)
    out = os.path.join(TOOLS_DIR, f"capture_{int(time.time())}.csv")
    cmd = [pm, "--process_name", exe, "--output_file", out, "--timed", str(seconds), "--terminate_after_timed",
           "--no_console_stats", "--stop_existing_session", "--session_name", "OptimaX"]
    log(f"  {' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd))}")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=E.CREATE_NO_WINDOW)
    t0 = time.time()
    while p.poll() is None:
        el = int(time.time() - t0)
        if progress:
            progress(min(el, seconds), seconds, tr("fps.recording", s=max(0, seconds - el)))
        if E.CANCEL.is_set() or el > seconds + 25:
            p.kill()
            break
        time.sleep(0.5)
    try:
        tail = (p.stdout.read() or b"").decode("utf-8", "replace").strip()
    except Exception:
        tail = ""
    if not os.path.exists(out):
        raise RuntimeError(tr("fps.no_frames", exe=exe) + (f" ({E.first_line(tail, 80)})" if tail else ""))
    frames = parse_csv(out)
    try:
        os.remove(out)
    except OSError:
        pass
    res = stats(frames)
    if not res:
        raise RuntimeError(tr("fps.no_frames", exe=exe))
    res.update(exe=exe, ts=int(time.time()))
    log(tr("fps.result_log", avg=res["avg"], low=res["low1"]))
    return res


def compare(before: dict, after: dict) -> dict:
    if not before or not after:
        return {}
    d_avg = (after["avg"] - before["avg"]) / before["avg"] * 100
    d_low = (after["low1"] - before["low1"]) / before["low1"] * 100
    score = (d_avg + d_low) / 2
    verdict = "better" if score >= 3 else "worse" if score <= -3 else "same"
    return dict(d_avg=round(d_avg, 1), d_low=round(d_low, 1), verdict=verdict,
                d_stutter=after.get("stutters", 0) - before.get("stutters", 0))


def changes_between(t0: int, t1: int) -> list:
    """Записи журналу, створені між двома замірами: їх пропонуємо відкотити, якщо стало гірше."""
    return [tid for tid, e in E.JOURNAL.data["applied"].items() if t0 <= e.get("ts", 0) <= t1]
