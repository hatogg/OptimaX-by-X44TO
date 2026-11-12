"""Чесні результати й скасування (6.15). Справжні системні команди тут не виконуються: engine.run / engine.ps
підмінені, журнал — тимчасовий файл; єдиний справжній процес — сам Python (перевірка, що «Зупинити» його зупиняє).

• у кожної дії свій токен: зупинка однієї не чіпає іншу, а нова дія не скидає чужу зупинку (OX-018);
• «Зупинити» перериває й читання, і PowerShell (OX-019);
• твік, у якого не вдався крок, — «частково», а не «✓ готово» (OX-008);
• підсумок дії розрізняє успіх, частково, зупинку й помилку (OX-009);
• зупинка завантаження оновлення — не «файл не пройшов перевірку» (OX-017);
• undo_or_default повертає справжній результат (OX-028)."""
import os
import subprocess
import sys
import tempfile
import threading
import time

from _util import ROOT, has_qt, skip

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
from test_undo_guarantees import patched, temp_journal, runner  # noqa: E402


# ───────────────────────── OX-018: токен на дію ─────────────────────────
def _in_thread(token, fn):
    out = {}

    def body():
        E.bind_cancel(token)
        try:
            out["r"] = fn()
        finally:
            E.bind_cancel(None)
    th = threading.Thread(target=body)
    th.start()
    th.join(10)
    return out.get("r")


def test_two_parallel_actions_cancel_independently():
    a, b = E.CancelToken(), E.CancelToken()
    started, go = threading.Event(), threading.Event()
    seen = {}

    def first():  # довга дія: чекає, поки її зупинять
        E.bind_cancel(a)
        started.set()
        go.wait(5)
        seen["a"] = E.CANCEL.is_set()

    th = threading.Thread(target=first)
    th.start()
    started.wait(5)
    a.set()  # користувач натиснув «Зупинити» в першій дії
    # друга дія стартує саме тепер і, як раніше run_quick, скидає «свій» прапорець
    seen["b"] = _in_thread(b, lambda: (E.CANCEL.clear(), E.CANCEL.is_set())[1])
    go.set()
    th.join(5)
    assert seen == {"a": True, "b": False}, seen
    assert not b.is_set()


def test_unbound_threads_are_not_cancelled_by_an_action():
    t = E.CancelToken()
    t.set()
    assert _in_thread(t, E.CANCEL.is_set) is True
    assert _in_thread(None, E.CANCEL.is_set) is False


def test_child_thread_inherits_the_token():
    t = E.CancelToken()

    def parent():
        box = {}
        th = threading.Thread(target=E.inherit_cancel(lambda: box.setdefault("v", E.CANCEL.is_set())))
        t.set()
        th.start()
        th.join(5)
        return box.get("v")
    assert _in_thread(t, parent) is True


def test_stop_all_cancels_every_token():
    t = E.CancelToken()
    try:
        E.stop_all()
        assert t.is_set() and _in_thread(None, E.CANCEL.is_set)
    finally:
        E._SHUTDOWN.clear()
    assert not t.is_set()


# ───────────────────────── OX-019: зупинка читання й PowerShell ─────────────────────────
def _real_run(token, **kw):
    """Справжній engine.run для довгого процесу Python; токен ставиться через 0,3 с."""
    cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
    with patched(IS_WIN=True, DRY_RUN=False, CREATE_NO_WINDOW=E.CREATE_NO_WINDOW if E.IS_WIN else 0,
                 _child_cwd=lambda: None), patched(E.SF, sysexe=lambda x: x):
        threading.Timer(0.3, token.set).start()
        t0 = time.time()
        rc, out = _in_thread(token, lambda: E.run(cmd, **kw))
        return rc, out, time.time() - t0


def test_read_only_command_stops_within_a_second():
    rc, out, took = _real_run(E.CancelToken(), timeout=20, ro=True)
    assert rc == E.TIMEOUT_RC and out == "[CANCELLED]" and took < 3, (rc, out, took)


def test_short_changing_command_is_not_cut_in_half():
    # коротку команду, що змінює систему, «Зупинити» не обриває (тайм-аут 2 с — сам її зупинить)
    rc, out, took = _real_run(E.CancelToken(), timeout=2)
    assert out == "[TIMEOUT]" and took >= 1.9, (rc, out, took)


def test_powershell_passes_its_own_stop_rule():
    got = []
    with patched(IS_WIN=True, DRY_RUN=False, run=lambda cmd, *a, **k: (got.append(k.get("stoppable")), (0, ""))[1]):
        E.ps("Get-Date", 30, ro=True)
        E.ps("Set-Something", 30)
        E.ps("Long-Thing", 900)
    assert got == [True, False, True], got


# ───────────────────────── OX-008: «частково» замість «готово» ─────────────────────────
def make_tweak(ops):
    """Копія будь-якого твіка каталогу з нашими кроками (так не треба знати всі поля Tweak)."""
    import copy
    t = copy.copy(E.BY_ID[next(iter(E.BY_ID))])
    t.id, t._title, t.ops = "t_honest", "Honest", list(ops)
    t.win11 = t.win10 = t.retired = t.reboot = False
    t.reversible = True
    return t


def apply(ops, results):
    calls, log = [], []
    t = make_tweak(ops)
    with temp_journal() as j, patched(run=runner(results, calls), compat=lambda *a: ("ok", ""),
                                      needs_admin=lambda t: False):
        res = E.apply_tweaks([t], log.append, header=True)
        return res, j.has(t.id), log


def test_failed_command_makes_the_tweak_partial():
    res, in_journal, log = apply([E.C("good on", "good off"), E.C("bad on", "bad off")], {"bad on": 5})
    assert res["ok"] == 0 and res["partial"] == 1 and res["fail"] == 0, res
    assert in_journal and res["failed_items"] == ["Honest"], res
    assert not any("✓" in x for x in log), log


def test_all_steps_failed_is_a_failure():
    res, in_journal, _ = apply([E.C("bad on", "bad off")], {"bad on": 1})
    assert res["ok"] == 0 and res["fail"] == 1 and res["partial"] == 0, res
    assert not in_journal


def test_good_tweak_is_still_done():
    res, in_journal, _ = apply([E.C("good on", "good off")], {})
    assert res["ok"] == 1 and res["partial"] == 0 and res["fail"] == 0, res


def test_denied_service_is_not_reported_disabled():
    log, ctx = [], E.Ctx(lambda s: log.append(s))
    ctx.begin()
    with patched(DRY_RUN=False, run=runner({"sc config": 5}, []), svc_get_start=lambda n: "auto"):
        E.exec_op(E.S("WSearch"), ctx)
    assert ctx.failed == ["svc WSearch"], ctx.failed
    assert not any("[DISABLED]" in x for x in log), log


def test_service_that_did_not_change_is_caught_by_rereading():
    log, ctx = [], E.Ctx(lambda s: log.append(s))
    ctx.begin()
    with patched(DRY_RUN=False, run=runner({}, []), svc_get_start=lambda n: "auto"):  # rc 0, але режим той самий
        E.exec_op(E.S("WSearch"), ctx)
    assert ctx.failed == ["svc WSearch"]


# ───────────────────────── OX-028 ─────────────────────────
def test_undo_or_default_reports_what_really_happened():
    t = make_tweak([E.C("x")])
    t.off = []
    with temp_journal():
        assert E.undo_or_default(t, lambda *_: None) == {"undone": 0, "partial": 0}
        t.off = [E.C("bad default")]
        with patched(run=runner({"bad default": 1}, [])):
            r = E.undo_or_default(t, lambda *_: None)
        assert r["undone"] == 0 and r["partial"] == 1, r


# ───────────────────────── OX-020: точка відновлення ─────────────────────────
def restore_point(before: str, after: str):
    """before / after — що PowerShell каже про найновішу точку до і після Checkpoint-Computer."""
    answers = [before, after]

    def ps(code, *a, **k):
        if code == E.LAST_RP_PS:
            return 0, answers.pop(0)
        return 0, ""
    noop = lambda *a, **k: None  # noqa: E731
    with patched(DRY_RUN=False, ps=ps, reg_get=noop, reg_set=noop, reg_del_value=noop):
        return E.create_restore_point(lambda *_: None)["ok"]


def test_old_optimax_point_is_not_a_new_one():
    name = E.RESTORE_POINT_NAME
    assert restore_point(f"7|{name}", f"7|{name}") is False  # захист вимкнено — лишилася стара точка OptimaX
    assert restore_point(f"7|{name}", f"8|{name}") is True
    assert restore_point("0|", f"1|{name}") is True  # перша точка на цьому ПК
    assert restore_point("7|Windows Update", f"8|Windows Update") is False  # нова, але не наша
    assert restore_point("WARNING: oops", f"8|{name}") is False  # до спроби не прочиталося — довести нічим
    assert restore_point("ERR", f"8|{name}") is False  # «Access denied» — не те саме, що «точок немає»
    assert restore_point("0|", "ERR") is False
    assert restore_point(f"WARNING: x\n7|{name}", f"8|{name}") is True  # попередження перед відповіддю


# ───────────────────────── OX-023: settings.json ─────────────────────────
def _cfg_dir():
    import json
    d = tempfile.mkdtemp(prefix="oxcfg_")
    return d, os.path.join(d, "settings.json"), json


def test_damaged_settings_come_back_from_the_backup():
    import features as F
    d, p, json = _cfg_dir()
    c = F.Config(p)
    c["theme"] = "light"
    c["hotkeys"] = False  # друге збереження: перше («light») — у .bak
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"theme": "li')  # обірваний запис
    c2 = F.Config(p)
    assert c2.problem == "restored" and c2["theme"] == "light", (c2.problem, c2["theme"])
    assert any(n.startswith("settings.json.corrupt-") for n in os.listdir(d)), os.listdir(d)


def test_damaged_settings_without_backup_are_reported_not_silently_reset():
    import features as F
    d, p, json = _cfg_dir()
    with open(p, "w", encoding="utf-8") as f:
        f.write("\x00\x00\x00")
    c = F.Config(p)
    assert c.problem == "lost" and c["theme"] == F.DEFAULTS["theme"]
    kept = [n for n in os.listdir(d) if n.startswith("settings.json.corrupt-")]
    assert kept, os.listdir(d)  # зіпсований файл не перезаписано типовими значеннями


def test_crash_between_write_steps_uses_the_newer_tmp():
    import features as F
    d, p, json = _cfg_dir()
    with open(p + ".bak", "w", encoding="utf-8") as f:
        json.dump({"theme": "dark"}, f)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"theme": "light"}, f)
    c = F.Config(p)  # основного файлу немає: його вже перенесли в .bak, а .tmp ще не став основним
    assert c.problem == "restored" and c["theme"] == "light"


def test_fresh_install_is_not_a_problem_and_saves_report_errors():
    import features as F
    d, p, json = _cfg_dir()
    c = F.Config(p)
    assert c.problem is None and c.save() is True and c.take_save_error() is None
    blocker = os.path.join(d, "file")
    open(blocker, "w").close()
    bad = F.Config(os.path.join(blocker, "settings.json"))  # «папка» — це файл: запис неможливий
    assert bad.save() is False and bad.take_save_error()
    assert bad.save() is False and bad.take_save_error() is None  # про ту саму помилку — один раз


# ───────────────────────── OX-021: видалення програми ─────────────────────────
def _uninstall(entries: int, revert: bool = False):
    import types
    import lifecycle as LC
    import rescue as RS
    stubs = {"adblock": types.SimpleNamespace(Backend=lambda cfg: types.SimpleNamespace(uninstall=lambda log: None)),
             "phonemon": types.SimpleNamespace(cleanup=lambda: None)}
    old = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    wrote = []
    try:
        # деінсталятор працює з правами адміністратора (без них записи cmd не відкочуються — так і має бути)
        with temp_journal() as j, patched(run=runner({}, []), is_admin=lambda: True), \
                patched(RS, write_rescue=lambda *a: wrote.append(1)):
            for i in range(entries):
                j.put(f"t{i}", [{"t": "cmd", "c": f"undo {i}"}])
            code = LC.run_cli(["x", "--uninstall"] + (["--revert-all"] if revert else []))
    finally:
        for k, v in old.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return code, bool(wrote)


def test_uninstall_tells_the_installer_about_changes_left():
    import lifecycle as LC
    assert _uninstall(0) == (0, False)
    assert _uninstall(2) == (LC.PENDING_RC, True)  # Rescue оновлено: він лишиться єдиним способом відкату
    assert _uninstall(2, revert=True) == (0, False)  # усе відкочено — інсталятор може видалити журнал


def test_installer_keeps_journal_and_rescue_while_changes_are_left():
    """Статична перевірка OptimaX.iss: код 3 від --uninstall береже state і rescue (компілює й ганяє CI)."""
    from _util import ROOT as R
    iss = open(os.path.join(R, "packaging", "OptimaX.iss"), encoding="utf-8-sig").read()
    assert "PendingChanges := ResultCode <> 0" in iss
    assert "DelTreeExcept(ExpandConstant('{commonappdata}\\OptimaX'), 'state', 'rescue')" in iss
    for lang in ("uk", "ru", "en"):
        assert f"{lang}.DeleteDataKeepAsk=" in iss


# ───────────────────────── OX-009: підсумок дії ─────────────────────────
def test_outcome_has_four_states():
    if not has_qt():
        skip("PyQt6 не встановлено")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import ui_kit as UK
    assert UK.outcome({"ok": 3, "fail": 0}) == ("ok", 0)
    assert UK.outcome({"ok": 1, "fail": 2}) == ("partial", 2)
    assert UK.outcome({"ok": 1, "fail": 0, "partial": 1}) == ("partial", 1)
    assert UK.outcome({"undone": 2, "partial": 1}) == ("partial", 1)
    assert UK.outcome({"ok": False}) == ("partial", 1)
    assert UK.outcome({"ok": 1}, cancelled=True) == ("stopped", 0)
    assert UK.outcome({"cancelled": True}) == ("stopped", 0)
    assert UK.outcome({"error": "x", "ok": 1}) == ("error", 0)


# ───────────────────────── OX-017: оновлення ─────────────────────────
def test_cancelled_update_download_is_not_a_verify_failure():
    import updater as U
    import verify as V
    t = E.CancelToken()

    def stopped(*a, **k):
        t.set()
        raise RuntimeError("Stopped by user")
    with patched(U, download=stopped):
        r = _in_thread(t, lambda: U.download_job({}, lambda *_: None))
    assert r == {"cancelled": True, "kind": "cancelled"}, r

    def offline(*a, **k):
        raise OSError("no network")
    with patched(U, download=offline):
        r = _in_thread(E.CancelToken(), lambda: U.download_job({}, lambda *_: None))
    assert r["kind"] == "network" and r["error"], r

    def bad(*a, **k):
        raise V.VerifyError("vf.no_hash", name="x.exe")
    with patched(U, download=bad):
        r = _in_thread(E.CancelToken(), lambda: U.download_job({}, lambda *_: None))
    assert r["kind"] == "verify", r
