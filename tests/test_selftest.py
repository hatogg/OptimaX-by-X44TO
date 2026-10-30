"""Режим --selftest (ним CI перевіряє зібраний OptimaX.exe) — тут із вихідних файлів, з вікном."""
import json
import os
import tempfile

from _util import IS_WIN, has_qt, run_script, skip, tail


def test_selftest_with_ui():
    if not has_qt():
        skip("PyQt6 is not installed")
    out_dir = os.environ.get("OPTIMAX_TEST_SHOTS") or tempfile.mkdtemp(prefix="oxst_")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"selftest-source-{'windows' if IS_WIN else 'linux'}.json")
    rc, out, _ = run_script("run_app.py", f"--selftest={path}", "--selftest-ui", "--lang=en", timeout=900)
    assert os.path.exists(path), tail(out)
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)
    failed = {c["name"]: c.get("error") for c in rep["checks"] if not c["ok"]}
    assert rc == 0 and rep["ok"], failed or tail(out)
    names = {c["name"] for c in rep["checks"]}
    assert {"modules", "i18n", "hardware", "tweaks", "rescue", "abtest", "safety", "adblock", "ui"} <= names, names
    assert rep["dry_run"], "selftest must never change the system"
    ui = next(c for c in rep["checks"] if c["name"] == "ui")
    assert len(ui["info"]["pages"]) >= 14
