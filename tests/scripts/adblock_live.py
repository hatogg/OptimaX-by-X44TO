"""Справжня перевірка DNS-фільтра: сокети, списки, кеш, TCP, API, DoH через локальний TLS-сервер.
Порти вибираються вільні (на Windows 5353 зайнятий mDNS)."""
import _boot
import datetime
import http.server
import os
import random
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time

sys.argv = _boot.argv("--lang=uk")
import adblock as AB  # noqa: E402


def free_port() -> int:
    for _ in range(50):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            u.bind(("127.0.0.1", 0))
            port = u.getsockname()[1]
            t.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            u.close()
            t.close()
    raise RuntimeError("no free port")


fails = []


def check(cond, what):
    print(("  ok  " if cond else "  FAIL") + "  " + what)
    if not cond:
        fails.append(what)


def build_query(name, qtype=1, edns=None, qid=None):
    qid = random.randint(0, 0xFFFF) if qid is None else qid
    ar = 1 if edns else 0
    head = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, ar)
    body = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00" + struct.pack(">HH", qtype, 1)
    if edns:
        body += b"\x00" + struct.pack(">HHIH", 41, edns, 0, 0)
    return head + body


def answers(resp):
    """-> (rcode, [(type, rdata)], tc)"""
    rc = resp[3] & 0xF
    tc = bool(resp[2] & 0x02)
    qd, an = struct.unpack(">HH", resp[4:8])
    i = 12
    for _ in range(qd):
        i = AB._skip_name(resp, i) + 4
    out = []
    for _ in range(an):
        i = AB._skip_name(resp, i)
        t, c, ttl, ln = struct.unpack(">HHIH", resp[i:i + 10])
        out.append((t, resp[i + 10:i + 10 + ln], ttl))
        i += 10 + ln
    return rc, out, tc


# ── фальшивий «інтернет-DNS» на 127.0.0.1:5399 ──
UP_PORT = free_port()
SVC_PORT = free_port()
DOH_PORT = free_port()
upstream_hits = []


def up_answer(data):
    q = AB.parse_query(data)
    upstream_hits.append(q.name)
    if q.name == "big.test":
        txt = b"".join(bytes([200]) + b"x" * 200 for _ in range(4))
        rr = b"\xc0\x0c" + struct.pack(">HHIH", 16, 1, 120, len(txt)) + txt
        return AB.make_response(q, 0, rr, 1)
    if q.name.endswith("nx.test"):
        return AB.make_response(q, 3)
    if q.qtype == 1:
        rr = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 300, 4) + bytes([93, 184, 216, 34])
        return AB.make_response(q, 0, rr, 1)
    return AB.make_response(q)


def up_udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", UP_PORT))
    while True:
        d, a = s.recvfrom(4096)
        r = up_answer(d)
        if len(r) > 512:
            r = AB.truncate(r, AB.parse_query(d))
        s.sendto(r, a)


def up_tcp():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", UP_PORT))
    s.listen(8)
    while True:
        c, _ = s.accept()
        n = struct.unpack(">H", AB._recv_exact(c, 2))[0]
        r = up_answer(AB._recv_exact(c, n))
        c.sendall(struct.pack(">H", len(r)) + r)
        c.close()


threading.Thread(target=up_udp, daemon=True).start()
threading.Thread(target=up_tcp, daemon=True).start()
time.sleep(0.2)

print("── розбір списків")
hosts = "# StevenBlack\n0.0.0.0 ads.example.com\n127.0.0.1 tracker.test  # comment\n0.0.0.0 localhost\n0.0.0.0 0.0.0.0\n"
wild = "# HaGeZi\nadnet.test\n*.metrics.test\nbad_host.test\n"
adb = "! AdGuard\n||adserver.test^\n||cdn.test^$denyallow=x.com\n@@||good.test^\n/regex/\n||popup.test^$important\n"
e1, w1 = AB.parse_list(hosts, "hosts")
e2, w2 = AB.parse_list(wild, "wild")
e3, w3 = AB.parse_list(adb, "adblock")
check(e1 == {"ads.example.com", "tracker.test"} and not w1, f"hosts: {sorted(e1)}")
check(w2 == {"adnet.test", "metrics.test", "bad_host.test"} and not e2, f"wild: {sorted(w2)}")
check(w3 == {"adserver.test", "popup.test"} and not e3, f"adblock: {sorted(w3)}")
AB.save_compiled("stevenblack", e1, w1)
AB.save_compiled("hagezi_pro", e2, w2)
AB.save_compiled("adguard_dns", e3, w3)
check(AB.load_compiled("hagezi_pro") == (e2, w2), "компіляція списку і завантаження")

cfg = AB.load_cfg()
cfg.update(lists=["stevenblack", "hagezi_pro", "adguard_dns"], doh=False, block=["*.custom.test"],
           allow=["ok.adnet.test"], port=SVC_PORT)
AB.save_cfg(cfg)
f = AB.Filter.from_disk(cfg)
cases = {"ads.example.com": True, "x.ads.example.com": False, "tracker.test": True, "adnet.test": True,
         "a.b.adnet.test": True, "ok.adnet.test": False, "adserver.test": True, "sub.adserver.test": True,
         "good.test": False, "zz.custom.test": True, "custom.test": True, "use-application-dns.net": True,
         "github.com": False, "www.msftconnecttest.com": False, "example.org": False}
got = {k: f.check(k)[0] for k in cases}
check(got == cases, "рішення фільтра: " + ", ".join(k for k in cases if got[k] != cases[k]))
check(f.check("a.b.adnet.test")[1] == "hagezi_pro" and f.check("zz.custom.test")[1] == "custom", "джерело блокування")

print(f"── служба на 127.0.0.1:{SVC_PORT}")
AB.UPSTREAM_PORT = UP_PORT
svc = AB.Service(port=SVC_PORT, system_dns=False, upstream_override=["127.0.0.1"])
rc_holder = {}
th = threading.Thread(target=lambda: rc_holder.setdefault("rc", svc.run()), daemon=True)
th.start()
for _ in range(50):
    if svc.server.binds:
        break
    time.sleep(0.05)
check(f"127.0.0.1:{SVC_PORT}" in svc.server.binds, f"прослуховує: {svc.server.binds}")


def ask(name, qtype=1, **kw):
    return answers(AB.udp_query("127.0.0.1", build_query(name, qtype, **kw), 2.0, SVC_PORT))


rc, an, _ = ask("ads.example.com")
check(rc == 0 and an and an[0][1] == bytes(4) and an[0][2] == AB.BLOCK_TTL, "A заблокованого → 0.0.0.0, TTL 10")
rc, an, _ = ask("ads.example.com", 28)
check(rc == 0 and an and an[0][1] == bytes(16), "AAAA заблокованого → ::")
rc, an, _ = ask("ads.example.com", 65)
check(rc == 0 and not an, "HTTPS заблокованого → порожня відповідь (NODATA)")
rc, an, _ = ask("use-application-dns.net")
check(rc == 3, "канарка Firefox → NXDOMAIN")
upstream_hits.clear()
rc, an, _ = ask("example.org")
check(rc == 0 and an and an[0][1] == bytes([93, 184, 216, 34]) and upstream_hits == ["example.org"],
      "дозволений домен → відповідь сервера")
time.sleep(1.1)
rc, an, _ = ask("example.org")
check(rc == 0 and an and upstream_hits == ["example.org"] and an[0][2] in (298, 299), f"кеш (TTL {an[0][2] if an else '?'})")
rc, an, _ = ask("x.ads.example.com")
check(rc == 0 and an and an[0][1] != bytes(4), "піддомен точного імені з hosts — не блокується")
rc, an, _ = ask("nothing.nx.test")
check(rc == 3, "NXDOMAIN від сервера передається")
_u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_u.settimeout(2)
_u.sendto(build_query("big.test", 16), ("127.0.0.1", SVC_PORT))
_raw, _ = _u.recvfrom(4096)
_u.close()
rc, an, tc = answers(_raw)
check(tc and not an and len(_raw) <= 512, "велика відповідь по UDP без EDNS → TC (клієнт повторить по TCP)")
w = build_query("big.test", 16)
with socket.create_connection(("127.0.0.1", SVC_PORT), 3) as s:
    s.sendall(struct.pack(">H", len(w)) + w)
    n = struct.unpack(">H", AB._recv_exact(s, 2))[0]
    rc, an, tc = answers(AB._recv_exact(s, n))
check(rc == 0 and an and len(an[0][1]) == 804 and not tc, "той самий запит по TCP → повна відповідь")
rc, an, tc = ask("big.test", 16, edns=4096)
check(rc == 0 and an and not tc, "по UDP з EDNS 4096 → повна відповідь")
check(AB._client_ok("192.168.1.23") and AB._client_ok("::1") and AB._client_ok("10.0.0.5") and
      not AB._client_ok("8.8.8.8") and not AB._client_ok("2001:4860::1"), "відповідаємо лише локальним адресам")
bad = svc.server.handle(b"\x00\x01garbage", "127.0.0.1")
check(bad is None, "сміття замість запиту — ігнорується")

print("── API")
c = AB.Client()
st = c.call("GET", "/api/status")
check(st and st["domains"] == len(e1) + len(w2) + len(w3) and st["blocking"], f"статус: {st and st['domains']} доменів")
check(AB.Client.__new__(AB.Client) is not None and AB.Client().call("GET", "/api/status") is not None, "клієнт читає api.json")
bad_c = AB.Client()
bad_c.token = "wrong"
check(bad_c.call("GET", "/api/status") is None, "без правильного ключа API — відмова")
snap = c.call("GET", "/api/stats")
check(snap and snap["today"]["blocked"] >= 4 and snap["today"]["cache"] >= 1 and len(snap["series"]) == 144,
      f"статистика: {snap and snap['today']}")
lg = c.call("GET", "/api/log?n=50&filter=blocked")
check(lg and all(e["status"] == "blocked" for e in lg) and lg[0]["name"] in ("ads.example.com", "use-application-dns.net"),
      f"журнал запитів: {len(lg or [])} заблокованих")
c.call("POST", "/api/pause", {"seconds": 60})
rc, an, _ = ask("tracker.test")
check(rc == 0 and an and an[0][1] == bytes([93, 184, 216, 34]), "пауза → реклама проходить")
c.call("POST", "/api/pause", {"seconds": 0})
rc, an, _ = ask("tracker.test")
check(an and an[0][1] == bytes(4), "після паузи блокування знову працює")
cfg = AB.load_cfg()
cfg["allow"].append("tracker.test")
AB.save_cfg(cfg)
c.call("POST", "/api/reload")
rc, an, _ = ask("tracker.test")
check(an and an[0][1] != bytes(4), "дозволений вручну домен → проходить")

print("── DoH через локальний TLS-сервер (перевірка сертифіката за іменем, з'єднання за IP)")
tmp = tempfile.mkdtemp()
key, crt = os.path.join(tmp, "k.pem"), os.path.join(tmp, "c.pem")


def make_cert() -> bool:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        try:
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt,
                            "-days", "1", "-subj", "/CN=dns.test", "-addext", "subjectAltName=DNS:dns.test"],
                           capture_output=True, check=True)
            return True
        except (OSError, subprocess.CalledProcessError):
            return False
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "dns.test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("dns.test")]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(k, hashes.SHA256()))
    with open(key, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                serialization.NoEncryption()))
    with open(crt, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return True


HAVE_CERT = make_cert()


class DohHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        assert self.headers["Content-Type"] == "application/dns-message" and body[:2] == b"\x00\x00"
        r = up_answer(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/dns-message")
        self.send_header("Content-Length", str(len(r)))
        self.end_headers()
        self.wfile.write(r)


if HAVE_CERT:
    hs = http.server.ThreadingHTTPServer(("127.0.0.1", DOH_PORT), DohHandler)
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    sctx.load_cert_chain(crt, key)
    hs.socket = sctx.wrap_socket(hs.socket, server_side=True)
    threading.Thread(target=hs.serve_forever, daemon=True).start()
    cctx = ssl.create_default_context(cafile=crt)
    d = AB.Doh("dns.test", ["127.0.0.1"], DOH_PORT, cctx)
    w = build_query("doh.example", qid=0x4242)
    r1 = d.query(w)
    r2 = d.query(build_query("doh2.example", qid=0x1111))
    check(r1[:2] == b"\x42\x42" and answers(r1)[1][0][1] == bytes([93, 184, 216, 34]), "DoH: відповідь, ID відновлено")
    check(r2[:2] == b"\x11\x11" and d.pool.qsize() == 1, "DoH: з'єднання перевикористовується")
    wrong = AB.Doh("other.name", ["127.0.0.1"], DOH_PORT, cctx)
    try:
        wrong.query(w)
        check(False, "DoH: чужий сертифікат має відхилятися")
    except OSError:
        check(True, "DoH: сертифікат на інше ім'я — відхилено")

else:
    print("  skip  DoH: no cryptography/openssl")

print("── зупинка")
c.call("POST", "/api/shutdown", {"restore": True})
th.join(5)
check(rc_holder.get("rc") == 0 and not os.path.exists(AB._path("api.json")), "служба завершилась і прибрала api.json")
check(os.path.exists(AB._path("stats.json")), "статистика збережена на диск")
st2 = AB.Stats(AB._path("stats.json"))
check(st2.today["total"] >= 10, f"статистика відновлюється після перезапуску: {st2.today['total']}")
print("\nFAILS:", fails)
_boot.result(fails=fails, doh=HAVE_CERT)
