"""
OptimaX — переклади: українська, російська, англійська.

Рядки зберігаються як кортежі (uk, ru, en). Мова береться з налаштувань, ключа --lang=xx
або з мови Windows. Зміна мови застосовується після перезапуску програми.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys

LANGS = (("uk", "Українська"), ("ru", "Русский"), ("en", "English"))
_IDX = {"uk": 0, "ru": 1, "en": 2}
APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
CONFIG_PATH = os.path.join(APPDATA, "OptimaX", "settings.json")


def system_language() -> str:
    try:
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return {0x22: "uk", 0x19: "ru"}.get(lid, "en")
    except Exception:
        env = (os.environ.get("LANG") or "").lower()
        return "uk" if env.startswith("uk") else "ru" if env.startswith("ru") else "en"


def _initial() -> str:
    for a in sys.argv:
        if a.startswith("--lang=") and a[7:] in _IDX:
            return a[7:]
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            v = json.load(f).get("language")
        if v in _IDX:
            return v
    except Exception:
        pass
    try:  # мову, вибрану в інсталяторі, він записує сюди
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\X44TO\OptimaX") as k:
            v = winreg.QueryValueEx(k, "Language")[0]
        if v in _IDX:
            return v
    except Exception:
        pass
    return system_language()


LANG = _initial()
STR: dict = {}
TWEAK_TEXT: dict = {}


def set_language(code: str) -> None:
    """Для тестів і попереднього перегляду; інтерфейс перебудовується лише після перезапуску."""
    global LANG
    if code in _IDX:
        LANG = code


def tr(key: str, **kw) -> str:
    v = STR.get(key)
    if v is None:
        text = key
    else:
        text = v[_IDX[LANG]] or v[2] or v[0]
    if kw:
        try:
            text = text.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def tweak_text(tid: str) -> tuple:
    v = TWEAK_TEXT.get(tid)
    if not v:
        return tid, ""
    i = _IDX[LANG]
    return v[2 * i] or v[4], v[2 * i + 1] or v[5]


def _load() -> None:
    from lang_engine import STRINGS as eng
    from lang_ui import STRINGS as ui
    from lang_extra import STRINGS as extra
    from lang_setup import STRINGS as setup
    from lang_lab import STRINGS as lab
    from lang_safe import STRINGS as safe
    from lang_tweaks import TEXTS
    STR.update(eng)
    STR.update(ui)
    STR.update(extra)
    STR.update(setup)
    STR.update(lab)
    STR.update(safe)
    TWEAK_TEXT.update(TEXTS)


_load()
