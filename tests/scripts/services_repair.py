"""«Вимкнути зайві служби» чіпає лише FORCE_OFF; служби, які помилково змінив 6.3, повертаються з журналу."""
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

# так виглядав запис 6.3: FORCE_OFF + служби виробника ноутбука, переведені в ручний режим
E.JOURNAL.put("disable_services", [{"t": "svc", "n": "DiagTrack", "old": "auto"},
                                   {"t": "svc", "n": "ETDService", "old": "auto"},
                                   {"t": "svc", "n": "SharedAccess", "old": "demand"},
                                   {"t": "svc", "n": "LenovoFnAndFunctionKeys", "old": "delayed-auto"}])
before = sorted(u["n"] for u in E.services_to_repair())
r1 = E.repair_services(lines.append)
left = [u["n"] for u in E.JOURNAL.get("disable_services")["undo"]]
again = E.services_to_repair()

E.JOURNAL.pop("disable_services")
E.JOURNAL.put("disable_services", [{"t": "svc", "n": "ETDService", "old": "auto"}])
r2 = E.repair_services(lines.append)
print("RESULT " + json.dumps({"applied": applied, "force_off": sorted(E.FORCE_OFF), "before": before, "n1": r1["n"],
                              "left": left, "again": len(again), "n2": r2["n"],
                              "popped": not E.JOURNAL.has("disable_services"),
                              "undo_lines": [ln for ln in lines if "undo svc" in ln]}))
