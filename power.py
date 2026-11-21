"""
OptimaX — ноутбуки: частота екрана залежно від живлення (на батареї 60 Гц, від мережі максимум)
та ліміт заряду батареї там, де виробник дає таку можливість через Windows.
"""
from __future__ import annotations

import ctypes
import os

import engine as E
import secfs as SF
from i18n import tr

DM_DISPLAYFREQUENCY = 0x400000
CDS_UPDATEREGISTRY = 0x1

_demo = {"ac": True, "hz": 144}


def on_ac() -> bool:
    if not E.IS_WIN:
        return _demo["ac"]

    class SPS(ctypes.Structure):
        _fields_ = [("AC", ctypes.c_ubyte), ("Flag", ctypes.c_ubyte), ("Pct", ctypes.c_ubyte),
                    ("Saver", ctypes.c_ubyte), ("Life", ctypes.c_ulong), ("Full", ctypes.c_ulong)]
    s = SPS()
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
        return s.AC != 0
    return True


def rates() -> list:
    """Частоти, доступні для поточної роздільності основного монітора, від меншої до більшої."""
    if not E.IS_WIN:
        return [60, 120, 144]
    import hardware as H
    u = ctypes.windll.user32
    cur = H.DEVMODEW()
    cur.dmSize = ctypes.sizeof(cur)
    if not u.EnumDisplaySettingsW(None, -1, ctypes.byref(cur)):
        return []
    out, i = set(), 0
    m = H.DEVMODEW()
    m.dmSize = ctypes.sizeof(m)
    while u.EnumDisplaySettingsW(None, i, ctypes.byref(m)) and i < 2000:
        if m.dmPelsWidth == cur.dmPelsWidth and m.dmPelsHeight == cur.dmPelsHeight and m.dmDisplayFrequency > 1:
            out.add(m.dmDisplayFrequency)
        i += 1
    return sorted(out)


def current_rate() -> int:
    if not E.IS_WIN:
        return _demo["hz"]
    import hardware as H
    return H.refresh_rates()[0]


def set_rate(hz: int) -> bool:
    if not E.IS_WIN:
        _demo["hz"] = hz
        return True
    if E.DRY_RUN:
        return True
    import hardware as H
    u = ctypes.windll.user32
    dm = H.DEVMODEW()
    dm.dmSize = ctypes.sizeof(dm)
    if not u.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
        return False
    dm.dmDisplayFrequency = hz
    dm.dmFields = DM_DISPLAYFREQUENCY
    return u.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, CDS_UPDATEREGISTRY, None) == 0


class RefreshByPower:
    """Перемикає частоту екрана, коли ноутбук підключають до зарядки або відключають від неї."""

    def __init__(self):
        self.last = None

    def tick(self, cfg: dict, log) -> None:
        if not cfg.get("enabled"):
            self.last = None
            return
        ac = on_ac()
        if ac == self.last:
            return
        self.last = ac
        avail = rates()
        if not avail:
            return
        if ac:
            target = max(avail)
        else:
            want = int(cfg.get("battery_hz") or 60)
            target = min([r for r in avail if r >= want] or [min(avail)])
        if target != current_rate() and set_rate(target):
            log(tr("rfp.switched", hz=target, src=tr("rfp.ac" if ac else "rfp.dc")))


# ───────────────────────── ліміт заряду ─────────────────────────
ASUS_DEV = 0x00120057
# 7.1.1: cctk.exe — лише в Program Files (шлях із Windows API, а не з %ProgramFiles%, який користувач може
# перевизначити): OptimaX запускає його з правами адміністратора
CCTK_REL = os.path.join("Dell", "Command Configure", "X86_64", "cctk.exe")
METHODS = ("asus", "dell")
VENDOR_HINTS = [("lenovo", "lenovo"), ("hp", "hp"), ("hewlett", "hp"), ("micro-star", "msi"), ("msi", "msi"),
                ("huawei", "huawei"), ("honor", "huawei"), ("samsung", "samsung"), ("acer", "acer"),
                ("gigabyte", "gigabyte"), ("aorus", "gigabyte"), ("microsoft", "surface"), ("razer", "razer"),
                ("xiaomi", "xiaomi"), ("timi", "xiaomi"), ("dell", "dell"), ("asus", "asus")]


def _cctk():
    for pf in SF.program_files_dirs():
        p = os.path.join(pf, CCTK_REL)
        if os.path.isfile(p) and SF.trusted_location(p):
            return p
    return None


def vendor_key(hw: dict) -> str:
    v = (hw.get("vendor") or "").lower()
    return next((k for w, k in VENDOR_HINTS if w in v), "other")


def _asus_wmi() -> bool:
    rc, out = E.ps("[bool](Get-CimInstance -Namespace root/wmi -ClassName AsusAtkWmi_WMNB -ErrorAction "
                   "SilentlyContinue)", 20, ro=True)
    return out.strip().lower() == "true"


def method_available(method: str) -> bool:
    """7.1.1: спосіб зміни ліміту справді є на цьому ПК (не з settings.json на віру)."""
    if method == "asus":
        return not E.IS_WIN or _asus_wmi()
    if method == "dell":
        return _cctk() is not None
    return False


def charge_method(hw: dict):
    """-> 'asus' | 'dell' | None (лише підказка, де шукати налаштування у фірмовій утиліті)."""
    vk = vendor_key(hw)
    if vk == "asus":
        if not E.IS_WIN:
            return "asus"
        return "asus" if _asus_wmi() else None
    if vk == "dell" and _cctk():
        return "dell"
    return None


def set_charge_limit(method: str, pct: int, log) -> dict:
    # 7.1.1: відсоток приходить і з settings.json — у команду PowerShell / cctk лише ціле число з допустимого діапазону
    try:
        pct = max(50, min(100, int(pct)))
    except (TypeError, ValueError):
        return {"ok": False}
    if method == "asus":
        rc, out = E.ps("Get-CimInstance -Namespace root/wmi -ClassName AsusAtkWmi_WMNB | Invoke-CimMethod -MethodName "
                       f"DEVS -Arguments @{{Device_ID=[uint32]{ASUS_DEV}; Control_status=[uint32]{pct}}}", 30, log)
    elif method == "dell" and _cctk():
        arg = "Standard" if pct >= 100 else f"Custom:50-{pct}"
        rc, out = E.run([_cctk(), f"--PrimaryBattChargeCfg={arg}"], 30, log)
    else:
        return {"ok": False}
    ok = rc == 0
    log(tr("chg.limit_set", pct=pct) if ok else tr("chg.limit_fail", msg=E.first_line(out, 80)))
    return {"ok": ok}
