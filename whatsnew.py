"""
OptimaX — «Що нового» після оновлення: коротко й простими словами, один раз для кожної нової версії.
Під час першого встановлення вікно не показується — людина ще не знає, що було «до».
"""
from __future__ import annotations

import engine as E
import features as F

# версія -> ключі рядків (lang_life.py); у вікні — у такому порядку
NOTES = {
    "6.12": ["wn.612.freeze", "wn.612.deep"],
    "6.11": ["wn.611.menu", "wn.611.catalog", "wn.611.oc", "wn.611.support"],
    "6.10.1": ["wn.6101.menu", "wn.6101.setup"],
    "6.10": ["wn.610.temp", "wn.610.gpu", "wn.610.info"],
    "6.9": ["wn.69.honest", "wn.69.removed", "wn.69.rollback", "wn.69.fast"],
    "6.8.1": ["wn.681.nvpair", "wn.681.check"],
    "6.8": ["wn.68.hwc", "wn.68.overlay", "wn.68.gpu", "wn.68.buy", "wn.68.diag"],
    "6.7": ["wn.67.safe", "wn.67.portable", "wn.67.fast"],
    "6.6": ["wn.66.crash", "wn.66.library", "wn.66.simple", "wn.66.phone", "wn.66.transfer", "wn.66.bug"],
    "6.5": ["wn.65.renderer", "wn.65.check", "wn.65.diag", "wn.65.booster"],
}


def notes(version: str = None) -> list:
    return list(NOTES.get(version or E.VERSION, []))


def pending() -> str:
    """Версія, про яку ще не розповіли, або "". Під час першого запуску — просто запам'ятовує поточну."""
    seen = F.CFG["seen_version"]
    if seen == E.VERSION:
        return ""
    if F.CFG["first_run"] or not notes():
        F.CFG["seen_version"] = E.VERSION
        return ""
    return E.VERSION


def mark_seen() -> None:
    F.CFG["seen_version"] = E.VERSION
