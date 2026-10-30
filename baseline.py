"""
OptimaX — знімок початкових налаштувань Windows.

Перед першою зміною OptimaX один раз запам'ятовує, якими були всі параметри реєстру й служб, які може змінити
каталог оптимізацій. Для того, що OptimaX уже змінював раніше (оновлення з 6.3 і старіших), береться значення
«до» з журналу відкату, а не поточне.

Навіщо, якщо є журнал: журнал відкату — основний спосіб повернути зміни. Знімок — запасний: якщо журнал
загубився (видалили папку налаштувань, пошкоджено диск), OptimaX усе одно знайде параметри, які мають значення
оптимізації, хоча до OptimaX були іншими, і запропонує повернути саме їх («сироти» без запису в журналі).
Знімок ніколи не перезаписується.
"""
from __future__ import annotations

import json
import os
import time

import engine as E
from i18n import tr

PATH = os.path.join(E.DATA_DIR, "baseline.dryrun.json" if E.DRY_RUN else "baseline.json")
VERSION = 1


def _rkey(path: str, name: str) -> str:
    return f"{path}|{name}"


def _norm(v) -> str:
    """Значення для порівняння: 0 і "0", REG_SZ у різному регістрі, байти — однаково."""
    if isinstance(v, dict) and "hex" in v:
        return "hex:" + v["hex"].lower()
    if isinstance(v, (bytes, bytearray)):
        return "hex:" + bytes(v).hex()
    return str(v).lower()


def targets() -> dict:
    """Усе, що каталог змінює фіксованими значеннями: {"reg": {ключ: (шлях, ім'я, {значення}, [твіки])},
    "svc": {ім'я: ({режими}, [твіки])}}. Динамічні операції (пристрої, мережеві адаптери) не враховуються —
    їх відкат є лише в журналі."""
    reg, svc = {}, {}
    for t in E.TWEAKS:
        if not t.reversible:
            continue
        for op in t.ops:
            if op[0] == "reg" and not callable(op[3]):
                k = _rkey(op[1], op[2])
                item = reg.setdefault(k, (op[1], op[2], set(), []))
                item[2].add(_norm(E._enc(op[3])))
                item[3].append(t.id)
            elif op[0] == "regdel":
                k = _rkey(op[1], op[2])
                item = reg.setdefault(k, (op[1], op[2], set(), []))
                item[2].add("<deleted>")
                item[3].append(t.id)
            elif op[0] == "svc":
                item = svc.setdefault(op[1], (set(), []))
                item[0].add(op[2])
                item[1].append(t.id)
    return {"reg": reg, "svc": svc}


def _journal_originals(journal: E.Journal = None) -> tuple:
    """Найперші значення «до» з журналу відкату: {ключ реєстру: [тип, значення] | None}, {служба: режим}."""
    j = journal or E.JOURNAL
    reg, svc = {}, {}
    for tid in reversed(j.newest_first()):  # від найстарішого: перше «до» — справжнє початкове
        for rec in (j.get(tid) or {}).get("undo", []):
            if rec.get("t") == "reg":
                reg.setdefault(_rkey(rec["p"], rec["n"]).lower(), rec.get("old"))
            elif rec.get("t") == "svc":
                svc.setdefault(str(rec.get("n")).lower(), rec.get("old"))
    return reg, svc


def capture(journal: E.Journal = None) -> dict:
    tg = targets()
    j_reg, j_svc = _journal_originals(journal)
    reg = {}
    for k, (path, name, _vals, _ids) in tg["reg"].items():
        if k.lower() in j_reg:
            reg[k] = j_reg[k.lower()]
        else:
            cur = E.reg_get(path, name)
            reg[k] = None if cur is None else [cur[0], E._enc(cur[1])]
    svc = {}
    for name in tg["svc"]:
        svc[name] = j_svc[name.lower()] if name.lower() in j_svc else E.svc_get_start(name)
    return {"v": VERSION, "ts": int(time.time()), "build": E.win_build(), "app": E.VERSION, "reg": reg, "svc": svc}


def load():
    try:
        with open(PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get("reg"), dict) else None
    except (OSError, ValueError):
        return None


def ensure(log=lambda *_: None) -> bool:
    """Зробити знімок, якщо його ще немає. -> True, якщо знімок щойно створено."""
    if os.path.exists(PATH) and load():
        return False
    if E.JOURNAL.problem == "lost":  # журнал загубився: поточні значення вже не «початкові»
        return False
    snap = capture()
    E._write_atomic(PATH, snap, durable=True)
    log(tr("bl.saved", n=len(snap["reg"]) + len(snap["svc"])))
    return True


def _covered(journal: E.Journal = None) -> tuple:
    """Що зараз уміє повернути журнал відкату."""
    j = journal or E.JOURNAL
    reg, svc = set(), set()
    for tid in j.newest_first():
        for rec in (j.get(tid) or {}).get("undo", []):
            if rec.get("t") == "reg":
                reg.add(_rkey(rec["p"], rec["n"]).lower())
            elif rec.get("t") == "svc":
                svc.add(str(rec.get("n")).lower())
    return reg, svc


def orphans(snap: dict = None, journal: E.Journal = None) -> list:
    """Параметри, які зараз мають значення оптимізації OptimaX, до OptimaX були іншими, а журнал відкату про них
    не знає. -> [{kind, key, path, name, base, cur, tweaks}]"""
    snap = snap or load()
    if not snap:
        return []
    tg = targets()
    c_reg, c_svc = _covered(journal)
    out = []
    for k, (path, name, vals, ids) in tg["reg"].items():
        if k not in snap["reg"] or k.lower() in c_reg:
            continue
        base = snap["reg"][k]
        cur = E.reg_get(path, name)
        cur_n = "<deleted>" if cur is None else _norm(E._enc(cur[1]))
        base_n = "<deleted>" if base is None else _norm(base[1])
        if cur_n != base_n and cur_n in vals:
            out.append(dict(kind="reg", key=k, path=path, name=name, base=base,
                            cur=None if cur is None else [cur[0], E._enc(cur[1])], tweaks=sorted(set(ids))))
    for name, (modes, ids) in tg["svc"].items():
        if name not in snap.get("svc", {}) or name.lower() in c_svc:
            continue
        base, cur = snap["svc"][name], E.svc_get_start(name)
        if base and cur and cur != base and cur in modes:
            out.append(dict(kind="svc", key=name, name=name, base=base, cur=cur, tweaks=sorted(set(ids))))
    return out


def restore(items: list, log, progress=None) -> dict:
    """Повертає знайдені «сироти» до значень зі знімка."""
    ok = fail = 0
    for i, it in enumerate(items):
        if progress:
            progress(i, len(items), it.get("name") or it["key"])
        what = f"{it['path']}\\{it['name']}" if it["kind"] == "reg" else f"{tr('d.service')}: {it['name']}"
        log(f"[↩] {what}")
        if E.DRY_RUN:
            log(f"  [dry-run] → {it['base']}")
            ok += 1
            continue
        try:
            if it["kind"] == "reg":
                if it["base"] is None:
                    E.reg_del_value(it["path"], it["name"])
                else:
                    E.reg_set(it["path"], it["name"], E._dec(it["base"][1]), it["base"][0])
            else:
                rc, out = E.run(f"sc config {it['name']} start= {it['base']}", 15, log)
                if rc != 0:
                    raise RuntimeError(E.first_line(out, 70) or f"sc {rc}")
            ok += 1
            log(tr("e.undone"))
        except Exception as e:
            fail += 1
            log(tr("e.err", err=f"{type(e).__name__}: {e}"))
    if progress:
        progress(len(items), len(items), tr("e.finished"))
    log(tr("bl.restored", n=ok))
    return {"ok": ok, "fail": fail}


def state() -> dict:
    snap = load()
    return {"exists": bool(snap), "ts": (snap or {}).get("ts", 0),
            "n": len((snap or {}).get("reg", {})) + len((snap or {}).get("svc", {}))}


if ensure not in E.BEFORE_APPLY:
    E.BEFORE_APPLY.append(ensure)
