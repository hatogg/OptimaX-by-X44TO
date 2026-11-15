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
import secfs as SF
import features as F
from i18n import tr

RESCUE_NAME = "OptimaX-Rescue.cmd"
SAFETY_TASK = "OptimaX Safety"
WATCH_DAYS = 3
BATCH_GAP = 120  # записи журналу, зроблені з проміжком до 2 хв, — один пакет
EVENT_IDS = {1001: "bsod", 41: "power", 6008: "shutdown", 4101: "gpu"}


def rescue_dir() -> str:
    """%ProgramData%\\OptimaX\\rescue, захищена від запису звичайними програмами: цей файл запускають з правами
    адміністратора, а done.txt поруч прибирає записи з журналу відкату."""
    return E.admin_dir("rescue")


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
    if E.IS_WIN and not E.DRY_RUN and not F.autostart_enabled() and F.elevated_tasks_ok():
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
    """Рядок усередині лапок для reg/sc у .cmd: % подвоюємо, лапки екрануємо (лише для аргументів програми — cmd.exe
    \\" не розуміє, тож текст із лапками сюди не потрапляє: див. _cmd_safe)."""
    return str(s).replace("%", "%%").replace('"', '\\"')


def _cmd_safe(s) -> bool:
    """Текст можна покласти в лапки рядка .cmd: лише друковані ASCII без лапок. У лапках cmd.exe не розбирає
    & | < > ^ ( ), % подвоює _q, а затримане розгортання (!) вимкнене в setlocal. Лапка ж закрила б лапки,
    а CR/LF почали б новий рядок — і решта значення виконалася б окремою командою з правами адміністратора."""
    return isinstance(s, str) and all(" " <= c <= "~" for c in s) and '"' not in s


def _qa(s: str) -> str:
    """_q для аргументу в лапках: \\ перед закриваючою лапкою програма прочитала б як лапку — подвоюємо."""
    s = _q(s)
    return s + "\\" if s.endswith("\\") else s


def _ctl(s: str) -> str:
    """Керівні символи -> пробіл: CR/LF (і Ctrl-Z, який cmd.exe теж читає як кінець рядка) почали б новий рядок."""
    return "".join(" " if c < " " or c == "\x7f" else c for c in str(s))


def _echo(s: str) -> str:
    for a, b in (("^", "^^"), ("&", "^&"), ("|", "^|"), ("<", "^<"), (">", "^>"), ("%", "%%")):
        s = str(s).replace(a, b)
    return _ctl(s)


def _echo_block(s: str) -> str:
    """Підпис кроку для echo всередині ( … ). Лапки прибираємо (у лапках ^ не екранує, а дужки й & тоді треба
    було б лишати як є), а все інше екрануємо — разом із дужками, інакше «Program Files (x86)» закриє блок.
    % не подвоюємо: команда вже записана з %% там, де відсоток буквальний."""
    s = _ctl(str(s).replace('"', ""))
    for a, b in (("^", "^^"), ("&", "^&"), ("|", "^|"), ("<", "^<"), (">", "^>"), ("(", "^("), (")", "^)")):
        s = s.replace(a, b)
    return s


def _echo_id(tid: str) -> str:
    """id запису для echo в done.txt / failed.txt так, щоб cmd.exe надрукував його дослівно: msi:PCI\\VEN_10DE&DEV_…
    без екранування & виконав би решту як команду. Те, що echo дослівно не надрукує (лапки — у них ^ не екранує;
    керівні символи, пробіли з країв, «on»/«off», «/?»), пишемо як b64:… — sync() декодує."""
    tid = str(tid)
    if (tid and tid == tid.strip() and '"' not in tid and tid[0] != "/" and not tid.startswith("b64:")
            and tid.lower() not in ("on", "off") and all(c >= " " and c != "\x7f" for c in tid)):
        return _echo(tid).replace("(", "^(").replace(")", "^)")
    return "b64:" + base64.b64encode(tid.encode("utf-8", "surrogatepass")).decode("ascii")


def _unecho_id(s: str) -> str:
    """Зворотне до _echo_id: що записав echo (або сам рядок скрипта, якщо його прочитали без cmd.exe) -> id."""
    if s.startswith("b64:"):
        try:
            return base64.b64decode(s[4:], validate=True).decode("utf-8", "surrogatepass")
        except (ValueError, UnicodeDecodeError):
            return s
    out, i = [], 0
    while i < len(s):
        if s[i] == "^" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 2
        elif s.startswith("%%", i):
            out.append("%")
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


_REG_HIVE_NET = {"HKLM": "LocalMachine", "HKCU": "CurrentUser", "HKCR": "ClassesRoot", "HKU": "Users"}
_REG_KIND_NET = {1: "String", 2: "ExpandString", 7: "MultiString"}  # рядкові типи: у reg add — лише _reg_exe_ok
_REG_NUM_NET = {3: "Binary", 4: "DWord", 11: "QWord"}  # для шляху чи імені, яких не можна лишити в лапках .cmd


def _ps_text(s) -> str:
    """Рядок для PowerShell без жодного символу самого рядка в коді: base64 (UTF-8 — коротше, а рядок .cmd
    обмежений 8191 символом) і декодування на місці. Так значення не закриє лапки ні в cmd.exe, ні в PowerShell."""
    b64 = base64.b64encode(str(s).encode("utf-8", "surrogatepass")).decode("ascii")
    return f"[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}'))"


def _reg_ps(rec: dict) -> str:
    """Те саме, що engine.reg_set / reg_del_value (64-розрядне подання реєстру), але через .NET у PowerShell: так
    повертаються рядкові значення (і шляхи з лапками чи не-ASCII), які в рядку reg add стали б командою cmd.exe.
    '' — тип, якого не підтримуємо."""
    hive, _, sub = rec["p"].partition("\\")
    old = rec.get("old")
    head = ("$ErrorActionPreference='Stop';try {"
            "$h=[Microsoft.Win32.RegistryKey]::OpenBaseKey("
            f"[Microsoft.Win32.RegistryHive]::{_REG_HIVE_NET[hive.upper()]},[Microsoft.Win32.RegistryView]::Registry64);"
            f"$s={_ps_text(sub)};$n={_ps_text(rec['n'])};")
    if old is None:  # як reg delete: значення вже немає — мети досягнуто
        return head + "$k=$h.OpenSubKey($s,$true);if ($k) { $k.DeleteValue($n,$false);$k.Close() }} catch { exit 1 };exit 0"
    rtype, val = old[0], E._dec(old[1])
    if rtype == 7:
        v = "[string[]]@(" + ",".join(_ps_text(x) for x in (val or [])) + ")"
    elif rtype in (1, 2):
        v = _ps_text(val)
    elif rtype == 4:  # .NET приймає DWORD/QWORD як знакове число з тими самими бітами
        x = int(val) & 0xFFFFFFFF
        v = f"[int]({x - (1 << 32) if x >> 31 else x})"
    elif rtype == 11:
        x = int(val) & 0xFFFFFFFFFFFFFFFF
        v = f"[long]({x - (1 << 64) if x >> 63 else x})"
    elif rtype == 3 and isinstance(val, (bytes, bytearray)):
        v = f"[byte[]][Convert]::FromBase64String('{base64.b64encode(bytes(val)).decode('ascii')}')"
    else:
        return ""
    kind = _REG_KIND_NET.get(rtype) or _REG_NUM_NET[rtype]
    return head + (f"$k=$h.CreateSubKey($s);$k.SetValue($n,{v},[Microsoft.Win32.RegistryValueKind]::{kind});"
                   "$k.Close()} catch { exit 1 };exit 0")


def _reg_exe_ok(rtype, val) -> bool:
    """Рядкове значення можна лишити в reg add: усі символи — _cmd_safe; у REG_MULTI_SZ ще й без \\ і порожніх
    рядків (роздільник \\0 і \\ перед лапкою reg прочитав би інакше). Усе інше — через _reg_ps."""
    if rtype in (1, 2):
        return _cmd_safe(val)
    return isinstance(val, list) and all(_cmd_safe(x) and x and "\\" not in x for x in val)


def _reg_lines(rec: dict) -> list:
    path, name, old = rec["p"], rec["n"], rec.get("old")
    rtype, val = (old[0], E._dec(old[1])) if old is not None else (None, None)
    # Рядкові значення (і шлях чи ім'я, які не можна безпечно лишити в лапках) — лише через PowerShell у base64:
    # жоден символ значення не проходить розбір cmd.exe. Інакше «a" & whoami & rem "» чи «\r\ncalc.exe» у старому
    # значенні стали б окремою командою з правами адміністратора.
    if not (_cmd_safe(path) and _cmd_safe(name)) or (rtype in _REG_KIND_NET and not _reg_exe_ok(rtype, val)):
        code = _reg_ps(rec)
        if code:
            return [_ps_line(code)]
        return [f"rem {_echo(path)}\\{_echo(name)}: type {rtype} is not supported"]
    vflag = "/ve" if name == "" else f'/v "{_qa(name)}"'
    if old is None:
        return [f'reg delete "{_qa(path)}" {vflag} /f']
    if rtype in (1, 2):
        data = f'/t {"REG_SZ" if rtype == 1 else "REG_EXPAND_SZ"} /d "{_qa(val)}"'
    elif rtype == 4:  # int(): лише цифри — метасимволів cmd.exe тут бути не може
        data = f"/t REG_DWORD /d {int(val) & 0xFFFFFFFF}"
    elif rtype == 11:
        data = f"/t REG_QWORD /d {int(val) & 0xFFFFFFFFFFFFFFFF}"
    elif rtype == 3 and isinstance(val, (bytes, bytearray)):  # .hex(): лише 0-9a-f
        hx = bytes(val).hex()
        data = "/t REG_BINARY" + (f" /d {hx}" if hx else "")
    elif rtype == 7:
        items = [_q(x) for x in (val or [])]
        data = '/t REG_MULTI_SZ /d "' + "\\0".join(items) + '"' if items else "/t REG_MULTI_SZ"
    else:
        return [f"rem {_echo(path)}\\{_echo(name)}: type {rtype} is not supported"]
    return [f'reg add "{_qa(path)}" {vflag} {data} /f']


# Видалення, яке «не знайшло що видаляти», — не збій: значення вже таке, як до OptimaX
GONE_OK = ("reg delete ", "bcdedit /deletevalue ")


def _psq(s: str) -> str:
    """Рядок PowerShell в одинарних лапках. Лапкою PowerShell вважає й ‘ ’ ‚ ‛ (папка «Assassin’s Creed» закрила б
    рядок, а решта шляху стала б кодом) — подвоюємо кожну."""
    for c in "'‘’‚‛":
        s = str(s).replace(c, c + c)
    return "'" + str(s) + "'"


def _ps_line(code: str) -> str:
    b64 = base64.b64encode((E.PS_PREFIX + code).encode("utf-16-le", "surrogatepass")).decode("ascii")
    return f"powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {b64}"


def _file_undo_ps(rec: dict) -> str:
    """Те саме, що engine._undo_file: файл, який гра встигла замінити своїм, лишаємо; помилка (гра запущена й тримає
    бібліотеку) — ненульовий код, тож крок потрапить у failed.txt, а не в done.txt."""
    p, b, sha = _psq(rec["p"]), _psq(rec.get("bak") or ""), _psq(str(rec.get("sha") or "").upper())
    return ("$ErrorActionPreference='Stop';"
            f"$p={p};$b={b};$h={sha};"
            "Remove-Item -LiteralPath ($p+'.optimax-tmp') -Force -ErrorAction SilentlyContinue;"
            "if (Test-Path -LiteralPath $p) {"
            " if ($h -and (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne $h) {"
            "  if ($b -and (Test-Path -LiteralPath $b)) { Remove-Item -LiteralPath $b -Force }; exit 0 };"
            " Remove-Item -LiteralPath $p -Force };"
            "if ($b -and (Test-Path -LiteralPath $b)) { Move-Item -LiteralPath $b -Destination $p -Force };"
            "exit 0")


_HIVE_PS = {"HKLM": "HKEY_LOCAL_MACHINE", "HKCU": "HKEY_CURRENT_USER", "HKCR": "HKEY_CLASSES_ROOT", "HKU": "HKEY_USERS"}


def _kv_undo_ps(rec: dict) -> str:
    """Те саме, що engine._undo_kv: у спільному рядку реєстру повертаємо лише свій параметр, решту не чіпаємо."""
    hive, _, rest = rec["p"].partition("\\")
    k = _psq("Registry::" + _HIVE_PS.get(hive.upper(), hive) + "\\" + rest)
    old = "$null" if rec.get("kvold") is None else _psq(rec["kvold"])
    had = "$true" if rec.get("old") is not None else "$false"
    return ("$ErrorActionPreference='Stop';"
            f"$k={k};$n={_psq(rec['n'])};$key={_psq(rec['kv'])};$old={old};$had={had};"
            "$cur=(Get-ItemProperty -LiteralPath $k -Name $n -ErrorAction SilentlyContinue).$n;"
            # як engine.kv_set: параметр — на своєму місці, решта рядка в тому самому порядку
            "$parts=@();$done=$false;"
            "foreach ($p in ([string]$cur -split ';')) { if (-not $p) { continue };"
            " if ($p.StartsWith($key+'=')) { if (($null -ne $old) -and -not $done) { $parts += ($key+'='+$old) };"
            " $done=$true; continue }; $parts += $p };"
            "if (($null -ne $old) -and -not $done) { $parts += ($key+'='+$old) };"
            "$s=''; if ($parts.Count) { $s=($parts -join ';')+';' };"
            "if ($s -eq '' -and -not $had) { Remove-ItemProperty -LiteralPath $k -Name $n -ErrorAction "
            "SilentlyContinue; exit 0 };"
            "if (-not (Test-Path -LiteralPath $k)) { New-Item -Path $k -Force | Out-Null };"
            "Set-ItemProperty -LiteralPath $k -Name $n -Value $s -Type String;"
            "exit 0")


class _When(str):
    """Крок, який виконується лише за умови cond (команда cmd.exe з кодом 0, коли крок потрібен). Сам рядок — команда
    кроку: невдача рахується як і в інших кроках, а невиконана умова — не збій."""

    def __new__(cls, cmd: str, cond: str):
        s = super().__new__(cls, cmd)
        s.cond = cond
        return s


def undo_lines(rec: dict) -> list:
    """Команди .cmd для одного запису відкату з журналу. Рядок «rem …» — крок, який виконати не можна: запис
    лишиться в журналі (див. build_script)."""
    if not E.valid_undo(rec):
        return [f"rem {_echo(tr('e.undo_bad', what=str(rec)[:60]))}"]
    t = rec.get("t")
    if t == "reg" and rec.get("kv"):
        return [_ps_line(_kv_undo_ps(rec))]
    if t == "reg":
        return _reg_lines(rec)
    if t == "svc":
        return [f'sc config "{_q(rec["n"])}" start= {rec["old"]}']
    if t == "task":
        if _ctl(rec["n"]) != rec["n"]:  # ім'я з керівним символом розірвало б рядок скрипта
            return [f"rem {_echo(tr('e.undo_bad', what=rec['n'][:60]))}"]
        return [f'schtasks /Change /Enable /TN "{_qa(rec["n"])}"']
    if t == "cmd":
        c = str(rec["c"])
        if _ctl(c.replace("\t", " ")) != c.replace("\t", " "):  # CR/LF почали б новий рядок скрипта поза обліком кроку
            return [f"rem {_echo(tr('e.undo_bad', what=c[:60]))}"]
        return [c.replace("%", "%%")]
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
        # Як engine._undo_record: схему знову активуємо, лише якщо вона й зараз активна — інакше Rescue перемкнув би
        # на неї ПК, який після OptimaX уже перейшов на іншу схему
        return [f"powercfg {verb} {rec['g']} {rec['s']} {rec['st']} {rec['old']}",
                _When(f"powercfg -setactive {rec['g']}",
                      f'powercfg /getactivescheme 2>nul | "%SystemRoot%\\System32\\find.exe" /i "{rec["g"]}" >nul')]
    if t == "file":  # копія, яку OptimaX поклала поруч із грою (Mesa), і файл, що лежав там раніше
        return [_ps_line(_file_undo_ps(rec))]
    return []  # live: оновлення Провідника — в кінці; решта діє після перезавантаження


def _cut(cmd: str, n: int = 150) -> str:
    """Початок команди для failed.txt. Відсотки в ній уже подвоєні — обрізаний навпіл %% лишив би одинокий %."""
    s = cmd[:n]
    if (len(s) - len(s.rstrip("%"))) % 2:
        s = s[:-1]
    return s


def build_script(journal: E.Journal = None) -> str:
    j = journal or E.JOURNAL
    groups = batches(j)
    newest = j.newest_first()
    last = groups[0] if groups else []
    when = time.strftime("%d.%m.%Y %H:%M", time.localtime(j.get(last[0]).get("ts", 0))) if last else "—"
    # DisableDelayedExpansion: інакше (параметр DelayedExpansion у реєстрі) «!» у шляхах і значеннях розгорталися б
    L = ["@echo off", "setlocal EnableExtensions DisableDelayedExpansion", "chcp 65001 >nul",
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
        # XF — скільки збоїв було до цього запису: done.txt лише тоді, коли всі його кроки повернулися. Інакше sync()
        # прибрав би з журналу й ті кроки, що не відкотилися, — і повернути їх уже не було б як.
        L += ["", f":x{index[tid]}", "set XF=%FAIL%", f"echo   - {_echo(E.entry_title(tid))}"]
        note = _echo_block(tid).replace("%", "%%")  # id — не команда: відсоток у ньому буквальний
        for rec in reversed(e.get("undo", [])):
            for cmd in undo_lines(rec):
                if cmd.startswith("rem "):  # крок, який виконати не можна, — теж не повернувся
                    L += [cmd, f'set /a FAIL+=1 & >>"%~dp0failed.txt" echo {note}: {_echo_block(_cut(cmd[4:]))}']
                elif cmd.lower().startswith(GONE_OK):  # уже видалено (наприклад, іншим твіком) — мети досягнуто
                    L.append(f"{cmd} >nul 2>&1")
                else:  # невдалий крок — у failed.txt поруч зі скриптом: видно, що саме не повернулося
                    step = (f'{cmd} >nul 2>&1 || (set /a FAIL+=1 & >>"%~dp0failed.txt" echo '
                            f'{note}: {_echo_block(_cut(cmd))})')
                    L.append(f"{cmd.cond} && ({step})" if isinstance(cmd, _When) else step)
        L += ["if not %FAIL%==%XF% exit /b 0", f'>>"%~dp0done.txt" echo {_echo_id(tid)}', "exit /b 0"]
    return "\r\n".join(L) + "\r\n"


def write_rescue(journal: E.Journal = None) -> str:
    """Перегенерувати файл. -> шлях (або '' при помилці запису)."""
    try:
        path = rescue_path()
        tmp = path + ".tmp"
        with SF.remove_then_create(tmp, "w", encoding="utf-8", newline="") as f:
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
    # cmd.exe друкує id дослівно; рядок, записаний без cmd.exe, лишається в екранованому вигляді (^&, %%) чи b64:… —
    # тож порівнюємо точний id: спершу рядок як є, тоді розекранований
    ids = [i if j.has(i) else _unecho_id(i) for i in ids]
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
