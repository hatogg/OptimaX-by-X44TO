"""
OptimaX — оновлення через GitHub Releases.

У релізі мають лежати OptimaX-Setup-<версія>.exe (для встановленої програми) і, за бажанням,
OptimaX-<версія>-portable.exe. Тег релізу — версія: v6.1, 6.1 тощо.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request

import engine as E
import lifecycle as L
from i18n import tr

# Репозиторій із релізами у форматі "власник/репозиторій". Порожньо — перевірка оновлень вимкнена.
# Збірка з CI записує його в buildinfo.py (packaging/release.py buildinfo); змінна середовища важливіша.
try:
    import buildinfo as _bi
    _BUILT_REPO = getattr(_bi, "UPDATE_REPO", "") or ""
except ImportError:
    _BUILT_REPO = ""
UPDATE_REPO = os.environ.get("OPTIMAX_UPDATE_REPO", "") or _BUILT_REPO
SETUP_RE = re.compile(r"^OptimaX-Setup-[\d.]+\.exe$", re.I)
PORTABLE_RE = re.compile(r"^OptimaX-[\d.]+-portable\.exe$", re.I)


def enabled() -> bool:
    return bool(UPDATE_REPO) or not E.IS_WIN


def vtuple(v: str):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def check(log=lambda *_: None):
    """-> {version, notes, page, url, size, kind} якщо є новіша версія, інакше None."""
    if not E.IS_WIN:  # демо: показати, як виглядає оновлення
        log(tr("upd.checking"))
        nxt = ".".join(map(str, vtuple(E.VERSION)[:1] + (vtuple(E.VERSION)[1:2] or (0,)))).split(".")
        nxt = f"{nxt[0]}.{int(nxt[1]) + 1}"
        return dict(version=nxt, notes="• Нові твіки для Windows 11 26H1\n• Швидший аналізатор диска\n• Виправлення",
                    page="https://github.com/", url="", size=48_200_000, kind="setup")
    if not UPDATE_REPO:
        return None
    req = urllib.request.Request(f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest",
                                 headers={"User-Agent": f"{E.APP_NAME}/{E.VERSION}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        rel = json.load(r)
    ver = (rel.get("tag_name") or rel.get("name") or "").lstrip("vV")
    log(tr("upd.latest", v=ver or "?"))
    if vtuple(ver) <= vtuple(E.VERSION):
        return None
    pattern = SETUP_RE if L.is_installed() else PORTABLE_RE
    asset = next((a for a in rel.get("assets", []) if pattern.match(a.get("name", ""))), None)
    return dict(version=ver, notes=(rel.get("body") or "").strip()[:1500], page=rel.get("html_url", ""),
                url=asset["browser_download_url"] if asset else "", size=asset.get("size", 0) if asset else 0,
                kind="setup" if L.is_installed() else "portable")


def download(info: dict, log, progress=None) -> str:
    if not E.IS_WIN or E.DRY_RUN:
        for i in range(10):
            if progress:
                progress(i, 10, tr("upd.downloading", mb=f"{info.get('size', 0) / 2**20 * i / 10:.0f}"))
            time.sleep(0.01)
        log("  [dry-run] " + tr("upd.downloaded"))
        return ""
    name = info["url"].rsplit("/", 1)[-1]
    dest = os.path.join(tempfile.gettempdir(), name)
    req = urllib.request.Request(info["url"], headers={"User-Agent": f"{E.APP_NAME}/{E.VERSION}"})
    got, total = 0, info.get("size") or 0
    with urllib.request.urlopen(req, timeout=60) as r, open(dest + ".part", "wb") as f:
        while True:
            if E.CANCEL.is_set():
                raise RuntimeError(tr("e.stopped").strip())
            chunk = r.read(1 << 17)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if progress and total:
                progress(got, total, tr("upd.downloading", mb=f"{got / 2**20:.0f}"))
    if total and os.path.getsize(dest + ".part") != total:
        raise RuntimeError(tr("fps.bad_download"))
    os.replace(dest + ".part", dest)
    log(tr("upd.downloaded"))
    return dest


def launch(path: str, kind: str) -> bool:
    """Запускає інсталятор у тихому режимі (він сам закриє OptimaX і запустить нову версію)."""
    if not path or not E.IS_WIN or E.DRY_RUN:
        return False
    if kind == "setup":
        subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/UPDATE=1"],
                         creationflags=E.CREATE_NO_WINDOW)
    else:
        os.startfile(os.path.dirname(path))  # noqa: портативна версія — показуємо завантажений файл
    return True
