"""«Вимкнути зайві служби» чіпає лише FORCE_OFF; шкідливі зміни старіших версій повертаються з журналу."""
import _boot
import json
import sys

sys.argv = _boot.argv("--lang=uk")
import engine as E  # noqa: E402

lines = []
t = next(x for x in E.TWEAKS if x.id == "disable_services")
E.apply_tweaks([t], lines.append, header=False)
applied = sorted(u["n"] for u in (E.JOURNAL.get("disable_services") or {}).get("undo", []) if u["t"] == "svc")
E.JOURNAL.pop("disable_services")

# так виглядали записи 6.3: служби виробника ноутбука, очищення файлу підкачки, завдання мобільного інтернету
E.JOURNAL.put("disable_services", [{"t": "svc", "n": "DiagTrack", "old": "auto"},
                                   {"t": "svc", "n": "ETDService", "old": "auto"},
                                   {"t": "svc", "n": "SharedAccess", "old": "demand"},
                                   {"t": "svc", "n": "LenovoFnAndFunctionKeys", "old": "delayed-auto"}])
E.JOURNAL.put("optimize_pagefile", [{"t": "ps", "c": "# pagefile"},
                                    {"t": "reg", "p": E.MM, "n": "ClearPageFileAtShutdown", "old": None}])
E.JOURNAL.put("disable_spy_tasks", [{"t": "task", "n": r"\Microsoft\Windows\Management\Provisioning\Cellular"}])
before = sorted(f"{tid}:{u.get('n')}" for tid, u in E.legacy_to_repair())
r1 = E.repair_legacy(lines.append)
left = {tid: [u.get("n") or u.get("c") for u in (E.JOURNAL.get(tid) or {}).get("undo", [])]
        for tid in ("disable_services", "optimize_pagefile", "disable_spy_tasks")}
again = E.legacy_to_repair()
print("RESULT " + json.dumps({"applied": applied, "force_off": sorted(E.FORCE_OFF), "before": before, "n1": r1["n"],
                              "left": left, "spy_popped": not E.JOURNAL.has("disable_spy_tasks"), "again": len(again),
                              "undo_lines": [ln for ln in lines if "[dry-run] undo" in ln]}))
