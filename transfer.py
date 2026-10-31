"""
OptimaX — перенесення налаштувань: свій набір оптимізацій і налаштувань програми — у файл, а потім на інший ПК чи
після перевстановлення Windows.

У файлі: які оптимізації застосовано (лише id з каталогу OptimaX — без значень реєстру й шляхів системи), налаштування
режиму гри, чистильника пам'яті, бібліотеки, «Моїх ігор» (шляхи exe й позначки) і режимів ігор на майнінговій карті.
Під час імпорту нічого в системі не змінюється без перегляду: оптимізації відкриваються у звичайному «Перегляді змін»
(з перевіркою сумісності з цим залізом), «Мої ігри» додаються лише ті, чий exe є на цьому ПК, а режими ігор на
майнінговій карті — лише запам'ятовуються й застосовуються, коли їх виберуть.
"""
from __future__ import annotations

import json
import os
import time

import engine as E
import features as F

FORMAT = "optimax-settings"
BOOSTER_KEYS = ("services", "kill", "purge", "power", "timer", "auto", "dnd", "balance", "profile", "found")
CLEANER_KEYS = ("enabled", "standby_mb", "free_mb")
GAME_FLAGS = ("prio", "dgpu", "fso", "boost", "cores", "profile")
LIB_KEYS = ("fps", "boost")


def applied_tweaks() -> list:
    return [t for t in E.JOURNAL.newest_first() if t in E.BY_ID][::-1]


def export_data() -> dict:
    import mining as MG
    games = [{k: g.get(k) for k in ("path",) + GAME_FLAGS if k in g} for g in F.CFG["games"] or []]
    m = F.CFG["mining"] or {}
    profs = {k: {f: v for f, v in p.items() if f in ("name", "mode", "rating")} for k, p in MG.profiles().items()}
    return {"format": FORMAT, "version": E.VERSION, "ts": int(time.time()), "tweaks": applied_tweaks(),
            "booster": {k: v for k, v in (F.CFG["booster"] or {}).items() if k in BOOSTER_KEYS},
            "cleaner": {k: v for k, v in (F.CFG["cleaner"] or {}).items() if k in CLEANER_KEYS},
            "library": {k: v for k, v in (F.CFG["library"] or {}).items() if k in LIB_KEYS},
            "games": games, "mining": {"auto": m.get("auto"), "check": m.get("check", True),
                                       "gl_driver": m.get("gl_driver", "d3d12"), "profiles": profs},
            "close_to_tray": bool(F.CFG["close_to_tray"]), "hotkeys": bool(F.CFG["hotkeys"])}


def export(path: str) -> dict:
    data = export_data()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return {"tweaks": len(data["tweaks"]), "games": len(data["games"])}


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("format")
    return data


def plan(data: dict, hw: dict = None) -> dict:
    """Що вийде на цьому ПК: tweaks — можна (ще не застосовані), done — уже застосовані, blocked — [(id, причина)]
    (шкодить цьому залізу / не для цієї Windows), unknown — id, яких ця версія OptimaX не знає; games — exe є,
    missing — exe немає."""
    hw = hw or {}
    res = dict(tweaks=[], done=[], blocked=[], unknown=[], games=[], missing=[])
    for tid in data.get("tweaks") or []:
        t = E.BY_ID.get(str(tid))
        if t is None:
            res["unknown"].append(str(tid))
        elif E.JOURNAL.has(t.id):
            res["done"].append(t.id)
        else:
            state, reason = E.compat(t, hw) if hw else ("ok", "")
            if state in ("na", "block"):
                res["blocked"].append((t.id, reason))
            else:
                res["tweaks"].append(t.id)
    for g in data.get("games") or []:
        p = str((g or {}).get("path") or "")
        (res["games"] if p.lower().endswith(".exe") and os.path.isfile(p) else res["missing"]).append(p)
    return res


def apply_settings(data: dict) -> dict:
    """Налаштування самої програми (не системи). -> {"keys": [...], "games": [шляхи для позначок]}"""
    changed = []
    for key, allowed in (("booster", BOOSTER_KEYS), ("cleaner", CLEANER_KEYS), ("library", LIB_KEYS)):
        src = data.get(key)
        if isinstance(src, dict):
            cur = dict(F.CFG[key] or {})
            cur.update({k: v for k, v in src.items() if k in allowed})
            F.CFG[key] = cur
            changed.append(key)
    m = data.get("mining")
    if isinstance(m, dict):
        cur = dict(F.CFG["mining"] or {})
        for k in ("auto", "check"):
            if isinstance(m.get(k), bool):
                cur[k] = m[k]
        if m.get("gl_driver") in ("d3d12", "zink"):
            cur["gl_driver"] = m["gl_driver"]
        profs = dict(cur.get("profiles") or {})
        import mining as MG
        for k, p in (m.get("profiles") or {}).items():
            if isinstance(k, str) and isinstance(p, dict):
                q = dict(profs.get(k.lower()) or {})
                if p.get("mode") in MG.MODES and not q.get("mode"):
                    q["imported_mode"] = p["mode"]  # у папках ігор ще нічого не зроблено
                rating = {a: b for a, b in (p.get("rating") or {}).items() if a in MG.MODES and b in ("ok", "bad")}
                if rating:
                    q["rating"] = dict(q.get("rating") or {}, **rating)
                if isinstance(p.get("name"), str):
                    q["name"] = p["name"][:200]
                profs[k.lower()] = q
        cur["profiles"] = profs
        F.CFG["mining"] = cur
        changed.append("mining")
    for key in ("close_to_tray",):
        if isinstance(data.get(key), bool):
            F.CFG[key] = data[key]
            changed.append(key)
    games = []
    for g in data.get("games") or []:
        p = str((g or {}).get("path") or "")
        if p.lower().endswith(".exe") and os.path.isfile(p):
            F.add_game(p)
            flags = {k: g.get(k) for k in GAME_FLAGS if k in g and k not in ("prio", "dgpu", "fso", "cores")}
            if flags:
                F.update_game(p, **flags)
            games.append(p)
    return {"keys": changed, "games": games}


def game_options(data: dict) -> list:
    """Позначки «Моїх ігор», що змінюють систему (пріоритет, відеокарта, FSO, ядра): [(шлях, опція)] — застосовуються
    через журнал відкату, як і з «Моїх ігор»."""
    out = []
    for g in data.get("games") or []:
        p = str((g or {}).get("path") or "")
        if p.lower().endswith(".exe") and os.path.isfile(p):
            out += [(p, k) for k in ("prio", "dgpu", "fso", "cores") if g.get(k)]
    return out
