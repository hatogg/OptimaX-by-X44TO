"""Довірені шляхи й дані (6.17). OptimaX працює з правами адміністратора, а settings.json, HKCU\\Environment, PATH
користувача, %LOCALAPPDATA% і %TEMP% може змінити будь-яка програма користувача. Тому:

• оновлення: адреса, ім'я й сума файлу — лише з даних релізу, щойно отриманих з GitHub, а не з settings.json;
  ім'я — за шаблоном (без «..%5C»), адреса — лише github.com/<репо>/releases/download/;
• зібрана програма не бере репозиторій оновлень зі змінної середовища OPTIMAX_UPDATE_REPO;
• перевірка підпису не пропускає файл, видавця якого не вдалося прочитати;
• winget.exe і cdb.exe — лише з Program Files/Windows, не з PATH і не з %LOCALAPPDATA%.

Справжні команди й мережа тут не використовуються: engine.ps, мережеві функції й перевірки secfs підмінені."""
import hashlib
import os
import sys
import tempfile
import urllib.error

from _util import ROOT

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "engine" not in sys.modules:  # окремий запуск цього файла: режим перегляду й чиста папка налаштувань
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
import secfs as SF  # noqa: E402
import updater as U  # noqa: E402
import verify as V  # noqa: E402
import apps as A  # noqa: E402
import dumpanalyzer as DA  # noqa: E402
from test_undo_guarantees import patched  # noqa: E402

REPO = U._trusted_repo()
BASE = f"https://github.com/{REPO}/releases/download/v99.0/"
SETUP = "OptimaX-Setup-99.0.exe"
SHA = "a" * 64


def _raises(fn, key):
    try:
        fn()
    except V.VerifyError as e:
        assert e.key == key, (e.key, key)
        return
    raise AssertionError(f"expected VerifyError {key}")


def _touch(*parts) -> str:
    p = os.path.join(*parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"MZ")
    return p


# ───────────────────────── оновлення: ім'я й адреса ─────────────────────────
def test_traversal_names_are_rejected():
    for bad in ("..%5C..%5COptimaX-Setup-99.0.exe", "..%2F..%2FOptimaX-Setup-99.0.exe", "%2E%2E", "a%3A.exe"):
        assert not U.release_url(BASE + bad), bad
    assert not U.release_url(f"https://github.com/{REPO}/releases/download/../../x/{SETUP}")
    assert not U.release_url(BASE + SETUP, name="..\\" + SETUP), "the last URL segment must be the file name"
    for bad in ("..\\..\\OptimaX-Setup-99.0.exe", "OptimaX-Setup-99.0.exe\n", "x/OptimaX-Setup-99.0.exe",
                "OptimaX-99.0-portable.exe"):
        assert not U.asset_name_ok(bad, "setup"), bad
    assert U.asset_name_ok(SETUP, "setup") and U.asset_name_ok("OptimaX-99.0-portable.exe", "portable")
    assert U.asset_name_ok("OptimaX-Mesa-25.1.zip") and not U.asset_name_ok("..zip") \
        and not U.asset_name_ok("..\\x.zip") and not U.asset_name_ok("a/b.zip")


def test_foreign_hosts_are_rejected():
    assert U.release_url(BASE + SETUP, SETUP)
    assert U.release_url(BASE.upper().replace("HTTPS://GITHUB.COM", "https://github.com") + SETUP, SETUP), \
        "owner/repo on GitHub are case-insensitive"
    for bad in (f"https://evil.example/{REPO}/releases/download/v99.0/{SETUP}",
                f"http://github.com/{REPO}/releases/download/v99.0/{SETUP}",
                f"https://github.com.evil.example/{REPO}/releases/download/v99.0/{SETUP}",
                f"https://github.com/someone/else/releases/download/v99.0/{SETUP}",
                f"https://github.com/{REPO}/releases/download/v99.0/{SETUP}?x=1",
                f"file:///C:/Users/u/AppData/Local/Temp/{SETUP}", "", None):
        assert not U.release_url(bad, SETUP), bad
    assert U.release_page("C:\\Users\\u\\evil.exe") == f"https://github.com/{REPO}/releases/latest"
    assert U.release_page(f"https://github.com/{REPO}/releases/tag/v99.0").endswith("/tag/v99.0")


# ───────────────────────── оновлення: settings.json ─────────────────────────
def test_cached_exposes_only_display_data():
    poisoned = {"version": "99.0", "notes": "**hi**", "page": "C:\\Users\\u\\evil.exe", "kind": "setup",
                "url": "https://evil.example/..%5C..%5Cevil.exe", "name": "..\\..\\evil.exe", "sha256": SHA,
                "sums_url": "https://evil.example/SHA256SUMS.txt", "size": 1}
    c = U.cached({"latest": poisoned})
    assert set(c) == {"version", "notes", "page"}, c
    assert c["version"] == "99.0" and c["notes"] == "hi" and c["page"].startswith(f"https://github.com/{REPO}/")
    assert U.cached({"latest": {"version": "99.0"}}) == {"version": "99.0"}
    assert U.cached({"latest": {"version": E.VERSION}}) is None and U.cached({}) is None
    assert U.cached({"latest": {"version": ["99"]}}) is None and U.cached({"latest": {"version": "9\\..\\x"}}) is None


def _rel(url=BASE + SETUP, name=SETUP):
    return {"tag_name": "v99.0", "html_url": BASE, "body": "",
            "assets": [{"name": name, "browser_download_url": url, "size": 10, "digest": "sha256:" + SHA}]}


class _Net:
    """Підміна мережі: записує, що завантажувалося, і нічого не віддає (404)."""

    def __init__(self):
        self.urls, self.sums, self.checks = [], [], 0

    def open(self, url, timeout, accept=None):
        self.urls.append(url)
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)

    def text(self, url, limit=1 << 16):
        self.sums.append(url)
        raise OSError("offline")

    def check(self, rel):
        def fn(log=None):
            self.checks += 1
            return U.from_release(rel, True) if rel else None
        return fn


def _download(info, rel, tmp):
    """-> (ключ VerifyError або назва винятку, _Net)."""
    net = _Net()
    with patched(E, IS_WIN=True, DRY_RUN=False), \
            patched(U, _FRESH={}, _open=net.open, fetch_text=net.text, check=net.check(rel),
                                         download_dir=lambda: tmp):
        try:
            U.download(info, lambda *_: None)
            return None, net
        except V.VerifyError as e:
            return e.key, net
        except urllib.error.HTTPError:
            return "404", net


def test_download_refetches_release_instead_of_trusting_settings():
    tmp = tempfile.mkdtemp(prefix="oxdl_")
    victim = _touch(os.path.dirname(tmp), "victim-" + os.path.basename(tmp) + ".exe")
    poisoned = {"version": "99.0", "kind": "setup", "url": "https://evil.example/..%5C" + os.path.basename(victim),
                "name": "..\\" + os.path.basename(victim), "sha256": SHA, "sums_url": "https://evil.example/s.txt"}
    # дані з settings.json (і навіть повний словник із kind) не використовуються: реліз береться з GitHub заново
    err, net = _download(poisoned, _rel(), tmp)
    assert err == "404" and net.checks == 1, (err, net.checks)
    assert net.urls == [BASE + SETUP] and net.sums == [BASE + "SHA256SUMS.txt"], (net.urls, net.sums)
    assert os.path.exists(victim), "nothing outside the download folder may be removed"
    # дані з cached() (без адреси) — так само
    err, net = _download(U.cached({"latest": poisoned}), _rel(), tmp)
    assert err == "404" and net.checks == 1 and BASE + SETUP in net.urls, (err, net.urls)
    # на GitHub новішої версії немає — нічого не завантажуємо
    err, net = _download(poisoned, None, tmp)
    assert err == "vf.no_hash" and net.urls == [], (err, net.urls)


def test_download_rejects_bad_release_data():
    tmp = tempfile.mkdtemp(prefix="oxdl_")
    for url, name in ((BASE + "..%5C..%5C" + SETUP, SETUP),                   # вихід із папки через %5C
                      (f"https://evil.example/{REPO}/releases/download/v99.0/{SETUP}", SETUP),  # чужий сервер
                      (f"https://github.com/someone/else/releases/download/v99.0/{SETUP}", SETUP)):
        err, net = _download({"version": "99.0", "kind": "setup"}, _rel(url, name), tmp)
        assert err == "vf.no_hash" and net.urls == [], (url, err, net.urls)
    # інші файли релізу (архів шару mining.py): ім'я без папок, адреса — з релізу нашого репозиторію
    for info in ({"name": "..\\..\\x.zip", "url": BASE + "..%5C..%5Cx.zip", "sha256": SHA},
                 {"name": "x.zip", "url": "https://evil.example/x.zip", "sha256": SHA}):
        err, net = _download(info, None, tmp)
        assert err == "vf.no_hash" and net.urls == [], (info, err, net.urls)
    err, net = _download({"name": "OptimaX-Mesa-25.1.zip", "url": BASE + "OptimaX-Mesa-25.1.zip", "sha256": SHA,
                          "sums_url": "https://evil.example/SHA256SUMS.txt"}, None, tmp)
    assert err == "404" and net.urls == [BASE + "OptimaX-Mesa-25.1.zip"], (err, net.urls)
    assert net.sums == [BASE + "SHA256SUMS.txt"], "a foreign SHA256SUMS.txt is replaced by the one of the release"


def test_launch_runs_silently_only_an_installer_name():
    calls = []
    p = _touch(tempfile.mkdtemp(prefix="oxl_"), "OptimaX-99.0-portable.exe")
    sha = hashlib.sha256(b"MZ").hexdigest()
    had = hasattr(os, "startfile")
    old = getattr(os, "startfile", None)
    os.startfile = lambda d: calls.append(("open", d))  # поза Windows os.startfile немає
    try:
        with patched(E, IS_WIN=True, DRY_RUN=False), patched(U, _VERIFIED={p: sha}), \
                patched(V, own_publisher=lambda: ""), patched(U.subprocess, Popen=lambda *a, **k: calls.append(a)):
            assert U.launch(p, "setup"), U.LAST_ERROR
    finally:
        if had:
            os.startfile = old
        else:
            del os.startfile
    assert calls == [("open", os.path.dirname(p))], calls


# ───────────────────────── репозиторій оновлень ─────────────────────────
def test_frozen_build_ignores_update_repo_env():
    old_env = os.environ.get("OPTIMAX_UPDATE_REPO")
    had = hasattr(sys, "frozen")
    old_frozen = getattr(sys, "frozen", None)
    os.environ["OPTIMAX_UPDATE_REPO"] = "evil/repo"
    try:
        with patched(U, _BUILT_REPO="hatogg/OptimaX-by-X44TO"):
            sys.frozen = True
            assert U._configured_repo() == "hatogg/OptimaX-by-X44TO"
            del sys.frozen
            assert U._configured_repo() == "evil/repo", "the env var stays for running from source"
            os.environ["OPTIMAX_UPDATE_REPO"] = "a/.."
            assert U._configured_repo() == "hatogg/OptimaX-by-X44TO", "a malformed repo is ignored"
        with patched(U, _BUILT_REPO=""):
            sys.frozen = True
            assert U._configured_repo() == ""
    finally:
        if had:
            sys.frozen = old_frozen
        elif hasattr(sys, "frozen"):
            del sys.frozen
        if old_env is None:
            os.environ.pop("OPTIMAX_UPDATE_REPO", None)
        else:
            os.environ["OPTIMAX_UPDATE_REPO"] = old_env


# ───────────────────────── підпис ─────────────────────────
def test_verify_fails_closed_on_unknown_signer():
    p = _touch(tempfile.mkdtemp(prefix="oxv_"), "OptimaX-Setup-99.0.exe")
    sha = V.sha256(p)
    who = {p: "", "self": ""}

    def signer(path):
        return who[p] if path == p else who["self"]
    with patched(V, signature=lambda path: {"status": "valid", "code": 0}, signer=signer):
        _raises(lambda: V.check_file(p, sha, publisher="CN=X44TO"), "vf.sig_other")  # видавця не прочитано
        _raises(lambda: V.check_file(p, sha, publisher="*"), "vf.sig_other")
        who[p] = "CN=Someone Else"
        _raises(lambda: V.check_file(p, sha, publisher="*"), "vf.sig_other")  # «*» — не «будь-хто»
        _raises(lambda: V.check_file(p, sha, publisher="CN=X44TO"), "vf.sig_other")
        who[p] = 'CN="X44TO", O=X44TO'
        assert V.check_file(p, sha, publisher="CN=X44TO")["signer"] == who[p]
        assert V.check_file(p, sha, publisher="")["signer"] == "", "unsigned builds require no signature"
        had = hasattr(sys, "frozen")
        sys.frozen = True
        try:
            with patched(E, IS_WIN=True):
                _raises(lambda: V.check_file(p, sha, publisher="*"), "vf.sig_other")  # власного підпису OptimaX не прочитано
                who["self"] = "CN=X44TO"
                assert V.check_file(p, sha, publisher="*")["signature"] == "valid"  # той самий видавець
        finally:
            if not had:
                del sys.frozen


# ───────────────────────── winget і cdb ─────────────────────────
def _fs():
    root = tempfile.mkdtemp(prefix="oxtp_")
    pf = os.path.join(root, "Program Files")
    user = os.path.join(root, "Users", "u", "AppData", "Local", "Microsoft", "WindowsApps")
    return root, pf, user


def _trust(pf, owner=True):
    return dict(trusted_location=lambda p: SF.is_under(os.path.realpath(p), pf), trusted_owner=lambda p: owner)


def test_winget_only_from_trusted_package_folder():
    _root, pf, user = _fs()
    alias = _touch(user, "winget.exe")
    old_pkg = os.path.join(pf, "WindowsApps", "Microsoft.DesktopAppInstaller_1.9.2_x64__8wekyb3d8bbwe")
    new_pkg = os.path.join(pf, "WindowsApps", "Microsoft.DesktopAppInstaller_1.24.25200.0_x64__8wekyb3d8bbwe")
    _touch(old_pkg, "winget.exe")
    real = _touch(new_pkg, "winget.exe")
    out = {"text": ""}
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = user + os.pathsep + old_path  # псевдонім у PATH — не використовується
    try:
        with patched(E, IS_WIN=True, ps=lambda script, timeout=30, log=None, ro=False: (0, out["text"])), \
                patched(SF, program_files_dirs=lambda: [], **_trust(pf)):
            A._WINGET.clear()
            assert A.winget_path() is None, "the user-writable alias in PATH is not used"
            out["text"] = user + "\n"
            A._WINGET.clear()
            assert A.winget_path() is None, "a package location outside Program Files is rejected"
            out["text"] = f"{user}\n{new_pkg}\n"
            A._WINGET.clear()
            assert A.winget_path() == real
            with patched(SF, trusted_owner=lambda p: False):
                A._WINGET.clear()
                assert A.winget_path() is None, "a file owned by a normal user is rejected"
            out["text"] = ""
            with patched(SF, program_files_dirs=lambda: [pf]):
                A._WINGET.clear()
                assert A.winget_path() == real, "newest package version from Program Files\\WindowsApps"
        assert os.path.isfile(alias)
    finally:
        os.environ["PATH"] = old_path
        A._WINGET.clear()
    assert A.winget_path() == "winget", "demo mode outside Windows is unchanged"


def test_cdb_only_from_trusted_locations():
    root, pf, user = _fs()
    pf86 = os.path.join(root, "Program Files (x86)")
    app = os.path.join(root, "Users", "u", "Downloads")  # портативна OptimaX
    _touch(app, "tools", "cdb", "cdb.exe")
    on_path = _touch(user, "cdb.exe")
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = user + os.pathsep + old_path
    try:
        trust = dict(trusted_location=lambda p: SF.is_under(os.path.realpath(p), pf)
                     or SF.is_under(os.path.realpath(p), pf86), trusted_owner=lambda p: True)
        with patched(E, IS_WIN=True), patched(SF, **trust), patched(DA, _app_dir=lambda: app,
                                                                   _pf_dirs=lambda: (pf86, pf)):
            assert DA.find_cdb() == "", "neither the copy next to a portable exe nor PATH is used"
            kits = _touch(pf86, "Windows Kits", "10", "Debuggers", "x64", "cdb.exe")
            assert DA.find_cdb() == kits
            with patched(SF, trusted_owner=lambda p: False):
                assert DA.find_cdb() == ""
        assert os.path.isfile(on_path)
    finally:
        os.environ["PATH"] = old_path
    assert "Debuggers" in DA.cdb_candidates()[3]


def test_symbol_cache_is_in_protected_folder():
    with patched(E, admin_dir=lambda sub, users_read=True: os.path.join("C:\\ProgramData\\OptimaX", sub)):
        sp = DA.sympath()
    assert sp.startswith("srv*C:\\ProgramData\\OptimaX") and sp.endswith(DA.SYMBOLS_URL), sp
    assert tempfile.gettempdir() not in sp
