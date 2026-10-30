"""Ігри на майнінговій карті (mining.py): що імпортує exe, пошук ігор Steam і Epic, призначення на карту з відкатом,
Mesa для OpenGL і GPU-тест через Mesa."""
import json
import os
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, SCRIPTS, skip, tail

sys.path.insert(0, ROOT)
import mining as MG  # noqa: E402  (без Qt і без змін у системі)
from _pe import make_pe, write_pe  # noqa: E402


def _tmp():
    return tempfile.mkdtemp(prefix="oxmg_")


# ── exe: таблиця імпорту ──
def test_pe_imports_regular_and_delay_load():
    d = _tmp()
    p = os.path.join(d, "a.exe")
    with open(p, "wb") as f:
        f.write(make_pe(["KERNEL32.dll", "D3D11.dll"], ["opengl32.dll"]))
    assert MG.pe_imports(p) == {"kernel32.dll", "d3d11.dll", "opengl32.dll"}
    p32 = os.path.join(d, "b.exe")
    with open(p32, "wb") as f:
        f.write(make_pe(["kernel32.dll", "d3d9.dll"], pe32=True))
    assert MG.pe_info(p32) == ("x86", {"kernel32.dll", "d3d9.dll"})
    assert MG.pe_info(p)[0] == "x64"
    arm = os.path.join(d, "c.exe")
    with open(arm, "wb") as f:
        f.write(make_pe(["opengl32.dll"], machine=0xAA64))
    assert MG.pe_info(arm) == ("", {"opengl32.dll"})


def test_pe_imports_never_raises_on_junk():
    d = _tmp()
    for name, data in (("empty.exe", b""), ("text.exe", b"hello" * 100), ("mz.exe", b"MZ" + b"\xff" * 300),
                       ("cut.exe", make_pe(["d3d9.dll"])[:200])):
        p = os.path.join(d, name)
        with open(p, "wb") as f:
            f.write(data)
        assert MG.pe_imports(p) == set(), name
    assert MG.pe_imports(os.path.join(d, "missing.exe")) == set()


def test_api_classification():
    d = _tmp()
    assert MG.api_of(write_pe(os.path.join(d, "dx9.exe"), "kernel32.dll", "d3d9.dll")) == "dx9"
    # гра, що вміє і DX9, і DX11, — не «стара»: її можна на майнінгову карту напряму (DirectX 11)
    both = MG.classify(write_pe(os.path.join(d, "both.exe"), "d3d9.dll", "d3d11.dll"))
    assert both["api"] == "dx11" and both["apis"] == ["dx9", "dx11"], both
    assert MG.api_of(write_pe(os.path.join(d, "gl.exe"), "kernel32.dll", "opengl32.dll")) == "gl"
    assert MG.api_of(write_pe(os.path.join(d, "dx11.exe"), "d3d11.dll", "dxgi.dll")) == "dx11"
    assert MG.api_of(write_pe(os.path.join(d, "dx12.exe"), "d3d12.dll", "dxgi.dll")) == "dx12"
    assert MG.api_of(write_pe(os.path.join(d, "dx10.exe"), "d3d10.dll", "dxgi.dll")) == "dx10"
    assert MG.api_of(write_pe(os.path.join(d, "vk.exe"), "vulkan-1.dll")) == "vulkan"
    assert MG.api_of(write_pe(os.path.join(d, "launcher.exe"), "kernel32.dll", "user32.dll")) == "other"
    # Unity: exe — заглушка, API імпортує UnityPlayer.dll поруч
    uni = _tmp()
    stub_u = write_pe(os.path.join(uni, "Game.exe"), "kernel32.dll")
    write_pe(os.path.join(uni, "UnityPlayer.dll"), "d3d11.dll", "dxgi.dll")
    assert MG.classify(stub_u, (), MG.engine_imports(uni))["api"] == "dx11"
    # рушій вантажить d3d9 сам: Source — hl2.exe у корені, shaderapidx9.dll у bin\\ (або bin\\x64\\)
    src = _tmp()
    stub = write_pe(os.path.join(src, "hl2.exe"), "kernel32.dll")
    assert MG.api_of(stub, MG.engine_dlls(src)) == "other"
    os.makedirs(os.path.join(src, "bin", "x64"))
    open(os.path.join(src, "bin", "x64", "shaderapidx9.dll"), "wb").close()
    assert MG.api_of(stub, MG.engine_dlls(src)) == "dx9"
    assert MG.api_of(stub, ("UnityPlayer.dll",)) == "other"


# ── Steam і Epic ──
def test_vdf_both_libraryfolders_formats():
    new = MG.vdf_parse('"libraryfolders"\n{\n "0"\n {\n  "path" "C:\\\\Program Files (x86)\\\\Steam"\n  "apps"\n'
                       '  {\n   "730" "123"\n  }\n }\n "1"\n {\n  "path" "D:\\\\SteamLibrary"\n }\n}')
    assert new["libraryfolders"]["1"]["path"] == "D:\\SteamLibrary"
    assert new["libraryfolders"]["0"]["apps"] == {"730": "123"}
    old = MG.vdf_parse('"LibraryFolders"\n{\n "TimeNextStatsReport" "1"\n "1" "E:\\\\Games\\\\Steam"\n}')
    assert old["libraryfolders"]["1"] == "E:\\Games\\Steam"
    acf = MG.vdf_parse('"AppState"\n{\n "appid" "730"\n "name" "Counter-Strike 2"\n "installdir" "CS"\n "x" ""\n}')
    assert acf["appstate"] == {"appid": "730", "name": "Counter-Strike 2", "installdir": "CS", "x": ""}


def test_steam_games_and_exe_scan():
    root, lib2 = _tmp(), _tmp()
    os.makedirs(os.path.join(root, "steamapps"))
    with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), "w") as f:
        f.write('"libraryfolders"\n{\n "1"\n {\n  "path" "%s"\n }\n}\n' % lib2.replace("\\", "\\\\"))

    def app(lib, appid, name, inst):
        os.makedirs(os.path.join(lib, "steamapps", "common", inst), exist_ok=True)
        with open(os.path.join(lib, "steamapps", f"appmanifest_{appid}.acf"), "w") as f:
            f.write(f'"AppState"\n{{\n "appid" "{appid}"\n "name" "{name}"\n "installdir" "{inst}"\n}}\n')
        return os.path.join(lib, "steamapps", "common", inst)

    g = app(lib2, "10", "Game", "Game")
    app(root, "228980", "Steamworks Common Redistributables", "Steamworks Shared")
    app(root, "20", "Not installed yet", "Missing")
    os.rmdir(os.path.join(root, "steamapps", "common", "Missing"))
    for rel in ("Game.exe", "Binaries/Win64/Game-Win64-Shipping.exe", "_CommonRedist/DirectX/DXSETUP.exe",
                "unins000.exe", "Engine/Extras/Redist/en-us/UEPrereqSetup_x64.exe", "CrashReportClient.exe",
                "a/b/c/d/e/too_deep.exe"):
        p = os.path.join(g, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        write_pe(p, "kernel32.dll", "d3d11.dll")
    games = MG.steam_games(root)
    assert [x["name"] for x in games] == ["Game"], games
    exes = [os.path.relpath(x["path"], g).replace(os.sep, "/") for x in MG.scan_exes(games[0]["dir"])]
    assert exes == ["Game.exe", "Binaries/Win64/Game-Win64-Shipping.exe"], exes


def test_epic_manifests():
    d, man = _tmp(), _tmp()
    game, engine = os.path.join(d, "Fortnite"), os.path.join(d, "UE_5.4")
    os.makedirs(game)
    os.makedirs(engine)
    items = {"a.item": dict(DisplayName="Fortnite", InstallLocation=game, LaunchExecutable="Fortnite.exe",
                            AppCategories=["public", "games", "applications"]),
             "b.item": dict(DisplayName="Unreal Engine", InstallLocation=engine, AppCategories=["engines"]),
             "c.item": dict(DisplayName="Half", InstallLocation=game, bIsIncompleteInstall=True),
             "d.item": "{not json"}
    for n, m in items.items():
        with open(os.path.join(man, n), "w") as f:
            f.write(m if isinstance(m, str) else json.dumps(m))
    got = MG.epic_games(man)
    assert [(g["name"], g["main"]) for g in got] == [("Fortnite", os.path.join(game, "Fortnite.exe"))]


# ── на фальшивій Windows: реєстр, файли, журнал ──
_CACHE = {}


def fake_report() -> dict:
    if IS_WIN:
        skip("fake Windows runs only outside Windows")
    if "r" not in _CACHE:
        out = tempfile.mkdtemp(prefix="oxmgf_")
        env = dict(os.environ, FAKE_HW="gaming", FAKE_TARGET=os.path.join(SCRIPTS, "mining_fake.py"),
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fake_windows.py"), "--out", out], cwd=ROOT,
                           env=env, capture_output=True, timeout=600)
        text = (p.stdout + p.stderr).decode("utf-8", "replace")
        path = os.path.join(out, "roundtrip.json")
        assert p.returncode == 0 and os.path.exists(path), tail(text)
        with open(path, encoding="utf-8") as f:
            _CACHE["r"] = json.load(f)
    return _CACHE["r"]


def test_discovery_skips_redistributables_and_installers():
    r = fake_report()
    assert r["games"] == ["Half-Life 2", "Old Game", "Test Game"], "Steamworks Redistributables is not a game"
    assert r["exes"] == ["arm/glarm.exe:gl:", "bin/glview.exe:gl:x64", "bin/win64/game.exe:dx11:x64",
                         "bin32/gl32.exe:gl:x86", "launcher.exe:other:x64"], "a library path with [] must be found"
    assert r["old_api"] == ["dx9"]
    assert r["source_api"] == ["dx9"], "Source engine: hl2.exe in the root, shaderapidx9.dll in bin\\"


def test_games_go_to_the_mining_card_but_not_dx9_or_users_choice():
    r = fake_report()
    assert r["pref_after"] == {"dx11": "GpuPreference=2;", "gl": "GpuPreference=2;", "gl32": "GpuPreference=2;",
                               "launcher": "GpuPreference=1;", "dx9": None, "hl2": None}
    assert r["assign1"] == {"assigned": 4, "already": 0, "kept": 1, "dx9": 2}
    assert r["assign2"] == {"assigned": 0, "already": 4, "kept": 1, "dx9": 2}, "a second run changes nothing"
    assert r["status"]["on"] == 4 and r["status"]["kept"] == 1 and r["status"]["gl"] == 3
    assert r["status"]["gl_na"] == 1, "an ARM64 OpenGL exe has no Mesa"


def test_one_change_at_a_time():
    r = fake_report()
    assert r["busy"] == {"busy": True}, "while another mining change runs, assign must not touch the journal"
    assert r["parallel"] == ["busy", "ran"]


def test_mesa_archive_and_installed_files_are_verified():
    r = fake_report()
    assert r["tampered"] == "rejected" and r["mesa_after_bad"] is None
    assert r["dotdot"] == "rejected" and r["root_alive"], "a version of '..' must never wipe ProgramData\\OptimaX"
    lib = ["dxil.dll", "libgallium_wgl.dll", "opengl32.dll"]
    assert r["mesa"] == {"version": "26.2.0", "arch": {"x64": lib, "x86": lib}}
    assert r["bench_mesa"], "the GPU test must use the installed Mesa on a mining card"
    assert r["planted"] == "26.2.0", "a planted 'newer' Mesa without matching hashes must be ignored"
    assert r["tampered_installed"] is None, "a library changed after unpacking — the whole version is distrusted"


def test_mesa_matches_the_exe_bitness_and_keeps_the_games_own_file():
    r = fake_report()
    assert r["targets"] == ["bin32:x86", "bin:x64"]
    e = r["enable"]
    assert e["opengl32"] == "mesa x64 opengl32.dll" and e["opengl32_x86"] == "mesa x86 opengl32.dll"
    assert not e["arm"] and e["ok"] == 3 and e["env"] == "NVIDIA" and e["bak"] and e["dxil"] and e["status"]
    assert r["rescue"] == {"lines": 3, "ps": 3, "hash": True, "bak": 1}, r["rescue"]
    d = r["disable"]
    assert d == {"opengl32": "the game's own opengl32", "bak": False, "gallium": False, "x86": False, "env": None,
                 "ids": []}


def test_revert_all_leaves_files_the_game_replaced():
    r = fake_report()["revert"]
    assert r["undone"] == 6 and r["partial"] == 0 and r["left"] == []
    assert r["gallium"] == "updated by the game" and r["noted"], "a file the game updated must not be deleted"
    assert r["opengl32"] == "updated opengl32 by the game" and not r["bak_left"], "no orphaned .optimax-bak"
    assert not r["dxil"]
    assert r["pref"] == {"dx11": "GpuPreference=2;", "gl": None, "gl32": None, "launcher": "GpuPreference=1;"}
    assert r["env"] is None


def test_dxvk_puts_source_games_on_the_card():
    r = fake_report()
    assert r["dxvk_on"] == {"ok": 2, "d3d9": "dxvk x64 d3d9", "pref": "GpuPreference=2;", "status": True,
                            "targets": 1}, r["dxvk_on"]
    assert r["dxvk_off"] == {"d3d9": False, "pref": None, "ids": []}, "disabling DXVK removes its d3d9.dll and the exe"


def test_my_games_takes_over_an_assigned_exe():
    r = fake_report()
    assert r["handover"] == {"mine": True, "gpu": False, "pref": "GpuPreference=2;"}
    assert r["revert"]["pref"]["dx11"] == "GpuPreference=2;", "Revert all must not remove what My games set"
    assert r["handover_off"] is None, "turning it off in My games returns the original (no value)"


# ── GPU-тест ──
def test_mesa_scores_are_not_compared_with_native_ones():
    import gpubench as GB
    nv = "NVIDIA P106-100"
    base = dict(kind="own", preset="1080p", mode="bench", gpu=nv, rev=GB.BENCH_REV)
    cfg = {"bench": [dict(base, score=4000, avg=40.0)]}
    r = GB.save_result(cfg, dict(base, score=9000, avg=90.0, mesa=True))
    assert "delta" not in r
    r = GB.save_result(cfg, dict(base, score=9450, avg=94.5, mesa=True))
    assert r.get("delta") == 5.0


def test_load_mesa_is_a_noop_without_mesa():
    import gpubench as GB
    assert GB.load_mesa("") is False
    assert GB.load_mesa(_tmp()) is False


def test_verified_files_checks_every_library():
    import hashlib
    d = _tmp()
    os.makedirs(os.path.join(d, "x64"))
    data = {"opengl32.dll": b"a", "libgallium_wgl.dll": b"b"}
    for n, b in data.items():
        with open(os.path.join(d, "x64", n), "wb") as f:
            f.write(b)
    with open(os.path.join(d, "x64", "dxil.dll"), "wb") as f:  # не в маніфесті — не вантажимо
        f.write(b"unlisted")
    man = {"files": {f"x64/{n}": hashlib.sha256(b).hexdigest() for n, b in data.items()}}
    with open(os.path.join(d, "mesa.json"), "w") as f:
        json.dump(man, f)
    got = MG.verified_files(d, "x64")
    assert sorted(got) == ["libgallium_wgl.dll", "opengl32.dll"]
    assert MG.verified_files(d, "x86") == {}
    with open(os.path.join(d, "x64", "opengl32.dll"), "ab") as f:
        f.write(b"!")
    assert MG.verified_files(d, "x64") == {}
