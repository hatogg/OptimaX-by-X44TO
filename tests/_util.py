"""Спільне для тестів: кожен сценарій із станом (журнал, налаштування) іде в окремому процесі з тимчасовою APPDATA."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "tests", "scripts")
IS_WIN = sys.platform == "win32"


class Skip(Exception):
    """Пропуск тесту, коли pytest не встановлений (tests/run_tests.py)."""


def skip(reason: str):
    try:
        import pytest
    except ImportError:
        raise Skip(reason)
    pytest.skip(reason)


def has_qt() -> bool:
    """Справжній PyQt6 або (лише для локальної перевірки) заглушка з OPTIMAX_TEST_QTSTUB."""
    if os.environ.get("OPTIMAX_TEST_QTSTUB"):
        return True
    return importlib.util.find_spec("PyQt6") is not None


def env_for(demo: str = "gaming", **extra) -> dict:
    env = dict(os.environ)
    env.update(APPDATA=tempfile.mkdtemp(prefix="oxt_"), OPTIMAX_DEMO=demo, PYTHONIOENCODING="utf-8",
               PYTHONUTF8="1", OPTIMAX_BENCH_FAST="1")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.update({k: str(v) for k, v in extra.items()})
    return env


def run_script(name: str, *args, demo: str = "gaming", timeout: int = 900, env: dict = None, **extra):
    """-> (код виходу, вивід, RESULT-словник або None). Скрипт друкує останнім рядком «RESULT {json}»."""
    e = env or env_for(demo, **extra)
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, name), *map(str, args)], cwd=ROOT, env=e,
                       capture_output=True, timeout=timeout)
    out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
    res = None
    for line in reversed(out.splitlines()):
        if line.startswith("RESULT "):
            res = json.loads(line[7:])
            break
    return p.returncode, out, res


def tail(text: str, n: int = 60) -> str:
    return "\n".join(text.splitlines()[-n:])


def cases(argnames: str, values):
    """@pytest.mark.parametrize, який розуміє й tests/run_tests.py."""
    def deco(fn):
        fn.cases = [v if isinstance(v, tuple) else (v,) for v in values]
        try:
            import pytest
        except ImportError:
            return fn
        return pytest.mark.parametrize(argnames, values)(fn)
    return deco
