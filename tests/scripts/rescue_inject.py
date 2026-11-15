"""OptimaX-Rescue.cmd (6.17): невдалий крок не пише done.txt; id з & і % екрановано, а sync() усе одно його знаходить;
рядкові значення реєстру з лапками чи CR/LF — лише в base64 PowerShell; схема живлення активується лише якщо активна."""
import _boot
import base64
import os
import re
import sys
import time

sys.argv = _boot.argv("--lang=uk")
import engine as E  # noqa: E402
import rescue as RS  # noqa: E402

j = E.JOURNAL
now = int(time.time())
GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"
AMP = "msi:PCI\\VEN_10DE&DEV_1C03 (x) 100%^ !a!"  # & ( ) % ^ ! — усе, що cmd.exe розбирає в echo
QUOTED = 'odd"id & x'  # лапки echo дослівно не надрукує — такий id іде як b64:
EVIL_SZ = 'a" & whoami > C:\\pwn.txt & rem "'
EVIL_CRLF = "x\r\ncalc.exe"
EVIL_MULTI = ['ok', 'b" & calc.exe & "', "y\r\nnotepad.exe"]
j.data["applied"] = {
    AMP: {"ts": now - 50, "undo": [
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Sz", "old": [1, EVIL_SZ]},
        {"t": "reg", "p": r"HKLM\Software\Test", "n": "Exp", "old": [2, EVIL_CRLF]},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Multi", "old": [7, EVIL_MULTI]},
        {"t": "reg", "p": 'HKCU\\Software\\Te"st & calc', "n": "Gone", "old": None},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": 'N" & calc & "', "old": [4, 1]},
        {"t": "reg", "p": r"HKCU\Software\Test", "n": "Safe", "old": [1, "plain & (x) ^ 100%"]}]},
    QUOTED: {"ts": now - 40, "undo": [{"t": "svc", "n": "SysMain", "old": "auto"}]},
    "power": {"ts": now - 30, "undo": [
        {"t": "pw", "g": GUID, "s": "SUB_PROCESSOR", "st": "CPMINCORES", "old": 10, "m": "ac"}]},
    "badcmd": {"ts": now - 20, "undo": [{"t": "cmd", "c": "powercfg -h on\r\ncalc.exe"}]},
}
s = RS.build_script(j)
lines = s.split("\r\n")


def decode_ps(ln):
    return base64.b64decode(ln.split("-EncodedCommand ", 1)[1].split(" ", 1)[0]).decode("utf-16-le")


ps = [decode_ps(ln) for ln in lines if "-EncodedCommand " in ln]
inner = [base64.b64decode(b).decode("utf-8") for c in ps for b in re.findall(r"FromBase64String\('([^']*)'\)", c)]

# Блоки :xN — як їх виконає cmd.exe: steps — номери кроків, що «впадуть»; повертає, що потрапить у done.txt
blocks = {}
for i, ln in enumerate(lines):
    m = re.match(r":(x\d+)$", ln)
    if m:
        k = i + 1
        while lines[k] != "exit /b 0":
            k += 1
        blocks[m.group(1)] = lines[i + 1:k]


def run_block(body, failing=()):
    fail, xf, done, n = 0, None, [], 0
    for ln in body:
        if ln == "set XF=%FAIL%":
            xf = fail
        elif ln == "if not %FAIL%==%XF% exit /b 0":
            if fail != xf:
                return done
        elif ln.startswith('>>"%~dp0done.txt" echo '):
            done.append(ln.split(" echo ", 1)[1])
        elif ln.startswith("set /a FAIL+=1 & "):  # крок, який виконати не можна
            fail += 1
        elif "|| (set /a FAIL+=1 & " in ln:
            fail += n in failing
            n += 1
    return done


def echo_out(arg):
    """Що надрукує echo в .cmd без лапок: %% -> %, далі ^x -> x."""
    arg = arg.replace("%%", "%")
    return re.sub(r"\^(.)", r"\1", arg)


by_tid = {}
for tid in j.data["applied"]:
    for name, body in blocks.items():
        if any(ln.startswith('>>"%~dp0done.txt" echo ') and RS._unecho_id(ln.split(" echo ", 1)[1]) == tid
               for ln in body):
            by_tid[tid] = body
amp_body = by_tid[AMP]
steps = [ln for ln in amp_body if "|| (set /a FAIL+=1 & " in ln]
done_line = [ln for ln in amp_body if ln.startswith('>>"%~dp0done.txt" echo ')][0]
printed = echo_out(done_line.split(" echo ", 1)[1])

# sync(): один рядок — як надрукував cmd.exe, другий — як є в скрипті (екранований), третій — b64 з лапками
with open(os.path.join(RS.rescue_dir(), "done.txt"), "w", encoding="utf-8") as f:
    f.write(printed + "\n")
    f.write([ln for ln in by_tid["power"] if ln.startswith('>>"%~dp0done.txt"')][0].split(" echo ", 1)[1] + "\n")
    f.write([ln for ln in by_tid[QUOTED] if ln.startswith('>>"%~dp0done.txt"')][0].split(" echo ", 1)[1] + "\n")
synced = RS.sync(j)

pw = [ln for ln in by_tid["power"] if "setactive" in ln]
_boot.result(
    lone_lf=s.count("\n") - s.count("\r\n"), setlocal=lines[1], blocks=len(blocks),
    structure=all(b[0] == "set XF=%FAIL%" and b[-2] == "if not %FAIL%==%XF% exit /b 0"
                  and b[-1].startswith('>>"%~dp0done.txt" echo ') for b in blocks.values()),
    amp_ok=run_block(amp_body), amp_one_fails=[bool(run_block(amp_body, {i})) for i in range(len(steps))],
    steps=len(steps), done_line=done_line, printed=printed, amp=AMP,
    fail_note=[ln for ln in amp_body if "failed.txt" in ln][0],
    quoted_line=[ln for ln in by_tid[QUOTED] if ln.startswith('>>"%~dp0done.txt"')][0],
    synced=sorted(synced), left=sorted(j.data["applied"]),
    raw_evil=[x for x in ("whoami", "pwn.txt", "notepad", EVIL_SZ, EVIL_CRLF, *EVIL_MULTI, 'Te"st', 'N" &') if x in s],
    run_lines=[ln for ln in re.split(r"[\r\n\x1a]+", s) if re.match(r"\s*(calc|notepad|whoami)", ln, re.I)],
    reg_lines=[ln for ln in lines if ln.startswith("reg ")], ps=ps, inner=inner,
    evil_roundtrip=all(x in inner for x in (EVIL_SZ, EVIL_CRLF, *EVIL_MULTI, 'HKCU\\Software\\Te"st & calc'[5:])),
    pw=pw, bare_setactive=[ln for ln in lines if ln.startswith("powercfg -setactive")],
    badcmd=by_tid["badcmd"], badcmd_done=run_block(by_tid["badcmd"]),
    psq=RS._psq("Assassin\u2019s 'Creed'"))
