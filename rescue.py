"""
OptimaX — аварійний відкат.

• Пакет змін: після кожного застосування OptimaX запам'ятовує, що саме й коли змінено.
• Перевірка після перезавантаження: журнал подій Windows — синій екран (BugCheck 1001), аварійне
  перезавантаження чи зникнення живлення (Kernel-Power 41), неочікуване вимкнення (EventLog 6008),
  скидання відеодрайвера (Display 4101). Якщо таке сталося після змін — OptimaX пропонує їх відкотити.
  Щоб перевірка відбулася навіть без автозапуску, на 3 дні створюється задача «OptimaX Safety».
• OptimaX-Rescue.cmd — звичайний командний файл, який генерується з журналу змін після кожного запису.
  Він повертає зміни без Python і без запуску програми, зокрема в безпечному режимі Windows.
  Що він відкотив, OptimaX дізнається з файлу done.txt і прибирає ці записи з журналу.
"""
from __future__ import annotations

import base64
import os
import subprocess
import time

import engine as E
import features as F
from i18n import tr

RESCUE_NAME = "OptimaX-Rescue.cmd"
SAFETY_TASK = "OptimaX Safety"
WATCH_DAYS = 3
BATCH_GAP = 120  # записи журналу, зроблені з проміжком до 2 хв, — один пакет
EVENT_IDS = {1001: "bsod", 41: "power", 6008: "shutdown", 4101: "gpu"}


def rescue_dir() -> str:
    if E.IS_WIN and not E.DRY_RUN:
        return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "OptimaX", "rescue")
    return os.path.join(E.DATA_DIR, "rescue")


def rescue_path() -> str:
    return os.path.join(rescue_dir(), RESCUE_NAME)


# ───────────────────────── пакети змін ─────────────────────────
def batches(journal: E.Journal = None) -> list:
    """Записи журналу, згруповані за часом: [[новіші id…], [старіші…]] — від найновішого пакета."""
    j = journal or E.JOURNAL
    out, cur, last = [], [], None
    for tid in j.newest_first():  # той самий порядок, що й у відкаті програми
        e = j.get(tid) or {}
        ts = e.get("ts", 0)
        if last is not None and last - ts > BATCH_GAP:
            out.append(cur)
            cur = []
        cur.append(tid)
        last = ts
    if cur:
        out.append(cur)
    return out


def record_batch(before: set, kind: str = "apply", log=lambda *_: None) -> list:
    """Після застосування: запам'ятати новий пакет і почати стежити за стабільністю."""
    new = [i for i in E.JOURNAL.newest_first() if i not in before]
    if not new:
        return []
    import guard as G
    F.CFG["safety"] = dict(ts=int(time.time()), ids=new, kind=kind, boot=G.boot_time(), checked=False)
    if E.IS_WIN and not E.DRY_RUN and not F.autostart_enabled():
        cmd = subprocess.list2cmdline(F._self_command() + ["--check-crash"])
        E.run(["schtasks", "/Create", "/TN", SAFETY_TASK, "/TR", cmd, "/SC", "ONLOGON", "/RL", "HIGHEST", "/IT",
               "/DELAY", "0000:30", "/F"], 20, log)
    write_rescue()
    return new


def _stop_watch() -> None:
    st = F.CFG["safety"] or {}
    if st:
        st["checked"] = True
        F.CFG["safety"] = st
    if E.IS_WIN and not E.DRY_RUN:
        E.run(["schtasks", "/Delete", "/TN", SAFETY_TASK, "/F"], 20)


# ───────────────────────── журнал подій Windows ─────────────────────────
EVENTS_PS = r"""
$t=(Get-Date).AddSeconds(-{age})
$ev=Get-WinEvent -FilterHashtable @{{LogName='System'; Id=41,6008,1001,4101; StartTime=$t}} -MaxEvents 40 -ErrorAction SilentlyContinue
@($ev | ForEach-Object {{ @{{id=$_.Id; prov=$_.ProviderName; ts=([DateTimeOffset]$_.TimeCreated).ToUnixTimeSeconds()}} }}) | ConvertTo-Json -Compress
"""


def crash_events(since: float) -> list:
    """Події збоїв після моменту since: [{id, kind, ts}] від найранішої."""
    if not E.IS_WIN:
        if F.CFG["demo_crash"]:
            return [dict(id=41, kind="power", ts=int(since) + 3600), dict(id=1001, kind="bsod", ts=int(since) + 3590)]
        return []
    age = max(60, int(time.time() - since))
    data = E.ps_json(EVENTS_PS.format(age=age), 40)
    out = []
    for d in E.as_list(data):
        if not isinstance(d, dict):
            continue
        eid, prov = int(d.get("id") or 0), str(d.get("prov") or "")
        if eid == 1001 and "SystemErrorReporting" not in prov and "BugCheck" not in prov:
            continue
        if eid == 41 and "Kernel-Power" not in prov or eid == 4101 and "Display" not in prov:
            continue
        if eid in EVENT_IDS and int(d.get("ts") or 0) >= since:
            out.append(dict(id=eid, kind=EVENT_IDS[eid], ts=int(d["ts"])))
    return sorted(out, key=lambda e: e["ts"])


def check(force: bool = False):
    """-> {ts, ids, events, kinds} якщо після останнього пакета змін був збій, інакше None."""
    st = F.CFG["safety"] or {}
    if not st or (st.get("checked") and not force):
        return None
    ids = [i for i in st.get("ids", []) if E.JOURNAL.has(i)]
    if not ids:
        _stop_watch()
        return None
    events = crash_events(st["ts"] + 30)
    if not events:
        if time.time() - st["ts"] > WATCH_DAYS * 86400:
            _stop_watch()
        return None
    kinds = sorted({e["kind"] for e in events}, key=list(EVENT_IDS.values()).index)
    return dict(ts=st["ts"], ids=ids, events=events, kinds=kinds)


def dismiss() -> None:
    _stop_watch()


# ───────────────────────── аварійне завершення самої OptimaX ─────────────────────────
def recover_on_start(log=lambda *_: None) -> dict:
    """Під час запуску: повернути оптимізацію, застосування якої обірвалося, знайти перерваний пакет
    і зробити знімок початкових налаштувань, якщо його ще немає (оновлення з 6.3)."""
    res = E.recover_interrupted(log)
    if res.get("op") and F.CFG["smart"]:  # розумна оптимізація продовжить сама й поверне узгоджений стан
        E.JOURNAL.end_op()
        res.update(op=None, ids=[])
    try:
        import baseline as BL
        BL.ensure(log)  # без журналу («lost») знімок не робиться: поточні значення вже не «початкові»
    except Exception as e:  # знімок — запасний механізм; без нього програма працює як раніше
        log(f"  ⚠ baseline: {type(e).__name__}: {e}")
    if res.get("tweak"):
        write_rescue()
    res["journal"] = E.JOURNAL.problem
    return res


def revert(log, progress=None) -> dict:
    st = F.CFG["safety"] or {}
    ids = [i for i in st.get("ids", []) if E.JOURNAL.has(i)]
    res = E.undo_ids(ids, log, progress) if ids else {"undone": 0}
    _stop_watch()
    return res


def describe(kinds) -> str:
    return ", ".join(tr(f"rs.kind.{k}") for k in kinds)


# ───────────────────────── OptimaX-Rescue.cmd ─────────────────────────
def _q(s: str) -> str:
    """Рядок усередині лапок для reg/sc у .cmd: % подвоюємо, лапки екрануємо."""
    return str(s).replace("%", "%%").replace('"', '\\"')


def _echo(s: str) -> str:
    for a, b in (("^", "^^"), ("&", "^&"), ("|", "^|"), ("<", "^<"), (">", "^>"), ("%", "%%")):
        s = str(s).replace(a, b)
    return s.replace("\r", " ").replace("\n", " ")


def _echo_block(s: str) -> str:
    """Підпис кроку для echo всередині ( … ). Лапки прибираємо (у лапках ^ не екранує, а дужки й & тоді треба
    було б лишати як є), а все інше екрануємо — разом із дужками, інакше «Program Files (x86)» закриє блок.
    % не подвоюємо: команда вже записана з %% там, де відсоток буквальний."""
    s = str(s).replace('"', "").replace("\r", " ").replace("\n", " ")
    for a, b in (("^", "^^"), ("&", "^&"), ("|", "^|"), ("<", "^<"), (">", "^>"), ("(", "^("), (")", "^)")):
        s = s.replace(a, b)
    return s


def _reg_lines(rec: dict) -> list:
    path, name, old = rec["p"], rec["n"], rec.get("old")
    vflag = "/ve" if name == "" else f'/v "{_q(name)}"'
    if old is None:
        return [f'reg delete "{_q(path)}" {vflag} /f']
    rtype, val = old[0], E._dec(old[1])
    if rtype in (1, 2):
        s = _q(val)
        if s.endswith("\\"):
            s += "\\"  # інакше \" перед закриваючою лапкою reg прочитає як лапку
        data = f'/t {"REG_SZ" if rtype == 1 else "REG_EXPAND_SZ"} /d "{s}"'
    elif rtype == 4:
        data = f"/t REG_DWORD /d {int(val) & 0xFFFFFFFF}"
    elif rtype == 11:
        data = f"/t REG_QWORD /d {int(val) & 0xFFFFFFFFFFFFFFFF}"
    elif rtype == 3:
        hx = bytes(val).hex()
        data = "/t REG_BINARY" + (f" /d {hx}" if hx else "")
    elif rtype == 7:
        items = [_q(x) for x in (val or [])]
        data = '/t REG_MULTI_SZ /d "' + "\\0".join(items) + '"' if items else "/t REG_MULTI_SZ"
    else:
        return [f"rem {_echo(path)}\\{_echo(name)}: type {rtype} is not supported"]
    return [f'reg add "{_q(path)}" {vflag} {data} /f']


# Видалення, яке «не знайшло що видаляти», — не збій: значення вже таке, як до OptimaX
GONE_OK = ("reg delete ", "bcdedit /deletevalue ")


def undo_lines(rec: dict) -> list:
    """Команди .cmd для одного запису відкату з журналу."""
    t = rec.get("t")
    if t == "reg":
        return _reg_lines(rec)
    if t == "svc":
        return [f'sc config "{_q(rec["n"])}" start= {rec["old"]}']
    if t == "task":
        return [f'schtasks /Change /Enable /TN "{_q(rec["n"])}"']
    if t == "cmd":
        return [str(rec["c"]).replace("%", "%%")]
    if t == "ps":
        code = str(rec.get("c") or "")
        if not code.strip() or code.lstrip().startswith("#"):
            return []
        b64 = base64.b64encode((E.PS_PREFIX + code).encode("utf-16-le")).decode("ascii")
        return [f"powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {b64}"]
    if t == "pw":
        if rec.get("old") is None:
            return []
        verb = "-setdcvalueindex" if rec.get("m") == "dc" else "-setacvalueindex"
        return [f"powercfg {verb} {rec['g']} {rec['s']} {rec['st']} {rec['old']}", f"powercfg -setactive {rec['g']}"]
    return []  # live: оновлення Провідника — в кінці; решта діє після перезавантаження


def build_script(journal: E.Journal = None) -> str:
    j = journal or E.JOURNAL
    groups = batches(j)
    newest = j.newest_first()
    last = groups[0] if groups else []
    when = time.strftime("%d.%m.%Y %H:%M", time.localtime(j.get(last[0]).get("ts", 0))) if last else "—"
    L = ["@echo off", "setlocal", "chcp 65001 >nul",
         f"rem {E.APP_TITLE} {E.VERSION}: emergency rollback, generated {time.strftime('%Y-%m-%d %H:%M')}.",
         "rem Reverts changes from the OptimaX journal without starting the program (also in Safe Mode).",
         "rem Without a menu: OptimaX-Rescue.cmd /last (last batch) or /all (everything); exit code = failed steps.",
         "net session >nul 2>&1", "if not errorlevel 1 goto admin",
         f"echo {_echo(tr('rs.cmd_admin'))}",
         'if "%~1"=="" goto elevate',
         "powershell -NoProfile -Command \"Start-Process -FilePath '%~f0' -ArgumentList '%~1' -Verb RunAs\" >nul 2>&1",
         "exit /b 1", ":elevate",
         "powershell -NoProfile -Command \"Start-Process -FilePath '%~f0' -Verb RunAs\" >nul 2>&1",
         "exit /b 1", ":admin", "set FAIL=0", "set QUIET=",
         'if /i "%~1"=="/all" set QUIET=1', 'if /i "%~1"=="/last" set QUIET=1',
         "if not defined QUIET cls", "echo.",
         f"echo   {_echo(E.APP_TITLE + ' - ' + tr('rs.cmd_title'))}", "echo.",
         f"echo   {_echo(tr('rs.cmd_state', n=len(newest), last=len(last), when=when))}", "echo."]
    if not newest:
        L += [f"echo   {_echo(tr('rs.cmd_nothing'))}", "if not defined QUIET pause", "exit /b 0"]
        return "\r\n".join(L) + "\r\n"
    L += [f"echo   [1] {_echo(tr('rs.cmd_last', n=len(last)))}",
          f"echo   [2] {_echo(tr('rs.cmd_all', n=len(newest)))}",
          f"echo   [3] {_echo(tr('rs.cmd_exit'))}", "echo.",
          'if /i "%~1"=="/all" goto all', 'if /i "%~1"=="/last" goto last',
          'choice /c 123 /n /m "> "', "if errorlevel 3 exit /b 0", "if errorlevel 2 goto all", "goto last"]
    index = {tid: n for n, tid in enumerate(newest)}
    explorer = any(r.get("t") == "live" and r.get("k") == "explorer"
                   for tid in newest for r in (j.get(tid) or {}).get("undo", []))
    for label_, ids in (("last", last), ("all", newest)):
        L += ["", f":{label_}", "echo."]
        L += [f"call :x{index[tid]}" for tid in ids]
        L += ["goto finish"]
    L += ["", ":finish"]
    if explorer:
        L += ["taskkill /f /im explorer.exe >nul 2>&1", 'start "" explorer.exe']
    L += ["echo.", f"echo   {_echo(tr('rs.cmd_done'))}",
          f"if not %FAIL%==0 echo   {_echo(tr('rs.cmd_fail'))}",
          f"echo   {_echo(tr('rs.cmd_reboot'))}", "echo.", "if not defined QUIET pause", "exit /b %FAIL%"]
    for tid in newest:
        e = j.get(tid) or {}
        L += ["", f":x{index[tid]}", f"echo   - {_echo(E.entry_title(tid))}"]
        for rec in reversed(e.get("undo", [])):
            for cmd in undo_lines(rec):
                if cmd.startswith("rem "):
                    L.append(cmd)
                elif cmd.lower().startswith(GONE_OK):  # уже видалено (наприклад, іншим твіком) — мети досягнуто
                    L.append(f"{cmd} >nul 2>&1")
                else:  # невдалий крок — у failed.txt поруч зі скриптом: видно, що саме не повернулося
                    L.append(f'{cmd} >nul 2>&1 || (set /a FAIL+=1 & >>"%~dp0failed.txt" echo '
                             f'{_echo_block(tid)}: {_echo_block(cmd[:150])})')
        L += [f'>>"%~dp0done.txt" echo {tid}', "exit /b 0"]
    return "\r\n".join(L) + "\r\n"


def write_rescue(journal: E.Journal = None) -> str:
    """Перегенерувати файл. -> шлях (або '' при помилці запису)."""
    try:
        os.makedirs(rescue_dir(), exist_ok=True)
        path = rescue_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(build_script(journal))
        os.replace(tmp, path)
        return path
    except OSError:
        return ""


def sync(journal: E.Journal = None) -> list:
    """Що вже повернув OptimaX-Rescue.cmd — прибрати з журналу (без повторного відкату)."""
    j = journal or E.JOURNAL
    done = os.path.join(rescue_dir(), "done.txt")
    if not os.path.exists(done):
        return []
    try:
        with open(done, encoding="utf-8", errors="replace") as f:
            ids = [ln.strip() for ln in f if ln.strip()]
        os.remove(done)
    except OSError:
        return []
    gone = [i for i in dict.fromkeys(ids) if j.has(i)]
    for tid in gone:
        j.pop(tid)
    write_rescue(j)
    return gone


def state() -> dict:
    p = rescue_path()
    try:
        mtime = int(os.path.getmtime(p))
    except OSError:
        mtime = 0
    return dict(path=p, updated=mtime, n=E.JOURNAL.count(), last=len((batches() or [[]])[0]))


def _on_journal_change(journal) -> None:
    write_rescue(journal)


if _on_journal_change not in E.JOURNAL.listeners:
    E.JOURNAL.listeners.append(_on_journal_change)
