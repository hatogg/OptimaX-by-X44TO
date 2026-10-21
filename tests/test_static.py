"""Перевірки файлів без запуску програми: синтаксис, кодування скриптів збірки, повнота списків модулів."""
import glob
import os
import re

from _util import ROOT

APP_MODULES = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(ROOT, "*.py"))
                     if os.path.basename(p) not in ("buildinfo.py",))


def read(rel: str) -> bytes:
    with open(os.path.join(ROOT, rel), "rb") as f:
        return f.read()


def test_python_compiles():
    files = glob.glob(os.path.join(ROOT, "*.py")) + glob.glob(os.path.join(ROOT, "packaging", "*.py")) + \
        glob.glob(os.path.join(ROOT, "tests", "**", "*.py"), recursive=True)
    for p in files:
        with open(p, encoding="utf-8") as f:
            compile(f.read(), p, "exec")  # без запису .pyc


def test_batch_files_ascii_crlf():
    for rel in ("build.bat", "build_installer.bat"):
        b = read(rel)
        b.decode("ascii")  # cmd.exe читає .bat у кодовій сторінці OEM — лише ASCII
        assert b.count(b"\n") == b.count(b"\r\n"), f"{rel}: LF without CR"
        assert b"if not defined CI pause" in b, f"{rel}: pause would hang CI"


def test_rescue_launcher_crlf_utf8():
    b = read(os.path.join("packaging", "OptimaX-Rescue.cmd"))
    b.decode("utf-8")
    assert not b.startswith(b"\xef\xbb\xbf"), "BOM breaks the first cmd.exe line"
    assert b.count(b"\n") == b.count(b"\r\n")
    assert b"chcp 65001" in b.split(b"\r\n")[4] or b"chcp 65001" in b[:400]


def test_installer_script():
    b = read(os.path.join("packaging", "OptimaX.iss"))
    assert b.startswith(b"\xef\xbb\xbf"), "Inno Setup reads non-ASCII .iss correctly only with a BOM"
    s = b.decode("utf-8-sig")
    assert s.count("\n") == s.count("\r\n")
    for msg in re.findall(r"\{cm:(\w+)", s):
        if msg in ("CreateDesktopIcon", "AdditionalIcons", "LaunchProgram"):
            continue  # стандартні повідомлення Inno Setup
        for lang in ("uk", "ru", "en"):
            assert re.search(rf"^{lang}\.{msg}=", s, re.M), f"{lang}.{msg} missing in [CustomMessages]"
    assert 'Source: "OptimaX-Rescue.cmd"' in s


def _for_list(bat: str, marker: str) -> set:
    m = re.search(r"for %%[FM] in \(([^)]*" + re.escape(marker) + r"[^)]*)\)", bat)
    assert m, marker
    return set(m.group(1).split())


def test_build_scripts_list_every_module():
    """Новий модуль, забутий у скриптах збірки, — найчастіша причина «у мене не запускається exe»."""
    for rel in ("build.bat", "build_installer.bat"):
        bat = read(rel).decode("ascii")
        files = {f[:-3] for f in _for_list(bat, "optimizer.py")}
        hidden = _for_list(bat, "PyQt6.QtNetwork")
        missing = [m for m in APP_MODULES if m not in files]
        assert not missing, f"{rel}: not in the file check: {missing}"
        lazy = [m for m in APP_MODULES if m.startswith("lang_") or m in ("selftest", "rescue", "abtest", "smart_ui",
                                                                         "sharecard", "gpubench", "adblock")]
        assert not [m for m in lazy if m not in hidden], f"{rel}: hidden imports: {[m for m in lazy if m not in hidden]}"
        assert "buildinfo" in hidden


def test_version_everywhere():
    eng = read("engine.py").decode("utf-8")
    v = re.search(r'^VERSION = "([^"]+)"', eng, re.M).group(1)
    vi = read("version_info.txt").decode("utf-8")
    quad = ".".join((re.findall(r"\d+", v) + ["0"] * 4)[:4])
    assert f"'FileVersion', '{quad}'" in vi, "run: python packaging/release.py version-info"
    iss = read(os.path.join("packaging", "OptimaX.iss")).decode("utf-8-sig")
    assert f'#define MyAppVersion "{v}"' in iss


def test_workflows_reference_existing_files():
    for wf in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
        s = open(wf, encoding="utf-8").read()
        for rel in re.findall(r"(tests/[\w/.-]+\.(?:py|ps1)|build(?:_installer)?\.bat|packaging/[\w.-]+\.py)", s):
            assert os.path.exists(os.path.join(ROOT, rel)), f"{os.path.basename(wf)}: {rel} not found"


def test_powershell_scripts_encoding():
    """Windows PowerShell 5.1 читає UTF-8 без BOM як ANSI — кирилиця перетворюється на сміття."""
    for p in glob.glob(os.path.join(ROOT, "**", "*.ps1"), recursive=True):
        b = open(p, "rb").read()
        try:
            b.decode("ascii")
        except UnicodeDecodeError:
            assert b.startswith(b"\xef\xbb\xbf"), f"{os.path.relpath(p, ROOT)}: non-ASCII PowerShell script needs a UTF-8 BOM"
