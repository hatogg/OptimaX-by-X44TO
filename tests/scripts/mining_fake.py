"""Ігри на майнінговій карті (mining.py) на фальшивій Windows: пошук ігор Steam, призначення на карту через
UserGpuPreferences, вибір користувача й DirectX 9 (зокрема рушій Source) не чіпаються, Mesa потрібної розрядності в
папці гри з резервною копією файлу гри, перевірка сум розпакованої Mesa, одна зміна за раз, передача exe у «Мої ігри»,
відкат через журнал і рядки OptimaX-Rescue.cmd.

Запуск: FAKE_TARGET=tests/scripts/mining_fake.py python tests/scripts/fake_windows.py --out DIR"""
import base64
import hashlib
import json
import os
import sys
import tempfile
import threading
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import hardware as H  # noqa: E402
import mining as MG  # noqa: E402
import rescue as RS  # noqa: E402
from _pe import write_pe  # noqa: E402

R = {}
LOG = []
log = LOG.append
hw = H._from_demo("mining")
F.CFG["games"] = []

# ── Steam: дві бібліотеки (друга — з дужками в шляху), гра з кількома exe, Source-гра, перерозподілювані пакети ──
steam = tempfile.mkdtemp(prefix="steam_")
lib2 = os.path.join(tempfile.mkdtemp(prefix="lib_"), "Games [SSD]")
os.makedirs(os.path.join(steam, "steamapps"))
with open(os.path.join(steam, "steamapps", "libraryfolders.vdf"), "w") as f:
    f.write('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n'
            % (steam.replace("\\", "\\\\"), lib2.replace("\\", "\\\\")))


def app(lib, appid, name, inst):
    os.makedirs(os.path.join(lib, "steamapps", "common", inst), exist_ok=True)
    with open(os.path.join(lib, "steamapps", f"appmanifest_{appid}.acf"), "w") as f:
        f.write(f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n\t"installdir"\t\t"{inst}"\n}}\n')
    return os.path.join(lib, "steamapps", "common", inst)


game = app(lib2, "4000", "Test Game", "TestGame")
for d in (("bin", "win64"), ("bin32",), ("arm",), ("_CommonRedist", "vcredist")):
    os.makedirs(os.path.join(game, *d))
dx11 = write_pe(os.path.join(game, "bin", "win64", "game.exe"), "kernel32.dll", "d3d11.dll", "dxgi.dll")
launcher = write_pe(os.path.join(game, "launcher.exe"), "kernel32.dll", "user32.dll")
gl = write_pe(os.path.join(game, "bin", "glview.exe"), "kernel32.dll", "opengl32.dll")
gl32 = write_pe(os.path.join(game, "bin32", "gl32.exe"), "kernel32.dll", "opengl32.dll", pe32=True)
glarm = write_pe(os.path.join(game, "arm", "glarm.exe"), "kernel32.dll", "opengl32.dll", machine=0xAA64)
write_pe(os.path.join(game, "_CommonRedist", "vcredist", "vc_redist.x64.exe"), "kernel32.dll")
write_pe(os.path.join(game, "unins000.exe"), "kernel32.dll")
with open(os.path.join(game, "bin", "opengl32.dll"), "wb") as f:  # своя opengl32.dll гри — має повернутися після відкату
    f.write(b"the game's own opengl32")
old = app(steam, "5000", "Old Game", "OldGame")
dx9 = write_pe(os.path.join(old, "old.exe"), "kernel32.dll", "d3d9.dll")
src = app(steam, "220", "Half-Life 2", "Half-Life 2")  # рушій Source: exe у корені, d3d9 — у bin\shaderapidx9.dll
hl2 = write_pe(os.path.join(src, "hl2.exe"), "kernel32.dll", "user32.dll")
os.makedirs(os.path.join(src, "bin"))
with open(os.path.join(src, "bin", "shaderapidx9.dll"), "wb") as f:
    f.write(b"MZ")
app(steam, "228980", "Steamworks Common Redistributables", "Steamworks Shared")
write_pe(os.path.join(steam, "steamapps", "common", "Steamworks Shared", "x.exe"), "kernel32.dll")
E.reg_set(r"HKCU\Software\Valve\Steam", "SteamPath", steam.replace(os.sep, "/"), "sz")
# користувач сам вибрав для лаунчера «Енергозбереження» — OptimaX це не перезаписує
E.reg_set(E.DX_PREF, launcher, "GpuPreference=1;", "sz")


def pref(p):
    v = E.reg_get(E.DX_PREF, p)
    return v[1] if v else None


def rel(p):
    return os.path.relpath(p, game).replace(os.sep, "/")


games = MG.discover()
R["games"] = sorted(g["name"] for g in games)
tg = next(g for g in games if g["name"] == "Test Game")
R["exes"] = sorted(f"{rel(x['path'])}:{x['api']}:{x['arch']}" for x in tg["exes"])
R["old_api"] = [x["api"] for g in games if g["name"] == "Old Game" for x in g["exes"]]
R["source_api"] = [x["api"] for g in games if g["name"] == "Half-Life 2" for x in g["exes"]]

# одна зміна за раз: поки йде інша, assign нічого не пише в журнал
with MG._LOCK:
    R["busy"] = MG.assign(log, hw, games)
res = MG.assign(log, hw, games)
R["assign1"] = {k: res[k] for k in ("assigned", "already", "kept", "dx9")}
R["pref_after"] = {"dx11": pref(dx11), "gl": pref(gl), "gl32": pref(gl32), "launcher": pref(launcher),
                   "dx9": pref(dx9), "hl2": pref(hl2)}
res = MG.assign(log, hw, MG.discover())
R["assign2"] = {k: res[k] for k in ("assigned", "already", "kept", "dx9")}
R["status"] = MG.game_status(tg)
R["targets"] = sorted(f"{rel(d)}:{a}" for d, a in MG.gl_targets(tg))

# ── Mesa: перевірений архів, підмінений архів, недопустима версія, підмінена бібліотека після розпакування ──
pack = tempfile.mkdtemp(prefix="mesa_")
files = {f"{a}/{n}": f"mesa {a} {n}".encode() for a in ("x64", "x86") for n in ("opengl32.dll", "libgallium_wgl.dll",
                                                                                 "dxil.dll")}


def make_zip(path, tamper=False, version="26.2.0"):
    man = {"mesa": version, "files": {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mesa.json", json.dumps(man))
        for n, b in files.items():
            z.writestr(n, b + (b"!" if tamper and n == "x64/opengl32.dll" else b""))
    return path


def attempt(path):
    try:
        MG.install_zip(path, log)
        return "installed"
    except RuntimeError:
        return "rejected"


R["tampered"] = attempt(make_zip(os.path.join(pack, "bad.zip"), tamper=True))
R["dotdot"] = attempt(make_zip(os.path.join(pack, "dots.zip"), version=".."))
R["mesa_after_bad"] = MG.mesa_info()
R["root_alive"] = os.path.isdir(os.path.dirname(MG.mesa_root()))
info = MG.install_zip(make_zip(os.path.join(pack, "ok.zip")), log)
R["mesa"] = {"version": info["version"], "arch": {a: sorted(v) for a, v in info["arch"].items()}}
R["bench_mesa"] = MG.bench_mesa(hw) == info["dir"]
# хтось підкинув «новішу» Mesa з чужою opengl32.dll: без правильних сум вона не існує для OptimaX
fake = os.path.join(MG.mesa_root(), "999", "x64")
os.makedirs(fake)
for n in ("opengl32.dll", "libgallium_wgl.dll"):
    with open(os.path.join(fake, n), "wb") as f:
        f.write(b"evil")
with open(os.path.join(MG.mesa_root(), "999", "mesa.json"), "w") as f:
    json.dump({"mesa": "999", "files": {"x64/opengl32.dll": "0" * 64, "x64/libgallium_wgl.dll": "0" * 64}}, f)
R["planted"] = MG.mesa_info()["version"]

gl_dir, gl32_dir = os.path.dirname(gl), os.path.dirname(gl32)
out = MG.enable_mesa(tg, log, hw)
R["enable"] = {"ok": out.get("ok"), "env": (E.reg_get(MG.ENV_KEY, MG.ADAPTER_VAR) or [None, None])[1],
               "opengl32": open(os.path.join(gl_dir, "opengl32.dll"), "rb").read().decode(),
               "opengl32_x86": open(os.path.join(gl32_dir, "opengl32.dll"), "rb").read().decode(),
               "arm": os.path.exists(os.path.join(os.path.dirname(glarm), "opengl32.dll")),
               "bak": os.path.exists(os.path.join(gl_dir, "opengl32.dll.optimax-bak")),
               "dxil": os.path.exists(os.path.join(gl_dir, "dxil.dll")), "status": MG.game_status(tg)["mesa"]}
entry = E.JOURNAL.get(MG.mesa_id(gl_dir)) or {}
lines = [ln for rec in entry.get("undo", []) for ln in RS.undo_lines(rec)]
code = [base64.b64decode(ln.rsplit(" ", 1)[1]).decode("utf-16-le") for ln in lines if "-EncodedCommand" in ln]
R["rescue"] = {"lines": len(lines), "ps": len(code), "hash": all("Get-FileHash" in c for c in code),
               "bak": sum("Move-Item" in c and ".optimax-bak" in c for c in code)}

# підмінили бібліотеку вже в папці Mesa — копіювати її в наступну гру не можна
with open(os.path.join(info["dir"], "x64", "libgallium_wgl.dll"), "ab") as f:
    f.write(b"tampered")
R["tampered_installed"] = MG.mesa_info()

out = MG.disable_mesa(tg, log)
R["disable"] = {"opengl32": open(os.path.join(gl_dir, "opengl32.dll"), "rb").read().decode(),
                "bak": os.path.exists(os.path.join(gl_dir, "opengl32.dll.optimax-bak")),
                "gallium": os.path.exists(os.path.join(gl_dir, "libgallium_wgl.dll")),
                "x86": os.path.exists(os.path.join(gl32_dir, "opengl32.dll")),
                "env": E.reg_get(MG.ENV_KEY, MG.ADAPTER_VAR), "ids": [t for t in MG.our_ids() if not t.startswith("gpu:")]}

# гра оновилася й поклала свою libgallium_wgl.dll поверх нашої — відкат її не видаляє, а відкладений файл гри прибирає
info = MG.install_zip(make_zip(os.path.join(pack, "ok2.zip")), log)
MG.enable_mesa(tg, log, hw)
with open(os.path.join(gl_dir, "libgallium_wgl.dll"), "wb") as f:
    f.write(b"updated by the game")
with open(os.path.join(gl_dir, "opengl32.dll"), "wb") as f:
    f.write(b"updated opengl32 by the game")

# «Мої ігри» забирає exe, призначений на майнінгову карту: журнал лишається узгодженим
F.add_game(dx11)
F.set_game_option(dx11, "dgpu", True, log)
R["handover"] = {"mine": E.JOURNAL.has(f"game:{dx11.lower()}:dgpu"), "gpu": E.JOURNAL.has(MG.gpu_id(dx11)),
                 "pref": pref(dx11)}

LOG.clear()
out = MG.revert(log)
R["revert"] = {"undone": out.get("undone"), "partial": out.get("partial"),
               "gallium": open(os.path.join(gl_dir, "libgallium_wgl.dll"), "rb").read().decode(),
               "opengl32": open(os.path.join(gl_dir, "opengl32.dll"), "rb").read().decode(),
               "bak_left": os.path.exists(os.path.join(gl_dir, "opengl32.dll.optimax-bak")),
               "dxil": os.path.exists(os.path.join(gl_dir, "dxil.dll")),
               "noted": any("libgallium_wgl.dll" in ln for ln in LOG),
               "pref": {"dx11": pref(dx11), "gl": pref(gl), "gl32": pref(gl32), "launcher": pref(launcher)},
               "env": E.reg_get(MG.ENV_KEY, MG.ADAPTER_VAR), "left": MG.our_ids()}
F.set_game_option(dx11, "dgpu", False, log)
R["handover_off"] = pref(dx11)

# ── DXVK: DirectX 9 через Vulkan — d3d9.dll поруч з hl2.exe (рушій Source вантажить d3d9 з bin\\, але Windows шукає
# її спершу поруч з exe), сам exe — на карту; вимкнення прибирає обидва ──
dfiles = {f"{a}/d3d9.dll": f"dxvk {a} d3d9".encode() for a in ("x64", "x86")}
dz = os.path.join(pack, "dxvk.zip")
with zipfile.ZipFile(dz, "w") as z:
    z.writestr("dxvk.json", json.dumps({"dxvk": "2.6.2",
                                        "files": {n: hashlib.sha256(b).hexdigest() for n, b in dfiles.items()}}))
    for n, b in dfiles.items():
        z.writestr(n, b)
MG.install_zip(dz, log, "dxvk")
hl = next(g for g in MG.discover() if g["name"] == "Half-Life 2")
out = MG.enable_layer("dxvk", hl, log, hw)
R["dxvk_on"] = {"ok": out.get("ok"), "d3d9": open(os.path.join(src, "d3d9.dll"), "rb").read().decode(),
                "pref": pref(hl2), "status": MG.game_status(hl)["dxvk"], "targets": len(MG.layer_targets(hl, "dxvk"))}
MG.disable_layer("dxvk", hl, log)
R["dxvk_off"] = {"d3d9": os.path.exists(os.path.join(src, "d3d9.dll")), "pref": pref(hl2),
                 "ids": [t for t in MG.our_ids() if t.startswith(("dxvk:", "gpu:"))]}

# одночасний запуск із двох потоків: друга спроба не чекає й не пише в журнал
started, results = threading.Event(), []
orig = E.apply_tweaks


def slow(*a, **k):
    started.set()
    threading.Event().wait(0.3)
    return orig(*a, **k)


E.apply_tweaks = slow
t = threading.Thread(target=lambda: results.append(MG.assign(log, hw, MG.discover())))
t.start()
started.wait(5)
results.append(MG.assign(log, hw, MG.discover()))
t.join()
E.apply_tweaks = orig
R["parallel"] = sorted("busy" if r.get("busy") else "ran" for r in results)
MG.revert(log)

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "roundtrip.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
