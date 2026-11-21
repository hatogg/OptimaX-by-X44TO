"""OptimaX 7.1.1: виправлення з аудиту — залізо. Кеш шейдерів (резервна копія не з %APPDATA%, цілі не з файлу,
без посилань), сторонні бенчмарки з папок користувача — без прав адміністратора, автопідбір андервольту на іншій
карті / зависання, вентилятори NVIDIA після «не підтримується», карта після збою — з позначки, запис журналу ps,
0 МБ перевіреної пам'яті — не «пройдено», тест диска не видаляє чужі файли, аварійна зупинка за зоною ACPI."""
import contextlib
import os
import sys
import tempfile
import time

from _util import ROOT

sys.path.insert(0, ROOT)
import benchtools as BT  # noqa: E402
import engine as E  # noqa: E402
import gpudiag as GD  # noqa: E402
import gputune as GT  # noqa: E402
import hwtests as HT  # noqa: E402
import secfs as SF  # noqa: E402
import vramtest as VT  # noqa: E402


@contextlib.contextmanager
def patched(mod, **kw):
    old = {k: getattr(mod, k) for k in kw}
    for k, v in kw.items():
        setattr(mod, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(mod, k, v)


def _tmp():
    return os.path.realpath(tempfile.mkdtemp(prefix="ox711hw_"))


def _put(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


# ── C1: кеш шейдерів ──
def test_shader_backup_restore_uses_fixed_targets_not_index_file():
    root = _tmp()
    la, bak, evil = os.path.join(root, "Local"), os.path.join(root, "bak"), os.path.join(root, "evil")
    os.makedirs(bak)
    dirs = [os.path.join(la, "D3DSCache"), os.path.join(la, "NVIDIA", "DXCache")]
    _put(os.path.join(dirs[0], "a.bin"))
    _put(os.path.join(dirs[1], "sub", "b.bin"))
    with patched(E, IS_WIN=True, DRY_RUN=False), patched(SF, local_appdata=lambda: la, program_data=lambda: ""), \
            patched(GD, backup_dir=lambda: bak, shader_dirs=lambda: list(dirs)):
        res = GD.shader_backup_clear(lambda *_: None)
        assert res["moved"] == 2 and not os.listdir(dirs[0])
        b = GD.last_backup()
        assert sorted(os.listdir(b["dir"])) == ["0", "1"]
        # підкинутий index.txt зі «своєю» ціллю — не читається
        with open(os.path.join(b["dir"], "index.txt"), "w") as f:
            f.write(f"0\t{evil}\n1\t{evil}\n")
        res = GD.shader_restore(lambda *_: None)
        assert res["restored"] == 2 and not os.path.exists(evil)
        assert os.path.isfile(os.path.join(dirs[0], "a.bin")) and os.path.isfile(os.path.join(dirs[1], "sub", "b.bin"))


def test_shader_cache_dir_outside_roots_or_link_is_skipped():
    root = _tmp()
    la = os.path.join(root, "Local")
    os.makedirs(la)
    outside = os.path.join(root, "System32")
    os.makedirs(outside)
    _put(os.path.join(outside, "kernel.dll"))
    link = os.path.join(la, "D3DSCache")
    os.symlink(outside, link)
    with patched(SF, local_appdata=lambda: la, program_data=lambda: ""):
        assert GD._safe_cache_dir(os.path.join(la, "NVIDIA", "DXCache"))
        assert not GD._safe_cache_dir(link)
        assert not GD._safe_cache_dir(outside)
    bak = os.path.join(root, "bak")
    os.makedirs(bak)
    with patched(E, IS_WIN=True, DRY_RUN=False), patched(SF, local_appdata=lambda: la, program_data=lambda: ""), \
            patched(GD, backup_dir=lambda: bak, shader_dirs=lambda: [link]):
        res = GD.shader_backup_clear(lambda *_: None)
    assert res["moved"] == 0 and os.path.isfile(os.path.join(outside, "kernel.dll"))


def test_shader_walk_skips_links():
    root = _tmp()
    _put(os.path.join(root, "c", "real.bin"))
    _put(os.path.join(root, "target", "victim.bin"))
    os.symlink(os.path.join(root, "target"), os.path.join(root, "c", "lnk"))
    os.symlink(os.path.join(root, "target", "victim.bin"), os.path.join(root, "c", "file_link"))
    got = [os.path.relpath(p, os.path.join(root, "c")) for p in GD._walk_files(os.path.join(root, "c"))]
    assert got == ["real.bin"]


# ── H1, L7: сторонні бенчмарки ──
def test_untrusted_benchmark_launches_as_user():
    calls = []
    item = dict(BT.BY_ID["cinebench"])
    with patched(E, IS_WIN=True, start_as_user=lambda p, a="", log=None: calls.append(p) or True), \
            patched(BT, find_exe=lambda it: r"C:\Users\u\AppData\Local\Microsoft\WinGet\Links\Cinebench.exe"), \
            patched(SF, trusted_location=lambda p: False):
        assert BT.launch(item)
    assert calls and calls[0].endswith("Cinebench.exe")


def test_furmark_outside_program_files_refused():
    with patched(E, IS_WIN=True), patched(BT, find_exe=lambda it: r"C:\Users\u\FurMark\FurMark_GUI.exe",
                                          _furmark_cli=lambda g: r"C:\Users\u\FurMark\furmark.exe"), \
            patched(SF, trusted_location=lambda p: False):
        try:
            BT.run_furmark("1080p", lambda *_: None)
            assert False, "must refuse"
        except RuntimeError as e:
            assert "FurMark" in str(e)


# ── H2, M4: автопідбір ──
class _Run:
    def __init__(self, result=None, state="done", hang=False):
        self.result, self.state, self.hang, self.stopped = result, state, hang, False

    def poll(self):
        if self.hang:
            return {"state": "running"}
        return {"state": self.state, "result": dict(self.result or {})}

    def stop(self):
        self.stopped = True

    def cleanup(self):
        pass


class _Env:
    def __enter__(self):
        self.j, self.dry = E.JOURNAL, E.DRY_RUN
        E.JOURNAL = E.Journal(os.path.join(_tmp(), "back.json"))
        E.DRY_RUN = False
        GT.SESSION.tuner, GT.SESSION.fans = None, None
        return E.JOURNAL

    def __exit__(self, *a):
        E.JOURNAL, E.DRY_RUN = self.j, self.dry
        GT.SESSION.tuner, GT.SESSION.fans = None, None


class Cfg(dict):
    def __getitem__(self, k):
        return self.get(k)


def _run_tune(t, make_run, ticks=200):
    cfg = Cfg(gpu_tune={"profile": None, "orig": {}, "active": False})
    tune = GT.AutoTune(cfg, t, lambda s: make_run(t), step_s=1, verify_s=1)
    tune.start()
    for _ in range(ticks):
        if tune.tick() in ("done", "failed", "cancelled"):
            break
    return tune, cfg


def test_autotune_wrong_gpu_is_failure_not_verified():
    for marker in (dict(idle_gpu="NVIDIA P106-100"), dict(render_match="other"),
                   dict(gpu_check=dict(status="wrong"))):
        with _Env():
            t = GT.DemoTuner("nvidia", unstable_at=60)
            res = dict(verdict="stable", errors=0, score=900, **marker)
            tune, cfg = _run_tune(t, lambda tt: _Run(res))
            assert tune.phase == "failed" and tune.result["why"] == "gt.tune.wrong_gpu", (marker, tune.result)
            assert t.state["offset"] == 0 and not (GT.state(cfg).get("profile") or {}).get("verified")
    assert GT.run_ok({"state": "done", "result": {"verdict": "stable"}}) == (True, "")


def test_autotune_hang_counts_as_crash():
    with _Env(), patched(GT, TUNE_HANG_GRACE=0):
        t = GT.DemoTuner("nvidia", unstable_at=60)
        runs = []

        def mk(tt):
            r = _Run(hang=True)
            runs.append(r)
            return r
        cfg = Cfg(gpu_tune={"profile": None, "orig": {}, "active": False})
        tune = GT.AutoTune(cfg, t, mk, step_s=0, verify_s=0)
        tune.start()
        time.sleep(0.01)
        assert tune.tick() == "failed" and tune.result["why"] == "gt.tune.base_bad"
        assert runs[0].stopped and t.state["offset"] == 0


# ── H4: вентилятори NVIDIA ──
class _FakeNvml:
    """Вентилятор 0 керується, на вентиляторі 1 «не підтримується»."""

    def __init__(self):
        self.calls = []

    def nvmlDeviceSetFanSpeed_v2(self, h, i, pct):
        self.calls.append(("set", i))
        return GT.NVML_OK if i == 0 else GT.NVML_NOT_SUPPORTED

    def nvmlDeviceSetDefaultFanSpeed_v2(self, h, i):
        self.calls.append(("default", i))
        return GT.NVML_OK

    def nvmlDeviceSetFanControlPolicy(self, h, i, pol):
        return GT.NVML_OK


def test_nvml_fan_auto_resets_fans_after_not_supported():
    t = GT.NvmlTuner.__new__(GT.NvmlTuner)
    GT.Tuner.__init__(t)
    t.lib, t.h, t.fan_count, t._fans_set, t.uuid = _FakeNvml(), None, 2, set(), ""
    t.caps = dict(fan=dict(count=2, min=30, max=100, mode="manual", auto=True))
    assert not t.fan_set(60)
    assert "fan" not in t.caps  # «не підтримується» прибирає можливість з інтерфейсу…
    assert t.fan_auto()        # …але вентилятор 0 таки повертається драйверу
    assert ("default", 0) in t.lib.calls


# ── M2, M7: карта після збою, запис журналу ──
def test_startup_crash_uses_pending_card_not_profile():
    opened = []
    with _Env(), patched(GT.SESSION, open=lambda name="", vendor="", index=None: opened.append((name, vendor, index))
                         or GT.DemoTuner(vendor or "nvidia", name)):
        cfg = Cfg(gpu_tune=dict(profile=dict(gpu="nvidia:0:Card A"), pending=dict(key="nvidia:1:Card B", ts=1),
                                orig={}, enabled=True))
        out = GT.startup(cfg)
        assert out["crashed"] and opened[0] == ("Card B", "nvidia", 1)


def test_reset_record_is_quoted_powershell():
    t = GT.DemoTuner("nvidia")
    t.index = 1
    import gpubench as GB
    with patched(GB, self_command=lambda: [r"C:\Users\Tom&Jerry\100%\OptimaX.exe"]):
        code = GT.reset_command(t)
    assert "'C:\\Users\\Tom&Jerry\\100%\\OptimaX.exe'" in code and "--index=1" in code and "WaitForExit" in code
    with _Env() as j:
        cfg = Cfg(gpu_tune={"orig": {}})
        GT.remember_original(cfg, t)
        rec = j.get(GT.journal_id(t))["undo"][0]
        assert rec["t"] == "ps" and E.valid_undo(rec)


# ── M5, L1: 0 МБ перевіреної пам'яті ──
def test_zero_mb_tested_is_not_pass():
    r = HT.ram_result(dict(state="done", mb=0, errors=0), {"ram_gb": 16}, 8000)
    assert r["status"] == HT.NA
    v = VT.vram_result(dict(state="done", mb=0, errors=0, oom=True), {})
    assert v["status"] == HT.NA


def test_ram_child_explicit_zero_allocates_nothing():
    out = os.path.join(_tmp(), "ram.json")
    HT.ram_child({"mb": "0"}, out)
    import json
    with open(out) as f:
        st = json.load(f)
    assert st["mb"] == 0 and st["state"] == "done"


def test_vram_diff_count():
    a = bytes(1 << 20)
    b = bytearray(a)
    b[5] ^= 1
    b[1000] ^= 0xFF
    assert VT._diff_count(a, bytes(b)) == 2 and VT._diff_count(a, a) == 0


# ── H3: тест диска ──
def test_disk_test_refuses_link_and_keeps_foreign_file():
    root = _tmp()
    target = os.path.join(root, "victim")
    os.makedirs(target)
    link = os.path.join(root, HT.DISK_DIR)
    os.symlink(target, link)
    out = os.path.join(root, "d.json")
    HT.disk_child({"dir": link, "mb": "16"}, out)
    import json
    with open(out) as f:
        assert json.load(f)["error"] == "link"
    # файл із нашим іменем, якого цей запуск не створював, лишається (CREATE_NEW / O_EXCL не вдався)
    folder = os.path.join(root, "own", HT.DISK_DIR)
    os.makedirs(folder)
    foreign = os.path.join(folder, f"bench-{os.getpid()}.tmp")
    _put(foreign, b"keep")
    try:
        HT.disk_child({"dir": folder, "mb": "16"}, out)
    except OSError:
        pass  # процес тесту повідомить про помилку сам (hw_child_main)
    assert os.path.isfile(foreign)


# ── L3: аварійна зупинка ──
def test_danger_uses_acpi_zone_when_source_reads_low():
    s = [dict(temp=40, zone=HT.CPU_TEMP_STOP + 1)] * HT.HOT_SECONDS
    assert HT.danger(s) == "cpu"


# ── L2: зупинка без очікування в потоці інтерфейсу ──
def test_testproc_stop_does_not_block():
    class _P:
        pid = 0

        def poll(self):
            return None

    tp = HT.TestProc.__new__(HT.TestProc)
    tp.out, tp.proc, tp.stopped = os.path.join(_tmp(), "x.json"), _P(), False
    t0 = time.time()
    tp.stop()
    assert time.time() - t0 < 2 and tp.stopped and tp.kill_at > time.time()
