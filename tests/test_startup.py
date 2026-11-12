"""Швидкий запуск (6.15): що будується одразу, а що — пізніше чи на вимогу. Раніше сторінка «Оптимізація» з
експертним меню будувалася під час появи вікна (на ноутбуці з i5-7300U — до 2,8 с без відповіді), а результат
аналізу заліза змушував будувати ще сім сторінок поспіль."""
from _util import has_qt, run_script, skip, tail


def test_startup_builds_only_what_is_shown():
    if not has_qt():
        skip("PyQt6 is not installed")
    rc, out, r = run_script("startup_lazy.py", timeout=300)
    assert rc == 0 and r, tail(out, 60)
    assert r["after_main"] == ["home"], f"Main() must build only the home page, built: {r['after_main']}"
    assert r["after_hw"] == ["home"], f"the hardware result must not force pages to be built: {r['after_hw']}"
    assert r["laptop_hw"], "a page built after the analysis must still get the hardware"
    assert r["lazy_before"] and r["still_lazy"], "the expert menu must not be built until it is opened"
    assert r["expert_rows"] >= 100 and r["expert_current"] and r["back_ok"], r
    assert r["compat_ok"], "the expert menu built later must show the same compatibility as before"
    assert r["build_delay"] >= 500, "background page building must not start while the window is appearing"
