"""Документація: список оптимізацій актуальний, звіт не розкриває ім'я користувача, відносні посилання не биті."""
import os
import re
import subprocess
import sys

from _util import ROOT, run_script, tail


def test_tweak_docs_are_current():
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_docs.py"), "--check"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stdout + p.stderr


def test_report_has_no_user_paths():
    rc, out, r = run_script("report_privacy.py")
    assert rc == 0 and r, tail(out)
    assert not r["leak"], "the forum report must not contain C:\\Users\\<name>"
    assert any("cs2.exe" in ln for ln in r["game_lines"])


def _md_files():
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in (".git", "__pycache__", "build", "dist", "Output", "node_modules")]
        for fn in fns:
            if fn.endswith(".md"):
                yield os.path.join(dp, fn)


def _anchor(title: str) -> str:
    """Як GitHub робить якір із заголовка."""
    a = title.strip().lower()
    a = re.sub(r"[^\w\- ]", "", a, flags=re.UNICODE)
    return a.replace(" ", "-")


def test_relative_links_resolve():
    bad = []
    for path in _md_files():
        text = open(path, encoding="utf-8").read()
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        for m in re.finditer(r"\]\(([^)\s]+)\)|(?:src|href)=\"([^\"]+)\"", text):
            link = m.group(1) or m.group(2)
            if re.match(r"^(https?:|mailto:|#$)", link):
                continue
            target, _, frag = link.partition("#")
            full = os.path.normpath(os.path.join(os.path.dirname(path), target)) if target else path
            if not os.path.exists(full):
                bad.append(f"{os.path.relpath(path, ROOT)}: {link}")
                continue
            if frag and full.endswith(".md"):
                heads = {_anchor(h) for h in re.findall(r"(?m)^#{1,6} (.+)$", open(full, encoding="utf-8").read())}
                if frag.lower() not in heads:
                    bad.append(f"{os.path.relpath(path, ROOT)}: #{frag}")
    assert not bad, "\n".join(bad)
