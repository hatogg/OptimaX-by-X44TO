"""
Запуск тестів без pytest:  python tests/run_tests.py [фільтр]
(у CI тести запускає pytest — це той самий набір файлів tests/test_*.py).
"""
import glob
import importlib.util
import inspect
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _util import Skip  # noqa: E402


def params(fn):
    """Підтримка @pytest.mark.parametrize без pytest: tests записують варіанти в fn.cases."""
    return getattr(fn, "cases", None) or [()]


def main() -> int:
    flt = sys.argv[1] if len(sys.argv) > 1 else ""
    ok = fail = skipped = 0
    for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
        spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Skip as e:
            print(f"SKIP {os.path.basename(path)}: {e}")
            skipped += 1
            continue
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if not name.startswith("test_") or fn.__module__ != mod.__name__:
                continue
            for case in params(fn):
                tid = f"{mod.__name__}::{name}" + (f"[{'-'.join(map(str, case))}]" if case else "")
                if flt and flt not in tid:
                    continue
                t0 = time.time()
                try:
                    fn(*case)
                    ok += 1
                    print(f"ok   {tid}  ({time.time() - t0:.1f}s)")
                except Skip as e:
                    skipped += 1
                    print(f"skip {tid}: {e}")
                except Exception:
                    fail += 1
                    print(f"FAIL {tid}\n{traceback.format_exc()}")
    print(f"\n{ok} passed, {fail} failed, {skipped} skipped")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
