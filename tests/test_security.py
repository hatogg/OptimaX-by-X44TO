"""Захищені папки, журнал відкату й задачі планувальника (6.7): OptimaX працює з правами адміністратора, тож
те, що вона читає й запускає, не може лежати там, куди пише звичайна програма користувача."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, SCRIPTS, skip, tail

sys.path.insert(0, ROOT)
_CACHE = {}


def report() -> dict:
    if IS_WIN:
        skip("fake Windows runs only outside Windows")
    if "r" not in _CACHE:
        out = tempfile.mkdtemp(prefix="oxsec_")
        env = dict(os.environ, FAKE_HW="gaming", FAKE_TARGET=os.path.join(SCRIPTS, "security_fake.py"),
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fake_windows.py"), "--out", out], cwd=ROOT,
                           env=env, capture_output=True, timeout=600)
        text = (p.stdout + p.stderr).decode("utf-8", "replace")
        path = os.path.join(out, "roundtrip.json")
        assert p.returncode == 0 and os.path.exists(path), tail(text)
        with open(path, encoding="utf-8") as f:
            _CACHE["r"] = json.load(f)
    return _CACHE["r"]


# ───────────── на фальшивій Windows ─────────────
def test_admin_files_live_in_protected_programdata():
    p = report()["paths"]
    assert p == {"journal": True, "tools": True, "updates": True, "rescue": True, "marker": True, "problem": ""}, p


def test_planted_link_is_moved_aside_not_followed():
    assert report()["planted"] == {"is_dir_now": True, "moved": True, "target_untouched": True}


def test_portable_copy_gets_no_elevated_tasks():
    r = report()
    assert r["trusted"] is False
    assert r["autostart"] is False and r["schedule"] is False
    assert r["creates"] == [], "no schtasks /Create for a copy outside Program Files"
    assert r["dns"].startswith("This copy of OptimaX is outside Program Files") or "Program Files" in r["dns"]
    assert r["untrusted_msg"]


def test_audit_removes_old_tasks_for_untrusted_exe():
    a = report()["audit"]
    assert sorted(a["gone"]) == ["OptimaX", "OptimaX DNS"]
    assert a["deleted"] == ["OptimaX"], "the task on Program Files stays; DNS goes through its own disable()"
    assert a["dns_off"] is True


def test_presentmon_only_with_recorded_hash():
    assert report()["presentmon"] == {"picked_good": True, "after_tamper": None}


def test_planted_journal_record_is_refused():
    r = report()
    assert r["bad_undo"] == "refused"
    assert len(r["bad_rescue"]) == 1 and r["bad_rescue"][0].startswith("rem ")


# ───────────── у цьому процесі ─────────────
GOOD = [
    {"t": "reg", "p": r"HKLM\SOFTWARE\X", "n": "V", "old": None},
    {"t": "reg", "p": r"HKCU\Software\X", "n": "", "old": [4, 1]},
    {"t": "svc", "n": "SysMain", "old": "auto"},
    {"t": "svc", "n": "MSSQL$SQLEXPRESS", "old": "delayed-auto"},
    {"t": "task", "n": r"\Microsoft\Windows\Application Experience\ProgramDataUpdater"},
    {"t": "cmd", "c": "powercfg -h on"},
    {"t": "ps", "c": "Set-MpPreference -DisableRealtimeMonitoring $false"},
    {"t": "pw", "g": "381b4222-f694-41f0-9685-ff5bb260df2e", "s": "SUB_PCIEXPRESS", "st": "ASPM", "old": 1, "m": "ac"},
    {"t": "pw", "g": "381b4222-f694-41f0-9685-ff5bb260df2e", "s": "SUB_PCIEXPRESS", "st": "ASPM", "old": None},
    {"t": "live", "k": "explorer"},
    {"t": "file", "p": os.path.abspath("game/d3d9.dll"), "sha": "a" * 64,
     "bak": os.path.abspath("game/d3d9.dll") + ".optimax-bak"},
]
BAD = [
    {"t": "evil", "c": "calc"},
    {"t": "reg", "p": r"SOFTWARE\X", "n": "V", "old": None},
    {"t": "svc", "n": "x & calc", "old": "auto"},
    {"t": "svc", "n": "SysMain", "old": "auto & calc"},
    {"t": "task", "n": 'x" & calc & "'},
    {"t": "pw", "g": "x & calc", "s": "a", "st": "b", "old": 1},
    {"t": "pw", "g": "a", "s": "b", "st": "c", "old": "1 & calc"},
    {"t": "live", "k": "calc"},
    {"t": "file", "p": "relative.dll", "sha": "", "bak": None},
    {"t": "file", "p": os.path.abspath("a.dll"), "sha": "", "bak": r"C:\Windows\System32\x.dll"},
    "not a dict",
]


def test_valid_undo_records():
    import engine as E
    assert [r for r in GOOD if not E.valid_undo(r)] == []
    assert [r for r in BAD if E.valid_undo(r)] == []


def test_invalid_record_is_never_run():
    import engine as E
    for rec in BAD[:3]:
        try:
            E._undo_record(rec, lambda *_: None)
        except ValueError:
            continue
        raise AssertionError(f"{rec} was accepted")


def test_journal_migration_moves_and_filters():
    import engine as E
    d = tempfile.mkdtemp(prefix="oxmig_")
    old, new = os.path.join(d, "old", "back.json"), os.path.join(d, "new", "back.json")
    os.makedirs(os.path.dirname(old))
    data = {"applied": {"a": {"ts": 1, "undo": [GOOD[0], GOOD[2]]},
                        "b": {"ts": 2, "undo": [GOOD[5], BAD[2]]}}}
    with open(old, "w", encoding="utf-8") as f:
        json.dump(data, f)
    with open(old[:-5] + ".pending.json", "w", encoding="utf-8") as f:
        json.dump({"tid": "c", "undo": [GOOD[3], BAD[4]]}, f)
    E._migrate_journal(old, new)
    j = E.Journal(new)
    assert j.get("a")["undo"] == [GOOD[0], GOOD[2]]
    assert j.get("b")["undo"] == [GOOD[5]] and j.get("b")["partial"] is True
    assert j.data.get("migrated_dropped") == ["b"]
    assert j.interrupted()["undo"] == [GOOD[3]]
    assert not os.path.exists(old) and any(n.startswith("back.json.moved-") for n in os.listdir(os.path.dirname(old)))
    E._migrate_journal(old, new)  # повторний запуск нічого не ламає
    assert E.Journal(new).count() == 2


def test_write_never_follows_a_planted_tmp_link():
    import engine as E
    if not hasattr(os, "symlink"):
        skip("no symlinks")
    d = tempfile.mkdtemp(prefix="oxtmp_")
    victim = os.path.join(d, "victim.txt")
    with open(victim, "w") as f:
        f.write("keep")
    path = os.path.join(d, "back.json")
    os.symlink(victim, path + ".tmp")
    E._write_atomic(path, {"applied": {}}, durable=False)
    assert open(victim).read() == "keep"
    assert json.load(open(path)) == {"applied": {}}


def test_secfs_helpers_outside_windows():
    import secfs as SF
    assert SF.sysexe("schtasks") == "schtasks" and SF.sysexe(r"C:\x\y.exe") == r"C:\x\y.exe"
    assert SF.is_under("/a/b/c", "/a/b") and SF.is_under("/a/b", "/a/b") and not SF.is_under("/a/bc", "/a/b")
    assert SF.self_trusted() is True and SF.system_target("/anything") is False
    d = tempfile.mkdtemp(prefix="oxsd_")
    assert SF.secure_dir(os.path.join(d, "x", "y")) == os.path.join(d, "x", "y") and os.path.isdir(os.path.join(d, "x", "y"))


def test_presentmon_hash_cache_notices_changes():
    import fpstest as FT
    d = tempfile.mkdtemp(prefix="oxpm_")
    p = os.path.join(d, "PresentMon-2.3.0-x64.exe")
    with open(p, "wb") as f:
        f.write(b"MZ" + b"\0" * 100)
    sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
    FT._write_manifest(d, os.path.basename(p), sha)
    assert FT._read_manifest(d) == {"name": os.path.basename(p), "sha256": sha}
    assert FT._verified(p, sha)
    with open(p, "ab") as f:
        f.write(b"x")
    assert not FT._verified(p, sha)
    with open(os.path.join(d, FT.MANIFEST), "w") as f:
        json.dump({"name": "..\\evil.exe", "sha256": sha}, f)
    assert FT._read_manifest(d) == {}


def test_vbs_off_is_never_preselected():
    import engine as E
    import features as F
    t = E.BY_ID["disable_vbs"]
    assert t.p == "" and t.risky == "security"
    assert "disable_vbs" not in F.FPS
