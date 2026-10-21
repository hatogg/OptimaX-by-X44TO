"""Сцена тесту відеокарти на справжньому OpenGL (Mesa без екрана): шейдери компілюються, кадр не порожній,
контрольний кадр однаковий щоразу — на цьому тримається перевірка стабільності відеокарти."""
from _util import run_script, skip, tail


def test_scene_renders_and_is_deterministic():
    rc, out, r = run_script("gl_render.py", timeout=600)
    assert rc == 0 and r, tail(out)
    if r.get("skip"):
        skip(r["skip"])
    assert r["bytes"] == 320 * 180 * 4 and r["blit_bytes"] == 500 * 400 * 4
    assert r["distinct"] > 20 and 10 < r["mean"] < 245, "frame is blank or washed out"
    assert r["checks"] == [True, True, True], "check frame differs between runs"
    assert r["gl_error"] == 0
