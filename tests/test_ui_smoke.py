"""Головне вікно на справжньому PyQt6 (у CI — offscreen) з демо-залізом: усі розділи та основні сценарії."""
from _util import IS_WIN, cases, has_qt, run_script, skip, tail

CONFIGS = [("gaming", "uk"), ("laptop", "ru"), ("old", "en")]
SIMPLE_NAV = {"home", "library", "games", "diagnose", "backup", "settings"}


def check_66(st: dict) -> None:
    """OptimaX 6.6: бібліотека, простий вигляд, «Чому впав комп?», телефон, перенесення, «Що нового», звіт."""
    lib = st["library"]
    assert lib["tiles"] == 4, lib
    det = lib["detail"]
    assert det[0] and det[1] == "Counter-Strike 2" and det[2] and "212" in det[3], det
    assert lib["started"] and lib["boost_on"], "Play must start the game and Game Mode before it"
    assert lib["boost_off"], "Game Mode started by Play must switch itself off when the game closes"
    assert lib["sessions"] == ["cs2.exe"] and "212" in lib["sub"], lib
    s = st["simple"]
    assert s["card"] and s["full_hidden"] and s["cfg"] and set(s["nav"]) == SIMPLE_NAV, s
    assert s["review"][0] and s["review"][1] >= 10, "the one Optimize button opens the review of the recommended plan"
    assert s["restored"], s
    c = st["crash"]
    assert c["kinds"] == ["power", "bsod"] and c["rows"] >= 4 and c["gpu"] == 2 and c["whea"] == 1, c
    p = st["phone"]
    assert not p.get("http_error"), p
    assert p["running"] and p["url"].startswith("http://") and p["qr"] and p["shown"], p
    assert p["page"] and p["api"] and p["foreign"] == 404 and p["new_code"] and p["stopped"], p
    t = st["transfer"]
    assert t["format"] == "optimax-settings" and 10 <= t["tweaks"] <= st["applied"], (t, st["applied"])
    assert t["review"][0] and t["review"][1] == "import" and t["review"][2] >= 10, t
    assert st["whats_new"] == [True, True], st["whats_new"]
    assert st["report"] == ["ok", "ok"], st["report"]


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
    check_66(st)


def test_mining_card():
    """Майнінгова P106-100 (демо): розділ «Ігри на P106-100» — пошук і призначення ігор, Mesa для OpenGL-гри,
    примітка в GPU-тесті й повний відкат."""
    if not has_qt():
        skip("PyQt6 is not installed")
    if IS_WIN:
        skip("demo hardware exists only outside Windows")
    rc, out, r = run_script("ui_smoke.py", "uk", demo="mining", timeout=1500)
    assert rc == 0 and r, tail(out, 80)
    assert not r["errors"], "\n".join(r["errors"])
    assert not r["raw"], r["raw"]
    st = r["steps"]
    assert st["mining_card"], "a mining card must get its own section on the Games page"
    m = st["mining"]
    assert m["rows"] == 4 and m["mesa"] and m["dxvk"], m
    assert m["gpu"] == 5, "4 exe from the scan + the DirectX 9 exe that DXVK puts on the card"
    assert any("DXVK" in t for t in m["texts"]) and any("Mesa" in t for t in m["texts"]), m["texts"]
    assert "P106-100" in m["bench_note"], m["bench_note"]
    assert m["left"] == 0, "Revert all must remove every mining change"
    # Universal GPU Renderer: перевірка DirectX / Vulkan, режими, перевірка рендерингу, аналізатори
    assert "1.4.303" in m["probe"] and "582.78" in m["probe"], m["probe"]
    assert m["checked"] and m["menus"] >= 3 and m["link"] >= 2 and m["shader"], m
    assert st["anticheat_plan"] == [["dxvk", ["anticheat"]]], st["anticheat_plan"]
    d = st["mining_diag"]
    assert d["render"] == "mining" and "render_ok" in d["keys"] and d["fps"], d
    assert d["hist"] >= 2 and d["hist_rows"] > 0, d
    check_66(st)
