"""
OptimaX — перевірка завантажених файлів перед запуском: контрольна сума SHA-256 і цифровий підпис.

OptimaX працює з правами адміністратора, тож будь-який файл, який вона завантажує й запускає (оновлення,
PresentMon), отримує ті самі права. Тому перед запуском:

1. SHA-256 файлу має збігтися з опублікованою сумою: поле digest ресурсу релізу в GitHub API та/або
   SHA256SUMS.txt того самого релізу. Якщо обидва джерела є — вони мусять збігатися між собою.
   Немає жодної суми — файл не запускається.
2. Цифровий підпис Authenticode перевіряє сама Windows (WinVerifyTrust). Пошкоджений або недовірений підпис —
   файл не запускається ніколи. Якщо сама OptimaX підписана (або збірка вимагає підпису через
   buildinfo.SIGNER), оновлення мусить мати дійсний підпис того самого видавця: інакше підмінена непідписана
   збірка могла б «оновити» підписану.

Перевірка повторюється безпосередньо перед запуском — файл не можна непомітно підмінити між завантаженням
і запуском.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import re
import sys

import engine as E
from i18n import tr

try:
    import buildinfo as _bi
    SIGNER = getattr(_bi, "SIGNER", "") or ""  # видавець, якого вимагає збірка (CN сертифіката), якщо задано
except ImportError:
    SIGNER = ""

HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class VerifyError(RuntimeError):
    """Файл не пройшов перевірку. key — ключ перекладу з поясненням, kw — підстановки."""

    def __init__(self, key: str, **kw):
        self.key, self.kw = key, kw
        super().__init__(tr(key, **kw))


# ───────────────────────── SHA-256 ─────────────────────────
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_sums(text: str) -> dict:
    """SHA256SUMS.txt («<hash>  <файл>» або «<hash> *<файл>», як у sha256sum) -> {ім'я файлу (нижній регістр): hash}."""
    out = {}
    for line in (text or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and HEX64.match(parts[0]):
            out[parts[1].strip().lstrip("*").strip().lower()] = parts[0].lower()
    return out


def digest_of(asset: dict) -> str:
    """Сума з поля digest ресурсу релізу (GitHub API: "sha256:<hex>"), або ''."""
    d = str((asset or {}).get("digest") or "")
    if d.lower().startswith("sha256:") and HEX64.match(d[7:]):
        return d[7:].lower()
    return ""


def expected_hash(name: str, digest: str = "", sums_text: str = None) -> str:
    """Очікувана сума з двох незалежних джерел. Якщо вони розходяться — це підміна або зіпсований реліз."""
    from_sums = parse_sums(sums_text).get(name.lower(), "") if sums_text else ""
    digest = (digest or "").lower()
    if digest and from_sums and digest != from_sums:
        raise VerifyError("vf.sources_differ", name=name)
    exp = digest or from_sums
    if not exp:
        raise VerifyError("vf.no_hash", name=name)
    return exp


# ───────────────────────── цифровий підпис ─────────────────────────
TRUST_E_NOSIGNATURE = 0x800B0100
TRUST_E_SUBJECT_FORM_UNKNOWN = 0x800B0003
TRUST_E_PROVIDER_UNKNOWN = 0x800B0001
UNSIGNED = {TRUST_E_NOSIGNATURE, TRUST_E_SUBJECT_FORM_UNKNOWN, TRUST_E_PROVIDER_UNKNOWN}


def _winverifytrust(path: str) -> int:
    """Код WinVerifyTrust для файлу (0 — підпис дійсний). Без запитів у мережу: перевірка відкликання
    сертифіката лише з кешу, щоб не зависати без інтернету."""
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8)]

    class FILE_INFO(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pcwszFilePath", wintypes.LPCWSTR), ("hFile", wintypes.HANDLE),
                    ("pgKnownSubject", ctypes.c_void_p)]

    class TRUST_DATA(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pPolicyCallbackData", ctypes.c_void_p),
                    ("pSIPClientData", ctypes.c_void_p), ("dwUIChoice", wintypes.DWORD),
                    ("fdwRevocationChecks", wintypes.DWORD), ("dwUnionChoice", wintypes.DWORD),
                    ("pFile", ctypes.POINTER(FILE_INFO)), ("dwStateAction", wintypes.DWORD),
                    ("hWVTStateData", wintypes.HANDLE), ("pwszURLReference", wintypes.LPCWSTR),
                    ("dwProvFlags", wintypes.DWORD), ("dwUIContext", wintypes.DWORD),
                    ("pSignatureSettings", ctypes.c_void_p)]

    action = GUID(0x00AAC56B, 0xCD44, 0x11D0, (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
    fi = FILE_INFO(ctypes.sizeof(FILE_INFO), path, None, None)
    td = TRUST_DATA()
    td.cbStruct = ctypes.sizeof(TRUST_DATA)
    td.dwUIChoice = 2  # WTD_UI_NONE
    td.fdwRevocationChecks = 0  # WTD_REVOKE_NONE
    td.dwUnionChoice = 1  # WTD_CHOICE_FILE
    td.pFile = ctypes.pointer(fi)
    td.dwStateAction = 1  # WTD_STATEACTION_VERIFY
    td.dwProvFlags = 0x1000  # WTD_CACHE_ONLY_URL_RETRIEVAL
    wvt = ctypes.windll.wintrust.WinVerifyTrust
    wvt.argtypes = [wintypes.HANDLE, ctypes.POINTER(GUID), ctypes.c_void_p]
    wvt.restype = ctypes.c_long
    rc = wvt(None, ctypes.byref(action), ctypes.byref(td))
    td.dwStateAction = 2  # WTD_STATEACTION_CLOSE
    wvt(None, ctypes.byref(action), ctypes.byref(td))
    return rc & 0xFFFFFFFF


def signature(path: str) -> dict:
    """-> {"status": valid | unsigned | invalid | unknown, "code": int}."""
    if not E.IS_WIN:
        return {"status": "unknown", "code": 0}
    try:
        code = _winverifytrust(os.path.abspath(path))
    except Exception:
        return {"status": "unknown", "code": -1}
    if code == 0:
        return {"status": "valid", "code": 0}
    return {"status": "unsigned" if code in UNSIGNED else "invalid", "code": code}


def signer(path: str) -> str:
    """Видавець (Subject сертифіката), лише для файлів із дійсним підписом. '' — не вдалося дізнатися."""
    if not E.IS_WIN:
        return ""
    lit = "'" + os.path.abspath(path).replace("'", "''") + "'"
    _rc, out = E.ps(f"(Get-AuthenticodeSignature -LiteralPath {lit}).SignerCertificate.Subject", 30, ro=True)
    return (out or "").strip().splitlines()[0].strip() if (out or "").strip() else ""


def _cn(subject: str) -> str:
    m = re.search(r"CN=(\"[^\"]+\"|[^,]+)", subject or "")
    return (m.group(1).strip('"') if m else subject or "").strip().lower()


def own_publisher() -> str:
    """Видавець, якого має мати оновлення: з buildinfo.SIGNER або з підпису самої OptimaX.exe. '' — не вимагаємо."""
    if SIGNER:
        return SIGNER
    if E.IS_WIN and getattr(sys, "frozen", False) and signature(sys.executable)["status"] == "valid":
        return signer(sys.executable) or "*"  # «*» — підписана, але видавця прочитати не вдалося
    return ""


def check_file(path: str, expected_sha256: str, publisher: str = None, name: str = None) -> dict:
    """Перевіряє файл перед запуском. Невдача — VerifyError із поясненням. -> {sha256, signature, signer}."""
    name = name or os.path.basename(path)
    if not expected_sha256 or not HEX64.match(expected_sha256):
        raise VerifyError("vf.no_hash", name=name)
    got = sha256(path)
    if got != expected_sha256.lower():
        raise VerifyError("vf.hash_mismatch", name=name, got=got[:16], exp=expected_sha256[:16].lower())
    sig = signature(path)
    if sig["status"] == "invalid":
        raise VerifyError("vf.sig_invalid", name=name, code=f"0x{sig['code']:08X}")
    publisher = own_publisher() if publisher is None else publisher
    who = ""
    if publisher:
        if sig["status"] != "valid":
            raise VerifyError("vf.sig_missing", name=name)
        who = signer(path)
        if publisher != "*" and who and _cn(who) != _cn(publisher):
            raise VerifyError("vf.sig_other", name=name, who=_cn(who), want=_cn(publisher))
    return {"sha256": got, "signature": sig["status"], "signer": who}
