"""OptimaX 6.17: виправлення з незалежного аудиту — ядро відкату. Перенесення старого журналу лише з командами
каталогу, одна зміна системи за раз, запис відкату до зміни, повторне застосування після часткового відкату,
заблокований (а не зіпсований) журнал, чесний результат дій."""
import contextlib
import json
import os
import sys
import tempfile
import threading
import time

from _util import ROOT

sys.path.insert(0, ROOT)
import engine as E  # noqa: E402


@contextlib.contextmanager
def patched(**kw):
    old = {k: getattr(E, k) for k in kw}
    for k, v in kw.items():
        setattr(E, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(E, k, v)


# ───────────────────────── перенесення старого журналу (%APPDATA%) ─────────────────────────
def test_only_catalog_commands_survive_migration():
    good_cmd = next(op[2] for t in E.TWEAKS for op in t.ops if op[0] == "cmd" and op[2])
    assert E.migratable_undo({"t": "cmd", "c": good_cmd})
    assert E.migratable_undo({"t": "cmd", "c": "powercfg -setactive 381b4222-f694-41f0-9685-ff5bb260df2e"})
    assert E.migratable_undo({"t": "ps", "c": "Set-MpPreference -ScanAvgCPULoadFactor 50 -EnableLowCpuPriority "
                                              "$false -ScanOnlyIfIdleEnabled $true"})
    assert E.migratable_undo({"t": "reg", "p": r"HKCU\Software\X", "n": "Y", "old": None})
    for evil in ("net user evil P@ss /add", "powercfg -setactive x & calc.exe",
                 "Add-LocalGroupMember Administrators evil", "powercfg -h on & whoami"):
        assert not E.migratable_undo({"t": "cmd", "c": evil}), evil
        assert not E.migratable_undo({"t": "ps", "c": evil}), evil
    # файловий запис без контрольної суми видаляв би будь-який файл від імені адміністратора
    assert not E.migratable_undo({"t": "file", "p": r"C:\Games\x\dxgi.dll", "sha": ""})
    assert E.migratable_undo({"t": "file", "p": r"C:\Games\x\dxgi.dll", "sha": "a" * 64})


def test_migration_drops_planted_records_and_marks_the_entry():
    d = tempfile.mkdtemp(prefix="oxmig_")
    old, new = os.path.join(d, "old", "back.json"), os.path.join(d, "new", "back.json")
    os.makedirs(os.path.dirname(old))
    os.makedirs(os.path.dirname(new))
    good = {"t": "reg", "p": r"HKCU\Software\X", "n": "Y", "old": [4, 1]}
    with open(old, "w", encoding="utf-8") as f:
        json.dump({"applied": {"t1": {"ts": 1, "undo": [good, {"t": "cmd", "c": "net user evil x /add"}]}}}, f)
    E._migrate_journal(old, new)
    with open(new, encoding="utf-8") as f:
        data = json.load(f)
    assert data["applied"]["t1"]["undo"] == [good] and data["applied"]["t1"]["partial"]
    assert data["migrated_dropped"] == ["t1"]
    assert not os.path.exists(old), "the old user-writable journal must not be read again"


# ───────────────────────── одна зміна системи за раз ─────────────────────────
def test_changes_and_rollbacks_never_run_at_the_same_time():
    for fn in (E.apply_tweaks, E.undo_ids, E.undo_one, E.undo_or_default, E.recover_interrupted, E.repair_legacy):
        assert getattr(fn, "__wrapped__", None) is not None, fn.__name__
    inside, peak = [0], [0]

    def slow(*_a, **_k):
        inside[0] += 1
        peak[0] = max(peak[0], inside[0])
        time.sleep(0.05)
        inside[0] -= 1
        return {"ok": 1}
    wrapped = E._serial(slow)
    th = [threading.Thread(target=wrapped) for _ in range(4)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    assert peak[0] == 1


# ───────────────────────── запис відкату — до зміни ─────────────────────────
def _cmd_op(rc):
    ctx = E.Ctx(lambda *_: None)
    seen = []

    def fake_run(cmd, timeout=30, log=None, **k):
        seen.append((list(ctx.undo), k.get("stoppable")))
        return rc, ""
    with patched(run=fake_run):
        E.exec_op(("cmd", "bcdedit /set x yes", "bcdedit /deletevalue x", 30), ctx)
    return ctx, seen


def test_command_undo_is_written_before_the_command_runs():
    ctx, seen = _cmd_op(0)
    assert seen[0][0] == [{"t": "cmd", "c": "bcdedit /deletevalue x"}], "the undo must be in the WAL first"
    assert seen[0][1] is False, "a command that changes the system is never cut in half by Stop"
    assert list(ctx.undo) == [{"t": "cmd", "c": "bcdedit /deletevalue x"}]


def test_refused_command_leaves_no_undo_but_a_timeout_keeps_it():
    ctx, _ = _cmd_op(1)
    assert list(ctx.undo) == [] and ctx.failed
    ctx, _ = _cmd_op(E.TIMEOUT_RC)
    assert list(ctx.undo) == [{"t": "cmd", "c": "bcdedit /deletevalue x"}], "a timeout may have changed half"


def test_timeout_is_not_treated_as_already_removed():
    def fake_run(cmd, timeout=30, log=None, **k):
        return E.TIMEOUT_RC, "[TIMEOUT]"
    with patched(run=fake_run, DRY_RUN=False):
        try:
            E._undo_record({"t": "cmd", "c": "reg delete HKCU\\X /v Y /f"}, lambda *_: None)
            raised = False
        except RuntimeError:
            raised = True
    assert raised


# ───────────────────────── журнал ─────────────────────────
def _journal():
    return E.Journal(os.path.join(tempfile.mkdtemp(prefix="oxj_"), "back.json"))


def test_reapply_after_partial_rollback_records_the_lost_steps():
    j = _journal()
    a = {"t": "reg", "p": r"HKCU\A", "n": "1", "old": None}
    b = {"t": "reg", "p": r"HKCU\B", "n": "2", "old": None}
    j.put("x", [a, b])
    j.replace_undo("x", [b])  # A повернули, B — ні
    j.put("x", [dict(a, old=[4, 9]), dict(b, old=[4, 7])])  # застосували знову
    undo = j.get("x")["undo"]
    assert undo[0] == b, "the first snapshot of B (its original value) stays"
    assert undo[1]["n"] == "1", "the step changed again must get its record back"
    j2 = _journal()
    j2.put("y", [a])
    j2.put("y", [dict(a, old=[4, 1])])
    assert j2.get("y")["undo"] == [a], "a normal re-apply keeps the very first snapshot"


def test_a_locked_journal_is_not_quarantined_or_overwritten():
    j = _journal()
    j.put("x", [{"t": "reg", "p": r"HKCU\A", "n": "1", "old": None}])
    real = E.Journal._read

    def locked(p):
        raise PermissionError(13, "being scanned")
    E.Journal._read = staticmethod(locked)
    try:
        j2 = E.Journal(j.path)
    finally:
        E.Journal._read = staticmethod(real)
    assert j2.unreadable and not j2.has("x")
    assert not [n for n in os.listdir(os.path.dirname(j.path)) if ".corrupt-" in n]
    try:
        j2.put("y", [])
        raised = False
    except E.JournalError:
        raised = True
    assert raised, "no change may be made while the real journal can't be read"
    assert E.Journal(j.path).has("x"), "the journal on disk stays as it was"


def test_failed_step_makes_an_action_partial():
    a = E.Action("t_partial", lambda ctx: ctx.fail("ren"), "fix")
    res = E.run_action(a, lambda *_: None)
    assert res.get("ok") is False and res.get("partial") == 1
