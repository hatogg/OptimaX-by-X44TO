"""
OptimaX — ігри на майнінговій відеокарті (P106 / P104 / P102, CMP HX).

У таких карт немає відеовиходів: монітор підключено до материнської плати, і картинку виводить вбудована
графіка. Щоб гру малювала майнінгова карта:

• DirectX 10 / 11 / 12 (більшість ігор). Windows уміє малювати на одній карті, а показувати через іншу, — треба лише
  призначити exe гри на «Високу продуктивність» (HKCU\\…\\DirectX\\UserGpuPreferences, GpuPreference=2). OptimaX сама
  знаходить встановлені ігри (Steam, Epic, GOG, Ubisoft і «Мої ігри») і призначає кожен їхній exe — з відкатом через
  журнал. Значення, яке вже хтось задав (користувач у «Графіці» чи «Мої ігри»), не чіпаємо.
• DirectX 9 / 8 і OpenGL. Вони бачать лише відеокарту, до якої підключено монітор, тож налаштування «Графіка» на них
  не діє (перевірено на P106 + HD 4000: CS:Source з «Високою продуктивністю» однаково малює HD 4000). Обхід — шар-
  перекладач у папці гри, лише за згодою й для кожної гри окремо:
    – DXVK (DirectX 9 / 8 → Vulkan; Vulkan старі вбудовані графіки на Windows не мають, тож бачить лише карту);
    – Mesa (pal1000/mesa-dist-win, драйвер d3d12: OpenGL → DirectX 12; карту обирає за змінною
      MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA).
  Бібліотеки тієї самої розрядності, що й exe (x64 чи x86). Онлайн-ігри з античитом можуть не пустити гру з чужою
  d3d9.dll / opengl32.dll. DirectX 9 видно з таблиці імпорту exe або з бібліотек рушія поруч (Source:
  bin\\shaderapidx9.dll). Ігри на Adobe AIR лишаються як є.

Шари не входять в інсталятор (десятки мегабайтів): CI перепаковує збірки mesa-dist-win і DXVK у OptimaX-Mesa-<версія>.zip
та OptimaX-DXVK-<версія>.zip (x64\\ і x86\\ + манифест із сумами) і викладає їх у реліз OptimaX поруч із
SHA256SUMS.txt. Програма завантажує архів лише після перевірки суми й розпаковує в ProgramData\\OptimaX\\<шар>,
доступ до якої лишає тільки адміністраторам і SYSTEM (у ProgramData за замовчуванням будь-хто може створювати файли).
Перед кожним копіюванням у папку гри й перед завантаженням у GPU-тест бібліотеки звіряються із сумами з манифесту.
"""
from __future__ import annotations

import functools
import glob
import hashlib
import json
import ntpath
import os
import re
import shutil
import threading
import time
import zipfile

import engine as E
from i18n import tr

PREF_HIGH = "GpuPreference=2;"
AUTO_EVERY = 15 * 60  # фонова перевірка нових ігор не частіше
MAX_EXES = 40         # exe на одну гру — більше означає, що це не гра, а збірка інструментів
MAX_DEPTH = 4         # game\bin\win64\cs2.exe, Game\Binaries\Win64\Game-Win64-Shipping.exe

ADAPTER_VAR = "MESA_D3D12_DEFAULT_ADAPTER_NAME"
ADAPTER_NAME = "NVIDIA"  # майнінгові карти, які ми розпізнаємо (P106/P104/P102, CMP HX), — усі NVIDIA
ENV_KEY = r"HKCU\Environment"
ENV_ID = "mining:mesa_env"
MESA_ARCHES = ("x64", "x86")  # розрядності шарів (Mesa, DXVK) — як у exe гри
MACHINES = {0x8664: "x64", 0x14C: "x86"}  # ARM64 та інші — без Mesa
VERSION_RE = re.compile(r"^\d+(?:\.\d+){0,3}$")
DEMO_MESA = "26.2.0"

_LOCK = threading.Lock()  # одна зміна за раз: кнопки, фонова перевірка й Mesa пишуть той самий журнал відкату


def _exclusive(fn):
    @functools.wraps(fn)
    def run(*a, **kw):
        if not _LOCK.acquire(blocking=False):
            log = next((x for x in a if callable(x)), kw.get("log")) or (lambda *_: None)
            log(tr("mg.busy"))
            return {"busy": True}
        try:
            return fn(*a, **kw)
        finally:
            _LOCK.release()
    return run


def _dir(p: str) -> str:
    """Папка файлу — і для шляхів Windows у демо-режимі на Linux (там os.path не знає про «\\»)."""
    return ntpath.dirname(p) if "\\" in p else os.path.dirname(p)


def _base(p: str) -> str:
    return ntpath.basename(p) if "\\" in p else os.path.basename(p)


def _join(folder: str, name: str) -> str:
    return ntpath.join(folder, name) if "\\" in folder else os.path.join(folder, name)


def active(hw: dict) -> bool:
    return bool((hw or {}).get("mining_gpu"))


def model(hw: dict) -> str:
    return (hw or {}).get("mining_gpu") or "GPU"


# ───────────────────────── exe: розрядність і що він імпортує ─────────────────────────
def _u16(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 2], "little")


def _u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


def pe_info(path: str) -> tuple:
    """-> (машина: "x64" | "x86" | "" — інша чи не PE, імена DLL із таблиць імпорту — звичайної й відкладеної, у
    нижньому регістрі). Читаємо лише заголовки й самі таблиці, а не весь файл: exe ігор бувають по сотні мегабайтів."""
    try:
        with open(path, "rb") as f:
            head = f.read(1 << 16)
            if head[:2] != b"MZ" or len(head) < 0x40:
                return "", set()
            pe = _u32(head, 0x3C)
            if pe + 264 > len(head) or head[pe:pe + 4] != b"PE\0\0":
                return "", set()
            coff = pe + 4
            machine = MACHINES.get(_u16(head, coff), "")
            nsec, opt_size = _u16(head, coff + 2), _u16(head, coff + 16)
            opt = coff + 20
            magic = _u16(head, opt)
            if magic == 0x20B:
                dd = opt + 112
            elif magic == 0x10B:
                dd = opt + 96
            else:
                return machine, set()
            ndd = _u32(head, dd - 4)
            secs = []
            for i in range(min(nsec, 96)):
                s = opt + opt_size + 40 * i
                if s + 40 > len(head):
                    break
                secs.append((_u32(head, s + 12), max(_u32(head, s + 8), _u32(head, s + 16)), _u32(head, s + 20)))

            def off(rva):
                for va, size, raw in secs:
                    if va <= rva < va + size:
                        return rva - va + raw
                return None

            def at(o, n):
                f.seek(o)
                return f.read(n)

            def name(rva):
                o = off(rva)
                if o is None:
                    return ""
                return at(o, 256).split(b"\0", 1)[0].decode("ascii", "replace").strip().lower()

            def ddir(i):
                return (_u32(head, dd + 8 * i), _u32(head, dd + 8 * i + 4)) if i < ndd else (0, 0)

            out = set()
            rva, size = ddir(1)  # IMAGE_IMPORT_DESCRIPTOR: 20 байтів, Name — зміщення 12
            o = off(rva) if rva else None
            if o is not None:
                blob = at(o, min(max(size, 20), 20 * 1024))
                for i in range(0, len(blob) - 19, 20):
                    if not any(blob[i:i + 20]):
                        break
                    if _u32(blob, i + 12):
                        out.add(name(_u32(blob, i + 12)))
            rva, size = ddir(13)  # відкладений імпорт: 32 байти, DllNameRVA — зміщення 4 (якщо Attributes & 1)
            o = off(rva) if rva else None
            if o is not None:
                blob = at(o, min(max(size, 32), 32 * 512))
                for i in range(0, len(blob) - 31, 32):
                    if not any(blob[i:i + 32]):
                        break
                    if _u32(blob, i) & 1 and _u32(blob, i + 4):
                        out.add(name(_u32(blob, i + 4)))
            out.discard("")
            return machine, out
    except (OSError, ValueError, IndexError):
        return "", set()


def pe_imports(path: str) -> set:
    return pe_info(path)[1]


DX10_PLUS = {"d3d10.dll", "d3d10_1.dll", "d3d11.dll", "d3d12.dll", "dxgi.dll"}
API_DLLS = (("dx9", {"d3d9.dll", "d3d8.dll"}), ("dx10", {"d3d10.dll", "d3d10_1.dll"}), ("dx11", {"d3d11.dll"}),
            ("dx12", {"d3d12.dll"}), ("vulkan", {"vulkan-1.dll"}), ("gl", {"opengl32.dll"}))
DX9_DLL = re.compile(r"(d3d9|dx9)", re.I)  # shaderapidx9.dll, rendersystem_dx9.dll… — рушій вантажить d3d9 сам
ENGINE_DIRS = ("", "bin", os.path.join("bin", "x64"), os.path.join("bin", "win64"))  # Source: hl2.exe + bin\*.dll


def engine_dlls(folder: str) -> tuple:
    """Бібліотеки рушія поруч з exe і в його bin\\ (так лежать ігри на Source: hl2.exe, csgo.exe, left4dead2.exe)."""
    out = []
    for sub in ENGINE_DIRS:
        try:
            out += [f for f in os.listdir(os.path.join(folder, sub)) if f.lower().endswith(".dll")]
        except OSError:
            pass
    return tuple(out)


ENGINE_LIBS = ("UnityPlayer.dll",)  # exe Unity — лише заглушка, графічні API імпортує ця бібліотека


def engine_imports(folder: str) -> set:
    out = set()
    for n in ENGINE_LIBS:
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            out |= pe_imports(p)
    return out


def classify(path: str, sibling_dlls: tuple = (), engine: set = None) -> dict:
    """-> {path, api, arch}. api: dx9 (DirectX 9 / 8), dx10, dx11, dx12, gl (OpenGL), vulkan, other — не вдалося
    визначити (рушій вантажить API сам). arch: x64 / x86 / "" — для якої розрядності підходять шари."""
    arch, imps = pe_info(path)
    allimps = imps | (engine or set())
    if imps & {"d3d9.dll", "d3d8.dll"} and not imps & DX10_PLUS:
        api = "dx9"  # DirectX 9 і 8: обидва бачать лише карту з монітором, обидва перекладає DXVK
    elif "opengl32.dll" in imps:
        api = "gl"
    elif not imps & DX10_PLUS and any(DX9_DLL.search(d) for d in sibling_dlls):
        api = "dx9"
    elif "d3d11.dll" in allimps:
        api = "dx11"
    elif "d3d12.dll" in allimps:
        api = "dx12"
    elif allimps & {"d3d10.dll", "d3d10_1.dll"}:
        api = "dx10"
    elif "vulkan-1.dll" in allimps:
        api = "vulkan"
    elif "opengl32.dll" in allimps:
        api = "gl"
    else:
        api = "other"
    found = [a for a, dlls in API_DLLS if allimps & dlls]
    return dict(path=path, api=api, arch=arch, apis=found or [api])


def api_of(path: str, sibling_dlls: tuple = ()) -> str:
    return classify(path, sibling_dlls)["api"]


# ───────────────────────── Steam: формат VDF ─────────────────────────
_VDF_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')


def vdf_parse(text: str) -> dict:
    """Текстовий VDF Steam (libraryfolders.vdf, appmanifest_*.acf) -> вкладені словники; ключі — у нижньому регістрі."""
    root: dict = {}
    stack, key = [root], None
    for m in _VDF_TOKEN.finditer(text or ""):
        if m.group(2) == "{":
            d: dict = {}
            stack[-1][(key or "").lower()] = d
            stack.append(d)
            key = None
        elif m.group(2) == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        else:
            s = re.sub(r"\\(.)", r"\1", m.group(1))
            if key is None:
                key = s
            else:
                stack[-1][key.lower()] = s
                key = None
    return root


def _read(path: str, limit: int = 4 << 20) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


STEAM_SKIP_IDS = {"228980", "1070560", "1391110", "1628350", "1826330", "2180100", "1493710", "1420170", "1580130",
                  "1887720", "2348590", "2805730", "3658110"}  # Steamworks Redistributables, Steam Linux Runtime, Proton
STEAM_SKIP_NAME = re.compile(r"redistributable|steam linux runtime|^proton\b|steamworks", re.I)


def steam_root() -> str:
    for path, name in ((r"HKCU\Software\Valve\Steam", "SteamPath"),
                       (r"HKLM\SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                       (r"HKLM\SOFTWARE\Valve\Steam", "InstallPath")):
        v = E.reg_get(path, name)
        if v and str(v[1]).strip():
            return os.path.normpath(str(v[1]).strip())
    return ""


def steam_games(root: str = None) -> list:
    root = steam_root() if root is None else root
    if not root:
        return []
    libs = [root]
    lf = vdf_parse(_read(os.path.join(root, "steamapps", "libraryfolders.vdf")))
    lf = lf.get("libraryfolders") or {}
    for k, v in lf.items():
        if k.isdigit():
            p = v.get("path") if isinstance(v, dict) else v
            if p:
                libs.append(os.path.normpath(p))
    out, seen = [], set()
    for lib in libs:
        if lib.lower() in seen:
            continue
        seen.add(lib.lower())
        pattern = os.path.join(glob.escape(os.path.join(lib, "steamapps")), "appmanifest_*.acf")  # «D:\Games [SSD]»
        for acf in sorted(glob.glob(pattern)):
            st = vdf_parse(_read(acf, 1 << 20)).get("appstate") or {}
            appid, name, inst = str(st.get("appid") or ""), st.get("name") or "", st.get("installdir") or ""
            if not inst or appid in STEAM_SKIP_IDS or STEAM_SKIP_NAME.search(name):
                continue
            d = os.path.join(lib, "steamapps", "common", inst)
            if os.path.isdir(d):
                out.append(dict(name=name or inst, store="steam", dir=d, appid=appid))
    return out


def epic_games(folder: str = None) -> list:
    folder = folder or os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Epic", "EpicGamesLauncher",
                                    "Data", "Manifests")
    out = []
    for item in sorted(glob.glob(os.path.join(glob.escape(folder), "*.item"))):
        try:
            m = json.loads(_read(item, 1 << 20))
        except ValueError:
            continue
        cats = [str(c).lower() for c in m.get("AppCategories") or []]
        if m.get("bIsIncompleteInstall") or (cats and "games" not in cats):
            continue  # недовстановлене, рушії (Unreal Engine) і плагіни
        d = m.get("InstallLocation") or ""
        if d and os.path.isdir(d):
            exe = m.get("LaunchExecutable") or ""
            out.append(dict(name=m.get("DisplayName") or os.path.basename(d), store="epic", dir=os.path.normpath(d),
                            main=os.path.normpath(os.path.join(d, exe)) if exe else "", epic=m.get("AppName") or ""))
    return out


def gog_games() -> list:
    out = []
    base = r"HKLM\SOFTWARE\WOW6432Node\GOG.com\Games"
    for sub in E.reg_subkeys(base):
        key = f"{base}\\{sub}"
        d = E.reg_get(key, "path")
        if d and os.path.isdir(str(d[1])):
            n = E.reg_get(key, "gameName")
            exe = E.reg_get(key, "exe")
            out.append(dict(name=str(n[1]) if n else os.path.basename(str(d[1])), store="gog",
                            dir=os.path.normpath(str(d[1])), main=str(exe[1]) if exe else ""))
    return out


def ubisoft_games() -> list:
    out = []
    base = r"HKLM\SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"
    for sub in E.reg_subkeys(base):
        d = E.reg_get(f"{base}\\{sub}", "InstallDir")
        if d and os.path.isdir(str(d[1])):
            p = os.path.normpath(str(d[1]))
            out.append(dict(name=os.path.basename(p), store="ubisoft", dir=p, ubi=sub if sub.isdigit() else ""))
    return out


def my_games() -> list:
    """«Мої ігри» OptimaX: тут відомий сам exe, папку не скануємо."""
    import features as F
    out = []
    for g in F.CFG["games"] or []:
        p = g.get("path") or ""
        if p.lower().endswith(".exe") and os.path.isfile(p):
            out.append(dict(name=F.game_name(p), store="mine", dir=os.path.dirname(p), exes=[p]))
    return out


SKIP_DIRS = {"_commonredist", "commonredist", "redist", "_redist", "redistributables", "redistributable", "__installer",
             "installer", "installers", "directx", "dxsetup", "vcredist", "dotnet", "support", "prereq", "prereqs",
             "prerequisites", "easyanticheat", "battleye", "crashreporter", "crashpad", "uninstall", "__overlay",
             "eac", "anticheat"}
SKIP_EXE = re.compile(
    r"^(unins\d*|uninstall.*|setup.*|install(er)?\b.*|vc_?redist.*|dxsetup|dxwebsetup|dotnet.*|ndp\d.*|"
    r"ue\d?prereqsetup.*|.*crash.*|easyanticheat.*|eac_?launcher|beservice.*|battleye.*|cefsharp\..*|"
    r"qtwebengineprocess|.*webhelper.*|.*updater.*|.*redist.*|oalinst|physx.*|dxdiag|touchup|cleanup|"
    r"notification_helper|vcpkgsrv|7za?)\.exe$", re.I)


def scan_exes(folder: str) -> list:
    """exe гри в папці (до MAX_DEPTH рівнів), без інсталяторів, перерозподілюваних пакетів і звітів про збої.
    -> [{path, api, arch}] — спершу ближчі до кореня."""
    found = []
    root_depth = folder.rstrip("\\/").count(os.sep)
    for dp, dns, fns in os.walk(folder):
        depth = dp.rstrip("\\/").count(os.sep) - root_depth
        dns[:] = sorted(d for d in dns if d.lower() not in SKIP_DIRS and depth < MAX_DEPTH)
        for fn in sorted(fns):
            if fn.lower().endswith(".exe") and not SKIP_EXE.match(fn):
                found.append((depth, os.path.join(dp, fn)))
        if len(found) > MAX_EXES * 4:
            break
    found.sort(key=lambda x: (x[0], x[1].lower()))
    dlls: dict = {}
    eng: dict = {}
    out = []
    for _, p in found[:MAX_EXES]:
        d = os.path.dirname(p)
        if d not in dlls:
            dlls[d], eng[d] = engine_dlls(d), engine_imports(d)
        out.append(classify(p, dlls[d], eng[d]))
    return out


def _risky_folder(folder: str) -> str:
    """Adobe AIR — на майнінгових картах ті самі сині екрани, що й старі ігри DirectX 9."""
    if os.path.isdir(os.path.join(folder, "Adobe AIR")) or os.path.isfile(os.path.join(folder, "Adobe AIR.dll")):
        return "air"
    return ""


def discover() -> list:
    """Встановлені ігри з exe й тим, що вони використовують. -> [{name, store, dir, exes: [{path, api, arch}], risk}]"""
    if not E.IS_WIN:
        return demo_games()
    games, seen = [], set()
    for src in (my_games, steam_games, epic_games, gog_games, ubisoft_games):
        try:
            items = src()
        except Exception:
            items = []
        for g in items:
            key = g["dir"].lower()
            if key in seen:
                continue
            seen.add(key)
            if "exes" in g:
                g["exes"] = [classify(p, engine_dlls(os.path.dirname(p)), engine_imports(os.path.dirname(p)))
                             for p in g["exes"]]
            else:
                g["exes"] = scan_exes(g["dir"])
                main = g.get("main") or ""
                if main and os.path.isfile(main) and not any(x["path"].lower() == main.lower() for x in g["exes"]):
                    g["exes"].insert(0, classify(main, engine_dlls(os.path.dirname(main)),
                                                 engine_imports(os.path.dirname(main))))
            g["risk"] = _risky_folder(g["dir"])
            g["anticheat"] = anticheat(g["dir"])
            if g["exes"]:
                games.append(g)
    return sorted(games, key=lambda g: g["name"].lower())


def demo_games() -> list:
    root = r"C:\Program Files (x86)\Steam\steamapps\common"
    return [
        dict(name="Counter-Strike 2", store="steam", dir=root + r"\Counter-Strike Global Offensive", risk="", appid="730",
             exes=[dict(path=root + r"\Counter-Strike Global Offensive\game\bin\win64\cs2.exe", api="dx11",
                        arch="x64")]),
        dict(name="Fortnite", store="epic", dir=r"C:\Program Files\Epic Games\Fortnite", risk="", anticheat="EasyAntiCheat",
             exes=[dict(path=r"C:\Program Files\Epic Games\Fortnite\FortniteGame\Binaries\Win64\FortniteClient-Win64-"
                             r"Shipping.exe", api="dx11", arch="x64", apis=["dx11", "dx12"]),
                   dict(path=r"C:\Program Files\Epic Games\Fortnite\FortniteGame\Binaries\Win64\FortniteLauncher.exe",
                        api="other", arch="x64")]),
        dict(name="Half-Life", store="steam", dir=root + r"\Half-Life", risk="",
             exes=[dict(path=root + r"\Half-Life\hl.exe", api="gl", arch="x86")]),
        dict(name="Grand Theft Auto: San Andreas", store="steam", dir=root + r"\Grand Theft Auto San Andreas",
             risk="", exes=[dict(path=root + r"\Grand Theft Auto San Andreas\gta_sa.exe", api="dx9", arch="x86")]),
    ]


# ───────────────────────── призначення ігор на майнінгову карту ─────────────────────────
def gpu_id(exe: str) -> str:
    return "gpu:" + exe.lower()


def exe_state(exe: str) -> str:
    """ours — призначила OptimaX тут; user — вибір уже зроблено (у «Графіці» Windows чи «Мої ігри»): не чіпаємо;
    free — ще ніхто не вибирав."""
    if E.JOURNAL.has(gpu_id(exe)):
        return "ours"
    return "user" if E.reg_get(E.DX_PREF, exe) is not None else "free"


def gpu_tweak(game: str, exe: str, gpu: str) -> E.Tweak:
    t = E.Tweak(gpu_id(exe), "game", [E.R(E.DX_PREF, exe, PREF_HIGH, "sz")])
    t._title = tr("mg.t_gpu", game=game, exe=_base(exe), gpu=gpu)
    return t


# ───────────────────────── шари-перекладачі: Mesa (OpenGL) і DXVK (DirectX 9) ─────────────────────────
# OpenGL і DirectX 9 бачать лише відеокарту, до якої підключено монітор, тож «Висока продуктивність» на них не діє.
# Шар поруч з exe перекладає їх на API, що вміє вибрати іншу карту: Mesa — OpenGL → DirectX 12 (адаптер — за
# MESA_D3D12_DEFAULT_ADAPTER_NAME і налаштуванням «Графіка»), DXVK — DirectX 9 / 8 → Vulkan (вбудована графіка старих
# поколінь Vulkan на Windows не має, тож Vulkan бачить лише майнінгову карту).
LAYERS = {
    "mesa": dict(files=("opengl32.dll", "libgallium_wgl.dll", "libglapi.dll", "dxil.dll"),
                 required=("opengl32.dll", "libgallium_wgl.dll"), api="gl", prefix="glmesa:",
                 asset=re.compile(r"^OptimaX-Mesa-(\d+(?:\.\d+)*)\.zip$", re.I)),
    "dxvk": dict(files=("d3d9.dll", "d3d8.dll", "dxgi.dll", "d3d11.dll", "d3d10core.dll"), required=("d3d9.dll",),
                 api="dx9", prefix="dxvk:",
                 asset=re.compile(r"^OptimaX-DXVK-(\d+(?:\.\d+)*)\.zip$", re.I)),
}
MESA_FILES, MESA_REQUIRED = LAYERS["mesa"]["files"], LAYERS["mesa"]["required"]
DXVK_FILES, DXVK_REQUIRED = LAYERS["dxvk"]["files"], LAYERS["dxvk"]["required"]
MESA_ASSET_RE = LAYERS["mesa"]["asset"]
DEMO_VERSION = {"mesa": DEMO_MESA, "dxvk": "2.6.2"}
# які бібліотеки DXVK потрібні грі на якому API: DirectX 9 / 8 — d3d9 (+ d3d8); DirectX 10 / 11 — dxgi + d3d11 + d3d10core
DXVK_SETS = {"dx9": ("d3d9.dll", "d3d8.dll"), "dx10": ("dxgi.dll", "d3d11.dll", "d3d10core.dll"),
             "dx11": ("dxgi.dll", "d3d11.dll", "d3d10core.dll")}
DXVK_NEEDS = {"dx9": ("d3d9.dll",), "dx10": ("dxgi.dll", "d3d11.dll"), "dx11": ("dxgi.dll", "d3d11.dll")}
DX_APIS = ("dx9", "dx10", "dx11")


def layer_id(kind: str, folder: str) -> str:
    return LAYERS[kind]["prefix"] + folder.lower().rstrip("\\/")


def mesa_id(folder: str) -> str:
    return layer_id("mesa", folder)


def layer_targets(g: dict, kind: str, apis: tuple = None) -> list:
    """Куди класти шар: [(папка exe, розрядність)] для exe з його API (gl — Mesa, dx9 — DXVK; apis — інший набір,
    наприклад DXVK і для DirectX 10 / 11), x64 / x86. Бібліотеки — поруч з exe і тієї ж розрядності: 64-бітна
    opengl32.dll чи d3d9.dll поруч із 32-бітною грою не дасть їй запуститися. Для гри на Source exe лежить у корені, а
    d3d9 вантажить bin\\shaderapidx9.dll — Windows однаково шукає d3d9.dll спершу поруч з exe."""
    out = []
    if g.get("risk"):
        return out
    apis = apis or (LAYERS[kind]["api"],)
    for x in g["exes"]:
        if x["api"] in apis and x.get("arch") in MESA_ARCHES:
            d = _dir(x["path"])
            if d.lower() not in (o[0].lower() for o in out):
                out.append((d, x["arch"]))
    return out


def gl_targets(g: dict) -> list:
    return layer_targets(g, "mesa")


def gl_folders(g: dict) -> list:
    return [d for d, _ in layer_targets(g, "mesa")]


def layer_on(g: dict, kind: str) -> bool:
    folders = [d for d, _ in layer_targets(g, kind)]
    if folders:
        return all(E.JOURNAL.has(layer_id(kind, f)) for f in folders)
    return kind == "dxvk" and any(E.JOURNAL.has(layer_id(kind, d)) for d, _ in layer_targets(g, kind, DX_APIS))


def layer_folders_on(g: dict, kind: str) -> list:
    """Папки гри, куди OptimaX уже поклала шар."""
    return [d for d, _ in layer_targets(g, kind, DX_APIS if kind == "dxvk" else None) if E.JOURNAL.has(layer_id(kind, d))]


def game_status(g: dict) -> dict:
    """Підсумок для рядка гри: on — скільки exe малює майнінгова карта; kept — вибір користувача; dx9 — DirectX 9 /
    Adobe AIR (Windows їх не перемикає); gl — OpenGL-exe; gl_na / dx9_na — exe, для яких шару немає (ARM64…);
    mesa / dxvk — шар уже в усіх папках гри."""
    st = dict(on=0, kept=0, free=0, dx9=0, gl=0, gl_na=0, dx9_na=0, total=len(g["exes"]))
    for x in g["exes"]:
        if g.get("risk") or x["api"] == "dx9":
            st["dx9"] += 1
            if not g.get("risk") and x.get("arch") not in MESA_ARCHES:
                st["dx9_na"] += 1
            continue
        if x["api"] == "gl":
            st["gl"] += 1
            if x.get("arch") not in MESA_ARCHES:
                st["gl_na"] += 1
        s = exe_state(x["path"])
        st["on" if s == "ours" else "kept" if s == "user" else "free"] += 1
    st["mesa"] = layer_on(g, "mesa")
    st["dxvk"] = layer_on(g, "dxvk")
    st["dxvk_dx11"] = any(E.JOURNAL.has(layer_id("dxvk", d)) for d, _ in layer_targets(g, "dxvk", ("dx10", "dx11")))
    st["mode"] = current_mode(g)
    return st


@_exclusive
def assign(log, hw: dict, games: list = None) -> dict:
    """Призначає всі ще не призначені exe ігор на майнінгову карту. DirectX 9 і Adobe AIR пропускаємо: Windows їх на
    карту без виходів не перенесе (DirectX 9 бачить лише карту з монітором) — для DirectX 9 є DXVK."""
    gpu = model(hw)
    games = discover() if games is None else games
    todo, res = [], dict(games=len(games), assigned=0, already=0, kept=0, dx9=0, gl=0, failed=0)
    for g in games:
        if current_mode(g) == "original":
            res["original"] = res.get("original", 0) + 1
            continue  # «Оригінал»: користувач просив нічого в цій грі не змінювати
        if any(x["api"] == "gl" for x in g["exes"]):
            res["gl"] += 1
        for x in g["exes"]:
            if g.get("risk") or x["api"] == "dx9":
                res["dx9"] += 1
                continue
            s = exe_state(x["path"])
            if s == "ours":
                res["already"] += 1
            elif s == "user":
                res["kept"] += 1
            else:
                todo.append(gpu_tweak(g["name"], x["path"], gpu))
    if todo:
        r = E.apply_tweaks(todo, log, header=False, by="mining")
        res["assigned"], res["failed"] = r.get("ok", 0), r.get("fail", 0)
        if r.get("error"):
            res["error"] = r["error"]
    log(tr("mg.summary", games=res["games"], n=res["assigned"], already=res["already"], kept=res["kept"],
           dx9=res["dx9"], gpu=gpu))
    return res


def our_ids() -> list:
    prefixes = ("gpu:", "mining:") + tuple(v["prefix"] for v in LAYERS.values())
    return [tid for tid in E.JOURNAL.newest_first() if tid.startswith(prefixes)]


@_exclusive
def revert(log) -> dict:
    ids = our_ids()
    if not ids:
        log(tr("mg.nothing"))
        return {"undone": 0}
    return E.undo_ids(ids, log, by="mining")


def auto_due(cfg, now: float = None) -> bool:
    m = cfg["mining"] or {}
    return bool(m.get("auto")) and (now or time.time()) - float(m.get("last_scan") or 0) >= AUTO_EVERY


def mark_scan(cfg) -> None:
    m = dict(cfg["mining"] or {})
    m["last_scan"] = int(time.time())
    cfg["mining"] = m


def busy() -> bool:
    return _LOCK.locked()


# ───────────────────────── файли шарів: завантаження, перевірка, розпакування ─────────────────────────
def layer_root(kind: str) -> str:
    """OptimaX з правами адміністратора копіює ці бібліотеки в папки ігор (а Mesa ще й вантажить у GPU-тест) — тож
    вони лежать у ProgramData, і доступ до папки лишаємо тільки адміністраторам і SYSTEM (за замовчуванням у
    підпапках ProgramData будь-який користувач може створювати файли й папки — підкинути свої бібліотеки)."""
    if E.IS_WIN and not E.DRY_RUN and E.is_admin():
        return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "OptimaX", kind)
    return os.path.join(E.DATA_DIR, kind)


def mesa_root() -> str:
    return layer_root("mesa")


def _secure(path: str, log=lambda *_: None) -> None:
    os.makedirs(path, exist_ok=True)
    if E.IS_WIN and not E.DRY_RUN and E.is_admin():
        E.run(["icacls", path, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F",
               "*S-1-5-32-545:(OI)(CI)RX"], 20, log)


def _vt(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


_HASHES: dict = {}  # шлях -> (розмір, mtime, sha256): перевірка викликається часто, а бібліотеки — десятки мегабайтів


def _sha(path: str) -> str:
    st = os.stat(path)
    key = (st.st_size, st.st_mtime_ns)
    got = _HASHES.get(path)
    if got and got[:2] == key:
        return got[2]
    h = E.file_sha256(path)
    _HASHES[path] = (*key, h)
    return h


def verified_files(folder: str, arch: str, kind: str = "mesa") -> dict:
    """Бібліотеки шару розрядності arch з папки версії, звірені із сумами з її манифесту (mesa.json / dxvk.json):
    {ім'я: шлях}. Будь-яка невідповідність (файл підмінено, зіпсовано) — {}: такому шару не довіряємо зовсім."""
    lay = LAYERS[kind]
    try:
        with open(os.path.join(folder, f"{kind}.json"), encoding="utf-8") as f:
            man = json.load(f)
        files = man.get("files") or {}
        out = {}
        for n in lay["files"]:
            sha = files.get(f"{arch}/{n}")
            if not sha:
                continue
            p = os.path.join(folder, arch, n)
            if _sha(p) != str(sha).lower():
                return {}
            out[n] = p
        return out if all(n in out for n in lay["required"]) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def layer_info(kind: str) -> dict:
    """Розпакований і перевірений шар: {version, dir, arch: {"x64": {ім'я: шлях}, "x86": {…}}} або None."""
    best = None
    for man in glob.glob(os.path.join(glob.escape(layer_root(kind)), "*", f"{kind}.json")):
        folder = os.path.dirname(man)
        ver = os.path.basename(folder)
        if not VERSION_RE.match(ver):
            continue  # недорозпакована (*.part) чи чужа папка
        try:
            with open(man, encoding="utf-8") as f:
                listed = {k.split("/")[0] for k in (json.load(f).get("files") or {})}
        except (OSError, ValueError, AttributeError):
            continue
        arches = {a: v for a in MESA_ARCHES if a in listed and (v := verified_files(folder, a, kind))}
        if len(arches) != len(listed & set(MESA_ARCHES)):
            continue  # хоч один файл не збігся із сумою — цій версії не довіряємо зовсім
        if arches and (best is None or _vt(ver) > _vt(best["version"])):
            best = dict(version=ver, dir=folder, arch=arches)
    return best


def mesa_info() -> dict:
    return layer_info("mesa")


def install_zip(path: str, log, kind: str = "mesa") -> dict:
    """Розпаковує перевірений архів OptimaX-Mesa-*.zip / OptimaX-DXVK-*.zip: лише відомі бібліотеки (x64/…, x86/…),
    кожна — за сумою з манифесту всередині архіву."""
    lay = LAYERS[kind]
    allowed = {f"{a}/{n}" for a in MESA_ARCHES for n in lay["files"]}
    with zipfile.ZipFile(path) as z:
        man = json.loads(z.read(f"{kind}.json").decode("utf-8"))
        version = str(man.get(kind) or "")
        if not VERSION_RE.match(version):
            raise RuntimeError(tr("mg.layer_bad", name=f"{kind}.json"))
        root = layer_root(kind)
        _secure(root, log)
        dest = os.path.join(root, version)
        tmp = dest + ".part"
        shutil.rmtree(tmp, ignore_errors=True)
        files = {}
        for name, sha in (man.get("files") or {}).items():
            key = name.replace("\\", "/").lower()
            if key not in allowed:  # лише відомі імена: ні шляхів за межі папки, ні сторонніх файлів
                continue
            data = z.read(name)
            if hashlib.sha256(data).hexdigest() != str(sha).lower():
                shutil.rmtree(tmp, ignore_errors=True)
                raise RuntimeError(tr("mg.layer_bad", name=name))
            arch, n = key.split("/")
            os.makedirs(os.path.join(tmp, arch), exist_ok=True)
            with open(os.path.join(tmp, arch, n), "wb") as f:
                f.write(data)
            files[key] = str(sha).lower()
    with open(os.path.join(tmp, f"{kind}.json"), "w", encoding="utf-8") as f:
        json.dump(dict(man, files=files), f, indent=1)
    if not any(verified_files(tmp, a, kind) for a in MESA_ARCHES):
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(tr("mg.layer_bad", name=", ".join(lay["required"])))
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    log(tr("mg.layer_ready", what=LAYER_NAMES[kind], v=version))
    return layer_info(kind)


LAYER_NAMES = {"mesa": "Mesa", "dxvk": "DXVK"}


def find_asset(log, kind: str = "mesa") -> dict:
    """Архів шару в одному з останніх релізів OptimaX."""
    import updater as U
    import verify as V
    if not U.UPDATE_REPO:
        raise RuntimeError(tr("mg.layer_not_found", what=LAYER_NAMES[kind]))
    rels = json.loads(U.fetch_text(f"https://api.github.com/repos/{U.UPDATE_REPO}/releases?per_page=10", 1 << 22))
    rx = LAYERS[kind]["asset"]
    for rel in rels if isinstance(rels, list) else []:
        if rel.get("draft"):
            continue
        assets = rel.get("assets") or []
        a = next((a for a in assets if rx.match(a.get("name") or "")), None)
        if a:
            sums = next((x for x in assets if x.get("name") == U.SUMS_NAME), None)
            return dict(name=a["name"], url=a["browser_download_url"], size=a.get("size") or 0,
                        sha256=V.digest_of(a), sums_url=sums["browser_download_url"] if sums else "",
                        version=rx.match(a["name"]).group(1))
    raise RuntimeError(tr("mg.layer_not_found", what=LAYER_NAMES[kind]))


def install_layer(kind: str, log, progress=None) -> dict:
    if not E.IS_WIN or E.DRY_RUN:
        return _demo_layer(kind, log)
    import updater as U
    info = find_asset(log, kind)
    log(tr("mg.mesa_dl", name=info["name"], mb=f"{info['size'] / 2**20:.0f}"))
    path = U.download(info, log, progress, publisher="")  # zip без підпису: перевіряємо суму з релізу
    try:
        return install_zip(path, log, kind)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def install_mesa(log, progress=None) -> dict:
    return install_layer("mesa", log, progress)


def _demo_layer(kind: str, log) -> dict:
    ver = DEMO_VERSION[kind]
    dest = os.path.join(layer_root(kind), ver)
    files = {}
    for arch in MESA_ARCHES:
        os.makedirs(os.path.join(dest, arch), exist_ok=True)
        for n in LAYERS[kind]["files"]:
            data = f"demo {arch} {n}".encode()
            with open(os.path.join(dest, arch, n), "wb") as f:
                f.write(data)
            files[f"{arch}/{n}"] = hashlib.sha256(data).hexdigest()
    with open(os.path.join(dest, f"{kind}.json"), "w", encoding="utf-8") as f:
        json.dump({kind: ver, "files": files}, f)
    log("  [dry-run] " + tr("mg.layer_ready", what=LAYER_NAMES[kind], v=ver))
    return layer_info(kind)


# ───────────────────────── шари в папках ігор ─────────────────────────
def gl_driver() -> str:
    """Чим Mesa малює OpenGL: d3d12 (за замовчуванням, OpenGL → DirectX 12) або zink (OpenGL → Vulkan, експериментально)."""
    import features as F
    d = str((F.CFG["mining"] or {}).get("gl_driver") or "d3d12")
    return d if d in ("d3d12", "zink") else "d3d12"


def env_tweak() -> E.Tweak:
    ops = [E.R(ENV_KEY, ADAPTER_VAR, ADAPTER_NAME, "sz")]
    if gl_driver() == "zink":
        ops.append(E.R(ENV_KEY, "GALLIUM_DRIVER", "zink", "sz"))
    t = E.Tweak(ENV_ID, "game", ops + [E.X("env")])
    t._title = tr("mg.t_env_zink" if gl_driver() == "zink" else "mg.t_env")
    return t


def _files_for(kind: str, files: dict, apis: tuple) -> dict:
    """Лише ті бібліотеки шару, які потрібні цим API: DirectX 9 — d3d9 / d3d8, DirectX 10 / 11 — dxgi, d3d11, d3d10core
    (зайва dxgi.dll поруч із грою на DirectX 9 нічого не дає, а запуск лаунчера чи оверлея може зламати)."""
    if kind != "dxvk":
        return files
    names = {n for a in apis for n in DXVK_SETS.get(a, ())}
    return {n: p for n, p in files.items() if n in names}


def layer_tweak(kind: str, game: str, folder: str, files: dict) -> E.Tweak:
    """files: {ім'я: шлях} — щойно звірені із сумами (verified_files)."""
    ops = [E.FILE(files[n], _join(folder, n)) for n in LAYERS[kind]["files"] if n in files]
    t = E.Tweak(layer_id(kind, folder), "game", ops)
    t._title = tr("mg.t_layer", what=LAYER_NAMES[kind], game=game, folder=_base(folder) or folder)
    return t


def mesa_tweak(game: str, folder: str, files: dict) -> E.Tweak:
    return layer_tweak("mesa", game, folder, files)


@_exclusive
def enable_layer(kind: str, g: dict, log, hw: dict) -> dict:
    """Гру — на майнінгову карту через шар: бібліотеки потрібної розрядності в папку гри (для Mesa — ще й змінна з
    назвою карти), і самі exe — на «Високу продуктивність» (за цим Windows ставить карту першою для DirectX 12 і
    Vulkan, на яких працюють Mesa й DXVK)."""
    info = layer_info(kind)  # саме тут суми звіряються ще раз — безпосередньо перед копіюванням
    if not info:
        return {"ok": 0, "error": "no_layer"}
    items = [] if kind != "mesa" or E.JOURNAL.has(ENV_ID) else [env_tweak()]
    items += [layer_tweak(kind, g["name"], d, _files_for(kind, info["arch"][a], ("dx9",)))
              for d, a in layer_targets(g, kind) if a in info["arch"] and not E.JOURNAL.has(layer_id(kind, d))]
    items += [gpu_tweak(g["name"], x["path"], model(hw)) for x in g["exes"]
              if x["api"] == LAYERS[kind]["api"] and x.get("arch") in info["arch"] and exe_state(x["path"]) == "free"]
    if not items:
        return {"ok": 0}
    res = E.apply_tweaks(items, log, header=False, by="mining")
    log(tr("mg.layer_on", what=LAYER_NAMES[kind], game=g["name"]))
    return res


@_exclusive
def disable_layer(kind: str, g: dict, log) -> dict:
    ids = [layer_id(kind, d) for d in layer_folders_on(g, kind)]
    # і призначення exe цієї гри, які зробив шар: без нього DirectX 9 / OpenGL на «Високу продуктивність» не зважає
    api = LAYERS[kind]["api"]
    ids += [gpu_id(x["path"]) for x in g["exes"] if x["api"] == api and kind == "dxvk" and E.JOURNAL.has(gpu_id(x["path"]))]
    res = E.undo_ids(ids, log, by="mining") if ids else {"undone": 0}
    if kind == "mesa" and E.JOURNAL.has(ENV_ID) and not any(t.startswith("glmesa:") for t in E.JOURNAL.newest_first()):
        E.undo_ids([ENV_ID], log, by="mining")  # більше жодної гри з Mesa — прибираємо й змінну
    return res


def enable_mesa(g: dict, log, hw: dict) -> dict:
    return enable_layer("mesa", g, log, hw)


def disable_mesa(g: dict, log) -> dict:
    return disable_layer("mesa", g, log)


def bench_mesa(hw: dict) -> str:
    """Папка версії Mesa для GPU-тесту OptimaX (він на OpenGL, x64) — щоб тест малювала майнінгова карта."""
    if not active(hw) or not E.IS_WIN:
        return ""
    info = mesa_info()
    return info["dir"] if info and "x64" in info["arch"] else ""


# ───────────────────────── античит ─────────────────────────
ANTICHEAT = {"easyanticheat": "EasyAntiCheat", "easyanticheat_eos": "EasyAntiCheat", "battleye": "BattlEye",
             "beservice.exe": "BattlEye", "beservice_x64.exe": "BattlEye", "xigncode": "XIGNCODE3",
             "xigncode3": "XIGNCODE3", "gameguard": "GameGuard", "npgamemon.des": "GameGuard",
             "pnkbstra.exe": "PunkBuster", "pnkbstrb.exe": "PunkBuster", "eac_launcher.exe": "EasyAntiCheat",
             "start_protected_game.exe": "EasyAntiCheat", "vgc.exe": "Vanguard"}


def anticheat(folder: str) -> str:
    """Назва античиту в папці гри (до двох рівнів углиб) або "". Таким іграм не кладемо чужі d3d9/d3d11/opengl32.dll:
    античит може не пустити гру або, гірше, вважати це втручанням."""
    root_depth = folder.rstrip("\\/").count(os.sep)
    try:
        for dp, dns, fns in os.walk(folder):
            depth = dp.rstrip("\\/").count(os.sep) - root_depth
            for n in list(dns) + list(fns):
                hit = ANTICHEAT.get(n.lower())
                if hit:
                    return hit
            if depth >= 2:
                dns[:] = []
    except OSError:
        pass
    return ""


# ───────────────────────── режими рендерингу для кожної гри ─────────────────────────
# auto     — найкращий сумісний спосіб: DirectX 10–12 і Vulkan — напряму на карту («Висока продуктивність»); DirectX 9 —
#            через DXVK; OpenGL — через Mesa. Шар — лише якщо він завантажений і перевірений, exe потрібної розрядності, а
#            в грі немає античиту; інакше — як є, з поясненням чому.
# native   — лише «Висока продуктивність» для exe (без шарів). DirectX 9 і OpenGL так на карту без монітора не перейдуть.
# dxvk     — DXVK і для DirectX 10 / 11 (якщо напряму гра потрапляє на вбудовану — наприклад, у повноекранному режимі).
# opengl   — OpenGL через Mesa (d3d12 або Zink — див. gl_driver); DirectX — напряму.
# original — жодних змін OptimaX у цій грі (і фонове призначення її оминає).
MODES = ("auto", "native", "dxvk", "opengl", "original")
KEEP_CHECKS = 5


def game_key(g: dict) -> str:
    return g["dir"].lower().rstrip("\\/")


def profiles() -> dict:
    import features as F
    return dict((F.CFG["mining"] or {}).get("profiles") or {})


def profile(g: dict) -> dict:
    return dict(profiles().get(game_key(g)) or {})


def set_profile(g: dict, **kw) -> dict:
    import features as F
    m = dict(F.CFG["mining"] or {})
    profs = dict(m.get("profiles") or {})
    p = dict(profs.get(game_key(g)) or {})
    p.update(kw, name=g["name"])
    profs[game_key(g)] = p
    m["profiles"] = profs
    F.CFG["mining"] = m
    return p


def drop_profile(g: dict) -> None:
    import features as F
    m = dict(F.CFG["mining"] or {})
    profs = dict(m.get("profiles") or {})
    profs.pop(game_key(g), None)
    m["profiles"] = profs
    F.CFG["mining"] = m


def current_mode(g: dict) -> str:
    """Режим із профілю; без профілю (ігри, налаштовані до 6.5) — за тим, що вже зроблено: шар є — auto, інакше native."""
    m = profile(g).get("mode")
    if m in MODES:
        return m
    return "auto" if layer_folders_on(g, "dxvk") or layer_folders_on(g, "mesa") else "native"


def record_check(g: dict, res: dict) -> dict:
    """Результат перевірки рендерингу — у профіль гри (останні KEEP_CHECKS) і в базу сумісності."""
    checks = list(profile(g).get("checks") or [])
    rec = dict(ts=int(time.time()), mode=current_mode(g), verdict=res.get("verdict"), path=res.get("path") or "",
               d3=res.get("mining_3d"), vram=res.get("vram_mb"), exe=res.get("exe", ""))
    checks.append(rec)
    return set_profile(g, checks=checks[-KEEP_CHECKS:])


def probe_summary() -> dict:
    """Що показала перевірка DirectX / Vulkan ({} — її ще не було). probed — перевірка була."""
    import gpuinfo as GI
    import features as F
    pr = F.CFG["gpu_probe"]
    return dict(GI.summary(pr), probed=True) if isinstance(pr, dict) and "dxgi" in pr else {}


def compat(g: dict, kind: str, apis: tuple = None) -> list:
    """Що заважає шару kind ("dxvk" / "mesa") у цій грі — ключі пояснень mg.why.* (порожньо — можна):
    risk (Adobe AIR), anticheat, arch (немає exe x64 / x86 з потрібним API), no_layer (шар не завантажено, файли не
    збіглися із сумами або в архіві немає потрібних бібліотек), no_vulkan (DXVK і Zink працюють на Vulkan, а пристрою
    Vulkan на майнінговій карті не знайдено), no_d3d12 (Mesa d3d12 — на DirectX 12, а карта його не підтримала)."""
    out = []
    if g.get("risk"):
        return ["risk"]
    if g.get("anticheat"):
        out.append("anticheat")
    targets = layer_targets(g, kind, apis)
    if not targets:
        out.append("arch")
    info = layer_info(kind)
    if not info:
        out.append("no_layer")
    elif kind == "dxvk":
        for d, a in targets:
            need = {n for x in g["exes"] if _dir(x["path"]).lower() == d.lower() and x["api"] in (apis or ("dx9",))
                    for n in DXVK_NEEDS.get(x["api"], ())}
            if not need <= set(info["arch"].get(a) or {}):
                out.append("no_layer")
                break
    elif any(a not in info["arch"] for _, a in targets):
        out.append("no_layer")
    pr = probe_summary()
    if pr.get("probed") and not pr.get("gpu"):
        out.append("no_gpu")  # DirectX не бачить майнінгову карту (драйвер, карта вимкнена) — шар нічого не дасть
    elif pr.get("gpu"):  # перевірка DirectX / Vulkan уже була — зважаємо на неї (без неї не забороняємо)
        if (kind == "dxvk" or (kind == "mesa" and gl_driver() == "zink")) and not pr.get("vulkan"):
            out.append("no_vulkan")
        if kind == "mesa" and gl_driver() == "d3d12" and pr.get("dx12") is False:
            out.append("no_d3d12")
    return out


def plan(g: dict, mode: str) -> dict:
    """Що зробити для режиму: gpu — exe на «Високу продуктивність»; dxvk — {папка: (розрядність, [бібліотеки])};
    mesa — {папка: розрядність}; blocked — [(шар, [причини])] — чого зробити не можна й чому."""
    res = {"gpu": [], "dxvk": {}, "mesa": {}, "blocked": [], "mode": mode}
    if mode == "original" or g.get("risk"):
        return res
    dxvk_apis = DX_APIS if mode == "dxvk" else ("dx9",)
    if mode in ("auto", "dxvk") and any(x["api"] in dxvk_apis for x in g["exes"]):
        why = compat(g, "dxvk", dxvk_apis)
        if why:
            res["blocked"].append(("dxvk", why))
        else:
            info = layer_info("dxvk")
            for d, a in layer_targets(g, "dxvk", dxvk_apis):
                apis = tuple({x["api"] for x in g["exes"] if _dir(x["path"]).lower() == d.lower()
                              and x["api"] in dxvk_apis})
                res["dxvk"][d] = (a, sorted(_files_for("dxvk", info["arch"][a], apis)))
    if mode in ("auto", "opengl") and any(x["api"] == "gl" for x in g["exes"]):
        why = compat(g, "mesa")
        if why:
            res["blocked"].append(("mesa", why))
        else:
            res["mesa"] = dict(layer_targets(g, "mesa"))
    layered = {d.lower() for d in list(res["dxvk"]) + list(res["mesa"])}
    for x in g["exes"]:
        if x["api"] == "dx9" and _dir(x["path"]).lower() not in layered:
            continue  # DirectX 9 без DXVK на карту без монітора не перейде — «Висока продуктивність» нічого не дасть
        res["gpu"].append(x["path"])
    return res


def _deployed(kind: str, folder: str) -> set:
    e = E.JOURNAL.get(layer_id(kind, folder)) or {}
    return {_base(r.get("p", "")).lower() for r in e.get("undo", []) if r.get("t") == "file"}


def _stale(kind: str, folder: str, want: list) -> bool:
    """Шар у папці вже є, але не той набір бібліотек (DirectX 9 → DirectX 9 + 11 і навпаки) — перекласти."""
    have = _deployed(kind, folder)
    return bool(have - set(want)) or any(n not in have and not os.path.isfile(_join(folder, n)) for n in want)


def _apply(g: dict, mode: str, log, hw: dict) -> dict:
    p = plan(g, mode)
    undo, todo = [], []
    want_gpu = {e.lower() for e in p["gpu"]}
    for x in g["exes"]:
        if E.JOURNAL.has(gpu_id(x["path"])) and x["path"].lower() not in want_gpu:
            undo.append(gpu_id(x["path"]))
    for kind in ("dxvk", "mesa"):
        want = {d.lower(): d for d in p[kind]}
        for d in layer_folders_on(g, kind):
            if d.lower() not in want or (kind == "dxvk" and _stale(kind, d, p["dxvk"][want[d.lower()]][1])):
                undo.append(layer_id(kind, d))
    if undo:
        E.undo_ids(undo, log, by="mining")
    for d, (a, names) in p["dxvk"].items():
        if not E.JOURNAL.has(layer_id("dxvk", d)):
            files = layer_info("dxvk")["arch"][a]  # суми звіряються ще раз — безпосередньо перед копіюванням
            todo.append(layer_tweak("dxvk", g["name"], d, {n: v for n, v in files.items() if n in names}))
    for d, a in p["mesa"].items():
        if not E.JOURNAL.has(layer_id("mesa", d)):
            todo.append(layer_tweak("mesa", g["name"], d, layer_info("mesa")["arch"][a]))
    if p["mesa"] and not E.JOURNAL.has(ENV_ID):
        todo.insert(0, env_tweak())
    gpu = model(hw)
    todo += [gpu_tweak(g["name"], x["path"], gpu) for x in g["exes"]
             if x["path"].lower() in want_gpu and exe_state(x["path"]) == "free"]
    res = E.apply_tweaks(todo, log, header=False, by="mining") if todo else {"ok": 0, "fail": 0}
    res["new"] = [t.id for t in todo if E.JOURNAL.has(t.id)]
    if E.JOURNAL.has(ENV_ID) and not any(t.startswith(LAYERS["mesa"]["prefix"]) for t in E.JOURNAL.newest_first()):
        E.undo_ids([ENV_ID], log, by="mining")  # жодної гри з Mesa — змінна більше не потрібна
    res.update(blocked=p["blocked"], undone=len(undo), mode=mode)
    return res


@_exclusive
def apply_mode(g: dict, mode: str, log, hw: dict) -> dict:
    """Приводить гру до режиму: прибирає зайве (лише те, що зробила OptimaX) і додає потрібне — через журнал відкату
    (оригінальні файли гри зберігаються поруч як *.optimax-bak і повертаються під час відкату, також з
    OptimaX-Rescue.cmd). Вибір, який користувач сам зробив у «Графіці», не чіпаємо. Якщо щось не вдалося — гра
    повертається до попереднього режиму."""
    if mode not in MODES:
        return {"ok": 0, "error": "mode"}
    prev = current_mode(g)
    res = _apply(g, mode, log, hw)
    if res.get("fail") or res.get("error"):
        log(tr("mg.mode_failed", game=g["name"], mode=tr(f"mg.mode.{prev}")))
        if res.get("new"):
            E.undo_ids(res["new"], log, by="mining")
        if prev != mode:
            _apply(g, prev, log, hw)
        res["rolled_back"] = True
        return res
    set_profile(g, mode=mode, prev=prev if prev != mode else profile(g).get("prev", ""))
    log(tr("mg.mode_applied", game=g["name"], mode=tr(f"mg.mode.{mode}")))
    for kind, why in res["blocked"]:
        log(tr("mg.blocked", what=LAYER_NAMES[kind], why=", ".join(tr(f"mg.why.{w}") for w in why)))
    return res


@_exclusive
def reset_game(g: dict, log) -> dict:
    """Видалити профіль: усе, що OptimaX зробила для гри (шари, призначення exe), повертається, профіль стирається."""
    ids = [gpu_id(x["path"]) for x in g["exes"] if E.JOURNAL.has(gpu_id(x["path"]))]
    ids += [layer_id(k, d) for k in ("dxvk", "mesa") for d in layer_folders_on(g, k)]
    res = E.undo_ids(ids, log, by="mining") if ids else {"undone": 0}
    if E.JOURNAL.has(ENV_ID) and not any(t.startswith(LAYERS["mesa"]["prefix"]) for t in E.JOURNAL.newest_first()):
        E.undo_ids([ENV_ID], log, by="mining")
    drop_profile(g)
    log(tr("mg.reset_done", game=g["name"]))
    return res


@_exclusive
def set_gl_driver(driver: str, log) -> dict:
    """OpenGL через Mesa: d3d12 (за замовчуванням) чи zink. Змінна середовища перезаписується, лише якщо Mesa вже десь
    увімкнена."""
    import features as F
    m = dict(F.CFG["mining"] or {})
    m["gl_driver"] = "zink" if driver == "zink" else "d3d12"
    F.CFG["mining"] = m
    if E.JOURNAL.has(ENV_ID):
        E.undo_ids([ENV_ID], log, by="mining")
        return E.apply_tweaks([env_tweak()], log, header=False, by="mining")
    return {"ok": 1}


def recommend(g: dict) -> dict:
    """Який режим порадити й чому: {mode, why: [ключі mg.rec.*]} — з бази сумісності, античиту й API."""
    import gamedb as DB
    apis = {x["api"] for x in g["exes"]}
    known = DB.lookup(g)
    if g.get("risk"):
        return dict(mode="original", why=["air"])
    if known.get("mode") in MODES:
        return dict(mode=known["mode"], why=["db"])
    if g.get("anticheat"):
        return dict(mode="native", why=["anticheat"])
    if apis & {"dx9", "gl"}:
        return dict(mode="auto", why=["dx9" if "dx9" in apis else "gl"])
    return dict(mode="native", why=["direct"])


def game_for_exe(games: list, exe: str) -> dict:
    exe = (exe or "").lower()
    return next((g for g in games for x in g["exes"] if _base(x["path"]).lower() == exe), None)


# ───────────────────────── нові ігри ─────────────────────────
def new_games(games: list) -> list:
    """Ігри, яких OptimaX ще не бачила (за папкою), — і запам'ятовує їх."""
    import features as F
    m = dict(F.CFG["mining"] or {})
    seen = set(m.get("seen") or [])
    first = not seen  # перший пошук — усі ігри «нові», про них не сповіщаємо
    fresh = [g for g in games if game_key(g) not in seen]
    if fresh:
        m["seen"] = sorted(seen | {game_key(g) for g in fresh})[-2000:]
        F.CFG["mining"] = m
    return [] if first else fresh
