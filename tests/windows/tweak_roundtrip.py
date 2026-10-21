"""
OptimaX — перевірка твіків на справжній Windows (для CI: GitHub Actions windows-2022 / windows-2025).

Для кожного твіка: застосувати → перевірити, що значення справді змінились → відкотити →
перевірити, що КОЖЕН запис журналу відкату повернув початковий стан. Потім те саме пакетом
(як у програмі) з відкатом через згенерований OptimaX-Rescue.cmd /all і ще раз — через журнал програми.

    python tests/windows/tweak_roundtrip.py --out roundtrip [--only id,id] [--no-batch] [--no-rescue]

!!! ЗМІНЮЄ СИСТЕМУ. Запускається лише на одноразовій машині CI (змінна CI) або з --yes-change-this-pc.
Код виходу: 0 — усе гаразд, 1 — є невідновлені зміни або твіки без ефекту.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

# Не в CI: вони перепідключають мережеві адаптери — машина CI втратить зв'язок із GitHub
SKIP = {
    "nic_power": "resets network adapters (the CI runner would lose its connection)",
    "wifi_gaming": "resets the Wi-Fi adapter",
    "ethernet_latency": "resets the Ethernet adapter",
    "remove_onedrive": "uninstalls OneDrive; restoring reinstalls it, not a byte-exact rollback",
    "compact_os": "compresses the whole OS for many minutes",
}
# Можуть не застосуватися на машині CI з причин, що не залежать від OptimaX: звіт показує їх, але не валить збірку
ALLOW_FAIL = {
    "disable_defender": "Tamper Protection on the runner may block Defender policies",
    "defender_limit": "Tamper Protection on the runner may block Defender settings",
    "ai_recall": "the Recall feature may be missing from the runner image",
    "reserved_storage_off": "reserved storage can be locked while updates are pending",
    "hibernation_off": "hibernation may be unsupported on the VM",
}


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="roundtrip")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-batch", action="store_true")
    ap.add_argument("--no-rescue", action="store_true")
    ap.add_argument("--yes-change-this-pc", action="store_true")
    ap.add_argument("--budget-min", type=float, default=0,
                    help="stop starting new checks after this many minutes and still write the report")
    return ap.parse_args()


ARGS = parse_args()
if sys.platform != "win32":
    sys.exit("Windows only")
if not (os.environ.get("CI") or ARGS.yes_change_this_pc):
    sys.exit("This changes the system. It runs on a disposable CI machine (CI=true) or with --yes-change-this-pc.")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxrt_")  # окремий журнал і налаштування
sys.argv = ["x", "--lang=en"]

import engine as E  # noqa: E402
import hardware as H  # noqa: E402
import rescue as RS  # noqa: E402
from i18n import tr  # noqa: E402

if not E.is_admin():
    sys.exit("Run as administrator")
assert not E.DRY_RUN
ERR_PREFIX = tr("e.err", err="").strip()


# ───────────────────────── сторож зависань ─────────────────────────
# Журнали CI звідси не завантажити, а зависання до тайм-ауту завдання не лишає жодного звіту. Тож перевірка сама
# стежить за собою: що зараз робить і скільки; довго на одному кроці — попередження на сторінці запуску,
# дуже довго — звіт із тим, що встигли, і вихід із помилкою.
NOW = {"what": "start", "since": time.time()}
STATE = {"results": [], "batches": [], "skipped": [], "problems": [], "hw": {}, "t0": time.time()}
WARN_MIN, ABORT_MIN = 8, 20


def step(what: str) -> None:
    NOW.update(what=what, since=time.time())


def _watchdog() -> None:
    warned = None
    while True:
        time.sleep(20)
        what, mins = NOW["what"], (time.time() - NOW["since"]) / 60
        if mins > WARN_MIN and warned != (what, NOW["since"]):
            warned = (what, NOW["since"])
            print(f"::warning title=round-trip stuck::{what}: {mins:.0f} min on this step", flush=True)
        if mins > ABORT_MIN:
            STATE["problems"].append(f"stuck for {mins:.0f} min at: {what} — the check stopped here")
            try:
                write_report(build_report(ok=False))
            finally:
                os._exit(1)


# ───────────────────────── читання стану ─────────────────────────
def reg_now(path, name):
    return E.reg_get(path, name)


def same_reg(cur, old) -> bool:
    """Поточне значення реєстру проти запису журналу [тип, значення] (або None — значення не було)."""
    if old is None:
        return cur is None
    if cur is None:
        return False
    return cur[0] == old[0] and cur[1] == E._dec(old[1])


def reg_matches_target(cur, value) -> bool:
    if cur is None:
        return False
    if isinstance(value, (bytes, bytearray)):
        return bytes(cur[1]) == bytes(value)
    if isinstance(value, list):
        return list(cur[1]) == value
    return str(cur[1]).lower() == str(value).lower()


def task_states(names) -> dict:
    """{задача: True (увімкнена) | False | None (немає)} — одним запуском PowerShell на всі задачі (кожен запуск
    коштує 1–3 с, а твіки вимикають до півтора десятка задач). Стан із PowerShell не перекладається, на відміну
    від schtasks."""
    names = sorted(set(names))
    if not names:
        return {}
    arr = ",".join("'" + n.replace("'", "''") + "'" for n in names)
    q = (f"foreach ($n in @({arr})) {{ $i = $n.LastIndexOf('\\'); "
         "$t = Get-ScheduledTask -TaskPath ($n.Substring(0, $i + 1)) -TaskName ($n.Substring($i + 1)) "
         "-ErrorAction SilentlyContinue; if ($t) { $n + '|' + [string]$t.State } else { $n + '|MISSING' } }")
    _, out = E.ps(q, 120, ro=True)
    res = {n: None for n in names}
    for ln in out.splitlines():
        n, _, state = ln.strip().rpartition("|")
        if n in res and state and state != "MISSING":
            res[n] = state != "Disabled"
    return res


def task_enabled(name: str):
    return task_states([name]).get(name)


def pw_now(rec_or_op, scheme=None):
    if isinstance(rec_or_op, dict):
        return E.pw_get(rec_or_op["g"], rec_or_op["s"], rec_or_op["st"], rec_or_op.get("m") or "ac")
    _, sub, setting, _value, mode = rec_or_op
    return E.pw_get(scheme or E.active_scheme(), sub, setting, mode)


def static_targets(t) -> list:
    """Цілі операцій, які можна прочитати до застосування: реєстр, служби, параметри живлення."""
    out = []
    for op in t.ops:
        k = op[0]
        if k == "reg" and not callable(op[3]):
            out.append(("reg", op[1], op[2], op[3]))
        elif k == "regdel":
            out.append(("regdel", op[1], op[2], None))
        elif k == "svc":
            out.append(("svc", op[1], op[2], None))
        elif k == "pw":
            out.append(("pw", op, None, op[3]))
    return out


def read_target(tg, scheme=None):
    k = tg[0]
    if k in ("reg", "regdel"):
        return reg_now(tg[1], tg[2])
    if k == "svc":
        return E.svc_get_start(tg[1])
    if k == "pw":
        return pw_now(tg[1], scheme)
    return None


def key_of(tg) -> str:
    if tg[0] in ("reg", "regdel"):
        return f"reg:{tg[1].lower()}\\{tg[2].lower()}"
    if tg[0] == "svc":
        return f"svc:{tg[1].lower()}"
    _, sub, setting, _v, mode = tg[1]
    return f"pw:{sub}:{setting}:{mode}"


def service_starts() -> dict:
    """Тип запуску кожної служби І драйвера прямо з реєстру (за частку секунди замість ~10 с через CIM).
    Драйвери теж: побічна зміна запуску драйвера (клавіатура, диск, USB) — найгірше, що може зробити твік."""
    import winreg
    out, base = {}, r"SYSTEM\CurrentControlSet\Services"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as root:
        names = []
        while True:
            try:
                names.append(winreg.EnumKey(root, len(names)))
            except OSError:
                break
    for name in names:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + "\\" + name) as k:
                start = winreg.QueryValueEx(k, "Start")[0]
                try:
                    delayed = winreg.QueryValueEx(k, "DelayedAutostart")[0]
                except OSError:
                    delayed = 0
        except OSError:
            continue
        out[name] = f"{start}{' delayed' if delayed else ''}"
    return out


def invariants() -> dict:
    """Загальний стан, який твіки можуть зачепити побічно: схема живлення, BCD, TCP, запуск служб і драйверів."""
    inv = {"scheme": E.active_scheme()}
    inv["bcd"] = E.run("bcdedit /enum {current} /v", 20, ro=True)[1]
    inv["tcp"] = E.run("netsh int tcp show global", 20, ro=True)[1]
    inv["services"] = service_starts()
    return inv


def drift(a: dict, b: dict) -> list:
    out = []
    for k in ("scheme", "bcd", "tcp"):
        if a.get(k) != b.get(k):
            out.append(k)
    sa, sb = a.get("services", {}), b.get("services", {})
    out += [f"service {n}: {sa.get(n)} -> {sb.get(n)}" for n in sorted(set(sa) | set(sb)) if sa.get(n) != sb.get(n)]
    return out


def record_key(rec) -> str:
    t = rec["t"]
    if t == "reg":
        return f"reg:{rec['p'].lower()}\\{rec['n'].lower()}"
    if t == "svc":
        return f"svc:{rec['n'].lower()}"
    if t == "task":
        return f"task:{rec['n'].lower()}"
    if t == "pw":
        return f"pw:{rec['g']}:{rec['s']}:{rec['st']}:{rec.get('m') or 'ac'}"
    return f"{t}:{rec.get('c') or rec.get('k')}"


def restored(rec, tasks=None, schemes=None):
    """-> (перевірено, гаразд, опис) для одного запису журналу відкату. tasks — готові task_states(),
    schemes — GUID схем живлення, що існують зараз."""
    t = rec["t"]
    if t == "reg":
        cur = reg_now(rec["p"], rec["n"])
        return True, same_reg(cur, rec["old"]), f"{rec['p']}\\{rec['n']}: now {cur!r}, expected {rec['old']!r}"
    if t == "svc":
        cur = E.svc_get_start(rec["n"])
        return True, cur == rec["old"], f"service {rec['n']}: now {cur}, expected {rec['old']}"
    if t == "task":
        en = tasks[rec["n"]] if tasks is not None and rec["n"] in tasks else task_enabled(rec["n"])
        return True, en is not False, f"task {rec['n']}: still disabled"
    if t == "pw":
        if rec.get("old") is None:
            return False, True, ""
        if schemes is not None and rec["g"].lower() not in schemes:
            return False, True, ""  # схему видалив відкат (створена OptimaX Ultimate Performance) — нічого повертати
        cur = pw_now(rec)
        return True, cur == int(rec["old"]), f"power {rec['st']} ({rec.get('m')}): now {cur}, expected {rec['old']}"
    return False, True, ""  # cmd / ps / live — команду відкату виконано, прямо не перевіряється


def errors_in(lines) -> list:
    """Винятки під час застосування (e.err) — помилка твіка."""
    return [ln.strip() for ln in lines if ERR_PREFIX and ln.strip().startswith(ERR_PREFIX)]


def warnings_in(lines) -> list:
    """«⚠ не підтримується цим залізом» тощо — у звіт, але не помилка: залежить від машини CI."""
    return [ln.strip() for ln in lines if "⚠" in ln and not (ERR_PREFIX and ln.strip().startswith(ERR_PREFIX))]


def bad_log(lines) -> list:
    """Під час відкату будь-яке ⚠ — це виняток із undo_one."""
    return [ln.strip() for ln in lines if "⚠" in ln or (ERR_PREFIX and ln.strip().startswith(ERR_PREFIX))]


# ───────────────────────── один твік ─────────────────────────
def roundtrip(t, hw) -> dict:
    r = {"id": t.id, "title": t.title, "group": t.group, "status": "pass", "problems": [], "unchecked": 0}
    scheme0 = E.active_scheme()
    targets = static_targets(t)
    pre = {key_of(tg): read_target(tg, scheme0) for tg in targets}
    inv0 = invariants()
    probe0 = E.probe(t)
    log = []
    t0 = time.time()
    step(f"applying {t.id}")
    try:
        res = E.apply_tweaks([t], log.append, header=False, hw=hw)
    except Exception:
        r.update(status="fail", problems=["apply raised: " + traceback.format_exc()[-800:]])
        res = {"ok": 0, "skipped": 0}
    r["apply_s"] = round(time.time() - t0, 1)
    if res.get("skipped"):
        r.update(status="skip", why="; ".join(ln.strip() for ln in log[-2:]))
        return r
    entry = json.loads(json.dumps(E.JOURNAL.get(t.id) or {"undo": []}))
    undo = entry["undo"]
    r["records"] = len(undo)
    r["problems"] += [f"log: {x}" for x in errors_in(log)]
    r["warnings"] = warnings_in(log)

    # 1) застосовано?
    step(f"checking {t.id} was applied")
    scheme1 = E.active_scheme()
    for tg in targets:
        cur = read_target(tg, scheme1)
        k = tg[0]
        if k == "reg" and not reg_matches_target(cur, tg[3]):
            r["problems"].append(f"not applied: {tg[1]}\\{tg[2]} = {cur!r}, wanted {tg[3]!r}")
        elif k == "regdel" and cur is not None:
            r["problems"].append(f"not deleted: {tg[1]}\\{tg[2]} = {cur!r}")
        elif k == "svc" and pre.get(key_of(tg)) is not None and cur != tg[2]:
            r["problems"].append(f"service {tg[1]}: {cur}, wanted {tg[2]}")
        elif k == "pw" and cur is not None and cur != int(tg[3]):
            r["problems"].append(f"power {tg[1][2]}: {cur}, wanted {tg[3]}")
    states = task_states(rec["n"] for rec in undo if rec["t"] == "task")
    for n, en in states.items():
        if en:
            r["problems"].append(f"task still enabled: {n}")
    if any(op[0] == "reg" and not callable(op[3]) for op in t.ops) and not E.probe(t):
        r["problems"].append("probe() says not applied right after applying")
    if t.reversible and not undo and any(op[0] != "live" for op in t.ops) and pre and \
            any(pre[key_of(tg)] != read_target(tg, scheme1) for tg in targets):
        r["problems"].append("changed the system but wrote nothing to the rollback journal")

    # 2) відкат
    step(f"rolling back {t.id}")
    log2 = []
    try:
        E.undo_ids([t.id], log2.append)
    except Exception:
        r["problems"].append("undo raised: " + traceback.format_exc()[-800:])
    r["problems"] += [f"undo log: {x}" for x in bad_log(log2)]
    if E.JOURNAL.has(t.id):
        r["problems"].append("still in the journal after undo")
    step(f"checking {t.id} was restored")
    first = {}  # один ключ можна змінити двічі (вимкнути, потім «вручну») — початковий стан у першому записі
    for rec in undo:
        first.setdefault(record_key(rec), rec)
    tasks = task_states(rec["n"] for rec in first.values() if rec["t"] == "task")
    for rec in first.values():
        checked, ok, what = restored(rec, tasks)
        if not checked:
            r["unchecked"] += 1
        elif not ok:
            r["problems"].append("NOT RESTORED: " + what)
    scheme2 = E.active_scheme()
    for tg in targets:
        before, now = pre[key_of(tg)], read_target(tg, scheme2)
        if tg[0] == "pw" and scheme2 != scheme0:
            continue  # інша схема — порівняння нижче (scheme)
        if before != now:
            r["problems"].append(f"NOT RESTORED: {key_of(tg)}: {before!r} -> {now!r}")
    if E.probe(t) != probe0 and any(op[0] == "reg" and not callable(op[3]) for op in t.ops):
        r["problems"].append(f"probe() {probe0} before, {not probe0} after undo")
    r["drift"] = drift(inv0, invariants())
    if "scheme" in r["drift"]:
        r["problems"].append(f"active power scheme {scheme0} -> {scheme2}")
    if r["problems"]:
        r["status"] = "allowed" if t.id in ALLOW_FAIL else "fail"
        if t.id in ALLOW_FAIL:
            r["why"] = ALLOW_FAIL[t.id]
    return r


# ───────────────────────── пакет ─────────────────────────
def batch(items, hw, how: str) -> dict:
    """Застосувати пакетом (як кнопка «Застосувати»), відкотити через Rescue-файл або журнал програми."""
    r = {"how": how, "n": len(items), "problems": []}
    scheme0 = E.active_scheme()
    pre = {}
    for t in items:
        for tg in static_targets(t):
            pre.setdefault(key_of(tg), (tg, read_target(tg, scheme0)))
    inv0 = invariants()
    log = []
    t0 = time.time()
    step(f"batch via {how}: applying {len(items)} tweaks")
    res = E.apply_tweaks(items, log.append, header=False, hw=hw)
    r["apply"] = res
    r["apply_s"] = round(time.time() - t0, 1)
    first = {}  # ключ -> найперший запис (його old — справжній початковий стан)
    for tid in list(E.JOURNAL.data["applied"]):
        for rec in E.JOURNAL.get(tid)["undo"]:
            first.setdefault(record_key(rec), json.loads(json.dumps(rec)))
    r["records"] = len(first)
    r["journal"] = E.JOURNAL.count()
    t0 = time.time()
    if how == "rescue":
        step("batch via rescue: running OptimaX-Rescue.cmd /all")
        path = RS.write_rescue()
        r["script"] = path
        # Вивід — у файл, а не в канал: наприкінці скрипт перезапускає Провідник (start explorer.exe), і той успадкував
        # би канал і тримав його відкритим вічно — subprocess.run чекав би на нього навіть після тайм-ауту.
        out_path = os.path.join(tempfile.gettempdir(), "oxrt-rescue.log")
        with open(out_path, "wb") as out:
            p = subprocess.Popen(["cmd", "/c", path, "/all"], stdout=out, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL)
            try:
                rc = p.wait(1800)
            except subprocess.TimeoutExpired:
                E.kill_tree(p)
                rc = "timeout"
        r["rescue_rc"] = rc
        with open(out_path, "rb") as f:
            r["rescue_out"] = f.read().decode("utf-8", "replace")[-3000:]
        failed_txt = os.path.join(RS.rescue_dir(), "failed.txt")
        if os.path.exists(failed_txt):
            with open(failed_txt, encoding="utf-8", errors="replace") as f:
                r["rescue_failed"] = [ln.strip() for ln in f if ln.strip()]
            os.remove(failed_txt)
        gone = RS.sync()
        r["synced"] = len(gone)
        if rc != 0:
            r["problems"].append(f"OptimaX-Rescue.cmd /all: {rc} failed steps")
            r["problems"] += [f"rescue step failed: {x}" for x in r.get("rescue_failed", [])[:10]]
        if E.JOURNAL.count():
            r["problems"].append(f"{E.JOURNAL.count()} entries were not marked done by the rescue script")
    else:
        step("batch via journal: rolling back")
        log2 = []
        E.undo_ids(E.JOURNAL.newest_first(), log2.append)
        r["problems"] += [f"undo log: {x}" for x in bad_log(log2)[:20]]
    r["undo_s"] = round(time.time() - t0, 1)
    step(f"batch via {how}: checking everything was restored")
    if E.JOURNAL.count():  # прибрати за собою, щоб наступний етап почався з чистої системи
        E.undo_ids(E.JOURNAL.newest_first(), lambda *_: None)
    unchecked = 0
    tasks = task_states(rec["n"] for rec in first.values() if rec["t"] == "task")
    schemes = {g for g, _ in E.list_schemes()}
    for k, rec in first.items():
        checked, ok, what = restored(rec, tasks, schemes)
        unchecked += not checked
        if checked and not ok:
            r["problems"].append("NOT RESTORED: " + what)
    scheme2 = E.active_scheme()
    for k, (tg, before) in pre.items():
        if tg[0] == "pw" and scheme2 != scheme0:
            continue
        now = read_target(tg, scheme2)
        if before != now:
            r["problems"].append(f"NOT RESTORED: {k}: {before!r} -> {now!r}")
    r["unchecked"] = unchecked
    r["drift"] = drift(inv0, invariants())
    if "scheme" in r["drift"]:
        r["problems"].append(f"active power scheme {scheme0} -> {scheme2}")
    return r


# ───────────────────────── головне ─────────────────────────
def eligible(hw):
    only = {x.strip() for x in ARGS.only.split(",") if x.strip()}
    out, skipped = [], []
    build = E.win_build()
    for t in E.TWEAKS:
        if only and t.id not in only:
            continue
        why = (SKIP.get(t.id) or ("custom value" if t.custom else "") or ("not reversible" if not t.reversible else "")
               or ("takes too long" if t.long else "") or ("Windows 11 only" if t.win11 and build < 22000 else "")
               or ("Windows 10 only" if t.win10 and build >= 22000 else ""))
        if not why:
            st, reason = E.compat(t, hw)
            if st in ("na", "block"):
                why = f"{st}: {reason}"
        if why:
            skipped.append({"id": t.id, "why": why})
        else:
            out.append(t)
    return out, skipped


def write_report(rep: dict) -> None:
    os.makedirs(ARGS.out, exist_ok=True)
    with open(os.path.join(ARGS.out, "roundtrip.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=str)
    s = rep["summary"]
    md = [f"### Tweak round-trip on {rep['os']} (build {rep['build']}): "
          f"{'passed' if rep['ok'] else 'FAILED'}", "",
          f"{s['pass']} passed · {s['fail']} failed · {s['allowed']} allowed failures · {s['skip']} not applicable · "
          f"{s['excluded']} excluded · {rep['seconds']:.0f} s", ""]
    md += [f"- **{p}**" for p in rep.get("problems", [])] + ([""] if rep.get("problems") else [])
    bad = [r for r in rep["tweaks"] if r["status"] in ("fail", "allowed")]
    if bad:
        md += ["| tweak | result | problems |", "|---|---|---|"]
        for r in bad:
            probs = "<br>".join(p.replace("|", "/")[:220] for p in r["problems"][:6])
            md.append(f"| `{r['id']}` {r['title']} | {'**FAIL**' if r['status'] == 'fail' else 'allowed: ' + r.get('why', '')} "
                      f"| {probs} |")
        md.append("")
    for b in rep.get("batches", []):
        md.append(f"**Batch via {b['how']}**: {b['n']} tweaks, {b['records']} rollback records, apply {b['apply_s']} s, "
                  f"undo {b['undo_s']} s — {'ok' if not b['problems'] else 'FAILED'}")
        md += [f"- {p}" for p in b["problems"][:30]]
        md.append("")
    drifted = sorted({d for r in rep["tweaks"] for d in r.get("drift", [])})
    if drifted:
        md += ["<details><summary>Side effects seen (not counted as failures)</summary>", ""]
        md += [f"- {d}" for d in drifted[:60]] + ["", "</details>"]
    with open(os.path.join(ARGS.out, "roundtrip.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


def build_report(ok=None) -> dict:
    results, batches, problems = STATE["results"], STATE["batches"], STATE["problems"]
    summary = {k: sum(r["status"] == k for r in results) for k in ("pass", "fail", "allowed", "skip")}
    summary["excluded"] = len(STATE["skipped"])
    if ok is None:
        ok = summary["fail"] == 0 and all(not b["problems"] for b in batches) and not problems
    hw = STATE["hw"]
    return {"ok": ok, "os": hw.get("os"), "build": E.win_build(), "cpu": hw.get("cpu"), "summary": summary,
            "seconds": time.time() - STATE["t0"], "problems": problems, "tweaks": results, "batches": batches,
            "excluded": STATE["skipped"]}


def main() -> int:
    t_start = STATE["t0"] = time.time()
    threading.Thread(target=_watchdog, daemon=True).start()
    step("detecting hardware")
    hw = STATE["hw"] = H.detect_hw()
    items, skipped = eligible(hw)
    STATE["skipped"] = skipped
    print(f"{hw.get('os')} build {E.win_build()} · {len(items)} tweaks to check, {len(skipped)} excluded", flush=True)
    budget = ARGS.budget_min * 60
    over = lambda: budget and time.time() - t_start > budget  # noqa: E731
    results, problems = STATE["results"], STATE["problems"]
    for i, t in enumerate(items, 1):
        if over():
            problems.append(f"time budget of {ARGS.budget_min:.0f} min ran out: {len(items) - i + 1} of {len(items)} "
                            f"tweaks not checked, starting with {t.id}")
            break
        r = roundtrip(t, hw)
        results.append(r)
        print(f"[{i}/{len(items)}] {r['status']:7} {t.id} · {time.time() - t_start:.0f} s" +
              (f" — {r['problems'][0][:150]}" if r["problems"] else ""), flush=True)
        if r.get("apply_s", 0) > 120 and os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning title=slow tweak {t.id}::applying took {r['apply_s']:.0f} s", flush=True)
    batches = STATE["batches"]
    if not ARGS.no_batch:
        ok_ids = {r["id"] for r in results if r["status"] == "pass"}
        plan = [t for t in items if t.id in ok_ids]
        for how in (() if ARGS.no_rescue else ("rescue",)) + ("journal",):
            if over():
                problems.append(f"time budget ran out before the batch via {how}")
                continue
            b = batch(plan, hw, how)
            batches.append(b)
            print(f"batch via {how}: {len(b['problems'])} problems · {time.time() - t_start:.0f} s", flush=True)
    step("writing the report")
    rep = build_report()
    ok = rep["ok"]
    write_report(rep)
    print(open(os.path.join(ARGS.out, "roundtrip.md"), encoding="utf-8").read())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
