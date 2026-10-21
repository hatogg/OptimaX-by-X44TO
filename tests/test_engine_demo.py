"""Усі твіки в режимі перегляду на п'яти демо-конфігураціях: застосування, журнал, повний відкат."""
from _util import IS_WIN, cases, run_script, skip, tail

DEMOS = ("gaming", "laptop", "old", "x3d", "xeon")


@cases("demo", [(d,) for d in DEMOS])
def test_apply_and_undo_everything(demo):
    if IS_WIN:
        skip("demo hardware exists only outside Windows; on Windows see tests/windows/tweak_roundtrip.py")
    rc, out, r = run_script("engine_demo.py", {"old": "en", "laptop": "ru"}.get(demo, "uk"), demo=demo)
    assert rc == 0 and r, tail(out)
    assert not r["errors"], r["errors"]
    assert r["apply"]["fail"] == 0, r["apply"]
    assert not r["not_journaled"], f"applied but not in the journal (no rollback!): {r['not_journaled']}"
    assert r["journaled"] >= 40 and r["undone"] == r["before_undo"] and r["left"] == 0, r
    assert not r["warnings"], r["warnings"]
    assert r["trial"] == ["active", "decide"], r["trial"]
    assert r["recommended"] >= 15 and r["report_lines"] > 20
