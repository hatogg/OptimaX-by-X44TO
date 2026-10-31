"""
OptimaX by X44TO — ядро: запуск команд, реєстр, журнал відкату, каталог оптимізацій.

Режим --dry-run (або запуск не на Windows) нічого не змінює в системі, лише показує дії.
Читання стану системи (ro=True) у режимі перегляду на Windows виконується по-справжньому.
"""
from __future__ import annotations

import base64
import ctypes
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    import winreg
except ImportError:  # не Windows: інтерфейс можна переглянути, дії виконуються «вхолосту»
    winreg = None

from i18n import tr, tweak_text

APP_NAME = "OptimaX"
AUTHOR = "X44TO"
APP_TITLE = f"{APP_NAME} by {AUTHOR}"
VERSION = "6.6"
IS_WIN = sys.platform == "win32"
DRY_RUN = (not IS_WIN) or ("--dry-run" in sys.argv)
DEMO = os.environ.get("OPTIMAX_DEMO", "gaming")  # демо-залізо поза Windows: gaming/laptop/old/x3d/xeon
CANCEL = threading.Event()

APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
DATA_DIR = os.path.join(APPDATA, APP_NAME)
JOURNAL_PATH = os.path.join(DATA_DIR, "back.dryrun.json" if DRY_RUN else "back.json")
CREATE_NO_WINDOW = 0x08000000
TIMEOUT_RC = -999

GUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
POWER_SAVER = "a1841308-3541-4fab-bc81-f71556f20b4a"
ULTIMATE_TPL = "e9a42b02-d5df-448d-aa00-03f14749eb61"


def _oem() -> str:
    if IS_WIN:
        try:
            return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        except Exception:
            pass
    return "utf-8"


OEM = _oem()


def is_admin() -> bool:
    if not IS_WIN:
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def win_build() -> int:
    if IS_WIN:
        try:
            return sys.getwindowsversion().build
        except Exception:
            pass
    return 22631


# ───────────────────────── запуск процесів ─────────────────────────
def _decode(b: bytes, enc: Optional[str] = None) -> str:
    if not b:
        return ""
    if enc:
        return b.decode(enc, "replace")
    if b"\x00" in b[:200]:  # sfc.exe та частина утиліт пишуть UTF-16
        return b.decode("utf-16-le", "replace").lstrip("﻿")
    return b.decode(OEM, "replace")


def first_line(s: str, n: int = 90) -> str:
    lines = (s or "").strip().splitlines()
    return (lines[0] if lines else "")[:n]


def run(cmd, timeout: int = 30, log: Optional[Callable] = None, input_text: Optional[str] = None,
        enc: Optional[str] = None, ro: bool = False):
    """-> (код повернення, вивід). ro=True — лише читання, виконується навіть у режимі перегляду."""
    shown = cmd if isinstance(cmd, str) else subprocess.list2cmdline(cmd)
    if not IS_WIN:
        if log and not ro:
            log(f"  [dry-run] {shown[:110]}")
        return (1, "") if ro else (0, "")
    if DRY_RUN and not ro:
        if log:
            log(f"  [dry-run] {shown[:110]}")
        return 0, ""
    try:
        p = subprocess.Popen(cmd, shell=isinstance(cmd, str), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             stdin=subprocess.PIPE if input_text else subprocess.DEVNULL,
                             creationflags=CREATE_NO_WINDOW)
    except Exception as e:
        return 1, str(e)
    chunks = []
    reader = threading.Thread(target=_drain, args=(p.stdout, chunks.append), daemon=True)
    reader.start()
    if input_text:
        try:
            p.stdin.write(input_text.encode(OEM, "replace"))
            p.stdin.close()
        except OSError:
            pass
    # subprocess.run(timeout=…) на Windows після тайм-ауту вбиває лише cmd.exe і далі чекає, поки дочірні процеси
    # (dism → DismHost, wsreset → Store) закриють канал виводу, — тобто тайм-аут не спрацьовував узагалі,
    # а кнопка «Зупинити» не могла перервати довгу команду. Тепер зупиняємо все дерево процесів.
    stoppable = not ro and timeout >= 60
    deadline = time.time() + timeout
    while True:
        try:
            p.wait(0.2)
            break
        except subprocess.TimeoutExpired:
            if time.time() > deadline or (stoppable and CANCEL.is_set()):
                kill_tree(p)
                reader.join(5)
                return TIMEOUT_RC, "[TIMEOUT]" if time.time() > deadline else "[CANCELLED]"
    reader.join(5)  # нащадок, що пережив процес, може тримати канал — довше його не чекаємо
    return p.returncode, _decode(b"".join(chunks), enc).strip()


def _drain(pipe, put) -> None:
    try:
        for block in iter(lambda: pipe.read1(4096), b""):  # read1 — не чекати повних 4 КБ, віддавати що є
            put(block)
    except (OSError, ValueError):
        pass


def kill_tree(p) -> None:
    """Зупиняє процес разом з усіма дочірніми (taskkill /T), а не лише оболонку cmd.exe."""
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, timeout=20,
                       creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass
    try:
        p.kill()
    except Exception:
        pass


PS_PREFIX = "$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"


def ps(script: str, timeout: int = 30, log: Optional[Callable] = None, ro: bool = False):
    if not IS_WIN or (DRY_RUN and not ro):
        if log and not ro:
            head = (script.strip().splitlines() or [""])[0]
            log(f"  [dry-run] powershell: {head[:90]}")
        return (1, "") if (ro and not IS_WIN) else (0, "")
    b64 = base64.b64encode((PS_PREFIX + script).encode("utf-16-le")).decode("ascii")
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-EncodedCommand", b64], timeout, None, enc="utf-8-sig", ro=True)


def ps_json(script: str, timeout: int = 40):
    """PowerShell-запит, що повертає JSON. Лише читання. -> об'єкт або None."""
    _rc, out = ps(script, timeout, ro=True)
    # Код повернення не дивимося: PowerShell повертає 1, якщо остання команда скрипту дала помилку, хоча JSON уже
    # виведено. stderr злитий зі stdout — попередження й помилки окремих команд (обмежений режим мови, зламаний
    # WMI-клас, антивірус) стоять перед JSON або після нього, тож шукаємо сам JSON.
    return parse_json_out(out)


def parse_json_out(out: str):
    out = (out or "").strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except Exception:
        pass
    lines = out.splitlines()
    for line in reversed(lines):  # -Compress: увесь JSON — один рядок
        s = line.strip()
        if s[:1] in "{[" and s[-1:] in "}]":
            try:
                return json.loads(s)
            except Exception:
                continue
    starts = [i for i, ln in enumerate(lines) if ln.lstrip()[:1] in "{["]
    ends = [i for i, ln in enumerate(lines) if ln.rstrip()[-1:] in "}]"]
    for a in starts:  # багаторядковий JSON серед сторонніх рядків
        for b in reversed(ends):
            if b < a:
                break
            try:
                return json.loads("\n".join(lines[a:b + 1]))
            except Exception:
                continue
    return None


def as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])


def stream(cmd: str, log: Callable, parse: Callable, timeout: int = 1800, enc: Optional[str] = None) -> bool:
    """Довга команда з порядковим виводом (SFC, DISM, defrag)."""
    if DRY_RUN:
        log(f"  [dry-run] {cmd}")
        return True
    try:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding=enc or OEM, errors="replace", creationflags=CREATE_NO_WINDOW)
    except Exception as e:
        log(tr("e.stream_fail", err=e))
        return False
    import queue
    lines = queue.Queue()

    def read():
        try:
            for raw in p.stdout:
                lines.put(raw)
        except (OSError, ValueError):
            pass
        lines.put(None)
    threading.Thread(target=read, daemon=True).start()
    t0 = time.time()
    while True:
        # перевіряємо «Зупинити» й тайм-аут і тоді, коли команда довго мовчить (DISM може мовчати хвилинами)
        if CANCEL.is_set() or time.time() - t0 > timeout:
            kill_tree(p)
            log(tr("e.stream_stop"))
            return False
        try:
            raw = lines.get(timeout=0.3)
        except queue.Empty:
            continue
        if raw is None:
            break
        line = raw.replace("\x00", "").strip()
        if not line:
            continue
        out = parse(line)
        if out:
            log(out)
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:
        kill_tree(p)
    return p.returncode == 0


# ───────────────────────── реєстр ─────────────────────────
def _types():
    return {"dword": winreg.REG_DWORD, "sz": winreg.REG_SZ, "expand": winreg.REG_EXPAND_SZ,
            "qword": winreg.REG_QWORD, "bin": winreg.REG_BINARY}


TYPE_NAMES = {"dword": "REG_DWORD", "sz": "REG_SZ", "expand": "REG_EXPAND_SZ", "qword": "REG_QWORD",
              "bin": "REG_BINARY"}


def _split(path: str):
    hive, _, sub = path.partition("\\")
    return {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER,
            "HKCR": winreg.HKEY_CLASSES_ROOT, "HKU": winreg.HKEY_USERS}[hive.upper()], sub


def _enc(v):
    return {"hex": bytes(v).hex()} if isinstance(v, (bytes, bytearray)) else v


def _dec(v):
    return bytes.fromhex(v["hex"]) if isinstance(v, dict) and "hex" in v else v


def reg_get(path: str, name: str):
    """-> (тип, значення) або None."""
    if not winreg:
        return None
    try:
        hive, sub = _split(path)
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            v, t = winreg.QueryValueEx(k, name)
            return t, v
    except OSError:
        return None


def reg_set(path: str, name: str, value, rtype) -> None:
    if isinstance(rtype, str):
        rtype = _types()[rtype]
    hive, sub = _split(path)
    with winreg.CreateKeyEx(hive, sub, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
        winreg.SetValueEx(k, name, 0, rtype, value)


def reg_del_value(path: str, name: str) -> None:
    if not winreg:
        return
    try:
        hive, sub = _split(path)
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
            winreg.DeleteValue(k, name)
    except OSError:
        pass


def reg_subkeys(path: str) -> list:
    if not winreg:
        return []
    try:
        hive, sub = _split(path)
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return [winreg.EnumKey(k, i) for i in range(winreg.QueryInfoKey(k)[0])]
    except OSError:
        return []


def reg_values(path: str) -> list:
    """-> [(ім'я, значення, тип)]"""
    if not winreg:
        return []
    try:
        hive, sub = _split(path)
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return [winreg.EnumValue(k, i) for i in range(winreg.QueryInfoKey(k)[1])]
    except OSError:
        return []


# ───────────────────────── служби та живлення ─────────────────────────
def svc_get_start(name: str):
    """'auto' | 'delayed-auto' | 'demand' | 'disabled' | None (немає такої служби)."""
    if not IS_WIN:
        return "auto"
    base = rf"HKLM\SYSTEM\CurrentControlSet\Services\{name}"
    st = reg_get(base, "Start")
    mode = {2: "auto", 3: "demand", 4: "disabled"}.get(st[1]) if st else None
    if mode == "auto":
        d = reg_get(base, "DelayedAutostart")
        if d and d[1] == 1:
            mode = "delayed-auto"
    return mode


def active_scheme() -> str:
    if not IS_WIN:
        return BALANCED
    _, out = run("powercfg /getactivescheme", 10, ro=True)
    m = GUID_RE.search(out)
    return m.group(0).lower() if m else BALANCED


def list_schemes():
    _, out = run("powercfg /list", 10, ro=True)
    res = []
    for line in out.splitlines():
        m = GUID_RE.search(line)
        if m:
            nm = re.search(r"\(([^)]*)\)", line)
            res.append((m.group(0).lower(), nm.group(1) if nm else ""))
    return res


def pw_get(guid: str, sub: str, setting: str, mode: str = "ac"):
    """Поточне значення параметра схеми живлення (від мережі або від батареї) або None."""
    if not IS_WIN:
        return None
    _, out = run(f"powercfg /query {guid} {sub} {setting}", 10, ro=True)
    vals = re.findall(r"0x[0-9a-fA-F]{8}", out)
    if len(vals) < 2:
        return None
    return int(vals[-1] if mode == "dc" else vals[-2], 16)


def ensure_ultimate(log: Optional[Callable] = None):
    """Знаходить або створює схему Ultimate Performance. -> (guid, створено_зараз)."""
    for g, nm in list_schemes():
        if any(w in nm.lower() for w in ("ultimate", "максимальн", "максимальн", "найвищ")):
            return g, False
    rc, out = run(f"powercfg -duplicatescheme {ULTIMATE_TPL}", 15, log)
    m = GUID_RE.search(out)
    if rc == 0 and m:
        return m.group(0).lower(), True
    return HIGH_PERF, False


# ───────────────────────── журнал відкату ─────────────────────────
class JournalError(RuntimeError):
    """Журнал відкату не вдалося записати на диск. Без запису зміну потім не буде як повернути — тож її не робимо."""


def _write_atomic(path: str, data, durable: bool) -> None:
    """Запис через тимчасовий файл: файл на диску — або старий, або новий, але ніколи не наполовину записаний.
    durable — ще й дочекатися фізичного запису (fsync): журнал має пережити вимкнення світла одразу після змін.
    Антивірус, що саме сканує файл, на мить блокує заміну — пробуємо кілька разів."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.flush()
        if durable:
            os.fsync(f.fileno())
    for i in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 5:
                raise
            time.sleep(0.15 * (i + 1))


class Journal:
    """Журнал відкату: для кожної застосованої зміни — що саме було до неї.

    Надійність (6.4):
    • Попередній запис (write-ahead). Перед кожною зміною в системі її запис відкату вже лежить на диску
      (back.pending.json). Якщо OptimaX аварійно закриється посеред оптимізації, під час наступного запуску
      recover_interrupted() поверне саме те, що встигло змінитися, — у системі не лишиться змін без запису.
    • Резервна копія. Попередня версія журналу зберігається як back.json.bak; пошкоджений файл (вимкнули світло
      під час запису) відкладається як back.json.corrupt-<час>, а журнал відновлюється з копії.
    • Помилка запису більше не ігнорується: put() кидає JournalError, і пакет змін зупиняється.
    • Позначка операції ("op"): пакет застосування чи відкату, який не дійшов до кінця, видно після перезапуску."""

    def __init__(self, path: str):
        self.path = path
        self.bak = path + ".bak"
        self.wal = (path[:-5] if path.endswith(".json") else path) + ".pending.json"
        self.lock = threading.RLock()
        self.data = {"applied": {}}
        self.listeners = []  # викликаються після кожного запису (наприклад, оновлення OptimaX-Rescue.cmd)
        self.problem = None  # None | "restored" — відновлено з копії | "lost" — журнал пошкоджено, копії немає
        self.save_error = None
        self._wal = None
        self._load()

    # ── читання й запис ──
    @staticmethod
    def _read(p: str) -> dict:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not (isinstance(d, dict) and isinstance(d.get("applied"), dict)):
            raise ValueError("not an OptimaX journal")
        for tid, e in d["applied"].items():
            if not (isinstance(e, dict) and isinstance(e.get("undo"), list)):
                raise ValueError(f"bad entry {tid}")
        return d

    def _load(self) -> None:
        broken = False
        if os.path.exists(self.path):
            try:
                self.data = self._read(self.path)
                return
            except Exception:
                broken = True
                try:  # пошкоджений файл не перезаписуємо — відкладаємо поруч, щоб його можна було дослідити
                    os.replace(self.path, f"{self.path}.corrupt-{int(time.time())}")
                except OSError:
                    pass
        # основного файлу немає або він зіпсований: аварія між кроками запису — новіша копія в .tmp, інакше .bak
        for p in (self.path + ".tmp", self.bak):
            if not os.path.exists(p):
                continue
            try:
                self.data = self._read(p)
            except Exception:
                continue
            self.problem = "restored"
            self._save()
            return
        if broken:
            self.problem = "lost"

    def _save(self, notify: bool = True) -> bool:
        ok = True
        try:
            if os.path.exists(self.path):  # попередня версія — резервна копія
                try:
                    shutil.copyfile(self.path, self.bak)
                except OSError:
                    pass
            _write_atomic(self.path, self.data, durable=True)
            self.save_error = None
        except Exception as e:
            ok = False
            self.save_error = f"{type(e).__name__}: {e}"
        if notify:
            for cb in list(self.listeners):
                try:
                    cb(self)
                except Exception:
                    pass
        return ok

    # ── записи ──
    def has(self, tid: str) -> bool:
        return tid in self.data["applied"]

    def get(self, tid: str):
        return self.data["applied"].get(tid)

    def put(self, tid: str, undo: list, title: str = None, group: str = None) -> None:
        with self.lock:
            if tid in self.data["applied"]:  # повторне застосування: зберігаємо найперший знімок
                return
            entry = {"ts": int(time.time()), "undo": list(undo)}
            if title:
                entry["title"] = title
            if group:
                entry["group"] = group
            self.data["applied"][tid] = entry
            if not self._save():
                self.data["applied"].pop(tid, None)
                raise JournalError(self.save_error)

    def pop(self, tid: str) -> None:
        with self.lock:
            self.data["applied"].pop(tid, None)
            self._save()

    def replace_undo(self, tid: str, undo: list) -> None:
        """Після часткового відкату лишаємо в журналі лише кроки, які не вдалося повернути."""
        with self.lock:
            e = self.data["applied"].get(tid)
            if e is not None:
                e["undo"] = list(undo)
                e["partial"] = True
                self._save()

    # ── попередній запис (write-ahead) однієї оптимізації ──
    def begin(self, tid: str, title: str = None, group: str = None) -> None:
        with self.lock:
            self._wal = {"tid": tid, "ts": int(time.time()), "title": title, "group": group,
                         "fresh": tid not in self.data["applied"], "undo": []}
            try:
                _write_atomic(self.wal, self._wal, durable=True)
            except Exception as e:
                self._wal = None
                raise JournalError(f"{type(e).__name__}: {e}") from None

    def note(self, undo: list) -> None:
        """Записи відкату поточної оптимізації — на диск до того, як зміна відбудеться. Без fsync: процес, що
        аварійно завершився, файл не втрачає, а від вимкнення світла не вберігає й сам реєстр Windows."""
        with self.lock:
            if self._wal is None:
                return
            self._wal["undo"] = list(undo)
            try:
                _write_atomic(self.wal, self._wal, durable=False)
            except Exception as e:
                raise JournalError(f"{type(e).__name__}: {e}") from None

    def commit(self, tid: str, undo: list, title: str = None, group: str = None) -> None:
        if undo:
            self.put(tid, undo, title, group)
        self.abort()

    def abort(self) -> None:
        with self.lock:
            self._wal = None
            try:
                os.remove(self.wal)
            except OSError:
                pass

    def interrupted(self):
        """Запис оптимізації, застосування якої обірвалося (аварійне завершення), або None."""
        try:
            with open(self.wal, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) and d.get("tid") and isinstance(d.get("undo"), list) else None
        except (OSError, ValueError):
            return None

    # ── позначка пакета (застосування чи відкату), щоб після аварії знати, що він не дійшов до кінця ──
    def begin_op(self, kind: str, ids=(), by: str = "") -> None:
        with self.lock:
            self.data["op"] = {"kind": kind, "ts": int(time.time()), "ids": list(ids)[:500], "by": by}
            if not self._save(notify=False):
                self.data.pop("op", None)
                raise JournalError(self.save_error)

    def end_op(self) -> None:
        with self.lock:
            if self.data.pop("op", None) is not None:
                self._save(notify=False)

    def op(self):
        return self.data.get("op")

    def newest_first(self):
        """Від найновішого до найстарішого. Кілька твіків пакета мають однакову секунду ts — тоді вирішує порядок
        запису (словник його зберігає й у JSON): відкат строго у зворотному порядку, інакше значення, яке змінили
        два твіки, повернеться до проміжного стану, а не до початкового."""
        with self.lock:
            items = list(enumerate(self.data["applied"].items()))
        return [k for _, (k, _) in sorted(items, key=lambda x: (x[1][1].get("ts", 0), x[0]), reverse=True)]

    def count(self) -> int:
        return len(self.data["applied"])


JOURNAL = Journal(JOURNAL_PATH)


class UndoLog(list):
    """Список записів відкату, який після кожного нового запису одразу зберігає його в журнал на диску
    (Journal.note) — ще до того, як операція змінить систему."""

    def __init__(self, on_change: Optional[Callable] = None):
        super().__init__()
        self.on_change = on_change

    def _changed(self) -> None:
        if self.on_change:
            self.on_change(self)

    def append(self, rec) -> None:
        super().append(rec)
        self._changed()

    def insert(self, i, rec) -> None:
        super().insert(i, rec)
        self._changed()

    def extend(self, recs) -> None:
        super().extend(recs)
        self._changed()

    def __iadd__(self, recs):
        super().extend(recs)
        self._changed()
        return self


class Ctx:
    """Контекст виконання: журнал виводу, накопичення записів відкату, знайдене залізо."""

    def __init__(self, log: Callable, journal: Journal = None, hw: dict = None):
        self.log = log
        self.journal = journal or JOURNAL
        self.hw = hw or {}
        self.undo: list = UndoLog()
        self._tasks = False
        self.deferred = None  # множина «живих» оновлень, які виконаємо один раз наприкінці пакета

    def begin(self, track: bool = False) -> None:
        """track — кожен запис відкату одразу потрапляє в попередній запис журналу (Journal.begin/note)."""
        self.undo = UndoLog(self.journal.note if track else None)

    def enabled_tasks(self):
        """Множина ввімкнених задач планувальника (у нижньому регістрі) або None."""
        if self._tasks is False:
            self._tasks = None
            if IS_WIN:
                rc, out = ps("Get-ScheduledTask | Where-Object {$_.State -ne 'Disabled'} | "
                             "ForEach-Object { $_.TaskPath + $_.TaskName }", 90, ro=True)
                names = {ln.strip().lower() for ln in out.splitlines() if ln.strip()}
                if rc == 0 and names:
                    self._tasks = names
        return self._tasks


# ───────────────────────── операції каталогу ─────────────────────────
def R(path, name, value, t="dword"):
    return ("reg", path, name, value, t)


def RD(path, name):
    return ("regdel", path, name)


def S(name, start="disabled"):
    return ("svc", name, start)


def C(cmd, undo=None, timeout=30):
    return ("cmd", cmd, undo, timeout)


def TK(*tasks):
    return ("task", tasks)


def P(setting, value, sub="SUB_PROCESSOR", mode="ac"):
    return ("pw", sub, setting, value, mode)


def F(fn):
    return ("fn", fn)


def D(fn):
    return ("dyn", fn)


def X(kind):
    return ("live", kind)


def FILE(src, dest):
    """Покласти копію src у dest (наприклад, бібліотеку поруч з exe гри). Відкат: прибрати нашу копію і повернути
    файл, що лежав там раніше (його відкладено поруч як <ім'я>.optimax-bak)."""
    return ("file", src, dest)


def file_sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_doc(text: str):
    """Опис дії для панелі «Що саме зміниться»."""
    def deco(fn):
        fn.cmd = text
        return fn
    return deco


def exec_op(op, ctx: Ctx) -> None:
    k, log = op[0], ctx.log
    if k == "reg":
        _, path, name, value, rt = op
        if callable(value):
            value = value()
        old = reg_get(path, name)
        ctx.undo.append({"t": "reg", "p": path, "n": name,
                         "old": None if old is None else [old[0], _enc(old[1])]})
        if DRY_RUN:
            log(f"  [dry-run] reg {path} \\ {name} = {value}")
        else:
            reg_set(path, name, value, rt)
    elif k == "regdel":
        _, path, name = op
        old = reg_get(path, name)
        if old is not None:
            ctx.undo.append({"t": "reg", "p": path, "n": name, "old": [old[0], _enc(old[1])]})
        if DRY_RUN:
            log(f"  [dry-run] reg delete {path} \\ {name}")
        else:
            reg_del_value(path, name)
    elif k == "svc":
        _, name, start = op
        old = svc_get_start(name)
        if old is None:
            log(tr("e.svc_missing", name=name))
            return
        if old == start:
            return
        ctx.undo.append({"t": "svc", "n": name, "old": old})
        if start == "disabled":
            run(f"sc stop {name}", 12, log)
        run(f"sc config {name} start= {start}", 12, log)
        log(f"  [{start.upper()}] {name}")
    elif k == "task":
        en, n = ctx.enabled_tasks(), 0
        for tn in op[1]:
            if en is not None and tn.lower() not in en:
                continue
            rc, _ = run(f'schtasks /Change /Disable /TN "{tn}"', 15, log)
            if rc == 0:
                ctx.undo.append({"t": "task", "n": tn})
                n += 1
        log(tr("e.tasks_disabled", n=n))
    elif k == "cmd":
        _, cmd, undo, to = op
        rc, out = run(cmd, to, log)
        if rc == 3010:  # DISM/MSI: успіх, потрібне перезавантаження
            rc = 0
        if rc == TIMEOUT_RC:
            log(tr("e.slow", cmd=cmd[:60]))
        elif rc != 0:
            log(tr("e.skipped", why=first_line(out, 60) or tr("e.code", rc=rc), cmd=cmd[:55]))
        if undo and rc == 0:
            ctx.undo.append({"t": "cmd", "c": undo})
    elif k == "pw":
        _, sub, setting, value, mode = op
        g = active_scheme()
        old = pw_get(g, sub, setting, mode)
        verb = "-setdcvalueindex" if mode == "dc" else "-setacvalueindex"
        rc, _ = run(f"powercfg {verb} {g} {sub} {setting} {value}", 10, log)
        if rc != 0:
            log(tr("e.pw_na", setting=setting))
            return
        run(f"powercfg -setactive {g}", 10, log)
        if old is not None or DRY_RUN:
            ctx.undo.append({"t": "pw", "g": g, "s": sub, "st": setting, "old": old, "m": mode})
    elif k == "file":
        _, src, dest = op
        sha = file_sha256(src)
        bak = None
        if os.path.exists(dest):
            if file_sha256(dest) == sha:
                return  # там уже такий самий файл — змінювати й повертати нічого
            bak = dest + ".optimax-bak"
            n = 1
            while os.path.exists(bak):
                n += 1
                bak = f"{dest}.optimax-bak{n}"
        ctx.undo.append({"t": "file", "p": dest, "sha": sha, "bak": bak})
        if DRY_RUN:
            log(f"  [dry-run] copy {os.path.basename(src)} → {dest}")
            return
        tmp = dest + ".optimax-tmp"
        if os.path.exists(tmp):  # залишок попередньої спроби, перерваної аварією
            os.remove(tmp)
        if bak:
            os.replace(dest, bak)
        shutil.copyfile(src, tmp)
        os.replace(tmp, dest)
    elif k == "fn":
        op[1](ctx)
    elif k == "dyn":
        for sub_op in op[1](ctx):
            exec_op(sub_op, ctx)
    elif k == "live":
        if ctx.deferred is not None and op[1] == "explorer":
            ctx.deferred.add(op[1])
        else:
            live_refresh(op[1], log)
        if not any(r.get("t") == "live" and r.get("k") == op[1] for r in ctx.undo):
            ctx.undo.insert(0, {"t": "live", "k": op[1]})  # під час відкату виконається останнім


def _undo_record(rec: dict, log: Callable, deferred: set = None) -> None:
    t = rec["t"]
    if t == "live" and deferred is not None and rec.get("k") == "explorer":
        deferred.add("explorer")
        return
    if DRY_RUN:
        what = rec.get("p") or rec.get("n") or rec.get("c") or rec.get("st") or rec.get("k") or ""
        log(f"  [dry-run] undo {t}: {str(what)[:100]}")
        return
    if t == "reg":
        if rec["old"] is None:
            reg_del_value(rec["p"], rec["n"])
        else:
            reg_set(rec["p"], rec["n"], _dec(rec["old"][1]), rec["old"][0])
    elif t == "svc":
        rc, out = run(f"sc config {rec['n']} start= {rec['old']}", 15, log)
        if rc not in (0, 1060):  # 1060 — служби вже немає: повертати нічого
            raise RuntimeError(f"sc config {rec['n']}: {first_line(out, 70) or rc}")
    elif t == "task":
        run(f'schtasks /Change /Enable /TN "{rec["n"]}"', 15, log)
    elif t == "cmd":
        run(rec["c"], 1800, log)
    elif t == "ps":
        ps(rec["c"], 120, log)
    elif t == "pw":
        if rec.get("old") is None:
            return
        verb = "-setdcvalueindex" if rec.get("m") == "dc" else "-setacvalueindex"
        run(f"powercfg {verb} {rec['g']} {rec['s']} {rec['st']} {rec['old']}", 10, log)
        if active_scheme() == rec["g"]:
            run(f"powercfg -setactive {rec['g']}", 10, log)
    elif t == "live":
        live_refresh(rec["k"], log)
    elif t == "file":
        _undo_file(rec, log)


def _undo_file(rec: dict, log: Callable) -> None:
    path, bak = rec["p"], rec.get("bak")
    tmp = path + ".optimax-tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    if os.path.exists(path):
        if rec.get("sha") and file_sha256(path) != rec["sha"]:
            # файл уже не наш: гра оновилася й поклала свій. Його не чіпаємо, а відкладена нами стара версія файлу
            # гри більше не потрібна — прибираємо, щоб не лишалася в папці гри без жодного запису
            log(tr("e.file_changed", path=path))
            if bak and os.path.exists(bak):
                os.remove(bak)
            return
        os.remove(path)  # гра запущена й тримає бібліотеку — помилка, запис лишиться в журналі до наступної спроби
    if bak and os.path.exists(bak):
        os.replace(bak, path)


def _rollback(records: list, log: Callable, deferred: set = None) -> list:
    """Виконує записи відкату від останнього до першого. -> записи, які повернути не вдалося (у початковому порядку)."""
    failed = []
    for rec in reversed(list(records)):
        try:
            _undo_record(rec, log, deferred)
        except Exception as e:
            log(f"  ⚠ {type(e).__name__}: {e}")
            failed.append(rec)
    return list(reversed(failed))


def undo_one(tid: str, log: Callable, deferred: set = None):
    """-> True — повернуто; "partial" — частину кроків повернути не вдалося (вони лишаються в журналі, щоб
    повторити відкат пізніше або через OptimaX-Rescue.cmd); False — у журналі немає такого запису."""
    entry = JOURNAL.get(tid)
    if not entry:
        return False
    failed = _rollback(entry["undo"], log, deferred)
    if failed:
        JOURNAL.replace_undo(tid, failed)
        return "partial"
    JOURNAL.pop(tid)
    return True


# ───────────────────────── Explorer і миттєве застосування ─────────────────────────
def explorer_start(log=None) -> None:
    if DRY_RUN:
        return
    for _ in range(8):  # Windows сама перезапускає оболонку за секунду-дві
        time.sleep(0.5)
        _, out = run('tasklist /fi "imagename eq explorer.exe" /nh', 8, ro=True)
        if "explorer.exe" in out.lower():
            return
    subprocess.Popen(["explorer.exe"], creationflags=CREATE_NO_WINDOW)


def restart_explorer(log=None) -> None:
    run("taskkill /f /im explorer.exe", 10, log)
    explorer_start(log)


def _apply_syscolors() -> None:
    idx, cols = [], []
    for name, i in (("Hilight", 13), ("HilightText", 14), ("HotTrackingColor", 26)):
        v = reg_get(r"HKCU\Control Panel\Colors", name)
        if v:
            try:
                r, g, b = [int(x) for x in str(v[1]).split()[:3]]
                idx.append(i)
                cols.append(r | (g << 8) | (b << 16))
            except ValueError:
                pass
    if idx:
        ctypes.windll.user32.SetSysColors(len(idx), (ctypes.c_int * len(idx))(*idx),
                                          (ctypes.c_ulong * len(cols))(*cols))


def _apply_mouse() -> None:
    def g(n, d):
        v = reg_get(r"HKCU\Control Panel\Mouse", n)
        try:
            return int(v[1]) if v else d
        except (ValueError, TypeError):
            return d
    u = ctypes.windll.user32
    u.SystemParametersInfoW(0x0004, 0, (ctypes.c_int * 3)(g("MouseThreshold1", 6), g("MouseThreshold2", 10),
                                                         g("MouseSpeed", 1)), 3)
    u.SystemParametersInfoW(0x0071, 0, ctypes.c_void_p(g("MouseSensitivity", 10)), 3)


def _apply_keyboard() -> None:
    def g(n, d):
        v = reg_get(r"HKCU\Control Panel\Keyboard", n)
        try:
            return int(v[1]) if v else d
        except (ValueError, TypeError):
            return d
    u = ctypes.windll.user32
    u.SystemParametersInfoW(0x0017, g("KeyboardDelay", 1), None, 3)  # SPI_SETKEYBOARDDELAY
    u.SystemParametersInfoW(0x000B, g("KeyboardSpeed", 31), None, 3)  # SPI_SETKEYBOARDSPEED


def live_refresh(kind: str, log=None) -> None:
    """Застосувати зміну одразу, без виходу з системи."""
    if DRY_RUN:
        if log:
            log(f"  [dry-run] refresh: {kind}")
        return
    try:
        u = ctypes.windll.user32
        if kind == "explorer":
            restart_explorer(log)
        elif kind == "broadcast":
            res = ctypes.c_ulong(0)
            u.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "ImmersiveColorSet", 2, 3000, ctypes.byref(res))
        elif kind == "env":  # змінні середовища користувача: Провідник і нові програми побачать їх без виходу
            res = ctypes.c_ulong(0)
            u.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 3000, ctypes.byref(res))
        elif kind == "syscolor":
            _apply_syscolors()
        elif kind == "mouse":
            _apply_mouse()
        elif kind == "keyboard":
            _apply_keyboard()
        elif kind == "anim":
            cur = reg_get(r"HKCU\Control Panel\Desktop\WindowMetrics", "MinAnimate")
            on = 0 if (cur and str(cur[1]) == "0") else 1
            u.SystemParametersInfoW(0x0049, 8, (ctypes.c_uint * 2)(8, on), 3)
    except Exception as e:
        if log:
            log(f"  ⚠ refresh {kind}: {e}")


# ───────────────────────── низькорівневі помічники ─────────────────────────
class MEMSTAT(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_ulong), ("HighPart", ctypes.c_long)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", ctypes.c_ulong)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", ctypes.c_ulong), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong), ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong), ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_wchar * 260)]


def mem_status() -> MEMSTAT:
    s = MEMSTAT()
    s.dwLength = ctypes.sizeof(s)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return s


_PRIV_DONE = set()


def enable_privilege(name: str) -> bool:
    if not IS_WIN:
        return True
    if name in _PRIV_DONE:
        return True
    k32, adv = ctypes.windll.kernel32, ctypes.windll.advapi32
    h = ctypes.c_void_p
    k32.GetCurrentProcess.restype = h
    adv.OpenProcessToken.argtypes = [h, ctypes.c_ulong, ctypes.POINTER(h)]
    adv.AdjustTokenPrivileges.argtypes = [h, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                                          ctypes.c_void_p]
    token = h()
    if not adv.OpenProcessToken(k32.GetCurrentProcess(), 0x28, ctypes.byref(token)):
        return False
    luid = LUID()
    if not adv.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
        return False
    tp = TOKEN_PRIVILEGES(1, (LUID_AND_ATTRIBUTES * 1)(LUID_AND_ATTRIBUTES(luid, 2)))
    adv.AdjustTokenPrivileges(token, 0, ctypes.byref(tp), 0, None, None)
    ok = k32.GetLastError() == 0
    if ok:
        _PRIV_DONE.add(name)
    return ok


DEMO_PROCS = ["System", "explorer.exe", "OneDrive.exe", "steam.exe", "Discord.exe", "chrome.exe",
              "MicrosoftEdgeUpdate.exe", "Widgets.exe", "svchost.exe"]


def processes() -> list:
    """-> [(pid, ім'я exe)]"""
    if not IS_WIN:
        return [(1000 + i, n) for i, n in enumerate(DEMO_PROCS)]
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        return []
    e = PROCESSENTRY32W()
    e.dwSize = ctypes.sizeof(e)
    res = []
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        res.append((e.th32ProcessID, e.szExeFile))
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return res


def process_path(pid: int):
    if not IS_WIN:
        return None
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p,
                                               ctypes.POINTER(ctypes.c_ulong)]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    h = k32.OpenProcess(0x1000, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        k32.CloseHandle(h)
    return None


def clean_dir(path: str) -> int:
    """Видаляє вміст папки (зайняті файли пропускає). -> звільнено байтів."""
    freed = 0
    if not path or not os.path.isdir(path):
        return 0
    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            fp = os.path.join(root, f)
            try:
                sz = os.path.getsize(fp)
                os.remove(fp)
                freed += sz
            except OSError:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass
    return freed


def _env(p: str) -> str:
    return os.path.expandvars(p)


def set_timer_resolution(on: bool) -> bool:
    """Точність системного таймера 0.5 мс, поки процес OptimaX працює."""
    if not IS_WIN or DRY_RUN:
        return True
    cur = ctypes.c_ulong(0)
    return ctypes.windll.ntdll.NtSetTimerResolution(5000, 1 if on else 0, ctypes.byref(cur)) == 0


def _nt_memory_command(cmd: int) -> int:
    nt = ctypes.windll.ntdll
    nt.NtSetSystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    nt.NtSetSystemInformation.restype = ctypes.c_long
    v = ctypes.c_int(cmd)
    return nt.NtSetSystemInformation(80, ctypes.byref(v), 4)


def purge_standby() -> bool:
    """Очищення standby-списку пам'яті (як ISLC/RAMMap). Робочі набори процесів не чіпає."""
    if not IS_WIN or DRY_RUN:
        return True
    enable_privilege("SeProfileSingleProcessPrivilege")
    return _nt_memory_command(4) == 0


# ───────────────────────── складні дії ─────────────────────────
@cmd_doc("powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61; powercfg -setactive <guid>")
def f_ultimate(ctx: Ctx) -> None:
    log = ctx.log
    if DRY_RUN:
        log("  [dry-run] powercfg: Ultimate Performance")
        ctx.undo.append({"t": "cmd", "c": f"powercfg -setactive {BALANCED}"})
        return
    old = active_scheme()
    new, created = ensure_ultimate(log)
    if new == HIGH_PERF:
        log(tr("e.plan_fallback"))
    rc, out = run(f"powercfg -setactive {new}", 15, log)
    if rc != 0:
        log(tr("e.plan_fail", msg=first_line(out)))
        return
    if created:
        ctx.undo.append({"t": "cmd", "c": f"powercfg -delete {new}"})
    ctx.undo.append({"t": "cmd", "c": f"powercfg -setactive {old}"})
    log(tr("e.plan_active", guid=new))


@cmd_doc("NtSetTimerResolution(5000)")
def f_hold_timer(ctx: Ctx) -> None:
    ctx.log(tr("e.timer_ok") if set_timer_resolution(True) else tr("e.timer_fail"))


PF_APPLY = r"""
$cs = Get-CimInstance Win32_ComputerSystem
if ($cs.AutomaticManagedPagefile) { Set-CimInstance -InputObject $cs -Property @{AutomaticManagedPagefile=$false} }
$name = "$env:SystemDrive\pagefile.sys"
$pf = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -ieq $name }
if (-not $pf) { $pf = New-CimInstance -ClassName Win32_PageFileSetting -Property @{Name=$name} }
Set-CimInstance -InputObject $pf -Property @{InitialSize=[uint32]4096; MaximumSize=[uint32]8192}
"""
PF_UNDO = r"""
Get-CimInstance Win32_PageFileSetting | Remove-CimInstance
$cs = Get-CimInstance Win32_ComputerSystem
Set-CimInstance -InputObject $cs -Property @{AutomaticManagedPagefile=$true}
"""


@cmd_doc("Win32_PageFileSetting: InitialSize=4096, MaximumSize=8192")
def f_pagefile(ctx: Ctx) -> None:
    if DRY_RUN:
        ctx.log("  [dry-run] pagefile 4096-8192 MB")
        ctx.undo.append({"t": "ps", "c": PF_UNDO})
        return
    _, out = ps("(Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile", 20, ro=True)
    was_auto = out.strip().lower() == "true"
    rc, out = ps(PF_APPLY, 45)
    if rc != 0:
        ctx.log(f"  ⚠ pagefile: {first_line(out)}")
    if was_auto:
        ctx.undo.append({"t": "ps", "c": PF_UNDO})
    else:
        ctx.log(tr("e.pf_manual"))


@cmd_doc("Set-MpPreference -DisableRealtimeMonitoring $true")
def f_defender(ctx: Ctx) -> None:
    rc, _ = ps("Set-MpPreference -DisableRealtimeMonitoring $true", 25, ctx.log)
    if rc != 0:
        ctx.log(tr("e.tamper"))
    ctx.undo.append({"t": "ps", "c": "Set-MpPreference -DisableRealtimeMonitoring $false"})


@cmd_doc("Set-MpPreference -ScanAvgCPULoadFactor 20 -EnableLowCpuPriority $true -ScanOnlyIfIdleEnabled $true")
def f_defender_limit(ctx: Ctx) -> None:
    old = ps_json("$p=Get-MpPreference; @{a=$p.ScanAvgCPULoadFactor; b=$p.EnableLowCpuPriority; "
                  "c=$p.ScanOnlyIfIdleEnabled} | ConvertTo-Json -Compress", 30) or {}
    a = int(old.get("a") or 50)
    b = "$true" if old.get("b") else "$false"
    c = "$false" if old.get("c") is False else "$true"
    ps("Set-MpPreference -ScanAvgCPULoadFactor 20 -EnableLowCpuPriority $true -ScanOnlyIfIdleEnabled $true",
       30, ctx.log)
    ctx.undo.append({"t": "ps", "c": f"Set-MpPreference -ScanAvgCPULoadFactor {a} -EnableLowCpuPriority {b} "
                                     f"-ScanOnlyIfIdleEnabled {c}"})


@cmd_doc("winget uninstall Microsoft.OneDrive / OneDriveSetup.exe /uninstall")
def f_onedrive(ctx: Ctx) -> None:
    log = ctx.log
    run("taskkill /f /im OneDrive.exe", 8, log)
    if not DRY_RUN:
        time.sleep(1)
    rc, _ = run("winget uninstall --id Microsoft.OneDrive --silent --accept-source-agreements", 120, log)
    if rc == 0:
        log(tr("e.od_winget"))
    else:
        log(tr("e.od_classic"))
        for exe in (r"%SystemRoot%\SysWOW64\OneDriveSetup.exe", r"%SystemRoot%\System32\OneDriveSetup.exe"):
            run(f'"{exe}" /uninstall', 60, log)
        ps("Get-AppxPackage *OneDrive* | Remove-AppxPackage -ErrorAction SilentlyContinue", 90, log)
    ctx.undo.append({"t": "cmd", "c": "winget install -e --id Microsoft.OneDrive --silent "
                                      "--accept-package-agreements --accept-source-agreements"})


# Лише служби Windows, без яких система й залізо точно працюють. Версія 6.3 додавала сюди ще всі служби з
# автозапуском, які не працювали в мить застосування. На ноутбуках серед них бувають службові програми виробника
# (клавіатура, клавіші Fn, тачпад), і після перезавантаження ті переставали працювати. SharedAccess (спільний доступ
# до інтернету) теж прибрано: без нього не працює мобільна точка доступу.
FORCE_OFF = ["DiagTrack", "dmwappushservice", "WMPNetworkSvc", "RemoteRegistry", "Fax", "WerSvc", "PcaSvc",
             "wercplsupport", "MapsBroker", "lfsvc", "RetailDemo", "TrkWks", "WalletService", "PhoneSvc",
             "SmsRouter"]


@cmd_doc("sc config " + " ".join(FORCE_OFF) + " start= disabled")
def f_services(ctx: Ctx) -> None:
    for name in FORCE_OFF:
        exec_op(S(name, "disabled"), ctx)


# Зміни, які робили старіші версії і які тепер вважаються шкідливими: (твік, чи цей запис журналу треба відкотити).
LEGACY_FIXES = [
    # 6.3: службові програми виробника ноутбука (клавіатура, Fn, тачпад), SharedAccess (мобільна точка доступу)
    ("disable_services", lambda u: u.get("t") == "svc" and u.get("n") not in FORCE_OFF),
    # до 6.3.2: очищення файлу підкачки під час кожного вимкнення — вимкнення й перезавантаження ставали повільними
    ("optimize_pagefile", lambda u: u.get("t") == "reg" and u.get("n") == "ClearPageFileAtShutdown"),
    # до 6.3.2: завдання, яке налаштовує мобільний інтернет (LTE) на ноутбуках
    ("disable_spy_tasks", lambda u: u.get("t") == "task" and str(u.get("n", "")).endswith("\\Provisioning\\Cellular")),
]


def legacy_to_repair() -> list:
    """-> [(id твіку, запис журналу)], які треба повернути до початкового стану."""
    out = []
    for tid, bad in LEGACY_FIXES:
        rec = JOURNAL.get(tid) or {}
        out += [(tid, u) for u in rec.get("undo", []) if bad(u)]
    return out


def repair_legacy(log: Callable) -> dict:
    """Повертає ці записи до початкового стану з журналу і прибирає їх із нього — решта змін користувача лишається."""
    todo, done = legacy_to_repair(), []
    for tid, u in todo:
        log(f"  · {tid}: {u.get('n') or u.get('p')} → {u.get('old', '')}")
        try:
            _undo_record(u, log)
            done.append((tid, u))
        except Exception as e:  # не вдалося — запис лишається в журналі, спробуємо під час наступного запуску
            log(f"  ⚠ {type(e).__name__}: {e}")
    todo = done
    with JOURNAL.lock:
        for tid in {t for t, _ in todo}:
            rec = JOURNAL.get(tid)
            if rec is None:
                continue
            rec["undo"] = [u for u in rec.get("undo", []) if all(u is not b for t, b in todo if t == tid)]
            if rec["undo"]:
                JOURNAL._save()
            else:
                JOURNAL.pop(tid)
    return {"ok": True, "n": len(todo)}


TCP_IFACES = r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"


@cmd_doc(r"Tcpip\Parameters\Interfaces\<GUID>: TcpAckFrequency=1, TCPNoDelay=1, TcpDelAckTicks=0")
def dyn_nagle(ctx: Ctx):
    guids = reg_subkeys(TCP_IFACES) if IS_WIN else ["{interface-guid}"]
    ctx.log(tr("e.ifaces", n=len(guids)))
    ops = []
    for g in guids:
        for n, v in (("TcpAckFrequency", 1), ("TCPNoDelay", 1), ("TcpDelAckTicks", 0)):
            ops.append(R(TCP_IFACES + "\\" + g, n, v))
    return ops


GPU_CLASS = r"HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
ENUM_ROOT = r"HKLM\SYSTEM\CurrentControlSet\Enum"
MSI_SUB = r"Device Parameters\Interrupt Management\MessageSignaledInterruptProperties"


def msi_key(instance_id: str) -> str:
    return f"{ENUM_ROOT}\\{instance_id}\\{MSI_SUB}"


def pnp_devices(classes=("Display",)) -> list:
    """Присутні PCI-пристрої: [{'id', 'name', 'cls'}]. Лише читання."""
    if not IS_WIN:
        demo = {"Display": ("PCI\\VEN_10DE&DEV_2786\\4&1", "NVIDIA GeForce RTX 4070"),
                "Net": ("PCI\\VEN_8086&DEV_15F3\\3&2", "Intel(R) Ethernet Controller I225-V"),
                "USB": ("PCI\\VEN_8086&DEV_7AE0\\3&3", "Intel(R) USB 3.20 eXtensible Host Controller"),
                "SCSIAdapter": ("PCI\\VEN_144D&DEV_A80A\\4&4", "Standard NVM Express Controller"),
                "MEDIA": ("PCI\\VEN_10DE&DEV_22BC\\4&5", "NVIDIA High Definition Audio")}
        return [{"id": demo[c][0], "name": demo[c][1], "cls": c} for c in classes if c in demo]
    cls = ",".join(f"'{c}'" for c in classes)
    data = ps_json(f"Get-PnpDevice -PresentOnly -Class {cls} -ErrorAction SilentlyContinue | "
                   "Where-Object { $_.InstanceId -like 'PCI\\*' } | "
                   "Select-Object @{n='id';e={$_.InstanceId}}, @{n='name';e={$_.FriendlyName}}, "
                   "@{n='cls';e={$_.Class}} | ConvertTo-Json -Compress", 40)
    return [d for d in as_list(data) if isinstance(d, dict) and d.get("id")]


@cmd_doc(r"Enum\PCI\<GPU>\...\MessageSignaledInterruptProperties: MSISupported=1")
def dyn_msi_gpu(ctx: Ctx):
    return [R(msi_key(d["id"]), "MSISupported", 1) for d in pnp_devices(("Display",))]


@cmd_doc(r"Class\{4d36e968-...}\000X: EnableUlps=0")
def dyn_amd_ulps(ctx: Ctx):
    if not IS_WIN:
        return [R(GPU_CLASS + r"\0000", "EnableUlps", 0)]
    ops = []
    for sub in reg_subkeys(GPU_CLASS):
        if not sub.isdigit():
            continue
        prov = reg_get(GPU_CLASS + "\\" + sub, "ProviderName")
        desc = reg_get(GPU_CLASS + "\\" + sub, "DriverDesc")
        text = f"{prov[1] if prov else ''} {desc[1] if desc else ''}".lower()
        if "amd" in text or "ati " in text or "radeon" in text:
            ops.append(R(GPU_CLASS + "\\" + sub, "EnableUlps", 0))
    return ops


NV_TASK_MASKS = ("NvTmRep", "NvTmMon", "NvProfileUpdater", "NvDriverUpdateCheck", "NvNodeLauncher")


@cmd_doc("NvTelemetryContainer → disabled; schtasks NvTmRep*/NvTmMon*/NvProfileUpdater* → disabled")
def dyn_nvidia_tasks(ctx: Ctx):
    if not IS_WIN:
        return [TK(r"\NvTmRep_CrashReport1_{demo}")]
    cond = " -or ".join(f"$_.TaskName -like '{m}*'" for m in NV_TASK_MASKS)
    rc, out = ps(f"Get-ScheduledTask | Where-Object {{ {cond} }} | ForEach-Object {{ $_.TaskPath + $_.TaskName }}",
                 40, ro=True)
    names = [x.strip() for x in out.splitlines() if x.strip()]
    return [TK(*names)] if names else []


PREFETCH_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters"


@cmd_doc("SSD: SysMain → disabled;  HDD: SysMain → auto, EnablePrefetcher=3")
def dyn_sysmain(ctx: Ctx):
    if ctx.hw.get("ssd"):
        return [S("SysMain", "disabled")]
    return [S("SysMain", "auto"), R(PREFETCH_KEY, "EnablePrefetcher", 3)]


DX_PREF = r"HKCU\Software\Microsoft\DirectX\UserGpuPreferences"


def _merge_kv(old: str, key: str, value: str) -> str:
    parts = [p for p in (old or "").split(";") if p and not p.startswith(key + "=")]
    parts.append(f"{key}={value}")
    return ";".join(parts) + ";"


@cmd_doc(r"DirectX\UserGpuPreferences: DirectXUserGlobalSettings += SwapEffectUpgradeEnable=1")
def dyn_windowed(ctx: Ctx):
    cur = reg_get(DX_PREF, "DirectXUserGlobalSettings")
    return [R(DX_PREF, "DirectXUserGlobalSettings", _merge_kv(cur[1] if cur else "", "SwapEffectUpgradeEnable", "1"),
              "sz")]


NIC_KEYWORDS = ("*EEE", "EEELinkAdvertisement", "AdvancedEEE", "EnableGreenEthernet", "GreenEthernet",
                "PowerSavingMode", "ULPMode", "*SelectiveSuspend")


def _psq(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


@cmd_doc("Set-NetAdapterPowerManagement -AllowComputerToTurnOffDevice Disabled; "
         "Set-NetAdapterAdvancedProperty *EEE / GreenEthernet / PowerSavingMode = 0")
def f_nic_power(ctx: Ctx) -> None:
    kws = ",".join(_psq(k) for k in NIC_KEYWORDS)
    script = (
        "$r=@(); foreach ($a in Get-NetAdapter -Physical -ErrorAction SilentlyContinue) {"
        " $pm = Get-NetAdapterPowerManagement -Name $a.Name -ErrorAction SilentlyContinue;"
        " if ($pm -and [string]$pm.AllowComputerToTurnOffDevice -ne 'Unsupported') {"
        "  $r += @{n=$a.Name; k='__pm'; v=[string]$pm.AllowComputerToTurnOffDevice};"
        "  Set-NetAdapterPowerManagement -Name $a.Name -AllowComputerToTurnOffDevice Disabled -NoRestart "
        "-ErrorAction SilentlyContinue }"
        f" foreach ($kw in @({kws})) {{"
        "  $p = Get-NetAdapterAdvancedProperty -Name $a.Name -RegistryKeyword $kw -ErrorAction SilentlyContinue;"
        "  if ($p) { $r += @{n=$a.Name; k=$kw; v=($p.RegistryValue -join ',')};"
        "   Set-NetAdapterAdvancedProperty -Name $a.Name -RegistryKeyword $kw -RegistryValue 0 -NoRestart "
        "-ErrorAction SilentlyContinue } } }; $r | ConvertTo-Json -Compress")
    if DRY_RUN:
        ps(script, 60, ctx.log)
        ctx.undo.append({"t": "ps", "c": "# restore adapter power settings"})
        return
    rc, out = ps(script, 90)
    try:
        saved = as_list(json.loads(out)) if out.strip() else []
    except Exception:
        saved = []
    lines = []
    for s in saved:
        if not isinstance(s, dict):
            continue
        if s.get("k") == "__pm":
            lines.append(f"Set-NetAdapterPowerManagement -Name {_psq(s['n'])} -AllowComputerToTurnOffDevice "
                         f"{_psq(s['v'])} -NoRestart -ErrorAction SilentlyContinue")
        else:
            lines.append(f"Set-NetAdapterAdvancedProperty -Name {_psq(s['n'])} -RegistryKeyword {_psq(s['k'])} "
                         f"-RegistryValue {_psq(s['v'])} -NoRestart -ErrorAction SilentlyContinue")
    ctx.log(tr("e.nic_done", n=len(saved)))
    if lines:
        ctx.undo.append({"t": "ps", "c": "; ".join(lines)})


WIFI_FILTER = ("$_.NdisPhysicalMedium -eq 9 -or $_.InterfaceDescription -match "
               "'Wi-?Fi|Wireless|WLAN|802\\.11|Killer.*AX|Centrino'")
ETH_FILTER = "$_.NdisPhysicalMedium -eq 14 -and $_.InterfaceDescription -notmatch 'Wi-?Fi|Wireless|WLAN|802\\.11'"


def _nic_props(ctx: Ctx, media_filter: str, prop_filter: str, target: str) -> None:
    """Змінює додаткові властивості фізичних адаптерів і запам'ятовує попередні значення.
    target — PowerShell-вираз нового значення для властивості $p (порожній результат = пропустити)."""
    script = (
        "$r=@(); foreach ($a in Get-NetAdapter -Physical -ErrorAction SilentlyContinue | "
        f"Where-Object {{ {media_filter} }}) {{"
        " foreach ($p in Get-NetAdapterAdvancedProperty -Name $a.Name -AllProperties -ErrorAction SilentlyContinue |"
        f"  Where-Object {{ {prop_filter} }}) {{"
        f"  $v = {target};"
        "  if ($v -ne $null -and [string]$v -ne ($p.RegistryValue -join ',')) {"
        "   $r += @{n=$a.Name; k=$p.RegistryKeyword; v=($p.RegistryValue -join ',')};"
        "   Set-NetAdapterAdvancedProperty -Name $a.Name -RegistryKeyword $p.RegistryKeyword -RegistryValue $v "
        "-NoRestart -ErrorAction SilentlyContinue } } }; $r | ConvertTo-Json -Compress")
    if DRY_RUN:
        ps(script, 60, ctx.log)
        ctx.undo.append({"t": "ps", "c": "# restore adapter properties"})
        return
    rc, out = ps(script, 90)
    try:
        saved = as_list(json.loads(out)) if out.strip() else []
    except Exception:
        saved = []
    lines = [f"Set-NetAdapterAdvancedProperty -Name {_psq(s['n'])} -RegistryKeyword {_psq(s['k'])} "
             f"-RegistryValue {_psq(s['v'])} -NoRestart -ErrorAction SilentlyContinue"
             for s in saved if isinstance(s, dict) and s.get("k")]
    ctx.log(tr("e.nic_done", n=len(lines)))
    if lines:
        ctx.undo.append({"t": "ps", "c": "; ".join(lines)})


@cmd_doc("Wi-Fi: Roaming Aggressiveness → найнижче значення (адаптер менше шукає інші точки доступу)")
def f_wifi_gaming(ctx: Ctx) -> None:
    _nic_props(ctx, WIFI_FILTER,
               "$_.RegistryKeyword -match 'Roam' -and $_.DisplayName -match 'Aggress|Sensitiv|Roam'",
               "($p.ValidRegistryValues | Where-Object { $_ -match '^\\d+$' } | ForEach-Object { [int]$_ } | "
               "Measure-Object -Minimum).Minimum")


@cmd_doc("Ethernet: *InterruptModeration = 0, *FlowControl = 0")
def f_eth_latency(ctx: Ctx) -> None:
    _nic_props(ctx, ETH_FILTER, "$_.RegistryKeyword -in @('*InterruptModeration','*FlowControl')",
               "$(if (-not $p.ValidRegistryValues -or $p.ValidRegistryValues -contains '0') { '0' })")


@cmd_doc("Get-MMAgent: 32+ ГБ → Disable-MMAgent -MemoryCompression; до 12 ГБ → Enable-MMAgent -MemoryCompression")
def f_memory_compression(ctx: Ctx) -> None:
    ram = float(ctx.hw.get("ram_gb") or 0)
    if not ram and IS_WIN:
        try:
            ram = mem_status().ullTotalPhys / 2**30
        except Exception:
            ram = 16.0
    want = False if ram >= 30 else True if ram <= 12.5 else None
    if want is None:
        ctx.log(tr("e.mc_keep", gb=f"{ram:.0f}"))
        return
    if IS_WIN:
        _, cur = ps("(Get-MMAgent).MemoryCompression", 20, ro=True)
        if cur.strip().lower() == str(want).lower():
            ctx.log(tr("e.mc_already", state=tr("e.on" if want else "e.off")))
            return
    verb, back = ("Enable", "Disable") if want else ("Disable", "Enable")
    ps(f"{verb}-MMAgent -MemoryCompression", 40, ctx.log)
    ctx.undo.append({"t": "ps", "c": f"{back}-MMAgent -MemoryCompression"})
    ctx.log(tr("e.mc_set", gb=f"{ram:.0f}", state=tr("e.on" if want else "e.off")))


MMD_RENDER = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
FX_DISABLE = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"  # PKEY_AudioEndpoint_Disable_SysFx


@cmd_doc(r"MMDevices\Audio\Render\<пристрій>\FxProperties: {1da5d803-…},5 = 1; перезапуск Audiosrv")
def f_audio_fx(ctx: Ctx) -> None:
    log = ctx.log
    if not IS_WIN:
        log(f"  [dry-run] reg {MMD_RENDER}\\<device>\\FxProperties \\ {FX_DISABLE} = 1")
        ctx.undo.append({"t": "reg", "p": MMD_RENDER + r"\{demo}\FxProperties", "n": FX_DISABLE, "old": None})
        return
    n = denied = 0
    for dev in reg_subkeys(MMD_RENDER):
        st = reg_get(f"{MMD_RENDER}\\{dev}", "DeviceState")
        if not st or st[1] != 1:  # лише активні пристрої
            continue
        path = f"{MMD_RENDER}\\{dev}\\FxProperties"
        old = reg_get(path, FX_DISABLE)
        if old and old[1] == 1:
            continue
        if DRY_RUN:
            log(f"  [dry-run] reg {path} \\ {FX_DISABLE} = 1")
            n += 1
            continue
        try:
            reg_set(path, FX_DISABLE, 1, "dword")
            ctx.undo.append({"t": "reg", "p": path, "n": FX_DISABLE,
                             "old": None if old is None else [old[0], _enc(old[1])]})
            n += 1
        except OSError:
            denied += 1
    log(tr("e.audio_fx", n=n))
    if denied:
        log(tr("e.audio_denied", n=denied))
    if n:
        run("net stop Audiosrv /y", 30, log)
        run("net start Audiosrv", 30, log)


def _dx_merge(key: str, value: str):
    @cmd_doc(rf"DirectX\UserGpuPreferences: DirectXUserGlobalSettings += {key}={value}")
    def _dyn(ctx: Ctx):
        cur = reg_get(DX_PREF, "DirectXUserGlobalSettings")
        return [R(DX_PREF, "DirectXUserGlobalSettings", _merge_kv(cur[1] if cur else "", key, value), "sz")]
    return _dyn


def _utc_iso(days: int = 0) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wu_now() -> str:
    return _utc_iso(0)


def _wu_pause_end() -> str:
    return _utc_iso(35)


def _display_version() -> str:
    v = reg_get(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion", "DisplayVersion")
    if v and v[1]:
        return str(v[1])
    b = win_build()
    return "25H2" if b >= 26200 else "24H2" if b >= 26100 else "23H2" if b >= 22631 else "22H2"


def _product_version() -> str:
    return "Windows 11" if win_build() >= 22000 else "Windows 10"


@cmd_doc("NtSetSystemInformation: MemoryFlushModifiedList + MemoryPurgeStandbyList")
def f_memory_clean(ctx: Ctx) -> None:
    log = ctx.log
    if DRY_RUN:
        log("  [dry-run] NtSetSystemInformation(MemoryPurgeStandbyList)")
        return
    before = mem_status().ullAvailPhys
    if not enable_privilege("SeProfileSingleProcessPrivilege"):
        log(tr("e.no_priv", p="SeProfileSingleProcessPrivilege"))
    codes = [_nt_memory_command(3), _nt_memory_command(4)]
    after = mem_status().ullAvailPhys
    if all(c == 0 for c in codes):
        log(tr("e.ram_freed", a=f"{before / 2**30:.1f}", b=f"{after / 2**30:.1f}"))
    else:
        log(tr("e.nt_fail", codes=codes))


@cmd_doc("chkdsk C: /f")
def f_chkdsk(ctx: Ctx) -> None:
    drive = os.environ.get("SystemDrive", "C:")
    run(f"chkdsk {drive} /f", 25, ctx.log, input_text="Y\n")
    ctx.log(tr("e.chkdsk"))


@cmd_doc("pnputil /scan-devices")
def f_clean_invalid(ctx: Ctx) -> None:
    run(r'reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist" /f', 10, ctx.log)
    run("pnputil /scan-devices", 30, ctx.log)


@cmd_doc("Get-PnpDevice | Where Status -ne OK")
def f_fix_drivers(ctx: Ctx) -> None:
    _, out = ps("Get-PnpDevice | Where-Object {$_.Status -ne 'OK'} | Select-Object Name,Status | "
                "Format-Table -AutoSize | Out-String -Width 120", 40, ro=True)
    ctx.log(out if out.strip() else tr("e.devices_ok"))


REG_JUNK = [
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs",
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU",
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths",
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist",
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\ComDlg32\LastVisitedPidlMRU",
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\ComDlg32\OpenSavePidlMRU",
    r"HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags",
    r"HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU",
]


@cmd_doc("reg delete RecentDocs, RunMRU, TypedPaths, UserAssist, ComDlg32 MRU, ShellBags")
def f_clean_registry(ctx: Ctx) -> None:
    for key in REG_JUNK:
        run(f'reg delete "{key}" /f', 10, ctx.log)


@cmd_doc("TEMP, Windows\\Temp, SoftwareDistribution\\Download, Edge cache")
def f_clean_junk(ctx: Ctx) -> None:
    # Без Prefetch: Windows за ним швидше запускає програми, після видалення все стартує повільніше, доки не
    # збере його знову. Без wsreset (відкриває вікно Store) і DISM (на ноутбуці з HDD — до години): прибирання
    # WinSxS тепер окрема дія «Прибрати старі копії оновлень» у розділі «Очищення».
    log, freed = ctx.log, 0
    if DRY_RUN:
        log("  [dry-run] TEMP, Windows\\Temp, SoftwareDistribution\\Download, Edge")
        return
    for p in (os.environ.get("TEMP"), _env(r"%SystemRoot%\Temp")):
        freed += clean_dir(p)
    run("ie4uinit.exe -ClearIconCache", 15, log)
    log(tr("e.wu_cache"))
    for s in ("wuauserv", "bits"):
        run(f"net stop {s}", 25, log)
    freed += clean_dir(_env(r"%SystemRoot%\SoftwareDistribution\Download"))
    for s in ("wuauserv", "bits"):
        run(f"net start {s}", 25, log)
    log(tr("e.edge_cache"))
    for sub in ("Cache", "Code Cache", "GPUCache"):
        freed += clean_dir(os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                        "Microsoft", "Edge", "User Data", "Default", sub))
    log(tr("e.freed_mb", mb=f"{freed / 2**20:.0f}"))


POWER_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\Power"


@cmd_doc("powercfg -h off (відкат умикає гібернацію, лише якщо вона була ввімкнена до OptimaX)")
def f_hibernation_off(ctx: Ctx) -> None:
    """Раніше відкат завжди робив «powercfg -h on» — навіть якщо гібернацію ви вимкнули самі: після відкату
    з'являвся файл hiberfil.sys на кілька гігабайтів."""
    cur = reg_get(POWER_KEY, "HibernateEnabled")
    hiberfil = os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "hiberfil.sys")
    # гібернація справді ввімкнена лише тоді, коли є hiberfil.sys: на віртуальних машинах і ПК без підтримки S4
    # HibernateEnabled буває 1, а «powercfg -h on» потім не спрацює
    if (cur is not None and not cur[1]) or (IS_WIN and not os.path.exists(hiberfil)):
        ctx.log(tr("e.hib_off_already"))
        return
    rc, out = run("powercfg -h off", 30, ctx.log)
    if rc == 0:
        ctx.undo.append({"t": "cmd", "c": "powercfg -h on"})
    else:
        ctx.log(tr("e.skipped", why=first_line(out, 60) or tr("e.code", rc=rc), cmd="powercfg -h off"))


def a_clean_winsxs(ctx: Ctx) -> None:
    """Старі копії оновлень Windows (WinSxS). Довго, але можна зупинити будь-коли: Windows сама обриває це
    прибирання за розкладом через годину і потім продовжує."""
    ctx.log(tr("e.winsxs"))
    stream("dism /online /cleanup-image /startcomponentcleanup", ctx.log, _pct_parser("DISM"), 3600)


@cmd_doc("ipconfig /flushdns; netsh winsock reset catalog; netsh int ip reset")
def f_dns_winsock(ctx: Ctx) -> None:
    for c in ("ipconfig /flushdns", "ipconfig /registerdns", "netsh winsock reset catalog", "netsh int ip reset"):
        run(c, 25, ctx.log)


def f_appx(pkgs):
    @cmd_doc("Get-AppxPackage " + ", ".join(pkgs) + " | Remove-AppxPackage")
    def _f(ctx: Ctx) -> None:
        for pkg in pkgs:
            ctx.log(f"  · {pkg}")
            rc, _ = ps(f"Get-AppxPackage *{pkg}* | Remove-AppxPackage", 70, ctx.log)
            if rc == TIMEOUT_RC:
                ctx.log(tr("e.timeout_pkg", pkg=pkg))
    return _f


# ───────────────────────── каталог оптимізацій ─────────────────────────
@dataclass
class Tweak:
    id: str
    group: str
    ops: list = field(default_factory=list)
    off: list = field(default_factory=list)  # відкат за замовчуванням, якщо в журналі нічого немає
    p: str = ""  # профілі: F, M, L, T (ноутбук), O (старий ПК), X (Xeon/сервер)
    impact: str = "safe"  # safe — безпечно; medium — помірно; habits — впливає на звички
    reboot: bool = False
    relogin: bool = False
    long: bool = False
    risky: str = ""  # ключ попередження
    needs: str = ""  # ключ заліза, без якого твік недоступний
    warn_on: tuple = ()  # ключі заліза, на яких твік працює, але з попередженням
    block_on: tuple = ()  # ключі заліза, на яких твік шкодить і заблокований
    conflicts: tuple = ()
    win11: bool = False
    win10: bool = False  # лише для Windows 10 (у Windows 11 цих елементів немає)
    min_build: int = 0  # найстаріша збірка Windows 10, де цей параметр існує
    reversible: bool = True
    custom: bool = False
    _title: str = ""
    _desc: str = ""

    @property
    def title(self) -> str:
        return self._title or tweak_text(self.id)[0]

    @property
    def desc(self) -> str:
        return self._desc or tweak_text(self.id)[1]

    def badges(self):
        b = []
        if self.reboot:
            b.append((tr("b.reboot"), "muted"))
        if self.relogin:
            b.append((tr("b.relogin"), "muted"))
        if self.long:
            b.append((tr("b.long"), "muted"))
        if self.win11:
            b.append(("Windows 11", "muted"))
        if self.win10:
            b.append(("Windows 10", "muted"))
        if self.risky:
            b.append((tr(f"risk.{self.risky}"), "bad"))
        return b


TWEAKS: list = []


def tw(id_, group, ops=None, **kw) -> Tweak:
    t = Tweak(id_, group, ops or [], **kw)
    TWEAKS.append(t)
    return t


GROUP_IDS = ["perf", "gaming", "hw", "net", "laptop", "lite", "ai", "privacy", "explorer", "wu", "audio", "system",
             "svc", "space", "maint", "metro"]

SP = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
MM = r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
PRIO = r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl"
TCPIP = r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
DNSC = r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters"
EXPL = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer"
ADV = EXPL + r"\Advanced"
PERS = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
POL = r"HKLM\SOFTWARE\Policies\Microsoft\Windows"
GCS = r"HKCU\System\GameConfigStore"
DESK = r"HKCU\Control Panel\Desktop"
USB_SUB, USB_SET = "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"
WIFI_SUB, WIFI_SET = "19cbb8fa-5279-450e-9fac-8a3d5fedd0c1", "12bbebe6-58d6-4636-95bb-3217ef867c1a"
NONE_SUB, STANDBY_NET = "fea3413e-7e05-4911-9a71-700331f1c294", "f15576e8-98b7-4186-b944-eafa664402d9"
X3D = ("x3d_dual",)
LAP = ("laptop",)

# ── Продуктивність процесора і пам'яті ──
tw("ultimate_power", "perf", [F(f_ultimate)], off=[C(f"powercfg -setactive {BALANCED}")], p="FMX",
   warn_on=LAP, block_on=X3D, min_build=17134)
tw("processor_idle", "perf", [P("IDLEDISABLE", 1)], p="FX", impact="medium", warn_on=LAP, block_on=X3D)
tw("core_parking", "perf", [P("CPMINCORES", 100), P("CPMAXCORES", 100)], p="FMX", warn_on=LAP + ("hybrid",),
   block_on=X3D)
tw("power_throttling", "perf", [R(r"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling",
                                  "PowerThrottlingOff", 1), P("PROCTHROTTLEMAX", 100)], p="FMX", warn_on=LAP)
tw("turbo_aggressive", "perf", [P("PERFBOOSTMODE", 2)], p="FX", warn_on=LAP, conflicts=("cool_mode",))
tw("min_cpu_state", "perf", [P("PROCTHROTTLEMIN", 100)], p="X", impact="medium", warn_on=LAP)
tw("lock_power", "perf", [R(r"HKLM\SOFTWARE\Policies\Microsoft\Power\PowerSettings", "ActivePowerScheme",
                            active_scheme, "sz")], p="FMX", block_on=LAP)
tw("cpu_scheduling", "perf", [R(PRIO, "Win32PrioritySeparation", 38),
                              R(SP + r"\Tasks\Games", "Scheduling Category", "High", "sz")], p="FM", win11=True)
tw("rt_boost", "perf", [R(SP, "SystemResponsiveness", 0), R(PRIO, "Win32PrioritySeparation", 0x26)], p="FMX")
tw("system_responsiveness", "perf", [R(SP, "SystemResponsiveness", 0), R(SP + r"\Tasks\Games", "GPU Priority", 8),
                                     R(SP + r"\Tasks\Games", "Priority", 6),
                                     R(SP + r"\Tasks\Games", "Scheduling Category", "High", "sz"),
                                     R(SP + r"\Tasks\Games", "SFIO Priority", "High", "sz")], p="FMX")
tw("registry_boost", "perf", [R(MM, "IoPageLockLimit", 0xFFFFFFFF), R(MM, "DisablePagingExecutive", 1)],
   p="FMX", reboot=True)
tw("optimize_pagefile", "perf", [F(f_pagefile)], p="FMX", reboot=True)
tw("memory_compression", "perf", [F(f_memory_compression)], p="FMTOX", reboot=True)
tw("spectre_off", "perf", [R(MM, "FeatureSettingsOverride", 3), R(MM, "FeatureSettingsOverrideMask", 3)],
   reboot=True, impact="habits", risky="security")

# ── Ігри ──
tw("gpu_hw_scheduling", "gaming", [R(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2)],
   p="FM", reboot=True, min_build=19041, block_on=("mining_gpu",))
tw("game_mode_on", "gaming", [R(r"HKCU\Software\Microsoft\GameBar", "AllowAutoGameMode", 1),
                              R(r"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled", 1)], p="FMLTOX")
tw("disable_xbox_gamebar", "gaming", [R(GCS, "GameDVR_Enabled", 0), R(POL + r"\GameDVR", "AllowGameDVR", 0),
                                      R(r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR",
                                        "AppCaptureEnabled", 0),
                                      R(r"HKCU\SOFTWARE\Microsoft\GameBar", "UseNexusForGameBarEnabled", 0),
                                      S("XblGameSave"), S("XboxNetApiSvc")], p="FMX", impact="habits",
   block_on=X3D)
tw("fso_global", "gaming", [R(GCS, "GameDVR_FSEBehaviorMode", 2), R(GCS, "GameDVR_HonorUserFSEBehaviorMode", 1),
                            R(GCS, "GameDVR_FSEBehavior", 2), R(GCS, "GameDVR_DXGIHonorFSEWindowsCompatible", 1)],
   p="FX", impact="medium", block_on=("mining_display",))  # справжній повноекранний режим — лише на карті з монітором
tw("windowed_opt", "gaming", [D(dyn_windowed)], p="FMX", win11=True)
tw("timer_resolution", "gaming", [R(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
                                    "GlobalTimerResolutionRequests", 1),
                                  C("bcdedit /set disabledynamictick yes", "bcdedit /deletevalue disabledynamictick"),
                                  F(f_hold_timer)], p="FMX", reboot=True)
tw("dynamic_tick", "gaming", [C("bcdedit /set disabledynamictick yes", "bcdedit /deletevalue disabledynamictick")],
   p="FMX", reboot=True)
tw("hpet_tsc", "gaming", [C("bcdedit /set useplatformclock true", "bcdedit /deletevalue useplatformclock"),
                          C("bcdedit /set tscsyncpolicy Enhanced", "bcdedit /deletevalue tscsyncpolicy")],
   reboot=True, impact="medium", risky="fps")
tw("disable_mouse_accel", "gaming", [R(r"HKCU\Control Panel\Mouse", "MouseSpeed", "0", "sz"),
                                     R(r"HKCU\Control Panel\Mouse", "MouseThreshold1", "0", "sz"),
                                     R(r"HKCU\Control Panel\Mouse", "MouseThreshold2", "0", "sz"),
                                     R(r"HKCU\Control Panel\Mouse", "MouseSensitivity", "10", "sz"), X("mouse")],
   p="FMLOX", impact="medium")
tw("vrr_windowed", "gaming", [D(_dx_merge("VRROptimizeEnable", "1"))], p="FMX", win11=True)
tw("auto_hdr", "gaming", [D(_dx_merge("AutoHDREnable", "1"))], win11=True, impact="medium")
KBD = r"HKCU\Control Panel\Keyboard"
tw("keyboard_fast", "gaming", [R(KBD, "KeyboardDelay", "0", "sz"), R(KBD, "KeyboardSpeed", "31", "sz"), X("keyboard")],
   off=[R(KBD, "KeyboardDelay", "1", "sz"), R(KBD, "KeyboardSpeed", "31", "sz"), X("keyboard")], p="F",
   impact="medium")

# ── Залізо і драйвери ──
tw("hybrid_cores", "hw", [P("SCHEDPOLICY", 2), P("SHORTSCHEDPOLICY", 2), P("CPMINCORES1", 100)], p="FMT",
   needs="hybrid")
tw("msi_gpu", "hw", [D(dyn_msi_gpu)], p="F", reboot=True, impact="medium")
tw("nvidia_telemetry", "hw", [S("NvTelemetryContainer"), D(dyn_nvidia_tasks),
                              R(r"HKLM\SOFTWARE\NVIDIA Corporation\NvControlPanel2\Client", "OptInOrOutPreference", 0),
                              R(r"HKLM\SOFTWARE\NVIDIA Corporation\Global\FTS", "EnableRID44231", 0),
                              R(r"HKLM\SOFTWARE\NVIDIA Corporation\Global\FTS", "EnableRID64640", 0),
                              R(r"HKLM\SOFTWARE\NVIDIA Corporation\Global\FTS", "EnableRID66610", 0)],
   p="FMLTOX", needs="nvidia")
tw("amd_ulps", "hw", [D(dyn_amd_ulps)], p="FMX", needs="amd_gpu", reboot=True)
tw("disable_vbs", "hw", [R(r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard",
                           "EnableVirtualizationBasedSecurity", 0),
                         R(r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios"
                           r"\HypervisorEnforcedCodeIntegrity", "Enabled", 0)],
   p="F", reboot=True, impact="habits", risky="security")
tw("pcie_aspm", "hw", [P("ASPM", 0, "SUB_PCIEXPRESS")], p="FMX", warn_on=LAP)
tw("usb_suspend", "hw", [P(USB_SET, 0, USB_SUB)], p="FMTX")

# ── Мережа ──
tw("optimize_network", "net", [R(TCPIP, "TCPNoDelay", 1), R(TCPIP, "TcpAckFrequency", 1),
                               R(DNSC, "CacheHashTableBucketSize", 1), R(DNSC, "CacheHashTableSize", 384),
                               R(DNSC, "MaxCacheEntryTtlLimit", 64000), R(DNSC, "MaxSOACacheEntryTtlLimit", 301),
                               C("netsh int tcp set global autotuninglevel=normal",
                                 "netsh int tcp set global autotuninglevel=normal"),
                               C("netsh int tcp set global dca=enabled", "netsh int tcp set global dca=default"),
                               C("netsh int tcp set global ecncapability=disabled",
                                 "netsh int tcp set global ecncapability=default"),
                               C("netsh int tcp set global rss=enabled", "netsh int tcp set global rss=enabled"),
                               C("ipconfig /flushdns")], p="FMTX", reboot=True)
tw("disable_nagle", "net", [D(dyn_nagle)], p="FMX")
tw("network_stack_boost", "net", [
    C("netsh int tcp set global autotuninglevel=normal", "netsh int tcp set global autotuninglevel=normal"),
    C("netsh int tcp set global rss=enabled", "netsh int tcp set global rss=enabled"),
    C("netsh int tcp set global dca=enabled", "netsh int tcp set global dca=default"),
    C("netsh int tcp set heuristics disabled", "netsh int tcp set heuristics enabled")], p="FMX")
tw("network_throttling", "net", [R(SP, "NetworkThrottlingIndex", 0xFFFFFFFF)], p="FMTX")
tw("network_packet_opt", "net", [
    C("netsh int tcp set supplemental template=internet congestionprovider=ctcp",
      "netsh int tcp set supplemental template=internet congestionprovider=default"),
    C("netsh int tcp set global ecncapability=disabled", "netsh int tcp set global ecncapability=default")], p="FMX")
tw("nic_power", "net", [F(f_nic_power), P(WIFI_SET, 0, WIFI_SUB)], p="FMTOX", reboot=True)
tw("delivery_p2p", "net", [R(POL + r"\DeliveryOptimization", "DODownloadMode", 0)], p="FMLTOX")
tw("dns_winsock", "net", [F(f_dns_winsock)], reversible=False, reboot=True, impact="habits")
tw("wifi_gaming", "net", [F(f_wifi_gaming)], p="FM", needs="wifi", warn_on=LAP, reboot=True)
tw("ethernet_latency", "net", [F(f_eth_latency)], p="F", needs="ethernet", reboot=True, impact="medium")

# ── Ноутбук ──
tw("laptop_ac_max", "laptop", [P("PERFEPP", 0), P("PERFBOOSTMODE", 2)], p="T", needs="battery",
   conflicts=("cool_mode",))
tw("laptop_dc_save", "laptop", [P("PERFBOOSTMODE", 0, mode="dc"), P("PERFEPP", 80, mode="dc"),
                                P("ESBATTTHRESHOLD", 30, "SUB_ENERGYSAVER", "dc")], p="TO", needs="battery")
tw("cool_mode", "laptop", [P("PERFBOOSTMODE", 0), P("PERFBOOSTMODE", 0, mode="dc"), P("SYSCOOLPOL", 1),
                           P("SYSCOOLPOL", 1, mode="dc")], impact="medium",
   conflicts=("laptop_ac_max", "turbo_aggressive"))
tw("standby_net_off", "laptop", [P(STANDBY_NET, 0, NONE_SUB, "dc")], p="TO", needs="modern_standby")
tw("wake_timers_off", "laptop", [P("RTCWAKE", 0, "SUB_SLEEP", "dc")], p="TO", needs="battery")
tw("s3_sleep", "laptop", [R(r"HKLM\SYSTEM\CurrentControlSet\Control\Power", "PlatformAoAcOverride", 0)],
   off=[RD(r"HKLM\SYSTEM\CurrentControlSet\Control\Power", "PlatformAoAcOverride")], needs="modern_standby",
   reboot=True, impact="medium")

# ── Легкість для слабких і старих ПК ──
VFX = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
tw("visual_fx_perf", "lite", [R(VFX, "VisualFXSetting", 2),
                              R(DESK, "UserPreferencesMask", bytes.fromhex("9012038010000000"), "bin"),
                              R(DESK + r"\WindowMetrics", "MinAnimate", "0", "sz"), R(DESK, "FontSmoothing", "2", "sz"),
                              R(ADV, "TaskbarAnimations", 0), R(ADV, "ListviewAlphaSelect", 0),
                              R(ADV, "ListviewShadow", 0), R(r"HKCU\Software\Microsoft\Windows\DWM", "EnableAeroPeek", 0),
                              X("anim")], p="O", relogin=True, impact="habits")
tw("transparency_off", "lite", [R(PERS, "EnableTransparency", 0), X("broadcast")], p="O", impact="habits")
tw("bg_apps_off", "lite", [R(r"HKCU\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                             "GlobalUserDisabled", 1),
                           R(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Search", "BackgroundAppGlobalToggle", 0),
                           R(POL + r"\AppPrivacy", "LetAppsRunInBackground", 2)], p="TO", impact="habits")
tw("widgets_off", "lite", [R(r"HKLM\SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", 0),
                           R(POL + r"\Windows Feeds", "EnableFeeds", 0)], p="FMLTOX", relogin=True, impact="medium")
tw("edge_bg_off", "lite", [R(r"HKLM\SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", 0),
                           R(r"HKLM\SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", 0)], p="FMLTOX")
tw("sysmain_smart", "lite", [D(dyn_sysmain)], p="FMTOX")
tw("defender_limit", "lite", [F(f_defender_limit)], p="MLTOX", conflicts=("disable_defender",))
tw("startup_delay", "lite", [R(EXPL + r"\Serialize", "StartupDelayInMSec", 0),
                             R(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon", "SyncForegroundPolicy",
                               0)],
   off=[RD(EXPL + r"\Serialize", "StartupDelayInMSec"),
        RD(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon", "SyncForegroundPolicy")], p="FMLTOX")
# Через реєстр, а не fsutil: fsutil пише ті самі значення, але відкат «set … 2» повертав стандартне значення,
# а не ваше (якщо ви вже вимикали це вручну, відкат умикав назад). Тепер журнал повертає точне початкове значення.
FS_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\FileSystem"
tw("ntfs_lastaccess", "lite", [R(FS_KEY, "NtfsDisableLastAccessUpdate", 1)], p="O", reboot=True)
tw("ntfs_8dot3", "lite", [R(FS_KEY, "NtfsDisable8dot3NameCreation", 1)], p="O", reboot=True)
tw("w10_news_off", "lite", [R(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Feeds", "ShellFeedsTaskbarViewMode", 2),
                            X("explorer")], p="FMLTOX", win10=True)
tw("w10_cortana_off", "lite", [R(ADV, "ShowCortanaButton", 0), R(POL + r"\Windows Search", "AllowCortana", 0),
                               X("explorer")], p="FMLTOX", win10=True)
tw("w10_ink_off", "lite", [R(r"HKLM\SOFTWARE\Policies\Microsoft\WindowsInkWorkspace", "AllowWindowsInkWorkspace", 0)],
   p="FMOX", win10=True)
tw("w10_meetnow_off", "lite", [R(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer",
                                 "HideSCAMeetNow", 1), X("explorer")], p="FMLTOX", win10=True)

# ── Windows 11: AI і реклама ──
HPOL = r"HKCU\Software\Policies\Microsoft\Windows"
WAI = POL + r"\WindowsAI"
PAINT = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Paint"
EDGE = r"HKLM\SOFTWARE\Policies\Microsoft\Edge"
CDM = r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
tw("ai_copilot", "ai", [R(HPOL + r"\WindowsCopilot", "TurnOffWindowsCopilot", 1),
                        R(POL + r"\WindowsCopilot", "TurnOffWindowsCopilot", 1), R(ADV, "ShowCopilotButton", 0)],
   p="FMLTOX", win11=True, impact="habits")
tw("ai_recall", "ai", [R(WAI, "AllowRecallEnablement", 0), R(WAI, "DisableAIDataAnalysis", 1),
                       R(HPOL + r"\WindowsAI", "DisableAIDataAnalysis", 1),
                       C("DISM /Online /Disable-Feature /FeatureName:Recall /NoRestart",
                         "DISM /Online /Enable-Feature /FeatureName:Recall /NoRestart", 240)],
   p="FMLTOX", win11=True, reboot=True, impact="medium")
tw("ai_click_to_do", "ai", [R(WAI, "DisableClickToDo", 1), R(HPOL + r"\WindowsAI", "DisableClickToDo", 1)],
   p="FMLTOX", win11=True, impact="medium")
tw("ai_apps", "ai", [R(PAINT, "DisableCocreator", 1), R(PAINT, "DisableGenerativeFill", 1),
                     R(PAINT, "DisableImageCreator", 1),
                     R(r"HKLM\SOFTWARE\Policies\WindowsNotepad", "DisableAIFeatures", 1),
                     R(WAI, "DisableSettingsAgent", 1)], p="FMLTOX", win11=True, impact="medium")
tw("ai_edge", "ai", [R(EDGE, "HubsSidebarEnabled", 0), R(EDGE, "Microsoft365CopilotChatIconEnabled", 0),
                     R(EDGE, "CopilotPageContext", 0), R(EDGE, "ComposeInlineEnabled", 0)], p="FMLTOX",
   impact="medium")
tw("ads_start", "ai", [R(ADV, "Start_IrisRecommendations", 0), R(ADV, "Start_AccountNotifications", 0)],
   p="FMLTOX", win11=True)
tw("ads_tips", "ai", [R(CDM, n, 0) for n in ("SubscribedContent-338388Enabled", "SubscribedContent-338389Enabled",
                                             "SubscribedContent-310093Enabled", "SubscribedContent-338393Enabled",
                                             "SubscribedContent-353694Enabled", "SubscribedContent-353696Enabled",
                                             "SystemPaneSuggestionsEnabled", "SilentInstalledAppsEnabled",
                                             "SoftLandingEnabled")]
   + [R(POL + r"\CloudContent", "DisableWindowsConsumerFeatures", 1)], p="FMLTOX")
tw("ads_explorer", "ai", [R(ADV, "ShowSyncProviderNotifications", 0)], p="FMLTOX")
tw("ads_setup_nag", "ai", [R(r"HKCU\Software\Microsoft\Windows\CurrentVersion\UserProfileEngagement",
                             "ScoobeSystemSettingEnabled", 0)], p="FMLTOX")
tw("ads_lockscreen", "ai", [R(CDM, "RotatingLockScreenOverlayEnabled", 0), R(CDM, "SubscribedContent-338387Enabled", 0)],
   p="FMLTOX")
tw("search_no_bing", "ai", [R(HPOL + r"\Explorer", "DisableSearchBoxSuggestions", 1),
                            R(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", 0),
                            X("explorer")], p="FMLTOX", relogin=True, impact="medium")

# ── Конфіденційність ──
tw("disable_telemetry", "privacy", [R(POL + r"\DataCollection", "AllowTelemetry", 0),
                                    R(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
                                      "AllowTelemetry", 0), S("DiagTrack"), S("dmwappushservice"),
                                    R(r"HKCU\SOFTWARE\Microsoft\Input\TIPC", "Enabled", 0),
                                    R(r"HKLM\SOFTWARE\Policies\Microsoft\InputPersonalization",
                                      "AllowInputPersonalization", 0),
                                    R(r"HKCU\SOFTWARE\Microsoft\InputPersonalization",
                                      "RestrictImplicitTextCollection", 1),
                                    R(r"HKCU\SOFTWARE\Microsoft\InputPersonalization",
                                      "RestrictImplicitInkCollection", 1)], p="FMLTOX")
tw("disable_privacy", "privacy", [R(r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0),
                                  R(POL + r"\AdvertisingInfo", "DisabledByGroupPolicy", 1),
                                  R(r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Privacy",
                                    "TailoredExperiencesWithDiagnosticDataEnabled", 0),
                                  R(r"HKCU\SOFTWARE\Microsoft\Personalization\Settings", "AcceptedPrivacyPolicy", 0),
                                  R(POL + r"\Windows Search", "AllowCortana", 0)], p="FMLTOX")
TELEMETRY_TASKS = [
    r"\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
    r"\Microsoft\Windows\Application Experience\ProgramDataUpdater",
    r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
    r"\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
    r"\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector",
    r"\Microsoft\Windows\Feedback\Siuf\DmClient",
    r"\Microsoft\Windows\Feedback\Siuf\DmClientOnScenarioDownload",
    r"\Microsoft\Windows\Windows Error Reporting\QueueReporting",
    r"\Microsoft\Windows\CloudExperienceHost\CreateObjectTask",
    r"\Microsoft\Windows\Autochk\Proxy",
    r"\Microsoft\Windows\NetTrace\GatherNetworkInfo",
    r"\Microsoft\Windows\Diagnosis\Scheduled",
    r"\Microsoft\Windows\WindowsAI\CreateSuggestionIndex",
    r"\Microsoft\Windows\Recall\AutoIndexRecall",
]
SPY_TASKS = [
    r"\Microsoft\Windows\Maps\MapsToastTask", r"\Microsoft\Windows\Maps\MapsUpdateTask",
    r"\Microsoft\Windows\Shell\FamilySafetyMonitor", r"\Microsoft\Windows\Shell\FamilySafetyRefreshTask",
    r"\Microsoft\Windows\Location\Notifications", r"\Microsoft\Windows\Location\WindowsActionDialog",
    r"\Microsoft\Windows\BrokerInfrastructure\BrokerTask",
]
tw("disable_telemetry_tasks", "privacy", [TK(*TELEMETRY_TASKS)], p="FMLTOX")
tw("disable_spy_tasks", "privacy", [TK(*SPY_TASKS)], p="FMTOX", impact="medium")

# ── Провідник і панель завдань ──
CLS86 = r"HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
BLOCKED = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked"
BAGS_ALL = r"HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags\AllFolders\Shell"
CTX_JUNK = ["{e2bf9676-5f8f-435c-97eb-11607a5bedf7}",  # Поділитися
            "{f81e9010-6ea4-11ce-a7ff-00aa003ca9f6}",  # Надати доступ
            "{596AB062-B4D2-4215-9F74-E9109B0A8153}",  # Відновити попередню версію
            "{7AD84985-87B4-4a16-BE58-8B72A5B390F7}",  # Передати на пристрій
            "{CB3B0003-8088-4EDE-8769-8B354AB2FF8C}"]  # Запитати Copilot
tw("classic_context", "explorer", [C(f'reg add "{CLS86}\\InprocServer32" /f /ve', f'reg delete "{CLS86}" /f'),
                                   X("explorer")], off=[C(f'reg delete "{CLS86}" /f'), X("explorer")], win11=True,
   impact="medium")
tw("taskbar_end_task", "explorer", [R(ADV + r"\TaskbarDeveloperSettings", "TaskbarEndTask", 1)], win11=True)
tw("explorer_this_pc", "explorer", [R(ADV, "LaunchTo", 1)], impact="medium")
tw("explorer_fast_folders", "explorer", [R(BAGS_ALL, "FolderType", "NotSpecified", "sz"), X("explorer")],
   p="FMLTOX")
tw("explorer_no_gallery", "explorer", [R(r"HKCU\Software\Classes\CLSID\{e88865ea-0e1c-4e20-9aa6-edcd0212c87c}",
                                         "System.IsPinnedToNameSpaceTree", 0), X("explorer")], win11=True)
tw("explorer_no_recent", "explorer", [R(EXPL, "ShowRecent", 0), R(EXPL, "ShowFrequent", 0), X("explorer")],
   impact="medium")
tw("ctx_menu_clean", "explorer", [R(BLOCKED, c, "", "sz") for c in CTX_JUNK] + [X("explorer")], impact="medium")

# ── Оновлення Windows під контролем ──
WUPOL = POL + r"\WindowsUpdate"
WUX = r"HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
tw("wu_no_drivers", "wu", [R(WUPOL, "ExcludeWUDriversInQualityUpdate", 1),
                           R(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\DriverSearching", "SearchOrderConfig", 0)],
   p="FMX", impact="medium")
tw("wu_no_auto_reboot", "wu", [R(WUPOL + r"\AU", "NoAutoRebootWithLoggedOnUsers", 1)], p="FMLTOX")
tw("wu_pause", "wu", [R(WUX, "PauseUpdatesExpiryTime", _wu_pause_end, "sz"),
                      R(WUX, "PauseFeatureUpdatesStartTime", _wu_now, "sz"),
                      R(WUX, "PauseFeatureUpdatesEndTime", _wu_pause_end, "sz"),
                      R(WUX, "PauseQualityUpdatesStartTime", _wu_now, "sz"),
                      R(WUX, "PauseQualityUpdatesEndTime", _wu_pause_end, "sz")], impact="habits")
tw("wu_lock_version", "wu", [R(WUPOL, "TargetReleaseVersion", 1), R(WUPOL, "ProductVersion", _product_version, "sz"),
                             R(WUPOL, "TargetReleaseVersionInfo", _display_version, "sz")], impact="medium")

# ── Звук ──
tw("audio_fx_off", "audio", [F(f_audio_fx)], p="FM", impact="medium")
tw("audio_no_ducking", "audio", [R(r"HKCU\Software\Microsoft\Multimedia\Audio", "UserDuckingPreference", 3)],
   p="FMLTOX")

# ── Система ──
DEF = r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender"
tw("disable_defender", "system", [R(DEF, "DisableAntiSpyware", 1),
                                  R(DEF + r"\Real-Time Protection", "DisableRealtimeMonitoring", 1),
                                  R(DEF + r"\Real-Time Protection", "DisableBehaviorMonitoring", 1),
                                  R(DEF + r"\Real-Time Protection", "DisableOnAccessProtection", 1),
                                  R(DEF + r"\Real-Time Protection", "DisableIOAVProtection", 1), F(f_defender)],
   reboot=True, risky="danger", impact="habits", conflicts=("defender_limit",))
tw("remove_onedrive", "system", [F(f_onedrive), R(POL + r"\OneDrive", "DisableFileSyncNGSC", 1),
                                 R(POL + r"\OneDrive", "DisableLibrariesDefaultSaveToOneDrive", 1),
                                 RD(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "OneDrive"),
                                 R(r"HKCU\Software\Classes\CLSID\{018D5C66-4533-4307-9B53-224DE2ED1FE6}",
                                   "System.IsPinnedToNameSpaceTree", 0)], risky="removes", impact="habits")
tw("fast_startup_off", "system", [R(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power",
                                    "HiberbootEnabled", 0)],
   off=[R(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled", 1)], p="FMX")
PV = r"HKLM\SOFTWARE\Microsoft\Windows Photo Viewer\Capabilities"
tw("set_photo_viewer", "system", [R(PV, "ApplicationName", r"@%ProgramFiles%\Windows Photo Viewer\photoviewer.dll,-3009",
                                    "sz"),
                                  R(PV, "ApplicationDescription",
                                    r"@%ProgramFiles%\Windows Photo Viewer\photoviewer.dll,-3069", "sz"),
                                  R(r"HKLM\SOFTWARE\RegisteredApplications", "Windows Photo Viewer",
                                    r"SOFTWARE\Microsoft\Windows Photo Viewer\Capabilities", "sz")]
   + [R(PV + r"\FileAssociations", ext, "PhotoViewer.FileAssoc.Tiff", "sz")
      for ext in (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff")], p="FMLTOX")

# ── Служби ──
tw("disable_services", "svc", [F(f_services)], p="FMOX", impact="medium")
tw("disable_search_index", "svc", [S("WSearch")], p="FMTOX", impact="habits")

# ── Місце на диску ──
tw("compact_os", "space", [C("compact /compactos:always", "compact /compactos:never", 3600)], p="O", long=True)
tw("hibernation_off", "space", [F(f_hibernation_off)], p="O", warn_on=LAP, impact="habits")
tw("reserved_storage_off", "space", [C("DISM /Online /Set-ReservedStorageState /State:Disabled",
                                       "DISM /Online /Set-ReservedStorageState /State:Enabled", 180)], p="O",
   min_build=19041)

# ── Обслуговування (разові дії) ──
tw("memory_clean", "maint", [F(f_memory_clean)], p="FMLTOX", reversible=False)
tw("fix_errors", "maint", [F(f_chkdsk)], reversible=False, reboot=True)
tw("clean_invalid", "maint", [F(f_clean_invalid)], reversible=False)
tw("fix_drivers", "maint", [F(f_fix_drivers)], reversible=False)
tw("clean_registry", "maint", [F(f_clean_registry)], p="FMLTOX", reversible=False)
tw("clean_junk", "maint", [F(f_clean_junk)], p="FMLTOX", reversible=False)

# ── Metro-додатки ──
METRO = [
    ("remove_3dbuilder", ["Microsoft.3DBuilder"]),
    ("remove_camera", ["Microsoft.WindowsCamera"]),
    ("remove_mail", ["Microsoft.windowscommunicationsapps", "Microsoft.WindowsMaps"]),
    ("remove_money", ["Microsoft.BingFinance", "Microsoft.BingSports"]),
    ("remove_groove", ["Microsoft.ZuneMusic", "Microsoft.ZuneVideo"]),
    ("remove_people", ["Microsoft.People", "Microsoft.Office.OneNote"]),
    ("remove_phone", ["Microsoft.WindowsPhone", "Microsoft.Windows.Photos"]),
    ("remove_solitaire", ["Microsoft.MicrosoftSolitaireCollection"]),
    ("remove_voice", ["Microsoft.WindowsSoundRecorder"]),
    ("remove_xbox", ["Microsoft.XboxApp", "Microsoft.XboxGameOverlay", "Microsoft.XboxGamingOverlay",
                     "Microsoft.XboxIdentityProvider", "Microsoft.Xbox.TCUI", "Microsoft.XboxSpeechToTextOverlay"]),
    # Windows 11
    ("remove_clipchamp", ["Clipchamp.Clipchamp"]),
    ("remove_news", ["Microsoft.BingNews", "Microsoft.BingWeather", "Microsoft.BingSearch"]),
    ("remove_teams", ["MSTeams", "MicrosoftTeams"]),
    ("remove_outlook", ["Microsoft.OutlookForWindows"]),
    ("remove_devhome", ["Microsoft.Windows.DevHome"]),
    ("remove_todo", ["Microsoft.Todos"]),
    ("remove_family", ["MicrosoftCorporationII.MicrosoftFamily"]),
    ("remove_copilot", ["Microsoft.Copilot"]),
    ("remove_quickassist", ["MicrosoftCorporationII.QuickAssist"]),
    ("remove_feedback", ["Microsoft.WindowsFeedbackHub"]),
    ("remove_tips", ["Microsoft.Getstarted", "Microsoft.GetHelp"]),
    ("remove_powerautomate", ["Microsoft.PowerAutomateDesktop"]),
    ("remove_cortana", ["Microsoft.549981C3F5F10"]),
]
for _id, _pk in METRO:
    tw(_id, "metro", [F(f_appx(_pk))], reversible=False, impact="habits",
       risky="xbox" if _id == "remove_xbox" else "irrev")

# ── Зовнішній вигляд (вкладка «Вигляд») ──
SHELL_ICONS = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons"
tw("tweak_no_arrows", "visual", [R(SHELL_ICONS, "29", r"%windir%\System32\imageres.dll,197", "sz"),
                                 C("ie4uinit.exe -ClearIconCache"), X("explorer")],
   off=[RD(SHELL_ICONS, "29"), C("ie4uinit.exe -ClearIconCache"), X("explorer")])
tw("tweak_show_ext", "visual", [R(ADV, "HideFileExt", 0), X("explorer")], off=[R(ADV, "HideFileExt", 1), X("explorer")])
tw("tweak_show_hidden", "visual", [R(ADV, "Hidden", 1), X("explorer")], off=[R(ADV, "Hidden", 2), X("explorer")])
tw("tweak_dark_mode", "visual", [R(PERS, "AppsUseLightTheme", 0), R(PERS, "SystemUsesLightTheme", 0), X("broadcast")],
   off=[R(PERS, "AppsUseLightTheme", 1), R(PERS, "SystemUsesLightTheme", 1), X("broadcast")])
tw("tweak_no_aero_shake", "visual", [R(ADV, "DisallowShaking", 1)], off=[RD(ADV, "DisallowShaking")])
tw("tweak_fast_alttab", "visual", [R(DESK, "MenuShowDelay", "0", "sz"), R(DESK + r"\WindowMetrics", "MinAnimate", "0", "sz"),
                                   R(ADV, "ExtendedUIHoverTime", 1), X("anim")],
   off=[R(DESK, "MenuShowDelay", "400", "sz"), R(DESK + r"\WindowMetrics", "MinAnimate", "1", "sz"),
        RD(ADV, "ExtendedUIHoverTime"), X("anim")])
STICKY = r"HKCU\Control Panel\Accessibility"
tw("tweak_no_sticky", "visual", [R(STICKY + r"\StickyKeys", "Flags", "506", "sz"),
                                 R(STICKY + r"\ToggleKeys", "Flags", "58", "sz"),
                                 R(STICKY + r"\Keyboard Response", "Flags", "122", "sz")],
   off=[R(STICKY + r"\StickyKeys", "Flags", "510", "sz"), R(STICKY + r"\ToggleKeys", "Flags", "62", "sz"),
        R(STICKY + r"\Keyboard Response", "Flags", "126", "sz")])
tw("sel_color", "visual", custom=True)
tw("sel_text_color", "visual", custom=True)

BY_ID = {t.id: t for t in TWEAKS}


def _conflict_map() -> dict:
    """Конфлікти симетричні: якщо A конфліктує з B, то й B з A (у каталозі достатньо вказати з одного боку)."""
    m = {t.id: set(t.conflicts) for t in TWEAKS}
    for t in TWEAKS:
        for o in t.conflicts:
            m.setdefault(o, set()).add(t.id)
    return m


CONFLICTS = _conflict_map()


def conflicts_of(tid: str) -> set:
    return CONFLICTS.get(tid, set())


def resolve_conflicts(ids, applied=None) -> tuple:
    """Із вибраного прибирає те, що суперечить уже застосованому або вибраному раніше в цьому ж пакеті
    (наприклад, «Агресивний Turbo» і «Тихий режим»: друге просто перезаписало б перше).
    -> (що застосовувати, [(id, з чим конфліктує)])."""
    applied = set(JOURNAL.data["applied"]) if applied is None else set(applied)
    keep, dropped = [], []
    for tid in ids:
        clash = next((o for o in sorted(conflicts_of(tid)) if o in applied or o in keep), None)
        if clash:
            dropped.append((tid, clash))
        else:
            keep.append(tid)
    return keep, dropped


def _admin_op(op) -> bool:
    """Чи потрібні права адміністратора для операції. Без них змінюються лише параметри поточного користувача."""
    if op[0] in ("reg", "regdel"):
        return not str(op[1]).upper().startswith("HKCU")
    return op[0] != "live"


def needs_admin(t: Tweak) -> bool:
    return any(_admin_op(op) for op in t.ops)


def _admin_record(rec: dict) -> bool:
    if rec.get("t") == "reg":
        return not str(rec.get("p", "")).upper().startswith("HKCU")
    return rec.get("t") != "live"


COLORS_KEY = r"HKCU\Control Panel\Colors"
COLOR_NAMES = {"sel_color": ["Hilight", "HotTrackingColor"], "sel_text_color": ["HilightText"]}


def color_tweak(tid: str, rgb) -> Tweak:
    val = " ".join(str(int(c)) for c in rgb)
    return Tweak(tid, "visual", [R(COLORS_KEY, n, val, "sz") for n in COLOR_NAMES[tid]] + [X("syscolor")], custom=True)


def current_color(tid: str, default=(0, 120, 215)):
    v = reg_get(COLORS_KEY, COLOR_NAMES[tid][0])
    try:
        r, g, b = [int(x) for x in str(v[1]).split()[:3]]
        return r, g, b
    except Exception:
        return default


def probe(t: Tweak) -> bool:
    """Чи застосовано твік: за значеннями реєстру або за журналом відкату."""
    regs = [op for op in t.ops if op[0] == "reg" and not callable(op[3])][:3]
    if not regs or not winreg:
        return JOURNAL.has(t.id)
    for _, path, name, value, _rt in regs:
        cur = reg_get(path, name)
        if cur is None or str(cur[1]).lower() != str(value).lower():
            return False
    return True


WIN10_RELEASES = {17134: "1803", 17763: "1809", 18362: "1903", 19041: "2004"}


def compat(t: Tweak, hw: dict):
    """-> (стан, пояснення). Стан: ok | warn | block | na."""
    if not hw:
        return "ok", ""
    build = hw.get("build") or 0
    if t.win11 and build and build < 22000:
        return "na", tr("need.win11")
    if t.win10 and build >= 22000:
        return "na", tr("need.win10")
    if t.min_build and build and build < t.min_build:
        return "na", tr("need.build", ver=WIN10_RELEASES.get(t.min_build, str(t.min_build)))
    if t.needs and not hw.get(t.needs):
        return "na", tr(f"need.{t.needs}")
    for k in t.block_on:
        if hw.get(k):
            return "block", tr(f"block.{k}")
    for k in t.warn_on:
        if hw.get(k):
            return "warn", tr(f"warn.{k}")
    return "ok", ""


def describe_ops(t: Tweak) -> list:
    """Технічний опис змін для панелі «Що саме зміниться»."""
    out = []
    for op in t.ops:
        k = op[0]
        if k == "reg":
            v = op[3]
            if callable(v):
                v = "<" + tr("d.current_plan") + ">"
            elif isinstance(v, (bytes, bytearray)):
                v = bytes(v).hex(" ").upper()
            elif isinstance(v, int) and v > 255:
                v = f"0x{v:X}"
            out.append(f"{tr('d.reg')}: {op[1]}\\{op[2]} = {v} ({TYPE_NAMES.get(op[4], op[4])})")
        elif k == "regdel":
            out.append(f"{tr('d.reg')}: {op[1]}\\{op[2]} → {tr('d.delete')}")
        elif k == "svc":
            out.append(f"{tr('d.service')}: {op[1]} → {op[2]}")
        elif k == "task":
            names = [n.rsplit("\\", 1)[-1] for n in op[1]]
            more = f" +{len(names) - 3}" if len(names) > 3 else ""
            out.append(f"{tr('d.tasks')}: {', '.join(names[:3])}{more} → {tr('d.disabled')}")
        elif k == "cmd":
            out.append(f"{tr('d.command')}: {op[1]}")
        elif k == "pw":
            out.append(f"{tr('d.power')} ({tr('d.' + op[4])}): {op[1]} / {op[2]} = {op[3]}")
        elif k in ("fn", "dyn"):
            out.append(f"{tr('d.action')}: {getattr(op[1], 'cmd', op[1].__name__)}")
    return out


# ───────────────────────── профілі ─────────────────────────
PROFILES = [
    dict(key="F", color="#4F9EF8"),
    dict(key="M", color="#3DDC84"),
    dict(key="L", color="#F0C040"),
    dict(key="T", color="#C07AF0"),
    dict(key="O", color="#FF9F5A"),
    dict(key="X", color="#2DD4BF"),
]


def profile_name(key: str) -> str:
    return tr(f"prof.{key}.name")


# ───────────────────────── разові дії (виправлення та очищення) ─────────────────────────
@dataclass
class Action:
    id: str
    fn: Callable
    kind: str = "clean"  # clean — очищення; fix — виправлення

    @property
    def title(self) -> str:
        return tr(f"act.{self.id}.t")

    @property
    def desc(self) -> str:
        return tr(f"act.{self.id}.d")


def a_clean_temp(ctx: Ctx) -> None:
    if DRY_RUN:
        ctx.log("  [dry-run] TEMP, Windows\\Temp, Prefetch")
        return
    freed = sum(clean_dir(p) for p in (os.environ.get("TEMP"), _env(r"%SystemRoot%\Temp"),
                                       _env(r"%SystemRoot%\Prefetch")))
    ctx.log(tr("e.freed_mb", mb=f"{freed / 2**20:.0f}"))


def _explorer_files(patterns) -> int:
    n = 0
    for pat in patterns:
        for f in glob.glob(_env(pat)):
            try:
                os.remove(f)
                n += 1
            except OSError:
                pass
    return n


def a_reset_icons(ctx: Ctx) -> None:
    if DRY_RUN:
        ctx.log("  [dry-run] iconcache*.db, explorer")
        return
    run("taskkill /f /im explorer.exe", 10, ctx.log)
    n = _explorer_files([r"%LOCALAPPDATA%\IconCache.db", r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache_*.db"])
    explorer_start(ctx.log)
    ctx.log(tr("e.cache_files", n=n))


def a_clear_thumbs(ctx: Ctx) -> None:
    if DRY_RUN:
        ctx.log("  [dry-run] thumbcache_*.db")
        return
    run("taskkill /f /im explorer.exe", 10, ctx.log)
    n = _explorer_files([r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache_*.db"])
    explorer_start(ctx.log)
    ctx.log(tr("e.cache_files", n=n))


def a_clear_clipboard(ctx: Ctx) -> None:
    run('cmd /c "echo off | clip"', 8, ctx.log)


def a_flush_dns(ctx: Ctx) -> None:
    run("ipconfig /flushdns", 15, ctx.log)
    run("ipconfig /registerdns", 15, ctx.log)


def a_net_reset(ctx: Ctx) -> None:
    for c in ("netsh winsock reset", "netsh int ip reset", "arp -d *", "netsh int tcp reset"):
        run(c, 25, ctx.log)
    ctx.log(tr("e.net_reset_note"))


BLOAT_PROCS = ["OneDrive.exe", "MicrosoftEdgeUpdate.exe", "SearchIndexer.exe", "CompatTelRunner.exe",
               "YourPhone.exe", "PhoneExperienceHost.exe", "GameBar.exe", "GameBarFTServer.exe", "Widgets.exe",
               "WidgetService.exe", "Cortana.exe", "SkypeApp.exe", "SkypeBackgroundHost.exe"]


def a_kill_bloat(ctx: Ctx) -> None:
    n = 0
    for p in BLOAT_PROCS:
        rc, _ = run(f"taskkill /f /im {p}", 8, ctx.log)
        n += rc == 0
    ctx.log(tr("e.killed", n=n))


def a_restart_explorer(ctx: Ctx) -> None:
    restart_explorer(ctx.log)


def _pct_parser(label: str):
    last = [-10]

    def parse(line: str):
        m = re.search(r"(\d{1,3})(?:[.,]\d+)?\s*%", line)
        if m:
            pct = min(100, int(m.group(1)))
            if pct >= last[0] + 5 or (pct == 100 and last[0] != 100):
                last[0] = pct
                n = max(0, min(20, pct // 5))
                return f"  {label} [{'█' * n}{'░' * (20 - n)}] {pct}%"
            return None
        return f"  {line[:120]}"
    return parse


def a_optimize_disk(ctx: Ctx) -> None:
    drive = os.environ.get("SystemDrive", "C:")
    ok = stream(f"defrag {drive} /O /U /V", ctx.log, _pct_parser("defrag"), 7200)
    ctx.log(tr("e.done") if ok else tr("e.disk_warn"))


def a_sfc_dism(ctx: Ctx) -> None:
    integrity_check(ctx.log, None, 0, 2)


def a_reset_wu(ctx: Ctx) -> None:
    log = ctx.log
    for s in ("wuauserv", "bits", "cryptsvc", "msiserver"):
        run(f"net stop {s}", 30, log)
    stamp = time.strftime("%Y%m%d%H%M%S")
    run(rf'ren "%SystemRoot%\SoftwareDistribution" SoftwareDistribution.old{stamp}', 30, log)
    run(rf'ren "%SystemRoot%\System32\catroot2" catroot2.old{stamp}', 30, log)
    for s in ("wuauserv", "bits", "cryptsvc", "msiserver"):
        run(f"net start {s}", 30, log)


def a_reset_store(ctx: Ctx) -> None:
    run("wsreset.exe", 120, ctx.log)
    run("taskkill /f /im WinStore.App.exe", 8, ctx.log)


def a_fix_audio(ctx: Ctx) -> None:
    for c in ("net stop Audiosrv /y", "net stop AudioEndpointBuilder /y", "net start AudioEndpointBuilder",
              "net start Audiosrv"):
        run(c, 30, ctx.log)


def a_fix_search(ctx: Ctx) -> None:
    run("taskkill /f /im SearchHost.exe", 8, ctx.log)
    run("taskkill /f /im SearchApp.exe", 8, ctx.log)
    run("net stop WSearch /y", 30, ctx.log)
    run("net start WSearch", 30, ctx.log)


def a_enable_trim(ctx: Ctx) -> None:
    run("fsutil behavior set DisableDeleteNotify 0", 15, ctx.log)


SHADER_DIRS = [r"%LOCALAPPDATA%\D3DSCache", r"%LOCALAPPDATA%\NVIDIA\DXCache", r"%LOCALAPPDATA%\NVIDIA\GLCache",
               r"%LOCALAPPDATA%\..\LocalLow\NVIDIA\PerDriverVersion\DXCache", r"%LOCALAPPDATA%\AMD\DxCache",
               r"%LOCALAPPDATA%\AMD\DxcCache", r"%LOCALAPPDATA%\AMD\VkCache", r"%LOCALAPPDATA%\AMD\GLCache",
               r"%LOCALAPPDATA%\Intel\ShaderCache", r"%ProgramData%\NVIDIA Corporation\NV_Cache"]


def a_clear_shaders(ctx: Ctx) -> None:
    if DRY_RUN:
        ctx.log("  [dry-run] D3DSCache, NVIDIA DXCache/GLCache, AMD DxCache/VkCache, Intel ShaderCache")
        return
    freed = 0
    for d in SHADER_DIRS:
        path = os.path.normpath(_env(d))
        if os.path.isdir(path):
            got = clean_dir(path)
            freed += got
            ctx.log(f"  · {path}: {got / 2**20:.0f} MB")
    ctx.log(tr("e.freed_mb", mb=f"{freed / 2**20:.0f}"))
    ctx.log(tr("e.shaders_note"))


ACTIONS = [
    Action("fu_memory", f_memory_clean), Action("fu_temp", a_clean_temp), Action("fu_icons", a_reset_icons),
    Action("fu_thumbs", a_clear_thumbs), Action("fu_clip", a_clear_clipboard), Action("fu_bloat", a_kill_bloat),
    Action("fu_shaders", a_clear_shaders), Action("disk_optimize", a_optimize_disk), Action("junk_full", f_clean_junk),
    Action("clean_winsxs", a_clean_winsxs),
    Action("fu_dns", a_flush_dns, "fix"), Action("fu_net", a_net_reset, "fix"),
    Action("fu_explorer", a_restart_explorer, "fix"), Action("fix_audio", a_fix_audio, "fix"),
    Action("fix_search", a_fix_search, "fix"), Action("fix_store", a_reset_store, "fix"),
    Action("fix_wu", a_reset_wu, "fix"), Action("fix_sfc", a_sfc_dism, "fix"),
]
ACTION_BY_ID = {a.id: a for a in ACTIONS}
ACTION_BY_ID["trim_on"] = Action("trim_on", a_enable_trim, "fix")


def run_action(a: Action, log: Callable, hw: dict = None):
    ctx = Ctx(log, hw=hw)
    log(f"[►] {a.title}")
    try:
        a.fn(ctx)
        log(tr("e.done"))
    except Exception as e:
        log(tr("e.err", err=f"{type(e).__name__}: {e}"))
        return {"error": str(e)}
    return {"ok": True}


# ───────────────────────── запуск, відкат, перевірка цілісності ─────────────────────────
def run_tweak(t: Tweak, ctx: Ctx):
    """-> True — застосовано, False — помилка, None — пропущено (не підходить цьому залізу чи Windows)."""
    if t.win11 and win_build() < 22000:
        ctx.log(tr("e.win11_only"))
        return None
    if t.win10 and win_build() >= 22000:
        ctx.log(tr("e.win10_only"))
        return None
    state, reason = compat(t, ctx.hw)
    if state in ("na", "block"):
        ctx.log(tr("e.blocked", reason=reason))
        return None
    if not DRY_RUN and needs_admin(t) and not is_admin():
        ctx.log(tr("e.need_admin"))
        return None
    title = t._title or None
    track = t.reversible
    if track:  # JournalError тут — ще нічого не змінено; пакет зупиниться
        ctx.journal.begin(t.id, title, t.group)
    ctx.begin(track)
    try:
        for op in t.ops:
            exec_op(op, ctx)
        if track:
            ctx.journal.commit(t.id, list(ctx.undo), title=title, group=t.group)
    except Exception as e:
        # Оптимізація або вся, або ніяк: те, що встигло змінитися до помилки, одразу повертаємо — інакше в системі
        # лишився б «напівзастосований» пункт. Записи відкату вже на диску, тож навіть аварія під час цього
        # відкату не загубить їх (recover_interrupted доверне під час наступного запуску).
        ctx.log(tr("e.err", err=f"{type(e).__name__}: {e}"))
        if track and ctx.undo:
            failed = _rollback(list(ctx.undo), ctx.log)
            if failed:  # що не повернулося — у журнал, щоб можна було повторити відкат
                try:
                    ctx.journal.put(t.id, failed, title=title, group=t.group)
                except JournalError:
                    pass
            ctx.log(tr("e.rolled_back") if not failed else tr("e.rolled_back_part", n=len(failed)))
        if track:
            if isinstance(e, JournalError):
                ctx.journal.abort()
                raise
            ctx.journal.abort()
        return False
    return True


def integrity_check(log: Callable, progress: Optional[Callable], done: int, total: int) -> None:
    log("\n" + "═" * 58)
    log(" " + tr("e.integrity"))
    log("═" * 58)
    if progress:
        progress(done, total, "SFC /scannow")
    log("\n[►] SFC /scannow")
    ok = stream("sfc /scannow", log, _pct_parser("SFC"), 900, enc="utf-16-le")
    log(tr("e.sfc_ok") if ok else tr("e.sfc_warn"))
    if CANCEL.is_set():
        return
    if progress:
        progress(done + 1, total, "DISM RestoreHealth")
    log("\n[►] DISM /Online /Cleanup-Image /RestoreHealth")
    ok = stream("DISM /Online /Cleanup-Image /RestoreHealth", log, _pct_parser("DISM"), 1800)
    log(tr("e.dism_ok") if ok else tr("e.dism_warn"))


RESTORE_POINT_NAME = f"{APP_NAME} Restore Point"


def create_restore_point(log: Callable) -> dict:
    log(tr("e.rp"))
    key = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore"
    name = "SystemRestorePointCreationFrequency"
    old = reg_get(key, name)
    ok = False
    try:
        if not DRY_RUN:  # без цього Windows пропускає точку, якщо за 24 години вже була інша
            reg_set(key, name, 0, "dword")
        rc, out = ps('Enable-ComputerRestore -Drive ($env:SystemDrive + "\\"); '
                     f"Checkpoint-Computer -Description '{RESTORE_POINT_NAME}' "
                     "-RestorePointType MODIFY_SETTINGS", 120, log)
        _, last = ps("(Get-ComputerRestorePoint | Sort-Object CreationTime | Select-Object -Last 1).Description",
                     40, ro=True)
        ok = DRY_RUN or RESTORE_POINT_NAME in last
        if not ok and out:
            log(f"  ⚠ {first_line(out)}")
    finally:
        if not DRY_RUN:
            if old is None:
                reg_del_value(key, name)
            else:
                reg_set(key, name, old[1], old[0])
    log(tr("e.rp_ok") if ok else tr("e.rp_fail"))
    return {"ok": ok}


# Викликаються перед першою зміною кожного пакета (baseline.py: знімок початкових налаштувань Windows).
BEFORE_APPLY: list = []


def apply_tweaks(items, log: Callable, progress: Optional[Callable] = None, sfc: bool = False,
                 header: bool = True, hw: dict = None, restore_point: bool = False, by: str = "") -> dict:
    ctx = Ctx(log, hw=hw)
    keep, dropped = resolve_conflicts([t.id for t in items])
    items = [t for t in items if t.id in set(keep)]
    if len(items) > 1:
        ctx.deferred = set()  # Провідник перезапускаємо один раз наприкінці, а не після кожного твіка
    total = len(items) + (2 if sfc else 0) + (1 if restore_point else 0)
    ok = fail = skipped = 0
    reboot = False
    step = 0
    error = None
    if header:
        log("═" * 58)
        log(f" {APP_TITLE} — {tr('e.header_run')}")
        log("═" * 58)
        if DRY_RUN:
            log(tr("e.preview"))
    for tid, other in dropped:
        log(tr("e.conflict", title=entry_title(tid), other=entry_title(other)))
    if not DRY_RUN and not is_admin() and any(needs_admin(t) for t in items):
        log(tr("e.need_admin_all"))
    try:
        JOURNAL.begin_op("apply", [t.id for t in items], by)
    except JournalError as e:  # журнал не записується (диск повний, немає доступу) — не змінюємо нічого
        log(tr("e.journal_fail", err=str(e)))
        return {"ok": 0, "fail": 0, "skipped": len(items), "reboot": False, "error": "journal",
                "conflicts": dropped}
    for hook in list(BEFORE_APPLY):
        try:
            hook(log)
        except Exception as e:  # знімок початкових налаштувань не має заважати оптимізації
            log(f"  ⚠ {type(e).__name__}: {e}")
    if restore_point:
        if progress:
            progress(0, total, tr("e.rp_step"))
        create_restore_point(log)
        step = 1
    for i, t in enumerate(items):
        if CANCEL.is_set():
            log(tr("e.stopped"))
            break
        if progress:
            progress(step + i, total, t.title)
        log(f"\n[►] {t.title}")
        try:
            res = run_tweak(t, ctx)
        except JournalError as e:
            log(tr("e.journal_fail", err=str(e)))
            error = "journal"
            fail += 1
            break
        if res is None:
            skipped += 1
            continue
        if res:
            ok += 1
            log(tr("e.done_reboot") if t.reboot else tr("e.done"))
        else:
            fail += 1
        reboot = reboot or t.reboot
    for kind in sorted(ctx.deferred or ()):
        live_refresh(kind, log)
    JOURNAL.end_op()  # пакет дійшов до кінця (перевірка цілісності нижче нічого не змінює в журналі)
    if sfc and not CANCEL.is_set() and not error:
        integrity_check(log, progress, step + len(items), total)
    if progress:
        progress(total, total, tr("e.finished"))
    if header:
        log("\n" + "═" * 58)
        msg = tr("e.summary", ok=ok)
        if fail:
            msg += tr("e.summary_fail", fail=fail)
        if skipped or dropped:
            msg += tr("e.summary_skip", n=skipped + len(dropped))
        msg += tr("e.summary_reboot") if reboot else "."
        log(" " + msg)
        log("═" * 58)
    res = {"ok": ok, "fail": fail, "skipped": skipped, "reboot": reboot, "conflicts": dropped}
    if error:
        res["error"] = error
    return res


def run_selected(ids, log: Callable, progress: Optional[Callable] = None, sfc: bool = True, hw: dict = None,
                 restore_point: bool = False) -> dict:
    wanted = set(ids)
    return apply_tweaks([t for t in TWEAKS if t.id in wanted], log, progress, sfc, hw=hw, restore_point=restore_point)


def entry_title(tid: str) -> str:
    t = BY_ID.get(tid)
    if t:
        return t.title
    e = JOURNAL.get(tid) or {}
    return e.get("title") or tid


def undo_ids(ids, log: Callable, progress: Optional[Callable] = None, by: str = "") -> dict:
    # Завжди від найновішого до найстарішого, хоч би в якому порядку прийшли id (пробний режим, «зміни між
    # тестами FPS», аварійний відкат…): якщо два твіки змінили одне значення, лише так воно стане початковим.
    order = {tid: i for i, tid in enumerate(JOURNAL.newest_first())}
    ids = sorted(dict.fromkeys(ids), key=lambda tid: order.get(tid, len(order)))
    n = partial = 0
    reboot = False
    deferred = set() if len(ids) > 1 else None
    admin = DRY_RUN or is_admin()
    try:
        JOURNAL.begin_op("undo", ids, by)
    except JournalError:
        pass  # відкат усе одно робимо: він лише повертає систему до початкового стану
    for i, tid in enumerate(ids):
        if CANCEL.is_set():
            break
        title = entry_title(tid)
        if progress:
            progress(i, len(ids), title)
        log(f"\n[↩] {title}")
        t = BY_ID.get(tid)
        entry = JOURNAL.get(tid) or {}
        if not admin and any(_admin_record(r) for r in entry.get("undo", [])):
            log(tr("e.need_admin"))
            continue
        reboot = reboot or bool(t and t.reboot) or tid.startswith("msi:")
        res = undo_one(tid, log, deferred)
        if res == "partial":
            partial += 1
            log(tr("e.undo_partial", n=len((JOURNAL.get(tid) or {}).get("undo", []))))
        elif res:
            n += 1
            log(tr("e.undone"))
        else:
            log(tr("e.no_undo"))
    for kind in sorted(deferred or ()):
        live_refresh(kind, log)
    JOURNAL.end_op()
    if progress:
        progress(len(ids), len(ids), tr("e.finished"))
    log(tr("e.undone_total", n=n))
    return {"undone": n, "partial": partial, "reboot": reboot}


def recover_interrupted(log: Callable = lambda *_: None) -> dict:
    """Після аварійного завершення OptimaX (виліт, зняли процес, синій екран, зникло світло):

    1. Оптимізацію, яка застосовувалась у мить аварії, повертаємо одразу за попереднім записом журналу —
       вона «напівзастосована», і в журналі відкату її ще немає.
    2. Пакет, що не дійшов до кінця, повертаємо як {"op": {kind, ts, ids, by}, "ids": [...]}:
       apply — зміни цього пакета, які вже застосовано (інтерфейс запропонує їх відкотити);
       undo — зміни, які ще не відкочено (запропонує завершити відкат).
    Позначку пакета знімає той, хто ухвалить рішення (Journal.end_op)."""
    res = {"tweak": None, "records": 0, "failed": 0, "op": None, "ids": []}
    w = JOURNAL.interrupted()
    if w:
        tid = w["tid"]
        if w.get("fresh") and not JOURNAL.has(tid) and w.get("undo"):
            log(tr("e.recover_tweak", title=w.get("title") or entry_title(tid)))
            failed = _rollback(w["undo"], log)
            res.update(tweak=tid, records=len(w["undo"]), failed=len(failed))
            if failed:  # не вдалося — у журнал, щоб повернути пізніше (зокрема через OptimaX-Rescue.cmd)
                try:
                    JOURNAL.put(tid, failed, title=w.get("title"), group=w.get("group"))
                except JournalError:
                    pass
        JOURNAL.abort()
    op = JOURNAL.op()
    if op:
        if op.get("kind") == "undo":
            ids = [i for i in op.get("ids") or [] if JOURNAL.has(i)]
        else:
            ids = [i for i in JOURNAL.newest_first() if (JOURNAL.get(i) or {}).get("ts", 0) >= op.get("ts", 0)]
        if ids:
            res.update(op=op, ids=ids)
        else:
            JOURNAL.end_op()  # нічого не лишилося — і пропонувати нічого
    return res


def undo_or_default(t: Tweak, log: Callable) -> dict:
    log(f"\n[↩] {t.title}")
    res = undo_one(t.id, log)
    if res == "partial":
        log(tr("e.undo_partial", n=len((JOURNAL.get(t.id) or {}).get("undo", []))))
    elif res:
        log(tr("e.undone"))
    elif t.off:
        ctx = Ctx(log)
        ctx.begin()
        for op in t.off:
            exec_op(op, ctx)
        log(tr("e.defaults"))
    else:
        log(tr("e.nothing"))
    return {"undone": 1}
