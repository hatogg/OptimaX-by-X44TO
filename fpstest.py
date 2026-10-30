"""
OptimaX — тест FPS «до і після» через PresentMon (відкритий інструмент Intel, ліцензія MIT).

PresentMon не входить у програму: OptimaX шукає його поруч із собою або завантажує з офіційної сторінки
релізів на GitHub за вашою згодою.
"""
from __future__ import annotations

import csv
import glob
import json
import math
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
    """Середній FPS, 1% і 0.1% low, кількість фризів (кадр удвічі з половиною довший за медіану) і плавність:
    100 × медіанний час кадру / 99-й перцентиль — 100 означає ідеально рівні кадри, 50 — кожен сотий кадр
    удвічі довший за звичайний."""
    ft = [x for x in frametimes if 0.05 < x < 1000]
    if len(ft) < 30:
        return {}
    s = sorted(ft)
    n = len(s)
    worst1 = s[int(n * 0.99):] or s[-1:]
    worst01 = s[int(n * 0.999):] or s[-1:]
    med = _percentile(s, 0.5)
    p99 = _percentile(s, 0.99)
    step = max(1, n // 240)
    secs = sum(ft) / 1000
    stutters = sum(1 for x in ft if x > 2.5 * med)
    return dict(frames=n, seconds=round(secs, 1), avg=round(1000 * n / sum(ft), 1),
                low1=round(1000 / (sum(worst1) / len(worst1)), 1), low01=round(1000 / (sum(worst01) / len(worst01)), 1),
                p99=round(p99, 2), stutters=stutters, stutters_pm=round(stutters * 60 / secs, 1) if secs else 0.0,
                smooth=round(100 * med / p99, 1) if p99 else 0.0,
                series=[round(sum(ft[i:i + step]) / len(ft[i:i + step]), 2) for i in range(0, n, step)][:240])


# ───────────────────────── кілька прогонів: медіана, розкид, похибка ─────────────────────────
# Навіть у тій самій сцені FPS «гуляє» між запусками: кеш шейдерів, фонові задачі, частоти. Один замір «до»
# і один «після» не відрізняють приріст від випадковості, тож міряємо 3–5 разів, беремо медіану (один невдалий
# прогін її не зсуне) і рахуємо, яка різниця вже не пояснюється розкидом між прогонами.
METRICS = ("avg", "low1", "low01")
NOISE_FLOOR = {"avg": 0.02, "low1": 0.04, "low01": 0.08}  # менше цього не відрізнити навіть на ідеальному тесті
TYPICAL_CV = {"avg": 0.03, "low1": 0.06, "low01": 0.12}  # розкид, якщо прогін лише один і його не видно
MEDIAN_EFF = 1.57  # дисперсія медіани ≈ 1.57 × дисперсії середнього (π/2)


def _median(vals):
    v = sorted(x for x in vals if isinstance(x, (int, float)))
    if not v:
        return 0.0
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def _cv(vals):
    """Відносне стандартне відхилення між прогонами (None — прогін один)."""
    v = [x for x in vals if isinstance(x, (int, float)) and x > 0]
    if len(v) < 2:
        return None
    mean = sum(v) / len(v)
    var = sum((x - mean) ** 2 for x in v) / (len(v) - 1)
    return math.sqrt(var) / mean if mean else None


def drop_outliers(runs: list) -> tuple:
    """Із 4+ прогонів прибирає явно невдалий (догрузка рівня, сповіщення, фонове оновлення): той, чий FPS
    відхиляється від медіани більше ніж на 3 робастні сигми й щонайменше на 8%. Лишається не менше трьох."""
    if len(runs) < 4:
        return list(runs), []
    avgs = [r["avg"] for r in runs]
    med = _median(avgs)
    mad = _median([abs(a - med) for a in avgs]) * 1.4826
    lim = max(3 * mad, 0.08 * med)
    keep = [r for r in runs if abs(r["avg"] - med) <= lim]
    if len(keep) < 3:
        return list(runs), []
    return keep, [r for r in runs if r not in keep]


def summarize_runs(runs: list) -> dict:
    """Кілька замірів однієї сцени -> медіани, розкид між прогонами, плавність. Сумісно з одиночним заміром:
    ключі avg / low1 / low01 / stutters / series / ts такі самі."""
    runs = [r for r in runs if r and r.get("avg")]
    if not runs:
        return {}
    keep, dropped = drop_outliers(runs)
    mid = min(keep, key=lambda r: abs(r["avg"] - _median([x["avg"] for x in keep])))
    out = {k: round(_median([r.get(k) for r in keep]), 1) for k in METRICS}
    out.update(runs=len(keep), dropped=len(dropped), values={k: [r.get(k) for r in keep] for k in METRICS},
               spread={k: (round(_cv([r.get(k) for r in keep]), 4) if _cv([r.get(k) for r in keep]) is not None
                           else None) for k in METRICS},
               stutters=int(round(_median([r.get("stutters", 0) for r in keep]))),
               stutters_pm=round(_median([r.get("stutters_pm", 0) for r in keep]), 1),
               smooth=round(_median([r.get("smooth", 0) for r in keep]), 1) if all("smooth" in r for r in keep)
               else None,
               seconds=mid.get("seconds"), frames=mid.get("frames"), series=mid.get("series", []),
               exe=mid.get("exe"), ts=max(r.get("ts", 0) for r in runs))
    return out


def as_summary(m: dict) -> dict:
    """Заміри 6.3 і старіших — один прогін без розкиду."""
    if not m:
        return {}
    if "runs" in m:
        return m
    return dict(m, runs=1, dropped=0, spread={k: None for k in METRICS}, values={k: [m.get(k)] for k in METRICS})


def margin(before: dict, after: dict, key: str) -> float:
    """Відносна похибка порівняння (95%): стандартна похибка різниці медіан × квантиль Стьюдента за кількістю
    прогонів (з 3+3 — 2.78, з 5+5 — 2.31), не менше за поріг шуму. Розкид невідомий (один прогін) — типовий."""
    from abtest import t95
    se2, df = 0.0, 0
    for m in (before, after):
        cv = (m.get("spread") or {}).get(key)
        if cv is not None:
            df += max(0, m.get("runs", 1) - 1)
        cv = TYPICAL_CV[key] if cv is None else max(cv, NOISE_FLOOR[key] / 4)
        se2 += MEDIAN_EFF * cv ** 2 / max(1, m.get("runs", 1))
    return max(NOISE_FLOOR[key], t95(df) * math.sqrt(se2))


def compare_runs(before: dict, after: dict) -> dict:
    """Порівняння «до/після»: зміна кожної метрики у %, її похибка і чи вона значуща; плавність; вердикт.
    better — FPS або 1% low виріс більше за похибку, а інше не впало більше за похибку; worse — хоч одне з них
    впало більше за похибку; same — різниця в межах похибки вимірювання."""
    b, a = as_summary(before), as_summary(after)
    if not (b.get("avg") and a.get("avg")):
        return {}
    res = {}
    for k in METRICS:
        if not (b.get(k) and a.get(k)):
            continue
        d = (a[k] - b[k]) / b[k]
        mg = margin(b, a, k)
        res[k] = dict(d=round(d * 100, 1), margin=round(mg * 100, 1), sig=abs(d) > mg,
                      dir=(1 if d > 0 else -1) if abs(d) > mg else 0)
    avg, low = res.get("avg", {}), res.get("low1", {})
    up = avg.get("dir") == 1 or low.get("dir") == 1
    down = avg.get("dir") == -1 or low.get("dir") == -1
    verdict = "worse" if down else "better" if up else "same"
    runs = min(b.get("runs", 1), a.get("runs", 1))
    conf = "low" if runs < 2 else "high" if runs >= 3 and avg.get("margin", 99) <= 3.5 else "medium"
    out = dict(metrics=res, verdict=verdict, confidence=conf, runs=(b.get("runs", 1), a.get("runs", 1)),
               d_avg=avg.get("d", 0.0), d_low=low.get("d", 0.0), m_avg=avg.get("margin", 0.0),
               m_low=low.get("margin", 0.0), d_stutter=a.get("stutters", 0) - b.get("stutters", 0),
               d_stutter_pm=round(a.get("stutters_pm", 0) - b.get("stutters_pm", 0), 1))
    if b.get("smooth") is not None and a.get("smooth") is not None:
        out["smooth"] = (b["smooth"], a["smooth"])
        out["d_smooth"] = round(a["smooth"] - b["smooth"], 1)
    return out


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


_DEMO_RUN = [0]


def _demo_frametimes(seconds: int) -> list:
    """Поза Windows: правдоподібні кадри, що трохи кращають із кожною застосованою оптимізацією,
    з невеликим розкидом між прогонами, як у справжній грі."""
    n = E.JOURNAL.count()
    _DEMO_RUN[0] += 1
    rnd = random.Random(n * 7 + seconds + 1009 * _DEMO_RUN[0])
    base = {"gaming": 6.9, "laptop": 11.5, "old": 33.0, "x3d": 4.4, "xeon": 9.8}.get(E.DEMO, 8.0)
    base *= max(0.9, 1 - 0.004 * n) * (1 + rnd.uniform(-0.012, 0.012))
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


def capture_runs(exe: str, seconds: int, runs: int, log, progress, pause: float = 4.0, hw: dict = None) -> dict:
    """runs замірів по seconds секунд поспіль (гра має лишатися в тій самій сцені) -> summarize_runs().
    Невдалий прогін (гру згорнули) не зупиняє серію: результат рахується з тих, що вдалися.
    hw — паралельно з записом кадрів стежимо за процесором, відеокартою, пам'яттю, диском і температурами
    (monitor.lag_diagnosis): у результаті з'являється «bottleneck» — що саме обмежувало FPS у цій грі."""
    got, last_err = [], None
    total = seconds * runs
    diag, watcher = {}, None
    if hw is not None:
        import threading
        import monitor as M

        def watch():
            try:
                diag.update(M.lag_diagnosis(hw, total, lambda *_: None, None, game=exe))
            except Exception:  # діагностика — додаток до заміру FPS, а не його умова
                pass
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
    for i in range(runs):
        if E.CANCEL.is_set():
            break

        def prog(done, _n, text, i=i):
            if progress:
                progress(i * seconds + done, total, tr("fps.run_of", i=i + 1, n=runs) + " · " + text)
        try:
            r = capture(exe, seconds, log, prog)
        except RuntimeError as e:
            last_err = e
            log(tr("fps.run_failed", i=i + 1, err=str(e)))
            continue
        got.append(r)
        if i < runs - 1:  # коротка пауза: PresentMon закриває сесію, гра вирівнює частоти
            end = time.time() + (pause if E.IS_WIN else 0.01)
            while time.time() < end and not E.CANCEL.is_set():
                time.sleep(0.05)
    if watcher:
        watcher.join(15)
    if not got:
        raise last_err or RuntimeError(tr("fps.no_frames", exe=exe))
    res = summarize_runs(got)
    if diag.get("bottleneck"):
        res["bottleneck"] = diag["bottleneck"]
        res["findings"] = [f["key"] for f in diag.get("findings", [])]
    sp = (res.get("spread") or {}).get("avg")
    log(tr("fps.runs_log", n=res["runs"], avg=res["avg"], low=res["low1"],
           sp="—" if sp is None else f"±{sp * 100:.1f}%") + (tr("fps.dropped", n=res["dropped"]) if res["dropped"] else ""))
    return res


def compare(before: dict, after: dict) -> dict:
    """Сумісність зі старим кодом: те саме, що compare_runs (вердикт уже з урахуванням похибки)."""
    return compare_runs(before, after)


def changes_between(t0: int, t1: int) -> list:
    """Записи журналу, створені між двома замірами: їх пропонуємо відкотити, якщо стало гірше."""
    return [tid for tid, e in E.JOURNAL.data["applied"].items() if t0 <= e.get("ts", 0) <= t1]
