"""
OptimaX — розумна оптимізація: замір до змін, застосування, замір після, і лишаємо тільки те, що не шкодить.

Session — лише логіка, без інтерфейсу й без системних викликів (її перевіряють тести на симульованих замірах):
    a = s.next()        наступна дія: measure | apply | undo | reboot | done
    s.feed(metric)      результат заміру: {"avg": FPS, "low1": FPS}
    s.ok(applied=[…])   дію apply/undo/reboot виконано (applied — що справді застосувалося)

Як шукаємо винних: якщо після змін стало гірше, відкочуємо половину підозрюваних і міряємо ще раз.
Повернулося до норми — винний у відкоченій половині, ні — в іншій. Так за 4–5 замірів знаходимо
1–2 зміни, які шкодять саме цьому ПК, а решту залишаємо.

Перевіряються лише зміни, що діють одразу. Ті, що потребують перезавантаження, міряються разом
(OptimaX перезавантажує ПК і продовжує сам); якщо регрес пояснити не вдалося — пропонуємо відкотити все.
"""
from __future__ import annotations

import math
import time

PERF_GROUPS = ("perf", "gaming", "hw", "lite", "svc", "visual", "laptop")
MIN_NOISE = 0.02  # навіть стабільний тест «гуляє» на 1–2% між запусками
MAX_ROUNDS = 12
MAX_CULPRITS = 2
# Скільки замірів «до» і «після» (6.4): медіана трьох прогонів не зсувається від одного невдалого, а розкид між
# ними показує похибку — приріст, менший за неї, не вважається доведеним.
BASE_RUNS = 3
AFTER_RUNS = 3
MEDIAN_EFF = 1.57  # дисперсія медіани ≈ π/2 дисперсії середнього
# Двосторонній 95% квантиль Стьюдента за ступенями свободи: розкид, оцінений лише з 3 прогонів, сам неточний,
# тож множник більший за «2 сигми» (з 3+3 замірами — 2.78, з 5+5 — 2.31).
_T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 12: 2.18,
        16: 2.12, 20: 2.09, 30: 2.04}


def t95(df: int) -> float:
    """Множник похибки для df ступенів свободи; без оцінки розкиду (df ≤ 0) — 2, як для відомого розкиду."""
    if df <= 0:
        return 2.0
    for k in sorted(_T95):
        if df <= k:
            return _T95[k]
    return 1.96


def split_plan(ids, tweaks: dict) -> tuple:
    """-> (live — продуктивність, діють одразу; boot — продуктивність після перезавантаження; other — решта)."""
    live, boot, other = [], [], []
    for tid in ids:
        t = tweaks.get(tid)
        if t is None:
            continue
        if t.group in PERF_GROUPS and t.reversible and not t.custom:
            (boot if t.reboot else live).append(tid)
        else:
            other.append(tid)
    return live, boot, other


def _median(vals: list) -> float:
    v = sorted(vals)
    if not v:
        return 0.0
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def mean_metric(ms: list) -> dict:
    """Центр кількох замірів — медіана кожної метрики (назва лишилася з 6.3, де це було середнє)."""
    if not ms:
        return {"avg": 0.0, "low1": 0.0, "low01": 0.0}
    return {k: round(_median([m.get(k) or m["avg"] for m in ms]), 2) for k in ("avg", "low1", "low01")}


def cv(ms: list, key: str = "avg"):
    """Відносний розкид між замірами (None, якщо замір один)."""
    v = [m[key] for m in ms if m.get(key)]
    if len(v) < 2:
        return None
    mean = sum(v) / len(v)
    return math.sqrt(sum((x - mean) ** 2 for x in v) / (len(v) - 1)) / mean if mean else None


def rel(x: float, base: float) -> float:
    return (x - base) / base if base else 0.0


class Session:
    def __init__(self, live=(), boot=(), other=(), mode: str = "new", provider: str = "gpu", game: str = None):
        self.mode = mode  # new — нові зміни; audit — перевірка вже застосованих
        self.provider = provider  # gpu — GPU-тест OptimaX; game — ваша гра через PresentMon
        self.game = game
        self.live, self.boot, self.other = list(live), list(boot), list(other)
        self.stage = "init"
        self.base, self.after, self.probes = [], [], []
        self.current = None  # замір поточного стану (усе застосоване, крім прибраних)
        self.overall = None  # результат «після» щодо «до»: better | same | worse
        self.queue, self.half, self.removed = [], [], []
        self.scan_halves, self.scan_i = [], 0
        self.purpose = None
        self.rounds = 0
        self.result = None
        self.final = None
        self.pending = None
        self.events = []  # [(ключ, параметри)] — для журналу в інтерфейсі
        self.ts = int(time.time())

    # ── збереження (продовжити після перезавантаження) ──
    def to_dict(self) -> dict:
        return {k: v for k, v in vars(self).items()}

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        s = cls()
        for k, v in d.items():
            setattr(s, k, v)
        return s

    # ── оцінка ──
    @property
    def baseline(self) -> dict:
        return mean_metric(self.base)

    @property
    def noise(self) -> float:
        """Розкид одного заміру щодо інших (за замірами «до»)."""
        c = cv(self.base)
        return MIN_NOISE if c is None else max(MIN_NOISE, c)

    def margin(self, key: str = "avg") -> float:
        """Похибка порівняння медіан «до» і «після»: 2 стандартні похибки різниці (≈95%), не менше MIN_NOISE."""
        floor = {"avg": MIN_NOISE, "low1": 2 * MIN_NOISE, "low01": 4 * MIN_NOISE}[key]
        cb = cv(self.base, key)
        ca = cv(self.after, key) if len(self.after) > 1 else cb
        df = (len(self.base) - 1 if cb is not None else 0) + (len(self.after) - 1 if len(self.after) > 1 else 0)
        cb = floor if cb is None else cb
        ca = floor if ca is None else ca
        se2 = MEDIAN_EFF * (cb ** 2 / max(1, len(self.base)) + ca ** 2 / max(1, len(self.after)))
        return max(floor, t95(df) * math.sqrt(se2))

    def _cmp(self, m: dict, ref: dict) -> str:
        n = self.noise
        da, dl = rel(m["avg"], ref["avg"]), rel(m["low1"], ref["low1"])
        if da < -max(n * 1.5, 0.02) or dl < -max(n * 3, 0.04):
            return "worse"
        if da > max(n * 1.5, 0.02) or dl > max(n * 3, 0.04):
            return "better"
        return "same"

    def verdict(self, m: dict) -> str:
        """better | same | worse щодо заміру до змін, з урахуванням розкиду між замірами."""
        return self._cmp(m, self.baseline)

    def after_verdict(self) -> str:
        """Медіана замірів «після» проти медіани «до»: зміна має перевищити похибку (margin), інакше same."""
        m, b = mean_metric(self.after), self.baseline
        da, dl = rel(m["avg"], b["avg"]), rel(m["low1"], b["low1"])
        ma, ml = self.margin("avg"), self.margin("low1")
        if da < -ma or dl < -ml:
            return "worse"
        if da > ma or dl > ml:
            return "better"
        return "same"

    def delta(self, m: dict) -> dict:
        b = self.baseline
        out = {"avg": round(rel(m["avg"], b["avg"]) * 100, 1), "low1": round(rel(m["low1"], b["low1"]) * 100, 1)}
        if m.get("low01") and b.get("low01"):
            out["low01"] = round(rel(m["low01"], b["low01"]) * 100, 1)
        return out

    # ── кроки ──
    def _act(self, do: str, **kw) -> dict:
        self.pending = dict(do=do, **kw)
        return self.pending

    def _log(self, key: str, **kw) -> None:
        self.events.append((key, kw))

    def applied_live(self) -> list:
        return [i for i in self.live if i not in self.removed]

    def _halves(self, ids: list) -> tuple:
        k = len(ids) // 2
        return ids[:k], ids[k:]

    def next(self) -> dict:
        if self.pending:
            return self.pending
        st = self.stage
        if st == "init":
            if self.mode == "audit" and self.live:
                return self._act("undo", ids=list(self.live), why="audit")
            self.stage = "base"
            return self.next()
        if st == "base":
            if len(self.base) < BASE_RUNS:
                return self._act("measure", label="base", n=len(self.base) + 1)
            self.stage = "apply"
            return self.next()
        if st == "apply":
            ids = (self.other + self.live + self.boot) if self.mode == "new" else list(self.live)
            return self._act("apply", ids=ids, why="apply")
        if st == "reboot":
            return self._act("reboot")
        if st == "after":
            if len(self.after) < AFTER_RUNS:  # стільки ж замірів, скільки «до»: приріст має перевищити похибку
                return self._act("measure", label="after", n=len(self.after) + 1)
            v = self.after_verdict()
            self.current = self.final = mean_metric(self.after)
            self.overall = v
            live = self.applied_live()
            if v == "worse":
                self._log("sm.ev_worse", **self.delta(self.current))
                if not live:
                    return self._finish("unexplained")
                self.queue, self.stage = live, "search"
            elif len(live) >= 4:  # навіть якщо загалом краще — шукаємо зміну, що тихо з'їдає частину приросту
                self.scan_halves, self.scan_i, self.stage = list(self._halves(live)), 0, "scan"
            else:
                return self._finish(v)
            return self.next()
        if st == "scan":
            if self.scan_i >= len(self.scan_halves) or self.rounds >= MAX_ROUNDS:
                return self._finish("fixed" if self.removed else self.overall)
            self.half, self.purpose = list(self.scan_halves[self.scan_i]), "scan"
            self.stage = "probe"
            return self._act("undo", ids=list(self.half), why="probe")
        if st == "search":
            if self.rounds >= MAX_ROUNDS or not self.queue:
                return self._finish("fixed" if self.removed else ("unexplained" if self.overall == "worse"
                                                                  else self.overall))
            if len(self.queue) == 1:
                self.half, self.stage = list(self.queue), "confirm"
                return self._act("undo", ids=list(self.half), why="culprit")
            self.half, self.purpose = list(self._halves(self.queue)[0]), "search"
            self.stage = "probe"
            return self._act("undo", ids=list(self.half), why="probe")
        if st == "probe":
            return self._act("measure", label="probe", n=self.rounds + 1)
        if st == "reapply":
            return self._act("apply", ids=list(self.half), why="reapply")
        if st == "confirm":
            return self._act("measure", label="check", n=len(self.removed) + 1)
        if st == "restore":
            return self._act("apply", ids=list(self.half), why="restore")
        if st == "done":
            return dict(do="done", result=self.result)
        raise ValueError(st)

    def _finish(self, result: str) -> dict:
        self.result = result
        self.stage = "done"
        self.pending = None
        self._log(f"sm.ev_{result}", n=len(self.removed))
        return dict(do="done", result=result)

    def ok(self, applied=None) -> None:
        """Дію apply/undo/reboot виконано. applied — id, які після дії справді є в журналі змін."""
        a, self.pending = self.pending, None
        if not a:
            return
        why = a.get("why")
        if a["do"] == "undo" and why == "audit":
            self.stage = "base"
        elif a["do"] == "apply" and why == "apply":
            if applied is not None:
                have = set(applied)
                self.live = [i for i in self.live if i in have]
                self.boot = [i for i in self.boot if i in have]
            self._log("sm.ev_applied", n=len(a["ids"]))
            self.stage = "reboot" if (self.boot and self.mode == "new") else "after"
        elif a["do"] == "apply" and why == "reapply":
            if self.purpose == "scan" and self.stage == "reapply":
                self.stage = "scan"
            else:
                self.stage = "search"
        elif a["do"] == "apply" and why == "restore":
            self._log("sm.ev_false", id=self.half[0])
            self.stage = "search"
            self.queue = []  # підозра не підтвердилась — більше не шукаємо
        elif a["do"] == "reboot":
            self.stage = "after"

    def feed(self, m: dict) -> None:
        a, self.pending = self.pending, None
        m = {"avg": float(m["avg"]), "low1": float(m.get("low1") or m["avg"]),
             "low01": float(m.get("low01") or m.get("low1") or m["avg"])}
        label_ = a["label"] if a else "base"
        if label_ == "base":
            self.base.append(m)
            self._log("sm.ev_base", n=len(self.base), avg=round(m["avg"], 1))
        elif label_ == "after":
            self.after.append(m)
            self._log("sm.ev_after", avg=round(m["avg"], 1), d=self.delta(m)["avg"])
        elif label_ == "probe":
            self.rounds += 1
            self.probes.append(m)
            hit = self._cmp(m, self.current) == "better"  # без цієї половини стало краще → шкода в ній
            self._log("sm.ev_probe_hit" if hit else "sm.ev_probe_miss", n=len(self.half))
            if self.purpose == "scan":
                if hit:
                    self.queue, self.purpose = list(self.half), "search"
                else:
                    self.scan_i += 1
            else:
                self.queue = self.half if hit else [i for i in self.queue if i not in self.half]
            self.stage = "reapply"
        elif label_ == "check":
            self.probes.append(m)
            c = self.half[0]
            if self._cmp(m, self.current) == "better" or (self.overall == "worse" and self.verdict(m) != "worse"):
                self.removed.append(c)
                self.current = self.final = m
                self._log("sm.ev_culprit", id=c)
                live = self.applied_live()
                if len(self.removed) >= MAX_CULPRITS or self.rounds >= MAX_ROUNDS:
                    self.queue, self.stage = [], "search"
                elif self.verdict(m) == "worse":
                    self.queue, self.stage = live, "search"
                elif len(live) >= 4:  # може бути ще одна — швидко перевіряємо обидві половини
                    self.scan_halves, self.scan_i, self.stage = list(self._halves(live)), 0, "scan"
                else:
                    self.queue, self.stage = [], "search"
            else:
                self.stage = "restore"  # без неї не краще — повертаємо

    # ── підсумок ──
    def summary(self) -> dict:
        final = self.final or (mean_metric(self.after) if self.after else None)
        delta = self.delta(final) if (final and self.base) else None
        mg = round(self.margin("avg") * 100, 1) if (self.base and self.after) else None
        return dict(result=self.result, mode=self.mode, provider=self.provider, game=self.game,
                    base=self.baseline if self.base else None, final=final, delta=delta,
                    margin=mg, significant=bool(delta and mg is not None and abs(delta["avg"]) > mg),
                    runs={"base": len(self.base), "after": len(self.after)}, removed=list(self.removed),
                    kept=[i for i in self.live + self.boot + self.other if i not in self.removed],
                    measured=[i for i in self.live + self.boot if i not in self.removed],
                    measures=len(self.base) + len(self.after) + len(self.probes), ts=self.ts)


def update_evidence(ev: dict, sm: dict, now: int = None) -> dict:
    """Що розумна оптимізація довела про зміни на цьому ПК (для режимів оптимізації):
    harm — зміну знайдено шкідливою (відкочено); help — пакет, у якому вона була, дав приріст понад похибку;
    none — пакет не дав різниці понад похибку. Лічильники накопичуються між сесіями."""
    ev = {k: dict(v) for k, v in (ev or {}).items()}
    now = int(time.time()) if now is None else now
    for tid in sm.get("removed") or []:
        e = ev.setdefault(tid, {})
        e["harm"] = e.get("harm", 0) + 1
        e["ts"] = now
    d = (sm.get("delta") or {}).get("avg") or 0
    outcome = None
    if sm.get("result") in ("better", "fixed") and sm.get("significant") and d > 0:
        outcome = "help"
    elif sm.get("result") == "same":
        outcome = "none"
    if outcome:
        for tid in sm.get("measured") or []:
            e = ev.setdefault(tid, {})
            e[outcome] = e.get(outcome, 0) + 1
            e["ts"] = now
    return ev


def evidence_state(e: dict) -> str:
    """harmful | proven | no_effect | unknown — для однієї зміни за накопиченими сесіями."""
    e = e or {}
    if e.get("harm", 0) > 0 and e.get("harm", 0) >= e.get("help", 0):
        return "harmful"
    if e.get("help", 0) > 0:
        return "proven"
    if e.get("none", 0) >= 2:
        return "no_effect"
    return "unknown"
