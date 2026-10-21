"""Обмеження за збіркою Windows: на старих збірках Windows 10 параметри, яких там немає, недоступні."""
import _boot
import json
import sys

sys.argv = _boot.argv("--lang=uk")
import engine as E  # noqa: E402

by_id = {t.id: t for t in E.TWEAKS}
out = {}
for build in (10240, 14393, 17134, 17763, 18363, 19045, 22631):
    out[build] = sorted(t.id for t in E.TWEAKS if E.compat(t, {"build": build})[0] == "na" and t.min_build)
out["reason"] = E.compat(by_id["gpu_hw_scheduling"], {"build": 18363})[1]
out["bad_min_build"] = [t.id for t in E.TWEAKS if t.min_build and (t.min_build < 10240 or t.min_build >= 22000)]
print("RESULT " + json.dumps(out, ensure_ascii=False))
