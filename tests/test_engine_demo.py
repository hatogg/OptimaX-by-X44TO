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


def test_old_windows10_builds_hide_missing_settings():
    rc, out, r = run_script("win_builds.py")
    assert rc == 0 and r, tail(out)
    assert "gpu_hw_scheduling" in r["18363"] and "gpu_hw_scheduling" not in r["19045"], r
    assert "ultimate_power" in r["14393"] and "ultimate_power" not in r["17134"], r
    assert r["22631"] == [] and "2004" in r["reason"], r
    assert not r["bad_min_build"], r["bad_min_build"]


def test_services_tweak_touches_only_its_list_and_repairs_63():
    rc, out, r = run_script("services_repair.py")
    assert rc == 0 and r, tail(out)
    assert r["applied"] == r["force_off"] and "SharedAccess" not in r["applied"], r["applied"]
    assert r["before"] == ["ETDService", "LenovoFnAndFunctionKeys", "SharedAccess"] and r["n1"] == 3, r
    assert r["left"] == ["DiagTrack"] and r["again"] == 0, r
    assert r["n2"] == 1 and r["popped"], r
    assert len(r["undo_lines"]) == 4, r["undo_lines"]
