"""Аудит 7.1.1, ядро: журнал, виконавець операцій, аварійний відкат, межа довіри. Жодна справжня системна команда
тут не виконується: engine.run / engine.ps підмінені, журнал — тимчасовий файл.

• повторне застосування твіка, що вже в журналі, дописує записи нових пристроїв і задач (A10), і після аварії теж;
• запис відкату — до зміни; прибирається лише тоді, коли команда точно відмовила, не за тайм-аутом (A9, A11);
• служби й задачі — списком аргументів, без cmd.exe (A6); chkdsk і defrag — так само, диск — з папки Windows (A3);
• видалення параметра реєстру перевіряється перечитуванням (A12); ліміт Defender без прочитаних значень не
  змінюється (A12);
• FILE не йде за посиланням на шляху і не дописує підкинутий тимчасовий файл (A8);
• мережеві шляхи з імпортованого файлу налаштувань не перевіряються на диску (A14);
• ліміт заряду: лише відомий метод і ціле число (A4);
• OptimaX-Rescue.cmd: жодних %SystemRoot% у кроках, Провідник за повним шляхом, DNS фільтра реклами — в /all (A5, A7,
  B11); запускач у packaging не розгортає змінних середовища (B1)."""
import base64
import json
import os
import re
import shutil
import sys
import tempfile

from _util import ROOT, skip

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
from test_undo_guarantees import patched, temp_journal, runner  # noqa: E402

GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"


def _ctx(track=False):
    log = []
    ctx = E.Ctx(log.append)
    ctx.begin(track)
    return ctx, log


# ───────────────────────── A10: повторне застосування дописує нові записи ─────────────────────────
def test_reapply_merges_new_records_and_keeps_first_snapshot():
    with temp_journal() as j:
        first = {"t": "reg", "p": r"HKLM\X\dev1", "n": "MSISupported", "old": None}
        j.put("msi_gpu", [{"t": "live", "k": "explorer"}, first])
        again = dict(first, old=[4, 1])  # знімок уже зміненого — не має замінити найперший
        new = {"t": "reg", "p": r"HKLM\X\dev2", "n": "MSISupported", "old": [4, 0]}
        j.put("msi_gpu", [again, new])
        undo = j.get("msi_gpu")["undo"]
        assert undo[0] == {"t": "live", "k": "explorer"}, "the refresh still runs last on undo"
        assert first in undo and again not in undo and new in undo and len(undo) == 3, undo
        j.put("msi_gpu", [again, new])  # нічого нового — нічого не дописується
        assert len(j.get("msi_gpu")["undo"]) == 3


def test_crashed_reapply_records_are_merged_on_start():
    with temp_journal() as j:
        old = {"t": "task", "n": r"\NVIDIA\TaskA"}
        j.put("nv_tasks", [old])
        j.begin("nv_tasks")  # повторне застосування — «fresh» = False
        new = {"t": "task", "n": r"\NVIDIA\TaskB"}
        j.note([old, new])
        res = E.recover_interrupted(lambda *_: None)
        assert res["tweak"] is None
        assert j.get("nv_tasks")["undo"] == [old, new]
        assert j.interrupted() is None


# ───────────────────────── A9 / A11: запис до зміни, тайм-аут — не «точно відмовила» ─────────────────────────
def _pw(rc):
    ctx, _ = _ctx()
    calls = []
    with patched(DRY_RUN=False, IS_WIN=True, active_scheme=lambda: GUID, pw_get=lambda *a, **k: 5,
                 run=runner({"powercfg -setacvalueindex": rc}, calls)):
        E.exec_op(E.P("CPMINCORES", 100), ctx)
    return ctx, calls


def test_power_setting_failure_discards_but_timeout_keeps_record():
    ctx, _ = _pw(1)
    assert list(ctx.undo) == [] and ctx.failed
    ctx, _ = _pw(E.TIMEOUT_RC)
    assert len(ctx.undo) == 1 and ctx.failed, "after a timeout the change may have happened"


def test_power_scheme_is_read_once_for_a_run_of_settings():
    ctx, _ = _ctx()
    reads = []
    with patched(DRY_RUN=False, IS_WIN=True, active_scheme=lambda: reads.append(1) or GUID,
                 pw_get=lambda *a, **k: 5, run=runner({}, [])):
        E.exec_op(E.P("A", 1), ctx)
        E.exec_op(E.P("B", 1), ctx)
        assert len(reads) == 1
        E.exec_op(E.C("x"), ctx)  # інша операція могла перемкнути схему — читаємо знову
        E.exec_op(E.P("C", 1), ctx)
    assert len(reads) == 2


def test_hibernation_record_is_written_before_the_change():
    seen = []
    ctx, _ = _ctx()

    def run(cmd, *a, **k):
        seen.append(list(ctx.undo))
        return E.TIMEOUT_RC, ""
    with patched(DRY_RUN=False, IS_WIN=False, reg_get=lambda *a: (4, 1), run=run):
        E.f_hibernation_off(ctx)
    assert seen and seen[0] == [{"t": "cmd", "c": "powercfg -h on"}]
    assert list(ctx.undo) and ctx.failed
    ctx, _ = _ctx()
    with patched(DRY_RUN=False, IS_WIN=False, reg_get=lambda *a: (4, 1), run=lambda *a, **k: (1, "denied")):
        E.f_hibernation_off(ctx)
    assert list(ctx.undo) == [] and ctx.failed


def test_onedrive_uninstall_failure_is_reported():
    ctx, _ = _ctx()
    with patched(DRY_RUN=False, run=lambda *a, **k: (1, "no"), ps=lambda *a, **k: (0, "")):
        E.f_onedrive(ctx)
    assert ctx.failed and list(ctx.undo) == []
    ctx, _ = _ctx()
    with patched(DRY_RUN=False, run=lambda *a, **k: (0, ""), ps=lambda *a, **k: (0, "")):
        E.f_onedrive(ctx)
    assert not ctx.failed and len(ctx.undo) == 1


def test_defender_limit_without_old_values_changes_nothing():
    ctx, _ = _ctx()
    calls = []
    with patched(DRY_RUN=False, IS_WIN=True, ps_json=lambda *a, **k: None,
                 ps=lambda code, *a, **k: (calls.append(code), (0, ""))[1]):
        E.f_defender_limit(ctx)
    assert calls == [] and list(ctx.undo) == [] and ctx.failed
    ctx, _ = _ctx()
    with patched(DRY_RUN=False, IS_WIN=True, ps_json=lambda *a, **k: {"a": 35, "b": False, "c": True},
                 ps=lambda *a, **k: (1, "denied")):
        E.f_defender_limit(ctx)
    assert list(ctx.undo) == [] and ctx.failed


# ───────────────────────── A6 / A3: списки аргументів ─────────────────────────
def test_service_and_task_commands_are_argv_lists():
    raw = []

    def run(cmd, *a, **k):
        raw.append(cmd)
        return 0, ""
    ctx, _ = _ctx()
    with patched(DRY_RUN=False, run=run, svc_get_start=lambda n: "auto" if not raw else "disabled"):
        E.exec_op(E.S("Spooler%x%"), ctx)
    ctx._tasks = None
    with patched(DRY_RUN=False, run=run):
        E.exec_op(E.TK(r"\My %TEMP% task"), ctx)
    assert raw and all(isinstance(c, list) for c in raw), raw
    assert ["schtasks", "/Change", "/Disable", "/TN", r"\My %TEMP% task"] in raw


def test_chkdsk_and_defrag_take_the_drive_from_windows_not_the_environment():
    raw = []
    with patched(run=lambda cmd, *a, **k: (raw.append(cmd), (0, ""))[1],
                 stream=lambda cmd, *a, **k: raw.append(cmd) or True):
        old = os.environ.get("SystemDrive")
        os.environ["SystemDrive"] = "C: & calc"
        try:
            ctx, _ = _ctx()
            E.f_chkdsk(ctx)
            E.a_optimize_disk(ctx)
        finally:
            if old is None:
                os.environ.pop("SystemDrive", None)
            else:
                os.environ["SystemDrive"] = old
    assert raw[0][0] == "chkdsk" and raw[1][0] == "defrag", raw
    assert all(isinstance(c, list) and re.fullmatch(r"[A-Za-z]:", c[1]) for c in raw), raw


# ───────────────────────── A12: видалення параметра перевіряється ─────────────────────────
def test_registry_delete_that_did_not_happen_is_a_failure():
    ctx, _ = _ctx()
    with patched(DRY_RUN=False, reg_get=lambda p, n: (4, 1), reg_del_value=lambda p, n: None):
        E.exec_op(E.RD(r"HKLM\X", "V"), ctx)
    assert ctx.failed == ["reg V"] and list(ctx.undo) == []


# ───────────────────────── A8: FILE і посилання ─────────────────────────
def test_file_op_refuses_links_and_planted_tmp():
    if not hasattr(os, "symlink"):
        skip("no symlinks")
    d = os.path.realpath(tempfile.mkdtemp(prefix="oxf_"))
    try:
        src = os.path.join(d, "layer.dll")
        with open(src, "wb") as f:
            f.write(b"ours")
        game, elsewhere = os.path.join(d, "game"), os.path.join(d, "victim")
        os.makedirs(game)
        os.makedirs(elsewhere)
        os.symlink(elsewhere, os.path.join(d, "link"))
        ctx, _ = _ctx()
        with patched(DRY_RUN=False):
            try:
                E.exec_op(E.FILE(src, os.path.join(d, "link", "d3d9.dll")), ctx)
                raise AssertionError("a link in the path must be refused")
            except RuntimeError:
                pass
            assert not os.listdir(elsewhere)
            # підкинуте посилання на місці тимчасового файлу: копія не має піти за ним
            victim = os.path.join(elsewhere, "planted.dll")
            dest = os.path.join(game, "d3d9.dll")
            os.symlink(victim, dest + ".optimax-tmp")
            E.exec_op(E.FILE(src, dest), ctx)
        assert not os.path.lexists(victim) and open(dest, "rb").read() == b"ours"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ───────────────────────── A14: мережеві шляхи з імпорту ─────────────────────────
def test_import_never_touches_network_paths():
    import transfer as T
    touched = []
    real = os.path.isfile
    os.path.isfile = lambda p: touched.append(p) or False
    try:
        for p in (r"\\evil\share\game.exe", "//evil/share/game.exe", r"\/evil\game.exe"):
            assert not T._local_exe(p)
        T.plan({"games": [{"path": r"\\evil\share\game.exe"}]})
    finally:
        os.path.isfile = real
    assert touched == [], touched


# ───────────────────────── A4: ліміт заряду ─────────────────────────
def test_charge_limit_accepts_only_known_methods_and_numbers():
    import power as PW
    calls = []
    with patched(ps=lambda code, *a, **k: (calls.append(code), (0, ""))[1], run=runner({}, calls)):
        assert PW.set_charge_limit("asus", "60}; calc; @{", lambda *_: None) == {"ok": False}
        assert PW.set_charge_limit("calc.exe", 60, lambda *_: None) == {"ok": False}
        assert not PW.method_available("calc.exe")
    assert calls == []


# ───────────────────────── A5 / A7 / B11: OptimaX-Rescue.cmd ─────────────────────────
def _script(entries: dict, dns_backup=None):
    import adblock as AB
    import rescue as RS
    d = tempfile.mkdtemp(prefix="oxr_")
    with patched(JOURNAL=E.Journal(os.path.join(d, "back.json"))), patched(AB, data_dir=lambda: d):
        if dns_backup is not None:
            with open(os.path.join(d, "dns-backup.json"), "w", encoding="utf-8") as f:
                json.dump(dns_backup, f)
        for tid, undo in entries.items():
            E.JOURNAL.put(tid, undo)
        return RS.build_script(E.JOURNAL)


def test_rescue_script_has_no_environment_paths():
    s = _script({"power": [{"t": "live", "k": "explorer"},
                           {"t": "pw", "g": GUID, "s": "SUB_PROCESSOR", "st": "CPMINCORES", "old": 10, "m": "ac"}]})
    for var in ("SystemRoot", "windir", "ProgramData", "TEMP", "ComSpec"):
        assert f"%{var}%" not in s, var
    assert re.search(r'\| "[A-Za-z]:\\[^"%]*\\find\.exe" /i', s), s
    assert re.search(r'start "" "[A-Za-z]:\\[^"%]*\\explorer\.exe"', s), s


def _decoded(line: str) -> str:
    b64 = line.split("-EncodedCommand ", 1)[1].split(" ", 1)[0]
    return base64.b64decode(b64).decode("utf-16-le")


def test_rescue_all_restores_adblock_dns_from_validated_backup():
    g1, g2 = "{11111111-2222-3333-4444-555555555555}", "{aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee}"
    backup = {g1: {"idx": 7, "ns4": ["9.9.9.9", "127.0.0.1", "1.1.1.1'); calc; ('"], "ns6": ["2001:db8::1"]},
              g2: {"idx": "7; calc", "ns4": [], "ns6": []},
              "{bad}'; calc": {"idx": 3, "ns4": ["8.8.8.8"]}}
    s = _script({"t": [{"t": "cmd", "c": "powercfg -h on"}]}, backup)
    lines = s.split("\r\n")
    all_block = lines[lines.index(":all"):]
    assert "call :dns" in all_block[:all_block.index("goto finish")]
    last_block = lines[lines.index(":last"):lines.index(":all")]
    assert "call :dns" not in last_block, "only /all touches the ad filter"
    dns = lines[lines.index(":dns"):]
    codes = [_decoded(ln) for ln in dns if "-EncodedCommand" in ln]
    assert len(codes) == 3 and "OptimaX DNS" in codes[0] and "schtasks.exe" in codes[0]
    assert "@('9.9.9.9','2001:db8::1')" in codes[1] and "$i=7;" in codes[1] and g1 in codes[1]
    assert "-ResetServerAddresses" in codes[2] and "$i=$null;" in codes[2]
    joined = "".join(codes)
    assert "calc" not in joined and "127.0.0.1" not in joined and "{bad}" not in joined
    # без фільтра (резервної копії немає) — кроку немає
    assert ":dns" not in _script({"t": [{"t": "cmd", "c": "powercfg -h on"}]})


def test_rescue_launcher_expands_no_environment_variable():
    with open(os.path.join(ROOT, "packaging", "OptimaX-Rescue.cmd"), encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if not ln.lower().startswith("rem ")]
    used = {v.lower() for ln in lines for v in re.findall(r"%([A-Za-z_][A-Za-z0-9_()]*)%", ln)}
    assert used <= {"pd", "rs", "errorlevel"}, used  # лише власні змінні, які скрипт сам очищає й задає
    text = "\n".join(lines)
    for v in ("PD", "RS", "ERRORLEVEL"):
        assert f'set "{v}="' in text
    assert "Common AppData" in text and "HKLM\\" in text
