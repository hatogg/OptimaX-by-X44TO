"""Захищені папки й задачі планувальника (6.7) на фальшивій Windows.

Запуск: FAKE_TARGET=tests/scripts/security_fake.py python tests/scripts/fake_windows.py --out DIR
Фальшива Windows: права адміністратора, ProgramData і APPDATA — тимчасові папки, exe (python) лежить поза Program
Files, тобто це «портативна» копія, якій задачі з правами адміністратора не дозволені."""
import hashlib
import json
import os
import sys

import engine as E
import features as F
import fpstest as FT
import guard as G
import rescue as RS
import secfs as SF
import updater as U

R = {}
log_lines = []
log = log_lines.append
PD = os.environ["ProgramData"]

# 1. Журнал, PresentMon, оновлення й Rescue — у %ProgramData%\OptimaX, а не в %APPDATA%
R["paths"] = {
    "journal": E.JOURNAL_PATH.startswith(os.path.join(PD, "OptimaX", "state")),
    "tools": FT.tools_dir().startswith(os.path.join(PD, "OptimaX")),
    "updates": U.download_dir().startswith(os.path.join(PD, "OptimaX")),
    "rescue": RS.rescue_dir().startswith(os.path.join(PD, "OptimaX")),
    "marker": os.path.exists(os.path.join(PD, "OptimaX", "state", SF.MARK)),
    "problem": E.JOURNAL_PROBLEM,
}

# 2. Посилання, підкинуте замість нашої папки, відкладається вбік, а не використовується
target = os.path.join(PD, "elsewhere")
os.makedirs(target)
link = os.path.join(SF.data_root(), "planted")
os.symlink(target, link)
SF.secure_dir(link)
R["planted"] = {"is_dir_now": os.path.isdir(link) and not os.path.islink(link),
                "moved": any(n.startswith("planted.untrusted-") for n in os.listdir(SF.data_root())),
                "target_untouched": os.listdir(target) == []}

# 3. Портативна копія: задачі з правами адміністратора не створюються
CALLS = []
real_run = E.run


def rec_run(cmd, *a, **k):
    CALLS.append(cmd if isinstance(cmd, list) else [cmd])
    return real_run(cmd, *a, **k)


E.run = rec_run
R["trusted"] = SF.self_trusted()
R["autostart"] = F.set_autostart(True, log)
R["schedule"] = G.set_schedule(True, 2, 3, log)
F.CFG["trial"] = None
G.start_trial([], log)
RS.record_batch(set(), log=log)
R["creates"] = [c for c in CALLS if "/Create" in c]
try:
    import adblock as AB
    AB.Backend(F.CFG).enable(log)
    R["dns"] = "started"
except Exception as e:  # noqa: BLE001
    R["dns"] = str(e)[:60]
R["untrusted_msg"] = any(E.tr("e.task_untrusted")[:40] in x for x in log_lines)

# 4. Аудит задач: задача старої версії, що запускає exe поза Program Files, прибирається; задача на Program Files — ні
XML = {"OptimaX": r"C:\Users\me\Downloads\OptimaX-6.6-portable.exe",
       "OptimaX Maintenance": r"C:\Program Files\OptimaX\OptimaX.exe",
       "OptimaX DNS": r"C:\Users\me\Downloads\OptimaX-6.6-portable.exe"}
DELETED, DNS_OFF = [], []


def audit_run(cmd, *a, **k):
    if isinstance(cmd, list) and "/Query" in cmd and "/XML" in cmd:
        name = cmd[cmd.index("/TN") + 1]
        if name in XML:
            return 0, f"<Task><Actions><Exec><Command>&quot;{XML[name]}&quot;</Command></Exec></Actions></Task>"
        return 1, "ERROR"
    if isinstance(cmd, list) and "/Delete" in cmd:
        DELETED.append(cmd[cmd.index("/TN") + 1])
    return 0, ""


E.run = audit_run
SF.trusted_location = lambda p: p.lower().startswith("c:\\program files")
AB.Backend.disable = lambda self, lg, progress=None: DNS_OFF.append(True) or {"ok": True}
R["audit"] = {"gone": F.audit_tasks(log), "deleted": DELETED, "dns_off": bool(DNS_OFF)}
E.run = real_run

# 5. PresentMon: лише файл із записаною сумою в захищеній папці; підкинутий «новіший» поруч не береться,
#    змінений після завантаження — теж
d = FT.tools_dir()
good = os.path.join(d, "PresentMon-2.3.0-x64.exe")
with open(good, "wb") as f:
    f.write(b"MZ" + os.urandom(2000))
FT._write_manifest(d, os.path.basename(good), hashlib.sha256(open(good, "rb").read()).hexdigest())
with open(os.path.join(d, "PresentMon-99.0.0-x64.exe"), "wb") as f:
    f.write(b"MZ-decoy")
first = FT.find_presentmon()
with open(good, "ab") as f:
    f.write(b"tampered")
R["presentmon"] = {"picked_good": first == good, "after_tamper": FT.find_presentmon()}

# 6. Підкинутий запис у журналі не виконується й не потрапляє в Rescue як команда
bad = {"t": "svc", "n": "x & calc", "old": "auto"}
try:
    E._undo_record(bad, log)
    R["bad_undo"] = "ran"
except ValueError:
    R["bad_undo"] = "refused"
R["bad_rescue"] = RS.undo_lines(bad)

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "roundtrip.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
