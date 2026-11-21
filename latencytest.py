"""
OptimaX — тест затримки системи: чи встигає Windows вчасно віддати процесор грі, звуку й уводу.

Два виміри, кожен окремим процесом (OptimaX.exe --hw-test=latency_stall | latency_etw), як інші тести Hardware Center:

• Зупинки програми — потік найвищого пріоритету безперервно читає лічильник часу й записує кожен проміжок, коли його
  не виконували (процесор забрали переривання, DPC драйверів, BIOS чи процеси реального часу). Щосекунди потік
  переходить на наступне ядро, тож за тест перевірено всі. Права адміністратора не потрібні, у системі нічого не
  змінюється. Чому не таймер: високоточний таймер Windows сам прокидається із запізненням 0.3–1 мс (перевірено на
  ноутбуці з таймером 15.6 мс) — це шум, а не проблема драйверів, і він ховав би справжні зупинки.
• DPC і переривання (ISR) — журнал подій ядра Windows (ETW, власна сесія «OptimaX Latency»): скільки тривав кожен
  відкладений виклик і кожне переривання та якому драйверу він належить. Потрібні права адміністратора. Сесія лише
  читає події й зупиняється наприкінці; залишену після збою наступний тест закриває сам.

Подібно міряє LatencyMon, але драйвер OptimaX не встановлює. Обробка подій ядра в Python трохи навантажує процесор —
тому зупинки міряються в іншому процесі з вищим пріоритетом. Висновок — за найгіршим значенням, як у LatencyMon.
"""
from __future__ import annotations

import bisect
import gc
import json
import os
import struct
import threading
import time
import uuid

import engine as E
import hwtests as HT
from i18n import tr

SECONDS_CHOICES = (60, 180, 300)
STALL_MIN_US = 10               # коротші проміжки — звичайна робота циклу, не зупинка
STALL_WARN_US = 1000            # програма стояла від 1 мс — помітно для звуку й уводу
STALL_BAD_US = 4000             # від 4 мс — тріск звуку й мікрофризи майже напевно
EXEC_NOTE_US = 500              # DPC / ISR: від 0.5 мс — згадуємо драйвер
BURST_GAP_US = 20               # DPC / ISR, між якими менше 20 мкс, — одна безперервна серія на ядрі
EXEC_WARN_US = 1000
EXEC_BAD_US = 4000
BUCKETS_US = (10, 25, 50, 100, 250, 500, 1000, 2000, 4000, 8000)  # межі гістограми; останній кошик — «більше»
TOP_DRIVERS = 8
SESSION = "OptimaX Latency"
SESSION_GUID = uuid.UUID("5b0f3d2a-6c41-4f7e-9a8e-0b7d3c2e1f64")
KERNEL_SESSION = "NT Kernel Logger"
KERNEL_GUID = uuid.UUID("9e814aad-3204-11d2-9a82-006008a86939")  # SystemTraceControlGuid

PERFINFO_GUID = uuid.UUID("ce1dbfb4-137e-4da6-87b0-3f59aa102cbc").bytes_le  # клас подій PerfInfo (DPC, ISR)
IMAGE_GUID = uuid.UUID("2cb15d1d-5fc1-11d2-abe1-00a0c911f518").bytes_le     # клас подій Image (завантажені модулі)
ISR_OPS = frozenset((50, 67))          # ISR-MSI, ISR
DPC_OPS = frozenset((66, 68, 69))      # ThreadedDPC, DPC, TimerDPC
IMAGE_OPS = frozenset((3, 10))         # DCStart (уже завантажені), Load
HEADER_32BIT = 0x0020                  # EVENT_HEADER_FLAG_32_BIT_HEADER

# Драйвер -> що це за пристрій (для поради). Назва з «.sys» — точний збіг, без — початок назви.
DRIVER_KINDS = (
    ("net", ("ndis.sys", "tcpip.sys", "netio.sys", "afd.sys", "wdiwifi.sys", "nwifi.sys", "vwifibus.sys", "netwtw",
             "netwbw", "rt640x64", "rtux64", "rtwlan", "rtwlane", "rt68cx", "e1d", "e1r", "e2f", "ixgbe", "athw",
             "qcamain", "bcmwl", "mrvlpcie", "netadaptercx", "killer", "tap0901", "wintun", "wireguard")),
    ("gpu", ("nvlddmkm.sys", "amdkmdag.sys", "atikmdag.sys", "atikmpag.sys", "igdkmd", "dxgkrnl.sys", "dxgmms2.sys",
             "dxgmms1.sys", "basicdisplay.sys")),
    ("audio", ("hdaudbus.sys", "portcls.sys", "hdaudio.sys", "rtkvhd64.sys", "ks.sys", "usbaudio", "nvhda64v.sys",
               "atihdw", "intcaudiobus", "intcdaud", "intcsst")),
    ("storage", ("storport.sys", "stornvme.sys", "storahci.sys", "iastor", "ataport.sys", "disk.sys", "classpnp.sys",
                 "ntfs.sys", "volsnap.sys", "fltmgr.sys", "amdsata", "rstmwin", "secnvme", "samsungnvme", "nvme")),
    ("usb", ("usbxhci.sys", "usbport.sys", "ucx01000.sys", "usbhub3.sys", "usbhub.sys", "usbehci.sys", "hidclass.sys",
             "hidusb.sys", "mouclass.sys", "kbdclass.sys", "i8042prt.sys", "amdxhc", "iusb3")),
    ("power", ("acpi.sys", "intelppm.sys", "amdppm.sys", "processr.sys", "pci.sys", "cmbatt.sys", "battc.sys",
               "intelpep.sys", "amdpsp", "amdi2c")),
    ("security", ("wdfilter.sys", "wdnisdrv.sys", "mpfilter", "klif.sys", "aswsp.sys", "avgsp", "epfwwfp", "eamonm",
                  "bdselfpr", "cyprotectdrv", "sentinel")),
    ("wdf", ("wdf01000.sys",)),
    ("system", ("ntoskrnl.exe", "ntkrnlmp.exe", "hal.dll", "wpprecorder.sys", "cng.sys", "tm.sys", "clfs.sys")),
)
KINDS = tuple(k for k, _ in DRIVER_KINDS) + ("other",)


def driver_kind(name: str) -> str:
    n = (name or "").lower()
    for kind, pats in DRIVER_KINDS:
        for p in pats:
            if n == p or (not p.endswith((".sys", ".exe", ".dll")) and n.startswith(p)):
                return kind
    return "other"


def fmt_us(us) -> str:
    """240 мкс / 1.35 мс — так, як пишуть у LatencyMon."""
    if us is None:
        return tr("hwc.na")
    return tr("lat.ms", v=f"{us / 1000:.2f}") if us >= 1000 else tr("lat.us", v=f"{us:.0f}")


def bucket(us: float) -> int:
    return bisect.bisect_left(BUCKETS_US, us)


# ───────────────────────── адреса -> драйвер ─────────────────────────
class DriverMap:
    """Модулі ядра за початковою адресою: адреса процедури DPC/ISR -> найближчий модуль нижче (з розміром — точно)."""

    def __init__(self, mods=()):
        self.bases, self.items = [], []
        for m in mods:
            self.add(*m)

    def add(self, base: int, name: str, size: int = 0) -> None:
        if not base or not name:
            return
        name = os.path.basename(name.replace("\\", "/"))
        i = bisect.bisect_left(self.bases, base)
        if i < len(self.bases) and self.bases[i] == base:
            if size and not self.items[i][1]:
                self.items[i] = (name, size)
            return
        self.bases.insert(i, base)
        self.items.insert(i, (name, size))

    def __len__(self):
        return len(self.bases)

    def lookup(self, addr: int) -> str:
        i = bisect.bisect_right(self.bases, addr) - 1
        if i < 0 or not addr:
            return ""
        name, size = self.items[i]
        if size and addr >= self.bases[i] + size:
            return ""
        return name


def kernel_modules() -> list:
    """(адреса, назва) модулів ядра через EnumDeviceDrivers. Windows 11 24H2 віддає адреси лише з SeDebugPrivilege —
    вмикаємо його для власного процесу (адміністратор його має, але вимкненим)."""
    if not E.IS_WIN:
        return []
    import ctypes
    from ctypes import wintypes as W
    _enable_privilege("SeDebugPrivilege")
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.K32EnumDeviceDrivers.argtypes = [ctypes.POINTER(ctypes.c_void_p), W.DWORD, ctypes.POINTER(W.DWORD)]
    k32.K32GetDeviceDriverBaseNameW.argtypes = [ctypes.c_void_p, W.LPWSTR, W.DWORD]
    arr = (ctypes.c_void_p * 2048)()
    need = W.DWORD()
    if not k32.K32EnumDeviceDrivers(arr, ctypes.sizeof(arr), ctypes.byref(need)):
        return []
    out = []
    buf = ctypes.create_unicode_buffer(260)
    for addr in arr[:min(len(arr), need.value // ctypes.sizeof(ctypes.c_void_p))]:
        if addr and k32.K32GetDeviceDriverBaseNameW(addr, buf, 260):
            out.append((int(addr), buf.value))
    return out


def _enable_privilege(name: str) -> bool:
    import ctypes
    from ctypes import wintypes as W

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", W.DWORD), ("HighPart", W.LONG)]

    class TP(ctypes.Structure):
        _fields_ = [("Count", W.DWORD), ("Luid", LUID), ("Attr", W.DWORD)]

    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = W.HANDLE
    adv.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)]
    adv.LookupPrivilegeValueW.argtypes = [W.LPCWSTR, W.LPCWSTR, ctypes.POINTER(LUID)]
    adv.AdjustTokenPrivileges.argtypes = [W.HANDLE, W.BOOL, ctypes.POINTER(TP), W.DWORD, ctypes.c_void_p,
                                          ctypes.c_void_p]
    tok = W.HANDLE()
    if not adv.OpenProcessToken(k32.GetCurrentProcess(), 0x0020 | 0x0008, ctypes.byref(tok)):  # ADJUST | QUERY
        return False
    try:
        tp = TP(1, LUID(), 0x2)  # SE_PRIVILEGE_ENABLED
        if not adv.LookupPrivilegeValueW(None, name, ctypes.byref(tp.Luid)):
            return False
        ok = adv.AdjustTokenPrivileges(tok, False, ctypes.byref(tp), 0, None, None)
        return bool(ok) and ctypes.get_last_error() == 0
    finally:
        k32.CloseHandle(tok)


# ───────────────────────── статистика DPC / ISR ─────────────────────────
class ExecStats:
    """Тривалості DPC і ISR: по процедурах (адреса -> драйвер наприкінці), гістограми, найгірше за кожну секунду
    й частка часу процесора в DPC/ISR (найбільша серед ядер за секунду)."""

    def __init__(self, freq: int):
        self.k = 1e6 / float(freq or 1)
        self.routines = {}                 # адреса -> [isr_n, isr_max, isr_sum, dpc_n, dpc_max, dpc_sum]
        self.hist = {"isr": [0] * (len(BUCKETS_US) + 1), "dpc": [0] * (len(BUCKETS_US) + 1)}
        self.count = {"isr": 0, "dpc": 0}
        self.max = {"isr": 0.0, "dpc": 0.0}
        self.bad = 0                       # тривалість поза межами (від'ємна чи понад секунду) — пропущено
        self.t0 = None
        self.sec = -1
        self.sec_max = 0.0
        self.sec_cpu = {}
        self.series_max = []               # найдовший DPC/ISR за секунду, мкс
        self.series_pct = []               # найбільший % часу ядра в DPC/ISR за секунду
        # безперервна робота DPC/ISR на одному ядрі (кілька поспіль, переривання всередині DPC) — саме стільки стоїть
        # програма на цьому ядрі; порівнюється із зупинками з іншого виміру
        self.gap = BURST_GAP_US / self.k
        self.bursts = {}                   # ядро -> [початок, кінець] поточної серії, у тіках
        self.burst_max = 0.0
        self.core_burst = {}

    def add(self, isr: bool, ts: int, initial: int, routine: int, cpu: int) -> None:
        us = (ts - initial) * self.k
        if us < 0 or us > 1e6:
            self.bad += 1
            return
        if self.t0 is None:
            self.t0 = ts
        sec = int((ts - self.t0) * self.k / 1e6)
        # 7.1.1: події ETW приходять не строго за часом (буфери різних ядер). Закривати секунду на будь-якій «іншій»
        # давало фантомні секунди й занижений максимум; тепер секунди лише йдуть уперед, а запізніла подія
        # зараховується поточній секунді
        if sec > self.sec:
            self._close_second(sec)
        kind = "isr" if isr else "dpc"
        self.count[kind] += 1
        if us > self.max[kind]:
            self.max[kind] = us
        self.hist[kind][bucket(us)] += 1
        r = self.routines.get(routine)
        if r is None:
            r = self.routines[routine] = [0, 0.0, 0.0, 0, 0.0, 0.0]
        j = 0 if isr else 3
        r[j] += 1
        if us > r[j + 1]:
            r[j + 1] = us
        r[j + 2] += us
        if us > self.sec_max:
            self.sec_max = us
        self.sec_cpu[cpu] = self.sec_cpu.get(cpu, 0.0) + us
        b = self.bursts.get(cpu)
        if b is not None and b[0] - self.gap <= ts and initial <= b[1] + self.gap:
            if initial < b[0]:
                b[0] = initial
            if ts > b[1]:
                b[1] = ts
        else:
            b = self.bursts[cpu] = [initial, ts]
        dur = (b[1] - b[0]) * self.k
        if dur < 1e6:
            if dur > self.burst_max:
                self.burst_max = dur
            if dur > self.core_burst.get(cpu, 0.0):
                self.core_burst[cpu] = dur

    def _close_second(self, sec: int) -> None:
        if self.sec >= 0:
            self.series_max.append(round(self.sec_max, 1))
            self.series_pct.append(round(max(self.sec_cpu.values()) / 1e4, 2) if self.sec_cpu else 0.0)
            for _ in range(self.sec + 1, sec):  # секунди без жодної події
                self.series_max.append(0.0)
                self.series_pct.append(0.0)
        self.sec, self.sec_max, self.sec_cpu = sec, 0.0, {}

    def finish(self) -> None:
        if self.sec >= 0:
            self._close_second(self.sec + 1)

    def drivers(self, dmap: DriverMap, top: int = TOP_DRIVERS) -> list:
        """Найгірші драйвери: назва, вид, ISR (кількість, макс., сума мкс), DPC (те саме)."""
        agg = {}
        for addr, r in self.routines.items():
            name = dmap.lookup(addr) or "?"
            a = agg.setdefault(name, [0, 0.0, 0.0, 0, 0.0, 0.0])
            for j in (0, 3):
                a[j] += r[j]
                a[j + 1] = max(a[j + 1], r[j + 1])
                a[j + 2] += r[j + 2]
        rows = [dict(name=n, kind=driver_kind(n), isr_n=a[0], isr_max=round(a[1], 1), isr_sum=round(a[2]),
                     dpc_n=a[3], dpc_max=round(a[4], 1), dpc_sum=round(a[5])) for n, a in agg.items()]
        rows.sort(key=lambda d: max(d["isr_max"], d["dpc_max"]), reverse=True)
        return rows[:top]


def decode_header(rec: bytes):
    """EVENT_RECORD (x64, перші 104 байти) -> (час, клас, тип події, ядро, прапорці, довжина даних, адреса даних)."""
    flags, = struct.unpack_from("<H", rec, 4)
    ts, = struct.unpack_from("<q", rec, 16)
    return ts, rec[24:40], rec[45], rec[80], flags, struct.unpack_from("<H", rec, 86)[0], \
        struct.unpack_from("<Q", rec, 96)[0]


def decode_exec(data: bytes, ptr32: bool = False):
    """Дані події DPC / ISR: InitialTime (коли процедура почалася) і адреса процедури."""
    if ptr32:
        return struct.unpack_from("<qI", data, 0)
    return struct.unpack_from("<qQ", data, 0)


def decode_image(data: bytes, ptr32: bool = False):
    """Дані події Image: адреса, розмір, процес (0 — ядро) і шлях модуля."""
    if ptr32:
        base, size, pid = struct.unpack_from("<III", data, 0)
        off = 40
    else:
        base, size, pid = struct.unpack_from("<QQI", data, 0)
        off = 56
    name = data[off:].decode("utf-16-le", "ignore").split("\x00", 1)[0] if len(data) > off else ""
    return base, size, pid, name


# ───────────────────────── процес: зупинки програми ─────────────────────────
class StallStats:
    """Проміжки, коли зайнятий потік не виконувався: найбільший, скільки понад поріг, частка забраного часу, найгірший
    за кожну секунду й за кожне ядро, гістограма."""

    def __init__(self, cores: int):
        self.max = 0.0
        self.over = 0                  # зупинок від STALL_WARN_US
        self.count = 0                 # зупинок від STALL_MIN_US
        self.lost_us = 0.0             # сума зупинок
        self.run_us = 0.0              # скільки міряли
        self.hist = [0] * (len(BUCKETS_US) + 1)
        self.core_max = [0.0] * max(1, cores)
        self.series = []
        self.sec_max = 0.0

    def add(self, us: float, core: int) -> None:
        self.count += 1
        self.lost_us += us
        self.hist[bucket(us)] += 1
        if us >= STALL_WARN_US:
            self.over += 1
        if us > self.sec_max:
            self.sec_max = us
            if us > self.max:
                self.max = us
        if us > self.core_max[core]:
            self.core_max[core] = us

    def second(self, run_us: float) -> None:
        self.run_us += run_us
        self.series.append(round(self.sec_max, 1))
        self.sec_max = 0.0

    def state(self) -> dict:
        return dict(max_us=round(self.max, 1), over=self.over, stalls=self.count, hist=list(self.hist),
                    lost_pct=round(100.0 * self.lost_us / self.run_us, 3) if self.run_us else None,
                    core_max=[round(x, 1) for x in self.core_max], series=list(self.series))


def stall_child(a: dict, out: str) -> None:
    """Зупинки програми: потік TIME_CRITICAL (на двоядерних — HIGHEST, щоб не забрати процесор у решти) безперервно
    читає лічильник часу; щосекунди переходить на наступне ядро. Збирач сміття вимкнено, щоб його паузи не видавалися
    за зупинки системи; перший проміжок після переходу на інше ядро не рахується."""
    import ctypes
    from ctypes import wintypes as W
    seconds = float(a.get("seconds") or 60)
    cores = max(1, min(64, os.cpu_count() or 1))
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentThread.restype = W.HANDLE
    k32.GetCurrentProcess.restype = W.HANDLE
    k32.SetPriorityClass.argtypes = [W.HANDLE, W.DWORD]
    k32.SetThreadPriority.argtypes = [W.HANDLE, ctypes.c_int]
    k32.SetThreadAffinityMask.argtypes = [W.HANDLE, ctypes.c_size_t]
    k32.SetThreadAffinityMask.restype = ctypes.c_size_t
    me = k32.GetCurrentThread()
    if cores > 2:
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x80)    # HIGH_PRIORITY_CLASS (не REALTIME)
        k32.SetThreadPriority(me, 15)                           # THREAD_PRIORITY_TIME_CRITICAL
    else:
        k32.SetThreadPriority(me, 2)                            # THREAD_PRIORITY_HIGHEST
    st = StallStats(cores)
    clock = time.perf_counter_ns
    thr = STALL_MIN_US * 1000
    start = clock()
    end = start + int(seconds * 1e9)
    core = 0
    k32.SetThreadAffinityMask(me, 1 << core)
    gc.disable()
    try:
        t = sec_start = clock()
        next_sec = t + 1_000_000_000
        while True:
            t2 = clock()
            d = t2 - t
            t = t2
            if d > thr:
                st.add(d / 1000.0, core)
            if t2 >= next_sec:
                st.second((t2 - sec_start) / 1000.0)
                state = dict(kind="latency_stall", state="running", t=round((t2 - start) / 1e9, 1), seconds=seconds,
                             cores=cores)
                done, stop = t2 >= end, HT._stop_requested(out)
                if done or stop:
                    state.update(st.state(), state="done" if done else "cancelled")
                    HT._write(out, state)
                    return
                state.update(st.state())
                HT._write(out, state)
                core = (core + 1) % cores
                k32.SetThreadAffinityMask(me, 1 << core)
                t = sec_start = clock()
                next_sec = t + 1_000_000_000
    finally:
        gc.enable()


# ───────────────────────── процес: журнал подій ядра ─────────────────────────
def _etw_api():
    """Структури й функції ETW (advapi32) для ctypes."""
    import ctypes
    from ctypes import wintypes as W

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class WNODE_HEADER(ctypes.Structure):
        _fields_ = [("BufferSize", W.ULONG), ("ProviderId", W.ULONG), ("HistoricalContext", ctypes.c_uint64),
                    ("TimeStamp", ctypes.c_int64), ("Guid", GUID), ("ClientContext", W.ULONG), ("Flags", W.ULONG)]

    class EVENT_TRACE_PROPERTIES(ctypes.Structure):
        _fields_ = [("Wnode", WNODE_HEADER), ("BufferSize", W.ULONG), ("MinimumBuffers", W.ULONG),
                    ("MaximumBuffers", W.ULONG), ("MaximumFileSize", W.ULONG), ("LogFileMode", W.ULONG),
                    ("FlushTimer", W.ULONG), ("EnableFlags", W.ULONG), ("AgeLimit", W.LONG),
                    ("NumberOfBuffers", W.ULONG), ("FreeBuffers", W.ULONG), ("EventsLost", W.ULONG),
                    ("BuffersWritten", W.ULONG), ("LogBuffersLost", W.ULONG), ("RealTimeBuffersLost", W.ULONG),
                    ("LoggerThreadId", W.HANDLE), ("LogFileNameOffset", W.ULONG), ("LoggerNameOffset", W.ULONG)]

    class PROPS(ctypes.Structure):
        _fields_ = [("p", EVENT_TRACE_PROPERTIES), ("name", ctypes.c_wchar * 128), ("file", ctypes.c_wchar * 4)]

    class EVENT_TRACE_HEADER(ctypes.Structure):
        _fields_ = [("Size", W.USHORT), ("FieldTypeFlags", W.USHORT), ("Version", W.ULONG), ("ThreadId", W.ULONG),
                    ("ProcessId", W.ULONG), ("TimeStamp", ctypes.c_int64), ("Guid", GUID),
                    ("ProcessorTime", ctypes.c_uint64)]

    class EVENT_TRACE(ctypes.Structure):
        _fields_ = [("Header", EVENT_TRACE_HEADER), ("InstanceId", W.ULONG), ("ParentInstanceId", W.ULONG),
                    ("ParentGuid", GUID), ("MofData", ctypes.c_void_p), ("MofLength", W.ULONG),
                    ("ClientContext", W.ULONG)]

    class SYSTEMTIME(ctypes.Structure):
        _fields_ = [(n, W.WORD) for n in ("wYear", "wMonth", "wDayOfWeek", "wDay", "wHour", "wMinute", "wSecond",
                                          "wMilliseconds")]

    class TIME_ZONE_INFORMATION(ctypes.Structure):
        _fields_ = [("Bias", W.LONG), ("StandardName", ctypes.c_wchar * 32), ("StandardDate", SYSTEMTIME),
                    ("StandardBias", W.LONG), ("DaylightName", ctypes.c_wchar * 32), ("DaylightDate", SYSTEMTIME),
                    ("DaylightBias", W.LONG)]

    class TRACE_LOGFILE_HEADER(ctypes.Structure):
        _fields_ = [("BufferSize", W.ULONG), ("Version", W.ULONG), ("ProviderVersion", W.ULONG),
                    ("NumberOfProcessors", W.ULONG), ("EndTime", ctypes.c_int64), ("TimerResolution", W.ULONG),
                    ("MaximumFileSize", W.ULONG), ("LogFileMode", W.ULONG), ("BuffersWritten", W.ULONG),
                    ("LogInstanceGuid", GUID), ("LoggerName", ctypes.c_void_p), ("LogFileName", ctypes.c_void_p),
                    ("TimeZone", TIME_ZONE_INFORMATION), ("BootTime", ctypes.c_int64), ("PerfFreq", ctypes.c_int64),
                    ("StartTime", ctypes.c_int64), ("ReservedFlags", W.ULONG), ("BuffersLost", W.ULONG)]

    CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_void_p)

    class EVENT_TRACE_LOGFILEW(ctypes.Structure):
        _fields_ = [("LogFileName", W.LPWSTR), ("LoggerName", W.LPWSTR), ("CurrentTime", ctypes.c_int64),
                    ("BuffersRead", W.ULONG), ("ProcessTraceMode", W.ULONG), ("CurrentEvent", EVENT_TRACE),
                    ("LogfileHeader", TRACE_LOGFILE_HEADER), ("BufferCallback", ctypes.c_void_p),
                    ("BufferSize", W.ULONG), ("Filled", W.ULONG), ("EventsLost", W.ULONG),
                    ("EventRecordCallback", CALLBACK), ("IsKernelTrace", W.ULONG), ("Context", ctypes.c_void_p)]

    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.StartTraceW.argtypes = [ctypes.POINTER(ctypes.c_uint64), W.LPCWSTR, ctypes.c_void_p]
    adv.StartTraceW.restype = W.ULONG
    adv.ControlTraceW.argtypes = [ctypes.c_uint64, W.LPCWSTR, ctypes.c_void_p, W.ULONG]
    adv.ControlTraceW.restype = W.ULONG
    adv.OpenTraceW.argtypes = [ctypes.POINTER(EVENT_TRACE_LOGFILEW)]
    adv.OpenTraceW.restype = ctypes.c_uint64
    adv.ProcessTrace.argtypes = [ctypes.POINTER(ctypes.c_uint64), W.ULONG, ctypes.c_void_p, ctypes.c_void_p]
    adv.ProcessTrace.restype = W.ULONG
    adv.CloseTrace.argtypes = [ctypes.c_uint64]
    adv.CloseTrace.restype = W.ULONG

    def guid(u: uuid.UUID) -> GUID:
        g = GUID()
        ctypes.memmove(ctypes.byref(g), u.bytes_le, 16)
        return g

    def props(flags: int = 0, kernel: bool = False) -> PROPS:
        """kernel=False — власна системна сесія (Windows 8+, не заважає іншим програмам); True — класична
        «NT Kernel Logger», якщо системну сесію створити не вдалося."""
        pr = PROPS()
        pr.p.Wnode.BufferSize = ctypes.sizeof(PROPS)
        pr.p.Wnode.Flags = 0x00020000             # WNODE_FLAG_TRACED_GUID
        pr.p.Wnode.ClientContext = 1              # часові мітки — QPC (як у InitialTime подій DPC/ISR)
        pr.p.Wnode.Guid = guid(KERNEL_GUID if kernel else SESSION_GUID)
        pr.p.BufferSize = 128                     # КБ
        pr.p.MinimumBuffers = 16
        pr.p.MaximumBuffers = 64
        pr.p.FlushTimer = 1
        # EVENT_TRACE_REAL_TIME_MODE | EVENT_TRACE_SYSTEM_LOGGER_MODE
        pr.p.LogFileMode = 0x00000100 if kernel else 0x00000100 | 0x02000000
        pr.p.EnableFlags = flags
        pr.p.LoggerNameOffset = PROPS.name.offset
        pr.p.LogFileNameOffset = 0
        return pr

    return ctypes, adv, props, EVENT_TRACE_LOGFILEW, CALLBACK


ERROR_ALREADY_EXISTS = 183
ERROR_ACCESS_DENIED = 5
ERROR_NO_SYSTEM_RESOURCES = 1450
ERROR_WMI_INSTANCE_NOT_FOUND = 4201
FLAG_IMAGE_LOAD, FLAG_DPC, FLAG_INTERRUPT = 0x4, 0x20, 0x40


def stop_leftover() -> bool:
    """Зупинити сесію «OptimaX Latency», якщо її лишив тест, що аварійно завершився. True — сесія була."""
    if not E.IS_WIN:
        return False
    try:
        ctypes, adv, props, _L, _C = _etw_api()
        pr = props()
        return adv.ControlTraceW(0, SESSION, ctypes.byref(pr), 1) == 0  # EVENT_TRACE_CONTROL_STOP
    except Exception:
        return False


def etw_child(a: dict, out: str) -> None:
    """DPC/ISR з журналу подій ядра: власна системна сесія в реальному часі, події обробляє окремий потік."""
    seconds = float(a.get("seconds") or 60)
    if not E.is_admin():
        HT._write(out, dict(kind="latency_etw", state="error", error="admin"))
        return
    ctypes, adv, props, LOGFILE, CALLBACK = _etw_api()
    freq = ctypes.c_int64()
    ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
    stats = ExecStats(freq.value)
    dmap = DriverMap(kernel_modules())
    seen = {"events": 0}

    def on_event(ptr):
        try:
            rec = ctypes.string_at(ptr, 104)
            ts, cls, op, cpu, flags, ulen, uptr = decode_header(rec)
            seen["events"] += 1
            p32 = bool(flags & HEADER_32BIT)
            if cls == PERFINFO_GUID and (op in ISR_OPS or op in DPC_OPS):
                if uptr and ulen >= (12 if p32 else 16):
                    initial, routine = decode_exec(ctypes.string_at(uptr, 12 if p32 else 16), p32)
                    stats.add(op in ISR_OPS, ts, initial, routine, cpu)
            elif cls == IMAGE_GUID and op in IMAGE_OPS and uptr and ulen > 56:
                base, size, pid, name = decode_image(ctypes.string_at(uptr, min(ulen, 1200)), p32)
                if pid == 0:
                    dmap.add(base, name, size)
        except Exception:
            pass

    cb = CALLBACK(on_event)
    flags = FLAG_DPC | FLAG_INTERRUPT | FLAG_IMAGE_LOAD
    stop_leftover()
    handle = ctypes.c_uint64()
    name, kernel = SESSION, False
    rc = adv.StartTraceW(ctypes.byref(handle), name, ctypes.byref(props(flags)))
    if rc == ERROR_ALREADY_EXISTS:
        stop_leftover()
        rc = adv.StartTraceW(ctypes.byref(handle), name, ctypes.byref(props(flags)))
    if rc and rc not in (ERROR_ACCESS_DENIED, ERROR_ALREADY_EXISTS):
        # системна сесія недоступна (стара збірка Windows) — класичний журнал ядра; якщо він уже працює, це чужа
        # програма (LatencyMon, WPR, xperf), її не чіпаємо
        name, kernel = KERNEL_SESSION, True
        rc = adv.StartTraceW(ctypes.byref(handle), name, ctypes.byref(props(flags, kernel=True)))
    if rc:
        err = {ERROR_ACCESS_DENIED: "admin", ERROR_NO_SYSTEM_RESOURCES: "busy",
               ERROR_ALREADY_EXISTS: "busy"}.get(rc, f"etw:{rc}")
        HT._write(out, dict(kind="latency_etw", state="error", error=err, code=rc))
        return
    lf = LOGFILE()
    lf.LoggerName = name
    lf.ProcessTraceMode = 0x00000100 | 0x10000000 | 0x00001000  # REAL_TIME | EVENT_RECORD | RAW_TIMESTAMP
    lf.EventRecordCallback = cb
    th = adv.OpenTraceW(ctypes.byref(lf))
    if th == 0xFFFFFFFFFFFFFFFF:
        _stop(adv, ctypes, props, name, kernel)
        HT._write(out, dict(kind="latency_etw", state="error", error=f"open:{ctypes.get_last_error()}"))
        return
    th_arr = ctypes.c_uint64(th)
    proc_rc = {}
    worker = threading.Thread(target=lambda: proc_rc.setdefault("rc", adv.ProcessTrace(ctypes.byref(th_arr), 1,
                                                                                         None, None)), daemon=True)
    worker.start()
    start = time.time()
    lost = {}
    state = "running"
    try:
        while True:
            time.sleep(0.25)
            el = time.time() - start
            stop = HT._stop_requested(out)
            if el >= seconds or stop or not worker.is_alive():
                state = "done" if el >= seconds else ("cancelled" if stop else "error")
                break
            HT._write(out, _etw_state(stats, dmap, seen, "running", el, seconds, top=3))
    finally:
        lost = _stop(adv, ctypes, props, name, kernel)
        worker.join(10)
        adv.CloseTrace(th)
    stats.finish()
    st = _etw_state(stats, dmap, seen, state, time.time() - start, seconds)
    st.update(lost)
    st["session"] = "kernel" if kernel else "system"
    if state == "error":
        st["error"] = f"process:{proc_rc.get('rc')}"
    HT._write(out, st)


def _stop(adv, ctypes, props, name: str = SESSION, kernel: bool = False) -> dict:
    pr = props(kernel=kernel)
    rc = adv.ControlTraceW(0, name, ctypes.byref(pr), 1)
    if rc:
        return {}
    return dict(events_lost=int(pr.p.EventsLost), buffers_lost=int(pr.p.RealTimeBuffersLost + pr.p.LogBuffersLost))


def _etw_state(stats: ExecStats, dmap: DriverMap, seen: dict, state: str, el: float, seconds: float,
               top: int = TOP_DRIVERS) -> dict:
    drv = stats.drivers(dmap, top)
    return dict(kind="latency_etw", state=state, t=round(el, 1), seconds=seconds, events=seen["events"],
                isr_n=stats.count["isr"], dpc_n=stats.count["dpc"], isr_max=round(stats.max["isr"], 1),
                dpc_max=round(stats.max["dpc"], 1), hist=stats.hist, bad=stats.bad, modules=len(dmap),
                drivers=drv, series_max=list(stats.series_max), series_pct=list(stats.series_pct),
                burst_max=round(stats.burst_max, 1),
                core_burst={str(k): round(v, 1) for k, v in sorted(dict(stats.core_burst).items())})


def child(kind: str, a: dict, out: str) -> None:
    {"latency_stall": stall_child, "latency_etw": etw_child}[kind](a, out)


# ───────────────────────── підсумок ─────────────────────────
def _level(us, warn: float, bad: float) -> str:
    if us is None:
        return HT.NA
    return HT.FAIL if us >= bad else HT.WARN if us >= warn else HT.PASS


def latency_result(states: dict, admin: bool = True) -> dict:
    """Стани процесів «зупинки програми» й ETW -> результат Hardware Center «latency»."""
    sl, ew = states.get("stall") or {}, states.get("etw") or {}
    findings, statuses = [], []
    sl_ok = sl.get("state") in ("done", "cancelled") and sl.get("series")
    ew_ok = ew.get("state") in ("done", "cancelled") and (ew.get("isr_n") or ew.get("dpc_n"))
    if sl_ok:
        st = _level(sl.get("max_us"), STALL_WARN_US, STALL_BAD_US)
        statuses.append(st)
        if st != HT.PASS:
            findings.append((st, "lat.f.stall", dict(us=fmt_us(sl["max_us"]), n=sl.get("over", 0),
                                                     lim=fmt_us(STALL_WARN_US))))
    elif sl.get("state") in ("error", "crash"):
        findings.append(("info", "lat.f.stall_err", dict(code=sl.get("error") or sl.get("exit_code") or "?")))
    worst_exec = None
    if ew_ok:
        worst_exec = max(ew.get("isr_max") or 0, ew.get("dpc_max") or 0)
        statuses.append(_level(worst_exec, EXEC_WARN_US, EXEC_BAD_US))
        kinds, named = [], 0
        for d in ew.get("drivers") or []:
            for what in ("dpc", "isr"):
                us = d.get(f"{what}_max") or 0
                if us >= EXEC_NOTE_US and named < 5:
                    named += 1
                    lvl = _level(us, EXEC_WARN_US, EXEC_BAD_US)
                    findings.append((lvl if lvl != HT.PASS else "info", "lat.f.driver",
                                     dict(drv=d["name"], kind=tr(f"lat.kind.{d['kind']}"), what=what.upper(),
                                          us=fmt_us(us))))
                    if d["kind"] not in kinds:
                        kinds.append(d["kind"])
        for k in kinds[:3]:
            findings.append(("info", f"lat.adv.{k}", {}))
        busy = ew.get("burst_max") or worst_exec  # найдовша безперервна робота DPC/ISR на одному ядрі
        if sl_ok and (sl.get("max_us") or 0) >= STALL_WARN_US and busy < (sl.get("max_us") or 0) / 2:
            # програма стояла вдвічі довше, ніж драйвери безперервно тримали ядро, — процесор забирали не вони
            findings.append(("info", "lat.adv.stall_other", {}))
        if ew.get("events_lost") or ew.get("buffers_lost"):
            findings.append(("info", "lat.f.lost", dict(n=(ew.get("events_lost") or 0) +
                                                        (ew.get("buffers_lost") or 0))))
    elif not admin or ew.get("error") == "admin":
        findings.append(("info", "lat.f.no_admin", {}))
    elif ew.get("error") == "busy":
        findings.append(("info", "lat.f.etw_busy", {}))
    elif ew.get("error"):
        findings.append(("info", "lat.f.etw_err", dict(code=ew["error"])))
    if not statuses:
        status, summary = HT.NA, tr("lat.sum.na")
    else:
        status = HT.worst(statuses)
        summary = tr(f"lat.sum.{status}")
    drv = (ew.get("drivers") or [{}])[0] if ew_ok else {}
    rows = [("lat.r.stall_max", fmt_us(sl.get("max_us")) if sl_ok else None),
            ("lat.r.stall_n", f"{sl.get('over', 0)} / {sl.get('stalls', 0)}" if sl_ok else None),
            ("lat.r.stall_pct", f"{sl['lost_pct']:.2f} %" if sl_ok and sl.get("lost_pct") is not None else None),
            ("lat.r.dpc_max", _with_driver(ew, "dpc") if ew_ok else None),
            ("lat.r.isr_max", _with_driver(ew, "isr") if ew_ok else None),
            ("lat.r.burst", fmt_us(ew.get("burst_max")) if ew_ok and ew.get("burst_max") else None),
            ("lat.r.cpu_pct", f"{max(ew.get('series_pct') or [0]):.1f} %" if ew_ok else None),
            ("lat.r.duration", tr("lat.sec", n=int(max(sl.get("t") or 0, ew.get("t") or 0))))]
    r = HT.result("latency", status, summary, rows=rows, findings=findings,
                  series=dict(lat=sl.get("series") or [], dpc=ew.get("series_max") or []),
                  stall_max=sl.get("max_us"), exec_max=worst_exec, top_driver=drv.get("name"),
                  drivers=ew.get("drivers") or [], admin=bool(admin))
    if sl.get("state") == "cancelled" or ew.get("state") == "cancelled":
        r["cancelled"] = True
    return r


def _with_driver(ew: dict, what: str) -> str:
    us = ew.get(f"{what}_max") or 0
    best = max(ew.get("drivers") or [{}], key=lambda d: d.get(f"{what}_max") or 0)
    name = best.get("name") if (best.get(f"{what}_max") or 0) >= us - 0.05 and us else ""
    return f"{fmt_us(us)} ({name})" if name else fmt_us(us)


def describe(states: dict, seconds: float):
    """Рядок прогресу: час, найдовша зупинка програми й найдовший DPC/ISR на зараз."""
    sl, ew = states.get("stall") or {}, states.get("etw") or {}
    t = max(sl.get("t") or 0, ew.get("t") or 0)
    ex = max(ew.get("isr_max") or 0, ew.get("dpc_max") or 0) if ew.get("state") == "running" else 0
    return tr("hwc.p.latency", t=int(t), d=int(seconds), stall=fmt_us(sl.get("max_us")) if sl.get("series") else "—",
              exec=fmt_us(ex) if ex else "—"), t, seconds


# ───────────────────────── демо поза Windows ─────────────────────────
def demo_state(kind: str, el: float, duration: float, done: bool) -> dict:
    """Стан для DemoProc: спокійна система, на «старому» залізі — мережевий драйвер з довгими DPC."""
    bad = E.DEMO == "old"
    t = min(el, duration)
    n = int(t * 1000)
    if kind == "latency_stall":
        series = [round(60 + 30 * ((i * 7) % 5) + (2300 if bad and i % 13 == 5 else 0), 1) for i in range(int(t))]
        st = dict(kind=kind, t=round(t, 1), seconds=duration, cores=8, max_us=max(series or [0]),
                  over=sum(1 for v in series if v >= STALL_WARN_US), stalls=n // 4, lost_pct=0.08 if not bad else 0.9,
                  core_max=[max(series or [0])] + [120.0] * 7, hist=[0] * (len(BUCKETS_US) + 1), series=series)
        st["state"] = "done" if done else "running"
        return st
    drivers = [dict(name="ndis.sys" if bad else "nvlddmkm.sys", kind="net" if bad else "gpu", isr_n=0, isr_max=0.0,
                    isr_sum=0, dpc_n=n // 3, dpc_max=2350.0 if bad else 310.0, dpc_sum=n * 4),
               dict(name="ntoskrnl.exe", kind="system", isr_n=0, isr_max=0.0, isr_sum=0, dpc_n=n, dpc_max=95.0,
                    dpc_sum=n * 2),
               dict(name="ACPI.sys", kind="power", isr_n=n // 50, isr_max=44.0, isr_sum=n, dpc_n=0, dpc_max=0.0,
                    dpc_sum=0)]
    st = dict(kind=kind, t=round(t, 1), seconds=duration, events=n * 3, isr_n=n // 50, dpc_n=n + n // 3,
              isr_max=44.0, dpc_max=drivers[0]["dpc_max"], hist=None, bad=0, modules=180, drivers=drivers,
              series_max=[round(drivers[0]["dpc_max"] * (0.4 + 0.6 * ((i * 3) % 7 == 0)), 1) for i in range(int(t))],
              series_pct=[0.6 for _ in range(int(t))])
    st["state"] = "done" if done else "running"
    return st


