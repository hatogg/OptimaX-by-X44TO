"""Аудит 7.1.1, мережа й оновлення: DNS-фільтр (окремий пул TCP, перевірка відповіді вгорі), зміна DNS і DoH з
відкатом на кожен крок, лапки PowerShell, режим гри (без realtime), cdb без змінних _NT_*, звіт про помилку без IP і
токена, обкладинки Steam без повторного перегляду кешу, settings.json без зайвого перезапису, збірка Mesa/DXVK лише
з digest. Жодна справжня системна команда не виконується."""
import contextlib
import os
import socket
import struct
import sys
import tempfile
import threading
import time

from _util import ROOT

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "packaging"))
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxnet_")
import adblock as AB  # noqa: E402
import bugreport as BR  # noqa: E402
import dumpanalyzer as DA  # noqa: E402
import engine as E  # noqa: E402
import features as F  # noqa: E402
import library as LB  # noqa: E402
import netlab as N  # noqa: E402
import release as REL  # noqa: E402
import updater as U  # noqa: E402

TYPO = "a\u2019b\u2018c'd"


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


# ── B4 / B16: лапки PowerShell і адреси DNS ──
def test_ps_quote_doubles_typographic_quotes():
    for q in (U._ps_quote, AB._ps_quote):
        assert q(TYPO) == "'a\u2019\u2019b\u2018\u2018c''d'", q(TYPO)


def test_dns_servers_for_powershell_are_validated():
    assert AB._ps_servers(["127.0.0.1", "1.1.1.1'); calc; ('", "::1", "fe80::1%12"]) == "'127.0.0.1','::1','fe80::1%12'"
    assert N._ps_ips(["8.8.8.8", "x\u2019; calc"]) == "'8.8.8.8'"
    assert AB._ps_idx(12) == 12 and AB._ps_idx("17") == 17
    assert AB._ps_idx("12; calc") is None and AB._ps_idx(True) is None


# ── B10: DNS і DoH — запис відкату до зміни, на кожен крок ──
IFACES = [dict(idx=12, alias="Ethernet", guid="{a}", servers=["192.168.1.1"], static=False),
          dict(idx=17, alias="Wi-Fi", guid="{b}", servers=["9.9.9.9"], static=True)]
PROV = dict(id="cloudflare", name="Cloudflare", ips=["1.1.1.1", "1.0.0.1"], doh="https://cloudflare-dns.com/dns-query")


def _apply_dns(answer):
    """answer(script) -> (rc, out). -> (результат, ctx, [команди], [довжина журналу відкату перед кожною])."""
    cmds, undo_len = [], []
    ctx_box = {}

    def ps(script, timeout=30, log=None, **kw):
        cmds.append(script)
        undo_len.append(len(ctx_box["ctx"].undo))
        return answer(script)
    real = E.exec_op
    with patched(E, IS_WIN=True, DRY_RUN=True, ps=ps, run=lambda *a, **k: (0, ""), win_build=lambda: 22631,
                 exec_op=lambda op, ctx: real(op, ctx) if op[0] == "fn" else None), \
            patched(N, current_dns=lambda: [dict(x) for x in IFACES]):
        t = N.dns_tweak(PROV, True)
        ctx = ctx_box["ctx"] = E.Ctx(lambda *_: None)
        res = E.run_tweak(t, ctx)
    return res, ctx, cmds, undo_len


def test_dns_undo_is_recorded_per_adapter_before_the_change_and_kept_on_timeout():
    def answer(s):
        if "-InterfaceIndex 17 -ServerAddresses" in s:
            return E.TIMEOUT_RC, "[TIMEOUT]"
        return 0, ""
    res, ctx, cmds, undo_len = _apply_dns(answer)
    ps_undo = [u["c"] for u in ctx.undo if u.get("t") == "ps"]
    assert any("-InterfaceIndex 12 -ResetServerAddresses" in c for c in ps_undo), ps_undo
    assert any("-InterfaceIndex 17 -ServerAddresses ('9.9.9.9')" in c for c in ps_undo), "timeout keeps the undo"
    i12 = next(i for i, c in enumerate(cmds) if "-InterfaceIndex 12 -ServerAddresses" in c)
    i17 = next(i for i, c in enumerate(cmds) if "-InterfaceIndex 17 -ServerAddresses" in c)
    assert undo_len[i12] == 1 and undo_len[i17] == 2, "the record goes in before each adapter's command"
    assert res == "partial" and "dns Wi-Fi" in ctx.failed


def test_doh_registration_is_undone_remove_for_new_set_back_for_existing():
    def answer(s):
        if s.startswith("if (-not (Get-Command Get-DnsClientDohServerAddress"):
            if "'1.0.0.1'" in s:
                return 0, '{"t":"https://old.example/dns-query","f":false,"a":true}'
            return 0, ""  # 1.1.1.1 — запису не було
        return 0, ""
    res, ctx, cmds, _ = _apply_dns(answer)
    ps_undo = [u["c"] for u in ctx.undo if u.get("t") == "ps"]
    assert res is True, (res, ctx.failed)
    assert "Remove-DnsClientDohServerAddress -ServerAddress '1.1.1.1' -ErrorAction SilentlyContinue" in ps_undo
    assert ("Set-DnsClientDohServerAddress -ServerAddress '1.0.0.1' -DohTemplate 'https://old.example/dns-query' "
            "-AllowFallbackToUdp $false -AutoUpgrade $true") in ps_undo, ps_undo


def test_doh_state_not_read_means_no_change():
    def answer(s):
        return (1, "boom") if s.startswith("if (-not (Get-Command") else (0, "")
    res, ctx, cmds, _ = _apply_dns(answer)
    assert ctx.failed == ["doh 1.1.1.1", "doh 1.0.0.1"], ctx.failed
    assert not any("Add-DnsClientDohServerAddress" in c for c in cmds), "no DoH change without an undo record"


# ── B8 / B9: DNS-фільтр ──
def _query(name=b"\x07example\x03com\x00", qid=0x1234) -> bytes:
    return struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + name + b"\x00\x01\x00\x01"


def test_udp_query_ignores_spoofed_and_mismatched_answers():
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    spoof = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    wire = _query()

    def upstream():
        data, addr = srv.recvfrom(4096)
        assert data[2:] == wire[2:]
        sid = data[:2]
        spoof.sendto(sid + b"\x81\x80" + data[4:] + b"SPOOF", addr)  # та сама ID, інша адреса відправника
        srv.sendto(sid + b"\x81\x80" + _query(b"\x05other\x03com\x00")[4:], addr)  # інше запитання
        srv.sendto(sid + b"\x81\x80" + data[4:] + b"GOOD", addr)
    th = threading.Thread(target=upstream, daemon=True)
    th.start()
    try:
        got = AB.udp_query("127.0.0.1", wire, 2.0, port)
    finally:
        th.join(3)
        srv.close()
        spoof.close()
    assert got[:2] == wire[:2] and got.endswith(b"GOOD"), got


def test_udp_query_uses_its_own_random_id():
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    ids = []

    def upstream():
        for _ in range(3):
            data, addr = srv.recvfrom(4096)
            ids.append(data[:2])
            srv.sendto(data[:2] + b"\x81\x80" + data[4:], addr)
    th = threading.Thread(target=upstream, daemon=True)
    th.start()
    try:
        for _ in range(3):
            assert AB.udp_query("127.0.0.1", _query(), 2.0, srv.getsockname()[1])[:2] == b"\x12\x34"
    finally:
        th.join(3)
        srv.close()
    assert len(set(ids)) > 1 or ids[0] != b"\x12\x34", ids


def test_idle_tcp_clients_do_not_block_udp():
    class R:
        def resolve(self, data, q):
            return AB.make_response(q, 0), "up"

    class Flt:
        def check(self, name):
            return False, None

    class St:
        def add(self, *a, **k):
            pass
    srv = AB.DnsServer(Flt(), R(), St(), {"blocking": False})
    assert srv.tcp_pool is not srv.pool and AB.TCP_MAX <= 16 and AB.TCP_IDLE <= 3
    assert srv.bind("127.0.0.1", 0, quiet=True)
    u, t = srv.socks
    port_u, port_t = u.getsockname()[1], t.getsockname()[1]
    idle = []
    try:
        for _ in range(AB.TCP_MAX + 40):
            c = socket.create_connection(("127.0.0.1", port_t), 2)
            idle.append(c)
        time.sleep(0.3)
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        c.settimeout(2)
        c.sendto(_query(), ("127.0.0.1", port_u))
        data, _ = c.recvfrom(4096)
        c.close()
        assert data[:2] == b"\x12\x34", "UDP answered while TCP clients sit idle"
    finally:
        for c in idle:
            c.close()
        srv.stop()


# ── B5: режим гри не ставить realtime і не чіпає чужі процеси ──
def test_booster_restores_only_high_priority_and_never_realtime():
    import monitor as M
    sets = []
    cfg = F.Config(os.path.join(tempfile.mkdtemp(prefix="oxnet_"), "settings.json"))
    cfg["booster_state"] = {"prio": [[100, "game.exe", 0x100], [101, "game.exe", 0x20], [102, "game.exe", 0x20],
                                     [103, "other.exe", 0x20]]}
    prios = {100: 0x80, 101: 0x80, 102: 0x20, 103: 0x80}
    with patched(E, IS_WIN=True, DRY_RUN=True, run=lambda *a, **k: (0, ""),
                 processes=lambda: [(100, "game.exe"), (101, "game.exe"), (102, "game.exe"), (103, "x.exe")]), \
            patched(M, _get_priority=lambda pid: prios.get(pid, 0), _set_priority=lambda pid, c: sets.append((pid, c))):
        F.GameBooster(cfg).stop(lambda *_: None)
    assert sets == [(101, 0x20)], sets
    assert 0x100 not in F.PRIORITY_CLASSES


# ── D8: settings.json не переписується без змін, але зміна на місці зберігається ──
def test_config_skips_identical_rewrite_but_saves_in_place_changes():
    cfg = F.Config(os.path.join(tempfile.mkdtemp(prefix="oxnet_"), "settings.json"))
    cfg["x"] = 1
    m = os.stat(cfg.path).st_mtime_ns
    os.utime(cfg.path, ns=(m - 10**9, m - 10**9))
    cfg["x"] = 1
    assert os.stat(cfg.path).st_mtime_ns == m - 10**9, "same value — no rewrite"
    lst = cfg["games"]
    lst.append({"path": "a"})
    cfg["games"] = lst
    assert F.Config(cfg.path)["games"] == [{"path": "a"}], "a list changed in place is still saved"


# ── B6: cdb без _NT_* і INIT ──
def test_cdb_env_drops_debugger_variables():
    os.environ["_NT_DEBUGGER_EXTENSION_PATH"] = r"C:\Users\x\evil"
    os.environ["_nt_symbol_path"] = r"C:\Users\x\sym"
    os.environ["INIT"] = r"C:\Users\x"
    try:
        env = DA.cdb_env(os.path.join("C:", "Kits", "cdb.exe"))
    finally:
        for k in ("_NT_DEBUGGER_EXTENSION_PATH", "_nt_symbol_path", "INIT"):
            os.environ.pop(k, None)
    assert "INIT" not in env and not any(k.upper() == "_NT_SYMBOL_PATH" for k in env)
    assert env["_NT_DEBUGGER_EXTENSION_PATH"] == os.path.join("C:", "Kits", "winext")


# ── B13: звіт про помилку ──
def test_bug_report_masks_ip_and_phone_token():
    s = BR.sanitize("monitor http://192.168.1.50:8765/AbC_d-12xyZ0/ ok, dns 1.1.1.1, v6 2001:db8::1 fe80::1%12")
    assert "192.168" not in s and "AbC_d-12xyZ0" not in s and "1.1.1.1" not in s and "2001:db8" not in s, s
    assert "http://<ip>:8765/<token>/" in s
    keep = BR.sanitize("Windows 10.0.19045.5737, OptimaX 7.1.1, 12:30:45, x[1::2], 127.0.0.1")
    assert keep == "Windows 10.0.19045.5737, OptimaX 7.1.1, 12:30:45, x[1::2], 127.0.0.1", keep


# ── D3: обкладинки — корінь кешу переглядається один раз ──
def test_cover_lists_the_steam_cache_once():
    root = tempfile.mkdtemp(prefix="oxsteam_")
    cache = os.path.join(root, "appcache", "librarycache")
    os.makedirs(os.path.join(cache, "730", "h1"))
    for n in ("570_library_600x900.jpg", "570_header.jpg", "10_header.jpg"):
        open(os.path.join(cache, n), "wb").close()
    open(os.path.join(cache, "730", "h1", "header.jpg"), "wb").close()
    calls = []
    real = os.listdir
    LB.reset_covers()
    with patched(os, listdir=lambda p: calls.append(p) or real(p)):
        assert LB.cover({"appid": "570"}, root).endswith("570_library_600x900.jpg")
        assert LB.cover({"appid": "10"}, root).endswith("10_header.jpg")
        assert LB.cover({"appid": "730"}, root).endswith(os.path.join("730", "h1", "header.jpg"))
        assert LB.cover({"appid": "999"}, root) == ""
    assert calls.count(cache) == 1, calls


# ── B3: Mesa / DXVK — лише з digest GitHub і закріпленою сумою ──
def test_release_assets_need_a_digest_and_the_pinned_sum():
    import pytest
    sha = "0" * 64
    with pytest.raises(SystemExit):
        REL._check_digest(REL.DXVK_REPO, "dxvk-9.9.tar.gz", None, sha)
    with pytest.raises(SystemExit):
        REL._check_digest(REL.DXVK_REPO, "dxvk-9.9.tar.gz", "sha256:" + "1" * 64, sha)
    REL._check_digest(REL.DXVK_REPO, "dxvk-9.9.tar.gz", "sha256:" + sha, sha)
    with pytest.raises(SystemExit):  # закріплена версія з іншим вмістом — навіть з «правильним» digest
        REL._check_digest(REL.DXVK_REPO, "dxvk-2.6.2.tar.gz", "sha256:" + sha, sha)
