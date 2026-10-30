"""
OptimaX — база сумісності ігор із майнінговою картою (P106 / P104 / CMP): що відомо про гру (рушій, API, античит,
рекомендований режим рендерингу, параметри запуску) і що показали запуски на цьому ПК.

Вбудовані записи — лише загальновідоме про рушій і API гри (DirectX 9 → DXVK, OpenGL → Mesa, онлайн з античитом —
без шарів). Це «типово», а не «перевірено на вашому ПК»: перевіркою вважається лише результат GPU Renderer Monitor
(record_check у mining.py), і в інтерфейсі вони показуються окремо. Власні профілі користувача (режим, «працює / не
працює») мають перевагу над вбудованими і експортуються / імпортуються у JSON.
"""
from __future__ import annotations

import json
import ntpath
import os
import time

# exe (нижній регістр) -> запис. mode — рекомендований режим (mining.MODES), notes — ключі db.note.*, params —
# параметри запуску, які варто спробувати (лише ті, що гра справді розуміє), online — мережева гра (VAC тощо): шари
# в її папці — на ризик користувача.
BUILTIN = {
    "hl2.exe": dict(engine="Source", api="dx9", mode="auto", notes=["source"]),
    "csgo.exe": dict(engine="Source", api="dx9", mode="auto", notes=["source", "vac"], online=True),
    "left4dead2.exe": dict(engine="Source", api="dx9", mode="auto", notes=["source", "vac"], online=True),
    "portal2.exe": dict(engine="Source", api="dx9", mode="auto", notes=["source"]),
    "cs2.exe": dict(engine="Source 2", api="dx11", mode="native", notes=["vac", "cs2_vulkan"], params="-vulkan",
                    online=True),
    "dota2.exe": dict(engine="Source 2", api="dx11", mode="native", notes=["vac"], params="-vulkan", online=True),
    "hl.exe": dict(engine="GoldSrc", api="gl", mode="auto", notes=["goldsrc"]),
    "gta3.exe": dict(engine="RenderWare", api="dx9", mode="auto", notes=["dx8"]),
    "gta-vc.exe": dict(engine="RenderWare", api="dx9", mode="auto", notes=["dx8"]),
    "gta_sa.exe": dict(engine="RenderWare", api="dx9", mode="auto"),
    "gtaiv.exe": dict(engine="RAGE", api="dx9", mode="auto", notes=["gta4"]),
    "gta5.exe": dict(engine="RAGE", api="dx11", mode="native", notes=["anticheat_online"], online=True),
    "tesv.exe": dict(engine="Creation", api="dx9", mode="auto"),
    "skyrimse.exe": dict(engine="Creation", api="dx11", mode="native"),
    "fallout3.exe": dict(engine="Gamebryo", api="dx9", mode="auto"),
    "falloutnv.exe": dict(engine="Gamebryo", api="dx9", mode="auto"),
    "fallout4.exe": dict(engine="Creation", api="dx11", mode="native"),
    "witcher2.exe": dict(engine="REDengine", api="dx9", mode="auto"),
    "witcher3.exe": dict(engine="REDengine", api="dx11", mode="native"),
    "borderlands2.exe": dict(engine="Unreal 3", api="dx9", mode="auto"),
    "speed.exe": dict(engine="EAGL", api="dx9", mode="auto"),  # Need for Speed: Most Wanted (2005)
    "repo.exe": dict(engine="Unity", api="dx11", mode="native", notes=["unity"], params="-window-mode borderless"),
    "fortniteclient-win64-shipping.exe": dict(engine="Unreal", api="dx12", mode="native",
                                              notes=["anticheat_online"], online=True),
    "valorant-win64-shipping.exe": dict(engine="Unreal", api="dx11", mode="native", notes=["anticheat_online"],
                                        online=True),
    "r5apex.exe": dict(engine="Source", api="dx11", mode="native", notes=["anticheat_online"], online=True),
    "eurotrucks2.exe": dict(engine="Prism3D", api="dx11", mode="native"),
    "javaw.exe": dict(engine="Java", api="gl", mode="original", notes=["java"]),
}
# рушій за бібліотекою поруч з exe: підказки, коли гри немає в базі
ENGINE_FILES = (("UnityPlayer.dll", "Unity"), ("shaderapidx9.dll", "Source"), (os.path.join("bin", "shaderapidx9.dll"),
                                                                                  "Source"))
ENGINE_NOTES = {"Unity": ["unity"], "Source": ["source"]}
USER_FILE = "gamedb_user.json"
RESULTS = ("ok", "bad")  # оцінка користувача для режиму: працює / не працює


def _base(p: str) -> str:
    return ntpath.basename(p) if "\\" in p else os.path.basename(p)


def _dir(p: str) -> str:
    return ntpath.dirname(p) if "\\" in p else os.path.dirname(p)


def engine_of(g: dict) -> str:
    for x in g.get("exes") or []:
        d = _dir(x["path"])
        for n, eng in ENGINE_FILES:
            if os.path.isfile(os.path.join(d, n)):
                return eng
    return g.get("engine") or ""


def builtin(g: dict) -> dict:
    for x in g.get("exes") or []:
        hit = BUILTIN.get(_base(x["path"]).lower())
        if hit:
            return dict(hit, exe=_base(x["path"]))
    return {}


def lookup(g: dict) -> dict:
    """Усе, що відомо про гру: {engine, api, mode, notes, params, online, source: builtin|user|engine|""}.
    Режим, який користувач позначив як «працює», має перевагу; «не працює» — ніколи не радимо."""
    import mining as MG
    rec = builtin(g)
    src = "builtin" if rec else ""
    if not rec:
        eng = engine_of(g)
        if eng:
            rec, src = dict(engine=eng, notes=list(ENGINE_NOTES.get(eng, []))), "engine"
    rec = dict(rec)
    rec.setdefault("notes", [])
    rating = (MG.profile(g).get("rating") or {})
    good = [m for m, v in rating.items() if v == "ok" and m in MG.MODES]
    if good:
        rec["mode"], src = good[-1], "user"
    elif rec.get("mode") and rating.get(rec["mode"]) == "bad":
        rec.pop("mode")
    rec["bad"] = sorted(m for m, v in rating.items() if v == "bad")
    rec["source"] = src
    return rec


def rate(g: dict, mode: str, result: str) -> dict:
    """Позначка користувача: у цьому режимі гра працює (ok) / не працює (bad)."""
    import mining as MG
    if mode not in MG.MODES or result not in RESULTS + ("",):
        return MG.profile(g)
    rating = dict(MG.profile(g).get("rating") or {})
    if result:
        rating[mode] = result
    else:
        rating.pop(mode, None)
    return MG.set_profile(g, rating=rating)


def verified(g: dict) -> dict:
    """Остання перевірка рендерингу на цьому ПК: {mode, verdict, ts, path} або {}."""
    import mining as MG
    checks = MG.profile(g).get("checks") or []
    return dict(checks[-1]) if checks else {}


# ───────────────────────── експорт / імпорт власних профілів ─────────────────────────
EXPORT_KEYS = ("name", "mode", "rating", "params")


def export_profiles(path: str) -> int:
    import mining as MG
    data = {k: {f: v for f, v in p.items() if f in EXPORT_KEYS} for k, p in MG.profiles().items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"optimax_gamedb": 1, "ts": int(time.time()), "profiles": data}, f, ensure_ascii=False, indent=1)
    return len(data)


def import_profiles(path: str) -> int:
    """Додає режими й оцінки з файлу. Застосовуються вони лише тоді, коли користувач натисне «Застосувати» для гри —
    імпорт нічого не змінює в папках ігор сам."""
    import features as F
    import mining as MG
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = (data or {}).get("profiles") if isinstance(data, dict) else None
    if not isinstance(items, dict):
        raise ValueError("format")
    m = dict(F.CFG["mining"] or {})
    profs = dict(m.get("profiles") or {})
    n = 0
    for key, p in items.items():
        if not isinstance(key, str) or not isinstance(p, dict):
            continue
        clean = {}
        if p.get("mode") in MG.MODES:
            clean["imported_mode"] = p["mode"]  # не «mode»: у папці гри ще нічого не зроблено
        rating = {k: v for k, v in (p.get("rating") or {}).items() if k in MG.MODES and v in RESULTS}
        if rating:
            clean["rating"] = rating
        if isinstance(p.get("name"), str):
            clean["name"] = p["name"][:200]
        if clean:
            cur = dict(profs.get(key.lower()) or {})
            cur.update(clean)
            profs[key.lower()] = cur
            n += 1
    m["profiles"] = profs
    F.CFG["mining"] = m
    return n
