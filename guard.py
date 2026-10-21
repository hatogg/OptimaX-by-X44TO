"""
OptimaX — сторож налаштувань (помічає, що оновлення Windows повернуло змінене), пробний режим
(зміни відкочуються після перезавантаження, якщо їх не підтвердити) та обслуговування за розкладом.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import time

import engine as E
import features as F
from i18n import tr

SKIP_GROUPS = {"maint", "metro", "game", "msi", "visual"}
TRIAL_TASK = "OptimaX Trial"
MAINT_TASK = "OptimaX Maintenance"
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


# ───────────────────────── сторож ─────────────────────────
def os_fingerprint() -> str:
    """Збірка Windows + номер оновлення (UBR): змінюється після кожного накопичувального оновлення."""
    if not E.IS_WIN:
        return f"{E.win_build()}.demo"
    ubr = E.reg_get(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion", "UBR")
    return f"{E.win_build()}.{ubr[1] if ubr else 0}"


def _svc_ok(t: E.Tweak) -> bool:
    for op in t.ops:
        if op[0] == "svc":
            cur = E.svc_get_start(op[1])
            if cur is not None and cur != op[2] and not (op[2] == "auto" and cur == "delayed-auto"):
                return False
    return True


def _demo_reverted() -> list:
    """Поза Windows імітуємо, що оновлення повернуло рекламу й Copilot, щоб було видно, як працює сторож."""
    fixed = set(F.CFG["demo_guard_fixed"] or [])
    return [i for i in ("ads_tips", "ai_copilot", "disable_telemetry") if E.JOURNAL.has(i) and i not in fixed][:2]


def check_reverted() -> list:
    """Застосовані через OptimaX твіки, які зараз уже не діють."""
    if not E.IS_WIN:
        return _demo_reverted()
    out = []
    for tid in E.JOURNAL.newest_first():
        t = E.BY_ID.get(tid)
        if not t or t.group in SKIP_GROUPS or not t.reversible or t.custom:
            continue
        regs = [op for op in t.ops if op[0] == "reg" and not callable(op[3])]
        if regs and not E.probe(t):
            out.append(tid)
        elif not _svc_ok(t):
            out.append(tid)
    return out


def run_check(log=lambda *_: None) -> dict:
    ids = check_reverted()
    F.CFG["guard_state"] = dict(ts=int(time.time()), os=os_fingerprint(), reverted=ids)
    if ids:
        log(tr("guard.found", n=len(ids)))
        for i in ids:
            log(f"  · {E.entry_title(i)}")
    else:
        log(tr("guard.clean"))
    return {"ok": True, "reverted": ids}


def reapply(ids, log, progress=None) -> dict:
    """Застосовує знову. Журнал зберігає перший знімок, тож відкат і далі повертає ваші початкові значення."""
    items = [E.BY_ID[i] for i in ids if i in E.BY_ID]
    res = E.apply_tweaks(items, log, progress, header=False)
    if not E.IS_WIN:
        F.CFG["demo_guard_fixed"] = sorted(set(F.CFG["demo_guard_fixed"] or []) | set(ids))
    run_check(lambda *_: None)
    return res


def due(hours: float = 6.0) -> bool:
    """Чи час перевіряти: минуло N годин або змінилася версія Windows."""
    st = F.CFG["guard_state"] or {}
    return st.get("os") != os_fingerprint() or time.time() - st.get("ts", 0) > hours * 3600


# ───────────────────────── пробний режим ─────────────────────────
def boot_time() -> float:
    if not E.IS_WIN:
        return float(F.CFG["demo_boot"] or 1_000_000)
    k32 = ctypes.windll.kernel32
    k32.GetTickCount64.restype = ctypes.c_ulonglong
    return time.time() - k32.GetTickCount64() / 1000


def _self_cmd(extra: str) -> str:
    return subprocess.list2cmdline(F._self_command() + [extra])


def start_trial(ids: list, log) -> dict:
    """Запам'ятовує щойно застосовані зміни; після перезавантаження OptimaX сам запитає, залишати їх чи ні."""
    ids = [i for i in ids if E.JOURNAL.has(i)]
    if not ids:
        return {"ok": False}
    F.CFG["trial"] = dict(ids=ids, ts=int(time.time()), boot=boot_time())
    if E.IS_WIN and not E.DRY_RUN and not F.autostart_enabled():  # з автозапуском OptimaX і так стартує сам
        E.run(["schtasks", "/Create", "/TN", TRIAL_TASK, "/TR", _self_cmd("--trial"), "/SC", "ONLOGON", "/RL",
               "HIGHEST", "/IT", "/DELAY", "0000:15", "/F"], 20, log)
    log(tr("trial.started", n=len(ids)))
    return {"ok": True, "n": len(ids)}


def trial_state():
    """-> None | ('active', trial) — ще не перезавантажувались | ('decide', trial) — пора вирішувати."""
    t = F.CFG["trial"]
    if not t:
        return None
    rebooted = boot_time() > t.get("boot", 0) + 120
    return ("decide" if rebooted else "active"), t


def end_trial(keep: bool, log, progress=None) -> dict:
    t = F.CFG["trial"] or {}
    res = {"ok": True, "kept": keep}
    if not keep and t.get("ids"):
        res.update(E.undo_ids(t["ids"], log, progress))
    F.CFG["trial"] = None
    if E.IS_WIN and not E.DRY_RUN:
        E.run(["schtasks", "/Delete", "/TN", TRIAL_TASK, "/F"], 20)
    log(tr("trial.kept") if keep else tr("trial.reverted"))
    return res


# ───────────────────────── обслуговування за розкладом ─────────────────────────
MAINT_DIRS = [r"%TEMP%", r"%SystemRoot%\Temp", r"%LOCALAPPDATA%\CrashDumps",
              r"%ProgramData%\Microsoft\Windows\WER\ReportArchive", r"%ProgramData%\Microsoft\Windows\WER\ReportQueue"]


def run_maintenance(log) -> dict:
    """Тихе обслуговування: тимчасові файли, звіти про збої, перевірка сторожем. Без перезапуску Провідника."""
    log(tr("maint.start"))
    freed = 0
    if not E.DRY_RUN:
        for d in MAINT_DIRS:
            freed += E.clean_dir(os.path.expandvars(d))
    else:
        log("  [dry-run] TEMP, Windows\\Temp, CrashDumps, WER")
    log(tr("e.freed_mb", mb=f"{freed / 2**20:.0f}"))
    g = run_check(log)
    info = dict(ts=int(time.time()), freed_mb=round(freed / 2**20), reverted=len(g["reverted"]))
    F.CFG["maint_last"] = info
    try:
        os.makedirs(E.DATA_DIR, exist_ok=True)
        with open(os.path.join(E.DATA_DIR, "maintenance.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M") + f"  freed={info['freed_mb']}MB reverted={info['reverted']}\n")
    except OSError:
        pass
    log(tr("maint.done"))
    return info


def set_schedule(on: bool, day: int, hour: int, log=lambda *_: None) -> bool:
    F.CFG["schedule"] = dict(enabled=on, day=day, hour=hour)
    if not E.IS_WIN or E.DRY_RUN:
        return True
    if on:
        rc, _ = E.run(["schtasks", "/Create", "/TN", MAINT_TASK, "/TR", _self_cmd("--maintenance"), "/SC", "WEEKLY",
                       "/D", DAYS[day % 7], "/ST", f"{hour % 24:02d}:00", "/RL", "HIGHEST", "/IT", "/F"], 20, log)
    else:
        rc, _ = E.run(["schtasks", "/Delete", "/TN", MAINT_TASK, "/F"], 20, log)
    return rc == 0
