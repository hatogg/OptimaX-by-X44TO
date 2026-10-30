"""
OptimaX — ігри на майнінговій відеокарті (P106 / P104 / P102, CMP HX).

У таких карт немає відеовиходів: монітор підключено до материнської плати, і картинку виводить вбудована
графіка. Щоб гру малювала майнінгова карта:

• DirectX 10 / 11 / 12 (більшість ігор). Windows уміє малювати на одній карті, а показувати через іншу, — треба лише
  призначити exe гри на «Високу продуктивність» (HKCU\\…\\DirectX\\UserGpuPreferences, GpuPreference=2). OptimaX сама
  знаходить встановлені ігри (Steam, Epic, GOG, Ubisoft і «Мої ігри») і призначає кожен їхній exe — з відкатом через
  журнал. Значення, яке вже хтось задав (користувач у «Графіці» чи «Мої ігри»), не чіпаємо.
• DirectX 9 і Adobe AIR. На пропатчених драйверах такі ігри на майнінговій карті можуть давати синій екран
  (dxgmms1.sys), тож лишаємо їх на вбудованій графіці.
• OpenGL. Налаштування «Графіка» Windows на OpenGL не діє: вікно малює та карта, що виводить картинку. Обхід —
  Mesa (pal1000/mesa-dist-win, драйвер d3d12: OpenGL поверх DirectX 12) у папці гри та змінна
  MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA, за якою Mesa обирає карту. Лише за згодою, для кожної гри окремо: онлайн-ігри
  з античитом можуть не пустити гру з чужою opengl32.dll.

Mesa не входить в інсталятор (десятки мегабайтів): CI перепаковує збірку mesa-dist-win у OptimaX-Mesa-<версія>-x64.zip
і викладає її в реліз OptimaX поруч із SHA256SUMS.txt. Програма завантажує архів лише після перевірки суми й
розпаковує в ProgramData (туди звичайні програми не пишуть), звідки копіює бібліотеки в папки ігор і звідки їх
вантажить GPU-тест OptimaX, щоб малювати на майнінговій карті.
"""
from __future__ import annotations

import glob
import hashlib
import json
import ntpath
import os
import re
import shutil
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
MESA_FILES = ("opengl32.dll", "libgallium_wgl.dll", "libglapi.dll", "dxil.dll")
MESA_REQUIRED = ("opengl32.dll", "libgallium_wgl.dll")
MESA_ASSET_RE = re.compile(r"^OptimaX-Mesa-([\d.]+)-x64\.zip$", re.I)
DEMO_MESA = "26.2.0"


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


# ───────────────────────── exe: що він імпортує ─────────────────────────
def _u16(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 2], "little")


def _u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


def pe_imports(path: str) -> set:
    """Імена DLL із таблиць імпорту exe (звичайної й відкладеної), у нижньому регістрі. Порожньо — не PE або не
    вдалося прочитати. Читаємо лише заголовки й самі таблиці, а не весь файл: exe ігор бувають по сотні мегабайтів."""
    try:
        with open(path, "rb") as f:
            head = f.read(1 << 16)
            if head[:2] != b"MZ" or len(head) < 0x40:
                return set()
            pe = _u32(head, 0x3C)
            if pe + 264 > len(head) or head[pe:pe + 4] != b"PE\0\0":
                return set()
            coff = pe + 4
            nsec, opt_size = _u16(head, coff + 2), _u16(head, coff + 16)
            opt = coff + 20
            magic = _u16(head, opt)
            if magic == 0x20B:
                dd = opt + 112
            elif magic == 0x10B:
                dd = opt + 96
            else:
                return set()
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
            return out
    except (OSError, ValueError, IndexError):
        return set()


DX10_PLUS = {"d3d10.dll", "d3d10_1.dll", "d3d11.dll", "d3d12.dll", "dxgi.dll"}
DX9_DLL = re.compile(r"(d3d9|dx9)", re.I)  # shaderapidx9.dll, rendersystem_dx9.dll… — рушій вантажить d3d9 сам


def api_of(path: str, sibling_dlls: tuple = ()) -> str:
    """dx9 — DirectX 9 (на майнінговій карті ризик синього екрана); gl — OpenGL; other — решта (DX10+, Vulkan…)."""
    imps = pe_imports(path)
    if "d3d9.dll" in imps and not imps & DX10_PLUS:
        return "dx9"
    if "opengl32.dll" in imps:
        return "gl"
    if not imps & DX10_PLUS and any(DX9_DLL.search(d) for d in sibling_dlls):
        return "dx9"
    return "other"


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
        for acf in sorted(glob.glob(os.path.join(lib, "steamapps", "appmanifest_*.acf"))):
            st = vdf_parse(_read(acf, 1 << 20)).get("appstate") or {}
            appid, name, inst = str(st.get("appid") or ""), st.get("name") or "", st.get("installdir") or ""
            if not inst or appid in STEAM_SKIP_IDS or STEAM_SKIP_NAME.search(name):
                continue
            d = os.path.join(lib, "steamapps", "common", inst)
            if os.path.isdir(d):
                out.append(dict(name=name or inst, store="steam", dir=d))
    return out


def epic_games(folder: str = None) -> list:
    folder = folder or os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Epic", "EpicGamesLauncher",
                                    "Data", "Manifests")
    out = []
    for item in sorted(glob.glob(os.path.join(folder, "*.item"))):
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
                            main=os.path.normpath(os.path.join(d, exe)) if exe else ""))
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
            out.append(dict(name=os.path.basename(p), store="ubisoft", dir=p))
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
    -> [{path, api}] — спершу ближчі до кореня."""
    found = []
    root_depth = folder.rstrip("\\/").count(os.sep)
    for dp, dns, fns in os.walk(folder):
        depth = dp.rstrip("\\/").count(os.sep) - root_depth
        dns[:] = sorted(d for d in dns if d.lower() not in SKIP_DIRS and depth < MAX_DEPTH)
        dlls = tuple(f for f in fns if f.lower().endswith(".dll"))
        for fn in sorted(fns):
            if fn.lower().endswith(".exe") and not SKIP_EXE.match(fn):
                found.append((depth, os.path.join(dp, fn), dlls))
        if len(found) > MAX_EXES * 4:
            break
    found.sort(key=lambda x: (x[0], x[1].lower()))
    return [dict(path=p, api=api_of(p, dlls)) for _, p, dlls in found[:MAX_EXES]]


def _risky_folder(folder: str) -> str:
    """Adobe AIR — на майнінгових картах ті самі сині екрани, що й старі ігри DirectX 9."""
    if os.path.isdir(os.path.join(folder, "Adobe AIR")) or os.path.isfile(os.path.join(folder, "Adobe AIR.dll")):
        return "air"
    return ""


def discover() -> list:
    """Встановлені ігри з exe й тим, що вони використовують. -> [{name, store, dir, exes: [{path, api}], risk}]"""
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
                g["exes"] = [dict(path=p, api=api_of(p)) for p in g["exes"]]
            else:
                g["exes"] = scan_exes(g["dir"])
                main = g.get("main") or ""
                if main and os.path.isfile(main) and not any(x["path"].lower() == main.lower() for x in g["exes"]):
                    g["exes"].insert(0, dict(path=main, api=api_of(main)))
            g["risk"] = _risky_folder(g["dir"])
            if g["exes"]:
                games.append(g)
    return sorted(games, key=lambda g: g["name"].lower())


def demo_games() -> list:
    root = r"C:\Program Files (x86)\Steam\steamapps\common"
    return [
        dict(name="Counter-Strike 2", store="steam", dir=root + r"\Counter-Strike Global Offensive", risk="",
             exes=[dict(path=root + r"\Counter-Strike Global Offensive\game\bin\win64\cs2.exe", api="other")]),
        dict(name="Fortnite", store="epic", dir=r"C:\Program Files\Epic Games\Fortnite", risk="",
             exes=[dict(path=r"C:\Program Files\Epic Games\Fortnite\FortniteGame\Binaries\Win64\FortniteClient-Win64-"
                             r"Shipping.exe", api="other"),
                   dict(path=r"C:\Program Files\Epic Games\Fortnite\FortniteGame\Binaries\Win64\FortniteLauncher.exe",
                        api="other")]),
        dict(name="Half-Life", store="steam", dir=root + r"\Half-Life", risk="",
             exes=[dict(path=root + r"\Half-Life\hl.exe", api="gl")]),
        dict(name="Grand Theft Auto: San Andreas", store="steam", dir=root + r"\Grand Theft Auto San Andreas",
             risk="", exes=[dict(path=root + r"\Grand Theft Auto San Andreas\gta_sa.exe", api="dx9")]),
    ]


# ───────────────────────── призначення ігор на майнінгову карту ─────────────────────────
def gpu_id(exe: str) -> str:
    return "gpu:" + exe.lower()


def mesa_id(folder: str) -> str:
    return "glmesa:" + folder.lower().rstrip("\\/")


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


def game_status(g: dict) -> dict:
    """Підсумок для рядка гри: on — скільки exe малює майнінгова карта; kept — вибір користувача; dx9 — лишено на
    вбудованій; gl — є OpenGL; mesa — Mesa вже в усіх папках з OpenGL-exe."""
    st = dict(on=0, kept=0, free=0, dx9=0, gl=0, total=len(g["exes"]))
    for x in g["exes"]:
        if g.get("risk") or x["api"] == "dx9":
            st["dx9"] += 1
            continue
        if x["api"] == "gl":
            st["gl"] += 1
        s = exe_state(x["path"])
        st["on" if s == "ours" else "kept" if s == "user" else "free"] += 1
    folders = gl_folders(g)
    st["mesa"] = bool(folders) and all(E.JOURNAL.has(mesa_id(f)) for f in folders)
    return st


def assign(log, hw: dict, games: list = None) -> dict:
    """Призначає всі ще не призначені exe ігор (крім DirectX 9 / Adobe AIR) на майнінгову карту."""
    gpu = model(hw)
    games = discover() if games is None else games
    todo, res = [], dict(games=len(games), assigned=0, already=0, kept=0, dx9=0, gl=0, failed=0)
    for g in games:
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
    return [tid for tid in E.JOURNAL.newest_first() if tid.startswith(("gpu:", "glmesa:", "mining:"))]


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


# ───────────────────────── Mesa: OpenGL на майнінговій карті ─────────────────────────
def mesa_root() -> str:
    """Як і оновлення: OptimaX з правами адміністратора копіює ці бібліотеки в папки ігор і вантажить у GPU-тест,
    тож вони лежать там, куди звичайні програми писати не можуть."""
    if E.IS_WIN and not E.DRY_RUN and E.is_admin():
        return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "OptimaX", "mesa")
    return os.path.join(E.DATA_DIR, "mesa")


def _vt(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def mesa_info() -> dict:
    """Розпакована Mesa: {version, dir, files: {ім'я: sha256}} або None."""
    best = None
    for man in glob.glob(os.path.join(mesa_root(), "*", "mesa.json")):
        try:
            with open(man, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            continue
        folder = os.path.dirname(man)
        files = {k.lower(): v for k, v in (m.get("files") or {}).items()
                 if k.lower() in MESA_FILES and os.path.isfile(os.path.join(folder, k))}
        if not all(f in files for f in MESA_REQUIRED):
            continue
        ver = str(m.get("mesa") or os.path.basename(folder))
        if best is None or _vt(ver) > _vt(best["version"]):
            best = dict(version=ver, dir=folder, files=files)
    return best


def install_zip(path: str, log) -> dict:
    """Розпаковує перевірений архів OptimaX-Mesa-*.zip: лише відомі бібліотеки, кожна — за сумою з mesa.json."""
    with zipfile.ZipFile(path) as z:
        man = json.loads(z.read("mesa.json").decode("utf-8"))
        version = re.sub(r"[^\d.]", "", str(man.get("mesa") or "")) or "0"
        dest = os.path.join(mesa_root(), version)
        tmp = dest + ".part"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        files = {}
        for name, sha in (man.get("files") or {}).items():
            if name.lower() not in MESA_FILES:  # лише плоскі відомі імена: ні шляхів, ні сторонніх файлів
                continue
            data = z.read(name)
            if hashlib.sha256(data).hexdigest() != str(sha).lower():
                shutil.rmtree(tmp, ignore_errors=True)
                raise RuntimeError(tr("mg.mesa_bad", name=name))
            with open(os.path.join(tmp, name.lower()), "wb") as f:
                f.write(data)
            files[name.lower()] = str(sha).lower()
    if not all(f in files for f in MESA_REQUIRED):
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(tr("mg.mesa_bad", name=", ".join(MESA_REQUIRED)))
    with open(os.path.join(tmp, "mesa.json"), "w", encoding="utf-8") as f:
        json.dump(dict(man, files=files), f, indent=1)
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    log(tr("mg.mesa_ready", v=version))
    return mesa_info()


def find_asset(log) -> dict:
    """Архів Mesa в одному з останніх релізів OptimaX."""
    import updater as U
    import verify as V
    if not U.UPDATE_REPO:
        raise RuntimeError(tr("mg.mesa_not_found"))
    rels = json.loads(U.fetch_text(f"https://api.github.com/repos/{U.UPDATE_REPO}/releases?per_page=10", 1 << 22))
    for rel in rels if isinstance(rels, list) else []:
        if rel.get("draft"):
            continue
        assets = rel.get("assets") or []
        a = next((a for a in assets if MESA_ASSET_RE.match(a.get("name") or "")), None)
        if a:
            sums = next((x for x in assets if x.get("name") == U.SUMS_NAME), None)
            return dict(name=a["name"], url=a["browser_download_url"], size=a.get("size") or 0,
                        sha256=V.digest_of(a), sums_url=sums["browser_download_url"] if sums else "",
                        version=MESA_ASSET_RE.match(a["name"]).group(1))
    raise RuntimeError(tr("mg.mesa_not_found"))


def install_mesa(log, progress=None) -> dict:
    if not E.IS_WIN or E.DRY_RUN:
        return _demo_mesa(log)
    import updater as U
    info = find_asset(log)
    log(tr("mg.mesa_dl", name=info["name"], mb=f"{info['size'] / 2**20:.0f}"))
    path = U.download(info, log, progress, publisher="")  # zip без підпису: перевіряємо суму з релізу
    try:
        return install_zip(path, log)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _demo_mesa(log) -> dict:
    dest = os.path.join(mesa_root(), DEMO_MESA)
    os.makedirs(dest, exist_ok=True)
    files = {}
    for n in ("opengl32.dll", "libgallium_wgl.dll", "dxil.dll"):
        data = f"demo {n}".encode()
        with open(os.path.join(dest, n), "wb") as f:
            f.write(data)
        files[n] = hashlib.sha256(data).hexdigest()
    with open(os.path.join(dest, "mesa.json"), "w", encoding="utf-8") as f:
        json.dump(dict(mesa=DEMO_MESA, files=files), f)
    log("  [dry-run] " + tr("mg.mesa_ready", v=DEMO_MESA))
    return mesa_info()


def gl_folders(g: dict) -> list:
    """Папки з OpenGL-exe гри (бібліотеки Mesa кладуться саме туди, поруч з exe)."""
    out = []
    for x in g["exes"]:
        if x["api"] == "gl" and not g.get("risk"):
            d = _dir(x["path"])
            if d.lower() not in (o.lower() for o in out):
                out.append(d)
    return out


def env_tweak() -> E.Tweak:
    t = E.Tweak(ENV_ID, "game", [E.R(ENV_KEY, ADAPTER_VAR, ADAPTER_NAME, "sz"), E.X("env")])
    t._title = tr("mg.t_env")
    return t


def mesa_tweak(game: str, folder: str, info: dict) -> E.Tweak:
    ops = [E.FILE(os.path.join(info["dir"], n), _join(folder, n)) for n in MESA_FILES if n in info["files"]]
    t = E.Tweak(mesa_id(folder), "game", ops)
    t._title = tr("mg.t_mesa", game=game, folder=_base(folder) or folder)
    return t


def enable_mesa(g: dict, log, hw: dict) -> dict:
    """OpenGL-гру — на майнінгову карту через Mesa: бібліотеки в папку гри, змінна з назвою карти, і сам exe — на
    «Високу продуктивність» (за цим Windows теж ставить карту першою для DirectX 12, на якому працює Mesa)."""
    info = mesa_info()
    if not info:
        return {"ok": 0, "error": "no_mesa"}
    items = [] if E.JOURNAL.has(ENV_ID) else [env_tweak()]
    items += [mesa_tweak(g["name"], f, info) for f in gl_folders(g) if not E.JOURNAL.has(mesa_id(f))]
    items += [gpu_tweak(g["name"], x["path"], model(hw)) for x in g["exes"]
              if x["api"] == "gl" and exe_state(x["path"]) == "free"]
    if not items:
        return {"ok": 0}
    res = E.apply_tweaks(items, log, header=False, by="mining")
    log(tr("mg.mesa_on", game=g["name"]))
    return res


def disable_mesa(g: dict, log) -> dict:
    ids = [mesa_id(f) for f in gl_folders(g) if E.JOURNAL.has(mesa_id(f))]
    res = E.undo_ids(ids, log, by="mining") if ids else {"undone": 0}
    if E.JOURNAL.has(ENV_ID) and not any(t.startswith("glmesa:") for t in E.JOURNAL.newest_first()):
        E.undo_ids([ENV_ID], log, by="mining")  # більше жодної гри з Mesa — прибираємо й змінну
    return res


def bench_mesa(hw: dict) -> str:
    """Папка Mesa для GPU-тесту OptimaX (він на OpenGL) — щоб тест малювала майнінгова карта, а не вбудована."""
    if not active(hw) or not E.IS_WIN:
        return ""
    info = mesa_info()
    return info["dir"] if info else ""
