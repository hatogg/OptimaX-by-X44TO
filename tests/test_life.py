"""OptimaX 6.6: «Чому впав комп?» (журнал Windows -> збої), бібліотека ігор (сесії, обкладинки, запуск, FPS),
QR-код, монітор на телефоні, звіт про помилку, «Що нового», перенесення налаштувань."""
import json
import os
import struct
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from _util import IS_WIN, ROOT, skip

sys.path.insert(0, ROOT)
import crashlog as CL  # noqa: E402
import features as F  # noqa: E402
import library as LB  # noqa: E402


class _Cfg:
    """Тимчасово підмінені ключі налаштувань (і повернення після тесту)."""

    def __init__(self, **kw):
        self.kw = kw

    def __enter__(self):
        self.old = {k: F.CFG[k] for k in self.kw}
        for k, v in self.kw.items():
            F.CFG[k] = v
        return self

    def __exit__(self, *a):
        for k, v in self.old.items():
            F.CFG[k] = v


# ── «Чому впав комп?» ──
def ev(eid, ts, props=(), prov=None):
    prov = prov or {41: "Microsoft-Windows-Kernel-Power", 1001: "Microsoft-Windows-WER-SystemErrorReporting",
                    6008: "EventLog", 4101: "Display"}.get(eid, "x")
    return dict(id=eid, prov=prov, ts=ts, props=list(props), msg="")


def test_crash_incidents_from_the_event_log():
    t = 1_800_000_000
    events = [
        ev(41, t, ["0", "0", "0", "0", "0", "0", "0"]), ev(6008, t + 5),                      # живлення / зависання
        ev(41, t - 86400, ["278", "1", "0", "0", "0", "0", "0"]),                              # синій екран 0x116
        ev(1001, t - 86400 + 30, ["0x00000116 (0xffff, 0x1, 0x2, 0x3)", r"C:\Windows\MEMORY.DMP", "id"]),
        ev(41, t - 2 * 86400, ["0", "0", "0", "0", "0", "0", "133333333333"]),                 # кнопка живлення
        ev(1001, t - 3 * 86400, ["0x0000001a (0x41790, 0x1, 0x2, 0x3)", "C:\\x.dmp", "id"]),     # лише 1001 — теж збій
        ev(41, t - 4 * 86400, ["0"], prov="Something-Else"),                                    # чужа подія з id 41
        ev(4101, t - 100, ["nvlddmkm", ""]), ev(4101, t - 50, ["nvlddmkm", ""]),
        ev(19, t - 10, prov="Microsoft-Windows-WHEA-Logger"),
        ev(1201, t - 20, prov="Microsoft-Windows-MemoryDiagnostics-Results"),
    ]
    incs = CL.incidents(events)
    assert [(i["kind"], i["code"], i["category"]) for i in incs] == [
        ("power", 0, "power"), ("bsod", 0x116, "gpu"), ("button", 0, "button"), ("bsod", 0x1A, "memory")], incs
    assert incs[1]["name"] == "VIDEO_TDR_FAILURE" and incs[1]["dump"].endswith("MEMORY.DMP")
    assert sorted(incs[0]["events"]) == [41, 6008], "41 and 6008 of the same crash are one incident"
    assert CL.gpu_resets(events) == {"n": 2, "last": t - 50, "driver": "nvlddmkm"}
    assert CL.hardware_errors(events)["n"] == 1
    assert CL.memory_test(events)["ok"] is False
    assert CL.describe_code(0x124) == ("WHEA_UNCORRECTABLE_ERROR", "hardware")
    assert CL.describe_code(0xDEAD)[1] == "unknown"


def test_which_game_was_running_when_the_pc_crashed():
    boot = 1_800_000_000
    sessions = [dict(exe="old.exe", name="Old", start=boot - 9000, last=boot - 8000, end=boot - 8000),
                dict(exe="primetanki.exe", name="Prime Tanki", start=boot - 1800, last=boot - 240, end=boot - 240,
                     lost=True),
                dict(exe="later.exe", name="Later", start=boot + 60, last=boot + 600, end=None)]
    inc = dict(ts=boot, kind="power", category="power")
    assert CL.running_at(inc, sessions)["name"] == "Prime Tanki"
    assert CL.running_at(dict(inc, ts=boot + 10 * 3600), sessions) == {}, "too long ago — not this crash"
    assert CL.advice(inc, {"name": "Prime Tanki"}, mining=True)[0] == "game_mining"
    assert "game_mining" not in CL.advice(inc, {"name": "X"}, mining=False)
    assert CL.advice(dict(category="memory"), {}, False) == ["memtest", "xmp"]


def test_bugcheck_code_from_dump_headers():
    d = tempfile.mkdtemp(prefix="oxdmp_")
    h64 = bytearray(0x60)
    h64[:8] = b"PAGEDU64"
    struct.pack_into("<I", h64, 0x38, 0x116)
    h32 = bytearray(0x60)
    h32[:8] = b"PAGEDUMP"
    struct.pack_into("<I", h32, 0x28, 0x7E)
    for n, b in (("a.dmp", h64), ("b.dmp", h32), ("c.dmp", b"junk"), ("x.txt", h64)):
        with open(os.path.join(d, n), "wb") as f:
            f.write(bytes(b))
    got = {x["name"]: x["code"] for x in CL.dumps(d)}
    assert got == {"a.dmp": 0x116, "b.dmp": 0x7E, "c.dmp": 0}, got


def test_crash_analysis_in_demo_mode():
    if IS_WIN:
        skip("demo events exist only outside Windows")
    import engine as E
    old = E.DEMO
    E.DEMO = "mining"
    try:
        res = CL.analyze(sessions=[], mining=True)
    finally:
        E.DEMO = old
    assert [i["kind"] for i in res["incidents"]] == ["power", "bsod"]
    title, text = CL.explain(res["incidents"][1])
    assert "VIDEO_TDR_FAILURE" in title and text
    assert res["gpu"]["n"] == 2 and res["whea"]["n"] == 1


# ── бібліотека ──
def test_sessions_play_time_and_lost_sessions():
    games = [dict(key="c:\\g\\a", name="Alpha", store="steam", dir="c:\\g\\a", exes=["alpha.exe"], main="")]
    with _Cfg(play={}, library={"games": games, "fps": True, "boost": True}, games=[]):
        tr = LB.Tracker()
        t0 = 1_800_000_000
        assert tr.tick({"alpha.exe", "explorer.exe"}, t0) == {"started": ["alpha.exe"], "ended": []}
        assert tr.started_at("alpha.exe") == t0
        tr.tick({"alpha.exe"}, t0 + 300)
        assert tr.tick(set(), t0 + 600) == {"started": [], "ended": ["alpha.exe"]}
        assert LB.play_time(["alpha.exe"]) == 600 and LB.last_played(["alpha.exe"]) == t0 + 600
        tr2 = LB.Tracker()
        tr2.tick({"alpha.exe"}, t0 + 1000)
        tr2.tick({"alpha.exe"}, t0 + 1100)  # потім комп вимкнувся — сесія не закрилася
        assert LB.close_lost() == 1
        s = LB.sessions()[-1]
        assert s["lost"] and s["end"] == t0 + 1100
        assert LB.play_time(["alpha.exe"]) == 700
        assert CL.running_at(dict(ts=t0 + 1300), LB.sessions())["exe"] == "alpha.exe"


def test_fps_history_and_schedule():
    with _Cfg(game_fps={}):
        now = 1_800_000_000
        assert not LB.fps_due("a.exe", now - 60, 0, now), "not before 2 minutes of play"
        assert LB.fps_due("a.exe", now - 600, 0, now)
        assert not LB.fps_due("a.exe", now - 600, now - 60, now), "a recent attempt — wait"
        LB.add_fps("a.exe", dict(avg=88.4, low1=51.0, low01=40.0, stutters_pm=1.5, smooth=80.0, series=[1, 2]))
        h = LB.fps_history(["a.exe"])
        assert len(h) == 1 and h[0]["avg"] == 88.4 and "series" not in h[0]


def test_steam_covers_both_cache_layouts_and_launch_targets():
    root = tempfile.mkdtemp(prefix="oxsteam_")
    cache = os.path.join(root, "appcache", "librarycache")
    os.makedirs(os.path.join(cache, "730", "abc123"))
    old = os.path.join(cache, "570_library_600x900.jpg")
    new = os.path.join(cache, "730", "abc123", "library_600x900.jpg")
    for p in (old, new):
        open(p, "wb").close()
    assert LB.cover({"appid": "570"}, root) == old
    assert LB.cover({"appid": "730"}, root) == new
    assert LB.cover({"appid": "999"}, root) == "" and LB.cover({"appid": ""}, root) == ""
    assert LB.launch_target({"appid": "730"}) == "steam://rungameid/730"
    assert LB.launch_target({"epic": "Fortnite:x"}).startswith("com.epicgames.launcher://apps/Fortnite%3Ax?")
    assert LB.launch_target({"ubi": "635"}) == "uplay://launch/635/0"
    assert LB.launch_target({"main": "C:\\g\\a.exe"}) == "C:\\g\\a.exe"
    assert LB.launch_target({}) == ""


def test_library_entries_from_discovery():
    g = dict(name="Game", store="steam", dir="C:\\G", appid="10", exes=[
        dict(path="C:\\G\\launcher.exe", api="other", arch="x64"), dict(path="C:\\G\\bin\\game.exe", api="dx11",
                                                                         arch="x64")])
    e = LB.entry(g)
    assert e["exes"] == ["game.exe"] and e["main"] == "C:\\G\\bin\\game.exe" and e["appid"] == "10"
    assert LB.fmt_hours(0) == "—"


# ── QR-код ──
def test_qr_versions_and_decoding():
    import qr
    assert [qr.capacity(v) for v in (1, 2, 3, 10)] == [14, 26, 42, 213]
    url = "http://192.168.1.23:8765/k3j4h5g6f7d8s9a0/"
    m = qr.encode(url)
    assert len(m) == 29 and all(len(r) == 29 for r in m), "42 bytes fit version 3 (29x29)"
    assert len(qr.encode(url + "x")) == 33, "43 bytes need version 4"
    assert m[0][:7] == [True] * 7 and m[6][:7] == [True] * 7, "finder pattern in the corner"
    try:
        qr.encode("x" * 300)
        raise AssertionError("too long text must be refused")
    except ValueError:
        pass
    try:
        import cv2
        import numpy as np
    except ImportError:
        skip("OpenCV is not installed — decoding is not checked")
    det = [cv2.QRCodeDetector()]
    if hasattr(cv2, "QRCodeDetectorAruco"):
        det.append(cv2.QRCodeDetectorAruco())
    for text in (url, "HELLO", "Привіт OptimaX", "z" * 150, "q" * 200):
        mat = qr.encode(text)
        n = len(mat)
        ok = False
        for d in det:
            for scale in (8, 10, 13):
                img = np.full((n + 8, n + 8), 255, np.uint8)
                for y, row in enumerate(mat):
                    for x, v in enumerate(row):
                        if v:
                            img[y + 4, x + 4] = 0
                big = cv2.resize(img, ((n + 8) * scale,) * 2, interpolation=cv2.INTER_NEAREST)
                if d.detectAndDecode(big)[0] == text:
                    ok = True
                    break
            if ok:
                break
        assert ok, text


# ── монітор на телефоні ──
def test_phone_monitor_serves_only_with_the_code():
    import phonemon as PH
    assert PH.allowed("192.168.1.5") and PH.allowed("10.0.0.2") and PH.allowed("127.0.0.1") and \
        PH.allowed("172.20.1.1") and PH.allowed("169.254.3.4") and PH.allowed("::1")
    assert not PH.allowed("8.8.8.8") and not PH.allowed("172.32.0.1") and not PH.allowed("junk")
    fw = PH.firewall
    PH.firewall = lambda *a, **k: None  # правила брандмауера тест не чіпає
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    mon = PH.Monitor()
    try:
        with _Cfg(phone={"token": "testcode123", "port": port}):
            res = mon.start()
            assert res.get("ok"), res
            base = f"http://127.0.0.1:{mon.port}"
            page = urllib.request.urlopen(f"{base}/testcode123/", timeout=5).read().decode("utf-8")
            assert "OptimaX" in page and "fetch('api'" in page
            data = json.loads(urllib.request.urlopen(f"{base}/testcode123/api", timeout=5).read())
            assert "ts" in data
            for bad in ("/", "/wrong/", "/wrong/api", "/testcode123/x"):
                try:
                    urllib.request.urlopen(base + bad, timeout=5)
                    raise AssertionError(bad)
                except urllib.error.HTTPError as e:
                    assert e.code == 404, bad
            time.sleep(1.5)  # збір показників іде лише поки сторінку дивляться
            data = json.loads(urllib.request.urlopen(f"{base}/testcode123/api", timeout=5).read())
            assert "cpu" in data and "gpu" in data, data
    finally:
        mon.stop(remember=False)
        PH.firewall = fw


# ── звіт про помилку ──
def test_bug_report_hides_user_and_fits_the_url():
    import bugreport as BR
    home = os.path.expanduser("~")
    trace = (f'Traceback (most recent call last):\n  File "{home}{os.sep}AppData{os.sep}x.py", line 1, in f\n'
             f"ValueError: mail me@example.com\n")
    title, body = BR.build("crash", trace, hw={"cpu": "Intel i5-3570", "gpus": [("HD 4000", 0, "")]},
                           log_tail=["line"] * 100)
    assert home not in body and "%USERPROFILE%" in body and "<email>" in body
    assert "Intel i5-3570" in body and title.startswith(f"[") and "ValueError" in title
    url = BR.issue_url(title, body + "x" * 20000)
    assert len(url) <= BR.MAX_URL + 50 and url.startswith("https://github.com/")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["title"] == [title]


def test_bug_report_asks_once_per_error_and_native_crash_needs_an_unclean_exit():
    import bugreport as BR
    asked = []
    saved = dict(BR._state, seen=set(BR._state["seen"]))
    BR._state.update(handler=lambda trace, native: asked.append(trace), seen=set())
    try:
        for _ in range(5):  # помилка в таймері раз у кілька секунд — одне вікно
            BR._report("Traceback\nValueError: in timer")
        for i in range(5):
            BR._report(f"Traceback\nKeyError: {i}")
        assert len(asked) == BR.MAX_ASK and asked[0].endswith("in timer"), asked
    finally:
        BR._state.update(saved)
    native, mark = BR.NATIVE_FILE, BR.RUN_MARK
    d = tempfile.mkdtemp(prefix="oxbr_")
    BR.NATIVE_FILE, BR.RUN_MARK = os.path.join(d, "crash-native.txt"), os.path.join(d, "running.flag")
    boot = BR._boot_ts
    try:
        with open(BR.NATIVE_FILE, "w") as f:
            f.write("Windows fatal exception: access violation\n")
        assert BR.native_crash() == "", "closed normally (no run mark) — not a crash"
        for since_boot, expect in ((False, ""), (True, "access violation")):
            with open(BR.NATIVE_FILE, "w") as f:
                f.write("Windows fatal exception: access violation\n")
            open(BR.RUN_MARK, "w").close()
            # Windows перезавантажилася після запуску OptimaX (вимкнули ПК з програмою в треї) — це не збій програми
            BR._boot_ts = (lambda: time.time() - 3600) if since_boot else (lambda: time.time() + 60)
            got = BR.native_crash()
            assert (expect in got) if expect else got == "", (since_boot, got)
            assert os.path.getsize(BR.NATIVE_FILE) == 0, "the file is emptied once read"
    finally:
        BR.NATIVE_FILE, BR.RUN_MARK, BR._boot_ts = native, mark, boot


# ── «Що нового» ──
def test_whats_new_once_per_version_and_never_on_first_install():
    import engine as E
    import whatsnew as WN
    with _Cfg(first_run=True, seen_version=None):
        assert WN.pending() == "" and F.CFG["seen_version"] == E.VERSION, "a fresh install doesn't see «what's new»"
    with _Cfg(first_run=False, seen_version="0.0"):
        assert WN.pending() == (E.VERSION if WN.notes() else "")
        WN.mark_seen()
        assert WN.pending() == ""


# ── перенесення налаштувань ──
def test_settings_transfer_round_trip():
    import engine as E
    import transfer as TR
    d = tempfile.mkdtemp(prefix="oxtr_")
    exe = os.path.join(d, "game.exe")
    open(exe, "wb").close()
    path = os.path.join(d, "s.json")
    with _Cfg(booster=dict(F.CFG["booster"], profile="stable", kill=False),
              games=[{"path": exe, "prio": True, "dgpu": False, "fso": False, "boost": True, "cores": False,
                      "profile": "latency"}, {"path": os.path.join(d, "gone.exe"), "boost": True}],
              library={"fps": False, "boost": True}):
        n = TR.export(path)
        assert n["games"] == 2
        data = TR.load(path)
        assert data["format"] == TR.FORMAT and data["booster"]["profile"] == "stable"
    data["tweaks"] = ["disable_xbox_gamebar", "no_such_tweak_id"]
    p = TR.plan(data, {})
    assert "no_such_tweak_id" in p["unknown"] and p["games"] == [exe] and len(p["missing"]) == 1
    assert ("disable_xbox_gamebar" in p["tweaks"]) != E.JOURNAL.has("disable_xbox_gamebar")
    with _Cfg(booster=dict(F.CFG["booster"]), games=[], library={"fps": True, "boost": True}, mining=F.CFG["mining"]):
        res = TR.apply_settings(data)
        assert F.CFG["booster"]["profile"] == "stable" and F.CFG["library"]["fps"] is False
        assert res["games"] == [exe] and [g["path"] for g in F.CFG["games"]] == [exe]
        assert F.CFG["games"][0].get("profile") == "latency" and not F.CFG["games"][0].get("prio"), \
            "system-changing flags are applied only through the journal"
        assert TR.game_options(data) == [(exe, "prio")]
    try:
        bad = os.path.join(d, "bad.json")
        with open(bad, "w") as f:
            json.dump({"x": 1}, f)
        TR.load(bad)
        raise AssertionError("a foreign file must be refused")
    except ValueError:
        pass
