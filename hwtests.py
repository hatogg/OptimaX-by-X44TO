"""
OptimaX Hardware Center — тести заліза: процесор, оперативна пам'ять, диск, комбіноване навантаження.

Кожен тест працює окремим процесом (OptimaX.exe --hw-test=cpu|ram|disk …), як і GPU-тест: збій під навантаженням не
закриває програму, а зупинка тесту — це просто завершення процесу. Процес тесту пише стан у JSON-файл, програма читає
його й паралельно стежить за датчиками (лічильники Windows, NVML), щоб зупинити все при небезпечній температурі.

• Процесор — цілочисельне навантаження, що перевіряє саме себе: SHA-256 і BLAKE2b мегабайтного блока та стиснення
  zlib з розпаковуванням. Кожен результат звіряється з еталоном, тож неправильна відповідь (нестабільний розгін,
  андервольт, перегрів) рахується як помилка, а не лише як «процесор завантажено». hashlib і zlib відпускають GIL, тож
  потоки навантажують усі ядра. Це не заміна Prime95 / OCCT з AVX — так і пишемо.
• Оперативна пам'ять — запис і перевірка шаблонів (нулі, одиниці, шахівниця, біжуча одиниця, випадкові дані, номер
  блока в блоці — помилки адресації) у стільки пам'яті, скільки безпечно взяти, не витісняючи Windows. Перевіряється
  лише виділена процесу пам'ять, а не вся RAM: для повної — «Діагностика пам'яті Windows» (з перезавантаженням).
• Диск — лише в окремому тимчасовому файлі на вибраному диску: послідовні запис і читання блоками по 1 МБ, випадкові
  4 КБ (QD1), без кешу Windows (FILE_FLAG_NO_BUFFERING). Файл видаляється після тесту й при зупинці; користувацьких
  файлів тест не торкається, диск не форматує. Перевірка читання поверхні лише читає сектори.

Результат кожного тесту — однаковий словник (result()): статус PASS / WARN / FAIL / SKIPPED / N/A, підсумок, показники,
ряди для графіків і чи тест справді йшов на цьому залізі (hw_tested) — для звітів і перевірки перед покупкою.
"""
from __future__ import annotations

import hashlib
import json
import math
import mmap
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
import zlib

import engine as E
from i18n import tr

PASS, WARN, FAIL, SKIPPED, NA = "pass", "warn", "fail", "skipped", "na"
STATUSES = (PASS, WARN, FAIL, SKIPPED, NA)
_RANK = {NA: 0, SKIPPED: 0, PASS: 1, WARN: 2, FAIL: 3}

CPU_TEMP_STOP = 95.0   # °C теплової зони ACPI: вище — аварійна зупинка
CPU_TEMP_WARN = 90.0
GPU_TEMP_STOP = 92.0   # °C ядра (NVML)
GPU_TEMP_WARN = 87.0
HOT_SECONDS = 3        # стільки секунд поспіль понад поріг — і стоп (одиничний сплеск датчика не рахуємо)
CPU_MINUTES = (1, 5, 15, 30, 60)
SCORE_SECONDS = 30     # тести «одне ядро» / «усі ядра»
WARMUP = 3

RAM_CHUNK = 64 << 20
RAM_BLOCK = 1 << 20
RAM_RESERVE_MB = 1536  # не чіпаємо: Windows і програмам має лишитися пам'яті
RAM_CHOICES = (25, 50, 75)  # % від доступної зараз

DISK_SIZES_MB = (256, 1024, 4096)
DISK_DIR = "OptimaX-DiskTest"
DISK_RANDOM_SECONDS = 6
DISK_FREE_MARGIN_MB = 2048


# ───────────────────────── спільне ─────────────────────────
def worst(statuses) -> str:
    """Найгірший статус: FAIL > WARN > PASS > (SKIPPED, N/A)."""
    st = [s for s in statuses if s in _RANK]
    if not st:
        return NA
    top = max(st, key=lambda s: _RANK[s])
    return top if _RANK[top] else (SKIPPED if SKIPPED in st else NA)


def result(test: str, status: str, summary: str = "", **kw) -> dict:
    """Підсумок будь-якого тесту Hardware Center."""
    # hw_tested: тест справді йшов на цьому залізі (поза Windows — демо-імітація, у звіті так і позначається)
    r = dict(test=test, status=status if status in STATUSES else NA, summary=summary, ts=int(time.time()),
             hw_tested=bool(E.IS_WIN))
    r.update(kw)
    r.setdefault("rows", [])
    r.setdefault("findings", [])
    return r


def save(cfg, res: dict, keep: int = 60) -> dict:
    """Останній результат кожного тесту й історія (без рядів для графіків у старих записах)."""
    last = dict(cfg["hwc_last"] or {})
    last[res["test"]] = res
    cfg.data["hwc_last"] = last
    hist = list(cfg["hwc_hist"] or [])
    hist.append({k: v for k, v in res.items() if k != "series"})
    cfg["hwc_hist"] = hist[-keep:]
    return res


def _write(path: str, data: dict) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def _args(argv) -> dict:
    out = {}
    for a in argv:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            out[k] = v
    return out


def median(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


# ───────────────────────── процес тесту ─────────────────────────
def child_main(argv) -> int:
    """Точка входу: OptimaX.exe --hw-test=cpu|ram|disk --out=<json> …"""
    a = _args(argv)
    kind, out = a.get("hw-test", ""), a.get("out") or os.path.join(tempfile.gettempdir(), "optimax-hwtest.json")
    fn = {"cpu": cpu_child, "ram": ram_child, "disk": disk_child}.get(kind)
    if not fn:
        _write(out, dict(state="error", error=f"unknown test {kind}"))
        return 2
    try:
        fn(a, out)
    except MemoryError:
        _write(out, dict(state="error", error="MemoryError"))
        return 3
    except Exception as e:  # noqa: BLE001 — будь-яка помилка тесту має дійти до програми
        _write(out, dict(state="error", error=f"{type(e).__name__}: {e}"[:400]))
        return 1
    return 0


class TestProc:
    """Запущений процес тесту: старт, читання стану, зупинка, прибирання. Процес зник без підсумку — збій (crash)."""

    def __init__(self, kind: str, args: dict):
        import gpubench as GB
        self.kind = kind
        self.out = os.path.join(tempfile.gettempdir(), f"optimax-hw{kind}-{os.getpid()}-{int(time.time() * 1000)}.json")
        cmd = GB.self_command() + [f"--hw-test={kind}", f"--out={self.out}"] + [f"--{k}={v}" for k, v in args.items()]
        here = None if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        flags = E.CREATE_NO_WINDOW if E.IS_WIN else 0
        self.proc = subprocess.Popen(cmd, cwd=here, creationflags=flags, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        self.stopped = False
        self.started = time.time()

    def poll(self) -> dict:
        try:
            with open(self.out, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {"state": "starting"}
        rc = self.proc.poll()
        if rc is not None and data.get("state") not in ("done", "error", "cancelled"):
            data = dict(data, state="cancelled" if self.stopped else "crash", exit_code=rc)
        return data

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def stop(self) -> None:
        self.stopped = True
        try:
            open(self.out + ".stop", "w").close()  # процес тесту сам прибере за собою (тимчасовий файл диска)
        except OSError:
            pass
        deadline = time.time() + 8
        while self.alive and time.time() < deadline:
            time.sleep(0.05)
        if self.alive:
            self.proc.kill()

    def cleanup(self) -> None:
        for p in (self.out, self.out + ".tmp", self.out + ".stop"):
            try:
                os.remove(p)
            except OSError:
                pass


def _stop_requested(out: str) -> bool:
    return os.path.exists(out + ".stop")


# ───────────────────────── процесор ─────────────────────────
TEXT_BLOCK = (b"OptimaX Hardware Center CPU check " + bytes(range(256)) + b"\x00" * 90) * 680  # ~256 КБ, стискається


def cpu_unit(data: bytes) -> tuple:
    """Одна порція роботи -> (sha256, blake2b, crc32 після стиснення й розпаковування)."""
    s = hashlib.sha256(data).digest()
    b = hashlib.blake2b(data, digest_size=32).digest()
    back = zlib.decompress(zlib.compress(TEXT_BLOCK, 1))
    return s, b, zlib.crc32(back) if back == TEXT_BLOCK else -1


def cpu_reference(data: bytes) -> tuple:
    """Еталон: три обчислення й більшість — нестабільний процесор не мусить зіпсувати сам еталон."""
    votes = [cpu_unit(data) for _ in range(3)]
    return max(votes, key=votes.count)


def cpu_child(a: dict, out: str) -> None:
    threads = max(1, min(256, int(a.get("threads") or os.cpu_count() or 1)))
    seconds = max(3, int(a.get("seconds") or SCORE_SECONDS))
    data = random.Random(int(a.get("seed") or 44)).randbytes(1 << 20)
    ref = cpu_reference(data)
    stop = threading.Event()
    counts = [0] * threads
    errors = [0]
    first_error = {}
    lock = threading.Lock()

    fault = [int(os.environ.get("OPTIMAX_TEST_CPU_FAULT") or 0)]  # лише для тестів: зіпсувати N результатів

    def worker(i: int):
        n = 0
        while not stop.is_set():
            got = cpu_unit(data)
            if fault[0] and i == 0 and n == 5:
                fault[0] -= 1
                got = (b"x" * 32,) + got[1:]
            n += 1
            counts[i] = n
            if got != ref:
                with lock:
                    errors[0] += 1
                    first_error.setdefault("t", round(time.time() - t0, 1))
                    first_error.setdefault("thread", i)

    t0 = time.time()
    state = dict(state="running", kind="cpu", threads=threads, seconds=seconds, t=0.0, ops=0, rate=0.0, errors=0,
                 series=[], pid=os.getpid())
    pool = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(threads)]
    for t in pool:
        t.start()
    last_n, last_t = 0, t0
    try:
        while True:
            time.sleep(0.5)
            now = time.time()
            n = sum(counts)
            if now - last_t >= 1.0:
                state["series"].append(round((n - last_n) / (now - last_t), 1))
                last_n, last_t = n, now
            el = now - t0
            state.update(t=round(el, 1), ops=n, errors=errors[0], rate=state["series"][-1] if state["series"] else 0.0)
            if first_error:
                state["first_error"] = dict(first_error)
            if _stop_requested(out):
                state["state"] = "cancelled"
                break
            if el >= seconds:
                state["state"] = "done"
                break
            _write(out, state)
    finally:
        stop.set()
        for t in pool:
            t.join(timeout=5)
    meas = state["series"][WARMUP:] or state["series"]
    state["score"] = round(median(meas) or 0.0, 1)
    state["per_thread"] = round(state["score"] / threads, 1)
    _write(out, state)


# ── датчики під час навантаження ──
CPU_COUNTERS = {
    "util": r"\Processor Information(_Total)\% Processor Utility",
    "perf": r"\Processor Information(_Total)\% Processor Performance",
    "limit": r"\Processor Information(_Total)\% Performance Limit",
}
CPU_ARRAYS = {"temp": r"\Thermal Zone Information(*)\Temperature",
              "passive": r"\Thermal Zone Information(*)\% Passive Limit"}


class Sensors:
    """Раз на секунду: завантаження й частота процесора, ліміт продуктивності, температура процесора; NVIDIA — NVML.

    Температура процесора — з Core Temp / HWiNFO / AIDA64 / LibreHardwareMonitor, якщо котрась запущена
    (cpusensors). Інакше — теплова зона ACPI з позначкою temp_src="acpi": на настільних платах це датчик плати
    або стала, тож у підсумку вона підписується як «ACPI», а незмінна під навантаженням відкидається.
    gpu_name — котра карта NVIDIA (вибрана для тесту чи та, що малює гру); без неї — карта з найбільшою пам'яттю."""

    def __init__(self, hw: dict = None, gpu: bool = False, gpu_name: str = ""):
        self.hw = hw or {}
        self.base = int(self.hw.get("mhz") or 0)
        self.q = None
        self.nv = None
        self.cpu_t = None
        self.gpu_name = gpu_name or ""
        self.samples = []
        self.i = 0
        if E.IS_WIN:
            import cpusensors as CS
            import monitor as M
            self.q = M.Pdh(CPU_COUNTERS, CPU_ARRAYS)
            self.cpu_t = CS.CpuTemp()
            if gpu:
                try:
                    import gpubench as GB
                    nv = GB.Nvml(self.gpu_name)
                    self.nv = nv if nv.ok else None
                except Exception:
                    self.nv = None

    def use_gpu(self, name: str) -> None:
        """Перемкнути датчики NVML на іншу карту (оверлей дізнається, на чому малює гра, через кілька секунд)."""
        self.gpu_name = name or ""
        if self.nv and name:
            try:
                self.nv.select(name)
            except Exception:
                pass

    def sample(self, load: float = 1.0) -> dict:
        """load — частка навантаження в демо-режимі (0 — простій)."""
        self.i += 1
        if not E.IS_WIN:
            s = _demo_sensor(self.hw, self.i, load)
        else:
            import monitor as M
            d = self.q.collect() if self.q and self.q.ok else {}
            zones = M._zone_c(d.get("temp"))
            passive = [v for v in (d.get("passive") or {}).values() if 0 < v <= 100]
            perf = d.get("perf")
            zone = round(max(zones), 1) if zones else None
            t, src = self.cpu_t.read() if self.cpu_t else (None, None)
            if t is None and zone is not None:
                t, src = zone, "acpi"
            s = dict(util=min(100.0, d["util"]) if "util" in d else None, perf=perf,
                     mhz=round(self.base * perf / 100) if (perf and self.base) else None,
                     limit=d.get("limit"), temp=t, temp_src=src, zone=zone,
                     passive=min(passive) if passive else None)
            if self.nv:
                g = self.nv.read()
                s.update(gpu_temp=g.get("temp"), gpu_clock=g.get("clock"), gpu_power=g.get("power"),
                         gpu_util=g.get("util"), gpu_throttle=g.get("throttle") or [], vram_used=g.get("vram_used"),
                         vram_total=g.get("vram_total"))
            try:
                ms = E.mem_status()
                s["ram_used"] = round((ms.ullTotalPhys - ms.ullAvailPhys) / 2**30, 1)
                s["ram_total"] = round(ms.ullTotalPhys / 2**30, 1)
            except Exception:
                pass
        s["t"] = len(self.samples)
        self.samples.append(s)
        return s

    def close(self) -> None:
        if self.q:
            self.q.close()
        if self.nv:
            self.nv.close()


def _demo_sensor(hw: dict, i: int, load: float) -> dict:
    """Демо: ноутбук гріється й скидає частоту, ігровий ПК стабільний."""
    rnd = random.Random(500 + i)
    lap = E.DEMO == "laptop"
    old = E.DEMO == "old"
    base = int(hw.get("mhz") or 3000)
    heat = 1 - math.exp(-i / (25 if lap else 60))
    temp = 42 + ((93 if lap else 84 if old else 71) - 42) * heat * load
    perf = (110 if old else 112 if E.DEMO == "mining" else 165) * load + 40 * (1 - load)  # i5-3570: 3,4 -> 3,8 ГГц
    limit = 100.0
    passive = 100.0
    if lap and load and i > 30:
        perf *= 0.82
        limit = 86.0
        passive = 92.0
    # джерело температури: ігровий ПК — Core Temp, ноутбук і старий ПК — теплова зона, що справді гріється,
    # настільна плата з майнінговою картою — стала зона ACPI 27,8 °C (так поводяться плати на H67/Z77)
    t, src = round(temp + rnd.uniform(-0.4, 0.4), 1), ("coretemp" if E.DEMO in ("gaming", "x3d", "xeon") else "acpi")
    zone = t if src == "acpi" else round(30 + 6 * heat * load, 1)
    if E.DEMO == "mining":
        t = zone = 27.8
    return dict(util=round(min(100.0, 99 * load + rnd.uniform(-1, 1) * load), 1), perf=round(perf, 1),
                mhz=round(base * perf / 100), limit=limit, temp=t, temp_src=src, zone=zone,
                passive=passive, gpu_temp=round(40 + 36 * heat * load, 1) if E.DEMO in ("gaming", "laptop", "xeon") else None,
                gpu_clock=2520 if load else 300, gpu_power=170.0 * load, gpu_util=97 * load, gpu_throttle=[],
                vram_used=round(1200 + 4800 * load), vram_total=8188 if lap else 12282,
                ram_used=round(6.2 + 5 * load, 1), ram_total=float(hw.get("ram_gb") or 16))


def danger(samples: list) -> str:
    """"cpu" / "gpu" — останні HOT_SECONDS вимірів поспіль понад поріг аварійної зупинки; інакше ""."""
    tail = samples[-HOT_SECONDS:]
    if len(tail) < HOT_SECONDS:
        return ""
    if all((s.get("temp") or 0) >= CPU_TEMP_STOP for s in tail):
        return "cpu"
    if all((s.get("gpu_temp") or 0) >= GPU_TEMP_STOP for s in tail):
        return "gpu"
    return ""


def cpu_findings(samples: list, base_mhz: int = 0) -> list:
    """Що видно з датчиків під навантаженням: падіння частоти (тротлінг), ліміт потужності, перегрів, нестабільна
    частота. -> [(рівень warn|fail|info, ключ, підстановки)]"""
    load = [s for s in samples if (s.get("util") or 0) >= 70]
    out = []
    if len(load) < 6:
        return out
    clocks = [s.get("mhz") or s.get("perf") for s in load]
    clocks = [c for c in clocks if c]
    if len(clocks) >= 6:
        n = max(3, len(clocks) // 5)
        head, tail = median(clocks[:n]), median(clocks[-max(3, len(clocks) * 3 // 10):])
        if head and tail and tail < head * 0.9:
            unit = "mhz" if load[0].get("mhz") else "pct"
            out.append((WARN, "hwc.f.clock_drop", dict(a=round(head), b=round(tail), pct=round((1 - tail / head) * 100),
                                                        unit=tr("hwc.u.mhz") if unit == "mhz" else "%")))
        mean = sum(clocks) / len(clocks)
        sd = math.sqrt(sum((c - mean) ** 2 for c in clocks) / len(clocks))
        if mean and sd / mean > 0.12:
            out.append((WARN, "hwc.f.clock_unstable", dict(cv=round(sd / mean * 100))))
    temps, src = cpu_temps(samples)
    temps = [s["temp"] for s in load if s.get("temp") is not None] if temps else []
    passive = [s["passive"] for s in load if s.get("passive") is not None]
    limits = [s["limit"] for s in load if s.get("limit") is not None]
    thermal = bool(passive and min(passive) < 100)
    if thermal:
        out.append((WARN, "hwc.f.thermal", dict(p=round(min(passive)))))
    if limits and median(limits) < 95 and not thermal and (not temps or max(temps) < 85):
        out.append((WARN, "hwc.f.power_limit", dict(p=round(median(limits)))))
    elif limits and median(limits) < 95 and thermal:
        out.append(("info", "hwc.f.limit_thermal", dict(p=round(median(limits)))))
    if temps and max(temps) >= CPU_TEMP_WARN:
        out.append((WARN, "hwc.f.cpu_hot", dict(t=round(max(temps)), src=temp_source(src))))
    if src == "acpi_static":
        zone = next((s.get("zone") for s in samples if s.get("zone") is not None), None)
        out.append(("info", "hwc.f.acpi_static", dict(t=round(zone) if zone is not None else "?")))
    elif src == "acpi" and temps:
        out.append(("info", "hwc.f.acpi_zone", {}))
    elif not temps:
        out.append(("info", "hwc.f.no_cpu_temp", {}))
    return out


def cpu_temps(samples: list):
    """-> (температури процесора, джерело). Джерело — "coretemp" / "hwinfo" / "aida64" / "lhm" (справжній датчик),
    "acpi" (теплова зона, що змінюється), "acpi_static" (зона стоїть на одному числі — це не процесор, температур
    немає) або None."""
    import cpusensors as CS
    vals = [s for s in samples if s.get("temp") is not None]
    if not vals:
        return [], None
    real = [s for s in vals if s.get("temp_src") not in ("acpi", None)]
    if real:
        srcs = [s["temp_src"] for s in real]
        return [s["temp"] for s in real], max(set(srcs), key=srcs.count)
    temps = [s["temp"] for s in vals]
    if not any(s.get("temp_src") == "acpi" for s in vals):
        return temps, None  # заміри старших версій (без джерела) лишаємо як були
    if CS.acpi_static(temps):
        return [], "acpi_static"
    return temps, "acpi"


FINDING_DEFAULTS = {"hwc.f.cpu_hot": lambda: dict(src=tr("hwc.temp_src.zone"))}


def finding_str(f) -> str:
    """Текст висновку. Висновки з історії старших версій можуть не мати нових підстановок (до 6.10 у «гарячому
    процесорі» не було джерела температури) — підставляємо типові, щоб не показувати «{src}»."""
    level, key, kw = f
    kw = dict(kw or {})
    for k, v in (FINDING_DEFAULTS.get(key, dict)() or {}).items():
        kw.setdefault(k, v)
    return tr(key, **kw)


def temp_source(src) -> str:
    import cpusensors as CS
    return CS.source_name(src) or tr("hwc.temp_src.zone")


def temp_text(t, src) -> str:
    """«45 °C (Core Temp)» / «28 °C (ACPI)» для підсумків."""
    return f"{t:.0f} °C ({temp_source(src)})" if t is not None else None


def live_temp(s: dict) -> str:
    """Рядок для прогресу: «CPU 45 °C» зі справжнього датчика, «ACPI 28 °C» з теплової зони."""
    if s.get("temp") is None:
        return ""
    return f"{'ACPI' if s.get('temp_src') == 'acpi' else 'CPU'} {s['temp']:.0f} °C"


def temp_series(samples: list) -> list:
    """Графік температури процесора; стала зона ACPI — порожній, щоб рівна лінія 28 °C не вдавала процесор."""
    _t, src = cpu_temps(samples)
    if src == "acpi_static":
        return [None for _ in samples]
    real = src not in ("acpi", None)
    return [s.get("temp") if (not real or s.get("temp_src") not in ("acpi", None)) else None for s in samples]


def gpu_findings(samples: list) -> list:
    temps = [s["gpu_temp"] for s in samples if s.get("gpu_temp") is not None]
    out = []
    if temps and max(temps) >= GPU_TEMP_WARN:
        out.append((WARN, "hwc.f.gpu_hot", dict(t=round(max(temps)))))
    thr = sorted({x for s in samples for x in (s.get("gpu_throttle") or [])})
    if thr:
        out.append((WARN, "hwc.f.gpu_throttle", dict(why=", ".join(thr))))
    return out


def status_of(findings: list, fail: bool = False) -> str:
    if fail or any(f[0] == FAIL for f in findings):
        return FAIL
    return WARN if any(f[0] == WARN for f in findings) else PASS


def cpu_result(state: dict, samples: list, hw: dict, mode: str) -> dict:
    """Підсумок тесту процесора з процесу тесту (state) і датчиків (samples)."""
    st = state.get("state")
    findings = []
    fail = False
    if st == "crash":
        findings.append((FAIL, "hwc.f.crash", dict(code=state.get("exit_code", "?"))))
        fail = True
    if state.get("errors"):
        fe = state.get("first_error") or {}
        findings.append((FAIL, "hwc.f.cpu_errors", dict(n=state["errors"], t=fe.get("t", "?"))))
        fail = True
    if state.get("danger"):
        findings.append((FAIL, "hwc.f.overheat_stop", dict(what=tr(f"hwc.dev.{state['danger']}"))))
        fail = True
    findings += cpu_findings(samples, int((hw or {}).get("mhz") or 0))
    status = status_of(findings, fail)
    if st == "cancelled" and status == PASS:
        status = SKIPPED
    temps, tsrc = cpu_temps(samples)
    mhz = [s.get("mhz") for s in samples if s.get("mhz")]
    rows = [("hwc.r.threads", state.get("threads")), ("hwc.r.score", state.get("score")),
            ("hwc.r.per_thread", state.get("per_thread")), ("hwc.r.errors", state.get("errors", 0)),
            ("hwc.r.temp_max", temp_text(max(temps), tsrc) if temps else None),
            ("hwc.r.mhz", f"{round(median(mhz))} / {min(mhz)} {tr('hwc.u.mhz')}" if mhz else None),
            ("hwc.r.duration", f"{int(state.get('t') or 0)} {tr('hwc.u.s')}")]
    return result(f"cpu_{mode}", status, tr(f"hwc.sum.cpu.{status}"), rows=rows, findings=findings,
                  score=state.get("score"), threads=state.get("threads"), errors=state.get("errors", 0),
                  series=dict(ops=state.get("series") or [], temp=temp_series(samples),
                              mhz=[s.get("mhz") for s in samples]),
                  temp_max=max(temps) if temps else None, temp_src=tsrc, mode=mode)


# ───────────────────────── оперативна пам'ять ─────────────────────────
def mem_available_mb() -> float:
    try:
        return E.mem_status().ullAvailPhys / 2**20
    except Exception:
        return 0.0


def ram_plan(avail_mb: float, pct: int) -> int:
    """Скільки МБ перевірити: pct% від доступної зараз, але Windows лишається щонайменше RAM_RESERVE_MB; кратно блоку."""
    usable = max(0.0, avail_mb - RAM_RESERVE_MB)
    mb = int(min(usable, avail_mb * max(5, min(90, pct)) / 100))
    return max(0, mb - mb % (RAM_CHUNK >> 20))


def ram_patterns(seed: int = 7) -> list:
    """[(назва, блок 1 МБ або None для «номер блока в блоці»)]."""
    walk = bytes(1 << (i % 8) for i in range(64))
    return [("zeros", b"\x00" * RAM_BLOCK), ("ones", b"\xff" * RAM_BLOCK), ("checker", b"\x55\xaa" * (RAM_BLOCK // 2)),
            ("walking", walk * (RAM_BLOCK // len(walk))), ("random", random.Random(seed).randbytes(RAM_BLOCK)),
            ("address", None)]


def _addr_block(chunk: int, block: int) -> bytes:
    tag = (chunk * 1_000_003 + block).to_bytes(8, "little") + b"OPTIMAXA"
    return tag * (RAM_BLOCK // 16)


def diff_bytes(a: bytes, b: bytes, limit: int = 64) -> int:
    """Скільки байтів відрізняються (до limit — далі не рахуємо, вистачить і того, що помилка є)."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            n += 1
            if n >= limit:
                break
    return n


def ram_child(a: dict, out: str) -> None:
    mb = int(a.get("mb") or 256)
    passes = max(1, int(a.get("passes") or 1))
    nchunks = max(1, (mb << 20) // RAM_CHUNK)
    state = dict(state="allocating", kind="ram", mb=mb, done_mb=0, total_mb=0, errors=0, bad_bytes=0, pattern="",
                 t=0.0, pid=os.getpid(), log=[])
    _write(out, state)
    t0 = time.time()
    chunks = []
    try:
        for _ in range(nchunks):
            chunks.append(bytearray(RAM_CHUNK))
            if _stop_requested(out):
                break
    except MemoryError:
        pass  # беремо стільки, скільки дали
    state["mb"] = len(chunks) * (RAM_CHUNK >> 20)
    pats = ram_patterns()
    total = 2 * len(chunks) * RAM_CHUNK * len(pats) * passes
    f = (os.environ.get("OPTIMAX_TEST_RAM_FAULT") or "").split(":")  # лише для тестів: шаблон:блок64МБ:блок1МБ
    fault = (f[0], int(f[1]), int(f[2])) if len(f) == 3 else None
    state.update(state="running", total_mb=total >> 20)
    done = 0
    per = RAM_CHUNK // RAM_BLOCK
    stopped = False
    for p in range(passes):
        for name, blk in pats:
            state["pattern"] = name
            for phase in ("write", "verify"):
                for ci, ch in enumerate(chunks):
                    for bi in range(per):
                        o = bi * RAM_BLOCK
                        want = blk if blk is not None else _addr_block(ci, bi)
                        if phase == "write":
                            ch[o:o + RAM_BLOCK] = want
                            if fault and (name, ci, bi) == fault:
                                ch[o + 7] ^= 0x10  # лише для тестів: «перевернутий біт»
                        elif ch[o:o + RAM_BLOCK] != want:
                            bad = diff_bytes(ch[o:o + RAM_BLOCK], want)
                            state["errors"] += 1
                            state["bad_bytes"] += bad
                            if len(state["log"]) < 20:
                                state["log"].append(dict(pattern=name, chunk=ci, block=bi, bytes=bad, p=p))
                    done += RAM_CHUNK
                    state.update(done_mb=done >> 20, t=round(time.time() - t0, 1))
                    if _stop_requested(out):
                        stopped = True
                        break
                    _write(out, state)
                if stopped:
                    break
            if stopped:
                break
        if stopped:
            break
    chunks.clear()
    state["state"] = "cancelled" if stopped else "done"
    state["t"] = round(time.time() - t0, 1)
    state["speed"] = round((done >> 20) / max(0.1, state["t"]))
    _write(out, state)


def ram_result(state: dict, hw: dict, avail_mb: float) -> dict:
    st = state.get("state")
    findings = []
    if st == "crash":
        findings.append((FAIL, "hwc.f.crash", dict(code=state.get("exit_code", "?"))))
    if state.get("errors"):
        findings.append((FAIL, "hwc.f.ram_errors", dict(n=state["errors"], b=state.get("bad_bytes", 0))))
    total_gb = float((hw or {}).get("ram_gb") or 0)
    tested = state.get("mb", 0)
    findings.append(("info", "hwc.f.ram_partial", dict(t=round(tested / 1024, 1), all=round(total_gb, 1) or "?")))
    status = status_of(findings)
    if st == "cancelled" and status == PASS:
        status = SKIPPED
    if st == "error":
        status = NA
        findings.append((WARN, "hwc.f.error", dict(err=state.get("error", "?"))))
    rows = [("hwc.r.tested", f"{tested} {tr('u.mb')}"), ("hwc.r.ram_total", f"{total_gb:.1f} GB" if total_gb else None),
            ("hwc.r.errors", state.get("errors", 0)), ("hwc.r.patterns", len(ram_patterns())),
            ("hwc.r.speed", f"{state.get('speed')} {tr('u.mb')}/{tr('hwc.u.s')}" if state.get("speed") else None),
            ("hwc.r.duration", f"{int(state.get('t') or 0)} {tr('hwc.u.s')}")]
    return result("ram", status, tr(f"hwc.sum.ram.{status}"), rows=rows, findings=findings, mb=tested,
                  errors=state.get("errors", 0), log=state.get("log") or [])


# ───────────────────────── диск ─────────────────────────
def disk_target(letter: str) -> str:
    """Тимчасова папка тесту на диску: X:\\OptimaX-DiskTest (на Linux у демо — тимчасова папка)."""
    if not E.IS_WIN:
        return os.path.join(tempfile.gettempdir(), DISK_DIR)
    drive = letter.rstrip(":\\/")[:1].upper() or "C"
    return drive + ":\\" + DISK_DIR


def disk_free_mb(path: str) -> float:
    try:
        import shutil
        root = path if os.path.isdir(path) else os.path.dirname(path) or path
        while root and not os.path.exists(root):
            root = os.path.dirname(root.rstrip("\\/"))
        return shutil.disk_usage(root or path).free / 2**20
    except OSError:
        return 0.0


def disk_size_ok(free_mb: float, size_mb: int) -> bool:
    """Тест не забирає останнє місце: після файлу тесту лишається щонайменше DISK_FREE_MARGIN_MB."""
    return free_mb - size_mb >= DISK_FREE_MARGIN_MB


class _RawFile:
    """Файл без кешу Windows (FILE_FLAG_NO_BUFFERING | WRITE_THROUGH) і з вирівняним буфером; поза Windows —
    O_DIRECT, якщо файлова система його вміє, інакше звичайний файл з fsync (позначаємо cached=True)."""

    def __init__(self, path: str, create: bool):
        self.path = path
        self.cached = False
        if E.IS_WIN:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateFileW.restype = wintypes.HANDLE
            k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            k32.ReadFile.argtypes = k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                                              ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            self.k32, self.ct, self.wt = k32, ctypes, wintypes
            GENERIC_RW = 0x80000000 | 0x40000000
            flags = 0x20000000 | 0x80000000  # FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH
            self.h = k32.CreateFileW(path, GENERIC_RW, 0, None, 1 if create else 3, flags | 0x80, None)  # CREATE_NEW / OPEN_EXISTING
            if not self.h or self.h == wintypes.HANDLE(-1).value:
                raise OSError(ctypes.get_last_error(), "CreateFileW", path)
        else:
            fl = os.O_RDWR | (os.O_CREAT | os.O_EXCL if create else 0)
            direct = getattr(os, "O_DIRECT", 0)
            try:
                self.fd = os.open(path, fl | direct, 0o600)
                self.cached = not direct
            except OSError:
                self.fd = os.open(path, fl, 0o600)
                self.cached = True

    def pwrite(self, buf, offset: int) -> int:
        if E.IS_WIN:
            return self._io(self.k32.WriteFile, buf, offset)
        return os.pwrite(self.fd, buf, offset)

    def pread(self, buf, offset: int) -> int:
        if E.IS_WIN:
            return self._io(self.k32.ReadFile, buf, offset)
        return os.preadv(self.fd, [buf], offset)

    def _io(self, fn, buf, offset: int) -> int:
        ct, wt = self.ct, self.wt
        if not self.k32.SetFilePointerEx(self.h, offset, None, 0):
            raise OSError(ct.get_last_error(), "SetFilePointerEx")
        n = wt.DWORD(0)
        addr = ct.addressof(ct.c_char.from_buffer(buf))
        if not fn(self.h, addr, len(buf), ct.byref(n), None):
            raise OSError(ct.get_last_error(), "ReadFile/WriteFile")
        return n.value

    def sync(self) -> None:
        if not E.IS_WIN:
            os.fsync(self.fd)

    def close(self) -> None:
        if E.IS_WIN:
            self.k32.CloseHandle(self.h)
        else:
            os.close(self.fd)


def _bench_seq(f: _RawFile, size: int, write: bool, buf, state: dict, out: str) -> float:
    blk = len(buf)
    t0 = time.perf_counter()
    done = 0
    while done < size:
        (f.pwrite if write else f.pread)(buf, done)
        done += blk
        if done % (64 << 20) == 0:
            state["done_mb"] = (state.get("base_mb", 0) + done) >> 20
            if _stop_requested(out):
                raise KeyboardInterrupt
            _write(out, state)
    if write:
        f.sync()
    dt = time.perf_counter() - t0
    return round(size / 2**20 / max(dt, 1e-6), 1)


def _bench_rand(f: _RawFile, size: int, write: bool, buf, seconds: float, out: str) -> dict:
    blk = len(buf)
    slots = max(1, size // blk)
    rnd = random.Random(99 if write else 98)
    n, lat = 0, []
    t0 = time.perf_counter()
    end = t0 + seconds
    while time.perf_counter() < end:
        o = rnd.randrange(slots) * blk
        s = time.perf_counter()
        (f.pwrite if write else f.pread)(buf, o)
        lat.append(time.perf_counter() - s)
        n += 1
        if n % 2048 == 0 and _stop_requested(out):
            raise KeyboardInterrupt
    if write:
        f.sync()
    dt = time.perf_counter() - t0
    iops = n / max(dt, 1e-6)
    return dict(iops=round(iops), mbs=round(iops * blk / 2**20, 1),
                lat_ms=round((median(lat) or 0) * 1000, 3), lat_max_ms=round(max(lat or [0]) * 1000, 1))


def disk_child(a: dict, out: str) -> None:
    folder = a.get("dir") or disk_target("C")
    size = max(16, int(a.get("mb") or 256)) << 20
    mode = a.get("mode") or "bench"
    state = dict(state="running", kind="disk", mode=mode, phase="prepare", done_mb=0, total_mb=(size >> 20) * 2,
                 pid=os.getpid())
    _write(out, state)
    if mode == "scan":
        return _surface_scan(a, out, state)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"bench-{os.getpid()}.tmp")
    res = {}
    f = None
    try:
        if disk_free_mb(folder) - (size >> 20) < DISK_FREE_MARGIN_MB:
            state.update(state="error", error="space")
            return
        mm = mmap.mmap(-1, 1 << 20)  # вирівняний за сторінкою буфер — вимога NO_BUFFERING / O_DIRECT
        mm.write(random.Random(5).randbytes(1 << 20))
        small = mmap.mmap(-1, 4096)
        small.write(random.Random(6).randbytes(4096))
        f = _RawFile(path, create=True)
        state["cached"] = f.cached
        state["phase"] = "seq_write"
        res["seq_write"] = _bench_seq(f, size, True, mm, state, out)
        state.update(phase="seq_read", base_mb=size)
        res["seq_read"] = _bench_seq(f, size, False, mm, state, out)
        secs = float(a.get("rand_seconds") or DISK_RANDOM_SECONDS)
        state["phase"] = "rand_read"
        _write(out, state)
        res["rand_read"] = _bench_rand(f, size, False, small, secs, out)
        state["phase"] = "rand_write"
        _write(out, state)
        res["rand_write"] = _bench_rand(f, size, True, small, secs, out)
        state.update(state="done", result=res, done_mb=state["total_mb"])
    except KeyboardInterrupt:
        state["state"] = "cancelled"
    finally:
        if f is not None:
            f.close()
        _remove_own(path, folder)
        state["cleaned"] = not os.path.exists(path)
        _write(out, state)


def _remove_own(path: str, folder: str) -> None:
    """Видаляє лише власний тимчасовий файл тесту і власну папку, якщо вона порожня."""
    if os.path.basename(path).startswith("bench-") and path.endswith(".tmp") and \
            os.path.dirname(os.path.abspath(path)) == os.path.abspath(folder):
        try:
            os.remove(path)
        except OSError:
            pass
    if os.path.basename(folder.rstrip("\\/")) == DISK_DIR:
        try:
            os.rmdir(folder)  # лише порожню
        except OSError:
            pass


def _surface_scan(a: dict, out: str, state: dict) -> None:
    """Вибіркове читання поверхні фізичного диска (лише читання): 1 МБ у випадкових місцях за seconds секунд.
    Помилки читання й дуже повільні сектори (> 500 мс) — ознака проблем з поверхнею HDD чи контролером SSD."""
    dev = a.get("device") or ""
    seconds = float(a.get("seconds") or 30)
    size = int(a.get("size") or 0)
    state.update(phase="scan", reads=0, read_errors=0, slow=0)
    if E.IS_WIN:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                    wintypes.DWORD, wintypes.HANDLE]
        h = k32.CreateFileW(dev, 0x80000000, 3, None, 3, 0x20000000, None)  # GENERIC_READ, NO_BUFFERING
        if not h or h == wintypes.HANDLE(-1).value:
            state.update(state="error", error=f"open {ctypes.get_last_error()}")
            _write(out, state)
            return
        k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                 ctypes.c_void_p]
        k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        mm = mmap.mmap(-1, 1 << 20)
        addr = ctypes.addressof(ctypes.c_char.from_buffer(mm))

        def read_at(off: int) -> bool:
            n = wintypes.DWORD(0)
            return bool(k32.SetFilePointerEx(h, off, None, 0) and k32.ReadFile(h, addr, 1 << 20, ctypes.byref(n), None))
    else:
        h = None
        rnd_fail = random.Random(3)

        def read_at(off: int) -> bool:
            time.sleep(0.002)
            return rnd_fail.random() > 0.0

    rnd = random.Random(11)
    blocks = max(1, size // (1 << 20)) if size else 1 << 18
    lat = []
    t0 = time.perf_counter()
    try:
        while time.perf_counter() - t0 < seconds:
            off = rnd.randrange(blocks) * (1 << 20)
            s = time.perf_counter()
            ok = read_at(off)
            dt = time.perf_counter() - s
            state["reads"] += 1
            if not ok:
                state["read_errors"] += 1
            elif dt > 0.5:
                state["slow"] += 1
            lat.append(dt)
            if state["reads"] % 32 == 0:
                state["t"] = round(time.perf_counter() - t0, 1)
                if _stop_requested(out):
                    state["state"] = "cancelled"
                    break
                _write(out, state)
        else:
            state["state"] = "done"
    finally:
        if h is not None:
            k32.CloseHandle(h)
    state.update(lat_ms=round((median(lat) or 0) * 1000, 2), lat_max_ms=round(max(lat or [0]) * 1000, 1))
    if state.get("state") == "running":
        state["state"] = "done"
    _write(out, state)


def disk_result(state: dict, disk: dict) -> dict:
    st = state.get("state")
    r = state.get("result") or {}
    findings = []
    if st == "error":
        findings.append((WARN, "hwc.f.disk_space" if state.get("error") == "space" else "hwc.f.error",
                         dict(err=state.get("error", "?"), m=DISK_FREE_MARGIN_MB)))
    if state.get("cached"):
        findings.append(("info", "hwc.f.disk_cached", {}))
    media = (disk or {}).get("media") or ""
    sw = r.get("seq_write") or 0
    sr = r.get("seq_read") or 0
    if r and media in ("SSD", "NVMe") and max(sr, sw) < 150:
        findings.append((WARN, "hwc.f.ssd_slow", dict(r=sr, w=sw)))
    if r and media == "HDD" and sr and sr < 40:
        findings.append((WARN, "hwc.f.hdd_slow", dict(r=sr)))
    rr, rw = r.get("rand_read") or {}, r.get("rand_write") or {}
    if rr and (rr.get("lat_max_ms") or 0) > 1000:
        findings.append((WARN, "hwc.f.disk_stall", dict(ms=rr["lat_max_ms"])))
    status = NA if st == "error" else status_of(findings)
    if st == "cancelled":
        status = SKIPPED
    if st == "crash":
        status = FAIL
        findings.append((FAIL, "hwc.f.crash", dict(code=state.get("exit_code", "?"))))
    rows = [("hwc.r.seq_read", f"{sr} {tr('u.mb')}/{tr('hwc.u.s')}" if sr else None),
            ("hwc.r.seq_write", f"{sw} {tr('u.mb')}/{tr('hwc.u.s')}" if sw else None),
            ("hwc.r.rand_read", f"{rr.get('iops')} IOPS · {rr.get('mbs')} {tr('u.mb')}/{tr('hwc.u.s')}" if rr else None),
            ("hwc.r.rand_write", f"{rw.get('iops')} IOPS · {rw.get('mbs')} {tr('u.mb')}/{tr('hwc.u.s')}" if rw else None),
            ("hwc.r.latency", f"{rr.get('lat_ms')} / {rr.get('lat_max_ms')} ms" if rr else None),
            ("hwc.r.cleaned", tr("hwc.yes") if state.get("cleaned", True) else tr("hwc.no"))]
    return result("disk_bench", status, tr(f"hwc.sum.disk.{status}"), rows=rows, findings=findings, bench=r,
                  disk=(disk or {}).get("name", ""), letter=state.get("letter", ""))


def scan_result(state: dict, disk: dict) -> dict:
    findings = []
    if state.get("state") == "error":
        findings.append((WARN, "hwc.f.error", dict(err=state.get("error", "?"))))
    if state.get("read_errors"):
        findings.append((FAIL, "hwc.f.read_errors", dict(n=state["read_errors"])))
    if state.get("slow"):
        findings.append((WARN, "hwc.f.slow_reads", dict(n=state["slow"])))
    status = NA if state.get("state") == "error" else status_of(findings)
    if state.get("state") == "cancelled" and status == PASS:
        status = SKIPPED
    rows = [("hwc.r.reads", state.get("reads", 0)), ("hwc.r.read_errors", state.get("read_errors", 0)),
            ("hwc.r.slow_reads", state.get("slow", 0)),
            ("hwc.r.latency", f"{state.get('lat_ms')} / {state.get('lat_max_ms')} ms" if state.get("reads") else None)]
    return result("disk_scan", status, tr(f"hwc.sum.scan.{status}"), rows=rows, findings=findings,
                  disk=(disk or {}).get("name", ""))


# ───────────────────────── GPU-тест OptimaX -> результат Hardware Center ─────────────────────────
def gpu_bench_result(b: dict) -> dict:
    """Останній GPU-тест / стрес-тест OptimaX -> результат Hardware Center."""
    v = b.get("verdict") or "bench"
    st = {"bench": PASS, "stable": PASS, "errors": FAIL, "crash": FAIL, "hot": WARN,
          "throttle": WARN}.get(v, NA)
    chk = (b.get("gpu_check") or {}).get("status")
    if chk == "wrong":
        st = WARN
    f = []
    if chk == "wrong":
        f.append((WARN, "gs.wrong_d", dict(got=b.get("gpu") or "?", want=b["gpu_check"].get("want") or "?")))
    if b.get("errors"):
        f.append((FAIL, "hwc.f.gpu_errors", dict(n=b["errors"], c=b.get("checks", 0))))
    if (b.get("temp_max") or 0) >= GPU_TEMP_WARN:
        f.append((WARN, "hwc.f.gpu_hot", dict(t=b["temp_max"])))
    if b.get("throttle"):
        f.append((WARN, "hwc.f.gpu_throttle", dict(why=", ".join(b["throttle"]))))
    rows = [("gb.s.gpu", b.get("gpu")), ("hwc.r.score", b.get("score")), ("gb.s.avg", b.get("avg")),
            ("1% low", b.get("low1")), ("hwc.r.temp_max", f"{b['temp_max']} °C" if b.get("temp_max") else None),
            ("hwc.r.errors", f"{b.get('errors', 0)} / {b.get('checks', 0)}" if b.get("mode") == "stress" else None)]
    r = result("gpu", st, tr(f"gb.vs.{v}") if v != "bench" else tr("hwc.gpu.bench_done"), rows=rows,
                  findings=f, series=dict(fps=b.get("series_fps") or [], temp=b.get("series_temp") or []))
    r["ts"] = b.get("ts") or r["ts"]
    return r


# ───────────────────────── демо поза Windows ─────────────────────────
class DemoProc:
    """Імітація процесу тесту для інтерфейсу на демо-залізі: та сама послідовність станів, прискорена."""

    SPEED = 30.0

    def __init__(self, kind: str, args: dict):
        self.kind, self.args = kind, dict(args)
        self.started = time.time()
        self.stopped = False
        self.duration = float(args.get("seconds") or (12 if kind == "disk" else 20))

    def poll(self) -> dict:
        el = (time.time() - self.started) * self.SPEED
        if self.stopped:
            return {"state": "cancelled", "kind": self.kind}
        done = el >= self.duration
        k = min(1.0, el / self.duration)
        if self.kind == "cpu":
            thr = int(self.args.get("threads") or 1)
            per = {"old": 210.0, "laptop": 520.0, "x3d": 760.0}.get(E.DEMO, 640.0)
            rate = per * thr * (0.86 if E.DEMO == "laptop" and el > 30 else 1.0)
            series = [round(rate * (1 + 0.01 * math.sin(i)), 1) for i in range(int(min(el, self.duration)))]
            st = dict(kind="cpu", threads=thr, seconds=self.duration, t=round(min(el, self.duration), 1),
                      ops=int(sum(series)), rate=series[-1] if series else 0.0, errors=0, series=series)
            if done:
                meas = series[WARMUP:] or series
                st.update(state="done", score=round(median(meas) or 0, 1),
                          per_thread=round((median(meas) or 0) / thr, 1))
            else:
                st["state"] = "running"
            return st
        if self.kind == "ram":
            mb = int(self.args.get("mb") or 256)
            total = 2 * mb * len(ram_patterns())
            st = dict(kind="ram", mb=mb, total_mb=total, done_mb=int(total * k), errors=0, bad_bytes=0, t=round(el, 1),
                      pattern=ram_patterns()[min(5, int(k * 6))][0], log=[])
            st.update(state="done", speed=4800) if done else st.update(state="running")
            return st
        if self.args.get("mode") == "scan":
            st = dict(kind="disk", mode="scan", reads=int(el * 40), read_errors=0, slow=0, t=round(el, 1))
            st.update(state="done", lat_ms=0.12 if E.DEMO != "old" else 14.5, lat_max_ms=3.1) if done else \
                st.update(state="running")
            return st
        media = {"old": (95, 88, 160, 150), "laptop": (3400, 2900, 9500, 21000)}.get(E.DEMO, (3500, 3100, 11000, 26000))
        st = dict(kind="disk", mode="bench", total_mb=int(self.args.get("mb") or 256) * 2,
                  done_mb=int(int(self.args.get("mb") or 256) * 2 * k), cached=False,
                  phase=("seq_write", "seq_read", "rand_read", "rand_write")[min(3, int(k * 4))])
        if done:
            sr, sw, ri, wi = media
            st.update(state="done", cleaned=True, result=dict(
                seq_read=float(sr), seq_write=float(sw),
                rand_read=dict(iops=ri, mbs=round(ri * 4 / 1024, 1), lat_ms=round(1000 / ri, 3), lat_max_ms=4.0),
                rand_write=dict(iops=wi, mbs=round(wi * 4 / 1024, 1), lat_ms=round(1000 / wi, 3), lat_max_ms=6.0)))
        else:
            st["state"] = "running"
        return st

    @property
    def alive(self) -> bool:
        return self.poll().get("state") == "running"

    def stop(self) -> None:
        self.stopped = True

    def cleanup(self) -> None:
        pass


def start(kind: str, args: dict):
    """Запуск тесту: справжній процес на Windows, імітація на демо-залізі."""
    if not E.IS_WIN:
        return DemoProc(kind, args)
    return TestProc(kind, args)
