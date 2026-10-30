"""
OptimaX — що насправді бачать графічні API і на якій відеокарті малює гра (GPU Renderer Monitor).

Налаштування «Графіка» Windows (UserGpuPreferences) — лише побажання: DirectX 9 і OpenGL на нього не зважають, а гра в
справжньому повноекранному режимі може перейти на карту з монітором. Тому OptimaX перевіряє факт:

• probe() — окремий процес (OptimaX.exe --gpu-probe): адаптери DXGI (DirectX 10–12) з LUID, VEN/DEV, відеопам'яттю й
  кількістю виходів; чи створюється на кожному пристрій DirectX 12; пристрої Vulkan (назва, VEN/DEV, тип, версії API й
  драйвера, LUID). Окремий процес — бо збій драйвера під час такої перевірки не повинен закрити OptimaX.
• RenderMonitor — лічильники Windows «GPU Engine» по процесу гри: скільки 3D-роботи на кожному адаптері (за LUID).
  Лічильники є лише для драйверів WDDM 2.0+: у HD 4000 (WDDM 1.3) їх немає — тоді «гру малює вбудована» видно так:
  гра на передньому плані, а 3D на майнінговій карті ≈ 0.
• render_path — які бібліотеки завантажив процес гри: графічний API, шар (DXVK / Mesa поруч з exe) і драйвер якої
  відеокарти (NVIDIA / Intel / AMD / програмний WARP) обслуговує цей API. Драйвер вантажиться, коли гра створює пристрій
  на адаптері, тож це прямий доказ, і він працює й для HD 4000 без лічильників.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time

import engine as E
from i18n import tr

PROBE_TIMEOUT = 30
NVIDIA, INTEL, AMD = 0x10DE, 0x8086, 0x1002
VK_TYPES = {0: "other", 1: "integrated", 2: "discrete", 3: "virtual", 4: "cpu"}


# ───────────────────────── DXGI і DirectX 12 (у процесі перевірки) ─────────────────────────
class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


def _guid(s: str) -> _GUID:
    h = s.replace("-", "")
    g = _GUID(int(h[0:8], 16), int(h[8:12], 16), int(h[12:16], 16))
    for i in range(8):
        g.Data4[i] = int(h[16 + 2 * i:18 + 2 * i], 16)
    return g


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_uint32), ("HighPart", ctypes.c_int32)]


class _DESC1(ctypes.Structure):
    _fields_ = [("Description", ctypes.c_wchar * 128), ("VendorId", ctypes.c_uint), ("DeviceId", ctypes.c_uint),
                ("SubSysId", ctypes.c_uint), ("Revision", ctypes.c_uint), ("DedicatedVideoMemory", ctypes.c_size_t),
                ("DedicatedSystemMemory", ctypes.c_size_t), ("SharedSystemMemory", ctypes.c_size_t),
                ("AdapterLuid", _LUID), ("Flags", ctypes.c_uint)]


IID_FACTORY1 = "770aae78-f26f-4dba-a829-253c83d1b387"
IID_D3D12DEVICE = "189819f1-1db6-4b57-be54-1821339b85f7"
DXGI_NOT_FOUND = -2005270526  # 0x887A0002
DXGI_ADAPTER_FLAG_SOFTWARE = 2


def _method(obj, index: int, *argtypes):
    """Метод COM-інтерфейсу за номером у таблиці віртуальних функцій."""
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vtbl[index])
    return lambda *a: fn(obj, *a)


def _release(obj) -> None:
    if obj:
        vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(obj)


def luid_key(high: int, low: int) -> str:
    """LUID так, як його пишуть лічильники Windows: luid_0x00000000_0x0000D6B5."""
    return f"0x{high & 0xFFFFFFFF:08X}_0x{low & 0xFFFFFFFF:08X}"


def _dxgi_adapters() -> list:
    dxgi = ctypes.WinDLL("dxgi.dll")
    factory = ctypes.c_void_p()
    if dxgi.CreateDXGIFactory1(ctypes.byref(_guid(IID_FACTORY1)), ctypes.byref(factory)) != 0:
        return []
    d3d12 = None
    try:
        d3d12 = ctypes.WinDLL("d3d12.dll")
    except OSError:
        pass
    out = []
    try:
        enum = _method(factory, 12, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))  # IDXGIFactory1::EnumAdapters1
        i = 0
        while True:
            ad = ctypes.c_void_p()
            if enum(i, ctypes.byref(ad)) != 0:
                break
            try:
                d = _DESC1()
                _method(ad, 10, ctypes.POINTER(_DESC1))(ctypes.byref(d))  # IDXGIAdapter1::GetDesc1
                outputs = 0
                eo = _method(ad, 7, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))  # IDXGIAdapter::EnumOutputs
                while outputs < 16:
                    o = ctypes.c_void_p()
                    if eo(outputs, ctypes.byref(o)) != 0:
                        break
                    _release(o)
                    outputs += 1
                dx12 = None
                if d3d12 is not None:
                    # без вказівника на пристрій D3D12CreateDevice лише перевіряє: S_FALSE (1) — підтримується
                    rc = d3d12.D3D12CreateDevice(ad, 0xB000, ctypes.byref(_guid(IID_D3D12DEVICE)), None)
                    dx12 = rc in (0, 1)
                out.append(dict(name=d.Description, ven=d.VendorId, dev=d.DeviceId, sub=d.SubSysId,
                                vram_mb=d.DedicatedVideoMemory // 2**20, shared_mb=d.SharedSystemMemory // 2**20,
                                luid=luid_key(d.AdapterLuid.HighPart, d.AdapterLuid.LowPart),
                                software=bool(d.Flags & DXGI_ADAPTER_FLAG_SOFTWARE), outputs=outputs, dx12=dx12))
            finally:
                _release(ad)
            i += 1
    finally:
        _release(factory)
    return out


# ───────────────────────── Vulkan (у процесі перевірки) ─────────────────────────
class _VkAppInfo(ctypes.Structure):
    _fields_ = [("sType", ctypes.c_int), ("pNext", ctypes.c_void_p), ("pApplicationName", ctypes.c_char_p),
                ("applicationVersion", ctypes.c_uint32), ("pEngineName", ctypes.c_char_p),
                ("engineVersion", ctypes.c_uint32), ("apiVersion", ctypes.c_uint32)]


class _VkInstanceInfo(ctypes.Structure):
    _fields_ = [("sType", ctypes.c_int), ("pNext", ctypes.c_void_p), ("flags", ctypes.c_uint32),
                ("pApplicationInfo", ctypes.POINTER(_VkAppInfo)), ("enabledLayerCount", ctypes.c_uint32),
                ("ppEnabledLayerNames", ctypes.c_void_p), ("enabledExtensionCount", ctypes.c_uint32),
                ("ppEnabledExtensionNames", ctypes.c_void_p)]


def vk_version(v: int) -> str:
    return f"{(v >> 22) & 0x7F}.{(v >> 12) & 0x3FF}.{v & 0xFFF}"


def nv_driver(v: int) -> str:
    """Версія драйвера NVIDIA у Vulkan: 10 бітів major, 8 — minor (582.78)."""
    return f"{(v >> 22) & 0x3FF}.{(v >> 14) & 0xFF:02d}"


def parse_vk_props(buf: bytes) -> dict:
    """VkPhysicalDeviceProperties: перші поля — apiVersion, driverVersion, vendorID, deviceID, deviceType, deviceName[256]."""
    api, drv, ven, dev, typ = struct.unpack_from("<IIIII", buf, 0)
    name = bytes(buf[20:276]).split(b"\0", 1)[0].decode("utf-8", "replace")
    return dict(name=name, ven=ven, dev=dev, type=VK_TYPES.get(typ, "other"), api=vk_version(api),
                driver=nv_driver(drv) if ven == NVIDIA else vk_version(drv))


def _vulkan_devices() -> list:
    try:
        vk = ctypes.WinDLL("vulkan-1.dll")
    except OSError:
        return []
    app = _VkAppInfo(0, None, b"OptimaX", 1, b"OptimaX", 1, (1 << 22) | (1 << 12))  # Vulkan 1.1 — для LUID
    info = _VkInstanceInfo(1, None, 0, ctypes.pointer(app), 0, None, 0, None)
    inst = ctypes.c_void_p()
    if vk.vkCreateInstance(ctypes.byref(info), None, ctypes.byref(inst)) != 0:
        return []
    out = []
    try:
        n = ctypes.c_uint32(0)
        vk.vkEnumeratePhysicalDevices(inst, ctypes.byref(n), None)
        devs = (ctypes.c_void_p * n.value)()
        if n.value and vk.vkEnumeratePhysicalDevices(inst, ctypes.byref(n), devs) in (0, 5):
            vk.vkGetInstanceProcAddr.restype = ctypes.c_void_p
            p2 = vk.vkGetInstanceProcAddr(inst, b"vkGetPhysicalDeviceProperties2")
            props2 = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(p2) if p2 else None
            for i in range(n.value):
                buf = (ctypes.c_ubyte * 2048)()
                vk.vkGetPhysicalDeviceProperties(ctypes.c_void_p(devs[i]), buf)
                d = parse_vk_props(bytes(buf))
                if props2:  # VkPhysicalDeviceIDProperties: LUID, щоб зіставити з DXGI й лічильниками Windows
                    idp = (ctypes.c_ubyte * 64)()
                    struct.pack_into("<i", idp, 0, 1000071004)
                    p = (ctypes.c_ubyte * 2048)()  # VkPhysicalDeviceProperties2: sType, (4 байти вирівнювання), pNext
                    struct.pack_into("<i4xQ", p, 0, 1000059001, ctypes.addressof(idp))
                    props2(ctypes.c_void_p(devs[i]), p)
                    raw = bytes(idp)  # sType, pNext, deviceUUID[16], driverUUID[16], deviceLUID[8], nodeMask, LUIDValid
                    low, high = struct.unpack_from("<Ii", raw, 48)
                    if struct.unpack_from("<I", raw, 60)[0]:
                        d["luid"] = luid_key(high, low)
                out.append(d)
    finally:
        vk.vkDestroyInstance(inst, None)
    return out


def probe_child(argv) -> int:
    """Точка входу процесу перевірки: OptimaX.exe --gpu-probe --out=<json>."""
    out = next((a.split("=", 1)[1] for a in argv if a.startswith("--out=")), "")
    res = {"ts": int(time.time()), "dxgi": [], "vulkan": [], "errors": []}
    for key, fn in (("dxgi", _dxgi_adapters), ("vulkan", _vulkan_devices)):
        try:
            res[key] = fn()
        except Exception as e:
            res["errors"].append(f"{key}: {type(e).__name__}: {e}"[:300])
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    return 0


# ───────────────────────── перевірка з програми ─────────────────────────
DEMO_PROBE = {
    "mining": {"dxgi": [dict(name="Intel(R) HD Graphics 4000", ven=INTEL, dev=0x0162, vram_mb=32, shared_mb=8000,
                             luid="0x00000000_0x0000C2E1", software=False, outputs=1, dx12=False),
                        dict(name="NVIDIA GeForce GTX 1060 6GB", ven=NVIDIA, dev=0x1C07, vram_mb=6070, shared_mb=8000,
                             luid="0x00000000_0x0000D6B5", software=False, outputs=0, dx12=True),
                        dict(name="Microsoft Basic Render Driver", ven=0x1414, dev=0x8C, vram_mb=0, shared_mb=8000,
                             luid="0x00000000_0x0000F0F0", software=True, outputs=0, dx12=True)],
               "vulkan": [dict(name="NVIDIA GeForce GTX 1060 6GB", ven=NVIDIA, dev=0x1C07, type="discrete",
                               api="1.4.303", driver="582.78", luid="0x00000000_0x0000D6B5")]},
}


def probe(force: bool = False) -> dict:
    """Що бачать DirectX і Vulkan. Результат кешується до перезавантаження чи зміни драйвера (тут — на 6 годин)."""
    import features as F
    cached = F.CFG["gpu_probe"]
    if not force and isinstance(cached, dict) and time.time() - cached.get("ts", 0) < 6 * 3600:
        return cached
    if not E.IS_WIN:
        res = dict(DEMO_PROBE.get(E.DEMO) or {"dxgi": [], "vulkan": []}, ts=int(time.time()), errors=[])
    else:
        import gpubench as GB
        out = os.path.join(tempfile.gettempdir(), f"optimax-gpuprobe-{os.getpid()}-{int(time.time() * 1000)}.json")
        here = None if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        res = {"ts": int(time.time()), "dxgi": [], "vulkan": [], "errors": []}
        try:
            p = subprocess.run(GB.self_command() + ["--gpu-probe", f"--out={out}"], cwd=here, timeout=PROBE_TIMEOUT,
                               creationflags=E.CREATE_NO_WINDOW)
            with open(out, encoding="utf-8") as f:
                res = json.load(f)
            if p.returncode:
                res.setdefault("errors", []).append(f"exit {p.returncode}")
        except subprocess.TimeoutExpired:
            res["errors"].append("timeout")
        except (OSError, ValueError) as e:  # процес перевірки впав — найчастіше драйвер; це теж відповідь
            res["errors"].append(f"{type(e).__name__}: {e}"[:300])
        finally:
            try:
                os.remove(out)
            except OSError:
                pass
    F.CFG["gpu_probe"] = res
    return res


def mining_adapter(pr: dict) -> dict:
    """Майнінгова карта серед адаптерів DXGI: NVIDIA без виходів (у P106 їх немає взагалі)."""
    nv = [a for a in pr.get("dxgi") or [] if a.get("ven") == NVIDIA and not a.get("software")]
    return next((a for a in nv if not a.get("outputs")), nv[0] if nv else {})


def display_adapter(pr: dict) -> dict:
    return next((a for a in pr.get("dxgi") or [] if a.get("outputs") and not a.get("software")), {})


def vulkan_for(pr: dict, adapter: dict) -> dict:
    """Пристрій Vulkan тієї самої карти: за LUID, а якщо драйвер його не дав — за VEN/DEV."""
    for d in pr.get("vulkan") or []:
        if adapter.get("luid") and d.get("luid") == adapter["luid"]:
            return d
    return next((d for d in pr.get("vulkan") or []
                 if d.get("ven") == adapter.get("ven") and d.get("dev") == adapter.get("dev")), {})


def summary(pr: dict) -> dict:
    """Короткий стан для майнінгового ПК: {gpu, dx12, vulkan, vk_api, driver, display, display_counters}."""
    m = mining_adapter(pr)
    vk = vulkan_for(pr, m) if m else {}
    disp = display_adapter(pr)
    return dict(gpu=m.get("name", ""), luid=m.get("luid", ""), dx12=m.get("dx12"), vulkan=bool(vk),
                vk_api=vk.get("api", ""), driver=vk.get("driver", ""), vram_mb=m.get("vram_mb", 0),
                display=disp.get("name", ""), display_luid=disp.get("luid", ""), errors=pr.get("errors") or [])


# ───────────────────────── хто малює гру: лічильники GPU Engine ─────────────────────────
ENGINE_RE = re.compile(r"pid_(\d+)_luid_(0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+)_phys_\d+_eng_\d+_engtype_(\w+)")
PMEM_RE = re.compile(r"pid_(\d+)_luid_(0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+)_phys_\d+")


def engine_split(counters: dict, pids: set) -> dict:
    """Лічильники GPU Engine -> {luid: {"3d": %, "copy": %, "other": %}} лише для процесів pids."""
    out: dict = {}
    for inst, val in (counters or {}).items():
        m = ENGINE_RE.search(inst or "")
        if not m or int(m.group(1)) not in pids:
            continue
        luid, kind = m.group(2).upper().replace("0X", "0x"), m.group(3).lower()
        slot = "3d" if kind in ("3d", "graphics_1") else "copy" if kind.startswith("copy") else "other"
        d = out.setdefault(luid, {"3d": 0.0, "copy": 0.0, "other": 0.0})
        d[slot] += float(val or 0)
    return out


def process_vram(counters: dict, pids: set) -> dict:
    out: dict = {}
    for inst, val in (counters or {}).items():
        m = PMEM_RE.search(inst or "")
        if m and int(m.group(1)) in pids:
            luid = m.group(2).upper().replace("0X", "0x")
            out[luid] = out.get(luid, 0.0) + float(val or 0)
    return out


def verdict(samples: list, mining_luid: str) -> dict:
    """Висновок за кількома секундами вимірів: samples — [{"fg": bool, "eng": {luid: {...}}, "vram": {luid: байти}}].
    mining — малює майнінгова карта; igpu — гра на передньому плані, а на майнінговій карті 3D ≈ 0 (малює карта з
    монітором — у HD 4000 лічильників немає, тож її навантаження не видно); idle — гра не на передньому плані й нічого
    не малює (згорнута) — висновку немає; none — процес гри не знайдено."""
    if not samples:
        return {"verdict": "none"}
    fg = [s for s in samples if s.get("fg")]
    use = fg or samples
    luids = {k for s in use for k in (s.get("eng") or {})}
    avg = {lu: {k: round(sum((s.get("eng") or {}).get(lu, {}).get(k, 0.0) for s in use) / len(use), 1)
                for k in ("3d", "copy", "other")} for lu in luids}
    m3d = (avg.get(mining_luid) or {}).get("3d", 0.0)
    other3d = max([v["3d"] for lu, v in avg.items() if lu != mining_luid] or [0.0])
    vram = max([(s.get("vram") or {}).get(mining_luid, 0.0) for s in use] or [0.0])
    shared = max([(s.get("shared") or {}).get(mining_luid, 0.0) for s in use] or [0.0])
    res = dict(engines=avg, mining_3d=m3d, other_3d=other3d, copy=(avg.get(mining_luid) or {}).get("copy", 0.0),
               vram_mb=round(vram / 2**20), shared_mb=round(shared / 2**20), fg_share=round(100 * len(fg) / len(samples)))
    if m3d >= 3.0 and m3d >= other3d:
        res["verdict"] = "mining"
    elif other3d >= 3.0:
        res["verdict"] = "igpu"
    elif fg and m3d < 1.0:
        res["verdict"] = "igpu"
    else:
        res["verdict"] = "idle"
    return res


# ───────────────────────── хто малює гру: завантажені бібліотеки процесу ─────────────────────────
# драйвери користувацького режиму (UMD) за API. Вони вантажаться, лише коли гра створює пристрій на адаптері.
DRIVER_DLLS = (
    ("nvidia", "dx9", re.compile(r"^nvd3dum(x)?\.dll$")),
    ("nvidia", "dx11", re.compile(r"^nvwgf2um(x)?\.dll$")),  # DirectX 10 / 11 / 12
    ("nvidia", "gl", re.compile(r"^nvoglv(32|64)\.dll$")),  # OpenGL і Vulkan
    ("intel", "dx9", re.compile(r"^igdumd\w*\.dll$")),
    ("intel", "dx11", re.compile(r"^igd1\d\w*umd\w*\.dll$")),
    ("intel", "gl", re.compile(r"^ig\w*icd(32|64)\.dll$")),
    ("intel", "vulkan", re.compile(r"^igvk\w*\.dll$")),
    ("amd", "dx9", re.compile(r"^atiumd\w*\.dll$|^aticfx(32|64)\.dll$")),
    ("amd", "dx11", re.compile(r"^atidxx(32|64)\.dll$|^amdxx(32|64)\.dll$")),
    ("amd", "gl", re.compile(r"^atio6axx\.dll$|^atioglxx\.dll$")),
    ("amd", "vulkan", re.compile(r"^amdvlk(32|64)\.dll$")),
    ("warp", "dx11", re.compile(r"^d3d10warp\.dll$")),
)
API_DLLS = (("dx9", ("d3d9.dll", "d3d8.dll")), ("dx11", ("d3d11.dll",)), ("dx12", ("d3d12.dll",)),
            ("dx10", ("d3d10.dll", "d3d10_1.dll")), ("vulkan", ("vulkan-1.dll",)), ("gl", ("opengl32.dll",)))
LAYER_MARKERS = {"dxvk": ("d3d9.dll", "d3d8.dll", "d3d11.dll", "dxgi.dll", "d3d10core.dll"),
                 "mesa": ("opengl32.dll", "libgallium_wgl.dll")}


class _MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_uint32), ("th32ModuleID", ctypes.c_uint32), ("th32ProcessID", ctypes.c_uint32),
                ("GlblcntUsage", ctypes.c_uint32), ("ProccntUsage", ctypes.c_uint32), ("modBaseAddr", ctypes.c_void_p),
                ("modBaseSize", ctypes.c_uint32), ("hModule", ctypes.c_void_p), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


def process_modules(pid: int) -> list:
    """[(ім'я в нижньому регістрі, повний шлях)] бібліотек процесу — і 32-бітного з 64-бітної OptimaX. Захищені процеси
    (античит) не дають їх прочитати — тоді []."""
    if not E.IS_WIN:
        return []
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    k32.Module32FirstW.argtypes = k32.Module32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MODULEENTRY32W)]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    snap = None
    for _ in range(3):  # ERROR_BAD_LENGTH — процес саме вантажить бібліотеки: повторюємо
        snap = k32.CreateToolhelp32Snapshot(0x8 | 0x10, pid)  # TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32
        if snap and snap != ctypes.c_void_p(-1).value:
            break
        snap = None
        time.sleep(0.05)
    if not snap:
        return []
    out = []
    try:
        me = _MODULEENTRY32W()
        me.dwSize = ctypes.sizeof(_MODULEENTRY32W)
        ok = k32.Module32FirstW(snap, ctypes.byref(me))
        while ok and len(out) < 2000:
            out.append((me.szModule.lower(), me.szExePath))
            ok = k32.Module32NextW(snap, ctypes.byref(me))
    finally:
        k32.CloseHandle(snap)
    return out


def render_path(mods: list, game_dir: str = "") -> dict:
    """Що показують бібліотеки процесу: {apis: [...], layer: dxvk|mesa-d3d12|mesa-zink|"", drivers: {вендор: [API]},
    known: bool}. Шар — його бібліотека завантажена не з системної папки, а з папки гри."""
    names = {n for n, _ in mods}
    paths = {n: (p or "") for n, p in mods}
    sysroot = os.environ.get("SystemRoot", r"C:\Windows").lower()
    gd = (game_dir or "").lower().rstrip("\\/")

    def local(n: str) -> bool:
        pth = paths.get(n, "").lower()
        return bool(pth) and not pth.startswith(sysroot) and (not gd or pth.startswith(gd))

    apis = [a for a, dlls in API_DLLS if any(d in names for d in dlls)]
    layer = ""
    if any(local(n) for n in LAYER_MARKERS["mesa"] if n in names):
        layer = "mesa-zink" if "vulkan-1.dll" in names and "dxil.dll" not in names else "mesa-d3d12"
    elif any(local(n) for n in LAYER_MARKERS["dxvk"] if n in names) and "vulkan-1.dll" in names:
        layer = "dxvk"
    drivers: dict = {}
    for vendor, api, rx in DRIVER_DLLS:
        if any(rx.match(n) for n in names):
            drivers.setdefault(vendor, []).append(api)
    return dict(apis=apis, layer=layer, drivers=drivers, known=bool(mods))


def path_verdict(path: dict, mining_vendor: str = "nvidia") -> str:
    """mining — драйвер майнінгової карти завантажено, а драйвера вбудованої для графічного API — ні; igpu — навпаки;
    "" — бібліотеки не дають однозначної відповіді (обидва драйвери, нічого не прочитано)."""
    drv = path.get("drivers") or {}
    others = {v for v in drv if v != mining_vendor}
    if not path.get("known"):
        return ""
    if mining_vendor in drv and not others:
        return "mining"
    if others and mining_vendor not in drv:
        return "igpu" if others != {"warp"} else "warp"
    return ""


def describe_path(path: dict) -> str:
    """Рядок для людини: «DirectX 9 → DXVK → Vulkan · драйвер: NVIDIA»."""
    names = {"dx9": "DirectX 9", "dx10": "DirectX 10", "dx11": "DirectX 11", "dx12": "DirectX 12", "gl": "OpenGL",
             "vulkan": "Vulkan"}
    apis = [a for a in path.get("apis") or [] if a != "vulkan" or not path.get("layer")]
    parts = [" / ".join(names[a] for a in apis) or "?"]
    layer = path.get("layer")
    if layer == "dxvk":
        parts.append("DXVK → Vulkan")
    elif layer == "mesa-d3d12":
        parts.append("Mesa → DirectX 12")
    elif layer == "mesa-zink":
        parts.append("Mesa Zink → Vulkan")
    drv = ", ".join({"nvidia": "NVIDIA", "intel": "Intel", "amd": "AMD", "warp": "WARP"}[v]
                    for v in sorted(path.get("drivers") or {}))
    return " → ".join(parts) + (f" · {tr('gr.driver')}: {drv}" if drv else "")


class RenderMonitor:
    """Живий замір для одного процесу гри (раз на секунду, у потоці інтерфейсу — запит лічильників займає мілісекунди)."""

    def __init__(self):
        import monitor as M
        self.M = M
        self.q = M.Pdh(array={"eng": r"\GPU Engine(*)\Utilization Percentage",
                              "pmem": r"\GPU Process Memory(*)\Dedicated Usage",
                              "pshared": r"\GPU Process Memory(*)\Shared Usage"}) if E.IS_WIN else None

    def sample(self, pids: set, fg: bool) -> dict:
        if self.q is None:
            return {"fg": fg, "eng": {}, "vram": {}, "shared": {}}
        d = self.q.collect()
        return {"fg": fg, "eng": engine_split(d.get("eng"), pids), "vram": process_vram(d.get("pmem"), pids),
                "shared": process_vram(d.get("pshared"), pids)}

    def close(self) -> None:
        if self.q:
            self.q.close()


def pids_of(exe_names: set) -> set:
    names = {n.lower() for n in exe_names}
    return {pid for pid, n in E.processes() if (n or "").lower() in names}


DEMO_PATH = dict(apis=["dx9", "vulkan"], layer="dxvk", drivers={"nvidia": ["gl"]}, known=True)


def check(exe_names: set, mining_luid: str, seconds: int = 5, should_stop=None, game_dir: str = "") -> dict:
    """Замір на кілька секунд: на якому адаптері малює гра — за лічильниками GPU Engine і за драйвером, який завантажив
    процес. Якщо вони розходяться, вірити драйверу: лічильників у HD 4000 немає зовсім. Поза Windows — імітація."""
    if not E.IS_WIN:
        res = dict(verdict="mining", engines={mining_luid: {"3d": 64.0, "copy": 18.0, "other": 0.0}}, mining_3d=64.0,
                   other_3d=0.0, copy=18.0, vram_mb=3100, shared_mb=140, fg_share=100, path=dict(DEMO_PATH),
                   exe=sorted(exe_names)[0] if exe_names else "")
        res["path_text"] = describe_path(res["path"])
        return res
    pids = pids_of(exe_names)
    if not pids:
        return {"verdict": "none"}
    import monitor as M
    mon = RenderMonitor()
    samples = []
    try:
        for _ in range(seconds):
            if should_stop and should_stop():
                break
            time.sleep(1.0)
            fg = (M.foreground_process() or "").lower() in {n.lower() for n in exe_names}
            samples.append(mon.sample(pids, fg))
    finally:
        mon.close()
    res = verdict(samples, mining_luid)
    # процес гри, що малює: той, у кого завантажено графічний API (лаунчер поруч його не має)
    best = {}
    for pid in sorted(pids):
        path = render_path(process_modules(pid), game_dir)
        if path["apis"] and (not best or len(path["drivers"]) > len(best["drivers"])):
            best = path
    res["path"] = best
    res["path_text"] = describe_path(best) if best else ""
    pv = path_verdict(best) if best else ""
    if pv in ("igpu", "warp"):
        res["verdict"] = pv  # драйвер іншої карти — гра точно малює не на майнінговій
    elif pv == "mining" and res["verdict"] in ("igpu", "idle"):
        res["verdict"] = "mining" if res.get("mining_3d", 0) >= 1.0 or not res.get("engines") else res["verdict"]
    res["exe"] = next(iter(sorted(exe_names)), "")
    return res


def explain(res: dict, gpu: str) -> str:
    v = res.get("verdict")
    if v == "mining":
        return tr("gr.v.mining", gpu=gpu, d3=f"{res.get('mining_3d', 0):.0f}", copy=f"{res.get('copy', 0):.0f}",
                  vram=f"{(res.get('vram_mb') or 0) / 1024:.1f}")
    if v == "igpu":
        return tr("gr.v.igpu", gpu=gpu)
    if v == "warp":
        return tr("gr.v.warp")
    if v == "idle":
        return tr("gr.v.idle")
    return tr("gr.v.none")
