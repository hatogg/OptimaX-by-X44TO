"""Швидкий запуск (6.14): головне вікно будує лише головну сторінку; результат аналізу заліза не змушує будувати інші
сторінки (раніше це був один довгий блок, коли інтерфейс не відповідав); сторінка, збудована пізніше, однаково
отримує залізо; експертне меню (≈130 рядків) будується лише тоді, коли до нього звертаються."""
import _boot
import sys
import time

sys.argv = _boot.argv("--lang=en")
import engine as E  # noqa: E402
import hardware as H  # noqa: E402
import lifecycle as L  # noqa: E402
import optimizer as O  # noqa: E402
from PyQt6.QtWidgets import QSystemTrayIcon  # noqa: E402

L.start_server = lambda *a, **k: None
QSystemTrayIcon.show = lambda self: None
O.Main.run_quick = lambda self, *a, **k: None  # жодних фонових дій: результат аналізу подаємо самі

app = O.QApplication(sys.argv)
O.apply_theme(app)
t = time.perf_counter()
w = O.Main(start_hidden=True)
main_ms = int((time.perf_counter() - t) * 1000)
after_main = sorted(dict.keys(w.pages))

hw = H._from_demo("laptop")
w._hw_ready({"hw": hw, "an": H.analyze(hw), "checks": H.build_check(hw, []), "gpu_t": None})
after_hw = sorted(dict.keys(w.pages))

lp = w.pages["laptop"]  # збудована після аналізу — має отримати залізо під час побудови
laptop_hw = lp.banner.isHidden() == bool(hw.get("battery"))

opt = w.pages["optimize"]
lazy_before = opt._expert is None
opt.set_mode(0)
still_lazy = opt._expert is None
opt.set_mode(2)
ex = opt.expert
expert_current = opt.stack.currentWidget() is ex
compat_ok = all(r.state == E.compat(r.t, hw)[0] for r in ex.rows.values())
opt.set_mode(0)
back_ok = opt.stack.currentWidget() is opt.modes and opt.expert is ex

_boot.result(main_ms=main_ms, after_main=after_main, after_hw=after_hw, laptop_hw=laptop_hw,
             lazy_before=lazy_before, still_lazy=still_lazy, expert_rows=len(ex.rows),
             expert_current=expert_current, compat_ok=compat_ok, back_ok=back_ok,
             build_delay=O.Main.BUILD_DELAY_MS)
