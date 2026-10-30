"""
OptimaX — аналізатори для ПК з майнінговою картою (і для звичайних NVIDIA): драйвер і доступність DirectX / Vulkan
(P106 Driver Analyzer), відеопам'ять (GPU Memory Analyzer), лінія PCIe під навантаженням (PCIe Link Analyzer),
причини мікрофризів за кадрами PresentMon, історія замірів (GPU Bottleneck History) і кеш шейдерів (Shader Cache
Manager).

Усі висновки — з вимірів (gpuinfo.probe, NVML, лічильники Windows, PresentMon). Чого виміряти не вдалося, про те
аналізатор мовчить або прямо каже «невідомо», а не вгадує.
"""
from __future__ import annotations

import os
import shutil
import time

import engine as E
from i18n import tr

PCIE_LANE_MBPS = {1: 250, 2: 500, 3: 985, 4: 1969, 5: 3938}  # корисна пропускна здатність однієї лінії, МБ/с
HIST_KEEP = 40


def _f(key: str, level: str, fix=None, **kw) -> dict:
    """Висновок у форматі «Чому лагає?» (diag.f.<key>.t / .d)."""
    return dict(key=key, level=level, fix=fix, kw=kw)


# ───────────────────────── P106 Driver Analyzer ─────────────────────────
def driver_report(hw: dict, pr: dict) -> dict:
    """Стан майнінгової карти за PCI ID, драйвером і тим, що бачать DirectX і Vulkan.
    pr — результат gpuinfo.probe(). -> {model, driver_name, driver, dx12, vulkan, vk_api, display, rows: [(рівень,
    ключ, kw)]}; ключі — gd.<ключ>.t / .d."""
    import gpuinfo as GI
    hw = hw or {}
    mining = (hw.get("mining") or [{}])[0]
    s = GI.summary(pr or {})
    rows = []
    model = mining.get("model") or ""
    drv_name = s.get("gpu") or mining.get("name") or ""
    if model and drv_name and model.lower() not in drv_name.lower():
        rows.append(("info", "pci_name", dict(model=model, name=drv_name)))
    elif model:
        rows.append(("ok", "pci", dict(model=model)))
    if not isinstance(pr, dict) or "dxgi" not in pr:  # перевірки ще не було — про DirectX і Vulkan нічого не кажемо
        return dict(model=model, driver_name=drv_name, driver="", dx12=None, vulkan=None, vk_api="", display="",
                    rows=rows, probed=False)
    if not s.get("gpu"):
        rows.append(("bad", "no_dxgi", dict(model=model or "GPU")))
    else:
        if s.get("dx12"):
            rows.append(("ok", "dx12", {}))
        elif s.get("dx12") is False:
            rows.append(("warn", "no_dx12", {}))
        if s.get("vulkan"):
            rows.append(("ok", "vulkan", dict(api=s.get("vk_api") or "?", driver=s.get("driver") or "?")))
        else:
            rows.append(("warn", "no_vulkan", {}))
        vram = s.get("vram_mb") or 0
        if vram and model.startswith("P106-100") and vram < 5000:
            rows.append(("warn", "vram_small", dict(mb=vram)))
    disp = s.get("display") or ""
    if "basic display" in disp.lower() or "basic render" in disp.lower():
        rows.append(("bad", "igpu_basic", dict(name=disp)))
    elif disp:
        rows.append(("ok", "display", dict(name=disp)))
    elif s.get("gpu"):
        rows.append(("warn", "no_display", {}))
    dxgi = (pr or {}).get("dxgi") or []
    nv = [a for a in dxgi if a.get("ven") == GI.NVIDIA and not a.get("software")]
    if len(nv) > 1:
        rows.append(("info", "multi_nv", dict(n=len(nv))))
    for err in (s.get("errors") or [])[:2]:
        rows.append(("warn", "probe_err", dict(err=str(err)[:160])))
    return dict(model=model, driver_name=drv_name, driver=s.get("driver") or "", dx12=s.get("dx12"),
                vulkan=s.get("vulkan"), vk_api=s.get("vk_api") or "", display=disp, rows=rows, probed=True)


def driver_findings(hw: dict, pr: dict) -> list:
    """Те саме — висновками для «Чому лагає?» і перевірки ПК (лише проблеми)."""
    out = []
    rep = driver_report(hw, pr)
    for level, key, kw in rep["rows"]:
        if level in ("bad", "warn") and key in ("no_dxgi", "no_vulkan", "no_dx12", "igpu_basic", "vram_small"):
            out.append(_f(f"gd_{key}", level, ("hint", "mining"), **dict({"model": rep["model"] or "GPU"}, **kw)))
    return out


# ───────────────────────── PCIe Link Analyzer ─────────────────────────
def pcie_eval(samples: list) -> dict:
    """samples — показники NVML раз на секунду (gpubench.Nvml.read). Карта знижує покоління PCIe у простої, тож
    висновок — лише за секундами під навантаженням (util ≥ 50%). -> {gen, width, max_gen, max_width, load_gen,
    load_width, peak_mbps, link_mbps, share, n}"""
    have = [s for s in samples if s.get("pcie_gen")]
    if not have:
        return {}
    load = [s for s in have if (s.get("util") or 0) >= 50] or []
    last = have[-1]
    res = dict(gen=last.get("pcie_gen"), width=last.get("pcie_width"), max_gen=last.get("pcie_max_gen"),
               max_width=last.get("pcie_max_width"), n=len(load))
    if load:
        res["load_gen"] = max(s.get("pcie_gen") or 0 for s in load)
        res["load_width"] = max(s.get("pcie_width") or 0 for s in load)
        tput = [((s.get("pcie_tx") or 0) + (s.get("pcie_rx") or 0)) / 1024 for s in load]  # КБ/с -> МБ/с
        res["peak_mbps"] = round(max(tput)) if tput else 0
        res["avg_mbps"] = round(sum(tput) / len(tput)) if tput else 0
        link = PCIE_LANE_MBPS.get(res["load_gen"], 0) * (res["load_width"] or 0)
        res["link_mbps"] = link
        res["share"] = round(100 * res["avg_mbps"] / link) if link else 0
    return res


def screen_size() -> tuple:
    if E.IS_WIN:
        try:
            import ctypes
            u = ctypes.windll.user32
            w, h = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    return 1920, 1080


def frame_copy_mbps(width: int, height: int, fps: float) -> int:
    """Скільки МБ/с займає передача готових кадрів на вбудовану графіку (монітор підключено до неї): 4 байти на піксель."""
    return round(width * height * 4 * fps / 2**20)


def pcie_findings(ev: dict, hw: dict, fps: float = 0) -> list:
    out = []
    if not ev:
        return out
    mining = bool((hw or {}).get("mining_gpu"))
    if ev.get("load_width") and ev.get("max_width") and ev["load_width"] < ev["max_width"]:
        out.append(_f("pcie_narrow", "warn", ("hint", "pcie"), cur=ev["load_width"], max=ev["max_width"]))
    if ev.get("load_gen") and ev.get("max_gen") and ev["load_gen"] < ev["max_gen"]:
        out.append(_f("pcie_slow", "warn", ("hint", "pcie"), cur=ev["load_gen"], max=ev["max_gen"]))
    if ev.get("share", 0) >= 70:
        out.append(_f("pcie_full", "bad" if ev["share"] >= 85 else "warn", None, share=ev["share"],
                      mbps=ev.get("avg_mbps", 0), link=ev.get("link_mbps", 0), gen=ev.get("load_gen"),
                      width=ev.get("load_width")))
    if mining and ev.get("link_mbps") and fps:
        w, h = screen_size()
        copy = frame_copy_mbps(w, h, fps)
        if copy >= 0.25 * ev["link_mbps"]:
            out.append(_f("pcie_copy", "info", None, mbps=copy, link=ev["link_mbps"], fps=round(fps)))
    return out


# ───────────────────────── GPU Memory Analyzer ─────────────────────────
def memory_findings(nvml: list, render: dict, hw: dict, avail_mb: float = None) -> list:
    """Відеопам'ять карти (NVML), спільна пам'ять процесу гри (лічильники GPU Process Memory) і вільна RAM. Коли
    виділеної пам'яті забракло, драйвер кладе ресурси в оперативну («спільну») — кожне звернення до них іде через PCIe,
    звідси фризи."""
    out = []
    used = [s.get("vram_used") for s in nvml if s.get("vram_used")]
    total = next((s.get("vram_total") for s in nvml if s.get("vram_total")), 0)
    shared = (render or {}).get("shared_mb") or 0
    if used and total:
        peak = max(used)
        if peak >= 0.95 * total:
            out.append(_f("vram_full", "bad" if shared >= 256 else "warn", None, used=f"{peak / 1024:.1f}",
                          total=f"{total / 1024:.0f}"))
    if shared >= 512 and (not total or not used or max(used) >= 0.85 * total):
        out.append(_f("vram_spill", "bad", None, mb=shared))
    total_ram = ((hw or {}).get("ram_gb") or 0) * 1024
    if avail_mb is not None and total_ram and avail_mb < 0.1 * total_ram and shared >= 256:
        out.append(_f("ram_shared", "warn", ("page", "games"), free=f"{avail_mb / 1024:.1f}", mb=shared))
    return out


# ───────────────────────── мікрофризи: кадри PresentMon проти показників системи ─────────────────────────
def spike_times(frametimes: list) -> list:
    """Секунди від початку запису, у які були фризи (кадр у 2.5+ рази довший за медіану й довший за 25 мс)."""
    ft = [x for x in frametimes if 0.05 < x < 2000]
    if len(ft) < 30:
        return []
    med = sorted(ft)[len(ft) // 2]
    out, t = [], 0.0
    for x in ft:
        t += x
        if x > 2.5 * med and x > 25:
            out.append(t / 1000)
    return out


def spike_causes(spikes: list, samples: list, offset: float = 0.0) -> dict:
    """Чому фризи: для кожного фризу — що відбувалося в ту саму секунду (±1 с). samples — секундні заміри «Чому
    лагає?»; offset — на скільки секунд запис кадрів почався пізніше за заміри. -> {причина: кількість}
    причини: ram (підкачка), disk, vram (спільна пам'ять росте), cpu (ядро на 95%+), shader (на початку гри, без
    навантаження — компіляція шейдерів), other."""
    out: dict = {}
    if not spikes:
        return out
    n = len(samples)
    for t in spikes:
        i = int(t + offset)
        near = [samples[j] for j in range(max(0, i - 1), min(n, i + 2))]
        cause = "other"
        if any((s.get("pages_in") or 0) > 300 for s in near):
            cause = "ram"
        elif any((s.get("disk") or 0) >= 90 for s in near):
            cause = "disk"
        elif any((s.get("shared_d") or 0) >= 64 for s in near):
            cause = "vram"
        elif any((s.get("core_max") or 0) >= 97 for s in near):
            cause = "cpu"
        elif t < 45:
            cause = "shader"
        out[cause] = out.get(cause, 0) + 1
    return out


def stutter_findings(fstats: dict, causes: dict) -> list:
    out = []
    if not fstats:
        return out
    per_min = fstats.get("stutters_pm") or 0
    if per_min >= 3 or (fstats.get("smooth") or 100) < 55:
        main = max(causes.items(), key=lambda kv: kv[1])[0] if causes else "other"
        fix = {"ram": ("page", "games"), "disk": ("page", "cleanup"), "vram": None, "cpu": ("booster", "balance"),
               "shader": ("hint", "shaders"), "other": None}[main]
        out.append(_f(f"stutter_{main}", "bad" if per_min >= 10 else "warn", fix, n=fstats.get("stutters", 0),
                      pm=per_min, low=fstats.get("low1", 0), avg=fstats.get("avg", 0)))
    return out


# ───────────────────────── GPU Bottleneck History ─────────────────────────
def hist_entry(res: dict) -> dict:
    st = res.get("stats") or {}
    bn = res.get("bottleneck") or {}
    fr = res.get("frames") or {}
    rd = res.get("render") or {}
    return dict(ts=res.get("ts") or int(time.time()), game=res.get("game") or "", main=bn.get("main"),
                share=bn.get("share"), cpu=st.get("cpu"), core=st.get("core_max"), gpu=st.get("gpu"),
                vram=st.get("vram_used"), avg=fr.get("avg"), low1=fr.get("low1"), stutters_pm=fr.get("stutters_pm"),
                render=rd.get("verdict"), path=rd.get("path_text") or "", n=res.get("n", 0))


def add_history(res: dict) -> list:
    import features as F
    hist = list(F.CFG["diag_hist"] or [])
    hist.append(hist_entry(res))
    hist = hist[-HIST_KEEP:]
    F.CFG["diag_hist"] = hist
    return hist


def history(game: str = None) -> list:
    import features as F
    hist = [h for h in F.CFG["diag_hist"] or [] if isinstance(h, dict)]
    return [h for h in hist if not game or (h.get("game") or "").lower() == game.lower()]


def regression(hist: list) -> dict:
    """Останній замір гри гірший за середнє попередніх (≥ 15% середнього FPS або 1% low) — просідання продуктивності.
    -> {} або {game, metric, was, now, pct}"""
    if not hist:
        return {}
    last = hist[-1]
    prev = [h for h in hist[:-1] if (h.get("game") or "").lower() == (last.get("game") or "").lower()]
    for metric in ("avg", "low1"):
        vals = [h[metric] for h in prev[-5:] if h.get(metric)]
        if len(vals) >= 1 and last.get(metric):
            was = sum(vals) / len(vals)
            if was and last[metric] <= 0.85 * was:
                return dict(game=last["game"], metric=metric, was=round(was), now=round(last[metric]),
                            pct=round(100 * (1 - last[metric] / was)))
    return {}


# ───────────────────────── Shader Cache Manager ─────────────────────────
SHADER_EXTRA = [r"%LOCALAPPDATA%\..\LocalLow\NVIDIA\PerDriverVersion\GLCache",
                r"%LOCALAPPDATA%\..\LocalLow\Intel\ShaderCache", r"%LOCALAPPDATA%\mesa_shader_cache",
                r"%LOCALAPPDATA%\mesa_shader_cache_db"]
BACKUP_DIR = os.path.join(E.DATA_DIR, "shader-backup")


def shader_dirs() -> list:
    seen, out = set(), []
    for d in list(E.SHADER_DIRS) + SHADER_EXTRA:
        p = os.path.normpath(os.path.expandvars(d))
        if p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def _scan(path: str) -> dict:
    size = files = empty = 0
    newest = oldest = 0.0
    for dp, _dns, fns in os.walk(path):
        for n in fns:
            try:
                st = os.stat(os.path.join(dp, n))
            except OSError:
                continue
            files += 1
            size += st.st_size
            empty += st.st_size == 0
            newest = max(newest, st.st_mtime)
            oldest = st.st_mtime if not oldest else min(oldest, st.st_mtime)
    return dict(path=path, size=size, files=files, empty=empty, newest=newest, oldest=oldest)


DEMO_CACHES = [dict(path=r"C:\Users\Player\AppData\Local\D3DSCache", size=412 << 20, files=380, empty=0),
               dict(path=r"C:\Users\Player\AppData\LocalLow\NVIDIA\PerDriverVersion\DXCache", size=1650 << 20,
                    files=2900, empty=3),
               dict(path=r"C:\Users\Player\AppData\Local\NVIDIA\GLCache", size=96 << 20, files=210, empty=0)]


def shader_scan(driver: str = "") -> dict:
    """-> {caches: [{path, size, files, empty, newest, oldest}], total, empty, driver_changed, backup}
    driver_changed — драйвер NVIDIA змінився з минулої перевірки (тоді старі кеші — для попереднього драйвера)."""
    import features as F
    if not E.IS_WIN:
        caches = [dict(c, newest=time.time() - 3600, oldest=time.time() - 86400 * 40) for c in DEMO_CACHES]
    else:
        caches = [_scan(p) for p in shader_dirs() if os.path.isdir(p)]
        caches = [c for c in caches if c["files"]]
    st = dict(F.CFG["shader_state"] or {})
    changed = bool(driver and st.get("driver") and st["driver"] != driver)
    if driver and st.get("driver") != driver:
        st.update(driver=driver, since=int(time.time()), prev=st.get("driver", ""))
        F.CFG["shader_state"] = st
    return dict(caches=caches, total=sum(c["size"] for c in caches), empty=sum(c["empty"] for c in caches),
                driver_changed=changed or bool(st.get("prev") and time.time() - st.get("since", 0) < 7 * 86400),
                driver=driver, prev_driver=st.get("prev", ""), backup=last_backup())


def last_backup() -> dict:
    try:
        items = sorted(d for d in os.listdir(BACKUP_DIR) if d.isdigit())
    except OSError:
        return {}
    if not items:
        return {}
    folder = os.path.join(BACKUP_DIR, items[-1])
    size = sum(os.path.getsize(os.path.join(dp, n)) for dp, _d, fns in os.walk(folder) for n in fns)
    return dict(ts=int(items[-1]), dir=folder, size=size)


def shader_backup_clear(log) -> dict:
    """Кеш — у резервну копію (переміщенням, тож місце на диску не подвоюється), а не в нікуди. Файли, які зараз
    тримає запущена гра чи драйвер, пропускаються. Попередня резервна копія видаляється: зберігаємо одну, останню."""
    if not E.IS_WIN or E.DRY_RUN:
        log("  [dry-run] " + ", ".join(os.path.basename(c["path"]) for c in DEMO_CACHES))
        return dict(moved=sum(c["files"] for c in DEMO_CACHES), size=sum(c["size"] for c in DEMO_CACHES), skipped=0)
    old = last_backup()
    stamp = str(int(time.time()))
    dest_root = os.path.join(BACKUP_DIR, stamp)
    moved = skipped = size = 0
    index = []
    for i, src in enumerate(p for p in shader_dirs() if os.path.isdir(p)):
        dest = os.path.join(dest_root, str(i))
        index.append((str(i), src))
        for dp, _dns, fns in os.walk(src):
            for n in fns:
                s = os.path.join(dp, n)
                d = os.path.join(dest, os.path.relpath(s, src))
                try:
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    sz = os.path.getsize(s)
                    shutil.move(s, d)
                    moved += 1
                    size += sz
                except OSError:
                    skipped += 1
        log(f"  · {src}")
    os.makedirs(dest_root, exist_ok=True)
    with open(os.path.join(dest_root, "index.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(f"{k}\t{v}" for k, v in index))
    if old and moved:
        shutil.rmtree(old["dir"], ignore_errors=True)
    log(tr("sc.cleared", n=moved, mb=f"{size / 2**20:.0f}", skipped=skipped))
    return dict(moved=moved, size=size, skipped=skipped)


def shader_restore(log) -> dict:
    """Повертає останню резервну копію на місце. Файл, який драйвер уже створив заново, не перезаписується (новіший)."""
    b = last_backup()
    if not b:
        return dict(restored=0)
    if not E.IS_WIN or E.DRY_RUN:
        log("  [dry-run] restore " + b["dir"])
        return dict(restored=1)
    restored = kept = 0
    try:
        with open(os.path.join(b["dir"], "index.txt"), encoding="utf-8") as f:
            index = dict(line.rstrip("\n").split("\t", 1) for line in f if "\t" in line)
    except OSError:
        index = {}
    for key, target in index.items():
        src_root = os.path.join(b["dir"], key)
        if not os.path.isdir(src_root) or not target:
            continue
        for dp, _dns, fns in os.walk(src_root):
            for n in fns:
                s = os.path.join(dp, n)
                d = os.path.join(target, os.path.relpath(s, src_root))
                try:
                    if os.path.exists(d):
                        kept += 1
                        continue
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.move(s, d)
                    restored += 1
                except OSError:
                    kept += 1
    shutil.rmtree(b["dir"], ignore_errors=True)
    log(tr("sc.restored", n=restored, kept=kept))
    return dict(restored=restored, kept=kept)


def shader_advice(scan: dict) -> list:
    """Поради (ключі sc.a.*): кеш порожніх файлів (пошкоджений), щойно оновлено драйвер, кеш дуже великий."""
    out = []
    if scan.get("empty", 0) >= 3:
        out.append(("warn", "damaged", dict(n=scan["empty"])))
    if scan.get("driver_changed"):
        out.append(("info", "driver", dict(old=scan.get("prev_driver") or "?", new=scan.get("driver") or "?")))
    if scan.get("total", 0) >= 8 << 30:
        out.append(("info", "huge", dict(gb=f"{scan['total'] / 2**30:.1f}")))
    if not out:
        out.append(("ok", "fine", dict(mb=f"{scan.get('total', 0) / 2**20:.0f}")))
    return out
