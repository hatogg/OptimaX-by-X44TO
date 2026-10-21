"""Сторож: після відновлення системи (не діє більшість змін) пропонує забути записи; забування не чіпає систему."""
import _boot
import json
import sys

sys.argv = _boot.argv("--lang=uk")
import engine as E  # noqa: E402
import guard as G  # noqa: E402

ids = ["ads_tips", "ai_copilot", "disable_telemetry", "game_mode_on", "startup_delay", "delivery_p2p"]
for tid in ids:
    E.JOURNAL.put(tid, [{"t": "reg", "p": r"HKCU\Software\Demo", "n": tid, "old": None}])
lines = []
res = {"many": G.looks_like_restore(ids[:5]), "few": G.looks_like_restore(ids[:1]),
       "forgot": G.forget(ids[:5], lines.append), "left": [i for i in ids if E.JOURNAL.has(i)],
       "touched": [ln for ln in lines if "dry-run" in ln]}
print("RESULT " + json.dumps(res))
