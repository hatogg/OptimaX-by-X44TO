"""«Відновити winget» (wingetfix.py): рішення за станом пакета й користувача, команди PowerShell, ім'я й адреса файлу
з релізу OptimaX, суми файлів, а також збірка OptimaX-WinGet-*.zip (packaging/release.py)."""
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import zipfile

from _util import ROOT

sys.path.insert(0, ROOT)
import engine as E  # noqa: E402
import wingetfix as W  # noqa: E402

ME = "S-1-5-21-1-2-3-1001"
OTHER = "S-1-5-21-1-2-3-500"


def _release():
    spec = importlib.util.spec_from_file_location("optimax_release", os.path.join(ROOT, "packaging", "release.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _state(**kw):
    raw = dict(me=ME, me_name="PC\\me", desk=[ME], desk_name=["PC\\me"], reg="", staged=False, prov=False,
               arch="X64")
    raw.update(kw)
    return W.parse_state(raw)


# ── рішення ──
def test_decisions():
    assert W.decide(_state(reg="1.29.380.0"), 22631, "v1.29.380") == "ok"
    assert W.decide(_state(reg="1.29.380.0"), 22631, "") == "register"  # зареєстрований, але winget не запускається
    assert W.decide(_state(prov=True), 19045, "") == "register"  # підготовлений, не зареєстрований
    assert W.decide(_state(staged=True), 19045, "") == "register"  # встановлений іншому користувачу
    assert W.decide(_state(), 17763, "") == "install"  # немає зовсім (LTSC / Server)
    assert W.decide(_state(prov=True, desk=[OTHER]), 22631, "") == "other_user"
    assert W.decide(_state(desk=[OTHER]), 22631, "") == "other_user"  # і завантаження теж — не тому користувачу
    assert W.decide(_state(prov=True, desk=[]), 22631, "") == "register"  # власника робочого столу не видно
    assert W.decide(_state(prov=True), 17134, "") == "unsupported"  # Windows 10 1803
    assert W.decide(_state(), 14393, "v1.0") == "unsupported"
    assert W.decide(None, 22631, "") == "unknown"
    assert W.decide(None, 22631, "v1.29.380") == "ok"


def test_parse_state_treats_output_as_data():
    assert W.parse_state(None) is None
    assert W.parse_state({"me": "'; rm -rf /"}) is None
    s = W.parse_state({"me": ME, "desk": ME, "reg": "1.2.3.4; evil", "arch": "Arm64", "desk_name": "PC\\me"})
    assert s["desk"] == [ME] and s["reg"] == "" and s["arch"] == "arm64" and s["desk_name"] == ["PC\\me"]
    s = W.parse_state({"me": ME, "desk": [OTHER, "not-a-sid"], "reg": "1.29.380.0", "arch": "AMD64"})
    assert s["desk"] == [OTHER] and s["reg"] == "1.29.380.0" and s["arch"] == "x64"
    assert not W.same_user(s)


# ── команди ──
def test_register_command():
    cmd = W.register_script()
    assert "Add-AppxPackage -RegisterByFamilyName -MainPackage 'Microsoft.DesktopAppInstaller_8wekyb3d8bbwe'" in cmd
    assert "-ErrorAction Stop" in cmd and "exit 1" in cmd


def test_install_command_is_quoted():
    cmd = W.install_script("C:\\ProgramData\\OptimaX\\winget\\1.0\\O'x\u2019.msixbundle",
                           ["C:\\a\\x64\\Microsoft.VCLibs_14.0_x64.appx", "C:\\a\\x64\\b';calc;'.appx"])
    assert "-Path 'C:\\ProgramData\\OptimaX\\winget\\1.0\\O''x\u2019\u2019.msixbundle'" in cmd
    assert "-DependencyPath @('C:\\a\\x64\\Microsoft.VCLibs_14.0_x64.appx','C:\\a\\x64\\b'';calc;''.appx')" in cmd
    assert "-DependencyPath" not in W.install_script("C:\\b.msixbundle", [])


def test_powershell_runs_encoded(monkeypatch):
    seen = []
    monkeypatch.setattr(E, "IS_WIN", True)
    monkeypatch.setattr(E, "DRY_RUN", False)
    monkeypatch.setattr(E, "run", lambda cmd, *a, **k: seen.append(cmd) or (0, "OK"))
    E.ps(W.register_script(), 180, None, stoppable=False)
    cmd = seen[0]
    assert "-EncodedCommand" in cmd and not any("Add-AppxPackage" in str(x) for x in cmd)
    import base64
    assert W.register_script() in base64.b64decode(cmd[cmd.index("-EncodedCommand") + 1]).decode("utf-16-le")


def _fake_windows(monkeypatch, ps_answers):
    """Справжня Windows без Windows: PowerShell — заглушка, журнал — тимчасовий файл (не журнал користувача),
    apply_tweaks -> справжній run_tweak (запис відкату до команди, discard лише при точній відмові)."""
    calls = []
    jr = E.Journal(os.path.join(tempfile.mkdtemp(prefix="oxwgj_"), "back.json"))
    monkeypatch.setattr(E, "IS_WIN", True)
    monkeypatch.setattr(E, "DRY_RUN", False)
    monkeypatch.setattr(E, "is_admin", lambda: True)
    monkeypatch.setattr(E, "win_build", lambda: 19045)
    monkeypatch.setattr(W.time, "sleep", lambda *_: None)
    answers = iter(ps_answers)

    def ps(script, *a, **k):
        calls.append((script, k))
        return next(answers)

    def apply(items, log, header=True):
        r = E.run_tweak(items[0], E.Ctx(log, journal=jr))
        return {"ok": int(r is True), "partial": int(r == "partial"), "fail": int(r is False)}
    monkeypatch.setattr(E, "ps", ps)
    monkeypatch.setattr(E, "apply_tweaks", apply)
    return calls, jr


def test_register_goes_through_the_journal(monkeypatch):
    calls, jr = _fake_windows(monkeypatch, [(0, "OK")])
    vers = iter(["", "v1.29.380"])
    monkeypatch.setattr(W, "winget_version", lambda: next(vers))
    monkeypatch.setattr(W, "read_state", lambda: _state(prov=True))
    res = W.register(lambda *_: None)
    assert res["ok"] and res["version"] == "v1.29.380", res
    assert calls == [(W.register_script(), {"stoppable": False})]
    assert jr.get(W.TWEAK_ID)["undo"] == [{"t": "ps", "c": W.undo_user_script(ME)}]
    assert f"-User $s" in W.undo_user_script(ME) and f"'{ME}'" in W.undo_user_script(ME)


def test_register_failures_are_honest(monkeypatch):
    # команда точно відмовила — запису відкату немає, результат — помилка
    calls, jr = _fake_windows(monkeypatch, [(1, "Deployment failed with HRESULT: 0x80073CF3")])
    monkeypatch.setattr(W, "winget_version", lambda: "")
    monkeypatch.setattr(W, "read_state", lambda: _state(prov=True))
    assert W.register(lambda *_: None).get("error") and jr.get(W.TWEAK_ID) is None
    # тайм-аут — невідомо, чи зареєстровано: запис відкату лишається
    calls, jr = _fake_windows(monkeypatch, [(E.TIMEOUT_RC, "[TIMEOUT]")])
    assert W.register(lambda *_: None).get("error") and jr.get(W.TWEAK_ID)["undo"]
    # зареєстровано, але winget так і не знайшовся
    calls, jr = _fake_windows(monkeypatch, [(0, "OK")])
    assert W.register(lambda *_: None).get("error")
    # інший користувач — нічого не запускаємо, чесна відмова
    calls, jr = _fake_windows(monkeypatch, [])
    monkeypatch.setattr(W, "read_state", lambda: _state(prov=True, desk=[OTHER], desk_name=["PC\\other"]))
    res = W.register(lambda *_: None)
    assert res.get("error") and "PC\\other" in res["error"] and not calls
    # пакета немає — крок 1 не підходить; стара Windows — відмова
    monkeypatch.setattr(W, "read_state", lambda: _state())
    assert W.register(lambda *_: None).get("need_install")
    monkeypatch.setattr(E, "win_build", lambda: 17134)
    assert W.register(lambda *_: None).get("decision") == "unsupported" and not calls


def test_repair_of_registered_package_is_not_journaled(monkeypatch):
    calls, jr = _fake_windows(monkeypatch, [(0, "OK")])
    vers = iter(["", "v1.29.380"])
    monkeypatch.setattr(W, "winget_version", lambda: next(vers))
    monkeypatch.setattr(W, "read_state", lambda: _state(reg="1.29.380.0"))
    assert W.register(lambda *_: None)["ok"]
    assert len(calls) == 1 and jr.get(W.TWEAK_ID) is None


def test_install_journals_removes_files_and_keeps_frameworks(monkeypatch):
    import updater as U
    calls, jr = _fake_windows(monkeypatch, [(0, "OK")])
    vers = iter(["", "v1.29.380"])
    monkeypatch.setattr(W, "winget_version", lambda: next(vers))
    monkeypatch.setattr(W, "read_state", lambda: _state())
    root = tempfile.mkdtemp(prefix="oxwgi_")
    monkeypatch.setattr(W, "root_dir", lambda: root)
    z = os.path.join(tempfile.mkdtemp(prefix="oxwgz_"), "OptimaX-WinGet-1.29.380.zip")
    _zip(z, {W.BUNDLE: b"bundle", "x64/Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_x64.appx": b"vc",
             "arm64/Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_arm64.appx": b"vca"})
    monkeypatch.setattr(W, "find_asset", lambda log=None: {"name": os.path.basename(z), "size": 5})
    monkeypatch.setattr(U, "download", lambda *a, **k: z)
    res = W.install(lambda *_: None)
    assert res["ok"], res
    script = calls[0][0]
    assert "-Path" in script and "x64" in script and "arm64" not in script
    assert jr.get(W.TWEAK_ID)["undo"] == [{"t": "ps", "c": W.undo_all_script()}]
    assert "VCLibs" not in W.undo_all_script() and "UI.Xaml" not in W.undo_all_script()  # фреймворки лишаються
    assert os.listdir(root) == [] and not os.path.exists(z)  # ні розпакованих ~300 МБ, ні архіву


def test_undo_is_expressible_in_rescue():
    import rescue as RS
    for code in (W.undo_all_script(), W.undo_user_script(ME)):
        rec = {"t": "ps", "c": code}
        assert E.valid_undo(rec)
        lines = RS.undo_lines(rec)
        assert len(lines) == 1 and "-EncodedCommand" in lines[0] and "Remove-AppxPackage" not in lines[0]


def test_demo_needs_no_windows(monkeypatch):
    monkeypatch.setattr(E, "IS_WIN", False)  # демо — і на справжній Windows (CI): правило CLAUDE.md
    monkeypatch.setattr(E, "DRY_RUN", True)
    assert W.diagnose()["decision"] == "ok"
    assert W.register(lambda *_: None)["ok"]


# ── файл із релізу OptimaX ──
def _rels(name, url, digest="sha256:" + "a" * 64):
    return json.dumps([{"draft": True, "assets": [{"name": name, "browser_download_url": url}]},
                       {"assets": [{"name": name, "browser_download_url": url, "size": 5, "digest": digest}]}])


def test_find_asset_only_from_own_release(monkeypatch):
    import updater as U
    repo = "hatogg/OptimaX-by-X44TO"
    monkeypatch.setattr(U, "UPDATE_REPO", repo)
    good = f"https://github.com/{repo}/releases/download/v7.2/OptimaX-WinGet-1.29.380.zip"
    monkeypatch.setattr(U, "fetch_text", lambda *a, **k: _rels("OptimaX-WinGet-1.29.380.zip", good))
    a = W.find_asset()
    assert a["url"] == good and a["sha256"] == "a" * 64 and a["version"] == "1.29.380"
    import pytest
    for name, url in (("OptimaX-WinGet-1.29.380.zip", "https://evil.example/OptimaX-WinGet-1.29.380.zip"),
                      ("OptimaX-WinGet-1.29.380.zip", f"https://github.com/other/repo/releases/download/v1/"
                                                      "OptimaX-WinGet-1.29.380.zip"),
                      ("OptimaX-WinGet-1.29.380.zip", good.replace("OptimaX-WinGet", "x/..%2FOptimaX-WinGet")),
                      ("winget.zip", good.replace("OptimaX-WinGet-1.29.380.zip", "winget.zip")),
                      ("OptimaX-WinGet-..zip", good.replace("1.29.380.zip", ".zip"))):
        monkeypatch.setattr(U, "fetch_text", lambda *a, n=name, u=url, **k: _rels(n, u))
        with pytest.raises(RuntimeError):
            W.find_asset()
    assert W.ASSET_RE.match("OptimaX-WinGet-1.29.380.zip")
    assert not W.ASSET_RE.match("OptimaX-WinGet-1.29.380.zip.exe")


def _zip(path, files, man_files=None):
    sums = {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
    sums.update(man_files or {})
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("winget.json", json.dumps({"winget": "1.29.380", "files": sums}))
        for k, v in files.items():
            z.writestr(k, v)


def test_unpack_checks_every_sum(monkeypatch):
    root = tempfile.mkdtemp(prefix="oxwg_")
    monkeypatch.setattr(W, "root_dir", lambda: root)
    p = os.path.join(root, "a.zip")
    files = {W.BUNDLE: b"bundle", "x64/Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_x64.appx": b"vc",
             "arm64/Microsoft.UI.Xaml.2.8_8.2310.30001.0_arm64.appx": b"xaml"}
    _zip(p, dict(files, **{"../evil.appx": b"x", "x64/run.exe": b"x"}))
    folder = W.unpack(p, lambda *_: None, "x64")
    assert sorted(os.listdir(folder)) == sorted([W.BUNDLE, "x64", "winget.json"])  # лише потрібна архітектура
    got = W.verified_files(folder, "x64")
    assert got["bundle"].endswith(W.BUNDLE) and [os.path.basename(x) for x in got["deps"]] == [
        "Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_x64.appx"]
    assert W.verified_files(folder, "x86")["deps"] == []
    with open(os.path.join(folder, "x64", "Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_x64.appx"), "wb") as f:
        f.write(b"swapped")
    assert W.verified_files(folder, "x64") == {}  # підмінили після розпакування — не встановлюємо
    arm = W.unpack(p, lambda *_: None, "arm64")
    assert len(W.verified_files(arm, "arm64")["deps"]) == 1 and not os.path.exists(os.path.join(arm, "x64"))
    bad = os.path.join(root, "b.zip")
    _zip(bad, {W.BUNDLE: b"bundle"}, {W.BUNDLE: "0" * 64})
    import pytest
    with pytest.raises(RuntimeError):
        W.unpack(bad, lambda *_: None, "x64")
    assert not os.path.exists(os.path.join(root, "1.29.380.part"))


# ── збірка релізу ──
def test_release_digest_and_pins():
    import pytest
    REL = _release()
    sha = "0" * 64
    with pytest.raises(SystemExit):
        REL._check_digest(REL.WINGET_REPO, "v9.9/" + REL.WINGET_BUNDLE, None, sha)
    with pytest.raises(SystemExit):
        REL._check_digest(REL.WINGET_REPO, "v9.9/" + REL.WINGET_BUNDLE, "sha256:" + "1" * 64, sha)
    REL._check_digest(REL.WINGET_REPO, "v9.9/" + REL.WINGET_BUNDLE, "sha256:" + sha, sha)
    with pytest.raises(SystemExit):  # закріплена версія з іншим вмістом
        REL._check_digest(REL.WINGET_REPO, "v1.29.380/" + REL.WINGET_BUNDLE, "sha256:" + sha, sha)
    assert REL.WINGET_BUNDLE == W.BUNDLE and REL.WINGET_ARCHES == W.ARCHES


def test_release_picks_dependencies():
    REL = _release()
    deps = REL.winget_dependencies(json.dumps({"Dependencies": [
        {"Name": "Microsoft.VCLibs.140.00.UWPDesktop", "Version": "14.0.33728.0"},
        {"Name": "Microsoft.UI.Xaml.2.8", "Version": "8.2310.30001.0"}, {"Name": "bad name; x"}]}))
    assert deps == ["Microsoft.UI.Xaml.2.8", "Microsoft.VCLibs.140.00.UWPDesktop"]
    got = REL.winget_dep_files(["x64/Microsoft.UI.Xaml.2.8_8.2310.30001.0_x64.appx",
                                "Deps/ARM64/Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_arm64.appx",
                                "x64/../x64/evil.appx", "x64/readme.txt", "arm/x.appx", "top.appx"])
    xaml = "x64/Microsoft.UI.Xaml.2.8_8.2310.30001.0_x64.appx"
    assert got == {xaml: xaml,
                   "arm64/Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_arm64.appx":
                       "Deps/ARM64/Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_arm64.appx"}
    for k in got:  # усе, що кладе збірка, клієнт приймає
        assert W.DEP_RE.match(k), k


def test_release_builds_zip_the_client_accepts(monkeypatch):
    """build_winget на підробленому релізі (без мережі): digest, сума з .txt, залежності -> zip, який unpack приймає."""
    REL = _release()
    bundle = b"msixbundle"
    deps = io.BytesIO()
    with zipfile.ZipFile(deps, "w") as z:
        z.writestr("x64/Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_x64.appx", b"vc64")
        z.writestr("x64/Microsoft.UI.Xaml.2.8_8.2310.30001.0_x64.appx", b"xaml64")
        z.writestr("x86/Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_x86.appx", b"vc86")  # без UI.Xaml
    blobs = {REL.WINGET_BUNDLE: bundle, REL.WINGET_DEPS_ZIP: deps.getvalue(),
             REL.WINGET_DEPS_JSON: json.dumps({"Dependencies": [{"Name": "Microsoft.VCLibs.140.00.UWPDesktop"},
                                                                {"Name": "Microsoft.UI.Xaml.2.8"}]}).encode(),
             REL.WINGET_BUNDLE_SUM: hashlib.sha256(bundle).hexdigest().upper().encode()}
    rel = {"tag_name": "v9.9.1", "assets": [
        {"name": n, "browser_download_url": "mem://" + n, "digest": "sha256:" + hashlib.sha256(b).hexdigest()}
        for n, b in blobs.items()]}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.close()

    monkeypatch.setattr(REL, "_get", lambda url, api=False: R(json.dumps(rel).encode() if api else
                                                               blobs[url[len("mem://"):]]))
    out = REL.build_winget(tempfile.mkdtemp(prefix="oxwgb_"))
    assert os.path.basename(out) == "OptimaX-WinGet-9.9.1.zip" and W.ASSET_RE.match(os.path.basename(out))
    root = tempfile.mkdtemp(prefix="oxwgc_")
    monkeypatch.setattr(W, "root_dir", lambda: root)
    folder = W.unpack(out, lambda *_: None, "x64")
    assert len(W.verified_files(folder, "x64")["deps"]) == 2
    folder = W.unpack(out, lambda *_: None, "x86")
    assert W.verified_files(folder, "x86")["deps"] == []  # неповний набір для x86 не кладемо
    # сума bundle не збіглася з файлом .txt від Microsoft — збірка падає
    blobs[REL.WINGET_BUNDLE_SUM] = b"0" * 64
    import pytest
    with pytest.raises(SystemExit):
        REL.build_winget(tempfile.mkdtemp(prefix="oxwgb_"))
