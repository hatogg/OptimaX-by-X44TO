"""OptimaX — «Датчики» в Hardware Center: поточне / мін / макс / середнє, групування за пристроями, пороги з
гістерезисом, CSV (формат і відмова писати за посиланням), розбір регістрів PawnIO, демо-показники, і що панель не
опитує датчики, поки її не видно (крім запису в CSV)."""
import json
import os
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, env_for, has_qt, skip, tail

sys.path.insert(0, ROOT)
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
import sensors as S  # noqa: E402


def r(rid, value, gkind="cpu", group=None, unit="c", always=True, title="T"):
    return S.reading(rid, group or rid.split(".")[0], gkind, title, "sn.r.temp", unit, value, always=always)


# ── агрегування ──
def test_stat_min_max_avg_and_reset():
    st = S.Stat()
    for v in (50, 70, None, 60):
        st.add(v)
    assert st.cur == 60 and st.min == 50 and st.max == 70 and st.avg == 60.0 and st.n == 3
    st.add(None)  # датчик замовк: поточне невідоме, але min/max/avg не зіпсовано
    assert st.cur is None and st.min == 50 and st.max == 70
    st.add(float("nan"))
    st.add(True)  # не число, хоч і int
    assert st.n == 3
    st.reset()
    assert (st.cur, st.min, st.max, st.avg, st.n) == (None, None, None, None, 0)


def test_hub_feed_hides_unseen_capabilities_and_resets():
    hub = S.Hub({})
    rows = hub.feed([r("cpu.temp", None), r("gpu0.fan", None, "gpu", always=False), r("cpu.load", 40, unit="pct")])
    assert [x["id"] for x in rows] == ["cpu.temp", "cpu.load"], "fan never read -> no row; always -> «—» row"
    hub.feed([r("gpu0.fan", 55, "gpu", always=False)])
    rows = hub.feed([r("gpu0.fan", None, "gpu", always=False)])
    assert [x["id"] for x in rows] == ["gpu0.fan"], "seen once -> stays, now as «—»"
    assert hub.stats["gpu0.fan"].max == 55 and hub.stats["gpu0.fan"].cur is None
    hub.reset()
    assert hub.stats["gpu0.fan"].max is None and hub.stats["cpu.load"].n == 0


def test_fmt_units():
    assert S.fmt(None, "c") == "—"
    assert S.fmt(64.26, "c") == "64.3" and S.fmt(4301.4, "mhz") == "4301" and S.fmt(1.1324, "v") == "1.132"
    assert S.unit_text("c") == "°C" and S.unit_text("pct") == "%" and S.unit_text("mhz") == "MHz"


# ── групування ──
def test_grouping_order_by_device():
    rows = [r("disk1.temp", 36, "hdd", "disk1"), r("board.acpi", 40, "board"), r("ram.used", 8, "ram", unit="gb"),
            r("gpu1.temp", 60, "gpu", "gpu1"), r("cpu.temp", 50), r("disk0.temp", 41, "ssd", "disk0"),
            r("gpu0.temp", 55, "gpu", "gpu0"), r("gpu1.load", 90, "gpu", "gpu1", unit="pct"), r("cpu.load", 3)]
    groups = S.group_rows(rows)
    assert [g["id"] for g, _ in groups] == ["cpu", "gpu1", "gpu0", "ram", "disk1", "disk0", "board"]
    gpu1 = dict((g["id"], rs) for g, rs in groups)["gpu1"]
    assert [x["id"] for x in gpu1] == ["gpu1.temp", "gpu1.load"]
    assert [x["id"] for x in dict((g["id"], rs) for g, rs in groups)["cpu"]] == ["cpu.temp", "cpu.load"]


# ── пороги й гістерезис ──
def test_alert_hold_hysteresis_no_spam():
    al, lim = S.Alerts(hold=3, hyst=5.0), dict(S.DEFAULT_LIMITS)
    seq = [96, 97, 94, 96, 97, 98, 99, 93, 91, 96, 90, 89, 96, 96, 96]
    events = []
    for i, v in enumerate(seq):
        up, down = al.update([r("cpu.temp", v)], lim)
        events += [(i, "up")] * len(up) + [(i, "down")] * len(down)
    # 96,97 → сплеск без 3 поспіль; 96,97,98 → сповіщення; 93,91,96 ще в гістерезисі; 90 (= 95−5) → знято;
    # далі 96×3 → нове сповіщення
    assert events == [(5, "up"), (10, "down"), (14, "up")], events


def test_alert_exactly_at_limit_and_silent_sensor():
    al, lim = S.Alerts(hold=1), dict(S.DEFAULT_LIMITS)
    assert al.update([r("cpu.temp", 95)], lim) == ([], []), "Ryzen 7000 holds 95 °C by design: only above alerts"
    up, _ = al.update([r("gpu0.temp", 88, "gpu", "gpu0")], lim)
    assert len(up) == 1 and up[0][1] == 87
    assert al.update([r("gpu0.temp", None, "gpu", "gpu0")], lim) == ([], []) and "gpu0.temp" in al.active
    # не температура і не той вид пристрою — порогів немає
    assert al.update([r("cpu.load", 100, unit="pct"), r("board.acpi", 120, "board")], lim) == ([], [])
    assert S.limit_kind(r("disk0.temp", 1, "hdd")) == "hdd" and S.limit_kind(r("disk0.temp", 1, "ssd")) == "ssd"


def test_limits_from_settings_are_sanitized():
    class Cfg(dict):
        def __getitem__(self, k):
            return self.get(k)
    assert S.load_limits(Cfg()) == dict(on=True, **S.DEFAULT_LIMITS)
    got = S.load_limits(Cfg(sensor_alerts={"on": False, "cpu": 999, "gpu": True, "ssd": "70; calc.exe", "hdd": 50}))
    assert got == {"on": False, "cpu": 95, "gpu": 87, "ssd": 70, "hdd": 50}


# ── CSV ──
COLS = [("cpu.temp", "Intel Core i7", "Temperature · Core Temp", "c"), ("cpu.vid", "Intel Core i7", "VID", "v"),
        ("gpu0.load", "RTX 4070, OC", "Load", "pct")]


def test_csv_header_and_rows():
    assert S.csv_header(COLS) == ["Time", "Intel Core i7 / Temperature · Core Temp [°C]", "Intel Core i7 / VID [V]",
                                  "RTX 4070, OC / Load [%]"]
    row = S.csv_row(1_700_000_000, COLS, {"cpu.temp": 64.26, "cpu.vid": None, "gpu0.load": 97.0})
    assert row[1:] == ["64.3", "", "97"], "dot decimal, unit precision, unknown is empty (not 0)"
    line = S.csv_line(["Time", "RTX 4070, OC / Load [%]"])
    assert line == 'Time,"RTX 4070, OC / Load [%]"\r\n'


def test_csv_log_writes_new_file_and_refuses_links():
    d = tempfile.mkdtemp(prefix="oxsn_")
    path = os.path.join(d, "log.csv")
    with open(path, "w") as f:
        f.write("old content")
    log = S.CsvLog(path, COLS)
    log.write(1_700_000_000, {"cpu.temp": 50.0})
    log.write(1_700_000_001, {"cpu.temp": 51.0, "gpu0.load": 3})
    log.close()
    raw = open(path, "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf") and b"old content" not in raw
    lines = raw.decode("utf-8-sig").splitlines()
    assert len(lines) == 3 and lines[2].endswith(",51.0,,3")
    if IS_WIN:
        return  # symlink на Windows потребує привілею; is_reparse там перевіряє тест secfs
    victim = os.path.join(d, "victim.txt")
    with open(victim, "w") as f:
        f.write("keep")
    link = os.path.join(d, "link.csv")
    os.symlink(victim, link)
    linked_dir = os.path.join(d, "linkdir")
    os.symlink(d, linked_dir)
    for bad in (link, os.path.join(linked_dir, "x.csv"), d):
        try:
            S.CsvLog(bad, COLS)
            assert False, f"must refuse {bad}"
        except PermissionError:
            pass
    assert open(victim).read() == "keep"
    assert not os.path.exists(os.path.join(d, "x.csv"))


# ── регістри PawnIO ──
def test_msr_decoders():
    assert S.tjmax_of(100 << 16) == 100 and S.tjmax_of(0) is None and S.tjmax_of(None) is None
    pkg = 38 << 16  # відлік 38 до TjMax
    assert S.intel_temp(100, pkg) == 62
    assert S.intel_temp(100, pkg, need_valid=True) is None, "core status without the valid bit"
    assert S.intel_temp(100, pkg | 1 << 31, need_valid=True) == 62
    assert S.energy_unit(0x000A0E03) == 1 / 2**14 and S.energy_unit(0) is None
    unit = 1 / 2**14
    assert S.rapl_watts(1000, 1000 + 2**14 * 65, unit, 1.0) == 65.0
    assert S.rapl_watts(0xFFFFFF00, 0x100, unit, 1.0) == round(0x200 * unit, 1), "32-bit counter wraps"
    assert S.rapl_watts(None, 5, unit, 1.0) is None and S.rapl_watts(1, 5, unit, 0) is None
    # 7.2: після паузи (розділ ховали) — не середнє за всю паузу і не сміття від переповнення
    assert S.rapl_watts(1000, 1000 + 2**14 * 65 * 4200, unit, 4200.0) is None
    assert S.rapl_watts(1000, 1000 + 2**14 * 65 * 3, unit, 3.0) == 65.0
    assert S.amd_tctl(int(65.5 * 8) << 21) == 65.5
    assert S.amd_tctl((int(60 * 8) << 21) | 1 << 19) == 11.0, "range select: −49 °C"
    assert S.amd_tctl(0) is None


def test_msr_power_reseeds_after_pause():
    class Live:
        drv = None
        energy = 0

        def msr(self, reg):
            return {0xC0010299: 0x000A0E03, 0xC001029B: self.energy}.get(reg)

        def read(self):
            return {}
    live, clock = Live(), [100.0]
    real = S.time.monotonic
    S.time.monotonic = lambda: clock[0]
    try:
        m = S.MsrReader(live, "AMD")
        unit = 1 / 2**14
        powers = []
        for dt, watts in ((1, 0), (1, 65), (1, 65), (4200, 65), (1, 65)):
            clock[0] += dt
            live.energy = (live.energy + int(watts * dt / unit)) & 0xFFFFFFFF
            powers.append(m.read().get("power"))
    finally:
        S.time.monotonic = real
    assert powers == [None, 65.0, 65.0, None, 65.0], powers


def test_hub_close_during_read_closes_reader_after_it():
    import threading
    started, go, closed = threading.Event(), threading.Event(), []

    class Reader:
        def read(self):
            started.set()
            go.wait(5)
            return [r("cpu.temp", 50)]

        def close(self):
            closed.append(1)
    hub = S.Hub({})
    hub.reader = Reader()
    out = []
    t = threading.Thread(target=lambda: out.append(hub.read()))
    t.start()
    assert started.wait(5)
    hub.close()
    assert not closed, "must not close sources under a running read"
    go.set()
    t.join(5)
    assert closed == [1] and hub.reader is None and out and out[0]
    assert hub.read() == [] and hub.reader is None, "no new reader after close"


def test_link_like_only_name_surrogates():
    import stat

    class St:
        st_mode = stat.S_IFDIR

        def __init__(self, attrs, tag):
            self.st_file_attributes, self.st_reparse_tag = attrs, tag
    real = S.os.lstat
    try:
        for tag, want in ((0xA000000C, True), (0xA0000003, True), (0x9000001A, False), (0x9000601A, False),
                          (0x8000001B, False)):  # symlink, junction, OneDrive (cloud), AppExecLink
            S.os.lstat = lambda p, t=tag: St(0x400, t)
            assert S.link_like("x") is want, hex(tag)
        S.os.lstat = lambda p: St(0x10, 0)
        assert S.link_like("x") is False
    finally:
        S.os.lstat = real


def test_csv_log_detects_parent_swapped_after_check():
    if IS_WIN:
        skip("symlink needs a privilege on Windows; GetFinalPathNameByHandle path is checked on CI")
    import secfs as SF
    d = tempfile.mkdtemp(prefix="oxsn_")
    sub, elsewhere = os.path.join(d, "sub"), tempfile.mkdtemp(prefix="oxsn_other_")
    os.mkdir(sub)
    real = SF.remove_then_create

    def swap_then_open(path, *a, **k):  # підміна між перевіркою і відкриттям
        os.rename(sub, sub + "_moved")
        os.symlink(elsewhere, sub)
        return real(path, *a, **k)
    SF.remove_then_create = swap_then_open
    try:
        S.CsvLog(os.path.join(sub, "x.csv"), COLS)
        assert False, "must refuse"
    except PermissionError:
        pass
    finally:
        SF.remove_then_create = real
    assert os.listdir(elsewhere) == [], "the redirected file must be removed"


def test_pdh_gpu_counters_by_luid():
    c = {"eng": {"pid_10_luid_0x00000000_0x0000D6B5_phys_0_eng_0_engtype_3D": 60.0,
                 "pid_22_luid_0x00000000_0x0000d6b5_phys_0_eng_0_engtype_3D": 50.0,
                 "pid_22_luid_0x00000000_0x0000C2E1_phys_0_eng_0_engtype_3D": 4.0},
         "vram": {"luid_0x00000000_0x0000D6B5_phys_0": 3 * 2**30},
         "shared": {"luid_0x00000000_0x0000C2E1_phys_0": 512 * 2**20}}
    got = S.pdh_gpu(c)
    assert got["0x00000000_0x0000D6B5"] == {"util": 100.0, "vram": 3072.0}
    assert got["0x00000000_0x0000C2E1"] == {"util": 4.0, "shared": 512.0}


# ── демо ──
def test_demo_readings_plausible_and_honest():
    if IS_WIN:
        skip("demo hardware only outside Windows")
    import hardware as H
    old = E.DEMO
    try:
        for demo in ("gaming", "laptop", "old", "x3d", "mining"):
            E.DEMO = demo
            hub = S.Hub(H._from_demo(demo))
            for _ in range(3):
                rows = hub.feed(hub.read())
            groups = S.group_rows(rows)
            kinds = [g["kind"] for g, _ in groups]
            assert kinds[0] == "cpu" and "ram" in kinds and "gpu" in kinds, (demo, kinds)
            by = {x["id"]: x for x in rows}
            for x in rows:
                v = x["value"]
                if v is not None and x["unit"] == "c":
                    assert 10 < v < 105, (demo, x)
                if v is not None and x["unit"] == "pct":
                    assert 0 <= v <= 100, (demo, x)
            for x in rows:
                if x["id"].endswith(".vram") and x["value"] is not None:
                    assert x["value"] >= 0
            if demo in ("laptop", "old", "mining"):  # без програм датчиків і PawnIO — чесне «—», а не зона ACPI
                assert by["cpu.temp"]["value"] is None
            else:
                assert by["cpu.temp"]["value"] is not None and by["cpu.temp"]["src"]
            if demo == "x3d":  # AMD: температури Radeon без драйвера не читаємо
                assert not [x for x in rows if x["gkind"] == "gpu" and x["unit"] == "c"]
    finally:
        E.DEMO = old


# ── панель: опитування лише на екрані ──
PANEL = r'''
import json, os, sys, tempfile
sys.path.insert(0, ROOT)
sys.argv = ["x", "--lang=en", "--dry-run"]
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QFileDialog, QWidget
import hardware as H
import sensors as S
import pages_sensors as PS
from ui_kit import vbox

app = QApplication(sys.argv)


def spin(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class Main:
    hw = H.detect_hw()
    toasts = []

    def toast(self, text, kind="ok"):
        self.toasts.append((text, kind))


class Page:
    main = Main()


reads = []
orig = S.Hub.read
S.Hub.read = lambda self: reads.append(1) or orig(self)
w = QWidget()
v = vbox(w)
p = PS.SensorsPanel(Page())
v.addWidget(p)
w.resize(900, 700)
w.show()
spin(2600)
res = {"active": p.timer.isActive(), "reads": len(reads), "groups": len(p.table.groups),
       "h": p.table.height()}
p.hide()
spin(100)
n = len(reads)
spin(1500)
res["hidden_timer"] = p.timer.isActive()
res["hidden_reads"] = len(reads) - n
p.show()
spin(1300)
res["shown_again"] = p.timer.isActive() and len(reads) > n
w.showMinimized()
spin(300)
n = len(reads)
spin(1300)
res["min_timer"] = p.timer.isActive()
res["min_reads"] = len(reads) - n
w.showNormal()
spin(1300)
res["restored"] = p.timer.isActive() and len(reads) > n
out = os.path.join(tempfile.mkdtemp(), "rec.csv")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (out, ""))
p.toggle_record()
p.hide()
spin(2600)
res["rec_hidden_timer"] = p.timer.isActive()
p.stop_record()
res["rec_rows"] = len(open(out, encoding="utf-8-sig").read().splitlines()) - 1
res["after_stop_timer"] = p.timer.isActive()
p.show()
spin(200)
p.reset()
res["reset_max"] = [s.max for s in p.hub.stats.values() if s.n == 0 and s.max is not None]
p.shutdown()
print("RESULT " + json.dumps(res))
'''


def test_panel_polls_only_while_visible_and_records():
    if not has_qt():
        skip("PyQt6 is not installed")
    if IS_WIN:
        skip("demo hardware only outside Windows")
    p = subprocess.run([sys.executable, "-c", "ROOT = %r\n" % ROOT + PANEL], cwd=ROOT, env=env_for("gaming"),
                       capture_output=True, timeout=120)
    out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
    line = next((x for x in reversed(out.splitlines()) if x.startswith("RESULT ")), None)
    assert p.returncode == 0 and line, tail(out)
    res = json.loads(line[7:])
    assert res["active"] and res["reads"] >= 2 and res["groups"] >= 5 and res["h"] > 300, res
    assert not res["hidden_timer"] and res["hidden_reads"] == 0, f"no polling while hidden: {res}"
    assert res["shown_again"], res
    assert not res["min_timer"] and res["min_reads"] == 0 and res["restored"], f"minimized: no timer: {res}"
    assert res["rec_hidden_timer"] and res["rec_rows"] >= 2, f"recording keeps polling while hidden: {res}"
    assert not res["after_stop_timer"], res
    assert res["reset_max"] == [], res
