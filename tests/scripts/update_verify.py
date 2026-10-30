"""Безпечне оновлення (6.4) на фальшивій Windows: файл запускається лише після перевірки SHA-256 і підпису.

Запуск: FAKE_TARGET=tests/scripts/update_verify.py python tests/scripts/fake_windows.py --out DIR
Мережу замінено словником «URL -> байти», підпис Windows — підробленою відповіддю WinVerifyTrust."""
import hashlib
import io
import json
import os
import sys

import updater as U
import verify as V

R = {}
log = lambda *a: None  # noqa: E731
FILES = {}
LAUNCHED = []
BASE = "https://github.com/hatogg/OptimaX-by-X44TO/releases/download/v9.9/"
NAME = "OptimaX-Setup-9.9.exe"
GOOD = os.urandom(300_000)
SHA = hashlib.sha256(GOOD).hexdigest()


class Resp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_open(url, timeout, accept=None):
    if url not in FILES:
        raise OSError(f"404 {url}")
    return Resp(FILES[url])


U._open = fake_open
U.subprocess.Popen = lambda args, **k: LAUNCHED.append(args)
SIG = {"status": "unsigned", "code": V.TRUST_E_NOSIGNATURE}
WHO = {"name": ""}
V.signature = lambda path: dict(SIG)
V.signer = lambda path: WHO["name"]
V.own_publisher = lambda: ""


def rel(digest=True, sums=True):
    assets = [{"name": NAME, "browser_download_url": BASE + NAME, "size": len(GOOD)}]
    if digest:
        assets[0]["digest"] = "sha256:" + SHA
    if sums:
        assets.append({"name": "SHA256SUMS.txt", "browser_download_url": BASE + "SHA256SUMS.txt"})
    return {"tag_name": "v9.9", "html_url": BASE, "body": "", "assets": assets}


def attempt(info):
    """-> (шлях або None, ключ помилки або None, чи лишився .part)"""
    try:
        path = U.download(info, log)
        return path, None, False
    except V.VerifyError as e:
        part = any(n.endswith(".part") for n in os.listdir(U.download_dir()))
        return None, e.key, part


def sums(text):
    FILES[BASE + "SHA256SUMS.txt"] = text.encode()


# 1. Усе гаразд: digest і SHA256SUMS.txt збігаються з файлом → завантажено, перевірено, запущено
FILES[BASE + NAME] = GOOD
sums(f"{SHA.upper()}  {NAME}\n{'0' * 64}  OptimaX-9.9-portable.exe\n")
info = U.from_release(rel(), True)
R["info"] = {"sha256": info["sha256"] == SHA, "sums_url": info["sums_url"].endswith("SHA256SUMS.txt"),
             "name": info["name"]}
path, err, _ = attempt(info)
R["ok"] = {"err": err, "in_programdata": bool(path) and path.startswith(os.environ["ProgramData"])}
R["ok_launch"] = U.launch(path, "setup") and len(LAUNCHED) == 1

# 2. Файл підмінили після перевірки, перед запуском → не запускається
with open(path, "r+b") as f:
    f.write(b"MZ-evil")
R["swapped_launch"] = {"launched": U.launch(path, "setup"), "error": bool(U.LAST_ERROR), "runs": len(LAUNCHED)}

# 3. Під час завантаження файл пошкоджено/підмінено → hash_mismatch, .part не лишається
FILES[BASE + NAME] = GOOD[:-10] + b"0123456789"
R["tampered"] = attempt(U.from_release(rel(), True))[1:]
FILES[BASE + NAME] = GOOD

# 4. Джерела сум розходяться між собою
sums(f"{'a' * 64}  {NAME}\n")
R["differ"] = attempt(U.from_release(rel(), True))[1]

# 5. Лише SHA256SUMS.txt (старий API без digest) — достатньо; лише digest (файлу сум немає) — теж
sums(f"{SHA} *{NAME}\n")
R["sums_only"] = attempt(U.from_release(rel(digest=False), True))[1]
FILES.pop(BASE + "SHA256SUMS.txt")
R["digest_only"] = attempt(U.from_release(rel(sums=False), True))[1]

# 6. Жодної суми → не завантажуємо й не запускаємо
R["no_hash"] = attempt(U.from_release(rel(digest=False, sums=False), True))[1]
sums(f"{SHA}  {NAME}\n")

# 7. Підпис: пошкоджений — ніколи; підписана OptimaX вимагає підпису того самого видавця
SIG.update(status="invalid", code=0x80096010)
R["sig_invalid"] = attempt(U.from_release(rel(), True))[1]
V.own_publisher = lambda: "CN=X44TO, O=X44TO"
SIG.update(status="unsigned", code=V.TRUST_E_NOSIGNATURE)
R["sig_missing"] = attempt(U.from_release(rel(), True))[1]
SIG.update(status="valid", code=0)
WHO["name"] = "CN=Someone Else, O=Evil"
R["sig_other"] = attempt(U.from_release(rel(), True))[1]
WHO["name"] = 'CN="X44TO", O=X44TO, C=UA'
R["sig_same"] = attempt(U.from_release(rel(), True))[1]

# 8. Кешовані дані без sums_url (знайдені до перевірки) — файл сум береться з того самого релізу
info = U.from_release(rel(digest=False), True)
info.pop("sums_url")
R["derived_sums"] = attempt(info)[1]

R["parse"] = V.parse_sums(f"{SHA.upper()}  {NAME}\r\n{SHA} *OptimaX-9.9-portable.exe\nnot a line\n")

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "roundtrip.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
