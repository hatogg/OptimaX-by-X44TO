"""
Причини збою — прямо на сторінку запуску GitHub Actions (анотації ::error), без завантаження журналів.

    python tests/ci_annotate.py junit     <junit.xml>        — упалі тести pytest
    python tests/ci_annotate.py selftest  <report.json> [rc] — упалі перевірки --selftest (і код виходу exe)
    python tests/ci_annotate.py roundtrip <roundtrip.json>   — твіки, що не відкотилися
    python tests/ci_annotate.py smoke     <smoke.json>       — встановлення / видалення

GitHub показує до 10 помилок на крок, тож решта збирається в одну підсумкову анотацію.
Нічого не знайшли — нічого не друкуємо (код виходу завжди 0: крок лише пояснює, а не вирішує).
"""
import json
import os
import sys
import xml.etree.ElementTree as ET

LIMIT = 9
TEXT = 1800


def esc(s: str) -> str:
    return str(s).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def esc_prop(s: str) -> str:
    return esc(s).replace(":", "%3A").replace(",", "%2C")


def emit(items):
    """items: [(title, message)]"""
    for title, msg in items[:LIMIT]:
        print(f"::error title={esc_prop(title)[:200]}::{esc(str(msg)[-TEXT:])}")
    rest = items[LIMIT:]
    if rest:
        print(f"::error title={esc_prop(f'…and {len(rest)} more')}::{esc(chr(10).join(t for t, _ in rest))}")


def junit(path):
    if not os.path.exists(path):
        return [("pytest", f"no JUnit report at {path}: tests did not run or crashed")]
    out = []
    for case in ET.parse(path).iter("testcase"):
        for tag in ("failure", "error"):
            el = case.find(tag)
            if el is not None:
                name = f"{case.get('classname', '').split('.')[-1]}::{case.get('name')}"
                msg = (el.get("message") or "") + "\n" + (el.text or "")
                out.append((f"{tag}: {name}", msg.strip()))
    return out


def _tail(path, n=2500):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()[-n:].strip()
    except OSError:
        return ""


def selftest(path, rc=None, label="selftest"):
    base = os.path.splitext(path)[0]
    if not os.path.exists(path):
        crash = _tail(base + "-crash.txt")
        progress = _tail(base + "-progress.txt", 1500)
        out = [(label, f"no report at {path} (exit code {rc}): the program crashed before writing it."
                       f"\n--- last steps:\n{progress or '(none: it crashed before the self-test started)'}")]
        if crash:
            out.append((f"{label}: native crash stack", crash))
        return out
    rep = json.load(open(path, encoding="utf-8"))
    out = []
    for c in rep.get("checks", []):
        if not c.get("ok"):
            out.append((f"{label} {c['name']}", f"{c.get('error')}\n{c.get('trace', '')}"))
    if not out and rc not in (None, "0", 0):
        out.append(("selftest", f"exit code {rc}, but every check in the report passed"))
    return out


def roundtrip(path):
    if not os.path.exists(path):
        return [("tweak round-trip", f"no report at {path}: the harness crashed")]
    rep = json.load(open(path, encoding="utf-8"))
    out = [(f"tweak {r['id']}", "\n".join(r.get("problems", [])[:8])) for r in rep.get("tweaks", []) if r["status"] == "fail"]
    for b in rep.get("batches", []):
        if b.get("problems"):
            out.append((f"batch via {b['how']}", "\n".join(b["problems"][:12]) + ("\n" + b.get("rescue_out", "")[-600:]
                                                                               if b["how"] == "rescue" else "")))
    return out


def smoke(path):
    if not os.path.exists(path):
        return [("install smoke test", f"no report at {path}")]
    data = json.load(open(path, encoding="utf-8-sig"))
    data = data if isinstance(data, list) else [data]
    return [(f"install: {r['check']}", r.get("detail") or "failed") for r in data if not r.get("ok")]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 0
    kind, path = sys.argv[1], sys.argv[2]
    try:
        items = {"junit": junit, "roundtrip": roundtrip, "smoke": smoke}.get(
            kind, lambda p: selftest(p, sys.argv[3] if len(sys.argv) > 3 else None,
                                     sys.argv[4] if len(sys.argv) > 4 else "selftest"))(path)
    except Exception as e:  # пояснення не повинно саме падати
        items = [(f"{kind} report", f"could not read {path}: {type(e).__name__}: {e}")]
    emit(items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
