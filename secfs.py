"""
OptimaX — безпечні шляхи для програми з правами адміністратора (6.7).

OptimaX працює як адміністратор, а значить усе, що вона читає й запускає, мусить лежати там, куди звичайна програма
користувача (без прав адміністратора) не може писати. Інакше будь-яка така програма підкидає свій файл — і OptimaX
виконує його з правами адміністратора чи SYSTEM. Тут зібрано те, що для цього потрібно:

• Справжні системні папки. ProgramData, SystemRoot, ComSpec, PSModulePath — змінні середовища, і користувач може
  перевизначити їх для себе (HKCU\\Environment); процес з правами адміністратора успадковує їх. Тому папки беремо
  з Windows API (SHGetKnownFolderPath, GetSystemDirectory), а змінні середовища процесу виправляємо на старті.
• Повні шляхи до системних програм (powershell.exe, schtasks, icacls…). Windows шукає програму, названу лише на ім'я,
  спершу в папці самої програми й у поточній папці — у портативної версії це, наприклад, «Завантаження».
• Захищені папки в ProgramData. За замовчуванням у ProgramData будь-хто може створити папку (і стати її власником),
  а в підпапках — створювати файли. secure_dir() робить папку власністю адміністраторів, лишає запис лише
  адміністраторам і SYSTEM, а підкинуте посилання (junction) замість папки відкладає вбік.
• Довірене розташування exe: задачі планувальника з правами адміністратора чи SYSTEM запускають лише копію OptimaX
  з Program Files — портативний exe у «Завантаженнях» може підмінити будь-яка програма.

Модуль не залежить від engine (engine імпортує його першим) і поза Windows нічого не робить.
"""
from __future__ import annotations

import ctypes
import os
import stat
import subprocess
import sys
import threading
import time

IS_WIN = sys.platform == "win32"
CREATE_NO_WINDOW = 0x08000000

SID_SYSTEM = "S-1-5-18"
SID_ADMINS = "S-1-5-32-544"
SID_USERS = "S-1-5-32-545"
SID_TRUSTED_INSTALLER = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
TRUSTED_OWNERS = frozenset({SID_SYSTEM, SID_ADMINS, SID_TRUSTED_INSTALLER})

FOLDERID = {
    "ProgramData": "{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}",
    "ProgramFiles": "{905E63B6-C1BF-494E-B29C-65B732D3D21A}",
    "ProgramFilesX64": "{6D809377-6AF0-444B-8957-A3773F02200E}",
    "ProgramFilesX86": "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}",
    "Windows": "{F38BF404-1D43-42F2-9305-67DE0B28FC23}",
}

MARK = ".optimax-secured"
SCHEME = "1"  # версія схеми захисту: зміниться — папки захистяться ще раз
APP = "OptimaX"

_LOCK = threading.RLock()
_DONE: set = set()  # папки, уже перевірені в цьому процесі
_CACHE: dict = {}


# ───────────────────────── системні папки ─────────────────────────
def _known_folder(name: str) -> str:
    if not IS_WIN:
        return ""
    if name in _CACHE:
        return _CACHE[name]
    path = ""
    try:
        class GUID(ctypes.Structure):
            _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16),
                        ("d4", ctypes.c_ubyte * 8)]
        guid = GUID()
        ole32, shell32 = ctypes.windll.ole32, ctypes.windll.shell32
        if ole32.CLSIDFromString(ctypes.c_wchar_p(FOLDERID[name]), ctypes.byref(guid)) == 0:
            out = ctypes.c_void_p()
            if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0 and out.value:
                path = ctypes.wstring_at(out.value)
                ole32.CoTaskMemFree(out)
    except Exception:  # noqa: BLE001 — старий Windows, урізана збірка: нижче є запасний варіант
        path = ""
    if path and not os.path.isabs(path):
        path = ""
    _CACHE[name] = path
    return path


def windows_dir() -> str:
    if not IS_WIN:
        return ""
    p = _known_folder("Windows")
    if not p:
        try:
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.kernel32.GetWindowsDirectoryW(buf, 260) and os.path.isabs(buf.value):
                p = buf.value
        except Exception:  # noqa: BLE001
            p = ""
    return p or r"C:\Windows"


def system_dir() -> str:
    """Справжня System32 (не з %SystemRoot%, яке користувач може перевизначити)."""
    if not IS_WIN:
        return ""
    if "System32" in _CACHE:
        return _CACHE["System32"]
    p = ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.kernel32.GetSystemDirectoryW(buf, 260) and os.path.isabs(buf.value):
            p = buf.value
    except Exception:  # noqa: BLE001
        p = ""
    p = p or os.path.join(windows_dir(), "System32")
    _CACHE["System32"] = p
    return p


def program_data() -> str:
    if not IS_WIN:
        return ""
    return _known_folder("ProgramData") or os.environ.get("ProgramData") or r"C:\ProgramData"


def program_files_dirs() -> list:
    out = []
    for n in ("ProgramFiles", "ProgramFilesX64", "ProgramFilesX86"):
        p = _known_folder(n)
        if p and p not in out:
            out.append(p)
    return out


def data_root() -> str:
    """%ProgramData%\\OptimaX — спільна папка програми з правами адміністратора й служб SYSTEM."""
    return os.path.join(program_data(), APP)


_PS_DIR = os.path.join("WindowsPowerShell", "v1.0")


def sysexe(name: str) -> str:
    """Повний шлях до системної програми (powershell.exe, schtasks, icacls…), якщо вона є в System32; інакше — як є.
    Шлях із папкою не змінюється."""
    if not IS_WIN or not name or os.path.dirname(name):
        return name
    base = name if os.path.splitext(name)[1] else name + ".exe"
    sd = system_dir()
    if base.lower() == "powershell.exe":
        cand = os.path.join(sd, _PS_DIR, base)
    else:
        cand = os.path.join(sd, base)
    return cand if os.path.isfile(cand) else name


def ps_module_path() -> str:
    """Лише системні модулі PowerShell. Типовий PSModulePath починається з Documents\\WindowsPowerShell\\Modules
    користувача — модуль, підкинутий туди, PowerShell з правами адміністратора завантажив би сам."""
    parts = [os.path.join(system_dir(), _PS_DIR, "Modules")]
    for pf in program_files_dirs()[:1]:
        parts.append(os.path.join(pf, "WindowsPowerShell", "Modules"))
    return ";".join(parts)


def pin_environment() -> None:
    """Змінні середовища, які успадкують усі запущені OptimaX процеси, — на справжні системні значення."""
    if not IS_WIN:
        return
    wd, sd, pd = windows_dir(), system_dir(), program_data()
    env = os.environ
    env["SystemRoot"] = wd
    env["windir"] = wd
    env["ComSpec"] = os.path.join(sd, "cmd.exe")  # subprocess(shell=True) запускає саме %ComSpec%
    env["ProgramData"] = pd
    env["ALLUSERSPROFILE"] = pd
    env["NoDefaultCurrentDirectoryInExePath"] = "1"  # cmd.exe не шукатиме програми в поточній папці
    env["PSModulePath"] = ps_module_path()
    front = [sd, wd, os.path.join(sd, "Wbem"), os.path.join(sd, _PS_DIR)]
    rest = [p for p in (env.get("PATH") or "").split(os.pathsep) if p and p not in front]
    env["PATH"] = os.pathsep.join(front + rest)


# ───────────────────────── власник, посилання, розташування ─────────────────────────
def is_admin() -> bool:
    if not IS_WIN:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def owner_sid(path: str):
    """SID власника файлу чи папки ('S-1-5-32-544') або None, якщо дізнатися не вдалося."""
    if not IS_WIN:
        return None
    try:
        adv, k32 = ctypes.windll.advapi32, ctypes.windll.kernel32
        owner, sd = ctypes.c_void_p(), ctypes.c_void_p()
        rc = adv.GetNamedSecurityInfoW(ctypes.c_wchar_p(path), 1, 1, ctypes.byref(owner), None, None, None,
                                       ctypes.byref(sd))  # SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION
        if rc != 0 or not owner.value:
            return None
        s = ctypes.c_void_p()
        try:
            if not adv.ConvertSidToStringSidW(owner, ctypes.byref(s)) or not s.value:
                return None
            sid = ctypes.wstring_at(s.value)
            k32.LocalFree(s)
        finally:
            k32.LocalFree(sd)
        return sid if isinstance(sid, str) and sid.startswith("S-1-") else None
    except Exception:  # noqa: BLE001
        return None


def trusted_owner(path: str) -> bool:
    return owner_sid(path) in TRUSTED_OWNERS


def is_reparse(path: str) -> bool:
    """Посилання (symlink, junction): переходити за ним не можна — воно могло вести будь-куди."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)) or stat.S_ISLNK(st.st_mode)


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p)).rstrip("\\/")


def is_under(path: str, folder: str) -> bool:
    if not path or not folder:
        return False
    p, f = _norm(path), _norm(folder)
    return p == f or p.startswith(f + os.sep)


def trusted_location(path: str) -> bool:
    """exe лежить у Program Files чи Windows — туди звичайна програма користувача писати не може."""
    if not IS_WIN or not path:
        return False
    real = os.path.realpath(path)
    return any(is_under(real, d) for d in program_files_dirs() + [windows_dir()])


def self_trusted() -> bool:
    """Чи можна задачам планувальника з правами адміністратора запускати саме цю копію OptimaX."""
    if not IS_WIN:
        return True
    if not getattr(sys, "frozen", False):
        return trusted_location(sys.executable) and trusted_location(os.path.abspath(sys.argv[0] or ""))
    return trusted_location(sys.executable)


def system_target(path: str) -> bool:
    """Шлях веде в системну папку Windows (з урахуванням посилань): класти туди файли з папки гри не можна."""
    if not IS_WIN or not path:
        return False
    real = os.path.realpath(path)
    return is_under(real, windows_dir()) or os.path.dirname(real.rstrip("\\/")) == real.rstrip("\\/")


# ───────────────────────── захищені папки в ProgramData ─────────────────────────
def _icacls(*args) -> int:
    try:
        p = subprocess.run([sysexe("icacls")] + list(args), capture_output=True, timeout=120,
                           creationflags=CREATE_NO_WINDOW if IS_WIN else 0, cwd=system_dir() or None)
        return p.returncode
    except Exception:  # noqa: BLE001
        return -1


def _grants(users_read: bool) -> list:
    g = [f"*{SID_SYSTEM}:(OI)(CI)F", f"*{SID_ADMINS}:(OI)(CI)F"]
    if users_read:
        g.append(f"*{SID_USERS}:(OI)(CI)RX")
    return g


def harden(path: str, users_read: bool = True, children: bool = True) -> bool:
    """Власник — адміністратори; дозволи — лише SYSTEM і адміністратори (+ читання для користувачів).
    children — те саме для вмісту (файли, підкинуті туди раніше, коли папка ще була відкрита для запису)."""
    if not IS_WIN:
        return True
    ok = _icacls(path, "/setowner", f"*{SID_ADMINS}", "/C", "/Q") == 0
    _icacls(path, "/reset", "/C", "/Q")  # прибрати чужі явні дозволи
    ok = _icacls(path, "/inheritance:r", "/grant:r", *_grants(users_read), "/C", "/Q") == 0 and ok
    if children and os.listdir(path):
        _icacls(os.path.join(path, "*"), "/setowner", f"*{SID_ADMINS}", "/T", "/C", "/Q")
        _icacls(os.path.join(path, "*"), "/reset", "/T", "/C", "/Q")  # вміст успадковує дозволи папки
    return ok


def _marked(path: str) -> bool:
    m = os.path.join(path, MARK)
    try:
        if is_reparse(m) or not os.path.isfile(m) or not trusted_owner(m):
            return False
        with open(m, encoding="ascii") as f:
            return f.read().strip() == SCHEME
    except (OSError, ValueError):
        return False


def _mark(path: str) -> None:
    m = os.path.join(path, MARK)
    try:
        if os.path.lexists(m):
            os.remove(m)
        with open(m, "x", encoding="ascii") as f:
            f.write(SCHEME)
    except OSError:
        pass


def _quarantine(path: str, log=None) -> None:
    """Посилання чи файл на місці нашої папки — відкладаємо (перейменовуємо саме посилання, не те, куди воно веде)."""
    n, dest = 0, f"{path}.untrusted-{int(time.time())}"
    while os.path.lexists(dest):
        n += 1
        dest = f"{path}.untrusted-{int(time.time())}-{n}"
    os.rename(path, dest)
    if log:
        log(f"  ⚠ {os.path.basename(path)}: {os.path.basename(dest)}")


def _chain(path: str) -> list:
    root = data_root()
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))  # без normcase: назви папок як задано
    out, cur = [root], root
    if rel != ".":
        for part in rel.split(os.sep):
            cur = os.path.join(cur, part)
            out.append(cur)
    return out


def secure_dir(path: str, users_read: bool = True, log=None) -> str:
    """Створює (за потреби) і захищає папку всередині %ProgramData%\\OptimaX. -> шлях.
    Поза Windows і без прав адміністратора — просто створює папку."""
    path = os.path.normpath(path)
    if not (IS_WIN and is_admin()):
        os.makedirs(path, exist_ok=True)
        return path
    if not is_under(path, data_root()):
        raise ValueError(f"{path} is outside {data_root()}")
    key = (_norm(path), users_read)
    with _LOCK:
        if key in _DONE:
            return path
        chain = _chain(path)
        for i, p in enumerate(chain):
            leaf = i == len(chain) - 1
            if os.path.lexists(p) and (is_reparse(p) or not os.path.isdir(p)):
                _quarantine(p, log)
            if not os.path.isdir(p):
                os.mkdir(p)
            if not _marked(p) or (leaf and not trusted_owner(p)):
                # корінь — без вмісту: у ньому є папки з власними, суворішими дозволами (фільтр реклами, шари)
                harden(p, users_read=users_read or not leaf, children=leaf and p != chain[0])
                _mark(p)
        _DONE.add(key)
    return path


def remove_then_create(path: str, mode: str = "w", **kw):
    """Відкрити новий файл: якщо на його місці вже щось лежить (чужий файл чи посилання), спершу прибрати.
    Відкриття з "x" не піде за посиланням і не допише чужий файл, який зберіг би чужого власника."""
    if os.path.lexists(path):
        os.remove(path)
    return open(path, mode.replace("w", "x"), **kw)
