"""Гарантії відкату й безпека (6.14). Жодна справжня команда тут не виконується: engine.run / engine.ps підмінені,
журнал — тимчасовий файл. Тому ці тести однаково працюють на Windows і поза нею.

• крок відкату, який не спрацював (команда, задача, PowerShell, живлення), лишається в журналі;
• параметр живлення не змінюється, якщо його старе значення не прочиталося;
• файл підкачки, заданий вручну, не чіпається;
• попередження PowerShell перед JSON не губить записи відкату мережевих адаптерів;
• стан режиму гри й знімок налаштувань із файлів користувача не стають командою з правами адміністратора;
• очищення не видаляє дані самої OptimaX."""
import contextlib
import os
import sys
import tempfile

from _util import ROOT

sys.path.insert(0, ROOT)
if "engine" not in sys.modules:  # окремий запуск цього файла: режим перегляду й чиста папка налаштувань
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402

GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"
LOG = []


@contextlib.contextmanager
def patched(mod=E, **attrs):
    old = {k: getattr(mod, k) for k in attrs}
    for k, v in attrs.items():
        setattr(mod, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(mod, k, v)


@contextlib.contextmanager
def temp_journal():
    d = tempfile.mkdtemp(prefix="oxj_")
    with patched(JOURNAL=E.Journal(os.path.join(d, "back.json")), DRY_RUN=False):
        yield E.JOURNAL


def runner(results: dict, calls: list):
    """Підмінний engine.run: код повернення за початком команди (без збігу — успіх)."""
    def run(cmd, timeout=30, log=None, input_text=None, enc=None, ro=False):
        shown = cmd if isinstance(cmd, str) else " ".join(cmd)
        calls.append(shown)
        for prefix, rc in results.items():
            if shown.lower().startswith(prefix.lower()):
                return rc, f"rc {rc}"
        return 0, ""
    return run


def undo(rec: dict, results: dict = None, ps_rc: int = 0):
    """Кладе запис у тимчасовий журнал і відкочує його. -> (результат undo_one, записи, що лишилися, виклики)."""
    calls = []
    with temp_journal() as j:
        j.put("t", [rec])
        with patched(run=runner(results or {}, calls), active_scheme=lambda: GUID,
                     ps=lambda code, *a, **k: (calls.append("ps " + code[:40]), (ps_rc, "boom" if ps_rc else ""))[1]):
            res = E.undo_one("t", LOG.append)
        return res, (j.get("t") or {}).get("undo", []), calls


# ───────────────────────── OX-001: невдалий крок відкату лишається в журналі ─────────────────────────
def test_failed_command_undo_stays_in_the_journal():
    rec = {"t": "cmd", "c": "powercfg -h on"}
    res, left, _ = undo(rec, {"powercfg -h on": 5})
    assert res == "partial" and left == [rec], (res, left)
    res, left, _ = undo(rec)
    assert res is True and left == []


def test_cancelled_or_timed_out_undo_is_not_reported_as_done():
    rec = {"t": "cmd", "c": "powercfg -h on"}
    res, left, _ = undo(rec, {"powercfg -h on": E.TIMEOUT_RC})
    assert res == "partial" and left == [rec]


def test_nothing_left_to_delete_is_not_a_failure():
    """Те саме правило, що й в OptimaX-Rescue.cmd: «reg delete» / «bcdedit /deletevalue», які нічого не знайшли."""
    import rescue as RS
    assert E.UNDO_GONE_OK == RS.GONE_OK
    for cmd in ('reg delete "HKLM\\SOFTWARE\\X" /v Y /f', "bcdedit /deletevalue useplatformtick"):
        res, left, _ = undo({"t": "cmd", "c": cmd}, {cmd[:12]: 1})
        assert res is True and left == [], cmd


def test_restart_required_code_counts_as_success():
    res, left, _ = undo({"t": "cmd", "c": "dism /online /enable-feature /featurename:X"}, {"dism": 3010})
    assert res is True and left == []


def test_failed_powershell_undo_stays_in_the_journal():
    rec = {"t": "ps", "c": "Enable-MMAgent -MemoryCompression"}
    res, left, _ = undo(rec, ps_rc=1)
    assert res == "partial" and left == [rec]
    res, left, _ = undo(rec)
    assert res is True and left == []


def test_placeholder_powershell_record_is_skipped():
    res, left, calls = undo({"t": "ps", "c": "# restore adapter properties"}, ps_rc=1)
    assert res is True and left == [] and calls == []


def test_task_that_would_not_enable_stays_but_a_deleted_task_does_not():
    rec = {"t": "task", "n": r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator"}
    res, left, _ = undo(rec, {"schtasks /Change": 1})  # задача є (/Query = 0), але не ввімкнулася
    assert res == "partial" and left == [rec]
    res, left, _ = undo(rec, {"schtasks /Change": 1, "schtasks /Query": 1})  # задачі вже немає
    assert res is True and left == []


def test_failed_power_setting_undo_stays_in_the_journal():
    rec = {"t": "pw", "g": GUID, "s": "SUB_PROCESSOR", "st": "CPMINCORES", "old": 5, "m": "ac"}
    res, left, calls = undo(rec, {"powercfg -setacvalueindex": 1})
    assert res == "partial" and left == [rec]
    assert not any("-setactive" in c for c in calls), "a failed step must not re-apply the scheme"
    res, left, calls = undo(rec)
    assert res is True and left == [] and any("-setactive" in c for c in calls)


def test_unsaved_journal_after_rollback_is_reported():
    lines = []
    with temp_journal() as j:
        j.put("t", [{"t": "cmd", "c": "powercfg -h on"}])

        def broken(path, data, durable):
            raise OSError(28, "No space left on device")
        with patched(run=runner({}, []), _write_atomic=broken):
            assert E.undo_one("t", lines.append) is True
    assert any("No space left" in s for s in lines), lines


# ───────────────────────── OX-006: живлення — жодної зміни без запису відкату ─────────────────────────
def _pw(old, set_rc=0):
    calls, seen = [], []
    ctx = E.Ctx(LOG.append)

    def run(cmd, *a, **k):
        shown = cmd if isinstance(cmd, str) else " ".join(cmd)
        calls.append(shown)
        if "valueindex" in shown:
            seen.append(len(ctx.undo))  # скільки записів відкату вже є в мить зміни
            return set_rc, ""
        return 0, ""
    with patched(run=run, DRY_RUN=False, pw_get=lambda *a, **k: old, active_scheme=lambda: GUID):
        E.exec_op(E.P("CPMINCORES", 100), ctx)
    return list(ctx.undo), calls, seen


def test_power_setting_with_unknown_old_value_is_not_changed():
    undo_recs, calls, _ = _pw(None)
    assert undo_recs == [] and not any("valueindex" in c for c in calls), calls


def test_power_setting_is_recorded_before_it_changes():
    undo_recs, calls, seen = _pw(5)
    assert seen == [1], "the rollback record must exist before powercfg runs"
    assert undo_recs == [{"t": "pw", "g": GUID, "s": "SUB_PROCESSOR", "st": "CPMINCORES", "old": 5, "m": "ac"}]
    assert E.valid_undo(undo_recs[0])


def test_power_setting_that_failed_to_apply_leaves_no_record():
    undo_recs, calls, _ = _pw(5, set_rc=1)
    assert undo_recs == [] and not any("-setactive" in c for c in calls)


def test_hidden_power_settings_are_read():
    """powercfg /query не показує приховані параметри (паркування ядер) — читаємо через /qh."""
    calls = []
    out = "    Current AC Power Setting Index: 0x00000064\n    Current DC Power Setting Index: 0x00000032"
    with patched(run=lambda cmd, *a, **k: (calls.append(cmd), (0, out))[1], IS_WIN=True):
        assert E.pw_get(GUID, "SUB_PROCESSOR", "CPMINCORES") == 100
        assert E.pw_get(GUID, "SUB_PROCESSOR", "CPMINCORES", "dc") == 50
    assert calls[0] == ["powercfg", "/qh", GUID, "SUB_PROCESSOR", "CPMINCORES"]


# ───────────────────────── OX-005: файл підкачки, заданий вручну ─────────────────────────
def _pagefile(state: str):
    scripts = []
    ctx = E.Ctx(LOG.append)

    def ps(code, *a, **k):
        scripts.append((code, len(ctx.undo)))
        return (0, state) if "AutomaticManagedPagefile" in code and "Set-" not in code else (0, "")
    with patched(ps=ps, DRY_RUN=False):
        E.f_pagefile(ctx)
    return list(ctx.undo), scripts


def test_manual_page_file_is_left_alone():
    for state in ("False", "", "Get-CimInstance : Access denied"):
        undo_recs, scripts = _pagefile(state)
        assert undo_recs == [] and all(code != E.PF_APPLY for code, _ in scripts), state


def test_automatic_page_file_is_recorded_before_it_changes():
    undo_recs, scripts = _pagefile("True")
    assert undo_recs == [{"t": "ps", "c": E.PF_UNDO}]
    assert [n for code, n in scripts if code == E.PF_APPLY] == [1]


# ───────────────────────── OX-007: мережеві адаптери ─────────────────────────
def test_adapter_changes_keep_their_undo_despite_powershell_warnings():
    out = 'WARNING: The network adapter is restarting.\n[{"n":"Ethernet","k":"*EEE","v":"1"},' \
          '{"n":"Ethernet","k":"__pm","v":"Enabled"}]'
    for fn in (E.f_nic_power, E.f_eth_latency):
        ctx = E.Ctx(LOG.append)
        with patched(ps=lambda code, *a, **k: (0, out), DRY_RUN=False):
            fn(ctx)
        assert len(ctx.undo) == 1 and ctx.undo[0]["t"] == "ps", fn.__name__
        assert "-Name 'Ethernet'" in ctx.undo[0]["c"] and "'*EEE'" in ctx.undo[0]["c"]
        assert E.valid_undo(ctx.undo[0])


# ───────────────────────── OX-002 / OX-003: режим гри ─────────────────────────
def _stop(state):
    import features as F
    calls = []
    cfg = {"booster_state": state}
    with patched(run=runner({}, calls)):
        res = F.GameBooster(cfg).stop(LOG.append)
    return res, cfg["booster_state"], calls


def test_booster_state_from_settings_never_becomes_a_shell_command():
    state = {"ts": 1, "services": ["WSearch", "x & calc.exe", 'BITS" & whoami', 5, "NotOurService"],
             "plan": GUID + " & calc.exe", "onedrive": "yes", "dnd": "1", "timer": False,
             "prio": [["x", "y"], [4, "a.exe", 999999], "junk"]}
    res, left, calls = _stop(state)
    assert res == {"ok": True} and left is None
    assert calls == ["net start WSearch"], calls


def test_booster_state_is_restored_from_its_own_values():
    res, left, calls = _stop({"ts": 1, "services": ["WSearch", "SysMain"], "plan": GUID})
    assert left is None and calls == ["net start WSearch", "net start SysMain", f"powercfg -setactive {GUID}"]


def test_garbage_booster_state_is_dropped():
    for junk in (["net", "start"], "x & y", 7):
        res, left, calls = _stop(junk)
        assert res == {"ok": True} and left is None and calls == []


def test_user_programs_are_started_through_a_limited_task():
    calls = []
    with patched(run=lambda cmd, *a, **k: (calls.append(cmd), (0, ""))[1]):
        assert E.start_as_user(r"C:\Users\A B\AppData\Local\Microsoft\OneDrive\OneDrive.exe", "/background") is True
        assert E.start_as_user('C:\\x" & calc "\\y.exe') is False
        assert E.start_as_user("") is False
    create, run_, delete = calls
    assert create[:2] == ["schtasks", "/Create"] and "LIMITED" in create and "HIGHEST" not in create
    assert create[create.index("/TR") + 1] == \
        r'"C:\Users\A B\AppData\Local\Microsoft\OneDrive\OneDrive.exe" /background'
    assert run_ == ["schtasks", "/Run", "/TN", E.USER_TASK]
    assert delete == ["schtasks", "/Delete", "/TN", E.USER_TASK, "/F"]


# ───────────────────────── OX-004: знімок початкових налаштувань ─────────────────────────
def test_baseline_service_mode_from_the_file_is_checked():
    import baseline as BL
    calls = []
    item = dict(kind="svc", key="SysMain", name="SysMain", cur="disabled", tweaks=[])
    with patched(run=runner({}, calls), DRY_RUN=False):
        bad = BL.restore([dict(item, base="auto & calc.exe"), dict(item, name="Sys Main & calc", base="auto")],
                         LOG.append)
        good = BL.restore([dict(item, base="auto")], LOG.append)
    assert bad == {"ok": 0, "fail": 2} and good == {"ok": 1, "fail": 0}
    assert calls == ["sc config SysMain start= auto"], calls


def test_baseline_with_an_unknown_service_mode_is_not_offered():
    import baseline as BL
    snap = {"v": 1, "reg": {}, "svc": {name: "auto & calc.exe" for name in BL.targets()["svc"]}}
    with patched(svc_get_start=lambda name: "disabled"):
        assert [o for o in BL.orphans(snap, E.Journal(os.path.join(tempfile.mkdtemp(prefix="oxb_"), "j.json")))
                if o["kind"] == "svc"] == []


# ───────────────────────── OX-016: очищення ─────────────────────────
def test_cleaning_never_touches_optimax_own_data():
    d = os.path.realpath(tempfile.mkdtemp(prefix="oxc_"))
    root = os.path.join(d, "OptimaX")
    state, junk = os.path.join(root, "state"), os.path.join(d, "Temp")
    for folder in (state, junk):
        os.makedirs(folder)
        with open(os.path.join(folder, "back.json"), "w") as f:
            f.write("x" * 10)
    with patched(E.SF, data_root=lambda: root):
        assert E.clean_dir(state) == 0 and E.clean_dir(root) == 0
        assert os.path.exists(os.path.join(state, "back.json")), "the rollback journal must survive any cleanup"
        assert E.clean_dir(junk) == 10 and os.listdir(junk) == []
