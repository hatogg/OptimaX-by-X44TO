"""Безпечне оновлення (6.4): файл, який OptimaX завантажує й запускає з правами адміністратора, мусить пройти
перевірку SHA-256 (digest із GitHub і SHA256SUMS.txt) і цифрового підпису — і ще раз безпосередньо перед запуском."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

from _util import IS_WIN, ROOT, SCRIPTS, skip, tail

sys.path.insert(0, ROOT)
_CACHE = {}


def report() -> dict:
    if IS_WIN:
        skip("fake Windows runs only outside Windows")
    if "r" not in _CACHE:
        out = tempfile.mkdtemp(prefix="oxuv_")
        env = dict(os.environ, FAKE_HW="gaming", FAKE_TARGET=os.path.join(SCRIPTS, "update_verify.py"),
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fake_windows.py"), "--out", out], cwd=ROOT,
                           env=env, capture_output=True, timeout=600)
        text = (p.stdout + p.stderr).decode("utf-8", "replace")
        path = os.path.join(out, "roundtrip.json")
        assert p.returncode == 0 and os.path.exists(path), tail(text)
        with open(path, encoding="utf-8") as f:
            _CACHE["r"] = json.load(f)
    return _CACHE["r"]


def test_verified_update_is_launched_from_a_protected_folder():
    r = report()
    assert r["info"] == {"sha256": True, "sums_url": True, "name": "OptimaX-Setup-9.9.exe"}, r["info"]
    assert r["ok"] == {"err": None, "in_programdata": True} and r["ok_launch"], (r["ok"], r["ok_launch"])


def test_file_swapped_before_launch_is_not_run():
    assert report()["swapped_launch"] == {"launched": False, "error": True, "runs": 1}


def test_bad_or_unverifiable_files_are_refused():
    r = report()
    assert r["tampered"] == ["vf.hash_mismatch", False], "a file that failed the check must not stay on disk"
    assert r["differ"] == "vf.sources_differ"
    assert r["no_hash"] == "vf.no_hash"
    assert r["sums_only"] is None and r["digest_only"] is None and r["derived_sums"] is None


def test_signature_policy():
    r = report()
    assert r["sig_invalid"] == "vf.sig_invalid", "a broken signature is never accepted"
    assert r["sig_missing"] == "vf.sig_missing", "a signed OptimaX accepts only signed updates"
    assert r["sig_other"] == "vf.sig_other", "…from the same publisher"
    assert r["sig_same"] is None


def test_checksum_helpers():
    import verify as V
    data = b"OptimaX" * 1000
    sha = hashlib.sha256(data).hexdigest()
    p = os.path.join(tempfile.mkdtemp(prefix="oxv_"), "f.exe")
    with open(p, "wb") as f:
        f.write(data)
    assert V.sha256(p) == sha
    assert V.parse_sums(f"{sha.upper()}  F.exe\n{sha} *g.exe\nbroken line\n") == {"f.exe": sha, "g.exe": sha}
    assert V.digest_of({"digest": "sha256:" + sha.upper()}) == sha and V.digest_of({"digest": "md5:x"}) == ""
    assert V.expected_hash("f.exe", sha, f"{sha}  f.exe") == sha
    for args, key in ((("f.exe", "", None), "vf.no_hash"), (("f.exe", sha, "0" * 64 + "  f.exe"), "vf.sources_differ")):
        try:
            V.expected_hash(*args)
            raise AssertionError(key)
        except V.VerifyError as e:
            assert e.key == key
    assert V.check_file(p, sha, publisher="")["sha256"] == sha
    try:
        V.check_file(p, "f" * 64, publisher="")
        raise AssertionError("hash mismatch must fail")
    except V.VerifyError as e:
        assert e.key == "vf.hash_mismatch"


def test_winverifytrust_on_real_windows():
    """Справжня перевірка підпису Windows: підписаний файл — valid, його копія з одним зміненим байтом — invalid,
    файл без підпису — unsigned."""
    if not IS_WIN:
        skip("WinVerifyTrust exists only on Windows")
    import shutil
    import verify as V
    git = shutil.which("git")
    signed = git and V.signature(git)["status"] == "valid"
    tmp = tempfile.mkdtemp(prefix="oxwvt_")
    plain = os.path.join(tmp, "plain.exe")
    with open(plain, "wb") as f:
        f.write(b"MZ" + os.urandom(4096))
    assert V.signature(plain)["status"] in ("unsigned", "invalid"), V.signature(plain)  # ctypes-виклик працює
    if not signed:
        skip("no Authenticode-signed git.exe on this machine")
    bad = os.path.join(tmp, "bad.exe")
    shutil.copyfile(git, bad)
    with open(bad, "r+b") as f:
        f.seek(os.path.getsize(bad) // 3)
        b = f.read(1)
        f.seek(-1, 1)
        f.write(bytes([b[0] ^ 0xFF]))
    assert V.signature(bad)["status"] == "invalid", V.signature(bad)
    assert V.signer(git), "the publisher of a signed file must be readable"
