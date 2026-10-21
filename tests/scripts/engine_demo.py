"""Режим перегляду на демо-залізі: застосувати всі твіки, перевірити журнал, відкотити все. Аргумент: мова."""
import _boot
import sys

sys.argv = _boot.argv("--lang=" + (sys.argv[1] if len(sys.argv) > 1 else "uk"))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import fpstest as FT  # noqa: E402
import guard as G  # noqa: E402
import hardware as H  # noqa: E402
import monitor as M  # noqa: E402
import report as RP  # noqa: E402

hw = H.detect_hw()
checks = H.build_check(hw, [])
lines = []
log = lines.append
items = [t for t in E.TWEAKS if not t.custom]
res = {"ok": 0, "fail": 0, "skipped": 0}
not_journaled = []
for t in items:  # по одному: видно, який саме твік змінив систему, але не залишив запису для відкату
    tl = []
    r = E.apply_tweaks([t], tl.append, header=False, hw=hw)
    lines += tl
    for k in res:
        res[k] += r[k]
    changed = any("[dry-run]" in ln and "refresh:" not in ln for ln in tl)
    if r["ok"] and t.reversible and changed and not E.JOURNAL.has(t.id):
        not_journaled.append(t.id)
journaled = E.JOURNAL.count()
errors = [ln for ln in lines if "Traceback" in ln or "✗" in ln]
an = H.analyze(hw)
G.start_trial(["ads_tips", "x_none"], log)
trial0 = G.trial_state()[0]
F.CFG["demo_boot"] = 9_999_999
trial1 = G.trial_state()[0]
G.end_trial(False, log)
d = M.lag_diagnosis(hw, 10, log, None)
b = FT.capture("cs2.exe", 5, log, None)
a = FT.capture("cs2.exe", 5, log, None)
txt = RP.to_text(RP.sections(hw, checks, an))
maint = G.run_maintenance(log)
before_undo = E.JOURNAL.count()
u = E.undo_ids(E.JOURNAL.newest_first(), log)
warnings = [ln for ln in lines if "⚠ " in ln and "dry-run" not in ln]
_boot.result(device=hw["device"], apply=res, errors=errors[:5], not_journaled=not_journaled, trial=[trial0, trial1],
             findings=[f["key"] for f in d["findings"]], fps=[b["avg"], a["avg"]], report_lines=len(txt.splitlines()),
             maintenance=bool(maint), journaled=journaled, before_undo=before_undo, undone=u["undone"], left=E.JOURNAL.count(), warnings=warnings[:5],
             recommended=len(an["recommended"]))
