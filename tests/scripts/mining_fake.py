"""Ігри на майнінговій карті (mining.py) на фальшивій Windows: пошук ігор Steam, призначення на карту через
UserGpuPreferences, вибір користувача й DirectX 9 не чіпаються, Mesa в папці гри з резервною копією файлу гри,
відкат через журнал і рядки OptimaX-Rescue.cmd.

Запуск: FAKE_TARGET=tests/scripts/mining_fake.py python tests/scripts/fake_windows.py --out DIR"""
import hashlib
import json
import os
import sys
import tempfile
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

# ── Steam: дві бібліотеки, одна гра з трьома exe, перерозподілювані пакети, інсталятор ──
steam = tempfile.mkdtemp(prefix="steam_")
lib2 = tempfile.mkdtemp(prefix="lib2_")
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
os.makedirs(os.path.join(game, "bin", "win64"))
os.makedirs(os.path.join(game, "_CommonRedist", "vcredist"))
dx11 = write_pe(os.path.join(game, "bin", "win64", "game.exe"), "kernel32.dll", "d3d11.dll", "dxgi.dll")
launcher = write_pe(os.path.join(game, "launcher.exe"), "kernel32.dll", "user32.dll")
gl = write_pe(os.path.join(game, "bin", "glview.exe"), "kernel32.dll", "opengl32.dll")
write_pe(os.path.join(game, "_CommonRedist", "vcredist", "vc_redist.x64.exe"), "kernel32.dll")
write_pe(os.path.join(game, "unins000.exe"), "kernel32.dll")
with open(os.path.join(game, "bin", "opengl32.dll"), "wb") as f:  # своя opengl32.dll гри — має повернутися після відкату
    f.write(b"the game's own opengl32")
old = app(steam, "5000", "Old Game", "OldGame")
dx9 = write_pe(os.path.join(old, "old.exe"), "kernel32.dll", "d3d9.dll")
app(steam, "228980", "Steamworks Common Redistributables", "Steamworks Shared")
write_pe(os.path.join(steam, "steamapps", "common", "Steamworks Shared", "x.exe"), "kernel32.dll")
E.reg_set(r"HKCU\Software\Valve\Steam", "SteamPath", steam.replace(os.sep, "/"), "sz")
# користувач сам вибрав для лаунчера «Енергозбереження» — OptimaX це не перезаписує
E.reg_set(E.DX_PREF, launcher, "GpuPreference=1;", "sz")


def pref(p):
    v = E.reg_get(E.DX_PREF, p)
    return v[1] if v else None


games = MG.discover()
R["games"] = sorted(g["name"] for g in games)
tg = next(g for g in games if g["name"] == "Test Game")
R["exes"] = sorted(os.path.relpath(x["path"], game).replace(os.sep, "/") + ":" + x["api"] for x in tg["exes"])
R["old_api"] = [x["api"] for g in games if g["name"] == "Old Game" for x in g["exes"]]

res = MG.assign(log, hw, games)
R["assign1"] = {k: res[k] for k in ("assigned", "already", "kept", "dx9")}
R["pref_after"] = {"dx11": pref(dx11), "gl": pref(gl), "launcher": pref(launcher), "dx9": pref(dx9)}
res = MG.assign(log, hw, MG.discover())
R["assign2"] = {k: res[k] for k in ("assigned", "already", "kept", "dx9")}
R["status"] = MG.game_status(tg)

# ── Mesa: перевірений архів, підмінений архів ──
pack = tempfile.mkdtemp(prefix="mesa_")
files = {"opengl32.dll": b"mesa opengl32", "libgallium_wgl.dll": b"mesa gallium", "dxil.dll": b"dxil"}


def make_zip(path, tamper=False):
    man = {"mesa": "26.2.0", "files": {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mesa.json", json.dumps(man))
        for n, b in files.items():
            z.writestr(n, b + (b"!" if tamper and n == "opengl32.dll" else b""))
        z.writestr("../evil.dll", b"x")  # шлях за межі папки — має бути проігнорований
    return path


try:
    MG.install_zip(make_zip(os.path.join(pack, "bad.zip"), tamper=True), log)
    R["tampered"] = "installed"
except RuntimeError:
    R["tampered"] = "rejected"
R["mesa_after_bad"] = MG.mesa_info()
info = MG.install_zip(make_zip(os.path.join(pack, "ok.zip")), log)
R["mesa"] = {"version": info["version"], "files": sorted(info["files"]),
             "evil": os.path.exists(os.path.join(MG.mesa_root(), "evil.dll"))}
R["bench_mesa"] = MG.bench_mesa(hw) == info["dir"]

gl_dir = os.path.dirname(gl)
out = MG.enable_mesa(tg, log, hw)
R["enable"] = {"ok": out.get("ok"), "env": (E.reg_get(MG.ENV_KEY, MG.ADAPTER_VAR) or [None, None])[1],
               "opengl32": open(os.path.join(gl_dir, "opengl32.dll"), "rb").read().decode(),
               "bak": os.path.exists(os.path.join(gl_dir, "opengl32.dll.optimax-bak")),
               "dxil": os.path.exists(os.path.join(gl_dir, "dxil.dll")), "status": MG.game_status(tg)["mesa"]}
entry = E.JOURNAL.get(MG.mesa_id(gl_dir)) or {}
R["rescue"] = [ln for rec in entry.get("undo", []) for ln in RS.undo_lines(rec)]

out = MG.disable_mesa(tg, log)
R["disable"] = {"opengl32": open(os.path.join(gl_dir, "opengl32.dll"), "rb").read().decode(),
                "bak": os.path.exists(os.path.join(gl_dir, "opengl32.dll.optimax-bak")),
                "gallium": os.path.exists(os.path.join(gl_dir, "libgallium_wgl.dll")),
                "env": E.reg_get(MG.ENV_KEY, MG.ADAPTER_VAR), "ids": [t for t in MG.our_ids() if not t.startswith("gpu:")]}

# гра оновилася й поклала свою libgallium_wgl.dll поверх нашої — відкат її не видаляє
MG.enable_mesa(tg, log, hw)
with open(os.path.join(gl_dir, "libgallium_wgl.dll"), "wb") as f:
    f.write(b"updated by the game")
LOG.clear()
out = MG.revert(log)
R["revert"] = {"undone": out.get("undone"), "partial": out.get("partial"),
               "gallium": open(os.path.join(gl_dir, "libgallium_wgl.dll"), "rb").read().decode(),
               "opengl32": open(os.path.join(gl_dir, "opengl32.dll"), "rb").read().decode(),
               "dxil": os.path.exists(os.path.join(gl_dir, "dxil.dll")),
               "noted": any("libgallium_wgl.dll" in ln for ln in LOG),
               "pref": {"dx11": pref(dx11), "gl": pref(gl), "launcher": pref(launcher)},
               "env": E.reg_get(MG.ENV_KEY, MG.ADAPTER_VAR), "left": MG.our_ids()}

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "roundtrip.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
