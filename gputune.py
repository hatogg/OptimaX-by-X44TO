"""
OptimaX — керування відеокартою: кулери й андервольт через офіційні бібліотеки виробників, без драйвера ядра.

• NVIDIA — NVML (nvml.dll, ставиться разом із драйвером): швидкість вентиляторів (крива OptimaX або фіксована),
  ліміт потужності, обмеження частоти ядра й зсув кривої частота-напруга. Андервольт = обмеження частоти + зсув
  угору: та сама частота при меншій напрузі (так само роблять «плоскою» криву в MSI Afterburner). Саму криву NVIDIA
  відкриває лише недокументованими функціями — їх OptimaX не використовує.
• AMD — ADLX (amdadlx64.dll, ставиться з драйвером Adrenalin): крива вентилятора (точки «температура → швидкість»,
  виконує сам драйвер), ліміт потужності, максимальна частота й напруга (RDNA 2 і новіші).
• Intel та інші — нічого не змінюємо й кажемо чому.

Безпека (те, без чого цього розділу не було б):
• Нічого не змінюється без «Застосувати». Перед першою зміною запам'ятовуємо заводські значення; «Скинути», відкат
  у журналі OptimaX і OptimaX-Rescue.cmd повертають саме їх (запис журналу — OptimaX.exe --gpu-reset).
• Крива вентиляторів NVIDIA працює, поки працює OptimaX. Якщо програма закриється чи впаде, сторожовий процес
  поверне вентилятори драйверу. Від FAN_FORCE_TEMP °C вентилятори на 100 % незалежно від кривої; нижче FAN_MIN_SAFE %
  крива не опускається.
• Перед зміною частоти чи напруги ставимо позначку «перевіряється». Якщо програма чи система впала, поки позначка
  стоїть, під час наступного запуску OptimaX повертає заводські значення й не застосовує профіль автоматично.
• Автопідбір андервольту: кожен крок — стрес-тест відеокарти з порівнянням контрольного кадру до біта; помилка чи
  збій — відступ на TUNE_BACKOFF_STEPS кроки й фінальна перевірка.
• NVIDIA скидає ці налаштування після перезавантаження; «застосовувати під час запуску» дозволено лише профілю, який
  пройшов перевірку стабільності.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time

import engine as E
from i18n import tr

FAN_MIN_SAFE = 30          # % — нижче крива OptimaX не опускається (тиша нижче — лише в режимі «Авто» драйвера)
FAN_FORCE_TEMP = 85        # °C — від цієї температури вентилятори на 100 % незалежно від кривої
FAN_HYST = 3               # °C — знижуємо швидкість, лише коли стало холодніше на стільки
FAN_STEP_MIN = 2           # % — дрібніші зміни драйверу не надсилаємо
FAN_TICK = 1.0             # с між оновленнями кривої
FAN_FAILS = 3              # стільки помилок поспіль — і вентилятори повертаються драйверу
CURVE_PRESETS = {"quiet": [(40, 30), (60, 40), (70, 55), (78, 75), (85, 100)],
                 "balanced": [(40, 35), (55, 45), (65, 60), (75, 80), (85, 100)],
                 "cool": [(35, 40), (50, 55), (60, 70), (70, 90), (80, 100)]}
POWER_MIN_PCT = 50         # ліміт потужності — не нижче половини стандартного, хоч би що дозволяв драйвер
CONFIRM_SECONDS = 180      # стільки працювати без збою після зміни частоти/напруги, щоб зняти позначку «перевіряється»
TUNE_STEP_MHZ = 30         # NVIDIA: крок зсуву частоти під час автопідбору
TUNE_STEP_MV = 10          # AMD: крок зниження напруги
TUNE_STEP_SECONDS = 90     # стрес-тест на кожному кроці
TUNE_VERIFY_SECONDS = 300  # фінальна перевірка
TUNE_BACKOFF_STEPS = 2     # запас стабільності: на стільки кроків назад від першого збою
TUNE_MAX_STEPS = 12
VENDOR_NAMES = {"nvidia": "NVIDIA", "amd": "AMD"}


# ───────────────────────── крива вентиляторів ─────────────────────────
def curve_normalize(points) -> list:
    """[(°C, %)] -> відсортовані точки або ValueError: щонайменше 2 точки, температури 20…100 різні, швидкість 0…100
    і не спадає з температурою."""
    try:
        pts = sorted((int(round(float(t))), int(round(float(s)))) for t, s in points)
    except (TypeError, ValueError):
        raise ValueError("curve")
    if len(pts) < 2 or len({t for t, _ in pts}) != len(pts):
        raise ValueError("curve")
    for (t, s) in pts:
        if not (20 <= t <= 100 and 0 <= s <= 100):
            raise ValueError("curve")
    if any(b[1] < a[1] for a, b in zip(pts, pts[1:])):
        raise ValueError("curve")
    return pts


def curve_speed(points, temp: float) -> float:
    """Лінійна інтерполяція між точками; нижче першої — швидкість першої, вище останньої — останньої."""
    pts = list(points)
    if temp <= pts[0][0]:
        return float(pts[0][1])
    for (t0, s0), (t1, s1) in zip(pts, pts[1:]):
        if temp <= t1:
            return s0 + (s1 - s0) * (temp - t0) / float(t1 - t0)
    return float(pts[-1][1])


class FanCurve:
    """Крива з гістерезисом і запобіжниками: від FAN_FORCE_TEMP — 100 %, не нижче FAN_MIN_SAFE і меж драйвера; вгору —
    одразу, вниз — лише коли охололо на FAN_HYST °C від температури, за якої швидкість востаннє підняли."""

    def __init__(self, points, lo: int = 0, hi: int = 100):
        self.points = curve_normalize(points)
        self.lo, self.hi = max(0, int(lo)), min(100, int(hi or 100))
        self.speed = None
        self.temp_at = None

    def target(self, temp: float) -> int:
        if temp is None:
            return self.hi  # датчик не відповів — безпечніше на повну
        want = 100.0 if temp >= FAN_FORCE_TEMP else max(curve_speed(self.points, temp), FAN_MIN_SAFE)
        want = int(round(min(self.hi, max(self.lo, want))))
        if self.speed is not None and want < self.speed and temp > (self.temp_at or temp) - FAN_HYST:
            return self.speed
        return want

    def update(self, temp: float):
        """-> нова швидкість, якщо її треба надіслати драйверу, інакше None. Дрібні зміни (менше FAN_STEP_MIN) не
        надсилаємо, крім виходу на межу (мінімум, максимум, 100 %)."""
        want = self.target(temp)
        if self.speed is not None:
            if want == self.speed:
                return None
            if abs(want - self.speed) < FAN_STEP_MIN and want not in (self.lo, self.hi, 100):
                return None
        self.speed, self.temp_at = want, temp
        return want


def resample(points, temps) -> list:
    """Крива OptimaX -> точки драйвера AMD (у нього їх фіксована кількість) за заданими температурами."""
    pts = curve_normalize(points)
    out = []
    for t in temps:
        s = 100 if t >= FAN_FORCE_TEMP else max(FAN_MIN_SAFE, curve_speed(pts, t))
        out.append((int(t), int(round(min(100, s)))))
    for i in range(1, len(out)):  # не спадає
        if out[i][1] < out[i - 1][1]:
            out[i] = (out[i][0], out[i - 1][1])
    return out


def spread_temps(lo: int, hi: int, n: int, first: int = 40, last: int = FAN_FORCE_TEMP) -> list:
    """n температур для точок драйвера між first і last у межах, які дозволяє драйвер."""
    a, b = max(lo, first), min(hi, last)
    if n <= 1 or b <= a:
        return [a] * max(1, n)
    return [int(round(a + (b - a) * i / (n - 1))) for i in range(n)]


# ───────────────────────── бекенди ─────────────────────────
class Tuner:
    """Спільний вигляд будь-якої відеокарти. caps — що вміє, why — чому ні (ключі рядків)."""

    vendor = ""

    def __init__(self):
        self.name = ""
        self.index = 0
        self.caps = {}
        self.why = {}
        self.last_error = ""

    @property
    def key(self) -> str:
        return f"{self.vendor}:{self.index}:{self.name}"

    def ok(self) -> bool:
        return bool(self.name)

    def read(self) -> dict:
        return {}

    def snapshot(self) -> dict:
        """Поточні значення всього, що OptimaX може змінити, — щоб потім повернути саме їх."""
        return {}

    def restore(self, snap: dict) -> bool:
        return True

    def reset(self) -> bool:
        return True

    def fan_set(self, pct: int) -> bool:
        return False

    def fan_auto(self) -> bool:
        return True

    def fan_curve_native(self, points) -> bool:
        return False

    def power_set(self, value: int) -> bool:
        return False

    def clock_cap(self, mhz) -> bool:
        return False

    def offset_set(self, mhz: int) -> bool:
        return False

    def voltage_set(self, mv: int) -> bool:
        return False

    def close(self) -> None:
        pass


# ── NVIDIA: NVML ──
NVML_OK, NVML_NOT_SUPPORTED, NVML_NO_PERMISSION, NVML_NO_FUNCTION = 0, 3, 4, 13
NVML_CLOCK_GRAPHICS = 0
NVML_FAN_AUTO, NVML_FAN_MANUAL = 0, 1
NVML_CLOCK_OFFSET_V1 = 0x1000018
NVML_FAN_SPEED_INFO_V1 = 0x100000C


class _ClockOffset(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint), ("type", ctypes.c_uint), ("pstate", ctypes.c_uint),
                ("clockOffsetMHz", ctypes.c_int), ("minClockOffsetMHz", ctypes.c_int),
                ("maxClockOffsetMHz", ctypes.c_int)]


class _FanSpeedInfo(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint), ("fan", ctypes.c_uint), ("speed", ctypes.c_uint)]


def nvml_why(rc: int) -> str:
    return {NVML_NOT_SUPPORTED: "gt.why.unsupported", NVML_NO_PERMISSION: "gt.why.admin",
            NVML_NO_FUNCTION: "gt.why.old_driver"}.get(rc, "gt.why.error")


class NvmlTuner(Tuner):
    """NVIDIA через NVML. Кожен виклик повертає код NVML; «не підтримується» для конкретної функції вимикає лише її."""

    vendor = "nvidia"

    def __init__(self, name: str = ""):
        super().__init__()
        import gpubench as GB
        self.nv = GB.Nvml(name)
        if not self.nv.ok:
            return
        self.lib, self.h, self.index = self.nv.lib, self.nv.h, self.nv.index
        self.name = self.nv.name()
        self._probe()

    def _fn(self, name: str):
        return getattr(self.lib, name, None)

    def _call(self, name: str, *args) -> int:
        fn = self._fn(name)
        if fn is None:
            return NVML_NO_FUNCTION
        try:
            return int(fn(self.h, *args))
        except Exception:
            return -1

    def _u(self, name: str, *pre):
        v = ctypes.c_uint(0)
        rc = self._call(name, *pre, ctypes.byref(v))
        return (int(v.value) if rc == NVML_OK else None), rc

    def _probe(self) -> None:
        c, why = {}, {}
        n, rc = self._u("nvmlDeviceGetNumFans")
        if n:
            lo, hi = ctypes.c_uint(0), ctypes.c_uint(100)
            if self._call("nvmlDeviceGetMinMaxFanSpeed", ctypes.byref(lo), ctypes.byref(hi)) != NVML_OK:
                lo, hi = ctypes.c_uint(0), ctypes.c_uint(100)
            pol, prc = self._u("nvmlDeviceGetFanControlPolicy_v2", 0)
            c["fan"] = dict(count=n, min=int(lo.value), max=int(hi.value) or 100, mode="manual",
                            auto=pol in (None, NVML_FAN_AUTO))
            if self._fn("nvmlDeviceSetFanSpeed_v2") is None:
                del c["fan"]
                why["fan"] = "gt.why.old_driver"
        else:
            why["fan"] = "gt.why.no_fans" if rc == NVML_OK else nvml_why(rc)
        lo, hi = ctypes.c_uint(0), ctypes.c_uint(0)
        rc = self._call("nvmlDeviceGetPowerManagementLimitConstraints", ctypes.byref(lo), ctypes.byref(hi))
        dflt, _ = self._u("nvmlDeviceGetPowerManagementDefaultLimit")
        cur, _ = self._u("nvmlDeviceGetPowerManagementLimit")
        if rc == NVML_OK and hi.value and dflt:
            floor = max(int(lo.value), int(dflt * POWER_MIN_PCT / 100))
            c["power"] = dict(unit="W", min=round(floor / 1000), max=round(hi.value / 1000), default=round(dflt / 1000),
                              cur=round((cur or dflt) / 1000))
            if c["power"]["max"] <= c["power"]["min"]:
                del c["power"]
                why["power"] = "gt.why.locked"
        else:
            why["power"] = nvml_why(rc)
        mx, rc = self._u("nvmlDeviceGetMaxClockInfo", NVML_CLOCK_GRAPHICS)
        if mx and self._fn("nvmlDeviceSetGpuLockedClocks"):
            c["clock"] = dict(max=mx, min=min(300, mx), cur=None)
        else:
            why["clock"] = nvml_why(rc if not mx else NVML_NO_FUNCTION)
        rng = self._offset_range()
        if rng:
            c["offset"] = dict(min=rng[0], max=rng[1], cur=self._offset_get() or 0)
        else:
            why["offset"] = "gt.why.unsupported"
        why["voltage"] = "gt.why.nv_voltage"
        self.caps, self.why = c, why

    # зсув кривої частота-напруга: новіша функція (R555+) або старша
    def _offset_range(self):
        lo, hi = ctypes.c_int(0), ctypes.c_int(0)
        if self._call("nvmlDeviceGetGpcClkMinMaxVfOffset", ctypes.byref(lo), ctypes.byref(hi)) == NVML_OK \
                and hi.value > lo.value:
            return int(lo.value), int(hi.value)
        info = _ClockOffset(NVML_CLOCK_OFFSET_V1, NVML_CLOCK_GRAPHICS, 0, 0, 0, 0)
        if self._call("nvmlDeviceGetClockOffsets", ctypes.byref(info)) == NVML_OK \
                and info.maxClockOffsetMHz > info.minClockOffsetMHz:
            return int(info.minClockOffsetMHz), int(info.maxClockOffsetMHz)
        return None

    def _offset_get(self):
        v = ctypes.c_int(0)
        if self._call("nvmlDeviceGetGpcClkVfOffset", ctypes.byref(v)) == NVML_OK:
            return int(v.value)
        info = _ClockOffset(NVML_CLOCK_OFFSET_V1, NVML_CLOCK_GRAPHICS, 0, 0, 0, 0)
        if self._call("nvmlDeviceGetClockOffsets", ctypes.byref(info)) == NVML_OK:
            return int(info.clockOffsetMHz)
        return None

    def read(self) -> dict:
        out = dict(self.nv.read()) if self.nv.ok else {}
        fan = self.caps.get("fan")
        if fan:
            speeds = [self._u("nvmlDeviceGetFanSpeed_v2", i)[0] for i in range(fan["count"])]
            speeds = [s for s in speeds if s is not None]
            if speeds:
                out["fan"] = round(sum(speeds) / len(speeds))
            info = _FanSpeedInfo(NVML_FAN_SPEED_INFO_V1, 0, 0)
            if self._call("nvmlDeviceGetFanSpeedRPM", ctypes.byref(info)) == NVML_OK:
                out["rpm"] = int(info.speed)
            pol, _ = self._u("nvmlDeviceGetFanControlPolicy_v2", 0)
            if pol is not None:
                out["fan_auto"] = pol == NVML_FAN_AUTO
        cur, _ = self._u("nvmlDeviceGetPowerManagementLimit")
        if cur:
            out["power_limit"] = round(cur / 1000)
        off = self._offset_get() if "offset" in self.caps else None
        if off is not None:
            out["offset"] = off
        return out

    def _err(self, what: str, rc: int) -> bool:
        if rc != NVML_OK:
            self.last_error = f"{what}: {tr(nvml_why(rc))} ({rc})"
            if rc in (NVML_NOT_SUPPORTED, NVML_NO_FUNCTION) and what in self.caps:
                self.caps.pop(what, None)
                self.why[what] = nvml_why(rc)
        return rc == NVML_OK

    def fan_set(self, pct: int) -> bool:
        fan = self.caps.get("fan")
        if not fan:
            return False
        pct = int(min(fan["max"], max(fan["min"], pct)))
        ok = True
        for i in range(fan["count"]):
            ok = self._err("fan", self._call("nvmlDeviceSetFanSpeed_v2", i, pct)) and ok
        return ok

    def fan_auto(self) -> bool:
        fan = self.caps.get("fan") or {}
        ok = True
        for i in range(fan.get("count") or 0):
            rc = self._call("nvmlDeviceSetDefaultFanSpeed_v2", i)
            # повідомляли, що «типова швидкість» не завжди повертає автоматичну криву — ставимо й саму політику
            rc2 = self._call("nvmlDeviceSetFanControlPolicy", i, NVML_FAN_AUTO)
            ok = ok and (rc == NVML_OK or rc2 == NVML_OK)
        return ok

    def power_set(self, watts: int) -> bool:
        p = self.caps.get("power")
        if not p:
            return False
        w = int(min(p["max"], max(p["min"], watts)))
        if not self._err("power", self._call("nvmlDeviceSetPowerManagementLimit", ctypes.c_uint(w * 1000))):
            return False
        cur, _ = self._u("nvmlDeviceGetPowerManagementLimit")
        return cur is not None and abs(cur / 1000 - w) <= 1

    def clock_cap(self, mhz) -> bool:
        c = self.caps.get("clock")
        if not c:
            return False
        if mhz is None:
            return self._err("clock", self._call("nvmlDeviceResetGpuLockedClocks"))
        mhz = int(min(c["max"], max(c["min"], mhz)))
        return self._err("clock", self._call("nvmlDeviceSetGpuLockedClocks", ctypes.c_uint(c["min"]),
                                             ctypes.c_uint(mhz)))

    def offset_set(self, mhz: int) -> bool:
        o = self.caps.get("offset")
        if not o:
            return False
        mhz = int(min(o["max"], max(o["min"], mhz)))
        rc = self._call("nvmlDeviceSetGpcClkVfOffset", ctypes.c_int(mhz))
        if rc in (NVML_NO_FUNCTION, NVML_NOT_SUPPORTED):
            info = _ClockOffset(NVML_CLOCK_OFFSET_V1, NVML_CLOCK_GRAPHICS, 0, mhz, 0, 0)
            rc = self._call("nvmlDeviceSetClockOffsets", ctypes.byref(info))
        if not self._err("offset", rc):
            return False
        return self._offset_get() == mhz

    def snapshot(self) -> dict:
        r = self.read()
        return dict(power=r.get("power_limit"), offset=r.get("offset"), clock=None)

    def restore(self, snap: dict) -> bool:
        ok = self.fan_auto()
        if "clock" in self.caps:
            ok = self.clock_cap(None) and ok
        if "offset" in self.caps:
            ok = self.offset_set(int(snap.get("offset") or 0)) and ok
        if "power" in self.caps:
            ok = self.power_set(int(snap.get("power") or self.caps["power"]["default"])) and ok
        return ok

    def reset(self) -> bool:
        return self.restore(dict(power=(self.caps.get("power") or {}).get("default"), offset=0))

    def close(self) -> None:
        if getattr(self, "nv", None):
            self.nv.close()


# ── AMD: ADLX ──
ADLX_OK, ADLX_NOT_SUPPORTED, ADLX_RESET_NEEDED = 0, 12, 18
ADLX_OK_CODES = (0, 1)  # ADLX_OK, ADLX_ALREADY_ENABLED


class _IntRange(ctypes.Structure):
    _fields_ = [("minValue", ctypes.c_int), ("maxValue", ctypes.c_int), ("step", ctypes.c_int)]


def _vcall(obj, index: int, restype, argtypes, *args):
    """Виклик методу інтерфейсу ADLX за номером у таблиці методів (порядок — з заголовків ADLX SDK 2.0)."""
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(vtbl[index])(obj, *args)


# номери методів (ADLX SDK 2.0, C-таблиці *Vtbl): система не лічить посилань — у неї GetGPUs = 1
SYS_GET_GPUS, SYS_TUNING, SYS_PERF = 1, 8, 9
I_RELEASE, I_QUERY = 1, 2
LIST_SIZE, GPULIST_AT = 3, 11
GPU_NAME, GPU_UNIQUE_ID = 7, 18
TS_IS_FACTORY, TS_RESET, TS_SUP_GFX, TS_SUP_FAN, TS_SUP_POWER = 4, 5, 8, 10, 11
TS_GET_GFX, TS_GET_FAN, TS_GET_POWER = 14, 16, 17
FAN_RANGES, FAN_STATES, FAN_EMPTY, FAN_VALID, FAN_SET = 3, 4, 5, 6, 7
FAN_SUP_ZERO, FAN_GET_ZERO, FAN_SET_ZERO = 8, 9, 10
FLIST_AT = 11
FSTATE_GET_SPEED, FSTATE_SET_SPEED, FSTATE_GET_TEMP, FSTATE_SET_TEMP = 3, 4, 5, 6
GFX2_MAXF_RANGE, GFX2_MAXF_GET, GFX2_MAXF_SET, GFX2_V_RANGE, GFX2_V_GET, GFX2_V_SET = 6, 7, 8, 9, 10, 11
PWR_RANGE, PWR_GET, PWR_SET = 3, 4, 5
PERF_CUR_GPU = 18
MET_USAGE, MET_CLOCK, MET_TEMP, MET_HOTSPOT, MET_POWER, MET_BOARD_POWER, MET_FAN = 4, 5, 7, 8, 9, 10, 11


class AdlxTuner(Tuner):
    """AMD через ADLX. Крива вентилятора — у драйвері (працює й без OptimaX), тому сторож тут не потрібен."""

    vendor = "amd"

    def __init__(self, name: str = "", index: int = None):
        super().__init__()
        self.dll = self.sys = self.gpu = self.ts = self.fan_i = self.gfx = self.pwr = self.perf = None
        self._refs = []
        if not E.IS_WIN:
            return
        try:
            self.dll = ctypes.CDLL("amdadlx64.dll")
        except OSError:
            return
        try:
            self._init(name, index)
        except Exception as e:  # будь-яка несподіванка ADLX — карта просто «не підтримується», програма живе далі
            self.last_error = f"{type(e).__name__}: {e}"
            self.close()
            self.name = ""

    def _ok(self, rc) -> bool:
        return int(rc) in ADLX_OK_CODES

    def _init(self, want: str, want_index: int = None) -> None:
        ver = ctypes.c_uint64(0)
        q = getattr(self.dll, "ADLXQueryFullVersion", None)
        if q is None or not self._ok(q(ctypes.byref(ver))):
            return
        init = self.dll.ADLXInitialize
        init.argtypes = [ctypes.c_uint64, ctypes.POINTER(ctypes.c_void_p)]
        sysp = ctypes.c_void_p()
        if not self._ok(init(ver.value, ctypes.byref(sysp))) or not sysp:
            return
        self.sys = sysp
        lst = ctypes.c_void_p()
        if not self._ok(_vcall(self.sys, SYS_GET_GPUS, ctypes.c_int, [ctypes.POINTER(ctypes.c_void_p)],
                               ctypes.byref(lst))):
            return
        self._refs.append(lst)
        n = _vcall(lst, LIST_SIZE, ctypes.c_uint, [])
        best = None
        for i in range(min(int(n), 8)):
            g = ctypes.c_void_p()
            if not self._ok(_vcall(lst, GPULIST_AT, ctypes.c_int, [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)],
                                   i, ctypes.byref(g))):
                continue
            self._refs.append(g)
            nm = ctypes.c_char_p()
            _vcall(g, GPU_NAME, ctypes.c_int, [ctypes.POINTER(ctypes.c_char_p)], ctypes.byref(nm))
            name = (nm.value or b"").decode("utf-8", "replace")
            if want_index is not None:
                if i == want_index:
                    best = (i, g, name)
            elif best is None or (want and want.lower() in name.lower()):
                best = (i, g, name)
        if not best:
            return
        self.index, self.gpu, self.name = best
        ts = ctypes.c_void_p()
        if not self._ok(_vcall(self.sys, SYS_TUNING, ctypes.c_int, [ctypes.POINTER(ctypes.c_void_p)],
                               ctypes.byref(ts))):
            self.why = {k: "gt.why.unsupported" for k in ("fan", "power", "clock", "voltage")}
            return
        self.ts = ts
        self._refs.append(ts)
        perf = ctypes.c_void_p()
        if self._ok(_vcall(self.sys, SYS_PERF, ctypes.c_int, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(perf))):
            self.perf = perf
            self._refs.append(perf)
        self._probe()

    def _supported(self, idx: int) -> bool:
        b = ctypes.c_uint8(0)
        return self._ok(_vcall(self.ts, idx, ctypes.c_int, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8)],
                               self.gpu, ctypes.byref(b))) and bool(b.value)

    def _iface(self, getter: int, iid: str):
        base = ctypes.c_void_p()
        if not self._ok(_vcall(self.ts, getter, ctypes.c_int, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                               self.gpu, ctypes.byref(base))) or not base:
            return None
        self._refs.append(base)
        out = ctypes.c_void_p()
        if not self._ok(_vcall(base, I_QUERY, ctypes.c_int, [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)],
                               iid, ctypes.byref(out))) or not out:
            return None
        self._refs.append(out)
        return out

    def _range(self, obj, idx: int):
        r = _IntRange()
        if self._ok(_vcall(obj, idx, ctypes.c_int, [ctypes.POINTER(_IntRange)], ctypes.byref(r))):
            return int(r.minValue), int(r.maxValue), int(r.step or 1)
        return None

    def _geti(self, obj, idx: int):
        v = ctypes.c_int(0)
        return int(v.value) if self._ok(_vcall(obj, idx, ctypes.c_int, [ctypes.POINTER(ctypes.c_int)],
                                               ctypes.byref(v))) else None

    def _seti(self, obj, idx: int, value: int) -> int:
        return int(_vcall(obj, idx, ctypes.c_int, [ctypes.c_int], int(value)))

    def _probe(self) -> None:
        c, why = {}, {}
        if self._supported(TS_SUP_FAN):
            self.fan_i = self._iface(TS_GET_FAN, "IADLXManualFanTuning")
        if self.fan_i:
            sp, tp = _IntRange(), _IntRange()
            if self._ok(_vcall(self.fan_i, FAN_RANGES, ctypes.c_int, [ctypes.POINTER(_IntRange)] * 2,
                               ctypes.byref(sp), ctypes.byref(tp))):
                pts = self._fan_states()
                c["fan"] = dict(count=1, min=int(sp.minValue), max=int(sp.maxValue), tmin=int(tp.minValue),
                                tmax=int(tp.maxValue), points=len(pts), mode="native", auto=None)
        if "fan" not in c:
            why["fan"] = "gt.why.unsupported"
        if self._supported(TS_SUP_POWER):
            self.pwr = self._iface(TS_GET_POWER, "IADLXManualPowerTuning")
        rng = self._range(self.pwr, PWR_RANGE) if self.pwr else None
        if rng:
            c["power"] = dict(unit="%", min=rng[0], max=rng[1], default=0, cur=self._geti(self.pwr, PWR_GET))
        else:
            why["power"] = "gt.why.unsupported"
        if self._supported(TS_SUP_GFX):
            self.gfx = self._iface(TS_GET_GFX, "IADLXManualGraphicsTuning2")
        f = self._range(self.gfx, GFX2_MAXF_RANGE) if self.gfx else None
        v = self._range(self.gfx, GFX2_V_RANGE) if self.gfx else None
        if f:
            c["maxfreq"] = dict(min=f[0], max=f[1], step=f[2], cur=self._geti(self.gfx, GFX2_MAXF_GET))
        else:
            why["clock"] = "gt.why.amd_old" if self._supported(TS_SUP_GFX) else "gt.why.unsupported"
        if v:
            c["voltage"] = dict(min=v[0], max=v[1], step=v[2], cur=self._geti(self.gfx, GFX2_V_GET))
        else:
            why["voltage"] = "gt.why.amd_old" if self._supported(TS_SUP_GFX) else "gt.why.unsupported"
        why["offset"] = "gt.why.amd_offset"
        self.caps, self.why = c, why

    def _fan_states(self) -> list:
        lst = ctypes.c_void_p()
        if not self.fan_i or not self._ok(_vcall(self.fan_i, FAN_STATES, ctypes.c_int,
                                                 [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(lst))):
            return []
        out = []
        try:
            n = int(_vcall(lst, LIST_SIZE, ctypes.c_uint, []))
            for i in range(min(n, 16)):
                st = ctypes.c_void_p()
                if not self._ok(_vcall(lst, FLIST_AT, ctypes.c_int, [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)],
                                       i, ctypes.byref(st))):
                    continue
                t, s = self._geti(st, FSTATE_GET_TEMP), self._geti(st, FSTATE_GET_SPEED)
                _vcall(st, I_RELEASE, ctypes.c_long, [])
                out.append((t, s))
        finally:
            _vcall(lst, I_RELEASE, ctypes.c_long, [])
        return out

    def fan_curve_native(self, points) -> bool:
        """Точки кривої -> стани вентилятора драйвера (стільки ж, скільки їх у драйвера), перевірка драйвером, запис."""
        fan = self.caps.get("fan")
        if not fan:
            return False
        lst = ctypes.c_void_p()
        if not self._ok(_vcall(self.fan_i, FAN_EMPTY, ctypes.c_int, [ctypes.POINTER(ctypes.c_void_p)],
                               ctypes.byref(lst))):
            return False
        try:
            n = int(_vcall(lst, LIST_SIZE, ctypes.c_uint, []))
            pts = resample(points, spread_temps(fan["tmin"], fan["tmax"], n))
            if not n or len(pts) != n:
                return False
            for i, (t, s) in enumerate(pts):
                st = ctypes.c_void_p()
                if not self._ok(_vcall(lst, FLIST_AT, ctypes.c_int, [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)],
                                       i, ctypes.byref(st))):
                    return False
                self._seti(st, FSTATE_SET_TEMP, min(fan["tmax"], max(fan["tmin"], t)))
                self._seti(st, FSTATE_SET_SPEED, min(fan["max"], max(fan["min"], s)))
                _vcall(st, I_RELEASE, ctypes.c_long, [])
            bad = ctypes.c_int(-1)
            if not self._ok(_vcall(self.fan_i, FAN_VALID, ctypes.c_int, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)],
                                   lst, ctypes.byref(bad))):  # драйвер не прийняв точки — нічого не записуємо
                self.last_error = f"fan curve point {bad.value}"
                return False
            rc = int(_vcall(self.fan_i, FAN_SET, ctypes.c_int, [ctypes.c_void_p], lst))
            if rc == ADLX_RESET_NEEDED:
                self.last_error = tr("gt.why.amd_auto")
            return self._ok(rc)
        finally:
            _vcall(lst, I_RELEASE, ctypes.c_long, [])

    def fan_auto(self) -> bool:
        return True  # «Авто» для AMD — повернути заводську криву (restore / reset)

    def power_set(self, pct: int) -> bool:
        p = self.caps.get("power")
        if not p:
            return False
        return self._ok(self._seti(self.pwr, PWR_SET, int(min(p["max"], max(p["min"], pct)))))

    def clock_cap(self, mhz) -> bool:
        """Найвища частота. None — нічого не змінювати: верх діапазону драйвера — це вже розгін, а не заводське
        значення; заводське повертає restore() із запам'ятованого знімка."""
        f = self.caps.get("maxfreq")
        if not f:
            return False
        if mhz is None:
            return True
        return self._ok(self._seti(self.gfx, GFX2_MAXF_SET, int(min(f["max"], max(f["min"], mhz)))))

    def voltage_set(self, mv: int) -> bool:
        v = self.caps.get("voltage")
        if not v:
            return False
        return self._ok(self._seti(self.gfx, GFX2_V_SET, int(min(v["max"], max(v["min"], mv)))))

    def read(self) -> dict:
        out = {}
        if not (self.perf and self.gpu):
            return out
        m = ctypes.c_void_p()
        if not self._ok(_vcall(self.perf, PERF_CUR_GPU, ctypes.c_int, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                               self.gpu, ctypes.byref(m))) or not m:
            return out
        try:
            for key, idx, kind in (("temp", MET_TEMP, "d"), ("hotspot", MET_HOTSPOT, "d"), ("power", MET_POWER, "d"),
                                   ("util", MET_USAGE, "d"), ("clock", MET_CLOCK, "i"), ("rpm", MET_FAN, "i")):
                v = ctypes.c_double(0) if kind == "d" else ctypes.c_int(0)
                if self._ok(_vcall(m, idx, ctypes.c_int, [ctypes.POINTER(type(v))], ctypes.byref(v))):
                    out[key] = round(v.value, 1) if kind == "d" else int(v.value)
        finally:
            _vcall(m, I_RELEASE, ctypes.c_long, [])
        if self.pwr:
            out["power_limit"] = self._geti(self.pwr, PWR_GET)
        if self.gfx and "voltage" in self.caps:
            out["voltage_set"] = self._geti(self.gfx, GFX2_V_GET)
        return out

    def snapshot(self) -> dict:
        return dict(fan=self._fan_states() if self.fan_i else [],
                    power=self._geti(self.pwr, PWR_GET) if self.pwr else None,
                    maxfreq=self._geti(self.gfx, GFX2_MAXF_GET) if self.gfx and "maxfreq" in self.caps else None,
                    voltage=self._geti(self.gfx, GFX2_V_GET) if self.gfx and "voltage" in self.caps else None)

    def restore(self, snap: dict) -> bool:
        ok = True
        if snap.get("voltage") is not None:
            ok = self.voltage_set(snap["voltage"]) and ok
        if snap.get("maxfreq") is not None:
            ok = self.clock_cap(snap["maxfreq"]) and ok
        if snap.get("power") is not None:
            ok = self.power_set(snap["power"]) and ok
        fan = [p for p in snap.get("fan") or [] if p[0] is not None and p[1] is not None]
        if fan and self.caps.get("fan"):
            ok = self._fan_exact(fan) and ok
        return ok

    def _fan_exact(self, pts) -> bool:
        lst = ctypes.c_void_p()
        if not self._ok(_vcall(self.fan_i, FAN_EMPTY, ctypes.c_int, [ctypes.POINTER(ctypes.c_void_p)],
                               ctypes.byref(lst))):
            return False
        try:
            n = int(_vcall(lst, LIST_SIZE, ctypes.c_uint, []))
            if n != len(pts):
                return False
            for i, (t, s) in enumerate(pts):
                st = ctypes.c_void_p()
                if not self._ok(_vcall(lst, FLIST_AT, ctypes.c_int, [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)],
                                       i, ctypes.byref(st))):
                    return False
                self._seti(st, FSTATE_SET_TEMP, t)
                self._seti(st, FSTATE_SET_SPEED, s)
                _vcall(st, I_RELEASE, ctypes.c_long, [])
            return self._ok(_vcall(self.fan_i, FAN_SET, ctypes.c_int, [ctypes.c_void_p], lst))
        finally:
            _vcall(lst, I_RELEASE, ctypes.c_long, [])

    def reset(self) -> bool:
        """Заводські налаштування розгону цієї карти (те саме, що «Скинути» в Adrenalin)."""
        if not (self.ts and self.gpu):
            return False
        return self._ok(_vcall(self.ts, TS_RESET, ctypes.c_int, [ctypes.c_void_p], self.gpu))

    def close(self) -> None:
        for r in reversed(self._refs):
            try:
                if r:
                    _vcall(r, I_RELEASE, ctypes.c_long, [])
            except Exception:
                pass
        self._refs = []
        if self.dll is not None and self.sys:
            try:
                self.dll.ADLXTerminate()
            except Exception:
                pass
        self.sys = None


# ── демо й тести ──
class DemoTuner(Tuner):
    """Відеокарта для демо поза Windows і для тестів: проста теплова модель, усі налаштування, збій вище порогу
    зсуву/нижче порогу напруги (unstable_at) — так перевіряється автопідбір."""

    def __init__(self, vendor: str = "nvidia", name: str = "", unstable_at: int = 165):
        super().__init__()
        self.vendor = vendor
        self.name = name or ("NVIDIA GeForce RTX 4070 (demo)" if vendor == "nvidia" else "AMD Radeon RX 7800 XT (demo)")
        self.unstable_at = unstable_at
        self.temp, self.load = 45.0, 0.0
        self.fan, self.fan_manual = 30, False
        self.calls = []
        if vendor == "nvidia":
            self.caps = dict(fan=dict(count=2, min=30, max=100, mode="manual", auto=True),
                             power=dict(unit="W", min=100, max=240, default=200, cur=200),
                             clock=dict(max=2610, min=300, cur=None), offset=dict(min=-1000, max=1000, cur=0))
            self.why = dict(voltage="gt.why.nv_voltage")
            self.state = dict(power=200, offset=0, clock=None)
        else:
            self.caps = dict(fan=dict(count=1, min=20, max=100, tmin=25, tmax=95, points=5, mode="native", auto=None),
                             power=dict(unit="%", min=-10, max=15, default=0, cur=0),
                             maxfreq=dict(min=500, max=2600, step=1, cur=2430),
                             voltage=dict(min=700, max=1150, step=5, cur=1150))
            self.why = dict(offset="gt.why.amd_offset")
            self.state = dict(power=0, maxfreq=2430, voltage=1150, fan=[(40, 25), (55, 35), (70, 50), (80, 70),
                                                                        (90, 100)])

    def stable(self) -> bool:
        if self.vendor == "nvidia":
            return self.state["offset"] < self.unstable_at
        return self.state["voltage"] > 1150 - self.unstable_at

    def read(self) -> dict:
        watts = 200.0 * (0.25 + 0.75 * self.load)
        if self.vendor == "nvidia":
            watts *= max(0.6, 1 - self.state["offset"] / 1000.0) if self.state["clock"] else 1.0
            watts = min(watts, self.state["power"])
        else:
            watts *= (self.state["voltage"] / 1150.0) ** 2
        target = 35 + watts * 0.28 - self.fan * 0.12
        self.temp += (target - self.temp) * 0.3
        if not self.fan_manual:
            self.fan = int(min(100, max(30, (self.temp - 30) * 1.6)))
        out = dict(temp=round(self.temp, 1), fan=self.fan, rpm=self.fan * 30, power=round(watts, 1),
                   clock=2610 if not self.state.get("clock") else self.state["clock"], util=int(self.load * 100),
                   fan_auto=not self.fan_manual, power_limit=self.state["power"])
        if self.vendor == "nvidia":
            out["offset"] = self.state["offset"]
        return out

    def fan_set(self, pct: int) -> bool:
        self.calls.append(("fan", pct))
        self.fan, self.fan_manual = int(pct), True
        return True

    def fan_auto(self) -> bool:
        self.calls.append(("fan_auto",))
        self.fan_manual = False
        return True

    def fan_curve_native(self, points) -> bool:
        if self.vendor != "amd":
            return False
        f = self.caps["fan"]
        self.state["fan"] = resample(points, spread_temps(f["tmin"], f["tmax"], f["points"]))
        self.calls.append(("curve", tuple(self.state["fan"])))
        return True

    def power_set(self, value: int) -> bool:
        p = self.caps["power"]
        self.state["power"] = int(min(p["max"], max(p["min"], value)))
        self.calls.append(("power", self.state["power"]))
        return True

    def clock_cap(self, mhz) -> bool:
        if self.vendor == "nvidia":
            self.state["clock"] = mhz
        elif mhz is not None:  # як і AdlxTuner: None для AMD — нічого не змінювати
            self.state["maxfreq"] = mhz
        self.calls.append(("clock", mhz))
        return True

    def offset_set(self, mhz: int) -> bool:
        if self.vendor != "nvidia":
            return False
        self.state["offset"] = int(mhz)
        self.calls.append(("offset", mhz))
        return True

    def voltage_set(self, mv: int) -> bool:
        if self.vendor != "amd":
            return False
        v = self.caps["voltage"]
        self.state["voltage"] = int(min(v["max"], max(v["min"], mv)))
        self.calls.append(("voltage", self.state["voltage"]))
        return True

    def snapshot(self) -> dict:
        return dict(self.state)

    def restore(self, snap: dict) -> bool:
        self.fan_auto()
        self.state.update({k: v for k, v in snap.items() if k in self.state})
        self.calls.append(("restore",))
        return True

    def reset(self) -> bool:
        if self.vendor == "nvidia":
            return self.restore(dict(power=self.caps["power"]["default"], offset=0, clock=None))
        return self.restore(dict(power=0, maxfreq=2430, voltage=1150))


def open_tuner(gpu_name: str = "") -> Tuner:
    """Відеокарта, якою можна керувати: NVIDIA (NVML), AMD (ADLX); поза Windows — демо. Нічого не знайдено —
    порожній Tuner (ok() == False), причину видно в why."""
    if not E.IS_WIN:
        return DemoTuner("amd" if "amd" in (gpu_name or "").lower() or "radeon" in (gpu_name or "").lower()
                         else "nvidia", gpu_name)
    low = (gpu_name or "").lower()
    order = (AdlxTuner, NvmlTuner) if ("amd" in low or "radeon" in low) else (NvmlTuner, AdlxTuner)
    for cls in order:
        try:
            t = cls(gpu_name)
        except Exception:
            continue
        if t.ok():
            return t
        t.close()
    t = Tuner()
    t.why = {k: "gt.why.no_gpu" for k in ("fan", "power", "clock", "voltage", "offset")}
    return t


# ───────────────────────── стан, журнал, запуск ─────────────────────────
JOURNAL_PREFIX = "gpu.tune:"


def journal_id(t: Tuner) -> str:
    return f"{JOURNAL_PREFIX}{t.vendor}:{t.index}"


def reset_command(t: Tuner) -> str:
    """Команда для запису журналу: OptimaX сама повертає заводські значення цієї карти (і з OptimaX-Rescue.cmd)."""
    import gpubench as GB
    parts = GB.self_command() + ["--gpu-reset", f"--vendor={t.vendor}", f"--index={t.index}"]
    return subprocess.list2cmdline(parts)


def state(cfg) -> dict:
    return dict(cfg["gpu_tune"] or {})


def save_state(cfg, st: dict) -> None:
    cfg["gpu_tune"] = st


def remember_original(cfg, t: Tuner) -> dict:
    """Заводські (до OptimaX) значення карти — лише перед першою зміною; повторні зміни їх не перезаписують.
    Запис журналу «OptimaX.exe --gpu-reset» — щоб відкат усього й OptimaX-Rescue.cmd повертали карту."""
    st = state(cfg)
    orig = dict(st.get("orig") or {})
    if t.key not in orig:
        orig[t.key] = t.snapshot()
        st["orig"] = orig
        save_state(cfg, st)
    tid = journal_id(t)
    if not E.DRY_RUN and not E.JOURNAL.has(tid):
        try:
            E.JOURNAL.put(tid, [{"t": "cmd", "c": reset_command(t)}], title=tr("gt.journal", gpu=t.name),
                          group="gpu")
        except Exception as e:  # журнал недоступний — змін не робимо (без запису їх не було б як повернути)
            raise RuntimeError(tr("gt.err.journal", e=e))
    return orig[t.key]


def mark_pending(cfg, t: Tuner, what: str) -> None:
    st = state(cfg)
    st["pending"] = dict(key=t.key, what=what, ts=int(time.time()))
    save_state(cfg, st)


def clear_pending(cfg) -> None:
    st = state(cfg)
    if st.pop("pending", None) is not None:
        save_state(cfg, st)


def restore_original(cfg, t: Tuner, drop_journal: bool = True) -> bool:
    """Повернути заводські значення карти (із запам'ятованих, інакше — типові драйвера) і прибрати запис журналу."""
    st = state(cfg)
    snap = (st.get("orig") or {}).get(t.key)
    ok = t.restore(snap) if snap else t.reset()
    if ok:
        st.get("orig", {}).pop(t.key, None)
        st.pop("pending", None)
        st["active"] = False
        save_state(cfg, st)
        if drop_journal and not E.DRY_RUN and E.JOURNAL.has(journal_id(t)):
            try:
                E.JOURNAL.pop(journal_id(t))
            except Exception:
                pass
    return ok


def apply_profile(cfg, t: Tuner, prof: dict, log=lambda *_: None) -> dict:
    """Застосувати профіль: потужність, обмеження частоти, зсув / напруга, крива вентилятора драйвера (AMD).
    Крива вентилятора NVIDIA — FanController (працює, поки працює OptimaX). -> {що: True/False}."""
    res = {}
    remember_original(cfg, t)
    risky = any(prof.get(k) not in (None, 0) for k in ("offset", "voltage")) or prof.get("clock") is not None
    if risky:
        mark_pending(cfg, t, "apply")
    if prof.get("power") is not None and "power" in t.caps:
        res["power"] = t.power_set(int(prof["power"]))
    if "clock" in prof and ("clock" in t.caps or "maxfreq" in t.caps):
        res["clock"] = t.clock_cap(prof.get("clock"))
    if prof.get("offset") is not None and "offset" in t.caps:
        res["offset"] = t.offset_set(int(prof["offset"]))
    if prof.get("voltage") is not None and "voltage" in t.caps:
        res["voltage"] = t.voltage_set(int(prof["voltage"]))
    fan = prof.get("fan") or {}
    if fan.get("mode") in ("curve", "fixed") and (t.caps.get("fan") or {}).get("mode") == "native":
        pts = fan.get("curve") if fan["mode"] == "curve" else [(40, fan.get("fixed") or 50),
                                                               (FAN_FORCE_TEMP - 1, fan.get("fixed") or 50)]
        res["fan"] = t.fan_curve_native(pts or CURVE_PRESETS["balanced"])
    st = state(cfg)
    st.update(active=True, profile=dict(prof, gpu=t.key), applied_ts=int(time.time()))
    save_state(cfg, st)
    for k, ok in res.items():
        log(("  ✓ " if ok else "  ✗ ") + tr(f"gt.part.{k}") + ("" if ok else f" — {t.last_error}"))
    return res


def confirm_stable(cfg) -> bool:
    """Позначку «перевіряється» знімаємо, коли після зміни минуло CONFIRM_SECONDS без збою."""
    st = state(cfg)
    p = st.get("pending")
    if p and not st.get("tuning") and time.time() - (p.get("ts") or 0) >= CONFIRM_SECONDS:
        clear_pending(cfg)
        return True
    return False


def startup(cfg, log=lambda *_: None) -> dict:
    """Під час запуску OptimaX: якщо минулого разу зміну частоти/напруги не підтвердили (збій) — заводські значення
    й без автозастосування; інакше, якщо ввімкнено й профіль перевірено, — застосувати профіль.
    -> {"crashed": bool, "applied": bool, "tuner": Tuner|None}"""
    st = state(cfg)
    out = dict(crashed=False, applied=False, tuner=None)
    if not st.get("pending") and not (st.get("on_start") and st.get("profile")):
        return out
    prof = st.get("profile") or {}
    t = SESSION.open((prof.get("gpu") or "::").split(":", 2)[-1])
    out["tuner"] = t
    if not t.ok():
        return out
    if st.get("pending"):
        out["crashed"] = True
        restore_original(cfg, t)
        st = state(cfg)
        st["on_start"] = False
        save_state(cfg, st)
        log(tr("gt.log.crashed"))
        return out
    if st.get("on_start") and prof.get("verified"):
        apply_profile(cfg, t, prof, log)
        out["applied"] = True
    return out


def reset_main(argv) -> int:
    """OptimaX.exe --gpu-reset --vendor=… --index=… — запис журналу й OptimaX-Rescue.cmd: заводські значення карти.
    Налаштування OptimaX тут лише читаються (заводські значення); стан «активно» прибере сама програма, побачивши,
    що запису журналу більше немає."""
    a = {k[2:]: v for k, _, v in (x.partition("=") for x in argv) if k.startswith("--")}
    vendor, index = a.get("vendor", ""), int(a.get("index") or 0)
    import features as F
    t = None
    try:
        if vendor == "amd":
            t = AdlxTuner(index=index)
        elif vendor == "nvidia":
            import gpubench as GB
            nv = GB.Nvml()
            names = {i: n for i, n, _ in nv.devices()}
            nv.close()
            t = NvmlTuner(names.get(index, ""))
        if t is None or not t.ok():
            return 2
        snap = ((F.CFG["gpu_tune"] or {}).get("orig") or {}).get(t.key)
        return 0 if (t.restore(snap) if snap else t.reset()) else 1
    finally:
        if t is not None:
            t.close()


def sync_with_journal(cfg) -> bool:
    """Запис журналу відкотили (відкат усього, OptimaX-Rescue.cmd) — значить, карта вже заводська: стан «активно»,
    профіль під час запуску й запам'ятовані значення прибираємо. -> True, якщо щось змінилося."""
    st = state(cfg)
    if not st.get("active") or E.DRY_RUN:  # у режимі перегляду записів журналу немає й не має бути
        return False
    if any(tid.startswith(JOURNAL_PREFIX) for tid in E.JOURNAL.newest_first()):
        return False
    st.update(active=False, on_start=False, orig={})
    st.pop("pending", None)
    save_state(cfg, st)
    return True


# ───────────────────────── вентилятори NVIDIA: крива й сторож ─────────────────────────
class FanController:
    """Крива OptimaX для карт, де драйвер сам кривої не тримає (NVIDIA): раз на FAN_TICK с — температура -> швидкість.
    Будь-яка помилка FAN_FAILS разів поспіль, зупинка чи закриття програми — вентилятори повертаються драйверу.
    Сторожовий процес (--gpu-watchdog) робить те саме, якщо OptimaX зникла, не встигнувши цього зробити."""

    def __init__(self, tuner: Tuner, curve=None, fixed: int = None, watchdog: bool = True):
        fan = tuner.caps.get("fan") or {}
        self.t = tuner
        self.curve = FanCurve(curve, fan.get("min", 0), fan.get("max", 100)) if curve else None
        self.fixed = None if fixed is None else int(min(fan.get("max", 100), max(FAN_MIN_SAFE, fixed)))
        if self.curve is None and self.fixed is None:
            raise ValueError("curve or fixed")
        self.sent = None
        self.stop_ev = threading.Event()
        self.thread = None
        self.fails = 0
        self.last = {}
        self.error = ""
        self.wd = None
        self.use_watchdog = watchdog and E.IS_WIN and tuner.vendor == "nvidia"

    @property
    def running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def start(self) -> None:
        if self.use_watchdog:
            self.wd = start_watchdog(self.t)
        self.thread = threading.Thread(target=self._loop, name="OptimaX-fan", daemon=True)
        self.thread.start()

    def step(self) -> None:
        """Один крок (і для тестів): фіксована швидкість чи крива; від FAN_FORCE_TEMP — 100 % в обох режимах."""
        r = self.t.read()
        self.last = r
        temp = r.get("temp")
        if self.curve is not None:
            speed = self.curve.update(temp)
        else:
            want = 100 if temp is None or temp >= FAN_FORCE_TEMP else self.fixed
            speed = None if want == self.sent else want
        if speed is not None:
            if not self.t.fan_set(speed):
                raise RuntimeError(self.t.last_error or "fan_set")
            self.sent = speed

    def _loop(self) -> None:
        try:
            while not self.stop_ev.is_set():
                try:
                    self.step()
                    self.fails = 0
                except Exception as e:
                    self.fails += 1
                    self.error = str(e)[:200]
                    if self.fails >= FAN_FAILS:
                        break
                self.stop_ev.wait(FAN_TICK)
        finally:
            self.t.fan_auto()
            stop_watchdog(self.wd)
            self.wd = None

    def stop(self, wait: float = 3.0) -> None:
        self.stop_ev.set()
        if self.thread:
            self.thread.join(wait)
        if self.thread is None or not self.thread.is_alive():
            stop_watchdog(self.wd)
            self.wd = None


def start_watchdog(t: Tuner):
    """Окремий процес: чекає, доки OptimaX завершиться, і тоді повертає вентилятори NVIDIA драйверу."""
    import gpubench as GB
    cmd = GB.self_command() + ["--gpu-watchdog", f"--parent={os.getpid()}", f"--name={t.name}"]
    here = None if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    try:
        return subprocess.Popen(cmd, cwd=here, creationflags=E.CREATE_NO_WINDOW if E.IS_WIN else 0,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return None


def stop_watchdog(proc) -> None:
    if proc is None:
        return
    try:
        proc.kill()
        proc.wait(3)
    except Exception:
        pass


def watchdog_main(argv) -> int:
    """OptimaX.exe --gpu-watchdog --parent=<pid> --name=<карта>: чекає на завершення OptimaX, тоді — вентилятори
    драйверу. Батьківський процес, зупиняючи криву нормально, сам повертає вентилятори й завершує сторожа."""
    a = {k[2:]: v for k, _, v in (x.partition("=") for x in argv) if k.startswith("--")}
    pid = int(a.get("parent") or 0) & 0xFFFFFFFF
    if E.IS_WIN and pid:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.WaitForSingleObject.restype = ctypes.c_uint32
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        h = k32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if h:
            while k32.WaitForSingleObject(h, 1000) == 0x102:  # WAIT_TIMEOUT — OptimaX ще працює; інше — завершилась
                pass
            k32.CloseHandle(ctypes.c_void_p(h))
    t = NvmlTuner(a.get("name") or "")
    try:
        return 0 if t.ok() and t.fan_auto() else 1
    finally:
        t.close()


class Session:
    """Відеокарта на рівні програми: одна відкрита карта, режим вентиляторів, завершення разом з OptimaX."""

    def __init__(self):
        self.tuner = None
        self.fans = None
        self.lock = threading.RLock()

    def open(self, gpu_name: str = "") -> Tuner:
        with self.lock:
            if self.tuner is None or (gpu_name and gpu_name.lower() not in (self.tuner.name or "").lower()
                                      and self.tuner.ok()):
                self.close()
                self.tuner = open_tuner(gpu_name)
            return self.tuner

    def set_fans(self, cfg, mode: str, curve=None, fixed: int = None) -> bool:
        """auto — драйверу; curve / fixed — NVIDIA: крива OptimaX у потоці + сторож; AMD: точки драйвера."""
        with self.lock:
            t = self.tuner
            if t is None or not t.ok() or "fan" not in t.caps:
                return False
            self.stop_fans()
            native = t.caps["fan"].get("mode") == "native"
            if mode == "auto":
                if native:
                    snap = ((state(cfg).get("orig") or {}).get(t.key) or {}).get("fan")
                    return t.restore(dict(fan=snap)) if snap else True
                return t.fan_auto()
            remember_original(cfg, t)
            if native:
                pts = curve if mode == "curve" else [(40, fixed), (FAN_FORCE_TEMP - 1, fixed)]
                return t.fan_curve_native(pts or CURVE_PRESETS["balanced"])
            self.fans = FanController(t, curve=curve if mode == "curve" else None,
                                      fixed=fixed if mode == "fixed" else None)
            self.fans.start()
            return True

    def stop_fans(self) -> None:
        with self.lock:
            if self.fans is not None:
                self.fans.stop()
                self.fans = None

    def fans_running(self) -> bool:
        return bool(self.fans and self.fans.running)

    def close(self) -> None:
        with self.lock:
            self.stop_fans()
            if self.tuner is not None:
                self.tuner.close()
                self.tuner = None


SESSION = Session()


def startup_fans(cfg) -> bool:
    """Після startup(): крива вентиляторів NVIDIA з профілю, якщо профіль застосовано під час запуску."""
    st = state(cfg)
    prof = st.get("profile") or {}
    fan = prof.get("fan") or {}
    if not (st.get("active") and st.get("on_start") and fan.get("mode") in ("curve", "fixed")):
        return False
    t = SESSION.open((prof.get("gpu") or "::").split(":", 2)[-1])
    if not t.ok() or (t.caps.get("fan") or {}).get("mode") == "native":
        return False  # AMD: точки вже в драйвері
    return SESSION.set_fans(cfg, fan["mode"], fan.get("curve"), fan.get("fixed"))


# ───────────────────────── автопідбір андервольту ─────────────────────────
class AutoTune:
    """Пошук андервольту кроками зі стрес-тестом на кожному.

    NVIDIA: частота обмежена заводською найвищою (продуктивність та сама), зсув кривої росте на TUNE_STEP_MHZ —
    чим більший зсув, тим нижча напруга на цій частоті. AMD: напруга знижується на TUNE_STEP_MV. Перша помилка
    (кадр не збігся до біта, збій тесту чи драйвера) — відступ на TUNE_BACKOFF_STEPS кроки й фінальна перевірка
    TUNE_VERIFY_SECONDS. Будь-що пішло не так — заводські значення.

    run_fn(seconds) -> об'єкт тесту з poll()/stop()/cleanup() (gpubench.start); tick() викликає інтерфейс."""

    def __init__(self, cfg, tuner: Tuner, run_fn, log=lambda *_: None, step_s: int = TUNE_STEP_SECONDS,
                 verify_s: int = TUNE_VERIFY_SECONDS):
        self.cfg, self.t, self.run_fn, self.log = cfg, tuner, run_fn, log
        self.step_s, self.verify_s = step_s, verify_s
        self.kind = "offset" if "offset" in tuner.caps and "clock" in tuner.caps else \
            "voltage" if "voltage" in tuner.caps else ""
        self.phase = "idle"   # baseline -> step -> verify -> done | failed | cancelled
        self.value = 0        # поточний зсув (МГц) або зниження напруги (мВ)
        self.good = 0
        self.steps = []       # [{value, ok, power, temp, score}]
        self.run = None
        self.samples = []
        self.result = None
        self.stopped = False
        self.base_mv = 0

    @property
    def supported(self) -> bool:
        return bool(self.kind)

    def _apply(self, value: int) -> bool:
        if self.kind == "offset":
            return self.t.clock_cap(self.t.caps["clock"]["max"]) and self.t.offset_set(value)
        return self.t.voltage_set(self.base_mv - value)

    def start(self) -> None:
        """Заводські значення (з них — базовий замір), позначка «перевіряється», перший стрес-тест."""
        if not self.supported:
            raise RuntimeError(tr("gt.tune.unsupported"))
        orig = remember_original(self.cfg, self.t) or {}
        v = self.t.caps.get("voltage") or {}
        self.base_mv = int(orig.get("voltage") or v.get("cur") or v.get("max") or 0)
        st = state(self.cfg)
        st["tuning"] = dict(key=self.t.key, ts=int(time.time()))
        save_state(self.cfg, st)
        mark_pending(self.cfg, self.t, "tune")
        if not self._apply(0):
            self._finish("failed", why="gt.tune.apply_bad")
            return
        self.phase = "baseline"
        self._launch(self.step_s)

    def _launch(self, seconds: int) -> None:
        self.samples = []
        self.run = self.run_fn(seconds)

    def stop(self) -> None:
        self.stopped = True
        if self.run is not None:
            try:
                self.run.stop()
            except Exception:
                pass

    def tick(self) -> str:
        """-> фаза. Читає датчики (потужність, температура) і стан тесту; перехід до наступного кроку — тут."""
        if self.phase in ("idle", "done", "failed", "cancelled"):
            return self.phase
        try:
            r = self.t.read()
            if r:
                self.samples.append(r)
        except Exception:
            pass
        st = self.run.poll() if self.run else {"state": "error"}
        if st.get("state") in ("starting", "running", "warmup", "allocating"):
            return self.phase
        try:
            self.run.cleanup()
        except Exception:
            pass
        res = st.get("result") or {}
        ok = st.get("state") == "done" and res.get("verdict") not in ("errors", "crash") and not res.get("errors")
        if self.stopped or st.get("state") == "cancelled":
            return self._finish("cancelled")
        rec = dict(value=self.value, ok=ok, power=_avg(self.samples, "power"), temp=_max(self.samples, "temp"),
                   score=res.get("score") or res.get("avg"))
        self.steps.append(rec)
        self.log(tr("gt.tune.step", v=self._label(self.value), st=tr("gt.tune.ok" if ok else "gt.tune.bad")))
        if self.phase == "baseline":
            if not ok:
                return self._finish("failed", why="gt.tune.base_bad")
            return self._next(TUNE_STEP_MHZ if self.kind == "offset" else TUNE_STEP_MV)
        if self.phase == "step":
            if ok:
                self.good = self.value
                if len(self.steps) - 1 >= TUNE_MAX_STEPS:
                    return self._verify()
                return self._next(self.value + (TUNE_STEP_MHZ if self.kind == "offset" else TUNE_STEP_MV))
            return self._verify(backoff=True)
        if self.phase == "verify":
            if ok:
                return self._finish("done")
            return self._finish("failed", why="gt.tune.verify_bad")
        return self.phase

    def _label(self, v: int) -> str:
        return f"+{v} MHz" if self.kind == "offset" else f"−{v} mV"

    def _next(self, value: int) -> str:
        self.value = value
        if not self._apply(value):
            return self._finish("failed", why="gt.tune.apply_bad")
        self.phase = "step"
        self._launch(self.step_s)
        return self.phase

    def _verify(self, backoff: bool = False) -> str:
        """Збій на кроці v — перевіряємо v − TUNE_BACKOFF_STEPS кроків; збою не було (досягли TUNE_MAX_STEPS) — на
        крок нижче останнього вдалого. Запас потрібен: короткий стрес-тест ловить не всі нестабільності."""
        step = TUNE_STEP_MHZ if self.kind == "offset" else TUNE_STEP_MV
        final = self.value - TUNE_BACKOFF_STEPS * step if backoff else self.good - step
        if final <= 0:
            return self._finish("failed", why="gt.tune.no_margin")
        self.value = final
        if not self._apply(final):
            return self._finish("failed", why="gt.tune.apply_bad")
        self.phase = "verify"
        self._launch(self.verify_s)
        return self.phase

    def _finish(self, how: str, why: str = "") -> str:
        self.phase = how
        st = state(self.cfg)
        st.pop("tuning", None)
        save_state(self.cfg, st)
        base = self.steps[0] if self.steps else {}
        final = self.steps[-1] if self.steps else {}
        if how == "done":
            st = state(self.cfg)
            old = st.get("profile") or {}
            prof = dict(old) if old.get("gpu") == self.t.key else {}  # крива й потужність користувача лишаються
            if self.kind == "offset":
                prof.update(clock=self.t.caps["clock"]["max"], offset=self.value)
            else:
                prof.update(voltage=self.base_mv - self.value)
            prof.update(gpu=self.t.key, verified=int(time.time()), auto=True)
            st.update(active=True, profile=prof, applied_ts=int(time.time()))
            save_state(self.cfg, st)
            clear_pending(self.cfg)
            self.log(tr("gt.tune.done", v=self._label(self.value)))
        else:
            restore_original(self.cfg, self.t)
            if why:
                self.log(tr(why))
        self.result = dict(how=how, why=why, kind=self.kind, value=self.value if how == "done" else 0,
                           power_before=base.get("power"), power_after=final.get("power") if how == "done" else None,
                           temp_before=base.get("temp"), temp_after=final.get("temp") if how == "done" else None,
                           score_before=base.get("score"), score_after=final.get("score") if how == "done" else None,
                           steps=list(self.steps))
        return how


def _avg(samples, key):
    v = [s[key] for s in samples if s.get(key) is not None]
    return round(sum(v) / len(v), 1) if v else None


def _max(samples, key):
    v = [s[key] for s in samples if s.get(key) is not None]
    return max(v) if v else None


def describe_caps(t: Tuner) -> list:
    """[(що, підтримується, пояснення)] — для інтерфейсу й звіту тестерів."""
    out = []
    for k in ("fan", "power", "clock", "offset", "voltage"):
        have = k in t.caps or (k == "clock" and "maxfreq" in t.caps)
        out.append((k, have, "" if have else tr(t.why.get(k) or "gt.why.unsupported")))
    return out
