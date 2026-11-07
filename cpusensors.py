"""
OptimaX — справжня температура процесора з програм датчиків, які вже запущені.

Чому так. Windows не віддає температуру ядер без драйвера режиму ядра, а «теплова зона» ACPI
(\\Thermal Zone Information) на більшості настільних плат — це датчик плати або взагалі стала
(часто 27,8 °C), яка не змінюється під навантаженням. Раніше її показували як «CPU °C», тож під
стрес-тестом процесор «мав» 28 °C. Власний драйвер ставити не будемо (небезпечно, антивіруси),
тому читаємо готові дані тих програм, що вже мають свій драйвер і запущені користувачем:

  • Core Temp      — спільна пам'ять CoreTempMappingObject(Ex), увімкнена за замовчуванням;
  • HWiNFO         — спільна пам'ять Global\\HWiNFO_SENS_SM2 (Налаштування → «Shared Memory Support»);
  • AIDA64         — спільна пам'ять AIDA64_SensorValues (Параметри → Зовнішні програми → «Shared memory»);
  • LibreHardwareMonitor — його вебсервер http://127.0.0.1:8085/data.json (Options → Remote Web Server).

Усе лише читання. Розбір — чисті функції над байтами/текстом, їх перевіряють тести. Якщо жодна
програма не запущена — None, і тоді Hardware Center показує зону ACPI окремо з підписом «ACPI».
"""
from __future__ import annotations

import ctypes
import json
import re
import struct
import time

import engine as E

SOURCES = {"coretemp": "Core Temp", "hwinfo": "HWiNFO", "aida64": "AIDA64", "lhm": "LibreHardwareMonitor",
           "acpi": "ACPI"}
LHM_URL = "http://127.0.0.1:8085/data.json"


def plausible(t) -> bool:
    return isinstance(t, (int, float)) and 5.0 <= t <= 125.0


# ───────────────────────── спільна пам'ять ─────────────────────────
def read_mapping(name: str, limit: int = 4 << 20) -> bytes:
    """Вміст іменованої спільної пам'яті (лише читання) або b"", якщо її немає."""
    if not E.IS_WIN:
        return b""
    k32 = ctypes.windll.kernel32
    k32.OpenFileMappingW.restype = ctypes.c_void_p
    k32.OpenFileMappingW.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_wchar_p]
    k32.MapViewOfFile.restype = ctypes.c_void_p
    k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_size_t]
    k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    k32.VirtualQuery.restype = ctypes.c_size_t
    FILE_MAP_READ = 0x0004
    h = k32.OpenFileMappingW(FILE_MAP_READ, 0, name)
    if not h:
        return b""
    try:
        p = k32.MapViewOfFile(h, FILE_MAP_READ, 0, 0, 0)
        if not p:
            return b""
        try:
            class MBI(ctypes.Structure):
                _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                            ("AllocationProtect", ctypes.c_ulong), ("PartitionId", ctypes.c_ushort),
                            ("RegionSize", ctypes.c_size_t), ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong),
                            ("Type", ctypes.c_ulong)]
            mbi = MBI()
            size = mbi.RegionSize if k32.VirtualQuery(p, ctypes.byref(mbi), ctypes.sizeof(mbi)) else 0
            return ctypes.string_at(p, min(size, limit)) if size else b""
        finally:
            k32.UnmapViewOfFile(p)
    finally:
        k32.CloseHandle(h)


# ───────────────────────── Core Temp ─────────────────────────
# CORE_TEMP_SHARED_DATA: uiLoad[256], uiTjMax[128], uiCoreCnt, uiCPUCnt, fTemp[256], fVID, fCPUSpeed, fFSBSpeed,
# fMultiplier, sCPUName[100], ucFahrenheit, ucDeltaToTjMax (далі в Ex — додаткові поля, нам не потрібні)
CT_TJMAX, CT_CNT, CT_TEMP, CT_NAME, CT_FAHR, CT_DELTA = 1024, 1536, 1544, 2584, 2684, 2685


def parse_coretemp(b: bytes):
    """-> (найгарячіше ядро °C, назва процесора) або None."""
    if len(b) < CT_DELTA + 1:
        return None
    cores, cpus = struct.unpack_from("<II", b, CT_CNT)
    if not (1 <= cores <= 256 and 1 <= cpus <= 16 and cores * cpus <= 256):
        return None
    fahr, delta = b[CT_FAHR], b[CT_DELTA]
    temps = []
    for i in range(cores * cpus):
        t = struct.unpack_from("<f", b, CT_TEMP + 4 * i)[0]
        if delta:
            tj = struct.unpack_from("<I", b, CT_TJMAX + 4 * min(i // cores, 127))[0]
            t = tj - t
        if fahr:
            t = (t - 32) * 5 / 9
        if plausible(t):
            temps.append(t)
    if not temps:
        return None
    name = b[CT_NAME:CT_NAME + 100].split(b"\0")[0].decode("latin-1", "replace").strip()
    return round(max(temps), 1), name


# ───────────────────────── HWiNFO ─────────────────────────
HWI_SIG = 0x53695748  # 'HWiS'
HWI_HEAD = struct.Struct("<IIIqIIIIII")
HWI_LABELS = ("cpu package", "cpu (tctl/tdie)", "cpu die (average)", "cpu (tdie)", "cpu (tctl)", "core max",
              "cpu ccd1 (tdie)", "cpu")


def _cstr(b: bytes) -> str:
    return b.split(b"\0")[0].decode("cp1252", "replace").strip()


def parse_hwinfo(b: bytes, now: float = None):
    """Заголовок HWiNFO_SENSORS_SHARED_MEM2 + показники -> (°C, підпис) або None. Пріоритет — CPU Package /
    CPU (Tctl/Tdie) / Core Max з датчиків процесора, а «CPU» плати — лише коли немає інших."""
    if len(b) < HWI_HEAD.size:
        return None
    sig, _ver, _rev, poll, s_off, s_size, s_num, r_off, r_size, r_num = HWI_HEAD.unpack_from(b, 0)
    if sig != HWI_SIG or not (0 < r_num < 100000) or r_size < 316 or s_size < 264:
        return None
    if now is not None and poll and abs(now - poll) > 30:
        return None  # HWiNFO зупинив опитування — дані застарілі
    sensors = []
    for i in range(min(s_num, 4096)):
        o = s_off + i * s_size
        if o + 264 > len(b):
            break
        sensors.append(_cstr(b[o + 8:o + 136]))
    best = None
    for i in range(r_num):
        o = r_off + i * r_size
        if o + 316 > len(b):
            break
        typ, s_idx = struct.unpack_from("<II", b, o)
        if typ != 1:  # SENSOR_TYPE_TEMP
            continue
        label = _cstr(b[o + 12:o + 140]).lower()
        if label not in HWI_LABELS:
            continue
        unit = _cstr(b[o + 268:o + 284])
        val = struct.unpack_from("<d", b, o + 284)[0]
        if unit.endswith("F"):
            val = (val - 32) * 5 / 9
        if not plausible(val):
            continue
        sensor = sensors[s_idx] if s_idx < len(sensors) else ""
        rank = HWI_LABELS.index(label) + (0 if sensor.lower().startswith("cpu") else 10)
        if best is None or rank < best[0] or (rank == best[0] and val > best[1]):
            best = (rank, val, label)
    return (round(best[1], 1), best[2]) if best else None


# ───────────────────────── AIDA64 ─────────────────────────
AIDA_RE = re.compile(r"<temp><id>([^<]*)</id><label>([^<]*)</label><value>([^<]*)</value></temp>")


def parse_aida64(b: bytes):
    text = b.split(b"\0")[0].decode("utf-8", "replace")
    vals = {}
    for tid, label, value in AIDA_RE.findall(text):
        try:
            v = float(value.replace(",", "."))
        except ValueError:
            continue
        if plausible(v):
            vals[tid] = (v, label)
    for key in ("TCPUPKG", "TCPU"):
        if key in vals:
            return round(vals[key][0], 1), vals[key][1]
    cores = [v for k, v in vals.items() if k.startswith("TCC-")]
    if cores:
        v = max(cores)
        return round(v[0], 1), v[1]
    return None


# ───────────────────────── LibreHardwareMonitor ─────────────────────────
LHM_LABELS = ("cpu package", "core (tctl/tdie)", "core max", "cpu core", "core average", "core (tctl)")


def parse_lhm(data):
    """Дерево data.json -> (°C, підпис) або None. Беремо лише датчики процесора (SensorId /intelcpu/…, /amdcpu/…,
    або вузол під залізом із картинкою процесора)."""
    best = None

    def walk(node, under_cpu):
        nonlocal best
        if not isinstance(node, dict):
            return
        img = str(node.get("ImageURL") or "").lower()
        sid = str(node.get("SensorId") or "").lower()
        cpu = under_cpu or img.endswith("cpu.png") or sid.startswith(("/intelcpu/", "/amdcpu/"))
        text = str(node.get("Text") or "").strip().lower()
        val = str(node.get("Value") or "")
        if cpu and text in LHM_LABELS and ("°c" in val.lower() or "/temperature/" in sid):
            m = re.search(r"-?\d+(?:[.,]\d+)?", val)
            if m:
                v = float(m.group(0).replace(",", "."))
                if plausible(v):
                    rank = LHM_LABELS.index(text)
                    if best is None or rank < best[0]:
                        best = (rank, v, text)
        for ch in node.get("Children") or []:
            walk(ch, cpu)
    walk(data, False)
    return (round(best[1], 1), best[2]) if best else None


def _lhm_fetch(timeout: float = 0.35):
    import urllib.request
    try:
        with urllib.request.urlopen(LHM_URL, timeout=timeout) as r:
            raw = r.read(8 << 20)
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None


# ───────────────────────── усе разом ─────────────────────────
class CpuTemp:
    """read() -> (°C, джерело) або (None, None). Джерело, що спрацювало, опитується першим; ті, яких немає,
    перевіряються не частіше ніж раз на RETRY секунд, щоб опитування раз на секунду нічого не гальмувало."""
    RETRY = 15.0

    def __init__(self):
        self.src = None
        self.label = ""
        self.cpu_name = ""
        self._next = {}

    def _try(self, src: str, now: float):
        if src == "coretemp":
            for name in ("CoreTempMappingObjectEx", "CoreTempMappingObject"):
                r = parse_coretemp(read_mapping(name))
                if r:
                    self.cpu_name = r[1]
                    return r[0], "core max"
            return None
        if src == "hwinfo":
            r = parse_hwinfo(read_mapping("Global\\HWiNFO_SENS_SM2"), now=time.time())
            return r
        if src == "aida64":
            return parse_aida64(read_mapping("AIDA64_SensorValues", 1 << 20))
        if src == "lhm":
            d = _lhm_fetch()
            return parse_lhm(d) if d else None
        return None

    def read(self):
        if not E.IS_WIN:
            return None, None
        now = time.monotonic()
        order = ([self.src] if self.src else []) + [s for s in ("coretemp", "hwinfo", "aida64", "lhm") if s != self.src]
        for src in order:
            if src != self.src and self._next.get(src, 0) > now:
                continue
            try:
                r = self._try(src, now)
            except Exception:
                r = None
            if r:
                self.src, self.label = src, r[1]
                return r[0], src
            self._next[src] = now + self.RETRY
            if src == self.src:
                self.src = None
        return None, None


def acpi_static(vals: list, min_samples: int = 20, below: float = 50.0) -> bool:
    """Зона ACPI, що за весь замір під навантаженням (не менше min_samples секунд) не зрушила й на пів градуса і
    стоїть нижче за below, — стала плати (27,8 °C, 30 °C, 40 °C), а не процесор: під повним навантаженням процесор
    так не поводиться. Зону ноутбука, що оновлюється рідко й грубо (70 °C по 20 с), це не зачіпає."""
    v = [x for x in vals if isinstance(x, (int, float))]
    return len(v) >= min_samples and max(v) - min(v) < 0.5 and max(v) < below


def source_name(src) -> str:
    return SOURCES.get(src or "", "")
