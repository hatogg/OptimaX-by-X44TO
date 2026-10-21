"""Підключається першим рядком кожного скрипта тестів: шлях до програми і (лише локально) заглушка Qt."""
import json
import os
import sys
import tempfile

# кожен запуск — з чистою тимчасовою папкою налаштувань (і ніколи — з налаштуваннями користувача)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

_stub = os.environ.get("OPTIMAX_TEST_QTSTUB")
STUB = bool(_stub)
if _stub:  # каталог із qtstub2.py — для перевірки тестів без справжнього PyQt6; у CI не використовується
    sys.path.insert(0, _stub)
    import qtstub2
    qtstub2.install()


def argv(*extra) -> list:
    """sys.argv для скрипта: завжди режим перегляду — тести ніколи не змінюють систему, на якій їх запущено."""
    return ["x", *extra, "--dry-run"]


def result(**kw) -> None:
    print("RESULT " + json.dumps(kw, ensure_ascii=False, default=str), flush=True)
