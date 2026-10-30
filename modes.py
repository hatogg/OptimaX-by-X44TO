"""
OptimaX — режими оптимізації: «Безпечний», «Ігровий», «Слабкий ПК», «Ручний».

Режим — не фіксований список. План складається для конкретного ПК:
• залізо й Windows: те, що не підходить (compat «na»/«block»), не потрапляє в план;
• що обмежує FPS (діагностика «Чому лагає?» або тест FPS у грі): якщо продуктивність упирається, наприклад,
  у відеокарту, твіки процесора FPS не додадуть — і не застосовуються; при перегріві — нічого, що гріє;
• що довела розумна оптимізація на цьому ПК: шкідливе тут не пропонується ніколи, а те, що двічі не дало
  жодного ефекту понад похибку, — не пропонується в «Ігровому»;
• конфлікти: із двох змін, що перезаписують одна одну, лишається одна.
Кожна виключена зміна має пояснення — його видно під планом.

Лише логіка: тести перевіряють плани на демо-залізі без інтерфейсу.
"""
from __future__ import annotations

import abtest as AB
import engine as E
import features as F

MODES = ("safe", "gaming", "lowend", "manual")
SMART_BY_DEFAULT = {"gaming": True, "lowend": True}  # приріст має бути доведений замірами

# Що реально допомагає, коли продуктивність упирається в певний ресурс. Інші зміни продуктивності при цьому
# обмеженні FPS не додають (лише гріють чи витрачають енергію) — у плані їх не буде.
FOR_LIMIT = {
    "cpu": {"cpu_scheduling", "rt_boost", "system_responsiveness", "core_parking", "power_throttling",
            "ultimate_power", "turbo_aggressive", "processor_idle", "min_cpu_state", "hybrid_cores",
            "disable_services", "bg_apps_off", "sysmain_smart", "defender_limit", "timer_resolution",
            "dynamic_tick", "registry_boost", "disable_vbs", "lock_power"},
    "gpu": {"gpu_hw_scheduling", "msi_gpu", "fso_global", "windowed_opt", "vrr_windowed", "amd_ulps", "pcie_aspm",
            "disable_xbox_gamebar", "disable_vbs"},
    "ram": {"memory_compression", "optimize_pagefile", "bg_apps_off", "sysmain_smart", "disable_services",
            "registry_boost", "visual_fx_perf", "transparency_off"},
    "disk": {"disable_search_index", "sysmain_smart", "ntfs_lastaccess", "ntfs_8dot3", "defender_limit",
             "optimize_pagefile", "memory_compression"},
    "power": {"ultimate_power", "power_throttling", "laptop_ac_max", "min_cpu_state", "lock_power", "pcie_aspm"},
    "thermal": set(),
}
# Корисні за будь-якого обмеження: менше фонової роботи, режим гри Windows.
UNIVERSAL = {"game_mode_on", "windowed_opt", "nvidia_telemetry", "edge_bg_off", "startup_delay", "sysmain_smart"}
# Те, що підвищує температуру й споживання, — не для перегрітого ПК і не для ноутбука
HOT = set(F.HOT)
CONFIDENT = 50  # % часу, після якого обмеження вважаємо головним і фільтруємо за ним


def latest_bottleneck(cfg=None) -> dict:
    """Найсвіжіше «що обмежує FPS»: з діагностики «Чому лагає?» або з тесту FPS у грі (обидва зберігають ts)."""
    cfg = cfg or F.CFG
    cands = []
    d = cfg["diag_last"] or {}
    if d.get("bottleneck"):
        cands.append((d.get("ts", 0), dict(d["bottleneck"], source="diag", game=d.get("game"))))
    for exe, t in (cfg["fps_tests"] or {}).items():
        for k in ("after", "before"):
            r = (t or {}).get(k) or {}
            if r.get("bottleneck"):
                cands.append((r.get("ts", 0), dict(r["bottleneck"], source="fps", game=exe)))
    return max(cands, key=lambda c: c[0])[1] if cands else {}


def lowend(hw: dict) -> bool:
    hw = hw or {}
    return hw.get("device") == "old" or (hw.get("ram_gb") or 16) <= 8 or bool(hw.get("hdd"))


def recommended(hw: dict) -> str:
    return "lowend" if lowend(hw) else "gaming"


def _base(mode: str, hw: dict) -> list:
    hw = hw or {}
    laptop = bool(hw.get("laptop")) or hw.get("device") == "laptop"
    if mode == "safe":
        return [t.id for t in E.TWEAKS if "L" in t.p and t.impact == "safe" and not t.risky and t.reversible]
    if mode == "lowend":
        return [t.id for t in E.TWEAKS if "O" in t.p]
    if mode == "gaming":
        dev = "laptop" if laptop else hw.get("device") if hw.get("device") in ("gaming", "xeon") else "gaming"
        ans = {"device": dev, "usage": "games", "goal": "fps", "av": "defender", "ms": []}
        return F.build_plan(ans, hw)
    return []


def plan(mode: str, hw: dict = None, bottleneck: dict = None, evidence: dict = None, applied=None) -> dict:
    """-> {mode, ids, excluded: [{id, why, kw}], smart, limit, proven}.
    why: na | block | harmful | no_effect | limit | hot | conflict | not_reversible."""
    hw = hw or {}
    evidence = F.CFG["tweak_evidence"] if evidence is None else evidence
    bn = bottleneck if bottleneck is not None else latest_bottleneck()
    out = {"mode": mode, "ids": [], "excluded": [], "smart": SMART_BY_DEFAULT.get(mode, False),
           "limit": None, "proven": []}
    if mode == "manual" or mode not in MODES:
        return out
    limit = bn.get("main") if bn and (bn.get("share") or 0) >= CONFIDENT else None
    if limit in FOR_LIMIT:
        out["limit"] = limit
    keep = []

    def drop(tid, why, **kw):
        out["excluded"].append({"id": tid, "why": why, "kw": kw})

    base = _base(mode, hw)
    if mode == "lowend" and out["limit"] in ("ram", "disk"):  # слабкий ПК упирається в пам'ять чи диск — і їх
        base += sorted(i for i in FOR_LIMIT[out["limit"]] if i in E.BY_ID)
    for tid in dict.fromkeys(base):
        t = E.BY_ID.get(tid)
        if t is None:
            continue
        state, _reason = E.compat(t, hw)
        if state in ("na", "block"):
            drop(tid, state)
            continue
        if mode == "safe" and not t.reversible:
            drop(tid, "not_reversible")
            continue
        ev = AB.evidence_state((evidence or {}).get(tid))
        if ev == "harmful":
            drop(tid, "harmful")
            continue
        if ev == "no_effect" and mode == "gaming":
            drop(tid, "no_effect")
            continue
        perf = t.group in AB.PERF_GROUPS and t.group != "visual"
        if tid in HOT and limit == "thermal" and mode != "safe":  # профіль ноутбука й так без агресивних змін
            drop(tid, "hot")
            continue
        if perf and out["limit"] and out["limit"] != "thermal" and mode == "gaming" and tid not in UNIVERSAL:
            useful = FOR_LIMIT[out["limit"]] | FOR_LIMIT.get(bn.get("second") or "", set())
            if tid not in useful:
                drop(tid, "limit", limit=out["limit"])
                continue
        if ev == "proven":
            out["proven"].append(tid)
        keep.append(tid)
    keep, clashes = E.resolve_conflicts(keep, applied)
    for tid, other in clashes:
        drop(tid, "conflict", other=other)
    out["ids"] = keep
    return out
