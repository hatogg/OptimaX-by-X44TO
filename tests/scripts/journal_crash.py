"""Надійний відкат (6.4) на фальшивій Windows: аварія посеред оптимізації, помилка посеред оптимізації, збій
запису журналу, частковий відкат, конфлікти, права адміністратора.

Запуск: FAKE_TARGET=tests/scripts/journal_crash.py python tests/scripts/fake_windows.py --out DIR
(реєстр — у пам'яті процесу, тож «перезапуск програми» тут — новий об'єкт журналу з того самого файлу)."""
import json
import os
import sys

import engine as E

R = {}
LOG = []
log = LOG.append


class Crash(BaseException):
    """Аварійне завершення: як зняли процес чи вимкнули світло — жоден except Exception його не перехопить."""


def regs(t):
    return [op for op in t.ops if op[0] == "reg" and not callable(op[3])]


def snapshot(tweaks):
    return {f"{op[1]}|{op[2]}": E.reg_get(op[1], op[2]) for t in tweaks for op in regs(t)}


def pick(n=3, hive="HKLM", skip=()):
    """Твіки лише з операцій реєстру: їхній стан повністю видно в REG."""
    out = []
    for t in E.TWEAKS:
        if t.id in skip or not t.reversible or t.reboot:
            continue
        ops = t.ops
        if len(ops) >= n and all(op[0] == "reg" and not callable(op[3]) for op in ops) and \
                all(str(op[1]).upper().startswith(hive) for op in ops):
            out.append(t)
    return out


def part(tweaks):
    """Початкові значення лише цих твіків."""
    return {k: initial[k] for k in snapshot(tweaks)}


def restart():
    """Новий процес OptimaX: журнал читається з диска заново."""
    E.JOURNAL = E.Journal(E.JOURNAL_PATH)
    return E.JOURNAL


_set = E.reg_set


def crash_on(n):
    calls = [0]

    def rs(*a, **k):
        calls[0] += 1
        if calls[0] == n:
            raise Crash()
        return _set(*a, **k)
    return rs


def fail_on(n, exc=PermissionError):
    calls = [0]

    def rs(*a, **k):
        calls[0] += 1
        if calls[0] == n:
            raise exc(5, "Access is denied")
        return _set(*a, **k)
    return rs


cands = pick(3)
assert len(cands) >= 3, [t.id for t in cands]
A, B, C = cands[:3]
R["tweaks"] = [A.id, B.id, C.id]
initial = snapshot([A, B, C])

# 1. Аварія посеред першої оптимізації: її записи вже на диску, а в журналі відкату пункту ще немає
E.reg_set = crash_on(2)
try:
    E.apply_tweaks([A, B], log, header=False)
    R["crash1_raised"] = False
except Crash:
    R["crash1_raised"] = True
E.reg_set = _set
R["crash1_changed"] = snapshot([A]) != part([A])
R["crash1_wal"] = os.path.exists(E.JOURNAL.wal)
R["crash1_in_journal"] = E.JOURNAL.has(A.id)
j = restart()
res = E.recover_interrupted(log)
R["crash1_recover"] = {"tweak": res["tweak"], "failed": res["failed"], "op": bool(res["op"]), "ids": res["ids"]}
R["crash1_restored"] = snapshot([A, B, C]) == initial
R["crash1_wal_gone"] = not os.path.exists(j.wal)
R["crash1_op_cleared"] = j.op() is None

# 2. Аварія в другій оптимізації пакета: першу (уже записану) пропонуємо відкотити, другу повертаємо самі
E.reg_set = crash_on(len(regs(A)) + 2)
try:
    E.apply_tweaks([A, B], log, header=False)
except Crash:
    pass
E.reg_set = _set
j = restart()
res = E.recover_interrupted(log)
R["crash2_recover"] = {"tweak": res["tweak"], "op": (res["op"] or {}).get("kind"), "ids": res["ids"]}
R["crash2_b_restored"] = snapshot([B]) == part([B])
E.undo_ids(res["ids"], log)  # користувач погодився відкотити перерваний пакет
R["crash2_all_restored"] = snapshot([A, B, C]) == initial
R["crash2_op_cleared"] = j.op() is None and j.count() == 0

# 3. Звичайна помилка посеред оптимізації (немає доступу до ключа): пункт повертається одразу, пакет іде далі
E.reg_set = fail_on(2)
out = E.apply_tweaks([A, C], log, header=False)
E.reg_set = _set
R["fail3"] = {"ok": out["ok"], "fail": out["fail"], "a_in_journal": E.JOURNAL.has(A.id),
              "c_in_journal": E.JOURNAL.has(C.id), "wal": os.path.exists(E.JOURNAL.wal)}
R["fail3_a_restored"] = snapshot([A]) == part([A])
E.undo_ids([C.id], log)
R["fail3_all_restored"] = snapshot([A, B, C]) == initial

# 4. Журнал не записується (диск повний): нічого не змінюємо
_wa = E._write_atomic


def broken_write(path, data, durable):
    if path.endswith(".pending.json"):
        raise OSError(28, "No space left on device")
    return _wa(path, data, durable)


E._write_atomic = broken_write
out = E.apply_tweaks([A, B], log, header=False)
E._write_atomic = _wa
R["full4"] = {"error": out.get("error"), "ok": out["ok"], "unchanged": snapshot([A, B, C]) == initial,
              "journal": E.JOURNAL.count()}

# 5. Частковий відкат: крок, який не повернувся, лишається в журналі; повторний відкат завершує справу
E.apply_tweaks([A], log, header=False)
E.reg_set = fail_on(1)
r1 = E.undo_ids([A.id], log)
E.reg_set = _set
left = (E.JOURNAL.get(A.id) or {}).get("undo", [])
R["partial5"] = {"partial": r1["partial"], "undone": r1["undone"], "left": len(left),
                 "marked": bool((E.JOURNAL.get(A.id) or {}).get("partial"))}
r2 = E.undo_ids([A.id], log)
R["partial5_retry"] = {"undone": r2["undone"], "in_journal": E.JOURNAL.has(A.id),
                       "restored": snapshot([A]) == part([A])}

# 6. Пошкоджений журнал: відновлення з резервної копії, зіпсований файл відкладено
E.apply_tweaks([A], log, header=False)
E.apply_tweaks([B], log, header=False)  # друге збереження — у .bak уже є запис про A
with open(E.JOURNAL_PATH, "w", encoding="utf-8") as f:
    f.write('{"applied": {"x": ')  # обірваний запис
j = restart()
corrupt = [n for n in os.listdir(os.path.dirname(E.JOURNAL_PATH)) if ".corrupt-" in n]
R["corrupt6"] = {"problem": j.problem, "has_a": j.has(A.id), "has_b": j.has(B.id), "quarantined": len(corrupt)}
j.end_op()
for p in (E.JOURNAL_PATH, E.JOURNAL_PATH + ".bak"):
    with open(p, "w", encoding="utf-8") as f:
        f.write("garbage")
j2 = E.Journal(E.JOURNAL_PATH)
R["corrupt6_lost"] = j2.problem
E.JOURNAL = j
E.undo_ids(E.JOURNAL.newest_first(), log)

# 7. Конфлікти: «Агресивний Turbo» і «Тихий режим» разом не застосовуються
out = E.apply_tweaks([E.BY_ID["turbo_aggressive"], E.BY_ID["cool_mode"]], log, header=False)
R["conflict7"] = {"dropped": [d[0] for d in out["conflicts"]], "turbo": E.JOURNAL.has("turbo_aggressive"),
                  "cool": E.JOURNAL.has("cool_mode")}
out = E.apply_tweaks([E.BY_ID["cool_mode"]], log, header=False)
R["conflict7_applied"] = {"dropped": [d[0] for d in out["conflicts"]], "cool": E.JOURNAL.has("cool_mode")}
E.undo_ids(E.JOURNAL.newest_first(), log)
R["conflict_symmetric"] = all(t.id in E.conflicts_of(o) for t in E.TWEAKS for o in t.conflicts)

# 8. Без прав адміністратора: системні параметри пропускаються, параметри користувача застосовуються
hkcu = pick(1, "HKCU")
_adm = E.is_admin
E.is_admin = lambda: False
out = E.apply_tweaks([A, hkcu[0]], log, header=False)
E.is_admin = _adm
R["admin8"] = {"skipped": out["skipped"], "ok": out["ok"], "a": E.JOURNAL.has(A.id), "user": E.JOURNAL.has(hkcu[0].id),
               "a_unchanged": snapshot([A]) == part([A])}
E.undo_ids(E.JOURNAL.newest_first(), log)
R["end_clean"] = snapshot([A, B, C]) == initial and E.JOURNAL.count() == 0

# 9. Знімок початкових налаштувань: журнал загубився — OptimaX усе одно знаходить і повертає свої зміни
import baseline as BL  # noqa: E402  (реєструє знімок перед першою зміною пакета)
if os.path.exists(BL.PATH):
    os.remove(BL.PATH)
E.apply_tweaks([A], log, header=False)
snap_made = os.path.exists(BL.PATH)
os.remove(BL.PATH)
fresh = BL.capture()  # A вже застосовано: «до» для його параметрів береться з журналу, а не з реєстру
R["baseline_from_journal"] = all(fresh["reg"].get(f"{op[1]}|{op[2]}") == E.JOURNAL.get(A.id)["undo"][i]["old"]
                                 for i, op in enumerate(regs(A)))
E.undo_ids([A.id], log)
BL.ensure(log)
E.apply_tweaks([A, B], log, header=False)
lost = E.Journal(E.JOURNAL_PATH + ".lost-test")  # журнал загубився: про зміни A і B він нічого не знає
orph = BL.orphans(journal=lost)
R["baseline9"] = {"made": snap_made, "orphans": sorted({t for o in orph for t in o["tweaks"]} & {A.id, B.id}),
                  "covered": len(BL.orphans())}
BL.restore(orph, log)
R["baseline9_restored"] = snapshot([A, B]) == part([A, B])
E.JOURNAL.data["applied"].clear()  # система вже як до OptimaX — записи журналу більше не потрібні
E.JOURNAL._save()

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "roundtrip.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
