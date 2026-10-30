"""Головне вікно на справжньому PyQt6 (у CI — offscreen) з демо-залізом: усі розділи та основні сценарії."""
from _util import IS_WIN, cases, has_qt, run_script, skip, tail

CONFIGS = [("gaming", "uk"), ("laptop", "ru"), ("old", "en")]


@cases("demo,lang", CONFIGS)
def test_main_window(demo, lang):
    if not has_qt():
        skip("PyQt6 is not installed")
    if IS_WIN:
        skip("demo hardware exists only outside Windows; on Windows the built exe runs --selftest-ui")
    rc, out, r = run_script("ui_smoke.py", lang, demo=demo, timeout=1500)
    assert rc == 0 and r, tail(out, 80)
    st = r["steps"]
    assert not r["errors"], "\n".join(r["errors"])
    assert not r["bad"] and not r["raw"], (r["bad"], r["raw"])
    assert st["hw"] and st["pages"] >= 14, st
    assert st["modes"]["rows"] >= 10 and st["modes"]["smart"] and st["modes"]["safe"] >= 10, st["modes"]
    assert st["modes"]["limit"]
    assert st["applied"] >= 15 and st["batch"] == st["applied"], st
    assert st.get("banner") and st["banner"][0], st.get("banner")
    assert st["after_rescue"] == 0, "emergency rollback left changes of the batch"
    assert st["smart_switch"] and st["smart"]["result"] in ("better", "same", "fixed"), st["smart"]
    assert st["smart"]["measures"] >= 3
    assert st["card"] == [1200, 675]
    assert "ShareDialog" in r["dialogs"] and "SmartDialog" in r["dialogs"]
