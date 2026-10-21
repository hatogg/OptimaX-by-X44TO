"""
OptimaX — мережа: тест і вибір найшвидшого DNS (з DNS-over-HTTPS), пінг і джитер до регіонів ігрових
серверів, тест bufferbloat (наскільки зростає пінг, коли канал завантажений).

Пінг міряється часом TCP-з'єднання: більшість ігрових компаній не відповідають на ICMP-ping.
"""
from __future__ import annotations

import json
import random
import socket
import statistics
import struct
import threading
import time
import urllib.request

import engine as E
from i18n import tr

DNS_PROVIDERS = [
    dict(id="cloudflare", name="Cloudflare", ips=("1.1.1.1", "1.0.0.1"), doh="https://cloudflare-dns.com/dns-query"),
    dict(id="google", name="Google", ips=("8.8.8.8", "8.8.4.4"), doh="https://dns.google/dns-query"),
    dict(id="quad9", name="Quad9", ips=("9.9.9.9", "149.112.112.112"), doh="https://dns.quad9.net/dns-query"),
    dict(id="adguard", name="AdGuard", ips=("94.140.14.14", "94.140.15.15"),
         doh="https://dns.adguard-dns.com/dns-query"),
    dict(id="opendns", name="OpenDNS", ips=("208.67.222.222", "208.67.220.220"), doh="https://doh.opendns.com/dns-query"),
]
TEST_DOMAINS = ["google.com", "youtube.com", "steamcommunity.com", "discord.com", "riotgames.com", "twitch.tv",
                "epicgames.com", "microsoft.com"]

# Регіони дата-центрів AWS: на них працюють сервери багатьох онлайн-ігор. Вимірюємо час TCP-з'єднання.
REGIONS = ["eu-central-1", "eu-north-1", "eu-west-1", "eu-west-2", "eu-west-3", "eu-south-1", "me-central-1",
           "us-east-1", "us-west-2", "ap-southeast-1", "ap-northeast-1", "sa-east-1"]
BASELINES = [("cloudflare", "1.1.1.1", 443), ("google", "8.8.8.8", 443)]
LOAD_URL = "https://speed.cloudflare.com/__down?bytes=200000000"


def region_host(code: str) -> str:
    return f"dynamodb.{code}.amazonaws.com"


# ───────────────────────── DNS ─────────────────────────
def _dns_query(server: str, name: str, timeout: float = 1.5):
    """Один запит типу A по UDP. -> час у мс або None."""
    qid = random.randint(0, 0xFFFF)
    head = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    body = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00" + struct.pack(">HH", 1, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        t0 = time.perf_counter()
        s.sendto(head + body, (server, 53))
        while True:
            data, _ = s.recvfrom(1024)
            if len(data) >= 2 and struct.unpack(">H", data[:2])[0] == qid:
                return (time.perf_counter() - t0) * 1000
    except OSError:
        return None
    finally:
        s.close()


DEMO_DNS = {"cloudflare": 9.8, "google": 14.6, "quad9": 21.3, "adguard": 27.9, "opendns": 31.2, "current": 38.5}


def current_dns() -> list:
    """Активні підключення: [{idx, alias, guid, servers, static}]."""
    if not E.IS_WIN:
        return [dict(idx=12, alias="Ethernet", guid="{demo}", servers=["192.168.1.1"], static=False)]
    data = E.ps_json(
        "$r=@(); foreach ($c in Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and "
        "$_.NetAdapter.Status -eq 'Up' }) { $g=$c.NetAdapter.InterfaceGuid; "
        "$ns=(Get-ItemProperty -Path ('HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\' + $g) "
        "-Name NameServer -ErrorAction SilentlyContinue).NameServer; "
        "$r += @{idx=$c.InterfaceIndex; alias=$c.InterfaceAlias; guid=$g; "
        "servers=@($c.DNSServer | Where-Object { $_.AddressFamily -eq 2 } | ForEach-Object { $_.ServerAddresses }); "
        "static=[bool]$ns} }; $r | ConvertTo-Json -Depth 3 -Compress", 40)
    out = []
    for d in E.as_list(data):
        if isinstance(d, dict) and d.get("idx"):
            out.append(dict(idx=int(d["idx"]), alias=str(d.get("alias") or ""), guid=str(d.get("guid") or ""),
                            servers=[str(x) for x in E.as_list(d.get("servers")) if x], static=bool(d.get("static"))))
    return out


def dns_benchmark(log, progress) -> list:
    """-> [{id, name, ips, ms, ok}] від найшвидшого. ms — медіана часу відповіді, ok — частка відповідей."""
    cur = current_dns()
    cur_ips = [ip for c in cur for ip in c["servers"]][:1]
    cands = [dict(p) for p in DNS_PROVIDERS]
    if cur_ips and not any(cur_ips[0] in p["ips"] for p in cands):
        cands.append(dict(id="current", name=tr("net.dns.current"), ips=tuple(cur_ips), doh=None))
    rounds = 3
    total = len(cands) * rounds
    step = 0
    for c in cands:
        times = []
        for r in range(rounds):
            if E.CANCEL.is_set():
                break
            if progress:
                progress(step, total, tr("net.dns.testing", name=c["name"]))
            step += 1
            if not E.IS_WIN:
                base = DEMO_DNS.get(c["id"], 30)
                times += [base * random.uniform(0.85, 1.25) for _ in TEST_DOMAINS]
                continue
            for d in TEST_DOMAINS:
                times.append(_dns_query(c["ips"][0], d))
        good = [t for t in times if t is not None]
        c["ms"] = round(statistics.median(good), 1) if good else None
        c["ok"] = round(len(good) / len(times), 2) if times else 0.0
        log(tr("net.dns.result", name=c["name"], ms=c["ms"] if c["ms"] is not None else "—",
               ok=round(c["ok"] * 100)))
    cands.sort(key=lambda c: (c["ms"] is None, c["ok"] < 0.9, c["ms"] or 9e9))
    return cands


def dns_tweak(provider: dict, doh: bool) -> E.Tweak:
    """Твік із записом у журнал: при відкаті повертаються ваші попередні DNS (або DHCP)."""
    ips = tuple(provider["ips"])

    @E.cmd_doc(f"Set-DnsClientServerAddress -ServerAddresses {', '.join(ips)}" + ("; DNS-over-HTTPS" if doh else ""))
    def apply(ctx: E.Ctx) -> None:
        ifaces = current_dns()
        undo = []
        for c in ifaces:
            if c["static"] and c["servers"]:
                old = ",".join(f"'{s}'" for s in c["servers"])
                undo.append(f"Set-DnsClientServerAddress -InterfaceIndex {c['idx']} -ServerAddresses ({old})")
            else:
                undo.append(f"Set-DnsClientServerAddress -InterfaceIndex {c['idx']} -ResetServerAddresses")
            new = ",".join(f"'{s}'" for s in ips)
            E.ps(f"Set-DnsClientServerAddress -InterfaceIndex {c['idx']} -ServerAddresses ({new})", 30, ctx.log)
            ctx.log(tr("net.dns.set_iface", alias=c["alias"], ips=", ".join(ips)))
        if undo:
            ctx.undo.append({"t": "ps", "c": "; ".join(undo) + "; ipconfig /flushdns"})
        if doh and provider.get("doh") and E.win_build() >= 22000:
            for ip in ips:
                E.ps(f"if (Get-DnsClientDohServerAddress -ServerAddress '{ip}' -ErrorAction SilentlyContinue) "
                     f"{{ Set-DnsClientDohServerAddress -ServerAddress '{ip}' -DohTemplate '{provider['doh']}' "
                     f"-AllowFallbackToUdp $true -AutoUpgrade $true }} else {{ Add-DnsClientDohServerAddress "
                     f"-ServerAddress '{ip}' -DohTemplate '{provider['doh']}' -AllowFallbackToUdp $true "
                     f"-AutoUpgrade $true }}", 30, ctx.log)
            E.exec_op(E.R(r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters", "EnableAutoDoh", 2), ctx)
            ctx.log(tr("net.dns.doh_on"))
        E.run("ipconfig /flushdns", 15, ctx.log)

    t = E.Tweak("dns", "net", [E.F(apply)])
    t._title = tr("net.dns.tweak", name=provider["name"])
    return t


# ───────────────────────── пінг ─────────────────────────
def tcp_ping(host: str, port: int = 443, count: int = 8, timeout: float = 2.0, gap: float = 0.15) -> dict:
    times = []
    try:
        addr = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4]
    except OSError:
        return dict(host=host, avg=None, min=None, jitter=None, loss=100)
    for _ in range(count):
        if E.CANCEL.is_set():
            break
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        t0 = time.perf_counter()
        try:
            s.connect(addr)
            times.append((time.perf_counter() - t0) * 1000)
        except OSError:
            times.append(None)
        finally:
            s.close()
        time.sleep(gap)
    return _ping_stats(host, times)


def _ping_stats(host: str, times: list) -> dict:
    good = [t for t in times if t is not None]
    if not good:
        return dict(host=host, avg=None, min=None, jitter=None, loss=100)
    jit = statistics.mean(abs(a - b) for a, b in zip(good, good[1:])) if len(good) > 1 else 0.0
    return dict(host=host, avg=round(statistics.mean(good), 1), min=round(min(good), 1), jitter=round(jit, 1),
                loss=round(100 * (len(times) - len(good)) / len(times)))


DEMO_PING = {"cloudflare": 6, "google": 9, "eu-central-1": 28, "eu-north-1": 41, "eu-west-1": 61, "eu-west-2": 52,
             "eu-west-3": 46, "eu-south-1": 39, "me-central-1": 104, "us-east-1": 121, "us-west-2": 186,
             "ap-southeast-1": 210, "ap-northeast-1": 248, "sa-east-1": 236}


def ping_regions(codes, log, progress) -> list:
    targets = [(c, h, p, True) for c, h, p in BASELINES] + [(c, region_host(c), 443, False) for c in codes]
    out = []
    for i, (code, host, port, base) in enumerate(targets):
        if E.CANCEL.is_set():
            break
        if progress:
            progress(i, len(targets), tr("net.ping.testing", name=tr(f"net.r.{code}")))
        if not E.IS_WIN:
            b = DEMO_PING.get(code, 80)
            st = _ping_stats(host, [b * random.uniform(0.95, 1.15) for _ in range(8)])
        else:
            st = tcp_ping(host, port)
        st.update(code=code, baseline=base)
        out.append(st)
        log(tr("net.ping.result", name=tr(f"net.r.{code}"), avg=st["avg"] if st["avg"] is not None else "—",
               jitter=st["jitter"] if st["jitter"] is not None else "—", loss=st["loss"]))
    return out


def ping_custom(host: str, log) -> dict:
    host = host.strip()
    port = 443
    if ":" in host and host.count(":") == 1:
        host, p = host.split(":")
        port = int(p) if p.isdigit() else 443
    st = tcp_ping(host, port, 10) if E.IS_WIN else _ping_stats(host, [35 * random.uniform(0.9, 1.2) for _ in range(10)])
    st.update(code="custom", baseline=False)
    log(tr("net.ping.result", name=host, avg=st["avg"] if st["avg"] is not None else "—",
           jitter=st["jitter"] if st["jitter"] is not None else "—", loss=st["loss"]))
    return st


# ───────────────────────── bufferbloat ─────────────────────────
def grade(increase_ms: float) -> str:
    for lim, g in ((5, "A+"), (30, "A"), (60, "B"), (200, "C"), (400, "D")):
        if increase_ms < lim:
            return g
    return "F"


def bufferbloat(log, progress, seconds: int = 10) -> dict:
    """Пінг без навантаження, потім під час завантаження великого файлу. Різниця — це bufferbloat."""
    if not E.IS_WIN:
        for i in range(seconds + 3):
            if progress:
                progress(i, seconds + 3, tr("net.bb.running"))
            time.sleep(0.005)
        idle = 9.0 if E.DEMO != "old" else 24.0
        loaded = idle + (21.0 if E.DEMO != "old" else 168.0)
        res = dict(idle=idle, loaded=loaded, increase=loaded - idle, mbps=310.0 if E.DEMO != "old" else 38.0)
        res["grade"] = grade(res["increase"])
        log(tr("net.bb.result", **res))
        return res
    host, port = "1.1.1.1", 443
    if progress:
        progress(0, seconds + 3, tr("net.bb.idle"))
    idle = tcp_ping(host, port, 10, gap=0.1)
    got, stop = [0], threading.Event()

    def download():
        try:
            req = urllib.request.Request(LOAD_URL, headers={"User-Agent": f"{E.APP_NAME}/{E.VERSION}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                while not stop.is_set():
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    got[0] += len(chunk)
        except Exception:
            pass
    th = threading.Thread(target=download, daemon=True)
    t0 = time.perf_counter()
    th.start()
    loaded = []
    while time.perf_counter() - t0 < seconds and not E.CANCEL.is_set():
        if progress:
            progress(3 + int(time.perf_counter() - t0), seconds + 3, tr("net.bb.loaded"))
        st = tcp_ping(host, port, 1, gap=0.25)
        if st["avg"] is not None:
            loaded.append(st["avg"])
    stop.set()
    span = time.perf_counter() - t0
    th.join(2)
    if idle["avg"] is None or not loaded:
        raise RuntimeError(tr("net.bb.fail"))
    lo = statistics.median(loaded)
    res = dict(idle=idle["avg"], loaded=round(lo, 1), increase=round(lo - idle["avg"], 1),
               mbps=round(got[0] * 8 / span / 1e6, 1))
    res["grade"] = grade(res["increase"])
    log(tr("net.bb.result", **res))
    return res


def save(cfg, key: str, value) -> None:
    data = cfg["net"] or {}
    data[key] = value
    data["ts"] = int(time.time())
    cfg["net"] = json.loads(json.dumps(data))
