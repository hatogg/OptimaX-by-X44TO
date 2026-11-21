"""
OptimaX — бібліотека ігор: ігри зі Steam, Epic, GOG, Ubisoft і «Моїх ігор» з обкладинками, запуск, час гри,
історія FPS по кожній грі.

• Обкладинки — лише локальні: кеш бібліотеки Steam (appcache/librarycache); для інших — іконка exe.
• Запуск — через лаунчер гри (steam://, com.epicgames.launcher://, uplay://) або exe напряму, і завжди через
  explorer.exe: OptimaX працює з правами адміністратора, а гра має запуститися від імені користувача, як із робочого
  столу (інакше її файли й налаштування належали б адміністратору, а оверлеї та моди могли б не працювати).
• Сесії — фонова перевірка процесів: коли гра запустилася, коли востаннє працювала, коли закрилася. Сесія, яка не
  закрилася, бо закрився сам комп, позначається «lost» — за нею «Чому впав комп?» бачить, яка гра працювала.
• FPS — якщо є PresentMon: через 2 хвилини гри й далі раз на 15 хвилин — запис 60 секунд, поки гра на передньому
  плані. Історія — останні 40 замірів на гру.
"""
from __future__ import annotations

import fnmatch
import ntpath
import os
import subprocess
import time
from urllib.parse import quote

import engine as E
import features as F

SESS_KEEP = 80
FPS_KEEP = 40
HEARTBEAT = 60          # як часто зберігати «гра ще працює»
FPS_AFTER = 120         # перший запис FPS — після 2 хвилин гри (завантаження, шейдери)
FPS_EVERY = 15 * 60
FPS_SECONDS = 60
LIBRARY_EVERY = 24 * 3600


def _base(p: str) -> str:
    return ntpath.basename(p) if "\\" in p else os.path.basename(p)


# ───────────────────────── список ігор ─────────────────────────
def entry(g: dict) -> dict:
    """Гра з mining.discover -> запис бібліотеки (лише те, що потрібно інтерфейсу й запуску)."""
    import mining as MG
    exes = [x for x in g.get("exes") or [] if x.get("api") != "other"] or list(g.get("exes") or [])
    main = g.get("main") or ""
    if not main or not any(x["path"].lower() == main.lower() for x in g.get("exes") or []):
        main = exes[0]["path"] if exes else ""
    return dict(key=MG.game_key(g), name=g["name"], store=g.get("store") or "mine", dir=g["dir"],
                exes=sorted({_base(x["path"]).lower() for x in exes}), main=main, appid=g.get("appid") or "",
                epic=g.get("epic") or "", ubi=g.get("ubi") or "", risk=g.get("risk") or "",
                anticheat=g.get("anticheat") or "")


def refresh(games: list = None) -> list:
    import mining as MG
    games = MG.discover() if games is None else games
    items = [entry(g) for g in games]
    F.CFG["library"] = dict(F.CFG["library"] or {}, ts=int(time.time()), games=items)
    F.remember_game_exes(games)
    reset_covers()
    if E.IS_WIN:  # 7.1.1: корінь Steam і список кешу обкладинок — тут, у фоновому потоці, а не під час побудови плиток
        _cover_index(_cover_state(), _cover_base(_cover_state()["root"]))
    return items


def games() -> list:
    return list((F.CFG["library"] or {}).get("games") or [])


def due() -> bool:
    return time.time() - float((F.CFG["library"] or {}).get("ts") or 0) >= LIBRARY_EVERY


def known_exes() -> dict:
    """exe (нижній регістр) -> назва гри: бібліотека і «Мої ігри»."""
    out = {}
    for g in games():
        for x in g.get("exes") or []:
            out.setdefault(x, g["name"])
    for g in F.CFG["games"] or []:
        p = g.get("path") or ""
        if p:
            out.setdefault(_base(p).lower(), F.game_name(p))
    return out


def setting(key: str, default=None):
    return (F.CFG["library"] or {}).get(key, default)


def set_setting(key: str, value) -> None:
    lib = dict(F.CFG["library"] or {})
    lib[key] = value
    F.CFG["library"] = lib


# ───────────────────────── обкладинки ─────────────────────────
COVER_NAMES = ("library_600x900", "library_capsule", "header")


# 7.1.1: раніше кожна плитка читала корінь Steam з реєстру й до 9 разів переглядала весь librarycache (тисячі
# файлів) — у потоці інтерфейсу. Тепер корінь і список кешу — один раз на оновлення бібліотеки (reset_covers),
# а папка <appid> — один раз на гру. Збіги й порядок — ті самі, що в glob (fnmatch, сортування повних шляхів).
_COVER_STATE: dict = {"root": None, "index": {}}


def reset_covers() -> None:
    global _COVER_STATE
    _COVER_STATE = {"root": None, "index": {}}  # заміною цілком: потік інтерфейсу міг саме читати попередній


def _cover_state() -> dict:
    st = _COVER_STATE
    if st["root"] is None:
        import mining as MG
        st["root"] = MG.steam_root() or ""
    return st


def _cover_base(steam_root: str) -> str:
    return os.path.join(steam_root, "appcache", "librarycache") if steam_root else ""


def _listdir(path: str) -> list:
    try:
        return os.listdir(path)
    except OSError:
        return []


def _cover_index(st: dict, base: str) -> dict:
    idx = st["index"].get(base)
    if idx is None and base:
        top = {}  # <appid> -> імена «<appid>_…» у корені кешу (інших шаблон «<appid>_<назва>*.jpg» не бере)
        for n in _listdir(base):
            top.setdefault(n.split("_", 1)[0], []).append(n)
        idx = st["index"][base] = {"top": top, "apps": {}}
    return idx


def _app_files(idx: dict, base: str, appid: str) -> tuple:
    """(файли в <appid>/, [(ім'я, шлях)] у <appid>/*/) — один раз на гру."""
    got = idx["apps"].get(appid)
    if got is None:
        d = os.path.join(base, appid)
        lvl1 = _listdir(d)
        lvl2 = []
        for n in lvl1:
            if not n.startswith(".") and os.path.isdir(os.path.join(d, n)):  # «*» у glob не бере приховані
                lvl2 += [(m, os.path.join(d, n, m)) for m in _listdir(os.path.join(d, n))]
        got = idx["apps"][appid] = (lvl1, lvl2)
    return got


def cover(g: dict, steam_root: str = None) -> str:
    """Шлях до локальної обкладинки Steam або "". Нові версії Steam кладуть файли в librarycache/<appid>/(…/), старі —
    librarycache/<appid>_library_600x900.jpg."""
    appid = str(g.get("appid") or "")
    if not appid.isdigit():
        return ""
    st = _cover_state() if steam_root is None else _COVER_STATE
    base = _cover_base(st["root"] if steam_root is None else steam_root)
    if not base:
        return ""
    idx = _cover_index(st, base)
    lvl1, lvl2 = _app_files(idx, base, appid)
    top = [(n, os.path.join(base, n)) for n in idx["top"].get(appid, ())]
    sub = [(n, os.path.join(base, appid, n)) for n in lvl1]
    for name in COVER_NAMES:
        for cands, pat in ((top, f"{appid}_{name}*.jpg"), (sub, f"{name}*.jpg"), (lvl2, f"{name}*.jpg")):
            hits = sorted(p for n, p in cands if fnmatch.fnmatch(n, pat))
            if hits:
                return hits[0]
    return ""


# ───────────────────────── запуск ─────────────────────────
def launch_target(g: dict) -> str:
    if str(g.get("appid") or "").isdigit():
        return f"steam://rungameid/{g['appid']}"
    if g.get("epic"):
        return f"com.epicgames.launcher://apps/{quote(str(g['epic']), safe='')}?action=launch&silent=true"
    if str(g.get("ubi") or "").isdigit():
        return f"uplay://launch/{g['ubi']}/0"
    return g.get("main") or ""


def launch(g: dict, log) -> dict:
    target = launch_target(g)
    if not target:
        return {"error": "no_target"}
    log(f"  ▶ {g['name']}: {target}")
    if not E.IS_WIN or E.DRY_RUN:
        log("  [dry-run] explorer.exe " + target)
        return {"ok": 1, "target": target}
    try:
        # explorer.exe відкриває посилання чи exe від імені користувача, як подвійне натискання на робочому столі
        # 7.1.1: повний шлях (SF.explorer_exe): за самим ім'ям Windows шукає exe спершу в папці OptimaX.exe і в
        # поточній, куди будь-яка програма могла б покласти свій «explorer.exe»
        import secfs as SF
        subprocess.Popen([SF.explorer_exe(), target], cwd=os.path.dirname(g.get("main") or "") or None)
        return {"ok": 1, "target": target}
    except OSError as e:
        return {"error": str(e)}


# ───────────────────────── сесії ─────────────────────────
def _play() -> dict:
    p = dict(F.CFG["play"] or {})
    p.setdefault("sessions", [])
    p.setdefault("totals", {})
    return p


def sessions() -> list:
    return list(_play()["sessions"])


def totals() -> dict:
    return dict(_play()["totals"])


def close_lost() -> int:
    """Під час запуску OptimaX: сесії, що не закрилися (комп вимкнувся чи впав, OptimaX закрили), — «lost»."""
    p = _play()
    n = 0
    for s in p["sessions"]:
        if not s.get("end"):
            s["end"] = s.get("last") or s["start"]
            s["lost"] = True
            p["totals"][s["exe"]] = p["totals"].get(s["exe"], 0) + max(0, s["end"] - s["start"])
            n += 1
    if n:
        F.CFG["play"] = p
    return n


class Tracker:
    """Фонова перевірка: які ігри працюють. tick(running) -> {"started": [exe], "ended": [exe]}."""

    def __init__(self):
        self.active = {}  # exe -> індекс сесії в CFG
        self.saved = 0.0

    def tick(self, running: set, now: float = None) -> dict:
        now = int(now or time.time())
        known = known_exes()
        live = {n for n in running if n in known}
        p = _play()
        changed = False
        res = {"started": [], "ended": []}
        for exe in sorted(live - set(self.active)):
            p["sessions"].append(dict(exe=exe, name=known[exe], start=now, last=now, end=None))
            self.active[exe] = len(p["sessions"]) - 1
            res["started"].append(exe)
            changed = True
        for exe in list(self.active):
            i = self.active[exe]
            if i >= len(p["sessions"]) or p["sessions"][i].get("exe") != exe:
                self.active.pop(exe)
                continue
            s = p["sessions"][i]
            if exe in live:
                s["last"] = now
            else:
                s["end"] = s["last"] = now
                p["totals"][exe] = p["totals"].get(exe, 0) + max(0, now - s["start"])
                self.active.pop(exe)
                res["ended"].append(exe)
                changed = True
        if len(p["sessions"]) > SESS_KEEP:
            drop = len(p["sessions"]) - SESS_KEEP
            p["sessions"] = p["sessions"][drop:]
            self.active = {e: i - drop for e, i in self.active.items() if i - drop >= 0}
            changed = True
        if changed or (self.active and now - self.saved >= HEARTBEAT):
            F.CFG["play"] = p
            self.saved = now
        return res

    def started_at(self, exe: str) -> int:
        i = self.active.get(exe)
        ss = _play()["sessions"]
        return int(ss[i]["start"]) if i is not None and i < len(ss) else 0


def play_time(exe_names) -> int:
    t = totals()
    return sum(int(t.get(e, 0)) for e in exe_names)


def last_played(exe_names) -> int:
    names = set(exe_names)
    return max([int(s.get("last") or s.get("start") or 0) for s in sessions() if s.get("exe") in names] or [0])


# ───────────────────────── FPS ─────────────────────────
def fps_history(exe_names) -> list:
    data = F.CFG["game_fps"] or {}
    out = []
    for e in exe_names:
        out += data.get(e, [])
    return sorted(out, key=lambda r: r.get("ts", 0))[-FPS_KEEP:]


def add_fps(exe: str, res: dict) -> list:
    data = dict(F.CFG["game_fps"] or {})
    rows = list(data.get(exe, []))
    if not isinstance(res, dict) or not res.get("avg"):  # запис не вдався (гру згорнули, кадрів немає) — не історія
        return rows
    row = {k: res.get(k) for k in ("avg", "low1", "low01", "stutters_pm", "smooth")}
    row["ts"] = int(time.time())
    rows.append(row)
    data[exe] = rows[-FPS_KEEP:]
    F.CFG["game_fps"] = data
    return data[exe]


def fps_due(exe: str, started: int, last_try: float, now: float = None) -> bool:
    now = now or time.time()
    if not started or now - started < FPS_AFTER or now - (last_try or 0) < FPS_EVERY:
        return False
    hist = (F.CFG["game_fps"] or {}).get(exe) or []
    return not hist or now - hist[-1].get("ts", 0) >= FPS_EVERY


def fmt_hours(sec: int) -> str:
    from i18n import tr
    if sec < 3600:
        return tr("lib.min", n=max(1, sec // 60)) if sec else "—"
    return tr("lib.hours", n=f"{sec / 3600:.1f}".rstrip("0").rstrip("."))
