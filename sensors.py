"""
OptimaX — «Датчики» в Hardware Center: усі показники заліза в одній таблиці, як в AIDA64 / HWiNFO.

Групи за пристроями: процесор, кожна відеокарта, пам'ять, кожен диск, плата (лише теплова зона ACPI — інших датчиків
плати без власного драйвера не прочитати). Для кожного показника — поточне, мінімум, максимум і середнє з одиницями.

Джерела — лише ті, що вже є в OptimaX (усе лише читання):
  • процесор: лічильники Windows (завантаження, частота), cpusensors (Core Temp / HWiNFO / AIDA64 / LHM), PawnIO
    (pawnio.CpuLive — VID і частота ядра 0; MSR — температура пакета й найгарячішого ядра Intel, споживання RAPL;
    AMD — Tctl через SMN під загальним м'ютексом Access_PCI);
  • NVIDIA — NVML із сеансом, який hardware.py тримає відкритим (7.1.1), інші карти — лічильники Windows
    «GPU Engine» / «GPU Adapter Memory» (завантаження й пам'ять; температури в них немає — її не вигадуємо);
  • диски — storagehealth (журнал здоров'я NVMe, SMART ATA), не частіше NVME_EVERY / ATA_EVERY секунд;
  • пам'ять — GlobalMemoryStatusEx.
Не прочиталось — None («—» в інтерфейсі), а не вигадане число.

Read() іде у фоновому потоці (повільні джерела не гальмують інтерфейс), feed() — у потоці інтерфейсу.
Тут же — пороги сповіщень із гістерезисом і запис у CSV.
"""
from __future__ import annotations

import csv
import io
import math
import os
import random
import re
import threading
import time

import engine as E
from i18n import tr

INTERVAL_MS = 1000
NVME_EVERY = 10.0   # с: журнал здоров'я NVMe — дешевий IOCTL, температура змінюється повільно
ATA_EVERY = 60.0    # с: SMART ATA — три команди диску; HWiNFO / CrystalDiskInfo теж не смикають HDD щосекунди
NV_RETRY = 30.0     # с: NVML не відкрився (драйвер оновлюється) — не пробувати щосекунди
PROBE_RETRY = 300.0

# ── пороги сповіщень, °C ──
# CPU 95: Intel скидає частоту на TjMax 100 °C, Ryzen 7000/9000 тримають 95 °C як розрахункову межу — понад 95 уже
#   робота на межі тротлінгу; самі 95 у Ryzen під навантаженням — норма, тому сповіщаємо лише ВИЩЕ за поріг.
# GPU 87: той самий поріг, від якого «Чому лагає?» вважає карту перегрітою (monitor.classify) — для більшості карт
#   NVIDIA це вже межа, де драйвер знижує частоти.
# SSD/NVMe 70 і HDD 55: ті самі межі «гаряче», що й у розділі «Диски» (pages_diskinfo.temp_level): типовий WCTEMP
#   NVMe — 70–85 °C, а HDD за специфікаціями виробників розраховані на 55–60 °C.
DEFAULT_LIMITS = {"cpu": 95, "gpu": 87, "ssd": 70, "hdd": 55}
LIMIT_RANGE = {"cpu": (60, 110), "gpu": (60, 105), "ssd": (45, 85), "hdd": (40, 65)}
HYSTERESIS = 5.0  # °C: сповіщення знімається, лише коли охололо на стільки нижче порога (шум датчика ±1–2 °C)
HOLD = 3          # вимірів поспіль вище порога, щоб сповістити (одиничний сплеск — не перегрів)

UNIT_DIGITS = {"c": 1, "pct": 0, "mhz": 0, "w": 1, "v": 3, "mb": 0, "gb": 1, "rpm": 0}
GROUP_ORDER = ("cpu", "gpu", "ram", "disk", "board")


def reading(rid: str, group: str, gkind: str, gtitle: str, key: str, unit: str, value, src: str = "",
            always: bool = False, sub: str = "") -> dict:
    """Один показник. gkind: cpu | gpu | ram | ssd | hdd | board; key — ключ перекладу назви."""
    if isinstance(value, float) and not math.isfinite(value):
        value = None
    return dict(id=rid, group=group, gkind=gkind, gtitle=gtitle, key=key, unit=unit, value=value, src=src,
                always=always, sub=sub)


# ───────────────────────── агрегування ─────────────────────────
class Stat:
    """Поточне / мінімум / максимум / середнє. None (датчик мовчить) не псує min/max/avg."""
    __slots__ = ("cur", "min", "max", "sum", "n")

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.cur = self.min = self.max = None
        self.sum, self.n = 0.0, 0

    def add(self, v) -> None:
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            self.cur = None
            return
        self.cur = v
        self.min = v if self.min is None else min(self.min, v)
        self.max = v if self.max is None else max(self.max, v)
        self.sum += v
        self.n += 1

    @property
    def avg(self):
        return self.sum / self.n if self.n else None


def fmt(v, unit: str) -> str:
    if v is None:
        return "—"
    d = UNIT_DIGITS.get(unit, 1)
    return f"{v:.{d}f}"


def unit_text(unit: str) -> str:
    return "°C" if unit == "c" else "%" if unit == "pct" else tr(f"sn.u.{unit}")


def name_text(r: dict) -> str:
    n = tr(r["key"])
    if r.get("sub"):
        n = f"{n} {r['sub']}"
    return f"{n} · {r['src']}" if r.get("src") else n


def group_rows(readings: list) -> list:
    """-> [(група-словник, [показники])] за GROUP_ORDER, а всередині — у порядку появи."""
    groups, order = {}, []
    for r in readings:
        if r["group"] not in groups:
            groups[r["group"]] = (dict(id=r["group"], kind=r["gkind"], title=r["gtitle"]), [])
            order.append(r["group"])
        groups[r["group"]][1].append(r)

    def rank(gid):
        kind = groups[gid][0]["kind"]
        base = "disk" if kind in ("ssd", "hdd") else kind
        return GROUP_ORDER.index(base) if base in GROUP_ORDER else len(GROUP_ORDER)
    order.sort(key=rank)  # сортування стабільне: усередині виду — порядок появи
    return [groups[g] for g in order]


# ───────────────────────── пороги й гістерезис ─────────────────────────
def limit_kind(r: dict):
    """Яким порогом перевіряти показник (лише температури процесора, відеокарт і дисків)."""
    if r.get("unit") != "c":
        return None
    return r["gkind"] if r["gkind"] in DEFAULT_LIMITS else None


def load_limits(cfg) -> dict:
    """settings.json пише будь-яка програма користувача — беремо лише числа в розумних межах."""
    raw = (cfg["sensor_alerts"] if cfg is not None else None) or {}
    out = {"on": raw.get("on", True) is not False}
    for k, dflt in DEFAULT_LIMITS.items():
        v = raw.get(k)
        lo, hi = LIMIT_RANGE[k]
        out[k] = int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi else dflt
    return out


class Alerts:
    """Сповіщення з гістерезисом: спрацьовує після HOLD вимірів поспіль понад поріг, знімається, коли значення
    опуститься на HYSTERESIS нижче порога. Поки активне — повторно не сповіщає."""

    def __init__(self, hold: int = HOLD, hyst: float = HYSTERESIS):
        self.hold, self.hyst = hold, hyst
        self.count, self.active = {}, {}

    def update(self, readings: list, limits: dict) -> tuple:
        """-> (нові [(показник, поріг)], зняті [показник])."""
        raised, cleared = [], []
        for r in readings:
            k = limit_kind(r)
            v = r.get("value")
            if k is None or v is None:
                continue  # датчик замовк — стан не змінюємо (ні «охололо», ні «перегрів»)
            lim = limits.get(k, DEFAULT_LIMITS[k])
            rid = r["id"]
            if rid in self.active:
                if v <= lim - self.hyst:
                    del self.active[rid]
                    self.count[rid] = 0
                    cleared.append(r)
                else:
                    self.active[rid] = lim
                continue
            if v > lim:
                self.count[rid] = self.count.get(rid, 0) + 1
                if self.count[rid] >= self.hold:
                    self.active[rid] = lim
                    raised.append((r, lim))
            else:
                self.count[rid] = 0
        return raised, cleared

    def reset(self) -> None:
        self.count.clear()
        self.active.clear()


# ───────────────────────── CSV ─────────────────────────
def csv_header(cols: list) -> list:
    """cols — [(id, група, назва, одиниця)] -> рядок заголовка."""
    return [tr("sn.csv.time")] + [f"{g} / {n} [{unit_text(u)}]" for _i, g, n, u in cols]


def csv_row(ts: float, cols: list, values: dict) -> list:
    """Числа з крапкою й точністю одиниці; невідоме — порожня клітинка (не 0)."""
    row = [time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))]
    for rid, _g, _n, unit in cols:
        v = values.get(rid)
        row.append("" if v is None else fmt(v, unit))
    return row


def csv_line(row: list) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n").writerow(row)
    return buf.getvalue()


NAME_SURROGATE = 0x20000000  # біт тегу точки повторного розбору: symlink, junction, mount point — «веде деінде»


def link_like(path: str) -> bool:
    """Ланка шляху, що веде деінде. 7.2: не будь-яка точка повторного розбору (secfs.is_reparse лишається суворою
    для своїх папок у ProgramData): «Файли на вимогу» OneDrive (Робочий стіл / Документи в OneDrive) мають тег
    хмари без біта name surrogate — це звичайна папка, і запис у неї не відхиляємо."""
    import stat
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    if not attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    return bool(getattr(st, "st_reparse_tag", NAME_SURROGATE) & NAME_SURROGATE)  # тег невідомий — як посилання


def unsafe_target(path: str) -> bool:
    """OptimaX працює як адміністратор: файл, папка на шляху до нього чи сам шлях-посилання (symlink, junction)
    могли вести в системну папку — туди писати не можна. Перевіряємо кожну ланку."""
    p = os.path.abspath(path)
    if os.path.isdir(p):
        return True
    cur = p
    while True:
        if link_like(cur):
            return True
        parent = os.path.dirname(cur)
        if parent == cur:
            return False
        cur = parent


def _long_path(p: str) -> str:
    """Windows: повні імена замість 8.3 (RUNNER~1), щоб порівнювати з тим, що каже дескриптор."""
    if not E.IS_WIN:
        return p
    import ctypes
    buf = ctypes.create_unicode_buffer(32768)
    n = ctypes.windll.kernel32.GetLongPathNameW(p, buf, 32768)
    return buf.value if 0 < n < 32768 else p


def final_path(f):
    """Справжній шлях відкритого файла — за дескриптором, а не за іменем (None — невідомо)."""
    try:
        if E.IS_WIN:
            import ctypes
            import msvcrt
            k32 = ctypes.windll.kernel32
            k32.GetFinalPathNameByHandleW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32,
                                                      ctypes.c_uint32]
            buf = ctypes.create_unicode_buffer(32768)
            n = k32.GetFinalPathNameByHandleW(msvcrt.get_osfhandle(f.fileno()), buf, 32768, 0)
            if not 0 < n < 32768:
                return None
            v = buf.value
            if v.startswith("\\\\?\\UNC\\"):
                return "\\\\" + v[8:]  # \\?\UNC\сервер\ресурс -> \\сервер\ресурс
            return v[4:] if v.startswith("\\\\?\\") else v
        link = f"/proc/self/fd/{f.fileno()}"
        return os.readlink(link) if os.path.exists(link) else None
    except Exception:
        return None


def same_path(a: str, b: str) -> bool:
    return bool(a and b) and os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


class CsvLog:
    """Запис показників у вибраний файл: лише цей файл, новий (secfs.remove_then_create — не за посиланням і не
    дописуючи чужий), колонки — ті, що були на початку запису."""
    FLUSH_EVERY = 5

    def __init__(self, path: str, cols: list):
        import secfs as SF
        if unsafe_target(path):
            raise PermissionError(path)
        p = os.path.abspath(path)
        expected = os.path.join(_long_path(os.path.dirname(p)), os.path.basename(p))
        self.path, self.cols, self.rows = path, cols, 0
        self.f = SF.remove_then_create(path, "w", encoding="utf-8-sig", newline="")  # BOM — Excel бачить кирилицю
        # 7.2: між перевіркою й відкриттям папку на шляху могли підмінити посиланням — тоді файл створено деінде.
        # Звіряємо, куди насправді веде дескриптор; не туди — закриваємо й прибираємо створене (воно порожнє).
        real = final_path(self.f)
        if real is not None and not same_path(real, expected):
            self.f.close()
            self.f = None
            try:
                os.remove(real)
            except OSError:
                pass
            raise PermissionError(path)
        self.f.write(csv_line(csv_header(cols)))
        self.f.flush()

    def write(self, ts: float, values: dict) -> None:
        self.f.write(csv_line(csv_row(ts, self.cols, values)))
        self.rows += 1
        if self.rows % self.FLUSH_EVERY == 0:
            self.f.flush()

    def close(self) -> None:
        if self.f:
            try:
                self.f.close()
            finally:
                self.f = None


# ───────────────────────── PawnIO: регістри процесора (чисті функції) ─────────────────────────
def tjmax_of(v):
    """MSR_TEMPERATURE_TARGET (0x1A2) -> TjMax °C або None."""
    if v is None:
        return None
    t = v >> 16 & 0xFF
    return t if 70 <= t <= 130 else None


def intel_temp(tjmax, status, need_valid: bool = False):
    """IA32_(PACKAGE_)THERM_STATUS -> °C: TjMax мінус цифровий відлік (біти 22:16). Для ядра (0x19C) біт 31 —
    «показ дійсний»; у пакета (0x1B1) його немає."""
    if tjmax is None or status is None or (need_valid and not status >> 31 & 1):
        return None
    t = tjmax - (status >> 16 & 0x7F)
    return t if 5 <= t <= 125 else None


def energy_unit(units):
    """RAPL_POWER_UNIT (Intel 0x606, AMD 0xC0010299): біти 12:8 — одиниця енергії 1/2^ESU Дж."""
    if units is None:
        return None
    esu = units >> 8 & 0x1F
    return 1.0 / (1 << esu) if esu else None


RAPL_MAX_GAP = 3 * INTERVAL_MS / 1000  # с


def rapl_watts(prev, cur, unit, dt, max_gap: float = RAPL_MAX_GAP):
    """Два покази 32-бітного лічильника енергії -> Вт (одне переповнення між ними враховуємо).
    7.2: між показами — пауза (розділ ховали, вікно згортали) довша за max_gap — None: середнє за всю паузу не є
    «зараз» (65 Вт показувало 2,6 Вт), а за кілька хвилин лічильник AMD може переповнитись не раз."""
    if prev is None or cur is None or not unit or not dt or dt <= 0 or dt > max_gap:
        return None
    d = (cur - prev) & 0xFFFFFFFF
    w = d * unit / dt
    return round(w, 1) if 0 <= w < 2000 else None


def amd_tctl(v):
    """SMN 0x00059800 (THM_TCON_CUR_TMP): біти 31:21 — °C × 8; біт 19 — діапазон −49 °C."""
    if v is None:
        return None
    t = (v >> 21 & 0x7FF) * 0.125
    if v >> 19 & 1:
        t -= 49
    return round(t, 1) if 5 <= t <= 125 else None


AMD_SMN_TCTL = 0x00059800


class MsrReader:
    """Що дає PawnIO, понад pawnio.CpuLive: температура пакета й найгарячішого ядра (Intel), Tctl (AMD), споживання
    пакета (RAPL). Усе лише читання; будь-який регістр, у якому модуль відмовив, — None."""

    def __init__(self, live, vendor: str):
        self.live, self.vendor = live, vendor
        self.tjmax = tjmax_of(live.msr(0x1A2)) if vendor == "Intel" else None
        self.unit = energy_unit(live.msr(0x606 if vendor == "Intel" else 0xC0010299))
        self.e_reg = 0x611 if vendor == "Intel" else 0xC001029B
        self.prev = None
        self.ncpu = min(os.cpu_count() or 1, 64)

    def _on_cpu(self, i: int, fn):
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentThread.restype = ctypes.c_void_p
        k32.SetThreadAffinityMask.restype = ctypes.c_size_t
        k32.SetThreadAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        th = k32.GetCurrentThread()
        old = k32.SetThreadAffinityMask(th, 1 << i)
        if not old:
            return None  # процесор не в цій групі (> 64 потоків)
        try:
            return fn()
        finally:
            k32.SetThreadAffinityMask(th, old)

    def core_max(self):
        """Найгарячіше ядро Intel: IA32_THERM_STATUS на кожному логічному процесорі (сусіди SMT дають те саме)."""
        if self.tjmax is None:
            return None
        drv, temps = self.live.drv, []
        for i in range(self.ncpu):
            out = self._on_cpu(i, lambda: drv.call("ioctl_read_msr", [0x19C], 1))
            t = intel_temp(self.tjmax, out[0] if out else None, need_valid=True)
            if t is not None:
                temps.append(t)
        return max(temps) if temps else None

    def amd_temp(self):
        import pawnio as PIO
        with PIO.BusLock("Global\\Access_PCI") as lk:  # індекс SMN ділимо з HWiNFO, LHM, Ryzen Master
            if not lk.held:
                return None
            out = self.live.drv.call("ioctl_read_smn", [AMD_SMN_TCTL], 1)
        return amd_tctl(out[0]) if out else None

    def read(self) -> dict:
        d = {}
        try:
            lv = self.live.read()
            d.update(vid=lv.get("volts"), clock0=lv.get("mhz"))
        except Exception:
            pass
        try:
            if self.vendor == "Intel":
                d["pkg"] = intel_temp(self.tjmax, self.live.msr(0x1B1))
                d["core_max"] = self.core_max()
            else:
                d["pkg"] = self.amd_temp()
        except Exception:
            pass
        try:
            now, raw = time.monotonic(), self.live.msr(self.e_reg)
            raw = raw & 0xFFFFFFFF if raw is not None else None
            if self.prev and raw is not None:  # після паузи rapl_watts дасть None — лише нова точка відліку
                d["power"] = rapl_watts(self.prev[1], raw, self.unit, now - self.prev[0])
            self.prev = (now, raw) if raw is not None else None
        except Exception:
            pass
        return d

    def close(self) -> None:
        try:
            self.live.close()
        except Exception:
            pass


# ───────────────────────── читання на Windows ─────────────────────────
LUID_RE = re.compile(r"luid_(0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+)")
NVIDIA_VEN = 0x10DE


def _luid(inst: str):
    m = LUID_RE.search(inst or "")
    return m.group(1).upper().replace("0X", "0x") if m else None


def pdh_gpu(counters: dict) -> dict:
    """Лічильники Windows -> {luid: {util %, vram МБ, shared МБ}} (завантаження — сума 3D-рушіїв усіх процесів)."""
    out = {}
    for inst, val in (counters.get("eng") or {}).items():
        lu = _luid(inst)
        if lu:
            d = out.setdefault(lu, {})
            d["util"] = min(100.0, d.get("util", 0.0) + float(val or 0))
    for key in ("vram", "shared"):
        for inst, val in (counters.get(key) or {}).items():
            lu = _luid(inst)
            if lu:
                d = out.setdefault(lu, {})
                d[key] = d.get(key, 0.0) + float(val or 0) / 2**20
    return out


class WinReader:
    """Усі джерела Windows. Створюється й читається лише з фонового потоку (по одному виклику за раз)."""

    def __init__(self, hw: dict):
        self.hw = hw or {}
        self.cpu_q = self.gpu_q = self.cpu_t = self.msr = None
        self.base = int(self.hw.get("mhz") or 0)
        self.nv = None          # [(індекс, назва)] або None — ще не пробували
        self.nv_next = 0.0
        self.adapters = None    # DXGI-адаптери з gpuinfo.probe (кеш на 6 годин у settings.json)
        self.probe_next = 0.0
        self.disk_cache = {}    # id -> (коли читати знову, °C)
        self._init()

    def _init(self) -> None:
        try:
            import cpusensors as CS
            import hwtests as HT
            import monitor as M
            self.cpu_q = M.Pdh(HT.CPU_COUNTERS, HT.CPU_ARRAYS)
            self.gpu_q = M.Pdh(None, {"eng": M.DIAG_ARRAY["gpu3d"], "vram": M.DIAG_ARRAY["vram"],
                                      "shared": r"\GPU Adapter Memory(*)\Shared Usage"})
            self.cpu_t = CS.CpuTemp()
        except Exception:
            pass  # без лічильників Windows відповідні рядки — «—»
        try:
            import cpuz as CZ
            import hwnative as HN
            import pawnio as PIO
            if PIO.status() == "ok":
                cid = CZ.parse_cpuid(CZ.read_cpuid_dump())
                live = PIO.CpuLive(cid.get("vendor") or "", cid.get("ext_family") or 0, cid.get("ext_model") or 0,
                                   int(HN._reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "~MHz") or 0))
                self.msr = MsrReader(live, cid.get("vendor") or "") if live.ok else None
        except Exception:
            self.msr = None

    # ── процесор, плата ──
    def cpu(self, out: list) -> None:
        import cpusensors as CS
        import monitor as M
        hw = self.hw
        title = hw.get("cpu") or "CPU"
        d = self.cpu_q.collect() if self.cpu_q and self.cpu_q.ok else {}
        zones = M._zone_c(d.get("temp"))
        m = self.msr.read() if self.msr else {}
        t, src = self.cpu_t.read() if self.cpu_t else (None, None)
        src = CS.source_name(src)
        if t is None and m.get("pkg") is not None:
            t, src = m["pkg"], "PawnIO"
        add = out.append
        add(reading("cpu.temp", "cpu", "cpu", title, "sn.r.temp", "c", t, src, always=True))
        if self.msr and self.msr.vendor == "Intel":
            add(reading("cpu.core_max", "cpu", "cpu", title, "sn.r.core_max", "c", m.get("core_max")))
        perf = d.get("perf")
        add(reading("cpu.load", "cpu", "cpu", title, "sn.r.load", "pct",
                    round(min(100.0, d["util"]), 1) if "util" in d else None, always=True))
        add(reading("cpu.clock", "cpu", "cpu", title, "sn.r.clock_avg", "mhz",
                    round(self.base * perf / 100) if perf and self.base else None, always=True))
        if self.msr:
            add(reading("cpu.clock0", "cpu", "cpu", title, "sn.r.clock0", "mhz", m.get("clock0")))
            add(reading("cpu.vid", "cpu", "cpu", title, "sn.r.vid", "v", m.get("vid")))
            add(reading("cpu.power", "cpu", "cpu", title, "sn.r.power_pkg", "w", m.get("power")))
        if zones:
            add(reading("board.acpi", "board", "board", tr("sn.g.board"), "sn.r.acpi", "c", round(max(zones), 1)))

    # ── відеокарти ──
    def _nv_list(self) -> list:
        """Картки NVIDIA через сеанс NVML, який тримає відкритим hardware.gpu_temp (7.1.1): той самий кеш і замок."""
        import gpubench as GB
        import hardware as H
        if self.nv is not None:
            return self.nv
        if time.monotonic() < self.nv_next:
            return []
        self.nv_next = time.monotonic() + NV_RETRY
        with H._NV_LOCK:
            base = H._NV_CACHE.get("")
            if base is None:
                base = GB.Nvml("")
                if not base.ok:
                    return []
                H._NV_CACHE[""] = base
            self.nv = [(i, name) for i, name, _mem in base.devices()]
        return self.nv

    def _nv_read(self, idx: int) -> dict:
        import gpubench as GB
        import hardware as H
        key = f"#sensors{idx}"  # ключ не збігається з назвою карти, якою користується gpu_temp
        with H._NV_LOCK:
            nv = H._NV_CACHE.get(key)
            if nv is None:
                nv = GB.Nvml(index=idx)
                if not nv.ok:
                    return {}
                H._NV_CACHE[key] = nv
            g = nv.read()
            if not g:  # драйвер перевстановили / карта зникла — наступного разу відкриємо заново
                H._NV_CACHE.pop(key, None)
                nv.close()
                self.nv = None
            return g

    def gpus(self, out: list) -> None:
        try:
            nv = self._nv_list()
        except Exception:
            nv = []
        for idx, name in nv:
            try:
                g = self._nv_read(idx)
            except Exception:
                g = {}
            nvml_rows(out, f"gpu{idx}", name, g)
        now = time.monotonic()
        if self.adapters is None and now >= self.probe_next:
            self.probe_next = now + PROBE_RETRY
            try:
                import gpuinfo as GI
                self.adapters = [a for a in (GI.probe() or {}).get("dxgi") or [] if not a.get("software")]
            except Exception:
                self.adapters = None
        counters = self.gpu_q.collect() if self.gpu_q and self.gpu_q.ok else {}
        per = pdh_gpu(counters)
        for i, a in enumerate(self.adapters or []):
            if nv and a.get("ven") == NVIDIA_VEN:
                continue  # NVIDIA — уже з NVML
            pdh_rows(out, f"gpux{i}", a.get("name") or "GPU", a, per.get(a.get("luid")) or ({} if per else None))

    # ── пам'ять, диски ──
    def ram(self, out: list) -> None:
        try:
            ms = E.mem_status()
            total = ms.ullTotalPhys / 2**30
            used = (ms.ullTotalPhys - ms.ullAvailPhys) / 2**30
            ram_rows(out, total, used, ms.dwMemoryLoad)
        except Exception:
            ram_rows(out, None, None, None)

    def disks(self, out: list) -> None:
        import storagehealth as SH
        now = time.monotonic()
        for dk in self.hw.get("disks") or []:
            num = str(dk.get("id"))
            if not num.isdigit():
                continue
            nvme = (dk.get("bus") or "").upper() == "NVME" or dk.get("media") == "NVMe"
            due, t = self.disk_cache.get(num, (0.0, None))
            if now >= due:
                try:
                    d = SH.read_nvme(num) if nvme else SH.read_ata(num)
                    t = d.get("temperature") if d else None
                except Exception:
                    t = None
                t = t if isinstance(t, (int, float)) and 0 < t < 100 else None
                self.disk_cache[num] = (now + (NVME_EVERY if nvme else ATA_EVERY), t)
            disk_rows(out, dk, t)

    def read(self) -> list:
        out = []
        for part in (self.cpu, self.gpus, self.ram, self.disks):
            try:
                part(out)
            except Exception:
                pass  # одне джерело впало — решта таблиці живе; його рядки просто «—»
        return out

    def close(self) -> None:
        for q in (self.cpu_q, self.gpu_q):
            if q:
                q.close()
        if self.msr:
            self.msr.close()
            self.msr = None


# ───────────────────────── рядки груп (спільні для Windows і демо) ─────────────────────────
def nvml_rows(out: list, gid: str, name: str, g: dict) -> None:
    add = out.append
    add(reading(f"{gid}.temp", gid, "gpu", name, "sn.r.temp", "c", g.get("temp"), always=True))
    add(reading(f"{gid}.load", gid, "gpu", name, "sn.r.load", "pct", g.get("util"), always=True))
    add(reading(f"{gid}.clock", gid, "gpu", name, "sn.r.core_clock", "mhz", g.get("clock"), always=True))
    add(reading(f"{gid}.mclock", gid, "gpu", name, "sn.r.mem_clock", "mhz", g.get("mem_clock")))
    add(reading(f"{gid}.vram", gid, "gpu", name, "sn.r.vram", "mb", g.get("vram_used"), always=True,
                sub=tr("sn.r.of", n=g["vram_total"], u=tr("sn.u.mb")) if g.get("vram_total") else ""))
    add(reading(f"{gid}.fan", gid, "gpu", name, "sn.r.fan", "pct", g.get("fan")))
    add(reading(f"{gid}.power", gid, "gpu", name, "sn.r.power", "w", g.get("power")))


def pdh_rows(out: list, gid: str, name: str, a: dict, d) -> None:
    """d=None — лічильники недоступні зовсім; {} — адаптер зараз простоює (0 %), а не «невідомо»."""
    import hardware as H
    integrated = (a.get("vram_mb") or 0) <= 512 or H.is_integrated(name, (a.get("vram_mb") or 0) / 1024)
    util = None if d is None else round(d.get("util", 0.0), 1)
    out.append(reading(f"{gid}.load", gid, "gpu", name, "sn.r.load", "pct", util, always=True))
    if integrated:
        v = None if d is None else round(d.get("shared", 0.0))
        out.append(reading(f"{gid}.shared", gid, "gpu", name, "sn.r.shared", "mb", v, always=True))
    else:
        v = None if d is None else round(d.get("vram", 0.0))
        out.append(reading(f"{gid}.vram", gid, "gpu", name, "sn.r.vram", "mb", v, always=True,
                           sub=tr("sn.r.of", n=a["vram_mb"], u=tr("sn.u.mb")) if a.get("vram_mb") else ""))


def ram_rows(out: list, total, used, load) -> None:
    title = tr("sn.g.ram") + (f" · {total:.0f} {tr('sn.u.gb')}" if total else "")
    out.append(reading("ram.used", "ram", "ram", title, "sn.r.ram_used", "gb",
                       round(used, 1) if used is not None else None, always=True))
    out.append(reading("ram.load", "ram", "ram", title, "sn.r.load", "pct", load, always=True))


def disk_kind(dk: dict) -> str:
    return "hdd" if dk.get("media") == "HDD" else "ssd"


def disk_rows(out: list, dk: dict, t) -> None:
    letters = ", ".join(f"{x}:" for x in dk.get("letters") or [])
    title = f"{dk.get('name') or '?'}" + (f" ({letters})" if letters else "")
    gid = f"disk{dk.get('id')}"
    out.append(reading(f"{gid}.temp", gid, disk_kind(dk), title, "sn.r.temp", "c", t, always=True))


# ───────────────────────── демо ─────────────────────────
class DemoReader:
    """Правдоподібні показники демо-заліза, що повільно «живуть» (навантаження хвилями, шум датчиків)."""

    def __init__(self, hw: dict):
        self.hw = hw or {}
        self.t0 = time.monotonic()
        self.rnd = random.Random(7)

    def _wave(self, period: float, phase: float = 0.0) -> float:
        """0..1"""
        return 0.5 + 0.5 * math.sin((time.monotonic() - self.t0) / period * 2 * math.pi + phase)

    def read(self) -> list:
        import pawnio as PIO
        hw, rnd, out = self.hw, self.rnd, []
        demo = E.DEMO
        load = 0.25 + 0.6 * self._wave(40)
        title = hw.get("cpu") or "CPU"
        base = int(hw.get("mhz") or 3000)
        hot = {"laptop": 88, "old": 80, "x3d": 82}.get(demo, 74)
        temp = round(38 + (hot - 38) * load + rnd.uniform(-0.8, 0.8), 1)
        pawn = PIO.status() == "demo"
        # як у hwtests._demo_sensor: ігровий ПК — Core Temp; X3D — лише PawnIO (Tctl); ноутбук і старий ПК без
        # програм датчиків і без PawnIO — температури процесора немає, є лише теплова зона ACPI у «Платі»
        src = "Core Temp" if demo in ("gaming", "xeon") else "PawnIO" if pawn else ""
        out.append(reading("cpu.temp", "cpu", "cpu", title, "sn.r.temp", "c", temp if src else None, src, True))
        intel = "intel" in title.lower()
        if pawn and intel:
            out.append(reading("cpu.core_max", "cpu", "cpu", title, "sn.r.core_max", "c",
                               round(temp + 4 + rnd.uniform(0, 3))))
        out.append(reading("cpu.load", "cpu", "cpu", title, "sn.r.load", "pct",
                           round(min(100.0, 100 * load + rnd.uniform(-3, 3)), 1), always=True))
        clock = round(base * (1.1 + 0.3 * load) + rnd.choice((-100, 0, 0, 100)))
        out.append(reading("cpu.clock", "cpu", "cpu", title, "sn.r.clock_avg", "mhz", clock, always=True))
        if pawn:
            out.append(reading("cpu.clock0", "cpu", "cpu", title, "sn.r.clock0", "mhz", clock + 200))
            out.append(reading("cpu.vid", "cpu", "cpu", title, "sn.r.vid", "v",
                               round(0.95 + 0.33 * load, 3) if intel else None))
            out.append(reading("cpu.power", "cpu", "cpu", title, "sn.r.power_pkg", "w",
                               round(18 + 150 * load * (1 if intel else 0.8) + rnd.uniform(-2, 2), 1)))
        for i, (name, vram_gb, _d) in enumerate(hw.get("gpus") or []):
            gl = 0.15 + 0.8 * self._wave(55, i)
            if "nvidia" in name.lower():
                total = int(vram_gb * 1024) - 4
                nvml_rows(out, f"gpu{i}", name, dict(
                    temp=round(36 + 38 * gl + rnd.uniform(-0.5, 0.5)), util=round(97 * gl),
                    clock=round(300 + 2200 * gl),
                    mem_clock=405 if gl < 0.2 else 10501, vram_used=round(900 + 0.55 * total * gl), vram_total=total,
                    fan=None if "laptop" in name.lower() else round(30 + 40 * gl),
                    power=round(8 + (75 if "laptop" in name.lower() else 180) * gl, 1)))
            else:
                vmb = int(vram_gb * 1024)
                pdh_rows(out, f"gpux{i}", name, dict(vram_mb=vmb),
                         dict(util=97 * gl if vram_gb >= 4 else 20 * gl, vram=min(0.9 * vmb, 900 + 6000 * gl),
                              shared=300 + 500 * gl))
        total = float(hw.get("ram_gb") or 16)
        used = total * (0.38 + 0.12 * self._wave(90)) + rnd.uniform(-0.05, 0.05)
        ram_rows(out, total, used, round(100 * used / total))
        for dk in hw.get("disks") or []:
            t0 = dk.get("temp")
            disk_rows(out, dk, round(t0 + 3 * self._wave(120) + rnd.uniform(-0.3, 0.3)) if t0 else None)
        zone = (hw.get("thermal") or {}).get("zone") if isinstance(hw.get("thermal"), dict) else None
        if zone:
            out.append(reading("board.acpi", "board", "board", tr("sn.g.board"), "sn.r.acpi", "c",
                               round(zone + 8 * load, 1)))
        return out

    def close(self) -> None:
        pass


# ───────────────────────── усе разом ─────────────────────────
class Hub:
    """read() — у фоновому потоці (по одному за раз); feed() / reset() / close() — у потоці інтерфейсу.
    7.2: close() під час читання не закриває джерела під ногами в потоку (PDH, PawnIO): їх закриє сам потік, щойно
    дочитає, — і ні читач, створений уже після close(), не лишиться відкритим."""

    def __init__(self, hw: dict):
        self.hw = hw or {}
        self.reader = None
        self.stats = {}
        self.seen = set()
        self.rows = []  # останній знімок, що показуємо (лише показники, які хоч раз мали значення, або always)
        self._lock = threading.Lock()
        self._busy = self._closed = False

    def read(self) -> list:
        with self._lock:
            if self._closed:
                return []
            self._busy = True
        try:
            if self.reader is None:
                self.reader = WinReader(self.hw) if E.IS_WIN else DemoReader(self.hw)
            return self.reader.read()
        finally:
            with self._lock:
                self._busy = False
                if self._closed:
                    self._close_reader()

    def feed(self, readings: list) -> list:
        rows = []
        for r in readings:
            if r["value"] is not None:
                self.seen.add(r["id"])
            elif not r.get("always") and r["id"] not in self.seen:
                continue  # можливості, якої в цього заліза немає (вентилятор ноутбучної карти), не показуємо
            self.stats.setdefault(r["id"], Stat()).add(r["value"])
            rows.append(r)
        self.rows = rows
        return rows

    def reset(self) -> None:
        for s in self.stats.values():
            s.reset()

    def _close_reader(self) -> None:
        if self.reader:
            try:
                self.reader.close()
            except Exception:
                pass
            self.reader = None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if not self._busy:
                self._close_reader()
