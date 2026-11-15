"""OptimaX 6.17: виправлення з аудиту — залізо й мережа. Античити поза ANTICHEAT і системні драйвери античитів,
точний розмір диска для читання поверхні, DNS-фільтр не слухає на CGNAT-адресах, залишок сесії WPR після вбитого
ловця, окремий ліміт подій 4101, чесний результат зміни DNS."""
import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import types

from _util import ROOT

sys.path.insert(0, ROOT)
import adblock as AB  # noqa: E402
import crashlog as CL  # noqa: E402
import engine as E  # noqa: E402
import freezecatch as FZ  # noqa: E402
import hwtests as HT  # noqa: E402
import mining as MG  # noqa: E402
import netlab as N  # noqa: E402


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
    return tempfile.mkdtemp(prefix="ox617hw_")


def _touch(*parts, folder=False):
    p = os.path.join(*parts)
    if folder:
        os.makedirs(p, exist_ok=True)
    else:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").close()
    return p


# ───────────────────────── 1. античит ─────────────────────────
def test_anticheat_new_file_patterns_in_game_folder():
    cases = {
        ("EAAntiCheat", "EAAntiCheat.GameServiceLauncher.exe"): "EA Javelin",
        ("bin", "EAAC_Installer.exe"): "EA Javelin",
        ("AntiCheatExpert", "x.dat"): "ACE",
        ("Win64", "ACE-Base64.sys"): "ACE",
        ("NeacSafe64.sys",): "NetEase",
        ("bin", "NeacClient.exe"): "NetEase",
        ("FACEIT", "faceit.exe"): "FACEIT",
        ("Denuvo Anti-Cheat", "denuvo-anti-cheat.sys"): "Denuvo Anti-Cheat",
        ("vgk.sys",): "Vanguard",
        ("EasyAntiCheat", "EasyAntiCheat_EOS_Setup.exe"): "EasyAntiCheat",  # як і раніше
    }
    for parts, want in cases.items():
        d = _tmp()
        _touch(d, *parts)
        assert MG.anticheat(d) == want, (parts, MG.anticheat(d))


def test_anticheat_patterns_do_not_catch_ordinary_files():
    d = _tmp()
    for n in ("ace-editor.js", "Facebook.dll", "eaa.txt", "neac.txt", "denuvo.dll", "ace.dll", "game.exe"):
        _touch(d, "data", n)
    assert MG.anticheat(d) == ""


def _fake_reg(present):
    present = {s.lower() for s in present}

    def reg_get(path, name):
        svc = path.rsplit("\\", 1)[-1].lower()
        if path.lower().startswith(MG.SERVICES_KEY.lower() + "\\") and svc in present and name == "Start":
            return 4, 1
        return None
    return reg_get


RIOT = dict(name="VALORANT", dir=r"C:\Riot Games\VALORANT\live",
            exes=[dict(path=r"C:\Riot Games\VALORANT\live\ShooterGame\Binaries\Win64\VALORANT-Win64-Shipping.exe")])
CS2 = dict(name="Counter-Strike 2", dir=r"D:\Steam\steamapps\common\Counter-Strike Global Offensive",
           exes=[dict(path=r"D:\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\cs2.exe")])
OLD = dict(name="Half-Life", dir=r"D:\Steam\steamapps\common\Half-Life",
           exes=[dict(path=r"D:\Steam\steamapps\common\Half-Life\hl.exe")])


def test_system_vanguard_blocks_only_riot_games():
    with patched(E, IS_WIN=True, reg_get=_fake_reg({"vgk", "vgc"})):
        svcs = MG.system_services()
        assert svcs == {"vgk", "vgc"}
        assert MG.system_anticheat(RIOT, svcs) == "Vanguard"
        assert MG.system_anticheat(CS2, svcs) == "" and MG.system_anticheat(OLD, svcs) == "", \
            "a system-wide Vanguard must not block games that are not Riot's"
        assert MG.system_anticheat(RIOT) == "Vanguard", "without a precomputed set the registry is read"


def test_system_faceit_and_eac_only_for_their_games():
    with patched(E, IS_WIN=True, reg_get=_fake_reg({"FACEIT", "EasyAntiCheat_EOS", "BEService"})):
        svcs = MG.system_services()
        assert MG.system_anticheat(CS2, svcs) == "FACEIT"
        assert MG.system_anticheat(OLD, svcs) == ""
        fortnite = dict(dir=r"C:\Program Files\Epic Games\Fortnite",
                        exes=[dict(path=r"C:\Program Files\Epic Games\Fortnite\FortniteGame\Binaries\Win64\FortniteClient"
                                        r"-Win64-Shipping.exe")])
        assert MG.system_anticheat(fortnite, svcs) == "EasyAntiCheat"
        gta = dict(dir=r"D:\Games\Grand Theft Auto V", exes=[dict(path=r"D:\Games\Grand Theft Auto V\GTA5.exe")])
        assert MG.system_anticheat(gta, svcs) == "BattlEye"
    with patched(E, IS_WIN=True, reg_get=_fake_reg(set())):
        assert MG.system_services() == set() and MG.system_anticheat(RIOT) == ""


def test_system_anticheat_is_off_outside_windows_and_feeds_compat():
    with patched(E, IS_WIN=False, reg_get=_fake_reg({"vgk"})):
        assert MG.system_services() == set() and MG.system_anticheat(RIOT) == ""
        assert [g.get("anticheat") for g in MG.discover() if g["name"] == "Fortnite"] == ["EasyAntiCheat"], \
            "demo games are unchanged"
    g = dict(RIOT, anticheat="Vanguard", risk="", exes=[dict(RIOT["exes"][0], api="dx9", arch="x64")])
    assert "anticheat" in MG.compat(g, "dxvk"), "a system anti-cheat blocks layers like one in the game folder"


# ───────────────────────── 2. читання поверхні диска ─────────────────────────
def test_scan_limit_prefers_exact_size_and_never_overshoots_rounded_gb():
    assert HT.scan_limit(62_537_072_640, 0, 63) == 62_537_072_640
    assert HT.scan_limit(0, "62537072640", "63") == 62_537_072_640, "size_bytes from the page (as a CLI string)"
    emmc = 62_537_072_640  # 62.54 GB, size_gb = round() = 63
    assert HT.scan_limit(0, 0, round(emmc / 1e9)) <= emmc
    vhd = 50 * 2 ** 30  # 50 GiB = 53.69 GB, size_gb = 54
    assert HT.scan_limit(0, 0, round(vhd / 1e9)) <= vhd
    assert HT.scan_limit(0, 0, 0) == 0 and HT.scan_limit(0, None, None) == 0 and HT.scan_limit(0, 0, "x") == 0
    assert HT.scan_limit(0, 0, 1) == 0, "below 2 GB nothing is left after the 1 GB margin — unknown"


def _scan(size, real, seconds=0.3):
    """_scan_loop на «диску» розміром real: читання за кінцем повертає None (як ERROR_HANDLE_EOF)."""
    seen = []

    def read_at(off):
        seen.append(off)
        return None if off + HT.SCAN_BLOCK > real else True
    out = os.path.join(_tmp(), "s.json")
    state = dict(state="running", reads=0, read_errors=0, slow=0)
    HT._scan_loop(read_at, size, seconds, out, state, [])
    return state, seen


def test_surface_scan_reads_stay_inside_the_disk():
    real = 62_537_072_640
    for size in (real, HT.scan_limit(0, 0, 63)):
        st, seen = _scan(size, real)
        assert st["reads"] > 0 and st["read_errors"] == 0 and st["state"] == "done", st
        assert max(seen) + HT.SCAN_BLOCK <= real


def test_surface_scan_unknown_size_does_not_count_past_end_as_errors():
    real = 3 * 2 ** 30  # маленький диск при запасних 256 ГіБ: майже всі перші читання — за кінцем
    st, seen = _scan(0, real, seconds=0.5)
    assert st["read_errors"] == 0 and st["reads"] > 0, st
    tail = seen[-50:]
    assert all(o + HT.SCAN_BLOCK <= real for o in tail), "after hitting the end the range shrinks to the real disk"


def test_surface_scan_real_errors_still_count():
    out = os.path.join(_tmp(), "s.json")
    state = dict(state="running", reads=0, read_errors=0, slow=0)
    HT._scan_loop(lambda off: False, 10 * HT.SCAN_BLOCK, 0.1, out, state, [])
    assert state["reads"] > 0 and state["read_errors"] == state["reads"]
    state = dict(state="running", reads=0, read_errors=0, slow=0)
    HT._scan_loop(lambda off: None, 0, 0.1, out, state, [])
    assert state["read_errors"] > 0, "a disk that cannot be read even at offset 0 is an error, not the end"


def test_surface_scan_child_accepts_size_gb_argument():
    out = os.path.join(_tmp(), "s.json")
    state = dict(state="running", kind="disk", mode="scan")
    with patched(E, IS_WIN=False):
        HT._surface_scan(dict(device="x", seconds="0.2", size="0", size_gb="63"), out, state)
    with open(out, encoding="utf-8") as f:
        st = json.load(f)
    assert st["state"] == "done" and st["read_errors"] == 0 and st["reads"] > 0, st


def test_hwcenter_passes_exact_bytes_to_the_scan():
    src = open(os.path.join(ROOT, "pages_hwcenter.py"), encoding="utf-8").read()
    assert 'size=int(d.get("size_bytes") or 0)' in src and "size_gb=d.get(\"size_gb\")" in src
    assert '* 1e9)))' not in src.split("def start_scan", 1)[1].split("def ", 1)[0]


# ───────────────────────── 3. DNS-фільтр: де слухати ─────────────────────────
def test_bind_ok_only_home_ranges():
    for ip in ("192.168.1.50", "10.0.0.2", "172.16.5.4", "172.31.255.1", "fd12:3456::1", "fe80::1%12",
               "169.254.3.3"):
        assert AB._bind_ok(ip), ip
    for ip in ("100.64.0.1", "100.127.1.1", "8.8.8.8", "172.32.0.1", "198.18.0.1", "2001:db8::1", "junk", ""):
        assert not AB._bind_ok(ip), ip
    assert AB._client_ok("100.64.0.1"), "CGNAT stays an allowed client (Tailscale); it is only never bound"


def test_lan_mode_does_not_bind_cgnat_address():
    bound = []
    srv = types.SimpleNamespace(bind=lambda ip, port, quiet=False: bound.append(ip) or True)
    me = types.SimpleNamespace(server=srv, port=53, cfg={"lan": True}, lan_ips=[],
                               info={"adapters": [{"ips": ["100.72.10.5", "192.168.0.10", "169.254.1.1", "8.8.4.4"]},
                                                  {"ips": ["10.1.2.3"]}]})
    assert AB.Service.bind_all(me)
    assert me.lan_ips == ["192.168.0.10", "10.1.2.3"], me.lan_ips
    assert "100.72.10.5" not in bound


# ───────────────────────── 4. залишок сесії WPR ─────────────────────────
def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _wpr_trace(status, replies):
    d = _tmp()
    if status is not None:
        with open(os.path.join(d, "status.json"), "w", encoding="utf-8") as f:
            json.dump(status, f)
    calls = []

    def run(cmd, timeout=None, log=None, **kw):
        calls.append(cmd[1])
        return replies.pop(0) if cmd[1] == "-start" and replies else (0, "")
    with patched(E, DRY_RUN=False, run=run), patched(FZ, wpr_path=lambda: "wpr.exe"):
        t = FZ.DeepTrace(d)
        ok = t.start()
    return ok, calls, t


def test_deep_trace_cancels_leftover_of_a_dead_catcher():
    ok, calls, _t = _wpr_trace(dict(pid=_dead_pid(), deep={"on": True}), [])
    assert ok and calls == ["-cancel", "-start"], calls


def test_deep_trace_keeps_a_live_or_stopped_session_alone():
    ok, calls, _t = _wpr_trace(dict(pid=os.getppid(), deep={"on": True}), [])
    assert ok and calls == ["-start"], "a running catcher's session is not cancelled"
    ok, calls, _t = _wpr_trace(dict(pid=_dead_pid(), deep={"on": True}, stopped=True), [])
    assert calls == ["-start"], "a cleanly stopped catcher already cancelled its trace"
    ok, calls, _t = _wpr_trace(dict(pid=_dead_pid(), deep={"on": False}), [])
    assert calls == ["-start"]


def test_deep_trace_retries_once_after_already_running():
    msg = "Profiles are already running.\n\nError code: 0xc5583001"
    ok, calls, t = _wpr_trace(None, [(1, msg), (0, "")])
    assert ok and calls == ["-start", "-cancel", "-start"] and t.error == "", calls
    ok, calls, t = _wpr_trace(None, [(1, msg), (1, msg)])
    assert not ok and calls == ["-start", "-cancel", "-start"], "only one retry"
    ok, calls, t = _wpr_trace(None, [(5, "Access is denied")])
    assert not ok and calls == ["-start"] and "denied" in t.error, "other failures are not retried"


# ───────────────────────── 5. журнал збоїв: окремий ліміт для 4101 ─────────────────────────
def test_crash_events_query_gives_4101_its_own_budget():
    ps = CL.EVENTS_PS.format(days=30)
    ids = re.findall(r"Id=([\d,]+)", ps)
    assert "41,6008,1001" in ids and "4101" in ids and not any("4101" in x and "41," in x for x in ids), ids
    assert ps.count("-MaxEvents") == 1 and "-MaxEvents $x[1]" in ps and "-FilterHashtable $x[0]" in ps
    assert len(re.findall(r"@\(@\{.*\}, \d+\)", ps)) == 5
    got = {}

    def ps_json(script, timeout=40):
        got["s"] = script
        return [dict(id=41, prov="Microsoft-Windows-Kernel-Power", ts=1, props=["0"], msg=""),
                dict(id=4101, prov="Display", ts=2, props=["nvlddmkm", ""], msg="")]
    with patched(E, IS_WIN=True, ps_json=ps_json):
        evs = CL.read_events(7)
    assert "AddDays(-7)" in got["s"] and [e["id"] for e in evs] == [41, 4101], "output format is unchanged"


# ───────────────────────── 6. зміна DNS: код повернення ─────────────────────────
IFACES = [dict(idx=12, alias="Ethernet", guid="{a}", servers=["192.168.1.1"], static=False),
          dict(idx=17, alias="Wi-Fi", guid="{b}", servers=["1.1.1.1"], static=True)]
PROV = dict(id="cloudflare", name="Cloudflare", ips=["1.1.1.1", "1.0.0.1"],
            doh="https://cloudflare-dns.com/dns-query")


def _apply_dns(fail_on=(), doh=False):
    cmds, regs = [], []

    def ps(script, timeout=30, log=None, **kw):
        cmds.append(script)
        return (1, "Access denied") if any(f in script for f in fail_on) else (0, "")
    log, real = [], E.exec_op

    def exec_op(op, ctx):  # сам твік виконується справді; запис у реєстр (EnableAutoDoh) лише запам'ятовуємо
        return real(op, ctx) if op[0] == "fn" else regs.append(op)
    with patched(E, IS_WIN=True, DRY_RUN=True, ps=ps, run=lambda *a, **k: (0, ""), win_build=lambda: 22631,
                 exec_op=exec_op), patched(N, current_dns=lambda: [dict(x) for x in IFACES]):
        t = N.dns_tweak(PROV, doh)
        ctx = E.Ctx(log.append, journal=E.Journal(os.path.join(_tmp(), "back.json")))
        res = E.run_tweak(t, ctx)
    return res, ctx, log, regs


def test_dns_refused_on_one_adapter_is_partial_and_not_recorded():
    res, ctx, log, _regs = _apply_dns(fail_on=("-InterfaceIndex 12 -ServerAddresses",))
    assert res == "partial" and ctx.failed == ["dns Ethernet"], (res, ctx.failed)
    undo = " ".join(u["c"] for u in ctx.undo if u.get("t") == "ps")
    assert "-InterfaceIndex 17" in undo and "-InterfaceIndex 12" not in undo, undo
    assert not any("Ethernet" in str(x) and "1.1.1.1" in str(x) for x in log), "no «set» line for the refused adapter"
    assert E.Journal(ctx.journal.path).has("dns")


def test_dns_refused_everywhere_is_a_failure():
    res, ctx, _log, _regs = _apply_dns(fail_on=("Set-DnsClientServerAddress",))
    assert res is False and len(ctx.failed) == 2 and not ctx.undo, (res, ctx.failed)
    assert not E.Journal(ctx.journal.path).has("dns"), "nothing changed — nothing in the undo journal"


def test_doh_refused_is_reported_and_auto_doh_not_enabled():
    res, ctx, log, regs = _apply_dns(fail_on=("DohServerAddress",), doh=True)
    assert res == "partial" and ctx.failed == ["doh 1.1.1.1", "doh 1.0.0.1"], (res, ctx.failed)
    assert not regs, "EnableAutoDoh is not switched on when no server accepted the DoH template"
    res, ctx, log, regs = _apply_dns(fail_on=("-ServerAddress '1.0.0.1' -ErrorAction",), doh=True)
    assert res == "partial" and ctx.failed == ["doh 1.0.0.1"] and len(regs) == 1


def test_dns_all_ok_is_still_applied():
    res, ctx, _log, regs = _apply_dns(doh=True)
    assert res is True and not ctx.failed and len(regs) == 1
