"""Аварійний відкат: генерація OptimaX-Rescue.cmd, пакети змін, синхронізація done.txt, перевірка збою (демо)."""
import _boot
import base64
import os
import re
import sys
import time

sys.argv = _boot.argv("--lang=uk")
import engine as E  # noqa: E402
import features as F  # noqa: E402
import rescue as RS  # noqa: E402

j = E.JOURNAL
now = int(time.time())
GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"
j.data["applied"] = {
    "old_one": {"ts": now - 7200, "undo": [{"t": "svc", "n": "SysMain", "old": "auto"}], "title": "Стара зміна"},
    "ultimate_power": {"ts": now - 30, "undo": [
        {"t": "cmd", "c": f"powercfg -setactive {GUID}"},
        {"t": "pw", "g": GUID, "s": "SUB_PROCESSOR", "st": "CPMINCORES", "old": 10, "m": "ac"}]},
    "ads_tips": {"ts": now - 20, "title": "Без реклами & порад <у> меню 100%", "undo": [
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Dw", "old": [4, 4294967295]},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "New", "old": None},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "", "old": [1, "default"]},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Path", "old": [1, "C:\\Games\\"]},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Exp", "old": [2, '%SystemRoot%\\x "q"']},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Bin", "old": [3, {"hex": "00ff10"}]},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Multi", "old": [7, ["a", "b c"]]},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Q", "old": [11, 5]},
        {"t": "task", "n": r"\Microsoft\Windows\Feedback\Siuf\DmClient"},
        {"t": "ps", "c": "Set-MpPreference -DisableRealtimeMonitoring $false"},
        {"t": "live", "k": "explorer"}]},
}
s = RS.build_script(j)
batches = RS.batches(j)
lines = s.split("\r\n")
calls = re.findall(r"call :(x\d+)", s)
labels = re.findall(r"^:(x\d+)\r?$", s, re.M)
b64 = re.search(r"-EncodedCommand (\S+)", s)
reg_lines = [ln for ln in lines if ln.startswith("reg ")]
p = RS.write_rescue(j)
raw = open(p, "rb").read()
with open(os.path.join(RS.rescue_dir(), "done.txt"), "w") as f:
    f.write("ads_tips\nultimate_power\nads_tips\n")
synced = RS.sync(j)
left_after_sync = sorted(j.data["applied"])
j.data["applied"]["timer_resolution"] = {"ts": int(time.time()), "undo": [{"t": "reg", "p": "HKLM\\X", "n": "Y",
                                                                           "old": None}]}
RS.record_batch({"old_one"}, "apply")
batch = F.CFG["safety"]["ids"]
no_crash = RS.check()
F.CFG["demo_crash"] = True
crash = RS.check()
RS.dismiss()
after_dismiss = RS.check()
m0 = os.path.getmtime(p)
time.sleep(1.1)
j.put("new_x", [{"t": "reg", "p": "HKLM\\A", "n": "B", "old": None}])
_boot.result(lone_lf=s.count("\n") - s.count("\r\n"), bom=raw.startswith(b"\xef\xbb\xbf"), calls=calls, labels=labels,
             batches=batches, reg_lines=reg_lines, ps=base64.b64decode(b64.group(1)).decode("utf-16-le")
             if b64 else None, unattended=['if /i "%~1"=="/all" goto all' in s, 'if /i "%~1"=="/last" goto last' in s],
             synced=synced, left_after_sync=left_after_sync, batch=batch, no_crash=no_crash,
             crash=crash and {"ids": crash["ids"], "kinds": crash["kinds"]}, after_dismiss=after_dismiss,
             regenerated=os.path.getmtime(p) > m0, empty=RS.build_script(E.Journal(p + ".none")))
