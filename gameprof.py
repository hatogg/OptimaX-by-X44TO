"""
OptimaX — профілі ігор (Game Booster 2.0): що змінювати, поки працює конкретна гра з «Бібліотеки».

Профіль гри — лише значення з білих списків:
• схема живлення на час гри: не змінювати / «Висока продуктивність» / «Максимальна продуктивність» (Ultimate,
  якщо її не вдається отримати — «Висока продуктивність», і про це пишеться в журнал);
• відеокарта для exe гри (налаштування «Графіка» Windows, GpuPreference): не змінювати / висока продуктивність (на
  ПК з майнінговою картою — саме вона, як у mining.py) / енергозбереження. Windows читає його під час запуску гри,
  тож воно діє, поки є профіль, і пишеться в журнал відкату одразу після збереження профілю (як «Мої ігри»);
• пріоритет процесу гри: не змінювати / звичайний / вище звичайного / високий. Реального часу немає й не буде:
  значення береться з settings.json, а realtime від імені адміністратора може «покласти» систему;
• чи вмикати режим гри (features.BOOSTER) з його власним відкатом.

Як це працює:
• фоновий такт головного вікна (needs_sync — лише порівняння імен процесів, без змін і без запуску програм) помічає,
  що exe гри з профілем запустився чи закрився, і лише тоді запускає sync у фоні;
• схема живлення — один запис журналу (features.PROFILE_POWER_ID) на всі запущені ігри з профілями: найсильніша з
  потрібних. Початкова схема записана один раз, тож дві гри одночасно не плутають, що повертати. Відкат — коли
  закриється остання така гра, коли закривається OptimaX, а після аварії — під час наступного запуску (recover) або
  через OptimaX-Rescue.cmd. Якщо схему вже змінив режим гри, профіль її не чіпає (і навпаки: режим гри не чіпає
  схему, яку тримає профіль) — повертає той, хто змінив;
• режим гри профіль вмикає лише тоді, коли той ще вимкнений, і вимикає, коли закриється остання гра з профілем, якій
  він потрібен;
• пріоритет — лише процесам, чий exe лежить у папці гри з бібліотеки; повертається, лише якщо в процесу досі наш
  пріоритет (гру закрили — повертати нічого).

Межа довіри: settings.json (профілі, бібліотека, стан сесії) пише будь-яка програма користувача. Звідти беремо лише
значення з білих списків; шлях exe — лише ім'я значення реєстру HKCU і перевірка «процес лежить у папці гри»: він
ніколи не запускається і не стає командою.
"""
from __future__ import annotations

import ntpath
import threading
import time

import engine as E
import features as F
from i18n import tr

POWER = ("keep", "high", "ultimate")
GPU = ("keep", "high", "saving")
PRIO = ("keep", "normal", "above", "high")
PRIO_CLASS = {"normal": 0x20, "above": 0x8000, "high": 0x80}  # без realtime (0x100) — навмисно
GPU_VALUE = {"high": "2", "saving": "1"}
POWER_RANK = {"high": 1, "ultimate": 2}
DEFAULT = {"enabled": True, "power": "keep", "gpu": "keep", "prio": "keep", "boost": False}
POWER_ID = F.PROFILE_POWER_ID
GPU_PREFIX = "gprof:gpu:"
CFG_KEY = "game_profiles"
STATE_KEY = "game_profile_state"
HIST_KEY = "game_profile_hist"
HIST_KEEP = 20
MAX_KEY = 400
MAX_EXES = 40
MAX_STATE = 64


# ───────────────────────── профілі (дані з settings.json) ─────────────────────────
def clean(raw) -> dict:
    """Профіль із settings.json -> лише значення з білих списків (решта — типові)."""
    p = dict(DEFAULT)
    if not isinstance(raw, dict):
        return p
    for k, allowed in (("power", POWER), ("gpu", GPU), ("prio", PRIO)):
        v = raw.get(k)
        if isinstance(v, str) and v in allowed:
            p[k] = v
    for k in ("enabled", "boost"):
        if isinstance(raw.get(k), bool):
            p[k] = raw[k]
    return p


def is_set(p: dict) -> bool:
    """Чи змінює профіль хоч щось."""
    return any(p.get(k) != DEFAULT[k] for k in ("power", "gpu", "prio", "boost"))


def _under(path: str, folder: str) -> bool:
    return path.lower().startswith(folder.lower().rstrip("\\/") + "\\")


def sane_game(g) -> dict:
    """Запис бібліотеки -> перевірена копія або {}. Папка гри — абсолютна, не корінь диска й не Windows; exe — лише
    імена *.exe без шляху (не службові процеси); головний exe — у папці гри."""
    if not isinstance(g, dict):
        return {}
    key, folder, name = g.get("key"), g.get("dir"), g.get("name")
    if not (isinstance(key, str) and 0 < len(key) <= MAX_KEY and isinstance(folder, str) and isinstance(name, str)):
        return {}
    folder = folder.rstrip("\\/")
    parts = [x for x in folder.replace("/", "\\").split("\\") if x]
    if not ntpath.isabs(folder) or len(parts) < 2 or folder.lower().startswith(F.SYS_DIRS):
        return {}
    exes = []
    for e in g.get("exes") or []:
        if (isinstance(e, str) and e.lower().endswith(".exe") and ntpath.basename(e) == e and "/" not in e
                and e.lower() not in F.SKIP_EXE and e.lower() not in exes):
            exes.append(e.lower())
    if not exes:
        return {}
    main = g.get("main") if isinstance(g.get("main"), str) else ""
    if main and not (_under(main, folder) and main.lower().endswith(".exe")):
        main = ""
    return dict(key=key, name=name[:120], dir=folder, exes=exes[:MAX_EXES], main=main)


def _library() -> dict:
    import library as LB
    out = {}
    for g in LB.games():
        s = sane_game(g)
        if s:
            out.setdefault(s["key"], s)
    return out


def profiles() -> dict:
    raw = F.CFG[CFG_KEY]
    if not isinstance(raw, dict):
        return {}
    return {k: clean(v) for k, v in raw.items() if isinstance(k, str) and 0 < len(k) <= MAX_KEY}


def profile(g: dict) -> dict:
    """Профіль гри (типовий, якщо не задано)."""
    return profiles().get((g or {}).get("key"), dict(DEFAULT))


def has_profile(g: dict) -> bool:
    p = profiles().get((g or {}).get("key"))
    return bool(p and p["enabled"] and is_set(p))


def watched() -> dict:
    """Ігри, за якими стежимо: {key: (гра, профіль)} — увімкнений профіль, що щось змінює, і гра є в бібліотеці."""
    profs = {k: p for k, p in profiles().items() if p["enabled"] and is_set(p)}
    if not profs:
        return {}
    lib = _library()
    return {k: (lib[k], p) for k, p in profs.items() if k in lib}


def _store(key: str, p) -> None:
    raw = F.CFG[CFG_KEY]
    data = {k: v for k, v in raw.items() if isinstance(k, str)} if isinstance(raw, dict) else {}
    if p is None:
        data.pop(key, None)
    else:
        data[key] = clean(p)
    F.CFG[CFG_KEY] = data


# ───────────────────────── відеокарта для exe гри (постійно, через журнал) ─────────────────────────
def gpu_id(path: str) -> str:
    return GPU_PREFIX + path.lower()


def gpu_paths(g: dict) -> list:
    """Повні шляхи exe гри для налаштування «Графіка»: головний exe і exe з бібліотеки, знайдені в папці гри."""
    out = [g["main"]] if g.get("main") else []
    if E.IS_WIN:
        import os
        import mining as MG
        if os.path.isdir(g["dir"]):
            for x in MG.scan_exes(g["dir"]):
                p = x.get("path") or ""
                if (ntpath.basename(p).lower() in g["exes"] and _under(p, g["dir"])
                        and p.lower() not in {q.lower() for q in out}):
                    out.append(p)
    return out[:MAX_EXES]


def ours_gpu(g: dict) -> list:
    """Записи журналу профілю для exe цієї гри."""
    pre = gpu_id(g["dir"]) + "\\"
    return [tid for tid in E.JOURNAL.newest_first() if tid.startswith(pre)]


def _gpu_now(path: str):
    cur = E.reg_get(E.DX_PREF, path)
    return E.kv_get(cur[1], "GpuPreference") if cur and isinstance(cur[1], str) else None


def gpu_tweak(g: dict, path: str, mode: str) -> E.Tweak:
    t = E.Tweak(gpu_id(path), "game", [E.KV(E.DX_PREF, path, "GpuPreference", GPU_VALUE[mode])], custom=True)
    t._title = tr("gprof.t_gpu", game=g["name"], exe=ntpath.basename(path), mode=tr(f"gprof.gpu.{mode}"))
    return t


def _sync_gpu(g: dict, p: dict, log) -> dict:
    """Налаштування «Графіка» для exe гри — як у профілі (вимкнений профіль — як до OptimaX)."""
    mode = p["gpu"] if p["enabled"] else "keep"
    want = GPU_VALUE.get(mode)
    paths = gpu_paths(g) if want else []
    keep = set()
    todo, undo, res = [], [], {"ok": 0, "fail": 0}
    for path in paths:
        tid = gpu_id(path)
        if E.JOURNAL.has(tid) and _gpu_now(path) == want:
            keep.add(tid)
            continue
        if E.JOURNAL.has(f"game:{path.lower()}:dgpu"):  # «Мої ігри» вже тримають це значення
            if want == "2":
                log(tr("gprof.gpu_mine", exe=ntpath.basename(path)))
            else:
                log(tr("gprof.gpu_clash", exe=ntpath.basename(path)))
                res["fail"] += 1
            continue
        mined = "gpu:" + path.lower()  # mining.gpu_id
        if E.JOURNAL.has(mined):
            if want == "2":
                log(tr("gprof.gpu_mining", exe=ntpath.basename(path)))
                continue
            undo.append(mined)  # значення переходить під профіль (як у features.set_game_option)
        if E.JOURNAL.has(tid):
            undo.append(tid)
        todo.append(gpu_tweak(g, path, mode))
    undo += [tid for tid in ours_gpu(g) if tid not in keep and tid not in undo]
    if undo:
        r = E.undo_ids(undo, log, by="gameprof")
        res["fail"] += int(r.get("partial") or 0)
        if any(E.JOURNAL.has(tid) for tid in undo):
            log(tr("gprof.gpu_undo_fail"))
            return dict(res, fail=res["fail"] + 1)
    if todo:
        r = E.apply_tweaks(todo, log, header=False, by="gameprof")
        res["ok"] += int(r.get("ok") or 0)
        res["fail"] += int(r.get("fail") or 0) + int(r.get("partial") or 0)
        if r.get("error"):
            res["error"] = r["error"]
    return res


@E._serial
def save(g: dict, prof, log) -> dict:
    """Зберегти профіль гри й одразу привести налаштування «Графіка» до нього."""
    s = sane_game(g)
    if not s:
        return {"error": "game"}
    p = clean(prof)
    _store(s["key"], p)
    res = _sync_gpu(s, p, log)
    log(tr("gprof.saved", game=s["name"]))
    return res


@E._serial
def remove(g: dict, log) -> dict:
    """Прибрати профіль: налаштування «Графіка» — як до OptimaX, гра більше не відстежується."""
    s = sane_game(g)
    if not s:
        return {"error": "game"}
    res = _sync_gpu(s, dict(DEFAULT, enabled=False), log)
    _store(s["key"], None)
    log(tr("gprof.removed", game=s["name"]))
    return res


# ───────────────────────── схема живлення на час гри ─────────────────────────
def _power_fn(target: str):
    def fn(ctx: E.Ctx) -> None:
        log = ctx.log
        old = E.active_scheme()
        created = False
        if target == "ultimate" and E.IS_WIN and not E.DRY_RUN:
            new, created = E.ensure_ultimate(log)
            if new == E.HIGH_PERF:
                log(tr("e.plan_fallback"))
        else:
            new = E.HIGH_PERF
        # записи відкату — до зміни; створену схему прибираємо й тоді, коли перемкнутися не вдалося (як f_ultimate)
        if created:
            ctx.undo.append({"t": "cmd", "c": f"powercfg -delete {new}"})
        if new == old:
            log(tr("gprof.power_same"))
            return
        rec = {"t": "cmd", "c": f"powercfg -setactive {old}"}
        ctx.undo.append(rec)
        rc, out = E.run(["powercfg", "-setactive", new], 15, log, stoppable=False)
        if rc != 0:
            log(tr("e.plan_fail", msg=E.first_line(out)))
            ctx.fail("powercfg -setactive")
            if rc != E.TIMEOUT_RC:
                ctx.undo.discard(rec)
            return
        log(tr("gprof.power_on", plan=tr(f"gprof.power.{target}")))
    return fn


def power_tweak(target: str) -> E.Tweak:
    t = E.Tweak(POWER_ID, "game", [E.F(_power_fn(target))], custom=True)
    t._title = tr("gprof.t_power", plan=tr(f"gprof.power.{target}"))
    return t


# ───────────────────────── процеси (окремо — щоб тести могли підмінити) ─────────────────────────
_DEMO_PRIO: dict = {}


def _procs() -> list:
    return E.processes()


def _path(pid: int):
    return E.process_path(pid)


def _get_prio(pid: int) -> int:
    if not E.IS_WIN:
        return _DEMO_PRIO.get(pid, 0x20)
    import monitor as M
    return M._get_priority(pid)


def _set_prio(pid: int, cls: int) -> bool:
    if not E.IS_WIN:
        _DEMO_PRIO[pid] = cls
        return True
    import monitor as M
    return M._set_priority(pid, cls)


def _match(w: dict, procs: list) -> dict:
    """{key: {pid: ім'я}} — процеси з іменами exe ігор (без перевірки шляху)."""
    by_exe: dict = {}
    for key, (g, _p) in w.items():
        for e in g["exes"]:
            by_exe.setdefault(e, []).append(key)
    out: dict = {}
    for pid, name in procs:
        for key in by_exe.get((name or "").lower(), ()):
            out.setdefault(key, {})[pid] = name
    return out


def _verified(g: dict, pid: int) -> bool:
    """Процес справді з папки гри з бібліотеки (на Windows — за повним шляхом exe)."""
    if not E.IS_WIN:
        return True
    p = _path(pid) or ""
    return bool(p) and _under(p, g["dir"]) and not p.lower().startswith(F.SYS_DIRS)


# ───────────────────────── сесії ─────────────────────────
class Manager:
    """Профілі запущених ігор: застосування, повернення, кілька ігор одночасно."""

    def __init__(self):
        self.lock = threading.RLock()
        self.active: dict = {}  # key -> {name, since, main, power, boost, prio: {pid: [ім'я, старий, новий]}}
        self.seen: dict = {}  # key -> pid усіх процесів з іменами exe гри на час останньої синхронізації
        self.power = None  # ціль схеми, яку вже пробували для поточного набору ігор
        self.booster_ours = False
        self.ready = False  # до відновлення після аварії (recover) нічого не застосовуємо

    # ── для інтерфейсу ──
    def active_keys(self) -> set:
        if not self.lock.acquire(timeout=0.05):
            return set()
        try:
            return set(self.active)
        finally:
            self.lock.release()

    def since(self, key: str) -> int:
        if not self.lock.acquire(timeout=0.05):
            return 0
        try:
            return int((self.active.get(key) or {}).get("since") or 0)
        finally:
            self.lock.release()

    def holds_booster(self) -> bool:
        return self.booster_ours and F.BOOSTER.active

    def busy(self) -> bool:
        """Є що повертати (закриття OptimaX)."""
        return bool(self.active or self.booster_ours or E.JOURNAL.has(POWER_ID))

    def needs_sync(self, procs: list = None) -> bool:
        """Дешево, у потоці інтерфейсу: чи запустилася / закрилася гра з профілем або з'явився новий її процес."""
        if not self.ready or not self.lock.acquire(blocking=False):
            return False
        try:
            w = watched()
            if not w and not self.active:
                return bool(self.booster_ours or self.power)
            run = _match(w, procs if procs is not None else _procs())
            if any(k not in run for k in self.active):
                return True
            return any(set(pids) - self.seen.get(k, set()) for k, pids in run.items())
        finally:
            self.lock.release()

    # ── синхронізація ──
    @E._serial
    def sync(self, log) -> dict:
        with self.lock:
            res = {"started": [], "ended": [], "ok": 0, "fail": 0}
            if not self.ready:
                return res
            w = watched()
            run = _match(w, _procs())
            self.seen = {k: set(p) for k, p in run.items()}
            live = {}
            for key, pids in run.items():
                g = w[key][0]
                ok = {pid: n for pid, n in pids.items() if _verified(g, pid)}
                if ok:
                    live[key] = ok
            for key in [k for k in self.active if k not in live]:
                a = self.active.pop(key)
                self._restore_prio(a, log, res)  # профіль прибрали, а гра ще працює
                self._hist(key, a)
                res["ended"].append(a["name"])
                log(tr("gprof.log_off", game=a["name"]))
            started = []
            for key, pids in sorted(live.items()):
                g, p = w[key]
                a = self.active.get(key)
                if a is None:
                    a = self.active[key] = dict(name=g["name"], since=int(time.time()), main=g["main"], prio={},
                                                done=set())
                    started.append(key)
                    res["started"].append(g["name"])
                    log(tr("gprof.log_on", game=g["name"]))
                a.update(power=p["power"], boost=p["boost"], want_prio=p["prio"])
                new = {pid: n for pid, n in pids.items() if pid not in a["done"]}
                a["done"] = set(pids)
                self._apply_prio(a, new, log, res)
            self._sync_power(log, res)
            self._sync_booster(log, res, started)
            self._save_state()
            return res

    def _apply_prio(self, a: dict, pids: dict, log, res: dict) -> None:
        want = PRIO_CLASS.get(a.get("want_prio"))
        if not want:
            return
        for pid, name in sorted(pids.items()):
            old = _get_prio(pid)
            if not old:
                log(tr("gprof.prio_fail", exe=name))
                res["fail"] += 1
                continue
            if old == want:
                continue
            if old not in F.PRIORITY_CLASSES:  # realtime чи щось нестандартне — поставили не ми, не чіпаємо
                log(tr("gprof.prio_skip", exe=name))
                continue
            a["prio"][pid] = [name, old, want]
            self._save_state()  # запис «що повертати» — до зміни
            if _set_prio(pid, want):
                res["ok"] += 1
                log(tr("gprof.prio_set", exe=name, prio=tr(f"gprof.prio.{a['want_prio']}")))
            else:
                a["prio"].pop(pid, None)
                res["fail"] += 1
                log(tr("gprof.prio_fail", exe=name))

    def _restore_prio(self, a: dict, log, res: dict) -> None:
        if not a.get("prio"):
            return
        alive = {pid: (n or "").lower() for pid, n in _procs()}
        for pid, (name, old, new) in list(a["prio"].items()):
            if alive.get(pid) == name.lower() and _get_prio(pid) == new:
                if _set_prio(pid, old):
                    log(tr("gprof.prio_back", exe=name))
                else:
                    res["fail"] += 1
                    log(tr("gprof.prio_fail", exe=name))
        a["prio"] = {}

    def _undo_power(self, log, res: dict) -> bool:
        if not E.JOURNAL.has(POWER_ID):
            return True
        E.undo_ids([POWER_ID], log, by="gameprof")
        if E.JOURNAL.has(POWER_ID):  # лишилося в журналі — повторимо пізніше (чи OptimaX-Rescue.cmd)
            res["fail"] += 1
            log(tr("gprof.power_undo_fail"))
            return False
        return True

    def _sync_power(self, log, res: dict) -> None:
        want = max((a.get("power") for a in self.active.values() if a.get("power") in POWER_RANK),
                   key=POWER_RANK.get, default=None)
        if want is None:
            if self.power is not None:
                self._undo_power(log, res)
            self.power = None
            return
        if want == self.power:  # уже пробували (вдалося, не вдалося чи схему повернули вручну) — не повторюємо
            return
        self.power = want
        if not self._undo_power(log, res):  # інша ціль: спершу повертаємо початкову схему, потім нову
            return
        st = F.CFG["booster_state"]
        if F.BOOSTER.active and isinstance(st, dict) and isinstance(st.get("plan"), str):
            log(tr("gprof.power_booster"))  # схему вже змінив режим гри — він її й поверне
            return
        r = E.apply_tweaks([power_tweak(want)], log, header=False, by="gameprof")
        res["ok"] += int(r.get("ok") or 0)
        res["fail"] += int(r.get("fail") or 0) + int(r.get("partial") or 0)

    def _sync_booster(self, log, res: dict, started: list) -> None:
        want = any(a.get("boost") for a in self.active.values())
        if want and not F.BOOSTER.active:
            first = next((k for k in started if self.active[k].get("boost")), None)
            if first is None:  # режим гри вимкнули вручну під час гри — не вмикаємо знову
                return
            skip = ["prio"] if any(PRIO_CLASS.get(a.get("want_prio")) for a in self.active.values()) else []
            if E.JOURNAL.has(POWER_ID):
                skip.append("power")
            F.BOOSTER.start(log, game=self.active[first]["main"] or None, skip=tuple(skip))
            self.booster_ours = F.BOOSTER.active
        elif not want and self.booster_ours:
            if F.BOOSTER.active:
                F.BOOSTER.stop(log)
            self.booster_ours = False

    # ── закриття OptimaX і відновлення після аварії ──
    @E._serial
    def stop_all(self, log) -> dict:
        """OptimaX закривається: усе, що змінили профілі, — як до гри."""
        with self.lock:
            res = {"ok": 0, "fail": 0, "ended": []}
            for key, a in list(self.active.items()):
                self._restore_prio(a, log, res)
                self._hist(key, a)
                res["ended"].append(a["name"])
            self.active.clear()
            self.seen = {}
            self.power = None
            self._undo_power(log, res)
            if self.booster_ours and F.BOOSTER.active:
                F.BOOSTER.stop(log)
            self.booster_ours = False
            self._save_state()
            return res

    @E._serial
    def recover(self, log) -> dict:
        """Запуск OptimaX після аварії посеред гри: повернути схему живлення (журнал) і пріоритети (лише перевірені
        записи: процес той самий і досі має пріоритет, який поставив профіль)."""
        with self.lock:
            res = {"ok": 0, "fail": 0, "did": False}
            try:
                if E.JOURNAL.has(POWER_ID):
                    res["did"] = True
                    self._undo_power(log, res)
                st = F.CFG[STATE_KEY]
                items = st.get("prio") if isinstance(st, dict) else None
                if isinstance(items, list) and items:
                    names = {e for g, _p in watched().values() for e in g["exes"]}
                    alive = {pid: (n or "").lower() for pid, n in _procs()}
                    for it in items[:MAX_STATE]:
                        if not (isinstance(it, list) and len(it) == 4):
                            continue
                        pid, name, old, new = it
                        if not (isinstance(pid, int) and not isinstance(pid, bool) and isinstance(name, str)
                                and name.lower() in names and old in F.PRIORITY_CLASSES
                                and new in PRIO_CLASS.values() and old != new):
                            continue
                        if alive.get(pid) == name.lower() and _get_prio(pid) == new:
                            res["did"] = True
                            if _set_prio(pid, old):
                                log(tr("gprof.prio_back", exe=name))
                            else:
                                res["fail"] += 1
                if st is not None:
                    F.CFG[STATE_KEY] = None
            finally:
                self.ready = True
            return res

    # ── стан на диску ──
    def _save_state(self) -> None:
        prio = [[pid, n, old, new] for a in self.active.values() for pid, (n, old, new) in a["prio"].items()]
        state = None
        if self.active or self.booster_ours:
            state = {"ts": int(time.time()), "games": sorted(self.active), "prio": prio[:MAX_STATE],
                     "booster": self.booster_ours}
        if F.CFG[STATE_KEY] != state:
            F.CFG[STATE_KEY] = state

    def _hist(self, key: str, a: dict) -> None:
        data = hist_all()
        rows = data.get(key, [])
        rows.append([int(a.get("since") or 0), int(time.time())])
        data[key] = rows[-HIST_KEEP:]
        F.CFG[HIST_KEY] = data


def needs_recovery() -> bool:
    st = F.CFG[STATE_KEY]
    return E.JOURNAL.has(POWER_ID) or bool(isinstance(st, dict) and st.get("prio"))


MANAGER = Manager()


# ───────────────────────── історія FPS гри ─────────────────────────
def hist_all() -> dict:
    """Сесії ігор з активним профілем: {key: [[початок, кінець], …]} (лише цілі числа)."""
    raw = F.CFG[HIST_KEY]
    out = {}
    if isinstance(raw, dict):
        for k, rows in raw.items():
            if isinstance(k, str) and isinstance(rows, list):
                ok = [[int(r[0]), int(r[1])] for r in rows[-HIST_KEEP:] if isinstance(r, list) and len(r) == 2
                      and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in r)]
                if ok:
                    out[k] = ok
    return out


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def fps_info(g: dict) -> dict:
    """Заміри FPS цієї гри — лише справжні: тест «до/після» (fpstest, розділ «Діагностика») і фонові записи
    бібліотеки, позначені «з профілем», якщо запис зроблено, поки профіль був активний."""
    import fpstest as FT
    import library as LB
    s = sane_game(g)
    if not s:
        return {}
    best, best_ts = None, -1
    for path, t in (F.CFG["fps_tests"] or {}).items():
        if not (isinstance(path, str) and isinstance(t, dict)) or ntpath.basename(path).lower() not in s["exes"]:
            continue
        ts = max((_num((t.get(k) or {}).get("ts")) or 0) if isinstance(t.get(k), dict) else 0
                 for k in ("before", "after"))
        if ts > best_ts:
            best, best_ts = (path, t), ts
    out = {"path": "", "before": {}, "after": {}, "cmp": {}, "rows": []}
    if best:
        path, t = best
        b = FT.as_summary(t.get("before")) if isinstance(t.get("before"), dict) else {}
        a = FT.as_summary(t.get("after")) if isinstance(t.get("after"), dict) else {}
        b = b if _num(b.get("avg")) else {}
        a = a if _num(a.get("avg")) else {}
        out.update(path=path, before=b, after=a)
        if b and a:
            try:
                out["cmp"] = FT.compare_runs(b, a)
            except (TypeError, ValueError, KeyError):
                out["cmp"] = {}
    spans = hist_all().get(s["key"], [])
    since = MANAGER.since(s["key"])
    if since:
        spans = spans + [[since, int(time.time())]]
    for r in LB.fps_history(s["exes"])[-6:]:
        avg, ts = _num(r.get("avg")), _num(r.get("ts"))
        if not avg or not ts:
            continue
        out["rows"].append(dict(ts=int(ts), avg=avg, low1=_num(r.get("low1")),
                                prof=any(a <= ts <= b for a, b in spans)))
    return out


def summary(p: dict) -> str:
    """«Ultimate · GPU: висока продуктивність · пріоритет: високий · режим гри»."""
    if not is_set(p):
        return tr("gprof.none")
    parts = []
    if p["power"] != "keep":
        parts.append(tr(f"gprof.power.{p['power']}"))
    if p["gpu"] != "keep":
        parts.append(tr("gprof.sum_gpu", v=tr(f"gprof.gpu.{p['gpu']}")))
    if p["prio"] != "keep":
        parts.append(tr("gprof.sum_prio", v=tr(f"gprof.prio.{p['prio']}")))
    if p["boost"]:
        parts.append(tr("gprof.sum_boost"))
    text = " · ".join(parts)
    return text if p["enabled"] else tr("gprof.sum_off", v=text)
