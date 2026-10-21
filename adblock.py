"""
OptimaX — блокування реклами як Pi-hole: власний DNS-фільтр на цьому комп'ютері.

Як це працює:
    • фоновий процес (OptimaX.exe --dns-service, задача планувальника «OptimaX DNS» від імені SYSTEM)
      слухає 127.0.0.1:53 і, за бажанням, домашню мережу;
    • Windows отримує DNS 127.0.0.1 — усі програми й браузери питають адреси в нашого фільтра;
    • домени зі списків (StevenBlack, HaGeZi, OISD, AdGuard…) отримують відповідь 0.0.0.0 — реклама,
      трекери й шкідливі сайти просто не завантажуються;
    • решта запитів іде до вибраного DNS (Cloudflare, Quad9…) зашифровано (DNS-over-HTTPS) і кешується;
    • імена домашньої мережі (роутер, NAS, принтер) і captive-портали готелів ідуть до DNS роутера;
    • якщо фільтр зупиниться, Windows сама перейде на резервний DNS роутера — інтернет не зникне.

Легкий режим: просто DNS із блокуванням реклами (AdGuard DNS, Control D) — без фонового процесу.

Модуль працює і в Linux (тести, перегляд інтерфейсу); зміна системних DNS і планувальник — лише Windows.
"""
from __future__ import annotations

import collections
import http.client
import http.server
import ipaddress
import json
import math
import os
import queue
import re
import secrets
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import engine as E
from i18n import tr

TASK = "OptimaX DNS"
API_PORT = 5381
BLOCK_TTL = 10
MAX_UDP = 512
UPSTREAM_PORT = 53  # для тестів
VERSION = 1

# Firefox вимикає свій вбудований DoH, якщо цей домен «не існує» — інакше він обходив би фільтр (як у Pi-hole)
CANARY = {"use-application-dns.net"}
# Ці домени ніколи не блокуються: перевірка інтернету Windows, оновлення OptimaX і самих списків
ALWAYS_ALLOW = {"msftconnecttest.com", "msftncsi.com", "api.github.com", "github.com", "objects.githubusercontent.com",
                "raw.githubusercontent.com", "release-assets.githubusercontent.com", "adguardteam.github.io",
                "small.oisd.nl", "big.oisd.nl", "urlhaus.abuse.ch", "localhost"}
LOCAL_SUFFIXES = ("lan", "home", "home.arpa", "internal", "localdomain", "router", "fritz.box", "local", "intranet",
                  "corp", "private")
PRIVATE_PTR = ("10.in-addr.arpa", "168.192.in-addr.arpa", "254.169.in-addr.arpa", "d.f.ip6.arpa", "8.e.f.ip6.arpa") + \
    tuple(f"{i}.172.in-addr.arpa" for i in range(16, 32))
QTYPES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX", 16: "TXT", 28: "AAAA", 33: "SRV", 64: "SVCB",
          65: "HTTPS", 255: "ANY"}

# ───────────────────────── списки ─────────────────────────
GH = "https://raw.githubusercontent.com"
HZ = GH + "/hagezi/dns-blocklists/main/wildcard"
# fmt: hosts — точні імена; wild — домен разом із піддоменами; adblock — синтаксис ||domain^
LISTS = [
    dict(id="stevenblack", cat="ads", name="StevenBlack Unified", url=GH + "/StevenBlack/hosts/master/hosts",
         fmt="hosts", default=True),
    dict(id="hagezi_pro", cat="ads", name="HaGeZi Multi PRO", url=HZ + "/pro-onlydomains.txt", fmt="wild", default=True),
    dict(id="oisd_big", cat="ads", name="OISD Big", url="https://big.oisd.nl/domainswild2", fmt="wild"),
    dict(id="adguard_dns", cat="ads", name="AdGuard DNS filter",
         url="https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt", fmt="adblock"),
    dict(id="hagezi_tif", cat="security", name="HaGeZi Threat Intelligence", url=HZ + "/tif.medium-onlydomains.txt",
         fmt="wild"),
    dict(id="urlhaus", cat="security", name="URLhaus (abuse.ch)", url="https://urlhaus.abuse.ch/downloads/hostfile/",
         fmt="hosts", default=True),
    dict(id="hagezi_win", cat="telemetry", name="HaGeZi Windows/Office", url=HZ + "/native.winoffice-onlydomains.txt",
         fmt="wild"),
    dict(id="hagezi_tv", cat="telemetry", name="HaGeZi Smart TV (Samsung, LG, Roku, Amazon)", fmt="wild",
         url=[HZ + "/native.samsung-onlydomains.txt", HZ + "/native.lgwebos-onlydomains.txt",
              HZ + "/native.roku-onlydomains.txt", HZ + "/native.amazon-onlydomains.txt"]),
    dict(id="hagezi_phone", cat="telemetry", name="HaGeZi Xiaomi, Huawei, OPPO, vivo", fmt="wild",
         url=[HZ + "/native.xiaomi-onlydomains.txt", HZ + "/native.huawei-onlydomains.txt",
              HZ + "/native.oppo-realme-onlydomains.txt", HZ + "/native.vivo-onlydomains.txt"]),
    dict(id="hagezi_tiktok", cat="telemetry", name="HaGeZi TikTok", url=HZ + "/native.tiktok-onlydomains.txt",
         fmt="wild"),
    dict(id="hagezi_gambling", cat="content", name="HaGeZi Gambling", url=HZ + "/gambling-onlydomains.txt", fmt="wild"),
    dict(id="adult", cat="content", name="StevenBlack Adult",
         url=GH + "/StevenBlack/hosts/master/alternates/porn-only/hosts", fmt="hosts"),
    dict(id="hagezi_social", cat="content", name="HaGeZi Social Networks", url=HZ + "/social-onlydomains.txt",
         fmt="wild"),
]
LIST_BY_ID = {x["id"]: x for x in LISTS}
LIST_CATS = ("ads", "security", "telemetry", "content")

# Куди фільтр пересилає дозволені запити. Підключаємось за IP, а ім'я — лише для перевірки сертифіката:
# так шифрований DNS працює, навіть коли системний DNS — це ми самі.
UPSTREAMS = {
    "cloudflare": dict(name="Cloudflare", host="cloudflare-dns.com", ips=("1.1.1.1", "1.0.0.1")),
    "quad9": dict(name="Quad9", host="dns.quad9.net", ips=("9.9.9.9", "149.112.112.112")),
    "google": dict(name="Google", host="dns.google", ips=("8.8.8.8", "8.8.4.4")),
    "adguard": dict(name="AdGuard Unfiltered", host="unfiltered.adguard-dns.com", ips=("94.140.14.140", "94.140.14.141")),
}
DOH_PATH = "/dns-query"

# Легкий режим — DNS-сервіси, які самі блокують рекламу
LIGHT = [
    dict(id="adguard", name="AdGuard DNS", ips=("94.140.14.14", "94.140.15.15"),
         doh="https://dns.adguard-dns.com/dns-query", what="ads"),
    dict(id="adguard_family", name="AdGuard DNS Family", ips=("94.140.14.15", "94.140.15.16"),
         doh="https://family.adguard-dns.com/dns-query", what="family"),
    dict(id="controld", name="Control D Free", ips=("76.76.2.2",), doh="https://freedns.controld.com/p2",
         what="malware"),
]
LIGHT_BY_ID = {x["id"]: x for x in LIGHT}

DEFAULT_CFG = dict(lists=[x["id"] for x in LISTS if x.get("default")], allow=[], block=[], upstream="cloudflare",
                   doh=True, lan=False, strict=False, log_queries=True, blocking=True, auto_update=True, port=53)


def data_dir() -> str:
    """Спільна папка для служби (SYSTEM) і програми: %ProgramData%\\OptimaX\\adblock."""
    if E.IS_WIN and not E.DRY_RUN:
        return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "OptimaX", "adblock")
    return os.path.join(E.DATA_DIR, "adblock")


def _path(*parts) -> str:
    return os.path.join(data_dir(), *parts)


def _read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_cfg() -> dict:
    cfg = dict(DEFAULT_CFG)
    cfg.update(_read_json(_path("config.json"), {}) or {})
    cfg["lists"] = [i for i in cfg["lists"] if i in LIST_BY_ID]
    return cfg


def save_cfg(cfg: dict) -> None:
    _write_json(_path("config.json"), cfg)


# ───────────────────────── протокол DNS ─────────────────────────
class Query:
    __slots__ = ("id", "flags", "name", "qtype", "qclass", "qend", "udp", "raw")


def parse_query(data: bytes):
    """Запит з одним питанням. -> Query або None."""
    if len(data) < 17:
        return None
    qid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    if flags & 0x8000 or qd != 1:
        return None
    i, labels = 12, []
    while True:
        if i >= len(data):
            return None
        n = data[i]
        i += 1
        if n == 0:
            break
        if n & 0xC0 or i + n > len(data):
            return None
        labels.append(data[i:i + n].decode("ascii", "replace").lower())
        i += n
        if i > 270:
            return None
    if i + 4 > len(data):
        return None
    q = Query()
    q.id, q.flags = qid, flags
    q.name = ".".join(labels)
    q.qtype, q.qclass = struct.unpack(">HH", data[i:i + 4])
    q.qend = i + 4
    q.udp = MAX_UDP
    q.raw = data
    if ar and not an and not ns and len(data) >= q.qend + 11 and data[q.qend] == 0:
        rtype, size = struct.unpack(">HH", data[q.qend + 1:q.qend + 5])
        if rtype == 41:
            q.udp = max(MAX_UDP, min(size, 4096))
    return q


def make_response(q: Query, rcode: int = 0, answers: bytes = b"", ancount: int = 0) -> bytes:
    flags = 0x8000 | (q.flags & 0x7910) | 0x0080 | rcode
    return struct.pack(">HHHHHH", q.id, flags, 1, ancount, 0, 0) + q.raw[12:q.qend] + answers


def blocked_response(q: Query) -> bytes:
    if q.qtype == 1:
        return make_response(q, 0, b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, BLOCK_TTL, 4) + bytes(4), 1)
    if q.qtype == 28:
        return make_response(q, 0, b"\xc0\x0c" + struct.pack(">HHIH", 28, 1, BLOCK_TTL, 16) + bytes(16), 1)
    return make_response(q)  # NODATA: такого запису немає, але й помилки немає


def _skip_name(data: bytes, i: int) -> int:
    while True:
        n = data[i]
        if n == 0:
            return i + 1
        if n & 0xC0 == 0xC0:
            return i + 2
        i += n + 1


def rr_ttls(data: bytes) -> list:
    """-> [(зсув TTL, TTL)] для всіх записів відповіді, крім OPT."""
    out = []
    try:
        qd, an, ns, ar = struct.unpack(">HHHH", data[4:12])
        i = 12
        for _ in range(qd):
            i = _skip_name(data, i) + 4
        for _ in range(an + ns + ar):
            i = _skip_name(data, i)
            rtype, _cls, ttl, rdlen = struct.unpack(">HHIH", data[i:i + 10])
            if rtype != 41:
                out.append((i + 4, ttl))
            i += 10 + rdlen
        if i > len(data):
            return []
    except (IndexError, struct.error):
        return []
    return out


def with_id(resp: bytes, qid: int) -> bytes:
    return struct.pack(">H", qid) + resp[2:]


def truncate(resp: bytes, q: Query) -> bytes:
    """Відповідь, що не влазить у UDP: лише заголовок із прапорцем TC — клієнт повторить запит по TCP."""
    head = bytearray(resp[:12])
    head[2] |= 0x02
    head[6:12] = b"\x00\x00\x00\x00\x00\x00"
    return bytes(head) + q.raw[12:q.qend]


def rcode_of(resp: bytes) -> int:
    return resp[3] & 0x0F if len(resp) >= 4 else 2


# ───────────────────────── розбір списків ─────────────────────────
_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)[a-z0-9_](?:[a-z0-9_-]{0,62})(?:\.[a-z0-9_-]{1,63})+$")
_SKIP = {"localhost", "localhost.localdomain", "local", "broadcasthost", "ip6-localhost", "ip6-loopback", "0.0.0.0"}


def _clean(d: str):
    d = d.strip().lower().rstrip(".")
    if d.startswith("*."):
        d = d[2:]
    if not d or d in _SKIP or not _DOMAIN_RE.match(d):
        return None
    try:
        ipaddress.ip_address(d)
        return None
    except ValueError:
        return d


def parse_list(text: str, fmt: str) -> tuple:
    """-> (точні імена, домени з піддоменами)."""
    exact, wild = set(), set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#!":
            continue
        if line.startswith("@@") or line.startswith("/"):
            continue  # винятки й регулярні вирази adblock-синтаксису DNS-фільтру не потрібні
        if line.startswith("||"):
            body = line[2:]
            end = body.find("^")
            if end < 0 or (end + 1 < len(body) and body[end + 1] not in "$|"):
                continue
            opts = body[end + 1:]
            if "$" in opts and any(o in opts for o in ("denyallow", "client", "ctag", "dnstype", "badfilter")):
                continue
            d = _clean(body[:end])
            if d:
                wild.add(d)
            continue
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        if len(parts) >= 2:
            try:
                ipaddress.ip_address(parts[0])
            except ValueError:
                continue
            for p in parts[1:]:
                d = _clean(p)
                if d:
                    exact.add(d)
            continue
        raw = parts[0]
        d = _clean(raw)
        if not d:
            continue
        if fmt == "wild" or raw.startswith("*.") or raw.startswith("."):
            wild.add(d)
        else:
            exact.add(d)
    return exact, wild


def save_compiled(lid: str, exact: set, wild: set) -> None:
    os.makedirs(_path("lists"), exist_ok=True)
    tmp = _path("lists", lid + ".txt.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(exact)))
        f.write("\n#wild\n")
        f.write("\n".join(sorted(wild)))
    os.replace(tmp, _path("lists", lid + ".txt"))


def load_compiled(lid: str):
    try:
        with open(_path("lists", lid + ".txt"), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    a, _, b = text.partition("\n#wild\n")
    return set(filter(None, a.split("\n"))), set(filter(None, b.split("\n")))


def download_lists(ids, log, progress=None) -> dict:
    """Завантажує й компілює списки. -> {id: {count, updated, error}}."""
    meta = _read_json(_path("lists.json"), {}) or {}
    ids = [i for i in ids if i in LIST_BY_ID]
    for n, lid in enumerate(ids):
        if E.CANCEL.is_set():
            break
        item = LIST_BY_ID[lid]
        if progress:
            progress(n, len(ids), tr("ab.dl_list", name=item["name"]))
        urls = item["url"] if isinstance(item["url"], list) else [item["url"]]
        exact, wild, err = set(), set(), None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": f"{E.APP_NAME}/{E.VERSION}"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    text = r.read(80 * 2**20).decode("utf-8", "replace")
                a, b = parse_list(text, item["fmt"])
                exact |= a
                wild |= b
            except Exception as e:
                err = str(e)[:160]
        if exact or wild:
            save_compiled(lid, exact, wild)
            meta[lid] = dict(count=len(exact) + len(wild), updated=int(time.time()), error=err if err else None)
            log(tr("ab.list_ok", name=item["name"], n=f"{len(exact) + len(wild):,}".replace(",", " ")))
        else:
            old = meta.get(lid) or {}
            meta[lid] = dict(old, error=err or "empty")
            log(tr("ab.list_fail", name=item["name"], err=err or "empty"))
    if progress:
        progress(len(ids), len(ids), tr("e.finished"))
    _write_json(_path("lists.json"), meta)
    return meta


def _rule_sets(rules) -> tuple:
    exact, wild, globs = set(), set(), []
    for r in rules or []:
        r = r.strip().lower()
        if not r or r.startswith("#"):
            continue
        if "*" in r.strip("*.") or r.startswith("*") and not r.startswith("*."):
            globs.append(re.compile("^" + re.escape(r).replace(r"\*", ".*") + "$"))
        else:
            d = _clean(r)
            if d:
                (wild if r.startswith("*.") or r.startswith(".") else exact).add(d)
    return exact, wild, globs


class Filter:
    """Рішення «блокувати чи ні» для імені. Набори лише читаються — заміна цілком при перезавантаженні."""

    def __init__(self, lists: list, allow=(), block=()):
        self.lists = lists  # [(id, exact, wild)]
        self.allow = _rule_sets(list(allow) + sorted(ALWAYS_ALLOW))
        self.block = _rule_sets(block)
        self.total = sum(len(e) + len(w) for _, e, w in lists)

    @staticmethod
    def _suffixes(name: str) -> list:
        parts = name.split(".")
        return [".".join(parts[i:]) for i in range(len(parts) - 1)]

    @staticmethod
    def _hit(rules, name, suf) -> bool:
        exact, wild, globs = rules
        return name in exact or any(s in wild for s in suf) or any(g.match(name) for g in globs)

    def check(self, name: str) -> tuple:
        """-> (blocked, джерело): джерело — id списку, 'custom' або 'canary'."""
        if name in CANARY:
            return True, "canary"
        suf = self._suffixes(name)
        if self._hit(self.allow, name, suf) or name.endswith(".msftconnecttest.com"):
            return False, None
        if self._hit(self.block, name, suf):
            return True, "custom"
        for lid, exact, wild in self.lists:
            if name in exact or any(s in wild for s in suf):
                return True, lid
        return False, None

    @classmethod
    def from_disk(cls, cfg: dict) -> "Filter":
        lists = []
        for lid in cfg.get("lists", []):
            data = load_compiled(lid)
            if data:
                lists.append((lid, data[0], data[1]))
        return cls(lists, cfg.get("allow", []), cfg.get("block", []))


# ───────────────────────── пересилання запитів ─────────────────────────
class _PinnedHTTPS(http.client.HTTPSConnection):
    """HTTPS до конкретної IP-адреси з перевіркою сертифіката за іменем сервера."""

    def __init__(self, host: str, ip: str, port: int = 443, timeout: float = 4.0, context=None):
        super().__init__(host, port, timeout=timeout, context=context)
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class Doh:
    def __init__(self, host: str, ips, port: int = 443, context=None):
        self.host, self.ips, self.port = host, list(ips), port
        self.ctx = context or ssl.create_default_context()
        self.pool = queue.LifoQueue()
        self.n = 0

    def query(self, wire: bytes, timeout: float = 4.0) -> bytes:
        body = b"\x00\x00" + wire[2:]  # RFC 8484: ID = 0
        last = None
        for attempt in range(3):
            try:
                conn = self.pool.get_nowait()
            except queue.Empty:
                self.n += 1
                conn = _PinnedHTTPS(self.host, self.ips[(self.n + attempt) % len(self.ips)], self.port, timeout,
                                    self.ctx)
            try:
                conn.request("POST", DOH_PATH, body=body, headers={"Content-Type": "application/dns-message",
                                                                   "Accept": "application/dns-message"})
                r = conn.getresponse()
                data = r.read()
                if r.status == 200 and len(data) >= 12:
                    if self.pool.qsize() < 8:
                        self.pool.put(conn)
                    else:
                        conn.close()
                    return with_id(data, struct.unpack(">H", wire[:2])[0])
                last = OSError(f"HTTP {r.status}")
                conn.close()
            except Exception as e:  # з'єднання могло застаріти — пробуємо нове
                last = e
                conn.close()
        raise OSError(f"DoH {self.host}: {last}")


def udp_query(server: str, wire: bytes, timeout: float = 2.0, port: int = 53) -> bytes:
    fam = socket.AF_INET6 if ":" in server else socket.AF_INET
    s = socket.socket(fam, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(wire, (server, port))
        end = time.time() + timeout
        while time.time() < end:
            data, _ = s.recvfrom(65535)
            if data[:2] == wire[:2]:
                if data[2] & 0x02:  # усічено — повторюємо по TCP
                    return tcp_query(server, wire, timeout + 1, port)
                return data
        raise socket.timeout()
    finally:
        s.close()


def tcp_query(server: str, wire: bytes, timeout: float = 3.0, port: int = 53) -> bytes:
    with socket.create_connection((server, port), timeout) as s:
        s.sendall(struct.pack(">H", len(wire)) + wire)
        n = struct.unpack(">H", _recv_exact(s, 2))[0]
        return _recv_exact(s, n)


def _recv_exact(s, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise OSError("closed")
        buf += chunk
    return buf


class Resolver:
    """Шифрований DNS → звичайний DNS того ж сервісу → DNS роутера. Локальні імена — одразу до роутера."""

    def __init__(self, cfg: dict, local=(), suffixes=(), upstream_override=None):
        self.cfg = cfg
        up = UPSTREAMS.get(cfg.get("upstream"), UPSTREAMS["cloudflare"])
        self.plain = list(upstream_override or up["ips"])
        self.doh = Doh(up["host"], up["ips"]) if cfg.get("doh", True) and not upstream_override else None
        self.local = [s for s in local if s and s not in ("127.0.0.1", "::1")]
        self.suffixes = tuple(sorted({s.strip(".").lower() for s in list(LOCAL_SUFFIXES) + list(suffixes) if s},
                                     key=len, reverse=True))
        self.doh_fail_until = 0.0
        self.port = UPSTREAM_PORT

    def is_local(self, name: str) -> bool:
        if "." not in name:
            return True
        if name.endswith(".arpa"):
            return any(name == z or name.endswith("." + z) for z in PRIVATE_PTR)
        return any(name == s or name.endswith("." + s) for s in self.suffixes)

    def resolve(self, wire: bytes, q: Query) -> tuple:
        """-> (відповідь, звідки: 'up' | 'local')."""
        if self.local and self.is_local(q.name):
            for srv in self.local:
                try:
                    return udp_query(srv, wire, 1.5), "local"
                except OSError:
                    continue
        if self.doh and time.time() >= self.doh_fail_until:
            try:
                return self.doh.query(wire), "up"
            except Exception:
                self.doh_fail_until = time.time() + 60  # мережа блокує DoH (готель, офіс) — хвилину без нього
        for srv in self.plain:
            try:
                return udp_query(srv, wire, 2.0, self.port), "up"
            except OSError:
                continue
        for srv in self.local:  # captive-портал: до входу працює лише DNS мережі
            try:
                return udp_query(srv, wire, 2.0), "local"
            except OSError:
                continue
        raise OSError("no upstream")


class Cache:
    def __init__(self, size: int = 20000):
        self.size = size
        self.data = collections.OrderedDict()
        self.lock = threading.Lock()

    def get(self, key, qid: int):
        now = time.time()
        with self.lock:
            v = self.data.get(key)
            if not v:
                return None
            exp, stored, resp, ttls = v
            if now >= exp:
                del self.data[key]
                return None
            self.data.move_to_end(key)
        age = int(now - stored)
        buf = bytearray(resp)
        for off, ttl in ttls:
            struct.pack_into(">I", buf, off, max(0, ttl - age))
        return with_id(bytes(buf), qid)

    def put(self, key, resp: bytes) -> None:
        rc = rcode_of(resp)
        if rc not in (0, 3) or resp[2] & 0x02:
            return
        ttls = rr_ttls(resp)
        an = struct.unpack(">H", resp[6:8])[0]
        if rc == 0 and an:
            ttl = min([t for _, t in ttls] or [60])
            ttl = max(0, min(ttl, 3600))
        else:
            ttl = max(10, min(min([t for _, t in ttls] or [60]), 300))
        if ttl <= 0:
            return
        now = time.time()
        with self.lock:
            self.data[key] = (now + ttl, now, resp, ttls)
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)

    def clear(self) -> None:
        with self.lock:
            self.data.clear()


# ───────────────────────── статистика ─────────────────────────
class Stats:
    SLOT = 600  # 10 хвилин

    def __init__(self, path: str = None, log_queries: bool = True):
        self.path = path
        self.lock = threading.Lock()
        self.log_queries = log_queries
        self.qlog = collections.deque(maxlen=3000)
        self.seq = 0
        self._reset(time.strftime("%Y-%m-%d"))
        self.buckets = {}
        if path:
            self.load()

    def _reset(self, day: str):
        self.day = day
        self.today = dict(total=0, blocked=0, cache=0, local=0, fail=0)
        self.top_blocked = collections.Counter()
        self.top_allowed = collections.Counter()
        self.clients = collections.Counter()
        self.ms_sum, self.ms_n = 0.0, 0

    def add(self, client: str, name: str, qtype: int, status: str, ms: float, src=None) -> None:
        now = time.time()
        with self.lock:
            day = time.strftime("%Y-%m-%d")
            if day != self.day:
                self._reset(day)
            self.today["total"] += 1
            if status in self.today:
                self.today[status] += 1
            slot = int(now // self.SLOT)
            b = self.buckets.setdefault(slot, [0, 0])
            b[0] += 1
            if status == "blocked":
                b[1] += 1
                self.top_blocked[name] += 1
            else:
                self.top_allowed[name] += 1
            self.clients[client] += 1
            if status in ("ok", "local") and ms is not None:
                self.ms_sum += ms
                self.ms_n += 1
            if len(self.buckets) > 160:
                for k in sorted(self.buckets)[:-145]:
                    del self.buckets[k]
            for c in (self.top_blocked, self.top_allowed):
                if len(c) > 20000:
                    keep = c.most_common(5000)
                    c.clear()
                    c.update(dict(keep))
            if self.log_queries:
                self.seq += 1
                self.qlog.append((self.seq, round(now, 2), client, name, QTYPES.get(qtype, str(qtype)), status,
                                  None if ms is None else round(ms, 1), src))

    def snapshot(self) -> dict:
        now_slot = int(time.time() // self.SLOT)
        with self.lock:
            series = [(s, *self.buckets.get(s, (0, 0))) for s in range(now_slot - 143, now_slot + 1)]
            t = dict(self.today)
            return dict(day=self.day, today=t, pct=round(100 * t["blocked"] / t["total"], 1) if t["total"] else 0.0,
                        series=series, top_blocked=self.top_blocked.most_common(12),
                        top_allowed=self.top_allowed.most_common(12), top_clients=self.clients.most_common(12),
                        avg_ms=round(self.ms_sum / self.ms_n, 1) if self.ms_n else None,
                        cache_pct=round(100 * t["cache"] / max(1, t["total"] - t["blocked"]), 1))

    def entries(self, n: int = 200, flt: str = "all", text: str = "", since: int = 0) -> list:
        text = (text or "").lower()
        with self.lock:
            items = list(self.qlog)
        out = []
        for e in reversed(items):
            if e[0] <= since:
                break
            if flt == "blocked" and e[5] != "blocked" or flt == "allowed" and e[5] == "blocked":
                continue
            if text and text not in e[3] and text not in e[2]:
                continue
            out.append(dict(seq=e[0], ts=e[1], client=e[2], name=e[3], type=e[4], status=e[5], ms=e[6], src=e[7]))
            if len(out) >= n:
                break
        return out

    def load(self) -> None:
        d = _read_json(self.path, None)
        if not d or d.get("day") != self.day:
            if d:
                self.buckets = {int(k): v for k, v in (d.get("buckets") or {}).items()}
            return
        self.today.update(d.get("today") or {})
        self.top_blocked.update(dict(d.get("top_blocked") or []))
        self.top_allowed.update(dict(d.get("top_allowed") or []))
        self.clients.update(dict(d.get("clients") or []))
        self.buckets = {int(k): v for k, v in (d.get("buckets") or {}).items()}
        self.ms_sum, self.ms_n = d.get("ms_sum", 0.0), d.get("ms_n", 0)

    def save(self) -> None:
        if not self.path:
            return
        with self.lock:
            d = dict(day=self.day, today=self.today, top_blocked=self.top_blocked.most_common(500),
                     top_allowed=self.top_allowed.most_common(500), clients=self.clients.most_common(100),
                     buckets={str(k): v for k, v in self.buckets.items()}, ms_sum=self.ms_sum, ms_n=self.ms_n)
        try:
            _write_json(self.path, d)
        except OSError:
            pass


# ───────────────────────── DNS-сервер ─────────────────────────
def _client_ok(ip: str) -> bool:
    """Відповідаємо лише своїм: цей комп'ютер і домашня мережа (щоб не стати відкритим резолвером)."""
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
        if a.version == 6 and a.ipv4_mapped:
            a = a.ipv4_mapped
        return a.is_loopback or a.is_private or a.is_link_local or a in ipaddress.ip_network("100.64.0.0/10")
    except ValueError:
        return False


class DnsServer:
    def __init__(self, filt: Filter, resolver: Resolver, stats: Stats, cfg: dict):
        self.filter = filt
        self.resolver = resolver
        self.stats = stats
        self.cfg = cfg
        self.cache = Cache()
        self.pool = ThreadPoolExecutor(48, thread_name_prefix="dns")
        self.socks = []
        self.binds = []
        self.errors = []
        self.running = True
        self.paused_until = 0.0

    @property
    def blocking(self) -> bool:
        return bool(self.cfg.get("blocking", True)) and time.time() >= self.paused_until

    # ── обробка одного запиту ──
    def handle(self, data: bytes, client: str, tcp: bool = False):
        q = parse_query(data)
        if q is None:
            return None
        t0 = time.perf_counter()
        name = q.name
        if self.blocking:
            hit, src = self.filter.check(name)
            if hit:
                resp = make_response(q, 3) if src == "canary" else blocked_response(q)
                self.stats.add(client, name, q.qtype, "blocked", None, src)
                return resp
        key = (name, q.qtype, q.qclass, bool(q.flags & 0x0010))
        resp = self.cache.get(key, q.id)
        if resp is not None:
            self.stats.add(client, name, q.qtype, "cache", (time.perf_counter() - t0) * 1000)
        else:
            try:
                resp, via = self.resolver.resolve(data, q)
                self.cache.put(key, resp)
                self.stats.add(client, name, q.qtype, "local" if via == "local" else "ok",
                               (time.perf_counter() - t0) * 1000)
            except Exception:
                self.stats.add(client, name, q.qtype, "fail", None)
                return make_response(q, 2)  # SERVFAIL
        if not tcp and len(resp) > q.udp:
            return truncate(resp, q)
        return resp

    # ── мережа ──
    def bind(self, host: str, port: int, quiet: bool = False) -> bool:
        fam = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            u = socket.socket(fam, socket.SOCK_DGRAM)
            if E.IS_WIN:
                u.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", -5), 1)
            u.bind((host, port))
            t = socket.socket(fam, socket.SOCK_STREAM)
            if E.IS_WIN:
                t.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", -5), 1)
            else:
                t.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            t.bind((host, port))
            t.listen(64)
        except OSError as e:
            if not quiet:
                self.errors.append(f"{host}:{port} — {e}")
            return False
        self.socks += [u, t]
        self.binds.append(f"{host}:{port}")
        threading.Thread(target=self._udp_loop, args=(u,), daemon=True).start()
        threading.Thread(target=self._tcp_loop, args=(t,), daemon=True).start()
        return True

    def _udp_loop(self, sock):
        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
            except OSError:
                if not self.running:
                    return
                time.sleep(0.005)  # Windows: ICMP «порт недоступний» від клієнта — не причина зупинятися
                continue
            if _client_ok(addr[0]):
                self.pool.submit(self._udp_reply, sock, data, addr)

    def _udp_reply(self, sock, data, addr):
        try:
            resp = self.handle(data, addr[0])
            if resp:
                sock.sendto(resp, addr)
        except Exception:
            pass

    def _tcp_loop(self, sock):
        while self.running:
            try:
                conn, addr = sock.accept()
            except OSError:
                if not self.running:
                    return
                time.sleep(0.05)
                continue
            if not _client_ok(addr[0]):
                conn.close()
                continue
            self.pool.submit(self._tcp_conn, conn, addr)

    def _tcp_conn(self, conn, addr):
        conn.settimeout(10)
        try:
            while self.running:
                head = conn.recv(2)
                if len(head) < 2:
                    break
                data = _recv_exact(conn, struct.unpack(">H", head)[0])
                resp = self.handle(data, addr[0], tcp=True)
                if not resp:
                    break
                conn.sendall(struct.pack(">H", len(resp)) + resp)
        except Exception:
            pass
        finally:
            conn.close()

    def stop(self):
        self.running = False
        for s in self.socks:
            try:
                s.close()
            except OSError:
                pass
        self.pool.shutdown(wait=False)


# ───────────────────────── системні DNS Windows ─────────────────────────
ADAPTERS_PS = r"""
$r=@(); foreach ($a in Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' }) {
  $g=$a.InterfaceGuid; $k4='HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\'+$g
  $k6='HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters\Interfaces\'+$g
  $p4=Get-ItemProperty -Path $k4 -ErrorAction SilentlyContinue; $p6=Get-ItemProperty -Path $k6 -ErrorAction SilentlyContinue
  $ip=@(Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object { $_.IPAddress })
  $r += @{idx=$a.ifIndex; alias=$a.Name; guid=$g; ns4=[string]$p4.NameServer; dhcp4=[string]$p4.DhcpNameServer;
          ns6=[string]$p6.NameServer; dom=[string]$p4.DhcpDomain; ips=$ip}
}
$sl=@((Get-DnsClientGlobalSetting -ErrorAction SilentlyContinue).SuffixSearchList)
$dom=[string](Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -ErrorAction SilentlyContinue).Domain
@{adapters=$r; suffixes=$sl; domain=$dom} | ConvertTo-Json -Depth 4 -Compress
"""


def _split(v) -> list:
    return [x for x in re.split(r"[\s,;]+", str(v or "")) if x]


def adapters() -> dict:
    if not E.IS_WIN:
        return dict(adapters=[dict(idx=12, alias="Ethernet", guid="{demo}", ns4="", dhcp4="192.168.1.1", ns6="",
                                   dom="lan", ips=["192.168.1.50"])], suffixes=[], domain="")
    d = E.ps_json(ADAPTERS_PS, 40) or {}
    d["adapters"] = [a for a in E.as_list(d.get("adapters")) if isinstance(a, dict)]
    for a in d["adapters"]:
        a["ips"] = [str(x) for x in E.as_list(a.get("ips")) if x]
    return d


def _ours(servers: list) -> bool:
    return bool(servers) and servers[0] in ("127.0.0.1", "::1")


def point_system_dns(slog, ipv6: bool, strict: bool) -> dict:
    """Ставить 127.0.0.1 першим DNS на всіх фізичних адаптерах; старі налаштування — у резервну копію."""
    info = adapters()
    backup = _read_json(_path("dns-backup.json"), {}) or {}
    changed = False
    for a in info["adapters"]:
        ns4 = _split(a.get("ns4"))
        if a["guid"] not in backup and not _ours(ns4):
            backup[a["guid"]] = dict(alias=a.get("alias"), idx=a.get("idx"), ns4=ns4, ns6=_split(a.get("ns6")),
                                     dhcp4=_split(a.get("dhcp4")))
            changed = True
        b = backup.get(a["guid"], {})
        servers = ["127.0.0.1"] + (["::1"] if ipv6 else [])
        if not strict:  # резервний DNS роутера: якщо фільтр зупиниться, інтернет працюватиме далі
            fb = _split(a.get("dhcp4")) or (b.get("dhcp4") or []) + (b.get("ns4") or [])
            servers += [s for s in fb if ":" not in s and s not in ("127.0.0.1", "::1")][:1] or ["1.1.1.1"]
        if ns4 == [s for s in servers if ":" not in s]:
            continue
        if E.IS_WIN and not E.DRY_RUN:
            lst = ",".join(f"'{s}'" for s in servers)
            E.ps(f"Set-DnsClientServerAddress -InterfaceIndex {a['idx']} -ServerAddresses ({lst})", 30)
        slog(f"dns: {a.get('alias')} -> {', '.join(servers)}")
    if changed:
        _write_json(_path("dns-backup.json"), backup)
    if E.IS_WIN and not E.DRY_RUN:
        E.run("ipconfig /flushdns", 15)
    return info


def restore_system_dns(log=lambda *_: None) -> int:
    """Повертає DNS адаптерів, як було до фільтра. -> скільки адаптерів повернуто."""
    backup = _read_json(_path("dns-backup.json"), {}) or {}
    if not backup:
        return 0
    cur = {a["guid"]: a for a in adapters()["adapters"]}
    n = 0
    for guid, b in backup.items():
        a = cur.get(guid)
        idx = (a or {}).get("idx") or b.get("idx")
        if not idx:
            continue
        ns4 = [s for s in b.get("ns4") or [] if s not in ("127.0.0.1", "::1")]
        ns6 = [s for s in b.get("ns6") or [] if s not in ("127.0.0.1", "::1")]
        if E.IS_WIN and not E.DRY_RUN:
            if ns4 or ns6:
                lst = ",".join(f"'{s}'" for s in ns4 + ns6)
                E.ps(f"Set-DnsClientServerAddress -InterfaceIndex {idx} -ServerAddresses ({lst})", 30)
            else:
                E.ps(f"Set-DnsClientServerAddress -InterfaceIndex {idx} -ResetServerAddresses", 30)
        log(tr("ab.dns_restored", alias=b.get("alias") or idx))
        n += 1
    try:
        os.remove(_path("dns-backup.json"))
    except OSError:
        pass
    if E.IS_WIN and not E.DRY_RUN:
        E.run("ipconfig /flushdns", 15)
    return n


def local_servers(info: dict) -> tuple:
    """DNS роутера (для імен домашньої мережі) і DNS-суфікси."""
    backup = _read_json(_path("dns-backup.json"), {}) or {}
    servers, suffixes = [], list(_split(" ".join(E.as_list(info.get("suffixes")))))
    for a in info.get("adapters", []):
        b = backup.get(a["guid"], {})
        for s in _split(a.get("dhcp4")) + (b.get("dhcp4") or []) + (b.get("ns4") or []):
            if s not in servers and s not in ("127.0.0.1", "::1"):
                servers.append(s)
        if a.get("dom"):
            suffixes.append(a["dom"])
    if info.get("domain"):
        suffixes.append(info["domain"])
    return servers[:3], suffixes


# ───────────────────────── служба ─────────────────────────
class ApiHandler(http.server.BaseHTTPRequestHandler):
    server_version = "OptimaX-DNS"

    def log_message(self, *_):
        pass

    def _send(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self) -> bool:
        if not secrets.compare_digest(self.headers.get("X-OptimaX-Token", ""), self.server.svc.token):
            self._send(403, {"error": "token"})
            return False
        return True

    def do_GET(self):
        if not self._auth():
            return
        svc = self.server.svc
        path, _, qs = self.path.partition("?")
        args = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
        if path == "/api/status":
            self._send(200, svc.status())
        elif path == "/api/stats":
            self._send(200, svc.stats.snapshot())
        elif path == "/api/log":
            from urllib.parse import unquote
            self._send(200, svc.stats.entries(int(args.get("n", 200)), args.get("filter", "all"),
                                              unquote(args.get("q", "")), int(args.get("since", 0))))
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._auth():
            return
        svc = self.server.svc
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except ValueError:
            body = {}
        if self.path == "/api/pause":
            svc.server.paused_until = time.time() + max(0, int(body.get("seconds", 0)))
            svc.server.cache.clear()
            self._send(200, svc.status())
        elif self.path == "/api/reload":
            svc.reload()
            self._send(200, svc.status())
        elif self.path == "/api/update-lists":
            threading.Thread(target=svc.update_lists, daemon=True).start()
            self._send(200, {"ok": True})
        elif self.path == "/api/flush":
            svc.server.cache.clear()
            self._send(200, {"ok": True})
        elif self.path == "/api/shutdown":
            svc.stop_requested = "restore" if body.get("restore", True) else "keep"
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})


class Service:
    def __init__(self, port: int = None, system_dns: bool = None, slog=None, upstream_override=None):
        self.dir = data_dir()
        os.makedirs(self.dir, exist_ok=True)
        self.cfg = load_cfg()
        self.port = port or int(self.cfg.get("port") or 53)
        self.system_dns = (E.IS_WIN and not E.DRY_RUN) if system_dns is None else system_dns
        self.slog = slog or self._slog
        self.upstream_override = upstream_override
        self.token = secrets.token_hex(16)
        self.stats = Stats(_path("stats.json"), self.cfg.get("log_queries", True))
        self.info = adapters() if self.system_dns else dict(adapters=[], suffixes=[], domain="")
        local, suf = local_servers(self.info)
        self.server = DnsServer(Filter.from_disk(self.cfg), Resolver(self.cfg, local, suf, upstream_override),
                                self.stats, self.cfg)
        self.started = time.time()
        self.stop_requested = None
        self.updating = False
        self.cfg_mtime = self._mtime()
        self.api = None
        self.lan_ips = []

    def _slog(self, msg: str) -> None:
        try:
            p = _path("service.log")
            if os.path.exists(p) and os.path.getsize(p) > 512 * 1024:
                os.replace(p, p + ".1")
            with open(p, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
        except OSError:
            pass

    def _mtime(self) -> float:
        try:
            return os.path.getmtime(_path("config.json"))
        except OSError:
            return 0.0

    def status(self) -> dict:
        meta = _read_json(_path("lists.json"), {}) or {}
        return dict(version=VERSION, app=E.VERSION, pid=os.getpid(), started=int(self.started),
                    binds=self.server.binds, errors=self.server.errors[-5:], blocking=self.server.blocking,
                    paused_until=int(self.server.paused_until) if self.server.paused_until > time.time() else 0,
                    domains=self.server.filter.total, lists={k: v for k, v in meta.items() if k in self.cfg["lists"]},
                    upstream=self.cfg.get("upstream"), doh=bool(self.cfg.get("doh")), lan=bool(self.cfg.get("lan")),
                    lan_ips=self.lan_ips, updating=self.updating, local_dns=self.server.resolver.local,
                    doh_ok=self.server.resolver.doh_fail_until < time.time())

    def reload(self) -> None:
        self.cfg = load_cfg()
        self.cfg_mtime = self._mtime()
        self.server.cfg = self.cfg
        self.server.filter = Filter.from_disk(self.cfg)
        local, suf = local_servers(self.info)
        self.server.resolver = Resolver(self.cfg, local, suf, self.upstream_override)
        self.server.cache.clear()
        self.stats.log_queries = self.cfg.get("log_queries", True)
        self.slog(f"reload: {self.server.filter.total} domains")

    def update_lists(self) -> None:
        if self.updating:
            return
        self.updating = True
        try:
            download_lists(self.cfg["lists"], self.slog)
            self.cfg["updated"] = int(time.time())
            save_cfg(self.cfg)
            self.reload()
        finally:
            self.updating = False

    def _api(self) -> None:
        for port in (API_PORT, 0):
            try:
                srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), ApiHandler)
                break
            except OSError:
                continue
        else:
            return
        srv.daemon_threads = True
        srv.svc = self
        self.api = srv
        _write_json(_path("api.json"), dict(port=srv.server_address[1], token=self.token, pid=os.getpid()))
        threading.Thread(target=srv.serve_forever, daemon=True).start()

    def bind_all(self) -> bool:
        ok = self.server.bind("127.0.0.1", self.port)
        self.ipv6 = socket.has_ipv6 and self.server.bind("::1", self.port, quiet=True)
        if self.cfg.get("lan"):
            for a in self.info.get("adapters", []):
                for ip in a.get("ips", []):
                    if _client_ok(ip) and not ip.startswith("169.254.") and self.server.bind(ip, self.port):
                        self.lan_ips.append(ip)
        return ok

    def run(self) -> int:
        self.slog(f"start {E.APP_TITLE} {E.VERSION}, pid {os.getpid()}")
        self._api()
        if not self.bind_all():
            self.slog("bind failed: " + "; ".join(self.server.errors))
            _write_json(_path("status.json"), dict(ok=False, errors=self.server.errors, ts=int(time.time())))
            time.sleep(5)
            return 2
        self.slog(f"listening {', '.join(self.server.binds)}; {self.server.filter.total} domains")
        _write_json(_path("status.json"), dict(ok=True, binds=self.server.binds, ts=int(time.time())))
        if self.system_dns:
            self.info = point_system_dns(self.slog, self.ipv6, self.cfg.get("strict", False))
            self.reload()
        last_save = last_ensure = time.time()
        while self.stop_requested is None:
            time.sleep(1)
            now = time.time()
            if now - last_save >= 60:
                last_save = now
                self.stats.save()
                if self._mtime() != self.cfg_mtime:
                    self.reload()
            if self.system_dns and now - last_ensure >= 90:
                last_ensure = now
                try:
                    self.info = point_system_dns(self.slog, self.ipv6, self.cfg.get("strict", False))
                except Exception as e:
                    self.slog(f"ensure: {e}")
            if self.cfg.get("auto_update", True) and not self.updating and \
                    now - (self.cfg.get("updated") or 0) > 7 * 86400 and now - self.started > 120:
                self.cfg["updated"] = int(now)  # щоб не повторювати спробу щосекунди, якщо мережі немає
                threading.Thread(target=self.update_lists, daemon=True).start()
        self.slog(f"stop ({self.stop_requested})")
        if self.system_dns and self.stop_requested == "restore":
            restore_system_dns(self.slog)
        self.stats.save()
        self.server.stop()
        if self.api:
            self.api.shutdown()
        for f in ("api.json", "status.json"):
            try:
                os.remove(_path(f))
            except OSError:
                pass
        return 0


def service_main(argv) -> int:
    """OptimaX.exe --dns-service — запускає планувальник Windows від імені SYSTEM."""
    port = None
    for a in argv:
        if a.startswith("--port="):
            port = int(a.split("=", 1)[1])
    try:
        return Service(port=port).run()
    except Exception as e:
        try:
            os.makedirs(data_dir(), exist_ok=True)
            with open(_path("service.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"fatal: {e!r}\n")
        except OSError:
            pass
        return 1


# ───────────────────────── керування з програми ─────────────────────────
class Client:
    def __init__(self):
        info = _read_json(_path("api.json"), {}) or {}
        self.port, self.token = info.get("port"), info.get("token", "")

    def call(self, method: str, path: str, body=None, timeout: float = 2.0):
        if not self.port:
            return None
        try:
            c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
            data = json.dumps(body).encode() if body is not None else None
            c.request(method, path, body=data, headers={"X-OptimaX-Token": self.token,
                                                        "Content-Type": "application/json"})
            r = c.getresponse()
            out = json.loads(r.read() or b"null")
            c.close()
            return out if r.status == 200 else None
        except (OSError, ValueError, http.client.HTTPException):
            return None


def _self_command() -> list:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return [pyw if os.path.exists(pyw) else exe, os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimizer.py")]


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def install_task(log) -> bool:
    cmd = _self_command()
    args = subprocess.list2cmdline(cmd[1:] + ["--dns-service"])
    script = (
        f"$a=New-ScheduledTaskAction -Execute {_ps_quote(cmd[0])} -Argument {_ps_quote(args)};"
        "$t=New-ScheduledTaskTrigger -AtStartup;"
        "$p=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest;"
        "$s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable "
        "-ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) "
        "-MultipleInstances IgnoreNew -Priority 4;"
        f"Register-ScheduledTask -TaskName {_ps_quote(TASK)} -Action $a -Trigger $t -Principal $p -Settings $s "
        "-Description 'OptimaX: DNS ad blocker' -Force | Out-Null;"
        f"Start-ScheduledTask -TaskName {_ps_quote(TASK)}")
    rc, out = E.ps(script, 60, log)
    if rc != 0:
        log(f"  {E.first_line(out, 160)}")
    return rc == 0


def task_exists() -> bool:
    if not E.IS_WIN:
        return False
    rc, _ = E.run(["schtasks", "/Query", "/TN", TASK], 10, ro=True)
    return rc == 0


def remove_task(log) -> None:
    E.run(["schtasks", "/End", "/TN", TASK], 20, log)
    E.run(["schtasks", "/Delete", "/TN", TASK, "/F"], 20, log)


def set_firewall(on: bool, log) -> None:
    E.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={TASK}"], 20)
    if on:
        for proto in ("UDP", "TCP"):
            E.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name={TASK}", "dir=in", "action=allow",
                   f"protocol={proto}", "localport=53", "profile=private,domain"], 20, log)


def secure_dir(log) -> None:
    """Папку фільтра (і ключ доступу до нього) можуть читати лише адміністратори й SYSTEM."""
    os.makedirs(data_dir(), exist_ok=True)
    if E.IS_WIN and not E.DRY_RUN:
        E.run(["icacls", data_dir(), "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"],
              20, log)


def port_owner(port: int = 53) -> str:
    """Хто вже займає порт 53 (ім'я процесу) — щоб пояснити, чому фільтр не стартує."""
    if not E.IS_WIN:
        return ""
    data = E.ps_json(f"$e=Get-NetUDPEndpoint -LocalPort {port} -ErrorAction SilentlyContinue | "
                     "Where-Object { $_.LocalAddress -in @('127.0.0.1','0.0.0.0','::','::1') } | Select-Object -First 1;"
                     "if ($e) { @{name=(Get-Process -Id $e.OwningProcess -ErrorAction SilentlyContinue).ProcessName;"
                     " pid=$e.OwningProcess} | ConvertTo-Json -Compress }", 20)
    return f"{data.get('name')} (PID {data.get('pid')})" if isinstance(data, dict) and data.get("pid") else ""


class Backend:
    """Те, чим користується сторінка «Блок реклами». Поза Windows (і в режимі перегляду) — правдоподібна імітація."""

    def __init__(self, cfg_store):
        self.store = cfg_store  # F.CFG
        self.demo = not E.IS_WIN or E.DRY_RUN

    # ── стан ──
    @property
    def ui(self) -> dict:
        return dict(dict(mode="off", light=None), **(self.store["adblock"] or {}))

    def _set_ui(self, **kw) -> None:
        d = self.ui
        d.update(kw)
        self.store["adblock"] = d

    @property
    def mode(self) -> str:
        return self.ui.get("mode", "off")

    def client(self) -> Client:
        return Client()

    def status(self):
        if self.mode != "filter":
            return None
        if self.demo:
            cfg = load_cfg()
            meta = _read_json(_path("lists.json"), {}) or {}
            paused = self.ui.get("paused_until", 0)
            return dict(version=VERSION, binds=["127.0.0.1:53", "[::1]:53"] + (["192.168.1.50:53"] if cfg["lan"] else []),
                        errors=[], blocking=cfg.get("blocking", True) and paused < time.time(),
                        paused_until=paused if paused > time.time() else 0,
                        domains=sum((meta.get(i) or {}).get("count", 0) for i in cfg["lists"]),
                        lists={k: v for k, v in meta.items() if k in cfg["lists"]}, upstream=cfg["upstream"],
                        doh=cfg["doh"], lan=cfg["lan"], lan_ips=["192.168.1.50"] if cfg["lan"] else [], updating=False,
                        local_dns=["192.168.1.1"], doh_ok=True, started=int(time.time()) - 5 * 3600)
        return self.client().call("GET", "/api/status")

    def stats(self):
        if self.mode != "filter":
            return None
        if self.demo:
            return demo_stats()
        return self.client().call("GET", "/api/stats")

    def querylog(self, n: int = 150, flt: str = "all", text: str = ""):
        if self.mode != "filter":
            return []
        if self.demo:
            return demo_log(n, flt, text)
        from urllib.parse import quote
        return self.client().call("GET", f"/api/log?n={n}&filter={flt}&q={quote(text)}") or []

    # ── увімкнення / вимкнення ──
    def enable(self, log, progress=None) -> dict:
        if E.JOURNAL.has("dns"):  # спершу повертаємо DNS, змінені на сторінці «Мережа» або легким режимом
            log(tr("ab.undo_light"))
            E.undo_ids(["dns"], log)
        secure_dir(log)
        cfg = load_cfg()
        save_cfg(cfg)
        meta = _read_json(_path("lists.json"), {}) or {}
        missing = [i for i in cfg["lists"] if not os.path.exists(_path("lists", i + ".txt"))]
        if missing:
            if self.demo:
                for lid in missing:
                    meta[lid] = dict(count=DEMO_COUNTS.get(lid, 50000), updated=int(time.time()), error=None)
                    save_compiled(lid, set(), set())
                    log(tr("ab.list_ok", name=LIST_BY_ID[lid]["name"],
                           n=f"{meta[lid]['count']:,}".replace(",", " ")))
                _write_json(_path("lists.json"), meta)
            else:
                meta = download_lists(missing, log, progress)
                cfg["updated"] = int(time.time())
                save_cfg(cfg)
            if not any((meta.get(i) or {}).get("count") for i in cfg["lists"]):
                raise RuntimeError(tr("ab.no_lists"))
        if self.demo:
            log("  [dry-run] Register-ScheduledTask 'OptimaX DNS' (SYSTEM, AtStartup) → 127.0.0.1:53")
            log("  [dry-run] Set-DnsClientServerAddress → 127.0.0.1, ::1, 192.168.1.1")
            self._set_ui(mode="filter", light=None, since=int(time.time()))
            return {"ok": True}
        owner = port_owner(53)
        if owner and "optimax" not in owner.lower():
            raise RuntimeError(tr("ab.port_busy", who=owner))
        if cfg.get("lan"):
            set_firewall(True, log)
        if not install_task(log):
            raise RuntimeError(tr("ab.task_fail"))
        log(tr("ab.starting"))
        for _ in range(60):
            time.sleep(0.5)
            st = Client().call("GET", "/api/status", timeout=1.0)
            if st and st.get("binds"):
                self._set_ui(mode="filter", light=None, since=int(time.time()))
                log(tr("ab.started", binds=", ".join(st["binds"]), n=f"{st['domains']:,}".replace(",", " ")))
                return {"ok": True}
            s = _read_json(_path("status.json"), {}) or {}
            if s.get("ok") is False:
                break
        s = _read_json(_path("status.json"), {}) or {}
        remove_task(log)
        restore_system_dns(log)
        raise RuntimeError(tr("ab.start_fail", err="; ".join(s.get("errors") or []) or "timeout"))

    def disable(self, log, progress=None) -> dict:
        if self.mode == "light":
            E.undo_ids(["dns"], log)
            self._set_ui(mode="off", light=None)
            return {"ok": True}
        if self.demo:
            log("  [dry-run] OptimaX DNS: stop, restore DNS, delete task")
            self._set_ui(mode="off")
            return {"ok": True}
        c = Client()
        if c.call("POST", "/api/shutdown", {"restore": True}):
            for _ in range(30):  # служба сама поверне DNS і завершиться
                time.sleep(0.5)
                if c.call("GET", "/api/status", timeout=0.5) is None:
                    break
        remove_task(log)
        restore_system_dns(log)  # якщо служба не встигла — повертаємо самі (резервна копія вже порожня — нічого)
        set_firewall(False, log)
        self._set_ui(mode="off")
        log(tr("ab.stopped"))
        return {"ok": True}

    def ensure_running(self, log=lambda *_: None) -> bool:
        """Після оновлення програми чи збою: якщо фільтр має працювати, але не відповідає — перезапускаємо."""
        if self.demo or self.mode != "filter":
            return True
        if Client().call("GET", "/api/status", timeout=1.0):
            return True
        if task_exists():
            E.run(["schtasks", "/Run", "/TN", TASK], 20, log)
            return False
        return install_task(log)

    def pause(self, seconds: int) -> None:
        if self.demo:
            self._set_ui(paused_until=int(time.time()) + seconds if seconds else 0)
            return
        Client().call("POST", "/api/pause", {"seconds": seconds})

    # ── легкий режим ──
    def set_light(self, pid: str, doh: bool, log) -> dict:
        import netlab as N
        if self.mode == "filter":
            self.disable(log)
        prov = LIGHT_BY_ID[pid]
        if E.JOURNAL.has("dns"):
            E.undo_ids(["dns"], log)
        t = N.dns_tweak(prov, doh)
        res = E.apply_tweaks([t], log, header=False)
        self._set_ui(mode="light", light=pid)
        return res

    # ── налаштування ──
    def cfg(self) -> dict:
        return load_cfg()

    def save(self, **changes) -> dict:
        cfg = load_cfg()
        old_lan = cfg.get("lan")
        cfg.update(changes)
        save_cfg(cfg)
        if self.mode == "filter" and not self.demo:
            if "lan" in changes and bool(changes["lan"]) != bool(old_lan):
                set_firewall(bool(changes["lan"]), lambda *_: None)
                self.restart()  # нові адреси для прослуховування — лише після перезапуску служби
            elif "strict" in changes:
                self.restart()  # служба одразу перепише DNS адаптерів (з резервним сервером чи без)
            else:
                Client().call("POST", "/api/reload")
        return cfg

    def apply_lists(self, ids, log, progress=None) -> dict:
        """Зберігає вибір списків і завантажує ті, яких ще немає на диску."""
        self.save(lists=list(ids))
        missing = [i for i in ids if not os.path.exists(_path("lists", i + ".txt"))]
        if missing:
            if self.demo:
                meta = _read_json(_path("lists.json"), {}) or {}
                for lid in missing:
                    meta[lid] = dict(count=DEMO_COUNTS.get(lid, 50000), updated=int(time.time()), error=None)
                    save_compiled(lid, set(), set())
                    log(tr("ab.list_ok", name=LIST_BY_ID[lid]["name"], n=f"{meta[lid]['count']:,}".replace(",", " ")))
                _write_json(_path("lists.json"), meta)
            else:
                download_lists(missing, log, progress)
        if self.mode == "filter" and not self.demo:
            Client().call("POST", "/api/reload")
        log(tr("ab.lists_saved", n=len(ids)))
        return {"ok": True}

    def restart(self) -> None:
        Client().call("POST", "/api/shutdown", {"restore": False})
        time.sleep(1.5)
        E.run(["schtasks", "/Run", "/TN", TASK], 20)

    def rule(self, domain: str, kind: str, add: bool = True) -> dict:
        """kind: allow | block. Прибирає домен із протилежного списку."""
        domain = domain.strip().lower().rstrip(".")
        cfg = load_cfg()
        other = "block" if kind == "allow" else "allow"
        cfg[other] = [d for d in cfg[other] if d != domain]
        cur = [d for d in cfg[kind] if d != domain]
        if add:
            cur.append(domain)
        cfg[kind] = cur
        return self.save(allow=cfg["allow"], block=cfg["block"])

    def update_lists(self, log, progress=None) -> dict:
        cfg = load_cfg()
        if self.demo:
            meta = _read_json(_path("lists.json"), {}) or {}
            for lid in cfg["lists"]:
                meta[lid] = dict(count=DEMO_COUNTS.get(lid, 50000), updated=int(time.time()), error=None)
                log(tr("ab.list_ok", name=LIST_BY_ID[lid]["name"], n=f"{meta[lid]['count']:,}".replace(",", " ")))
            _write_json(_path("lists.json"), meta)
            return {"ok": True}
        meta = download_lists(cfg["lists"], log, progress)
        cfg["updated"] = int(time.time())
        save_cfg(cfg)
        if self.mode == "filter":
            Client().call("POST", "/api/reload")
        return {"ok": all(not (meta.get(i) or {}).get("error") for i in cfg["lists"])}

    def lists_meta(self) -> dict:
        return _read_json(_path("lists.json"), {}) or {}

    def uninstall(self, log) -> None:
        """Для деінсталятора: зупинити фільтр, повернути DNS, прибрати задачу й правило брандмауера."""
        if self.demo:
            return
        running = task_exists() or os.path.exists(_path("api.json")) or os.path.exists(_path("dns-backup.json"))
        if not running:
            return  # легкий режим — запис у журналі змін, його відкотить «повернути всі зміни»
        try:
            Client().call("POST", "/api/shutdown", {"restore": True}, timeout=1.0)
            time.sleep(2)
        except Exception:
            pass
        remove_task(log)
        restore_system_dns(log)
        set_firewall(False, log)
        self._set_ui(mode="off")


# ───────────────────────── імітація для перегляду ─────────────────────────
DEMO_COUNTS = {"stevenblack": 79482, "hagezi_pro": 187215, "oisd_big": 214306, "adguard_dns": 129774,
               "hagezi_tif": 412880, "urlhaus": 3016, "hagezi_win": 412, "hagezi_tv": 1630, "hagezi_phone": 1984,
               "hagezi_tiktok": 381, "hagezi_gambling": 191433, "adult": 76540, "hagezi_social": 2913}
# лише домени, які справді є в стандартних списках (перевірено на StevenBlack і HaGeZi Pro)
DEMO_BLOCKED_SRC = [("doubleclick.net", 1184, "stevenblack"), ("googleads.g.doubleclick.net", 902, "stevenblack"),
                    ("app-measurement.com", 611, "stevenblack"), ("browser.events.data.msn.com", 488, "hagezi_pro"),
                    ("www.googletagmanager.com", 402, "stevenblack"), ("ads.pubmatic.com", 344, "stevenblack"),
                    ("adservice.google.com", 332, "stevenblack"), ("vortex.data.microsoft.com", 297, "hagezi_pro"),
                    ("pagead2.googlesyndication.com", 251, "stevenblack"), ("c.amazon-adsystem.com", 173, "stevenblack"),
                    ("sb.scorecardresearch.com", 144, "stevenblack"), ("sentry.io", 131, "hagezi_pro")]
DEMO_BLOCKED = [(d, n) for d, n, _ in DEMO_BLOCKED_SRC]
DEMO_ALLOWED = [("www.google.com", 2104), ("i.ytimg.com", 1820), ("steamcommunity.com", 1311),
                ("gateway.discord.gg", 1102), ("rr4---sn-4g5e6nsz.googlevideo.com", 960), ("api.steampowered.com", 822),
                ("www.youtube.com", 790), ("cdn.discordapp.com", 655), ("login.live.com", 402), ("github.com", 288)]
DEMO_CLIENTS = [("127.0.0.1", 15012), ("192.168.1.23", 2901), ("192.168.1.31", 1144)]


def demo_stats() -> dict:
    now_slot = int(time.time() // Stats.SLOT)
    series = []
    for i, s in enumerate(range(now_slot - 143, now_slot + 1)):
        hour = (time.localtime(s * Stats.SLOT).tm_hour + time.localtime(s * Stats.SLOT).tm_min / 60)
        act = 0.15 + 0.85 * max(0.0, math.sin((hour - 7) / 17 * math.pi)) if 7 <= hour <= 24 else 0.12
        total = int(60 + 260 * act + 25 * ((i * 37) % 11) / 11)
        series.append((s, total, int(total * (0.2 + 0.05 * ((i * 13) % 7) / 7))))
    total = sum(t for _, t, _ in series)
    blocked = sum(b for _, _, b in series)
    return dict(day=time.strftime("%Y-%m-%d"), today=dict(total=total, blocked=blocked, cache=int(total * 0.41),
                                                          local=212, fail=3),
                pct=round(100 * blocked / total, 1), series=series, top_blocked=DEMO_BLOCKED,
                top_allowed=DEMO_ALLOWED, top_clients=DEMO_CLIENTS, avg_ms=18.4, cache_pct=53.2)


def demo_log(n: int = 150, flt: str = "all", text: str = "") -> list:
    names = [d for d, _ in DEMO_BLOCKED[:8]] + [d for d, _ in DEMO_ALLOWED]
    out = []
    now = time.time()
    for i in range(160):
        name = names[(i * 7) % len(names)]
        src = next((s for d, _, s in DEMO_BLOCKED_SRC if d == name), None)
        blocked = src is not None
        st = "blocked" if blocked else ("cache" if i % 3 == 0 else "ok")
        e = dict(seq=1000 - i, ts=round(now - i * 9.5, 2), client=DEMO_CLIENTS[i % 5 == 0][0], name=name,
                 type="AAAA" if i % 4 == 1 else "A" if i % 4 else "HTTPS", status=st,
                 ms=None if blocked else (0.1 if st == "cache" else round(9 + (i * 13) % 31, 1)),
                 src=src)
        if flt == "blocked" and not blocked or flt == "allowed" and blocked:
            continue
        if text and text.lower() not in name:
            continue
        out.append(e)
        if len(out) >= n:
            break
    return out
