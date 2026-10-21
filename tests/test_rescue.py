"""OptimaX-Rescue.cmd: правильний cmd-файл, екранування, пакети, синхронізація з програмою, банер після збою."""
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
    assert '%%SystemRoot%%' in regs and '\\"q\\"' in regs
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
