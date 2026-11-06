"""
OptimaX — Smart Performance Diagnosis і поради щодо андервольтингу.

Об'єднує те, що вже вимірює OptimaX під час гри: датчики (hwtests.Sensors / «Чому лагає?»), кадри PresentMon (FPS,
1% low, фризи), на якій карті малює гра (gpuinfo), фонові процеси (procmon) і збої відеодрайвера (crashlog). Для
кожного обмеження — що саме обмежує, які показники це підтверджують, наскільки впевнений висновок, що можна зробити,
очікуваний результат і ризики. Приросту FPS не обіцяємо: висновок «вузьке місце — відеокарта» не означає «+20 FPS».

Андервольтинг: OptimaX нічого не змінює сама (ні напругу, ні BIOS) і не обходить блокувань. Лише дивиться, чи є сенс
(тротлінг за температурою чи потужністю), чи це взагалі можливо на цьому залізі (за моделлю: ноутбучні Intel з 10-го
покоління часто мають заблоковане керування напругою — Plundervolt / «Undervolt Protection»), і як перевірити
стабільність після ручного налаштування — стрес-тестами Hardware Center.
"""
from __future__ import annotations

import re
from collections import Counter

import engine as E
from i18n import tr

CONF = ("high", "medium", "low")


def to_monitor(s: dict) -> dict:
    """Вимір hwtests.Sensors -> формат monitor.classify (лічильники «Чому лагає?»)."""
    avail = None
    if s.get("ram_total") and s.get("ram_used") is not None:
        avail = (s["ram_total"] - s["ram_used"]) * 1024
    return dict(cpu=s.get("util"), core_max=s.get("core_max", s.get("util")), gpu=s.get("gpu_util"), avail_mb=avail,
                pages_in=s.get("pages_in"), disk=s.get("disk"), temp=s.get("temp"), passive=s.get("passive"),
                limit=s.get("limit"), gpu_t=s.get("gpu_temp"))


def _conf(n: int, share: float) -> str:
    if n >= 30 and share >= 60:
        return "high"
    if n >= 10 and share >= 35:
        return "medium"
    return "low"


def item(key: str, conf: str, evidence: list, **kw) -> dict:
    """Один висновок: ключі pd.<key>.t / .what / .do / .gain / .risk, докази [(ключ, підстановки)]."""
    return dict(key=key, conf=conf, evidence=evidence, kw=kw)


def diagnose(samples: list, fps: dict = None, render: dict = None, procs: dict = None, hw: dict = None,
             gpu_resets: int = 0) -> list:
    """-> [висновок] від найважливішого. samples — виміри hwtests.Sensors або вже у форматі monitor (cpu, gpu, …)."""
    import monitor as M
    hw = hw or {}
    fps = fps or {}
    out = []
    ms = [to_monitor(s) if "util" in s or "gpu_util" in s else s for s in samples or []]
    n = len(ms)
    if n >= 5:
        b = M.bottleneck(ms, hw or {"ram_gb": 16})
        sh = b.get("shares") or {}
        main = b.get("main")
        if main == "gpu":
            out.append(item("gpu", _conf(n, sh.get("gpu", 0)), [("pd.e.gpu", dict(p=sh.get("gpu", 0)))]))
        elif main == "cpu":
            out.append(item("cpu", _conf(n, sh.get("cpu", 0)), [("pd.e.cpu", dict(p=sh.get("cpu", 0)))]))
        elif main == "thermal":
            temps = [s.get("temp") for s in ms if s.get("temp")] or [0]
            gt = [s.get("gpu_t") for s in ms if s.get("gpu_t")] or [0]
            out.append(item("thermal", _conf(n, sh.get("thermal", 0)),
                            [("pd.e.thermal", dict(p=sh.get("thermal", 0), c=round(max(temps)), g=round(max(gt))))]))
        elif main == "ram":
            out.append(item("ram", _conf(n, sh.get("ram", 0)), [("pd.e.ram", dict(p=sh.get("ram", 0)))]))
        elif main == "disk":
            out.append(item("disk", _conf(n, sh.get("disk", 0)), [("pd.e.disk", dict(p=sh.get("disk", 0)))]))
        elif main == "power":
            out.append(item("power", _conf(n, sh.get("power", 0)), [("pd.e.power", dict(p=sh.get("power", 0)))]))
        elif main == "none" and fps.get("avg"):
            out.append(item("cap", "medium", [("pd.e.cap", dict(fps=round(fps["avg"])))]))
        vr = [(s.get("vram_used"), s.get("vram_total")) for s in samples or [] if s.get("vram_used") and s.get("vram_total")]
        if vr:
            peak = max(u / t for u, t in vr)
            if peak >= 0.95:
                out.append(item("vram", "medium" if peak >= 0.98 else "low", [("pd.e.vram", dict(p=round(peak * 100)))]))
        thr = Counter(x for s in samples or [] for x in (s.get("gpu_throttle") or []))
        if thr.get("power") and main != "power":
            out.append(item("gpu_power", "medium", [("pd.e.gpu_power", dict(n=thr["power"]))]))
    if (render or {}).get("verdict") in ("igpu", "warp"):
        out.insert(0, item("igpu", "high", [("pd.e.igpu", dict(path=render.get("path_text") or ""))]))
    bad = [p for p in (procs or {}).get("processes") or [] if p.get("suspect")]
    if bad:
        out.append(item("background", "medium" if len(bad) == 1 else "high",
                        [("pd.e.bg", dict(names=", ".join(p["name"] for p in bad[:3])))]))
    if gpu_resets:
        out.append(item("driver", "medium", [("pd.e.tdr", dict(n=gpu_resets))]))
    if fps.get("stutters_pm") and fps["stutters_pm"] >= 6 and not any(o["key"] in ("disk", "ram", "background")
                                                                      for o in out):
        out.append(item("stutter", "low", [("pd.e.stutter", dict(n=fps["stutters_pm"]))]))
    return out


def explain(it: dict) -> dict:
    """Висновок -> тексти для людини."""
    k = it["key"]
    return dict(title=tr(f"pd.{k}.t"), what=tr(f"pd.{k}.what"), do=tr(f"pd.{k}.do"), gain=tr(f"pd.{k}.gain"),
                risk=tr(f"pd.{k}.risk"), conf=tr(f"pd.conf.{it['conf']}"),
                evidence=[tr(e, **kw) for e, kw in it.get("evidence") or []])


# ───────────────────────── андервольтинг ─────────────────────────
def cpu_family(name: str) -> dict:
    """Що відомо про керування напругою за моделлю процесора (без читання MSR — OptimaX драйвер не встановлює)."""
    n = name or ""
    m = re.search(r"i[3579]-(\d{4,5})([A-Z]{0,2})", n)
    if m:
        num, suffix = m.group(1), m.group(2)
        gen = int(num[:2]) if len(num) == 5 else int(num[0])
        mobile = suffix.startswith(("H", "U", "P", "G")) or "HX" in suffix
        if gen >= 10 and mobile:
            return dict(vendor="intel", gen=gen, mobile=True, state="locked_likely")
        if gen >= 12 and not mobile:
            return dict(vendor="intel", gen=gen, mobile=False, state="bios")
        return dict(vendor="intel", gen=gen, mobile=mobile, state="possible")
    if re.search(r"Core\(TM\) Ultra|Core Ultra", n):
        return dict(vendor="intel", gen=14, mobile=True, state="locked_likely")
    if re.search(r"Ryzen", n, re.I):
        mobile = bool(re.search(r"\d{4}(H|HS|HX|U)\b", n))
        return dict(vendor="amd", mobile=mobile, state="curve_optimizer" if not mobile else "limited")
    return dict(vendor="other", state="unknown")


def undervolt_advice(hw: dict, cpu_res: dict = None, gpu_res: dict = None) -> dict:
    """-> {state, need, reasons: [ключі], steps: [ключі], gpu: ключ}. Нічого не змінює."""
    hw = hw or {}
    fam = cpu_family(hw.get("cpu") or "")
    keys = {f[1] for f in (cpu_res or {}).get("findings") or []}
    need = bool(keys & {"hwc.f.thermal", "hwc.f.clock_drop", "hwc.f.cpu_hot", "hwc.f.power_limit"})
    reasons = []
    if "hwc.f.thermal" in keys or "hwc.f.cpu_hot" in keys:
        reasons.append("uv.r.thermal")
    if "hwc.f.power_limit" in keys:
        reasons.append("uv.r.power")
    if not cpu_res:
        reasons.append("uv.r.no_test")
    elif not need:
        reasons.append("uv.r.fine")
    steps = {"locked_likely": ["uv.s.locked", "uv.s.bios", "uv.s.verify"],
             "bios": ["uv.s.bios_intel", "uv.s.verify"],
             "possible": ["uv.s.throttlestop", "uv.s.verify"],
             "curve_optimizer": ["uv.s.curve", "uv.s.verify"],
             "limited": ["uv.s.amd_laptop", "uv.s.verify"],
             "unknown": ["uv.s.unknown", "uv.s.verify"]}[fam["state"]]
    gkeys = {f[1] for f in (gpu_res or {}).get("findings") or []}
    gpu = "uv.g.hot" if gkeys & {"hwc.f.gpu_hot", "hwc.f.gpu_throttle"} else "uv.g.ok" if gpu_res else "uv.g.no_test"
    if hw.get("nvidia") or hw.get("amd_gpu"):
        gpu_tool = "uv.g.curve"
    else:
        gpu_tool = ""
    return dict(state=fam["state"], family=fam, need=need, reasons=reasons, steps=steps, gpu=gpu, gpu_tool=gpu_tool)
