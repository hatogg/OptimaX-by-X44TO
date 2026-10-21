"""
OptimaX — життєвий цикл програми: одна копія (друга лише показує вікно першої), службові режими для
інсталятора (--uninstall, --revert-all, --set-autostart), визначення встановленої версії.
"""
from __future__ import annotations

import ctypes
import os
import sys
import time

import engine as E
import features as F
from i18n import tr

MUTEX_NAMES = ("OptimaX_X44TO", "Global\\OptimaX_X44TO")  # ці ж імена — AppMutex в інсталяторі
SOCKET_NAME = "OptimaX-X44TO-ui"
WAIT_OBJECT_0, WAIT_ABANDONED = 0x0, 0x80
_handles: list = []


def app_dir() -> str:
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def is_installed() -> bool:
    """Встановлено інсталятором (поруч є деінсталятор), а не портативна копія."""
    return os.path.exists(os.path.join(app_dir(), "unins000.exe"))


def acquire_instance(wait_s: float = 0.0) -> bool:
    """True — ми єдина копія. wait_s — скільки чекати, поки попередня копія закриється (після перезапуску)."""
    if not E.IS_WIN:
        return True
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    owned = True
    for name in MUTEX_NAMES:
        h = k32.CreateMutexW(None, False, name)
        if not h:
            continue  # Global\ може бути недоступний без прав — тоді достатньо локального
        _handles.append(h)
        rc = k32.WaitForSingleObject(h, int(wait_s * 1000))
        if rc not in (WAIT_OBJECT_0, WAIT_ABANDONED):
            owned = False
    return owned


def notify_running() -> bool:
    """Просить уже запущену копію показати вікно."""
    try:
        from PyQt6.QtNetwork import QLocalSocket
    except ImportError:
        return False
    if E.IS_WIN:
        try:
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: перша копія зможе вийти на передній план
        except Exception:
            pass
    s = QLocalSocket()
    s.connectToServer(SOCKET_NAME)
    if not s.waitForConnected(1500):
        return False
    s.write(b"show")
    s.waitForBytesWritten(1000)
    s.disconnectFromServer()
    return True


def start_server(on_show):
    """Слухає запити інших копій. -> об'єкт сервера (тримайте посилання) або None."""
    try:
        from PyQt6.QtNetwork import QLocalServer
    except ImportError:
        return None
    srv = QLocalServer()
    QLocalServer.removeServer(SOCKET_NAME)
    if not srv.listen(SOCKET_NAME):
        return None

    def incoming():
        while srv.hasPendingConnections():
            c = srv.nextPendingConnection()
            c.waitForReadyRead(300)
            c.readAll()
            c.disconnectFromServer()
            on_show()
    srv.newConnection.connect(incoming)
    return srv


# ───────────────────────── службові режими для інсталятора ─────────────────────────
TASKS = ("OptimaX", "OptimaX Trial", "OptimaX Maintenance", "OptimaX DNS", "OptimaX Safety", "OptimaX Smart")


def uninstall_cleanup(revert: bool, log) -> dict:
    """Перед видаленням: (за бажанням) відкотити всі зміни, повернути режим гри, прибрати задачі планувальника."""
    res = {"undone": 0}
    log(f"{E.APP_TITLE} {E.VERSION} — {tr('lc.cleanup')}")
    if F.CFG["booster_state"]:
        F.BOOSTER.stop(log)
    if revert and E.JOURNAL.count():
        res.update(E.undo_ids(E.JOURNAL.newest_first(), log))
    try:  # блокування реклами: зупинити фільтр і повернути DNS адаптерів
        import adblock as AB
        AB.Backend(F.CFG).uninstall(log)
    except Exception as e:
        log(f"adblock: {e}")
    lim = F.CFG["charge_limit"]
    if lim and lim.get("method"):
        import power as PW
        PW.set_charge_limit(lim["method"], 100, log)
        F.CFG["charge_limit"] = None
    for name in TASKS:
        E.run(["schtasks", "/Delete", "/TN", name, "/F"], 20, log)
    for key in ("trial",):
        F.CFG[key] = None
    s = F.CFG["schedule"] or {}
    s["enabled"] = False
    F.CFG["schedule"] = s
    log(tr("lc.cleanup_done", n=res.get("undone", 0)))
    return res


def run_cli(argv) -> int:
    """Режими без вікна. -> код виходу або None, якщо треба запускати інтерфейс."""
    lines = []

    def log(s):
        lines.append(str(s))
    code = None
    if "--uninstall" in argv:
        uninstall_cleanup("--revert-all" in argv, log)
        code = 0
    elif "--set-autostart" in argv or "--no-autostart" in argv:
        code = 0 if F.set_autostart("--set-autostart" in argv, log) else 1
    if code is not None:
        try:
            path = os.path.join(os.environ.get("TEMP", E.DATA_DIR), "OptimaX-setup.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(argv[1:]) + "\n" + "\n".join(lines) + "\n")
        except OSError:
            pass
    return code
