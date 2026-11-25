"""
OptimaX — «Миша»: частота опитування, налаштування вказівника Windows і перерахунок чутливості між іграми.

Тут лише логіка без інтерфейсу (інтерфейс — pages_mouse.py):
• poll_stats() — чиста статистика за мітками часу подій руху з Raw Input: середня й медіанна частота, стабільність,
  найближча стандартна частота. Паузи (миша стоїть) відкидаються; замало подій — так і кажемо, без вигаданої цифри.
• RawMouse — реєстрація Raw Input (RegisterRawInputDevices) і розбір WM_INPUT (GetRawInputData). Лише читання: нічого в
  системі не змінює, після тесту реєстрацію знімаємо.
• read_settings() / parse_settings() — швидкість вказівника й «Підвищена точність» з HKCU\\Control Panel\\Mouse
  (лише читання). Змінює їх тільки твік disable_mouse_accel через журнал відкату.
• cm360() / convert() — сантиметри на оберт 360° і чутливість для іншої гри за кутом повороту на одиницю руху (yaw).
"""
from __future__ import annotations

import ctypes
import math
import random
import time

import engine as E

MOUSE_KEY = r"HKCU\Control Panel\Mouse"
SETTING_NAMES = ("MouseSensitivity", "MouseSpeed", "MouseThreshold1", "MouseThreshold2")
ACCEL_TWEAK = "disable_mouse_accel"  # швидкість 10 + прискорення вимкнено, з повним відкатом (engine.py)
REC_SPEED = 10  # 6-та поділка з 11 — множник 1.0: один відлік миші = один піксель

# ───────────────────────── частота опитування ─────────────────────────
STANDARD = (125, 250, 500, 1000, 2000, 4000, 8000)
IDLE_GAP = 0.02  # с: довша пауза між подіями — миша стояла (125 Гц — це 8 мс), такий проміжок не рахуємо
WINDOW = 0.1  # с: частоту рахуємо по вікнах безперервного руху — медіана вікон стійка до поодиноких збоїв
MIN_EVENTS = 150
MIN_ACTIVE = 0.5  # с безперервного руху
MIN_WINDOWS = 3
STABLE_BAND = 0.10  # вікно «стабільне», якщо його частота в межах ±10 % від медіани


def _median(xs: list) -> float:
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def nearest_standard(hz: float) -> int:
    """Найближча стандартна частота — за відношенням (лог-шкала), бо стандарти йдуть удвічі."""
    if not hz or hz <= 0:
        return 0
    return min(STANDARD, key=lambda r: abs(math.log(hz / r)))


def poll_stats(times) -> dict:
    """times — мітки часу подій руху в секундах (будь-якого початку відліку).
    -> {"ok": True, avg_hz, median_hz, stability, nearest, low, events, active_s, windows, idle}
       або {"ok": False, "reason": "few", events, active_s} — замало безперервного руху для чесної цифри."""
    ts = sorted(float(t) for t in times)
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    active, rates, idle = [], [], 0
    acc_n, acc_d = 0, 0.0
    for g in gaps:
        if g > IDLE_GAP:  # пауза: незавершене вікно відкидаємо, щоб не змішувати рух і спокій
            idle += 1
            acc_n, acc_d = 0, 0.0
            continue
        active.append(g)
        acc_n += 1
        acc_d += g
        if acc_d >= WINDOW:
            rates.append(acc_n / acc_d)
            acc_n, acc_d = 0, 0.0
    total = sum(active)
    base = {"events": len(ts), "active_s": round(total, 3), "idle": idle}
    if len(active) < MIN_EVENTS or total < MIN_ACTIVE or len(rates) < MIN_WINDOWS:
        return dict(base, ok=False, reason="few")
    avg = len(active) / total
    med = _median(rates)
    stable = sum(1 for r in rates if abs(r - med) <= STABLE_BAND * med) / len(rates)
    near = nearest_standard(med)
    return dict(base, ok=True, avg_hz=round(avg), median_hz=round(med), stability=round(stable * 100),
                nearest=near, low=med < near * 0.8, windows=len(rates))


def demo_stream(rate: int = 1000, seconds: float = 6.0, seed: int = 7, jitter: float = 0.04) -> list:
    """Імітація потоку подій для демо-режиму й тестів: рух із невеликим тремтінням інтервалу і двома паузами."""
    rnd = random.Random(seed)
    out, t, step = [], 0.0, 1.0 / rate
    pauses = (seconds * 0.35, seconds * 0.7)
    while t < seconds:
        out.append(t)
        t += step * (1 + rnd.uniform(-jitter, jitter))
        for p in pauses:
            if p <= t < p + step * 1.5:
                t += 0.3  # користувач на мить зупинив мишу
    return out


def demo_rate() -> int:
    return {"old": 125, "laptop": 500}.get(E.DEMO, 1000)


# ───────────────────────── Raw Input (лише Windows) ─────────────────────────
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RIDEV_REMOVE = 0x00000001
RIDEV_INPUTSINK = 0x00000100
MOUSE_MOVE_ABSOLUTE = 0x01


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", ctypes.c_ushort), ("usUsage", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                ("hwndTarget", ctypes.c_void_p)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", ctypes.c_ulong), ("dwSize", ctypes.c_ulong), ("hDevice", ctypes.c_void_p),
                ("wParam", ctypes.c_size_t)]


class RAWMOUSE(ctypes.Structure):  # union кнопок спрощено до ULONG — розмір і вирівнювання ті самі
    _fields_ = [("usFlags", ctypes.c_ushort), ("ulButtons", ctypes.c_ulong), ("ulRawButtons", ctypes.c_ulong),
                ("lLastX", ctypes.c_long), ("lLastY", ctypes.c_long), ("ulExtraInformation", ctypes.c_ulong)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE), ("_pad", ctypes.c_byte * 32)]


class RawMouse:
    """Події руху миші з Raw Input: мітка часу (perf_counter — QueryPerformanceCounter) для кожного пристрою окремо.
    Події надходять у вікно hwnd як WM_INPUT; їх передає сюди фільтр нативних подій Qt (pages_mouse.py)."""

    def __init__(self):
        self.devices: dict = {}
        self.absolute = 0  # події з абсолютними координатами (віддалений стіл, віртуальна машина, планшет)
        self.registered = False
        self.error = ""
        self._buf = RAWINPUT()
        self._size = ctypes.c_uint(0)
        self._u = None

    def start(self, hwnd: int) -> bool:
        try:
            u = ctypes.windll.user32
            u.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), ctypes.c_uint, ctypes.c_uint]
            u.RegisterRawInputDevices.restype = ctypes.c_int
            u.GetRawInputData.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
                                          ctypes.POINTER(ctypes.c_uint), ctypes.c_uint]
            u.GetRawInputData.restype = ctypes.c_uint
            dev = RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, hwnd)  # Generic Desktop / Mouse
            if not u.RegisterRawInputDevices(ctypes.byref(dev), 1, ctypes.sizeof(dev)):
                self.error = f"RegisterRawInputDevices: {ctypes.GetLastError()}"
                return False
            self._u = u
            self.registered = True
            return True
        except (AttributeError, OSError) as e:
            self.error = str(e)
            return False

    def stop(self) -> None:
        if not self.registered:
            return
        self.registered = False
        try:
            dev = RAWINPUTDEVICE(0x01, 0x02, RIDEV_REMOVE, None)
            self._u.RegisterRawInputDevices(ctypes.byref(dev), 1, ctypes.sizeof(dev))
        except (AttributeError, OSError):
            pass

    def on_input(self, lparam: int, now: float = None) -> bool:
        """Одна подія WM_INPUT. True — це рух миші (зараховано)."""
        now = time.perf_counter() if now is None else now
        if not self.registered:
            return False
        self._size.value = ctypes.sizeof(self._buf)
        n = self._u.GetRawInputData(ctypes.c_void_p(lparam & 0xFFFFFFFFFFFFFFFF), RID_INPUT, ctypes.byref(self._buf),
                                    ctypes.byref(self._size), ctypes.sizeof(RAWINPUTHEADER))
        if n == 0xFFFFFFFF or n < ctypes.sizeof(RAWINPUTHEADER) or self._buf.header.dwType != RIM_TYPEMOUSE:
            return False
        m = self._buf.mouse
        if m.usFlags & MOUSE_MOVE_ABSOLUTE:
            self.absolute += 1
            return False
        if not (m.lLastX or m.lLastY):  # лише кнопка чи колесо
            return False
        self.devices.setdefault(self._buf.header.hDevice or 0, []).append(now)
        return True

    def main_stream(self) -> list:
        """Мітки пристрою з найбільшою кількістю подій (дві миші разом дали б подвійну «частоту»)."""
        return max(self.devices.values(), key=len) if self.devices else []

    def count(self) -> int:
        return sum(len(v) for v in self.devices.values())


# ───────────────────────── налаштування вказівника Windows ─────────────────────────
# Множник швидкості вказівника при вимкненій «Підвищеній точності» (Microsoft, «Pointer ballistics»; таблиця MarkC):
# 1 → 1/32, 2 → 1/16, 3 → 1/8, далі по 1/8 до 10 → 1.0, вище 10 — по 0.25 до 20 → 3.5.
def speed_multiplier(v: int) -> float:
    if v <= 2:
        return (1 / 32) if v <= 1 else (1 / 16)
    if v <= 10:
        return (v - 2) / 8
    return 1 + (v - 10) * 0.25


def notch(v: int) -> int:
    """Поділка повзунка «Швидкість вказівника» (1–11); непарні значення — між поділками, ставить лише реєстр."""
    return v // 2 + 1


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def parse_settings(raw: dict) -> dict:
    """raw — {назва: рядок із реєстру або None}. -> швидкість, поділка, множник, прискорення й висновок."""
    sp = _int(raw.get("MouseSensitivity"))
    if sp is not None and not 1 <= sp <= 20:
        sp = None
    ms, t1, t2 = (_int(raw.get(n)) for n in ("MouseSpeed", "MouseThreshold1", "MouseThreshold2"))
    accel = None if ms is None else ms != 0  # MouseSpeed 0 — вимкнено; 1 — «Підвищена точність»; 2 — стара подвійна
    return {"speed": sp, "notch": notch(sp) if sp else None, "mult": speed_multiplier(sp) if sp else None,
            "accel": accel, "mouse_speed": ms, "t1": t1, "t2": t2,
            "speed_ok": sp == REC_SPEED, "accel_ok": accel is False,
            "ok": sp == REC_SPEED and accel is False}


def _demo_raw() -> dict:
    if E.JOURNAL.has(ACCEL_TWEAK):  # режим перегляду: показати, що записав би твік
        return {"MouseSensitivity": "10", "MouseSpeed": "0", "MouseThreshold1": "0", "MouseThreshold2": "0"}
    sp = {"old": "14", "laptop": "12"}.get(E.DEMO, "10")
    return {"MouseSensitivity": sp, "MouseSpeed": "1", "MouseThreshold1": "6", "MouseThreshold2": "10"}


def read_settings() -> dict:
    """Лише читання реєстру поточного користувача; поза Windows — демо-значення."""
    if not E.IS_WIN:
        return parse_settings(_demo_raw())
    raw = {}
    for n in SETTING_NAMES:
        v = E.reg_get(MOUSE_KEY, n)
        raw[n] = v[1] if v else None
    return parse_settings(raw)


# ───────────────────────── перерахунок чутливості ─────────────────────────
# Кут повороту камери (градуси) на одну одиницю руху миші при чутливості 1.0 — лише ігри з точно відомим значенням
# (огляд без прицілювання й без масштабу). Сумнівні ігри навмисно не додано.
GAMES = {
    "cs2": ("Counter-Strike 2", 0.022),  # m_yaw 0.022 (Source 2)
    "csgo": ("CS:GO", 0.022),  # m_yaw 0.022 (Source)
    "apex": ("Apex Legends", 0.022),  # m_yaw 0.022 (Source)
    "tf2": ("Team Fortress 2", 0.022),  # m_yaw 0.022 (Source)
    "quake": ("Quake Live", 0.022),  # m_yaw 0.022 (id Tech 3)
    "valorant": ("Valorant", 0.07),  # 0.07: чутливість CS ÷ 3.18
    "ow2": ("Overwatch 2", 0.0066),  # 0.0066: чутливість CS × 3.33
}
CM_PER_INCH = 2.54


def cm360(dpi: float, sens: float, yaw: float) -> float:
    """Сантиметри руху миші на повний оберт 360°. 0 — якщо дані неповні."""
    if dpi <= 0 or sens <= 0 or yaw <= 0:
        return 0.0
    return 360.0 / (yaw * sens * dpi) * CM_PER_INCH


def sens_for_cm(dpi: float, cm: float, yaw: float) -> float:
    if dpi <= 0 or cm <= 0 or yaw <= 0:
        return 0.0
    return 360.0 * CM_PER_INCH / (yaw * cm * dpi)


def convert(dpi: float, sens: float, src: str, dst: str, dst_dpi: float = None) -> dict:
    """Та сама відстань на оберт 360° в іншій грі (і, за бажанням, з іншим DPI)."""
    dst_dpi = dst_dpi or dpi
    cm = cm360(dpi, sens, GAMES[src][1])
    out = sens_for_cm(dst_dpi, cm, GAMES[dst][1]) if cm else 0.0
    return {"cm360": cm, "in360": cm / CM_PER_INCH if cm else 0.0, "sens": out, "edpi": dpi * sens,
            "dst_edpi": dst_dpi * out}
