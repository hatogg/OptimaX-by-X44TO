"""
OptimaX — глобальні гарячі клавіші (працюють, навіть коли вікно згорнуте в трей).
Ctrl+Alt+G — режим гри, Ctrl+Alt+M — очистити пам'ять.

Клавіші реєструє окремий потік без вікна (RegisterHotKey з hwnd = NULL): Windows кладе WM_HOTKEY в його
чергу повідомлень, а головне вікно отримує лише сигнал Qt. Так у віконну процедуру Qt не потрапляє
жоден Python-код (перевизначений nativeEvent), через який вікно падало з 0xC000041D.
"""
from __future__ import annotations

import ctypes
import threading

import engine as E

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
HOTKEYS = {1: ("boost", MOD_CONTROL | MOD_ALT, ord("G"), "Ctrl+Alt+G"),
           2: ("clean", MOD_CONTROL | MOD_ALT, ord("M"), "Ctrl+Alt+M")}


def _user32():
    from ctypes import wintypes
    u = ctypes.WinDLL("user32", use_last_error=True)
    u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    u.RegisterHotKey.restype = wintypes.BOOL
    u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    u.UnregisterHotKey.restype = wintypes.BOOL
    u.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    u.GetMessageW.restype = wintypes.BOOL
    u.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    u.PeekMessageW.restype = wintypes.BOOL
    u.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.PostThreadMessageW.restype = wintypes.BOOL
    return u


class Listener:
    """Потік із власною чергою повідомлень. on_action(name) викликається з цього потоку —
    у Qt передавайте далі сигналом (він сам перейде в головний потік)."""

    def __init__(self, on_action):
        self.on_action = on_action
        self.busy: list = []
        self._tid = None
        self._ready = threading.Event()
        self._thread = None

    def start(self) -> list:
        """-> дії, які не вдалося зареєструвати (клавіші вже зайняті іншою програмою)."""
        if not E.IS_WIN:
            return []
        if self._thread and self._thread.is_alive():
            return list(self.busy)
        self.busy, self._tid = [], None
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="OptimaX hotkeys", daemon=True)
        self._thread.start()
        self._ready.wait(3)
        return list(self.busy)

    def _run(self) -> None:
        from ctypes import wintypes
        u = _user32()
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # створює чергу повідомлень потоку
        ok = []
        for hid, (action, mods, vk, _text) in HOTKEYS.items():
            if u.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                ok.append(hid)
            else:
                self.busy.append(action)
        self._ready.set()
        if not ok:
            return
        try:
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam in HOTKEYS:
                    try:
                        self.on_action(HOTKEYS[msg.wParam][0])
                    except Exception:
                        pass
        finally:
            for hid in ok:
                u.UnregisterHotKey(None, hid)

    def stop(self) -> None:
        if not E.IS_WIN or not self._thread:
            return
        if self._tid:
            _user32().PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        self._thread.join(2)
        self._thread = None


def label(action: str) -> str:
    return next(t for a, _m, _v, t in HOTKEYS.values() if a == action)
