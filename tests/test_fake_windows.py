"""Перевірка твіків і Rescue-файлу на фальшивій Windows (Linux): уся логіка tests/windows/tweak_roundtrip.py,
команди відкату OptimaX-Rescue.cmd і порядок відкату. А також — що перевірка справді ловить зламаний відкат."""
import json
import os
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, SCRIPTS, cases, skip, tail


def fake(hw="gaming", bug=""):
    if IS_WIN:
        skip("on Windows the real round-trip runs instead")
    out = tempfile.mkdtemp(prefix="oxfw_")
    env = dict(os.environ, FAKE_HW=hw, FAKE_BUG=bug, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fake_windows.py"), "--out", out], cwd=ROOT, env=env,
                       capture_output=True, timeout=900)
    text = (p.stdout + p.stderr).decode("utf-8", "replace")
    path = os.path.join(out, "roundtrip.json")
    assert os.path.exists(path), tail(text)
    with open(path, encoding="utf-8") as f:
        return p.returncode, json.load(f), text


@cases("hw", ["gaming", "laptop", "old"])
def test_every_tweak_round_trips(hw):
    rc, rep, text = fake(hw)
    fails = [(r["id"], r["problems"][:3]) for r in rep["tweaks"] if r["status"] == "fail"]
    assert rc == 0 and rep["ok"], fails or [b["problems"][:5] for b in rep["batches"]] or tail(text)
    assert rep["summary"]["pass"] >= 80
    assert [b["how"] for b in rep["batches"]] == ["rescue", "journal"]
    assert all(b["records"] >= 200 for b in rep["batches"])


@cases("bug", ["svc", "reg", "rescue", "task"])
def test_broken_rollback_is_caught(bug):
    rc, rep, _ = fake("gaming", bug)
    assert rc == 1 and not rep["ok"], f"FAKE_BUG={bug} was not detected"
