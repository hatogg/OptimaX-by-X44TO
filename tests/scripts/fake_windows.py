"""Фальшива Windows для tests/windows/tweak_roundtrip.py на Linux: реєстр у пам'яті (половина значень уже
«існує», як на справжній системі), sc / schtasks / powercfg / bcdedit / netsh / reg, запити PowerShell і виконання
згенерованого OptimaX-Rescue.cmd /all (та підмножина cmd, яку він використовує).

    python tests/scripts/fake_windows.py --out DIR      FAKE_HW=gaming|laptop|old   FAKE_BUG=svc|reg|rescue|task

Перевіряє саму логіку перевірки й команди Rescue-файлу. Справжню Windows це не замінює — для неї CI запускає
tests/windows/tweak_roundtrip.py на windows-2022 / windows-2025."""
import base64
import ctypes
import os
import re
import runpy
import shlex
import subprocess
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BUG = os.environ.get("FAKE_BUG", "")

# ───────────── реєстр ─────────────
HKLM, HKCU, HKCR, HKU = 0x80000002, 0x80000001, 0x80000000, 0x80000003
HIVES = {HKLM: "HKLM", HKCU: "HKCU", HKCR: "HKCR", HKU: "HKU"}
REG = {}  # "HKLM\\path" (lower) -> {"name": str, "values": {lname: (name, type, value)}}


def _k(hive, sub):
    return (HIVES[hive] + "\\" + sub.strip("\\")).lower().rstrip("\\")


class Handle:
    def __init__(self, key):
        self.key = key

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def OpenKey(hive, sub, res=0, access=0):
    k = _k(hive, sub)
    if k not in REG:
        raise FileNotFoundError(2, "not found", k)
    return Handle(k)


OpenKeyEx = OpenKey


def CreateKeyEx(hive, sub, res=0, access=0):
    k = _k(hive, sub)
    parts = k.split("\\")
    for i in range(2, len(parts) + 1):
        REG.setdefault("\\".join(parts[:i]), {"values": {}})
    return Handle(k)


CreateKey = lambda h, s: CreateKeyEx(h, s)  # noqa: E731


def QueryValueEx(h, name):
    v = REG[h.key]["values"].get(name.lower())
    if v is None:
        raise FileNotFoundError(2, "no value", name)
    return v[2], v[1]


def SetValueEx(h, name, res, typ, value):
    REG[h.key]["values"][name.lower()] = (name, typ, value)


def DeleteValue(h, name):
    if name.lower() not in REG[h.key]["values"]:
        raise FileNotFoundError(2, "no value", name)
    del REG[h.key]["values"][name.lower()]


def _children(key):
    pre = key + "\\"
    return sorted({k[len(pre):].split("\\")[0] for k in REG if k.startswith(pre)})


def EnumKey(h, i):
    ch = _children(h.key)
    if i >= len(ch):
        raise OSError(259, "no more")
    return ch[i]


def EnumValue(h, i):
    vals = list(REG[h.key]["values"].values())
    if i >= len(vals):
        raise OSError(259, "no more")
    n, t, v = vals[i]
    return n, v, t


def QueryInfoKey(h):
    return len(_children(h.key)), len(REG[h.key]["values"]), 0


def DeleteKey(h, sub):
    REG.pop(_k_from(h, sub), None)


def _k_from(h, sub):
    return (h.key + "\\" + sub).lower() if isinstance(h, Handle) else _k(h, sub)


winreg = types.ModuleType("winreg")
for n, v in dict(HKEY_LOCAL_MACHINE=HKLM, HKEY_CURRENT_USER=HKCU, HKEY_CLASSES_ROOT=HKCR, HKEY_USERS=HKU,
                 KEY_READ=0x20019, KEY_WRITE=0x20006, KEY_SET_VALUE=2, KEY_ALL_ACCESS=0xF003F, KEY_WOW64_64KEY=0x100,
                 KEY_WOW64_32KEY=0x200, KEY_QUERY_VALUE=1, KEY_ENUMERATE_SUB_KEYS=8,
                 REG_NONE=0, REG_SZ=1, REG_EXPAND_SZ=2, REG_BINARY=3, REG_DWORD=4, REG_MULTI_SZ=7,
                 REG_QWORD=11).items():
    setattr(winreg, n, v)
for f in (OpenKey, OpenKeyEx, CreateKeyEx, CreateKey, QueryValueEx, SetValueEx, DeleteValue, EnumKey, EnumValue,
          QueryInfoKey, DeleteKey):
    setattr(winreg, f.__name__ if f.__name__ != "<lambda>" else "CreateKey", f)
winreg.HKEYType = Handle
sys.modules["winreg"] = winreg


def reg_set(path, name, typ, value):
    hive, _, sub = path.partition("\\")
    h = CreateKeyEx({"HKLM": HKLM, "HKCU": HKCU, "HKCR": HKCR, "HKU": HKU}[hive.upper()], sub)
    SetValueEx(h, name, 0, typ, value)


# службы
SVC = r"HKLM\SYSTEM\CurrentControlSet\Services"
for name, start, delayed in (("SysMain", 2, 0), ("DiagTrack", 2, 0), ("dmwappushservice", 3, 0), ("WSearch", 2, 1),
                             ("XblGameSave", 3, 0), ("XboxNetApiSvc", 3, 0), ("MapsBroker", 2, 1),
                             ("VendorUpdater", 2, 0), ("RemoteRegistry", 4, 0), ("Fax", 3, 0), ("WerSvc", 3, 0),
                             ("RetailDemo", 3, 0), ("lfsvc", 3, 0), ("PhoneSvc", 3, 0), ("WMPNetworkSvc", 3, 0),
                             ("wisvc", 3, 0), ("TrkWks", 2, 0), ("PcaSvc", 2, 1), ("SharedAccess", 3, 0)):
    reg_set(SVC + "\\" + name, "Start", 4, start)
    if delayed:
        reg_set(SVC + "\\" + name, "DelayedAutostart", 4, 1)
for g in ("{11111111-2222-3333-4444-555555555555}", "{aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee}"):
    reg_set(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces" + "\\" + g, "EnableDHCP", 4, 1)
reg_set(r"HKCU\Control Panel\Mouse", "MouseSpeed", 1, "1")
reg_set(r"HKCU\Control Panel\Desktop", "MenuShowDelay", 1, "400")

# ───────────── задачі, живлення, BCD, TCP ─────────────
TASKS = {}
BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
SCHEMES = {BALANCED: "Balanced", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c": "High performance"}
PW = {"active": BALANCED, "vals": {}}
BCD = {"identifier": "{current}", "nx": "OptIn"}
TCP = {"autotuninglevel": "normal", "rss": "enabled", "ecncapability": "default", "congestionprovider": "default"}
FS = {"disablelastaccess": "2", "disable8dot3": "2"}
PS_LOG = []


def svc_start(name):
    try:
        with OpenKey(HKLM, SVC[5:] + "\\" + name) as h:
            st = QueryValueEx(h, "Start")[0]
            try:
                d = QueryValueEx(h, "DelayedAutostart")[0]
            except OSError:
                d = 0
        return st, d
    except OSError:
        return None, 0


def argv_split(cmd):
    """Правила CommandLineToArgvW (як читають аргументи reg.exe, sc.exe тощо)."""
    out, cur, i, inq, have = [], [], 0, False, False
    while i < len(cmd):
        c = cmd[i]
        if c == "\\":
            j = i
            while j < len(cmd) and cmd[j] == "\\":
                j += 1
            n = j - i
            if j < len(cmd) and cmd[j] == '"':
                cur.append("\\" * (n // 2))
                if n % 2:
                    cur.append('"')
                    i = j + 1
                else:
                    i = j
                have = True
                continue
            cur.append("\\" * n)
            i = j
            have = True
            continue
        if c == '"':
            inq = not inq
            have = True
        elif c in " \t" and not inq:
            if have or cur:
                out.append("".join(cur))
            cur, have = [], False
        else:
            cur.append(c)
            have = True
        i += 1
    if have or cur:
        out.append("".join(cur))
    return out


TYPES = {"REG_SZ": 1, "REG_EXPAND_SZ": 2, "REG_BINARY": 3, "REG_DWORD": 4, "REG_MULTI_SZ": 7, "REG_QWORD": 11}


def fake_reg(a):
    op, key = a[1].lower(), a[2]
    o = {}
    i = 3
    while i < len(a):
        t = a[i].lower()
        if t in ("/v", "/t", "/d"):
            o[t] = a[i + 1]
            i += 2
        else:
            o[t] = True
            i += 1
    name = "" if "/ve" in o else o.get("/v", "")
    hive, _, sub = key.partition("\\")
    hv = {"HKLM": HKLM, "HKCU": HKCU, "HKCR": HKCR, "HKU": HKU,
          "HKEY_LOCAL_MACHINE": HKLM, "HKEY_CURRENT_USER": HKCU}[hive.upper()]
    if op == "delete" and "/v" not in o and "/ve" not in o:  # reg delete KEY /f — увесь розділ
        k = _k(hv, sub)
        gone = [x for x in REG if x == k or x.startswith(k + "\\")]
        for x in gone:
            del REG[x]
        return (0, "") if gone else (1, "ERROR: The system was unable to find the specified registry key or value.")
    if op == "delete":
        try:
            with OpenKey(hv, sub) as h:
                DeleteValue(h, name)
            return 0, ""
        except OSError:
            return 1, "ERROR: The system was unable to find the specified registry key or value."
    typ = TYPES[o.get("/t", "REG_SZ").upper()]
    d = o.get("/d", "")
    if typ == 4:
        v = int(d, 0)
        if BUG == "reg":
            v += 1
    elif typ == 11:
        v = int(d, 0)
    elif typ == 3:
        v = bytes.fromhex(d)
    elif typ == 7:
        v = d.split("\\0") if d else []
    else:
        v = d
    with CreateKeyEx(hv, sub) as h:
        SetValueEx(h, name, 0, typ, v)
    return 0, "The operation completed successfully."


def run_argv(a):
    if not a:
        return 0, ""
    exe = os.path.basename(a[0]).lower().removesuffix(".exe")
    low = [x.lower() for x in a]
    if exe == "reg":
        return fake_reg(a)
    if exe == "sc":
        if low[1] == "stop":
            return 0, ""
        if low[1] == "config":
            name, mode = a[2], a[a.index("start=") + 1] if "start=" in a else a[-1]
            if svc_start(name)[0] is None:
                return 1060, "[SC] OpenService FAILED 1060"
            if BUG == "svc" and mode == "auto":
                mode = "demand"
            st = {"auto": 2, "delayed-auto": 2, "demand": 3, "disabled": 4}[mode]
            reg_set(SVC + "\\" + name, "Start", 4, st)
            reg_set(SVC + "\\" + name, "DelayedAutostart", 4, 1 if mode == "delayed-auto" else 0)
            return 0, "[SC] ChangeServiceConfig SUCCESS"
        return 0, ""
    if exe == "schtasks":
        tn = a[low.index("/tn") + 1] if "/tn" in low else ""
        if "/change" in low:
            if tn.lower() not in TASKS:
                return 1, "ERROR: The system cannot find the file specified."
            if BUG == "task" and "/enable" in low:  # зламаний відкат: задача лишається вимкненою
                return 0, "SUCCESS"
            TASKS[tn.lower()] = "/enable" in low
            return 0, "SUCCESS"
        return 0, ""
    if exe == "powercfg":
        v = low[1]
        if v in ("/getactivescheme", "-getactivescheme"):
            return 0, f"Power Scheme GUID: {PW['active']}  ({SCHEMES.get(PW['active'], '?')})"
        if v in ("/list", "-list", "/l"):
            return 0, "\n".join(f"Power Scheme GUID: {g}  ({n}){' *' if g == PW['active'] else ''}"
                                for g, n in SCHEMES.items())
        if v in ("/query", "-query", "/q"):
            g, sub, st = a[2].lower(), a[3], a[4]
            ac, dc = PW["vals"].get((g, sub, st), (0, 0))
            return 0, f"    Current AC Power Setting Index: 0x{ac:08x}\n    Current DC Power Setting Index: 0x{dc:08x}"
        if v in ("-setacvalueindex", "/setacvalueindex", "-setdcvalueindex", "/setdcvalueindex"):
            g, sub, st, val = a[2].lower(), a[3], a[4], int(a[5], 0)
            ac, dc = PW["vals"].get((g, sub, st), (0, 0))
            PW["vals"][(g, sub, st)] = (val, dc) if "ac" in v else (ac, val)
            return 0, ""
        if v in ("-setactive", "/setactive", "/s"):
            if a[2].lower() not in SCHEMES:
                return 1, "Invalid"
            PW["active"] = a[2].lower()
            return 0, ""
        if v in ("-duplicatescheme", "/duplicatescheme"):
            g = "deadbeef-0000-4000-8000-%012x" % len(SCHEMES)
            SCHEMES[g] = "Ultimate Performance"
            return 0, f"Power Scheme GUID: {g}  (Ultimate Performance)"
        if v in ("-delete", "/delete", "/d"):
            SCHEMES.pop(a[2].lower(), None)
            return 0, ""
        return 0, ""
    if exe == "bcdedit":
        if low[1] == "/set":
            BCD[low[2]] = a[3]
        elif low[1] == "/deletevalue":
            if low[2] not in BCD:
                return 1, "The element was not found."
            BCD.pop(low[2], None)
        elif low[1] == "/enum":
            return 0, "\n".join(f"{k:24}{v}" for k, v in sorted(BCD.items()))
        return 0, "The operation completed successfully."
    if exe == "netsh":
        if "show" in low:
            return 0, "\n".join(f"{k}: {v}" for k, v in sorted(TCP.items()))
        for x in a:
            if "=" in x:
                k, v = x.split("=", 1)
                TCP[k.lower()] = v
        return 0, "Ok."
    if exe == "fsutil":
        if "set" in low:
            FS[low[low.index("set") + 1]] = a[-1]
        return 0, ""
    if exe in ("powershell", "pwsh"):
        if "-encodedcommand" in low:
            code = base64.b64decode(a[low.index("-encodedcommand") + 1]).decode("utf-16-le")
            return fake_ps(code)
        return 0, ""
    return 0, ""  # DISM, ie4uinit, taskkill, tasklist, start …


def fake_ps(code):
    PS_LOG.append(code[-200:])
    if "foreach ($n in @(" in code and "Get-ScheduledTask" in code:  # task_states() перевірки твіків
        arr = code.split("foreach ($n in @(", 1)[1].split("))", 1)[0]
        names = [n.replace("''", "'") for n in re.findall(r"'((?:[^']|'')*)'", arr)]
        out = []
        for n in names:
            st = TASKS.get(n.lower())
            out.append(f"{n}|{'MISSING' if st is None else 'Ready' if st else 'Disabled'}")
        return 0, "\n".join(out)
    m = re.search(r"Get-ScheduledTask -TaskPath '([^']*)' -TaskName '([^']*)'", code)
    if m:
        name = (m.group(1) + m.group(2)).lower()
        if name not in TASKS:
            return 0, "MISSING"
        return 0, "Ready" if TASKS[name] else "Disabled"
    if "Get-ScheduledTask | Where-Object" in code:
        return 0, "\n".join(k for k, en in TASKS.items() if en)
    if "Win32_Service" in code:
        out = []
        for n in _children(SVC.lower()):
            st, _ = svc_start(n)
            out.append(f"{n}={ {2: 'Auto', 3: 'Manual', 4: 'Disabled'}.get(st, 'Unknown') }")
        return 0, "\n".join(out)
    if "StartType -eq 'Automatic'" in code:
        return 0, "VendorUpdater\nMapsBroker"
    return 0, ""


def fake_run(cmd, timeout=30, log=None, input_text=None, enc=None, ro=False):
    a = argv_split(cmd) if isinstance(cmd, str) else list(cmd)
    rc, out = run_argv(a)
    return rc, out


# ───────────── виконання згенерованого OptimaX-Rescue.cmd /all ─────────────
def run_rescue(path, mode):
    lines = open(path, encoding="utf-8", newline="").read().split("\r\n")
    labels = {ln[1:]: i for i, ln in enumerate(lines) if ln.startswith(":")}
    fail, done = 0, []
    i = labels[mode.lstrip("/")] + 1
    while not lines[i].startswith("goto finish"):
        m = re.match(r"call :(x\d+)$", lines[i])
        if m:
            j = labels[m.group(1)] + 1
            while lines[j] != "exit /b 0":
                ln = lines[j]
                if ln.startswith(">>\"%~dp0done.txt\" echo "):
                    done.append(ln.split(" echo ", 1)[1])
                elif " >nul 2>&1 || (set /a FAIL+=1 & >>\"%~dp0failed.txt\" echo " in ln or ln.endswith(" >nul 2>&1"):
                    counts = " || (set /a FAIL+=1" in ln
                    c = ln[:ln.index(" >nul 2>&1")].replace("%%", "%")
                    if BUG == "rescue" and c.startswith("sc config"):
                        c = "rem skipped"
                    rc, out = run_argv(argv_split(c))
                    fail += counts and rc != 0
                    if rc and counts:
                        print("  rescue step failed:", rc, c[:160], "|", out[:80], flush=True)
                        note = ln.split(' echo ', 1)[1][:-1]
                        for a, b in (("^(", "("), ("^)", ")"), ("^&", "&"), ("^|", "|"), ("^<", "<"), ("^>", ">"),
                                     ("%%", "%"), ("^^", "^")):  # як надрукує echo у cmd
                            note = note.replace(a, b)
                        with open(os.path.join(os.path.dirname(path), "failed.txt"), "a") as f:
                            f.write(note + "\n")
                j += 1
        i += 1
    with open(os.path.join(os.path.dirname(path), "done.txt"), "a") as f:
        f.write("".join(d + "\n" for d in done))
    return fail


_orig_run = subprocess.run


def sub_run(args, *a, **k):
    if isinstance(args, list) and args[:2] == ["cmd", "/c"]:
        rc = run_rescue(args[2], args[3])
        return subprocess.CompletedProcess(args, rc, b"done", b"")
    return _orig_run(args, *a, **k)


_orig_popen = subprocess.Popen


class _RescueProc:
    """cmd /c OptimaX-Rescue.cmd, запущений через Popen із виводом у файл (як у перевірці на справжній Windows)."""
    pid = 0

    def __init__(self, args, stdout=None, **_k):
        self.returncode = run_rescue(args[2], args[3])
        if stdout is not None and hasattr(stdout, "write"):
            stdout.write(b"done")

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        pass


def sub_popen(args, *a, **k):
    if isinstance(args, list) and args[:2] == ["cmd", "/c"]:
        return _RescueProc(args, **k)
    return _orig_popen(args, *a, **k)


class _DLL:
    def __getattr__(self, n):
        return lambda *a, **k: 437 if n == "GetOEMCP" else 1


class _Win:
    def __getattr__(self, n):
        return _DLL()


# стандартні модулі — до підміни sys.platform (інакше вони шукатимуть _winapi тощо)
import importlib  # noqa: E402
for _m in ("tempfile", "shutil", "json", "threading", "socket", "ssl", "urllib.request", "http.server", "datetime",
           "random", "string", "struct", "glob", "ntpath", "platform", "locale", "uuid", "zipfile", "csv", "hashlib",
           "queue", "traceback", "dataclasses", "typing", "math", "statistics", "io", "collections", "itertools",
           "functools", "html", "xml.etree.ElementTree", "email.utils", "argparse", "webbrowser", "getpass",
           "concurrent.futures", "selectors", "signal", "copy", "textwrap", "difflib", "fnmatch", "pathlib",
           "configparser", "base64", "binascii", "secrets", "ipaddress", "gzip", "logging"):
    try:
        importlib.import_module(_m)
    except Exception:
        pass
import tempfile  # noqa: E402
ctypes.windll = _Win()
subprocess.run = sub_run
subprocess.Popen = sub_popen
sys.platform = "win32"
os.environ["CI"] = "true"
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="fakewin_app_")
os.environ["ProgramData"] = tempfile.mkdtemp(prefix="fakewin_pd_")
sys.path.insert(0, ROOT)
import engine as E  # noqa: E402
import hardware as H  # noqa: E402

E.run = fake_run
E.restart_explorer = lambda log=None: None
E.explorer_start = lambda log=None: None
E.create_restore_point = lambda log=None: None
_hw = H._from_demo(os.environ.get("FAKE_HW", "gaming"))
_hw.update(build=22631, os="Windows 11 Pro (fake)")
H.detect_hw = lambda: dict(_hw)
for t in E.TWEAKS:  # усі задачі з каталогу існують і ввімкнені
    for op in t.ops:
        if op[0] == "task":
            for tn in op[1]:
                TASKS[tn.lower()] = True
# справжня Windows уже має більшість цих значень: половину «вже існуючих» засіваємо іншими значеннями
import zlib  # noqa: E402
_TY = {"dword": 4, "sz": 1, "expand": 2, "qword": 11, "bin": 3}
for t in E.TWEAKS:
    for op in t.ops:
        if op[0] == "reg" and not callable(op[3]) and zlib.crc32(f"{op[1]}|{op[2]}".encode()) % 2 == 0:
            typ = _TY.get(op[4] if isinstance(op[4], str) else "dword", 4)
            v = op[3]
            seed = {4: ((int(v) + 7) & 0xFFFFFFFF) if isinstance(v, int) else 7, 11: 9, 1: f"orig-{v}", 2: f"%Orig%\\{v}",
                    3: b"\x01\x02"}[typ]
            reg_set(op[1], op[2], typ, seed)
# початкові значення живлення
for t in E.TWEAKS:
    for op in t.ops:
        if op[0] == "pw":
            PW["vals"].setdefault((BALANCED, op[1], op[2]), (5, 5))
sys.argv = [os.path.join(ROOT, "tests", "windows", "tweak_roundtrip.py")] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
