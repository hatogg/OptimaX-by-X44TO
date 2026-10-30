"""Надійний відкат (6.4): аварія посеред оптимізації, помилки, збій запису журналу, пошкоджений журнал,
конфлікти й права адміністратора — на фальшивій Windows (реєстр у пам'яті)."""
import json
import os
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, SCRIPTS, skip, tail

_CACHE = {}


def crash_report() -> dict:
    if IS_WIN:
        skip("fake Windows runs only outside Windows")
    if "r" not in _CACHE:
        out = tempfile.mkdtemp(prefix="oxjc_")
        env = dict(os.environ, FAKE_HW="gaming", FAKE_TARGET=os.path.join(SCRIPTS, "journal_crash.py"),
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fake_windows.py"), "--out", out], cwd=ROOT,
                           env=env, capture_output=True, timeout=600)
        text = (p.stdout + p.stderr).decode("utf-8", "replace")
        path = os.path.join(out, "roundtrip.json")
        assert p.returncode == 0 and os.path.exists(path), tail(text)
        with open(path, encoding="utf-8") as f:
            _CACHE["r"] = json.load(f)
    return _CACHE["r"]


def test_crash_mid_tweak_is_rolled_back_on_next_start():
    r = crash_report()
    assert r["crash1_raised"] and r["crash1_changed"], "the crash must hit after the first change"
    assert r["crash1_wal"] and not r["crash1_in_journal"], "the half-applied tweak lives only in the write-ahead log"
    assert r["crash1_recover"]["tweak"] == r["tweaks"][0] and r["crash1_recover"]["failed"] == 0
    assert r["crash1_restored"], "recovery must return every value the tweak had already changed"
    assert r["crash1_wal_gone"] and r["crash1_op_cleared"]


def test_crash_mid_batch_offers_the_rest_of_the_batch():
    r = crash_report()
    a, b = r["tweaks"][:2]
    assert r["crash2_recover"] == {"tweak": b, "op": "apply", "ids": [a]}, r["crash2_recover"]
    assert r["crash2_b_restored"] and r["crash2_all_restored"] and r["crash2_op_cleared"]


def test_error_mid_tweak_reverts_that_tweak_and_continues():
    r = crash_report()
    assert r["fail3"] == {"ok": 1, "fail": 1, "a_in_journal": False, "c_in_journal": True, "wal": False}, r["fail3"]
    assert r["fail3_a_restored"] and r["fail3_all_restored"]


def test_unwritable_journal_changes_nothing():
    r = crash_report()
    assert r["full4"] == {"error": "journal", "ok": 0, "unchanged": True, "journal": 0}, r["full4"]


def test_partial_rollback_keeps_failed_steps():
    r = crash_report()
    assert r["partial5"]["partial"] == 1 and r["partial5"]["undone"] == 0, r["partial5"]
    assert r["partial5"]["left"] == 1 and r["partial5"]["marked"]
    assert r["partial5_retry"] == {"undone": 1, "in_journal": False, "restored": True}, r["partial5_retry"]


def test_corrupt_journal_is_restored_from_backup():
    r = crash_report()
    assert r["corrupt6"] == {"problem": "restored", "has_a": True, "has_b": True, "quarantined": 1}, r["corrupt6"]
    assert r["corrupt6_lost"] == "lost"


def test_conflicting_tweaks_are_never_applied_together():
    r = crash_report()
    assert r["conflict7"] == {"dropped": ["cool_mode"], "turbo": True, "cool": False}, r["conflict7"]
    assert r["conflict7_applied"] == {"dropped": ["cool_mode"], "cool": False}
    assert r["conflict_symmetric"]


def test_without_admin_rights_only_user_settings_change():
    r = crash_report()
    assert r["admin8"] == {"skipped": 1, "ok": 1, "a": False, "user": True, "a_unchanged": True}, r["admin8"]
    assert r["end_clean"], "every scenario must leave the system exactly as it was"


def test_baseline_snapshot_recovers_changes_when_the_journal_is_lost():
    r = crash_report()
    a, b = r["tweaks"][:2]
    assert r["baseline_from_journal"], "a snapshot taken after changes must use the journal's original values"
    assert r["baseline9"] == {"made": True, "orphans": sorted([a, b]), "covered": 0}, r["baseline9"]
    assert r["baseline9_restored"]


def test_overlapping_settings_are_declared_conflicts():
    """Два твіки, що ставлять одному параметру різні значення, мають бути позначені як конфліктні —
    інакше результат залежав би від порядку, а відкат одного повертав би проміжне значення."""
    sys.path.insert(0, ROOT)
    import engine as E
    writes = {}
    for t in E.TWEAKS:
        for op in t.ops:
            if op[0] == "reg" and not callable(op[3]):
                key, val = ("reg", op[1].lower(), op[2].lower()), str(op[3])
            elif op[0] == "regdel":
                key, val = ("reg", op[1].lower(), op[2].lower()), "<deleted>"
            elif op[0] == "pw":
                key, val = ("pw", op[1], op[2], op[4]), str(op[3])
            elif op[0] == "svc":
                key, val = ("svc", op[1].lower()), op[2]
            else:
                continue
            writes.setdefault(key, []).append((t.id, val))
    bad = []
    for key, items in writes.items():
        for i, (a, va) in enumerate(items):
            for b, vb in items[i + 1:]:
                if a != b and va != vb and b not in E.conflicts_of(a):
                    bad.append((key, a, b))
    assert not bad, bad
