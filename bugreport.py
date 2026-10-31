"""
OptimaX — звіт про помилку одним натисканням.

• Необроблена помилка в інтерфейсі (sys.excepthook / threading.excepthook) більше не закриває програму: OptimaX
  показує вікно «Надіслати звіт?».
• Аварійне завершення самого Python (збій у бібліотеці) faulthandler записує у файл; під час наступного запуску
  OptimaX пропонує надіслати й цей звіт.
• Звіт — це сторінка нового issue на GitHub із заповненим текстом, яку відкриває браузер: користувач бачить усе, що
  буде надіслано, і сам натискає «Submit». Ім'я користувача, ім'я комп'ютера, шляхи профілю й адреси пошти з тексту
  прибираються; серійних номерів, ідентифікаторів заліза й IP у звіті немає.
"""
from __future__ import annotations

import faulthandler
import getpass
import os
import platform
import re
import sys
import threading
import time
import traceback
import urllib.parse

import engine as E

NATIVE_FILE = os.path.join(E.DATA_DIR, "crash-native.txt")
RUN_MARK = os.path.join(E.DATA_DIR, "running.flag")  # є під час роботи; лишився після запуску — минулий раз упав
MAX_URL = 7000  # GitHub і браузери надійно приймають посилання такої довжини
MAX_ASK = 3  # стільки різних помилок за запуск пропонуємо надіслати; далі — лише запис у crash-last.txt
_state = {"handler": None, "seen": set(), "fh": None}


def repo() -> str:
    try:
        import updater as U
        return U.UPDATE_REPO or "hatogg/OptimaX-by-X44TO"
    except Exception:
        return "hatogg/OptimaX-by-X44TO"


EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def sanitize(text: str) -> str:
    """Прибирає з тексту те, що вказує на людину чи комп'ютер."""
    out = str(text or "")
    home = os.path.expanduser("~")
    subs = []
    for p in {home, os.environ.get("USERPROFILE", ""), os.environ.get("HOME", "")}:
        if p and len(p) > 3:
            subs.append((p, "%USERPROFILE%"))
            subs.append((p.replace("\\", "/"), "%USERPROFILE%"))
            subs.append((p.replace("\\", "\\\\"), "%USERPROFILE%"))
    for s, r in sorted(subs, key=lambda x: -len(x[0])):
        out = re.sub(re.escape(s), r, out, flags=re.I)
    for name, mark in ((_user(), "<user>"), (os.environ.get("COMPUTERNAME", ""), "<pc>")):
        if name and len(name) >= 3:
            out = re.sub(r"(?<![\w])" + re.escape(name) + r"(?![\w])", mark, out, flags=re.I)
    return EMAIL.sub("<email>", out)


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME", "")


def system_lines(hw: dict = None) -> list:
    import i18n
    hw = hw or {}
    lines = [f"OptimaX {E.VERSION} ({'frozen' if getattr(sys, 'frozen', False) else 'source'}"
             f"{', dry-run' if E.DRY_RUN else ''}, {i18n.LANG})",
             f"Windows: {platform.platform()}" if E.IS_WIN else f"OS: {platform.platform()}",
             f"Python {platform.python_version()}"]
    if hw.get("cpu"):
        lines.append(f"CPU: {hw['cpu']}")
    if hw.get("gpus"):
        lines.append("GPU: " + ", ".join(n for n, *_ in hw["gpus"]))
    if hw.get("mining_gpu"):
        lines.append(f"Mining card: {hw['mining_gpu']}")
    return lines


def build(kind: str, trace: str = "", note: str = "", hw: dict = None, log_tail: list = None) -> tuple:
    """-> (заголовок, текст) issue. kind: crash | native | manual."""
    first = (trace.strip().splitlines() or [""])[-1][:120]
    title = {"crash": f"[{E.VERSION}] Error: {first}", "native": f"[{E.VERSION}] OptimaX closed unexpectedly",
             "manual": f"[{E.VERSION}] Problem: "}[kind]
    parts = ["### What happened", note or "_(describe what you were doing)_", "", "### System", "```",
             *system_lines(hw), "```"]
    if trace:
        parts += ["", "### Traceback", "```", trace.strip()[-4000:], "```"]
    if log_tail:
        parts += ["", "### Log", "```", *[str(x)[:200] for x in log_tail[-25:]], "```"]
    return sanitize(title), sanitize("\n".join(parts))


def issue_url(title: str, body: str) -> str:
    base = f"https://github.com/{repo()}/issues/new?"
    q = urllib.parse.urlencode({"title": title, "body": body})
    while len(base) + len(q) > MAX_URL and len(body) > 200:
        body = body[: int(len(body) * 0.8)] + "\n…"
        q = urllib.parse.urlencode({"title": title, "body": body})
    return base + q


def open_issue(title: str, body: str) -> str:
    url = issue_url(title, body)
    if E.IS_WIN and not E.DRY_RUN:
        import webbrowser
        webbrowser.open(url)
    return url


# ───────────────────────── перехоплення ─────────────────────────
def install(handler) -> None:
    """handler(trace: str, native: bool) — показує вікно. Його можуть викликати з будь-якого потоку, тож у
    optimizer це сигнал Qt із чергою до потоку інтерфейсу."""
    _state["handler"] = handler
    sys.excepthook = _hook
    threading.excepthook = _thread_hook
    try:
        os.makedirs(E.DATA_DIR, exist_ok=True)
        with open(RUN_MARK, "w") as f:
            f.write(str(os.getpid()))
        _state["fh"] = open(NATIVE_FILE, "a", encoding="utf-8")
        faulthandler.enable(file=_state["fh"], all_threads=True)
    except Exception:
        pass


def clean_exit() -> None:
    """Нормальне закриття OptimaX: позначка роботи прибирається, записане faulthandler — теж (на Windows він пише й
    про винятки, які бібліотека сама перехопила, тож без аварійного завершення це не збій)."""
    try:
        os.remove(RUN_MARK)
    except OSError:
        pass


def _report(trace: str) -> None:
    try:
        with open(os.path.join(E.DATA_DIR, "crash-last.txt"), "w", encoding="utf-8") as f:
            f.write(trace)
    except OSError:
        pass
    # той самий збій знову й знову (наприклад, у таймері) — одне вікно за запуск, а не потік вікон
    key = trace.strip().splitlines()[-1] if trace.strip() else ""
    if key in _state["seen"] or len(_state["seen"]) >= MAX_ASK:
        return
    _state["seen"].add(key)
    h = _state["handler"]
    if h:
        try:
            h(trace, False)
        except Exception:
            pass


def _hook(tp, val, tb):
    if issubclass(tp, KeyboardInterrupt):
        sys.__excepthook__(tp, val, tb)
        return
    _report("".join(traceback.format_exception(tp, val, tb)))


def _thread_hook(args):
    if args.exc_type is SystemExit:
        return
    _report("".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))


def _boot_ts() -> float:
    """Коли завантажилася Windows (0 поза Windows)."""
    if not E.IS_WIN:
        return 0.0
    try:
        import ctypes
        f = ctypes.windll.kernel32.GetTickCount64
        f.restype = ctypes.c_ulonglong
        return time.time() - f() / 1000.0
    except Exception:
        return 0.0


def native_crash() -> str:
    """Текст аварійного завершення з минулого запуску (і файл очищається), або "". Викликати до install():
    звіт є, лише якщо минулий запуск не закрився нормально (позначка роботи лишилася) і відтоді Windows не
    перезавантажувалася — вимкнення ПК з OptimaX у треї не є збоєм програми (а збій ПК розбирає «Чому впав комп?»)."""
    try:
        dirty = os.path.getmtime(RUN_MARK) > _boot_ts()
    except OSError:
        dirty = False
    try:
        with open(NATIVE_FILE, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
    except OSError:
        return ""
    if not dirty:
        text = ""
    if text or os.path.getsize(NATIVE_FILE):
        try:
            if _state["fh"]:
                _state["fh"].seek(0)
                _state["fh"].truncate()
                _state["fh"].flush()
            else:
                open(NATIVE_FILE, "w").close()
        except OSError:
            pass
    return text[-6000:]
