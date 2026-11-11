"""Заставка під час запуску (6.13.1): після Splash.finish(вікно) головне вікно стає видимим і непрозорим, а заставка
закривається — саме так, як це робить optimizer.main(). У 6.13 анімація передачі жила в локальній змінній, Python
знищував її одразу, і вікно лишалося прозорим під заставкою, що висіла зверху."""
import _boot
import gc
import sys
import time

BLOCK = "block" in sys.argv  # потік інтерфейсу зайнятий одразу після появи вікна (на повільному ПК — секунди)
sys.argv = _boot.argv("--lang=en")
import optimizer as O  # noqa: E402
import ui_kit as UK  # noqa: E402
import ui_motion as UM  # noqa: E402
from PyQt6.QtWidgets import QWidget  # noqa: E402

app = O.QApplication(sys.argv)
O.apply_theme(app)
win = QWidget()
splash = UM.Splash("OptimaX", "test")
st = {"motion": bool(UK.MOTION["on"]), "built": False, "t_finish": 0.0, "t_closed": 0.0}


def closed() -> bool:
    try:
        return not splash.isVisible()
    except RuntimeError:  # заставку вже видалено — вона закрилася як слід
        return True


def build():
    splash.finish(win)
    gc.collect()  # усе, на що після finish() ніхто не посилається, має право зникнути — анімація не повинна
    st.update(built=True, t_finish=time.time())
    if BLOCK:
        O.QTimer.singleShot(60, lambda: time.sleep(2.0))


splash.play(build)
end = time.time() + 8
while time.time() < end:
    app.processEvents()
    if st["built"] and closed():
        st["t_closed"] = time.time()
        break
    time.sleep(0.005)
for _ in range(60):  # після передачі вже ніщо не має змінювати прозорість вікна
    app.processEvents()
    time.sleep(0.005)
_boot.result(motion=st["motion"], built=st["built"], splash_closed=closed(), window_visible=win.isVisible(),
             opacity=round(win.windowOpacity(), 2),
             handoff_ms=int((st["t_closed"] - st["t_finish"]) * 1000) if st["t_closed"] else -1)
