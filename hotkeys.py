"""
OptimaX — глобальні гарячі клавіші (працюють, навіть коли вікно згорнуте в трей).
Ctrl+Alt+G — режим гри, Ctrl+Alt+M — очистити пам'ять.
"""
from __future__ import annotations

import ctypes

import engine as E

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
HOTKEYS = {1: ("boost", MOD_CONTROL | MOD_ALT, ord("G"), "Ctrl+Alt+G"),
           2: ("clean", MOD_CONTROL | MOD_ALT, ord("M"), "Ctrl+Alt+M")}


def register(hwnd: int) -> list:
    """-> список дій, які не вдалося зареєструвати (клавіші вже зайняті іншою програмою)."""
    if not E.IS_WIN:
        return []
    u = ctypes.windll.user32
    busy = []
    for hid, (action, mods, vk, _text) in HOTKEYS.items():
        u.UnregisterHotKey(hwnd, hid)
        if not u.RegisterHotKey(hwnd, hid, mods | MOD_NOREPEAT, vk):
            busy.append(action)
    return busy


def unregister(hwnd: int) -> None:
    if not E.IS_WIN:
        return
    for hid in HOTKEYS:
        ctypes.windll.user32.UnregisterHotKey(hwnd, hid)


def action_from_message(message) -> str:
    """Дія для WM_HOTKEY з nativeEvent або None."""
    if not E.IS_WIN:
        return None
    from ctypes import wintypes
    msg = wintypes.MSG.from_address(int(message))
    if msg.message == WM_HOTKEY and msg.wParam in HOTKEYS:
        return HOTKEYS[msg.wParam][0]
    return None


def label(action: str) -> str:
    return next(t for a, _m, _v, t in HOTKEYS.values() if a == action)
