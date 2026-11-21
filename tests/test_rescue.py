"""OptimaX-Rescue.cmd: правильний cmd-файл, екранування, пакети, синхронізація з програмою, банер після збою."""
import re
from _util import IS_WIN, run_script, tail


def test_rescue_script():
    rc, out, r = run_script("rescue_check.py")
    assert rc == 0 and r, tail(out)
    assert r["lone_lf"] == 0 and not r["bom"], "cmd.exe needs CRLF and no BOM"
    assert r["calls"] and set(r["calls"]) <= set(r["labels"]), (r["calls"], r["labels"])
    assert r["batches"][0] == ["ads_tips", "ultimate_power"] or set(r["batches"][0]) == {"ads_tips", "ultimate_power"}
    regs = "\n".join(r["reg_lines"])
    assert 'reg add "HKCU\\Software\\Test" /v "Dw" /t REG_DWORD /d 4294967295 /f' in regs
    assert 'reg delete "HKCU\\Software\\Test" /v "New" /f' in regs
    assert '/ve /t REG_SZ /d "default"' in regs
    assert '/d "C:\\Games\\\\"' in regs, "trailing backslash must be doubled before the closing quote"
    # значення з лапками (%SystemRoot%\x "q") у reg add не потрапляє — лише base64 PowerShell (test нижче)
    assert '"q"' not in regs and '\\"q\\"' not in regs and '"Exp"' not in regs
    assert "/t REG_BINARY /d 00ff10" in regs and '/t REG_MULTI_SZ /d "a\\0b c"' in regs
    assert "/t REG_QWORD /d 5" in regs
    assert r["ps"] and "DisableRealtimeMonitoring" in r["ps"]
    assert r["unattended"] == [True, True]
    assert sorted(r["synced"]) == ["ads_tips", "ultimate_power"] and r["left_after_sync"] == ["old_one"]
    assert r["batch"] == ["timer_resolution"] and r["regenerated"]
    if not IS_WIN:  # на Windows події збоїв читаються зі справжнього журналу системи — демо-збою там немає
        assert r["no_crash"] is None and r["after_dismiss"] is None
        assert r["crash"] and r["crash"]["ids"] == ["timer_resolution"] and set(r["crash"]["kinds"]) == {"bsod", "power"}
    assert "exit /b 0" in r["empty"] and "call :x" not in r["empty"]


def test_rescue_failed_step_keeps_entry_and_no_injection():
    """6.17: невдалий крок не пише done.txt; id з & ( ) % ^ екрановано, а sync() знаходить точний id; рядкові
    значення реєстру з лапками, CR/LF — лише в base64 PowerShell; схема живлення активується, лише якщо вона активна."""
    rc, out, r = run_script("rescue_inject.py")
    assert rc == 0 and r, tail(out)
    assert r["lone_lf"] == 0, "cmd.exe needs CRLF"
    assert r["setlocal"] == "setlocal EnableExtensions DisableDelayedExpansion"
    # done.txt — лише якщо в записі не впав жоден крок
    assert r["blocks"] == 4 and r["structure"], "every :xN block: set XF=%FAIL% ... if not %FAIL%==%XF% exit /b 0"
    assert r["steps"] == 6 and r["amp_ok"] and r["amp_one_fails"] == [False] * 6, r["amp_one_fails"]
    assert r["badcmd_done"] == [] and any(x.startswith("set /a FAIL+=1 & ") for x in r["badcmd"]), r["badcmd"]
    assert not any(x.startswith(("powercfg -h on", "calc")) for x in r["badcmd"]), "multi-line cmd must not run"
    # id екрановано для echo (і в failed.txt), а sync() прибирає саме цей запис
    esc = "msi:PCI\\VEN_10DE^&DEV_1C03 ^(x^) 100%%^^ !a!"
    assert r["done_line"] == '>>"%~dp0done.txt" echo ' + esc, r["done_line"]
    assert r["printed"] == r["amp"]
    assert f"echo {esc}: " in r["fail_note"], r["fail_note"]
    assert r["quoted_line"].startswith('>>"%~dp0done.txt" echo b64:'), r["quoted_line"]
    assert sorted(r["synced"]) == sorted([r["amp"], 'odd"id & x', "power"]) and r["left"] == ["badcmd"]
    # шкідливі старі значення — ніде в тексті скрипта, лише в base64, і декодуються точно
    assert r["raw_evil"] == [] and r["run_lines"] == [], (r["raw_evil"], r["run_lines"])
    assert r["evil_roundtrip"] and len(r["ps"]) == 5
    assert all("$ErrorActionPreference='Stop'" in c and "Registry64" in c and "catch { exit 1 }" in c for c in r["ps"])
    assert any("RegistryValueKind]::MultiString" in c for c in r["ps"])
    assert any("RegistryValueKind]::ExpandString" in c and "RegistryHive]::LocalMachine" in c for c in r["ps"])
    assert any("DeleteValue($n,$false)" in c for c in r["ps"])
    assert len(r["reg_lines"]) == 1 and r["reg_lines"][0].startswith(
        'reg add "HKCU\\Software\\Test" /v "Safe" /t REG_SZ /d "plain & (x) ^ 100%%" /f'), r["reg_lines"]
    # схема живлення — лише якщо вона зараз активна (як engine._undo_record)
    g = "381b4222-f694-41f0-9685-ff5bb260df2e"
    assert r["bare_setactive"] == [] and len(r["pw"]) == 1
    # 7.1.1: find.exe — буквальним шляхом зі збірки скрипта, не з %SystemRoot% (його користувач може перевизначити)
    assert re.match(r'powercfg /getactivescheme 2>nul \| "[A-Za-z]:\\[^"%]*\\System32\\find\.exe" /i "'
                    + g + r'" >nul && \(powercfg -setactive ' + g + r' >nul 2>&1 \|\| \(set /a FAIL\+=1 & ',
                    r["pw"][0], re.I), r["pw"]  # GetSystemDirectory дає «system32»
    assert r["psq"] == "'Assassin’’s ''Creed'''", "PowerShell treats ’ as a quote too"
