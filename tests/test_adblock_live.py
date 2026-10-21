"""DNS-фільтр наживо на 127.0.0.1: блокування, кеш, TCP, усічення, API, пауза, DoH, зупинка."""
from _util import run_script, tail


def test_dns_filter_live():
    rc, out, r = run_script("adblock_live.py", timeout=300)
    assert rc == 0 and r is not None, tail(out)
    assert not r["fails"], tail(out, 80)
