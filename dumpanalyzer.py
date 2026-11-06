"""
OptimaX Hardware Center — аналіз дампів синіх екранів (cdb.exe) і діагностика Windows.

cdb.exe (консольний налагоджувач із Debugging Tools for Windows) у складі OptimaX не постачається — це сотні мегабайтів
і ліцензія Microsoft на розповсюдження. OptimaX шукає вже встановлений: поруч із програмою (tools\\cdb\\cdb.exe — якщо
його туди поклали), у Windows SDK (Windows Kits\\10\\Debuggers\\x64) і в PATH. Без cdb лишається розбір за кодом
помилки з заголовка дампу (crashlog.py), як і раніше.

З cdb: `cdb -z <дамп> -c "!analyze -v; q"` із символами з офіційного сервера Microsoft
(srv*<кеш>*https://msdl.microsoft.com/download/symbols). Дамп відкривається лише для читання; мінідампи для певності
копіюються в тимчасову папку й аналізуються з копії. З виводу беремо BUGCHECK_CODE, MODULE_NAME, IMAGE_NAME,
FAILURE_BUCKET_ID, PROCESS_NAME, STACK_TEXT і підозрюваний драйвер (.sys).

Відновлення Windows (SFC, DISM) змінює систему й не відкочується журналом — запускається лише після підтвердження,
а в журнал програми пишеться, що саме запущено й з яким результатом.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import tempfile
import time

import engine as E
from i18n import tr

SYMBOLS_URL = "https://msdl.microsoft.com/download/symbols"
CDB_TIMEOUT = 600
MEMORY_DMP = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "MEMORY.DMP")
FIELDS = ("BUGCHECK_CODE", "BUGCHECK_STR", "MODULE_NAME", "IMAGE_NAME", "FAILURE_BUCKET_ID", "PROCESS_NAME",
          "SYMBOL_NAME", "DEFAULT_BUCKET_ID")
REPAIRS = {
    "sfc": ["sfc", "/scannow"],
    "dism_check": ["DISM", "/Online", "/Cleanup-Image", "/ScanHealth"],
    "dism_restore": ["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"],
}


def _app_dir() -> str:
    import sys
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def cdb_candidates() -> list:
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    app = _app_dir()
    return [os.path.join(app, "tools", "cdb", "cdb.exe"), os.path.join(app, "cdb", "cdb.exe"),
            os.path.join(app, "cdb.exe"),
            os.path.join(pf86, "Windows Kits", "10", "Debuggers", "x64", "cdb.exe"),
            os.path.join(pf, "Windows Kits", "10", "Debuggers", "x64", "cdb.exe"),
            os.path.join(pf86, "Windows Kits", "8.1", "Debuggers", "x64", "cdb.exe")]


def find_cdb() -> str:
    """Шлях до cdb.exe або "" (на Windows: поруч із програмою, Windows SDK, PATH)."""
    if not E.IS_WIN:
        return ""
    for p in cdb_candidates():
        if os.path.isfile(p):
            return p
    w = shutil.which("cdb.exe") or shutil.which("cdb")
    if w:
        return w
    for p in glob.glob(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WindowsApps",
                                    "Microsoft.WinDbg_*", "amd64", "cdb.exe")):
        return p  # WinDbg з Microsoft Store (якщо папка взагалі читається)
    return ""


def list_dumps() -> dict:
    import crashlog as CL
    out = []
    for d in CL.dumps() if E.IS_WIN else _demo_dumps():
        name, text = CL.describe_code(d.get("code") or 0) if d.get("code") else ("", "")
        out.append(dict(d, path=os.path.join(CL.DUMP_DIR, d["name"]) if E.IS_WIN else d["name"],
                        code_text=f"0x{d['code']:X} {name}".strip() if d.get("code") else ""))
    if E.IS_WIN and os.path.isfile(MEMORY_DMP):
        try:
            st = os.stat(MEMORY_DMP)
            out.append(dict(name="MEMORY.DMP", path=MEMORY_DMP, ts=int(st.st_mtime), size=st.st_size,
                            code=CL.dump_code(MEMORY_DMP), code_text=""))
        except OSError:
            pass
    return dict(cdb=find_cdb() if E.IS_WIN else "", dumps=out)


def _demo_dumps() -> list:
    if E.DEMO not in ("gaming", "mining"):
        return []
    return [dict(name="110626-9812-01.dmp", ts=int(time.time()) - 86400 * 3, size=1_310_720, code=0x116)]


def sympath() -> str:
    cache = os.path.join(tempfile.gettempdir(), "OptimaX-symbols")
    return f"srv*{cache}*{SYMBOLS_URL}"


def parse_analyze(text: str) -> dict:
    """Вивід `!analyze -v` -> {поле: значення, stack: [...], suspect: драйвер .sys або ""}."""
    out = {}
    for f in FIELDS:
        m = re.search(rf"^{f}:\s*(.+?)\s*$", text, re.M)
        if m:
            out[f.lower()] = m.group(1).strip()
    if "bugcheck_code" not in out:
        m = re.search(r"BugCheck\s+([0-9A-Fa-f]+),", text)
        if m:
            out["bugcheck_code"] = m.group(1)
    m = re.search(r"^Probably caused by\s*:\s*(\S+)", text, re.M)
    if m:
        out["probably"] = m.group(1)
    st = re.search(r"^STACK_TEXT:\s*\n(.*?)(?:\n\s*\n|\Z)", text, re.M | re.S)
    if st:
        out["stack"] = [ln.strip() for ln in st.group(1).splitlines() if ln.strip()][:12]
    img = out.get("image_name") or out.get("probably") or ""
    out["suspect"] = img if img.lower().endswith(".sys") else ""
    try:
        out["code"] = int(out.get("bugcheck_code", "0"), 16)
    except ValueError:
        out["code"] = 0
    return out


DEMO_ANALYZE = """BugCheck 116, {ffffb20f1b2c4010, fffff8065a1c8b90, ffffffffc000009a, 4}
Probably caused by : nvlddmkm.sys ( nvlddmkm+108b90 )

BUGCHECK_CODE:  116
BUGCHECK_STR:  0x116
PROCESS_NAME:  System
STACK_TEXT:
ffff8a01`1b6e7a08 fffff806`5a1f3b5e     : 00000000`00000116 ffffb20f`1b2c4010 : nt!KeBugCheckEx
ffff8a01`1b6e7a10 fffff806`5a1b1e94     : ffffb20f`1b2c4010 fffff806`5a1c8b90 : dxgkrnl!TdrBugcheckOnTimeout+0xfe

MODULE_NAME: nvlddmkm
IMAGE_NAME:  nvlddmkm.sys
FAILURE_BUCKET_ID:  0x116_IMAGE_nvlddmkm.sys
"""


def analyze_dump(path: str, log) -> dict:
    """!analyze -v через cdb (лише читання). -> результат Hardware Center «windiag_dump»."""
    import hwtests as HT
    cdb = find_cdb()
    if not E.IS_WIN:
        text = DEMO_ANALYZE
    elif not cdb:
        return HT.result("windiag_dump", HT.NA, tr("da.no_cdb"))
    else:
        src = path
        tmp = ""
        try:
            if os.path.getsize(path) < 64 << 20:  # мінідамп — аналізуємо копію, оригінал не відкривається взагалі
                tmp = os.path.join(tempfile.mkdtemp(prefix="oxdmp_"), os.path.basename(path))
                shutil.copy2(path, tmp)
                src = tmp
            log(f"  cdb -z {os.path.basename(path)} -c \"!analyze -v; q\"")
            p = subprocess.run([cdb, "-z", src, "-y", sympath(), "-c", "!analyze -v; q"], capture_output=True,
                               timeout=CDB_TIMEOUT, creationflags=E.CREATE_NO_WINDOW)
            text = (p.stdout or b"").decode("utf-8", "replace")
        except subprocess.TimeoutExpired:
            return HT.result("windiag_dump", HT.NA, tr("da.timeout", s=CDB_TIMEOUT))
        except OSError as e:
            return HT.result("windiag_dump", HT.NA, tr("e.err", err=e))
        finally:
            if tmp:
                shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
    a = parse_analyze(text)
    if not a.get("code") and not a.get("module_name"):
        return HT.result("windiag_dump", HT.NA, tr("da.unparsed"))
    import crashlog as CL
    name, cat = CL.describe_code(a["code"]) if a.get("code") else ("", "unknown")
    f = [(HT.FAIL, "da.f.bsod", dict(code=f"0x{a['code']:X}", name=name or a.get("bugcheck_str", "")))]
    if a.get("suspect"):
        f.append((HT.WARN, "da.f.suspect", dict(drv=a["suspect"])))
    f.append(("info", f"crash.cat.{cat or 'unknown'}", {}))
    rows = [("da.r.file", os.path.basename(path)), ("da.r.code", f"0x{a['code']:X} {name}".strip()),
            ("da.r.module", a.get("module_name")), ("da.r.image", a.get("image_name")),
            ("da.r.bucket", a.get("failure_bucket_id")), ("da.r.process", a.get("process_name")),
            ("da.r.stack", "\n".join(a.get("stack") or [])[:900] or None)]
    log(tr("da.log", code=f"0x{a['code']:X}", drv=a.get("suspect") or a.get("module_name") or "?"))
    return HT.result("windiag_dump", HT.FAIL, tr("da.sum", code=f"0x{a['code']:X}", name=name or "?"), rows=rows,
                     findings=f, analysis={k: v for k, v in a.items() if k != "stack"}, stack=a.get("stack") or [])


DRIVER_PS = r"""
@(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Error' } |
  ForEach-Object { @{name=$_.FriendlyName; cls=[string]$_.Class; code=[int]$_.ConfigManagerErrorCode} }) |
  ConvertTo-Json -Compress
"""


def problem_devices() -> list:
    if not E.IS_WIN:
        return [] if E.DEMO != "old" else [dict(name="PCI Simple Communications Controller", cls="Unknown", code=28)]
    try:
        return [x for x in E.as_list(E.ps_json(DRIVER_PS, 40)) if isinstance(x, dict) and x.get("name")]
    except Exception:
        return []


def windows_health(log) -> dict:
    """Аварійні перезавантаження й сині екрани, скидання відеодрайвера, апаратні помилки WHEA, пристрої з помилкою
    драйвера, результат перевірки пам'яті — за 30 днів журналу Windows (crashlog.py) -> результат «windiag»."""
    import crashlog as CL
    import hwtests as HT
    try:
        a = CL.analyze() if E.IS_WIN else _demo_crash()
    except Exception as e:  # noqa: BLE001
        log(tr("e.err", err=e))
        a = {}
    devs = problem_devices()
    incs = a.get("incidents") or []
    bsod = [i for i in incs if i.get("kind") == "bsod"]
    power = [i for i in incs if i.get("kind") == "power"]
    g, whea, mt = a.get("gpu") or {}, a.get("whea") or {}, a.get("memtest") or {}
    f = []
    if bsod:
        f.append((HT.FAIL if len(bsod) >= 2 else HT.WARN, "da.f.bsods", dict(n=len(bsod), d=a.get("days", CL.DAYS))))
    if power:
        f.append((HT.WARN, "da.f.power", dict(n=len(power))))
    if g.get("n"):
        f.append((HT.WARN, "da.f.tdr", dict(n=g["n"])))
    if whea.get("fatal"):
        f.append((HT.FAIL, "da.f.whea_fatal", dict(n=whea["fatal"])))
    elif whea.get("n"):
        f.append((HT.WARN, "da.f.whea", dict(n=whea["n"])))
    if mt.get("ok") is False:
        f.append((HT.FAIL, "da.f.memtest_bad", {}))
    for d in devs[:5]:
        f.append((HT.WARN, "da.f.device", dict(name=d.get("name"), code=d.get("code"))))
    st = HT.status_of(f)
    rows = [("da.r.bsod", len(bsod)), ("da.r.power", len(power)), ("da.r.tdr", g.get("n", 0)),
            ("da.r.whea", whea.get("n", 0)), ("da.r.devices", len(devs)),
            ("da.r.memtest", tr("hwc.st.pass") if mt.get("ok") else tr("hwc.st.fail") if mt.get("ok") is False else None)]
    return HT.result("windiag", st, tr(f"da.sum.{st}", d=a.get("days", CL.DAYS)), rows=rows, findings=f,
                     crash={k: v for k, v in a.items() if k in ("gpu", "whea", "memtest", "days")},
                     incidents=[{k: i.get(k) for k in ("ts", "kind", "code", "name", "category", "game")} for i in incs])


def _demo_crash() -> dict:
    now = int(time.time())
    if E.DEMO == "gaming":
        return dict(days=30, incidents=[dict(ts=now - 86400 * 3, kind="bsod", code=0x116, name="VIDEO_TDR_FAILURE",
                                             category="gpu", game="Counter-Strike 2")],
                    gpu=dict(n=2, last=now - 86400 * 3, driver="nvlddmkm"), whea={}, memtest={})
    return dict(days=30, incidents=[], gpu={}, whea={}, memtest={})


def repair(key: str, log) -> dict:
    """SFC / DISM — лише після підтвердження в інтерфейсі. Змінює систему: не відкочується журналом відкату."""
    cmd = REPAIRS.get(key)
    if not cmd:
        return {"error": key}
    log(f"[►] {' '.join(cmd)}")
    if not E.IS_WIN or E.DRY_RUN:
        log("  [dry-run]")
        return {"ok": 1}
    rc, out = E.run(cmd, 3600, ro=key == "dism_check")
    for line in (out or "").splitlines()[-15:]:
        if line.strip():
            log("  " + line.strip())
    log(tr("da.repair_rc", rc=rc))
    import features as F
    import hwtests as HT
    st = HT.PASS if rc == 0 else HT.WARN
    HT.save(F.CFG, HT.result(f"repair_{key}", st, tr("da.repair_rc", rc=rc), rows=[("da.r.cmd", " ".join(cmd))]))
    return {"ok": rc == 0, "rc": rc}
