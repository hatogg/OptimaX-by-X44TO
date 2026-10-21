"""Два твіки змінюють одне значення в ту саму секунду; відкат у будь-якому порядку id → початковий стан."""
import _boot
import re
import sys

sys.argv = _boot.argv("--lang=en")
import engine as E  # noqa: E402
import rescue as RS  # noqa: E402

j = E.JOURNAL
for tid, old in (("a", None), ("b", [4, 38]), ("c", [4, 40])):  # a: не було → 38, b: 38 → 40, c: 40 → 42
    j.put(tid, [{"t": "reg", "p": r"HKLM\X", "n": "V", "old": old}])
order = []
value = ["now 42"]


def fake_undo(rec, log, deferred=None):  # імітація реєстру: застосовуємо old
    value[0] = rec["old"]


E._undo_record = fake_undo
E.undo_one, _undo_one = (lambda tid, log, d=None: (order.append(tid), _undo_one(tid, log, d))[1]), E.undo_one
newest = j.newest_first()
s = RS.build_script(j)
calls = re.findall(r"call :(x\d+)", s[s.index(":all"):s.index(":finish")])
rescue = [newest[int(c[1:])] for c in calls]
E.undo_ids(["a", "c", "b"], lambda *_: None)
_boot.result(newest_first=newest, undo_order=order, rescue_order=rescue, value=value[0])
