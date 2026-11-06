"""
OptimaX — «Перевірка ПК перед покупкою»: покроковий майстер для нового чи вживаного комп'ютера.

Кроки йдуть у порядку ТЗ: характеристики → відповідність заявленому → процесор → відеокарта → відеопам'ять → пам'ять →
стан дисків → швидкість диска → батарея (ноутбук) → екран → клавіатура → камера, мікрофон і звук → комбінований
стрес-тест → підсумок. Кожен крок має статус PASS / WARN / FAIL / SKIPPED / N/A. Статус береться з результатів тестів
Hardware Center, зроблених після початку перевірки (старіші результати — не про цей сеанс), а візуальні кроки людина
позначає сама. На ноутбуці з двома відеокартами крок «Відеокарта» вимагає двох тестів — дискретної й вбудованої — і
пройдений, лише якщо дискретна карта справді малювала під навантаженням (gpuselect: «підтверджено»): найчастіший
обман із вживаними ноутбуками — мертва чи вимкнена дискретна карта.
"""
from __future__ import annotations

import re
import time

import hwtests as HT
from i18n import tr

STEPS = (("specs", "auto"), ("claimed", "manual"), ("cpu", "auto"), ("gpu", "auto"), ("vram", "auto"), ("ram", "auto"),
         ("disk_health", "auto"), ("disk_bench", "auto"), ("battery", "auto"), ("display", "manual"),
         ("keyboard", "manual"), ("av", "manual"), ("combined", "auto"), ("summary", "auto"))
SOURCES = {"specs": ("info",), "cpu": ("cpu_multi", "cpu_stress"), "vram": ("vram",), "ram": ("ram",),
           "disk_health": ("storage_health",), "disk_bench": ("disk_bench",), "battery": ("battery",),
           "display": ("display_pixels",), "keyboard": ("periph_keyboard",),
           "av": ("periph_camera", "periph_mic", "periph_speakers"), "combined": ("stress_combined",)}
SECTION = {"specs": "info", "cpu": "cpu", "gpu": "gpu", "vram": "vram", "ram": "ram", "disk_health": "storage",
           "disk_bench": "storage", "battery": "laptop", "display": "display", "keyboard": "peripherals",
           "av": "peripherals", "combined": "stress"}


def new_session(cfg) -> dict:
    s = dict(ts=int(time.time()), claimed={}, manual={}, skipped=[])
    cfg["inspect"] = s
    return s


def _tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in
            {"intel", "amd", "nvidia", "geforce", "core", "tm", "r", "cpu", "processor", "with", "radeon", "graphics",
             "gen", "th", "the", "laptop", "gpu"}}


def _num(s) -> float:
    m = re.search(r"\d+(?:[.,]\d+)?", str(s or ""))
    return float(m.group(0).replace(",", ".")) if m else 0.0


def compare_claimed(claimed: dict, hw: dict) -> list:
    """Заявлене продавцем проти визначеного OptimaX -> [(поле, заявлено, визначено, статус)].
    Порожнє поле — SKIPPED. Процесор і відеокарта — за номером моделі; пам'ять ±0.6 ГБ (частину забирає вбудована
    графіка); диски — сумарний обсяг ±8% (ГБ у продавця — десяткові, у Windows — двійкові)."""
    hw = hw or {}
    out = []
    c = (claimed or {}).get("cpu", "").strip()
    if c:
        want = {w for w in _tokens(c) if any(ch.isdigit() for ch in w)} or _tokens(c)
        got = _tokens(hw.get("cpu") or "")
        out.append(("cpu", c, hw.get("cpu") or "", HT.PASS if want and want <= got else HT.FAIL))
    else:
        out.append(("cpu", "", hw.get("cpu") or "", HT.SKIPPED))
    g = (claimed or {}).get("gpu", "").strip()
    names = [n for n, _, _ in hw.get("gpus") or []]
    if g:
        want = {w for w in _tokens(g) if any(ch.isdigit() for ch in w)} or _tokens(g)
        ok = any(want and want <= _tokens(n) for n in names)
        out.append(("gpu", g, ", ".join(names), HT.PASS if ok else HT.FAIL))
    else:
        out.append(("gpu", "", ", ".join(names), HT.SKIPPED))
    r = _num((claimed or {}).get("ram"))
    have = float(hw.get("ram_gb") or 0)
    if r:
        out.append(("ram", f"{r:g} GB", f"{have:.1f} GB", HT.PASS if abs(have - r) <= 0.6 + r * 0.02 else HT.FAIL))
    else:
        out.append(("ram", "", f"{have:.1f} GB", HT.SKIPPED))
    d = _num((claimed or {}).get("disk"))
    if d and str((claimed or {}).get("disk", "")).lower().find("tb") >= 0:
        d *= 1000
    total = sum(float(x.get("size_gb") or 0) for x in hw.get("disks") or [])
    if d:
        out.append(("disk", f"{d:g} GB", f"{total:.0f} GB", HT.PASS if total and abs(total - d) <= d * 0.08 + 8
                    else HT.FAIL))
    else:
        out.append(("disk", "", f"{total:.0f} GB", HT.SKIPPED))
    return out


def gpu_status(bench: list, since: int, hw: dict, ads: list) -> tuple:
    """GPU-тести після початку перевірки -> (статус, причина-ключ). Гібрид: потрібні обидві карти, дискретна —
    підтверджено."""
    runs = [b for b in bench or [] if (b.get("ts") or 0) >= since]
    if not runs:
        return None, ""
    def st_of(b):
        v = b.get("verdict") or "bench"
        return {"bench": HT.PASS, "stable": HT.PASS, "errors": HT.FAIL, "crash": HT.FAIL, "hot": HT.WARN,
                "throttle": HT.WARN}.get(v, HT.NA)
    if len(ads) > 1:
        strong = [a for a in ads if a.get("kind") in ("dgpu", "mining")]
        weak = [a for a in ads if a.get("kind") == "igpu"]
        d_runs = [b for b in runs if any(b.get("adapter_key") == a["key"] for a in strong)]
        i_runs = [b for b in runs if any(b.get("adapter_key") == a["key"] for a in weak)]
        d_ok = [b for b in d_runs if (b.get("gpu_check") or {}).get("status") in ("confirmed", "renderer")]
        if strong and d_runs and not d_ok:
            return HT.FAIL, "insp.gpu.dgpu_unconfirmed"
        if strong and not d_runs:
            return None, "insp.gpu.need_dgpu"
        if weak and not i_runs:
            return None, "insp.gpu.need_igpu"
        return HT.worst([st_of(b) for b in d_ok + i_runs]), ""
    return HT.worst([st_of(b) for b in runs]), ""


def step_status(step: str, sess: dict, last: dict, hw: dict, bench: list = None, ads: list = None) -> tuple:
    """-> (статус або None — ще не робили, підказка-ключ)."""
    sess = sess or {}
    since = int(sess.get("ts") or 0)
    if step in (sess.get("skipped") or []):
        return HT.SKIPPED, ""
    if step in (sess.get("manual") or {}):
        return sess["manual"][step], ""
    if step == "battery" and not (hw or {}).get("laptop"):
        return HT.NA, "insp.battery.na"
    if step == "claimed":
        cmp_ = compare_claimed(sess.get("claimed") or {}, hw)
        if all(s == HT.SKIPPED for *_x, s in cmp_):
            return None, ""
        return HT.worst([s for *_x, s in cmp_]), ""
    if step == "gpu":
        return gpu_status(bench, since, hw, ads or [])
    if step == "summary":
        return None, ""
    res = [last.get(t) for t in SOURCES.get(step, ()) if last.get(t) and (last[t].get("ts") or 0) >= since]
    if not res:
        return None, ""
    return HT.worst([r["status"] for r in res]), ""


def overall(statuses: dict) -> str:
    vals = [s for k, s in statuses.items() if k != "summary" and s]
    if not vals:
        return HT.NA
    return HT.worst(vals)


def progress(statuses: dict) -> tuple:
    done = sum(1 for k, s in statuses.items() if k != "summary" and s)
    return done, len(STEPS) - 1


def verdict_key(st: str, missing: int) -> str:
    if missing:
        return "insp.v.incomplete"
    return {HT.PASS: "insp.v.pass", HT.WARN: "insp.v.warn", HT.FAIL: "insp.v.fail"}.get(st, "insp.v.incomplete")
