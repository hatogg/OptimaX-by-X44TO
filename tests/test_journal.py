"""Журнал відкату: порядок відкату строго зворотний, навіть якщо твіки застосовано в ту саму секунду."""
from _util import run_script, tail


def test_rollback_order_same_second():
    rc, out, r = run_script("journal_order.py")
    assert rc == 0 and r, tail(out)
    assert r["newest_first"] == ["c", "b", "a"], r
    assert r["undo_order"] == ["c", "b", "a"], "undo_ids must undo newest first whatever order it gets"
    assert r["rescue_order"] == ["c", "b", "a"], r
    assert r["value"] is None, "a value changed by two tweaks must return to its original state"
