"""Universal GPU Renderer (OptimaX 6.5) на фальшивій Windows: режими рендерингу для кожної гри з профілями, DXVK для
DirectX 9 і DirectX 10 / 11 (лише потрібні бібліотеки потрібної розрядності), резервна копія й повернення файлів гри,
перевірка сумісності до змін (античит, Vulkan), повернення попереднього режиму після помилки, «Оригінал» і видалення
профілю, Zink для Mesa, нові ігри, база сумісності.

Запуск: FAKE_TARGET=tests/scripts/renderer_fake.py python tests/scripts/fake_windows.py --out DIR"""
import base64
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
import gamedb as DB  # noqa: E402
import hardware as H  # noqa: E402
import mining as MG  # noqa: E402
import rescue as RS  # noqa: E402
from _pe import write_pe  # noqa: E402

R = {}
LOG = []
log = LOG.append
hw = H._from_demo("mining")
F.CFG["games"] = []
F.CFG["gpu_probe"] = None

root = tempfile.mkdtemp(prefix="games_")


def game(name, *exes):
    """exes: (відносний шлях, розрядність, імпорти...)"""
    d = os.path.join(root, name)
    out = []
    for rel, arch, *imps in exes:
        p = os.path.join(d, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        write_pe(p, "kernel32.dll", *imps, pe32=arch == "x86")
        out.append(p)
    return d, out


dx11_dir, (dx11_exe,) = game("Racer", ("bin/racer.exe", "x64", "d3d11.dll", "dxgi.dll"))
with open(os.path.join(dx11_dir, "bin", "dxgi.dll"), "wb") as f:  # своя dxgi.dll гри (обгортка) — має повернутися
    f.write(b"the game's own dxgi")
dx9_dir, (dx9_exe,) = game("Classic", ("classic.exe", "x86", "d3d9.dll"))
ac_dir, (ac_exe,) = game("Arena", ("arena.exe", "x86", "d3d9.dll"))
os.makedirs(os.path.join(ac_dir, "EasyAntiCheat"))
gl_dir, (gl_exe,) = game("Quake", ("quake.exe", "x86", "opengl32.dll"))
for name, d in (("Racer", dx11_dir), ("Classic", dx9_dir), ("Arena", ac_dir), ("Quake", gl_dir)):
    F.add_game(os.path.join(d, {"Racer": "bin/racer.exe", "Classic": "classic.exe", "Arena": "arena.exe",
                                "Quake": "quake.exe"}[name]).replace("/", os.sep))


def pref(p):
    v = E.reg_get(E.DX_PREF, p)
    return v[1] if v else None


def find(games, name):
    return next(g for g in games if os.path.basename(g["dir"]) == name or g["name"] == name)


def files(d):
    return sorted(n for n in os.listdir(d) if n.endswith(".dll"))


def read(p):
    return open(p, "rb").read().decode() if os.path.exists(p) else None


games = MG.discover()
R["apis"] = {g["name"]: [f"{x['api']}:{x['arch']}" for x in g["exes"]] for g in games}
R["anticheat"] = {g["name"]: g.get("anticheat") for g in games}
racer = next(g for g in games if dx11_exe.lower() == g["exes"][0]["path"].lower())
classic = next(g for g in games if dx9_exe.lower() == g["exes"][0]["path"].lower())
arena = next(g for g in games if ac_exe.lower() == g["exes"][0]["path"].lower())
quake = next(g for g in games if gl_exe.lower() == g["exes"][0]["path"].lower())
R["new_first"] = len(MG.new_games(games))  # перший пошук: ще нічого не бачили — не сповіщаємо

# ── DXVK з усіма бібліотеками для обох розрядностей ──
pack = tempfile.mkdtemp(prefix="pack_")
dfiles = {f"{a}/{n}": f"dxvk {a} {n}".encode() for a in ("x64", "x86") for n in MG.DXVK_FILES}
dz = os.path.join(pack, "dxvk.zip")
with zipfile.ZipFile(dz, "w") as z:
    z.writestr("dxvk.json", json.dumps({"dxvk": "2.6.2",
                                        "files": {n: hashlib.sha256(b).hexdigest() for n, b in dfiles.items()}}))
    for n, b in dfiles.items():
        z.writestr(n, b)
MG.install_zip(dz, log, "dxvk")
mfiles = {f"{a}/{n}": f"mesa {a} {n}".encode() for a in ("x64", "x86") for n in ("opengl32.dll", "libgallium_wgl.dll")}
mz = os.path.join(pack, "mesa.zip")
with zipfile.ZipFile(mz, "w") as z:
    z.writestr("mesa.json", json.dumps({"mesa": "26.2.0",
                                        "files": {n: hashlib.sha256(b).hexdigest() for n, b in mfiles.items()}}))
    for n, b in mfiles.items():
        z.writestr(n, b)
MG.install_zip(mz, log, "mesa")

# ── перевірка сумісності до змін ──
R["compat"] = {"classic": MG.compat(classic, "dxvk"), "arena": MG.compat(arena, "dxvk"),
               "racer_dx11": MG.compat(racer, "dxvk", MG.DX_APIS), "racer_dx9": MG.compat(racer, "dxvk")}
F.CFG["gpu_probe"] = {"ts": 1, "dxgi": [dict(name="NVIDIA GeForce GTX 1060 6GB", ven=0x10DE, dev=0x1C07, outputs=0,
                                             luid="0x00000000_0x0000D6B5", dx12=True, vram_mb=6070)],
                      "vulkan": [], "errors": []}
R["compat_novk"] = MG.compat(classic, "dxvk")
R["plan_novk"] = MG.plan(classic, "auto")["blocked"]
# майнінгова карта недоступна: DirectX бачить лише вбудовану
F.CFG["gpu_probe"] = {"ts": 1, "dxgi": [dict(name="Intel(R) HD Graphics 4000", ven=0x8086, dev=0x162, outputs=1,
                                             luid="0x00000000_0x0000C2E1", dx12=False, vram_mb=32)],
                      "vulkan": [], "errors": []}
R["compat_nogpu"] = {"dxvk": MG.compat(classic, "dxvk"), "mesa": MG.compat(quake, "mesa")}
F.CFG["gpu_probe"] = None

# ── Auto для DirectX 9 (x86): лише d3d9 / d3d8 x86, exe — на карту ──
res = MG.apply_mode(classic, "auto", log, hw)
R["classic_auto"] = {"ok": res.get("ok"), "fail": res.get("fail"), "files": files(dx9_dir),
                     "d3d9": read(os.path.join(dx9_dir, "d3d9.dll")), "pref": pref(dx9_exe),
                     "mode": MG.current_mode(classic), "status": MG.game_status(classic)["dxvk"]}
entry = E.JOURNAL.get(MG.layer_id("dxvk", dx9_dir)) or {}
R["classic_rescue"] = len([ln for rec in entry.get("undo", []) for ln in RS.undo_lines(rec)])

# ── античит: шар не кладеться, DirectX 9 без шару на карту не призначається ──
res = MG.apply_mode(arena, "auto", log, hw)
R["arena_auto"] = {"blocked": res.get("blocked"), "files": files(ac_dir), "pref": pref(ac_exe),
                   "mode": MG.current_mode(arena)}

# ── Native для DirectX 11 → DXVK (DirectX 11) → Native: файли гри повертаються ──
res = MG.apply_mode(racer, "native", log, hw)
R["racer_native"] = {"pref": pref(dx11_exe), "files": files(os.path.dirname(dx11_exe))}
res = MG.apply_mode(racer, "dxvk", log, hw)
bindir = os.path.dirname(dx11_exe)
R["racer_dxvk"] = {"ok": res.get("ok"), "files": files(bindir), "dxgi": read(os.path.join(bindir, "dxgi.dll")),
                   "bak": read(os.path.join(bindir, "dxgi.dll.optimax-bak")), "pref": pref(dx11_exe),
                   "status": MG.game_status(racer).get("dxvk_dx11"), "mode": MG.current_mode(racer),
                   "prev": MG.profile(racer).get("prev")}
res = MG.apply_mode(racer, "native", log, hw)
R["racer_back"] = {"files": files(bindir), "dxgi": read(os.path.join(bindir, "dxgi.dll")),
                   "bak": os.path.exists(os.path.join(bindir, "dxgi.dll.optimax-bak")), "pref": pref(dx11_exe),
                   "undone": res.get("undone")}

# ── помилка посеред зміни: гра повертається до попереднього режиму ──
os.makedirs(os.path.join(bindir, "d3d11.dll"))  # на місці бібліотеки — тека: копіювання не вдасться
res = MG.apply_mode(racer, "dxvk", log, hw)
R["racer_fail"] = {"rolled_back": res.get("rolled_back"), "files": files(bindir),
                   "dxgi": read(os.path.join(bindir, "dxgi.dll")), "pref": pref(dx11_exe),
                   "mode": MG.current_mode(racer), "dxvk_ids": [t for t in MG.our_ids() if t.startswith("dxvk:")
                                                                and bindir.lower() in t]}
os.rmdir(os.path.join(bindir, "d3d11.dll"))

# ── OpenGL через Mesa, перемикання на Zink і назад ──
res = MG.apply_mode(quake, "opengl", log, hw)
R["quake_gl"] = {"files": files(gl_dir), "env": (E.reg_get(MG.ENV_KEY, MG.ADAPTER_VAR) or [None, None])[1],
                 "gallium": E.reg_get(MG.ENV_KEY, "GALLIUM_DRIVER")}
MG.set_gl_driver("zink", log)
R["zink"] = (E.reg_get(MG.ENV_KEY, "GALLIUM_DRIVER") or [None, None])[1]
MG.set_gl_driver("d3d12", log)
R["zink_off"] = E.reg_get(MG.ENV_KEY, "GALLIUM_DRIVER")

# ── «Оригінал»: усе повертається, фонове призначення гру оминає ──
res = MG.apply_mode(quake, "original", log, hw)
R["quake_original"] = {"files": files(gl_dir), "pref": pref(gl_exe), "env": E.reg_get(MG.ENV_KEY, MG.ADAPTER_VAR),
                       "mode": MG.current_mode(quake)}
res = MG.assign(log, hw, [quake])
R["assign_original"] = {"original": res.get("original"), "pref": pref(gl_exe)}

# ── перевірка рендерингу й база сумісності ──
MG.record_check(classic, {"verdict": "mining", "mining_3d": 70.0, "path": "DirectX 9 → DXVK → Vulkan"})
DB.rate(classic, "auto", "ok")
DB.rate(racer, "dxvk", "bad")
R["db"] = {"classic": DB.lookup(classic).get("mode"), "classic_src": DB.lookup(classic).get("source"),
           "racer_bad": DB.lookup(racer).get("bad"), "verified": DB.verified(classic).get("verdict")}
exp = os.path.join(pack, "profiles.json")
R["exported"] = DB.export_profiles(exp)

# ── видалити профіль: оригінальний стан і жодного запису ──
MG.reset_game(classic, log)
R["classic_reset"] = {"files": files(dx9_dir), "pref": pref(dx9_exe), "profile": MG.profile(classic)}
R["imported"] = DB.import_profiles(exp)
R["imported_mode"] = MG.profile(classic).get("imported_mode")

# ── нові ігри ──
game("NewOne", ("new.exe", "x64", "d3d12.dll"))
F.add_game(os.path.join(root, "NewOne", "new.exe"))
R["new_second"] = [g["name"] for g in MG.new_games(MG.discover())]

MG.revert(log)
R["left"] = MG.our_ids()
R["racer_final"] = {"files": files(bindir), "dxgi": read(os.path.join(bindir, "dxgi.dll"))}

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "renderer.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
