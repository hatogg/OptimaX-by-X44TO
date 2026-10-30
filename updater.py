"""
OptimaX — оновлення через GitHub Releases.

У релізі мають лежати OptimaX-Setup-<версія>.exe (для встановленої програми) і, за бажанням,
OptimaX-<версія>-portable.exe. Тег релізу — версія: v6.1, 6.1 тощо.

Безпека (6.4): завантажений файл запускається лише після перевірки (verify.py) — SHA-256 має збігтися з
сумою з GitHub (digest ресурсу) та/або SHA256SUMS.txt релізу, а цифровий підпис не може бути пошкодженим
чи чужим. Файл кладеться в папку, куди звичайний користувач не може писати, і перевіряється ще раз
безпосередньо перед запуском.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
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
SUMS_NAME = "SHA256SUMS.txt"
SETUP_RE = re.compile(r"^OptimaX-Setup-[\d.]+\.exe$", re.I)
PORTABLE_RE = re.compile(r"^OptimaX-[\d.]+-portable\.exe$", re.I)
CHECK_EVERY = 6 * 3600   # автоматична перевірка не частіше
RETRY_AFTER = 30 * 60    # після невдалої спроби (немає мережі, GitHub недоступний)
SNOOZE = 24 * 3600       # «Пізніше» ховає повідомлення про цю версію на добу
UA = f"{E.APP_NAME}/{E.VERSION}"


def enabled() -> bool:
    return bool(UPDATE_REPO) or not E.IS_WIN


def vtuple(v: str):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def due(cfg: dict, now: float = None) -> bool:
    """Чи пора автоматично перевіряти. Невдала спроба не відкладає наступну на весь інтервал."""
    now = time.time() if now is None else now
    cfg = cfg or {}
    if now - (cfg.get("last_try") or 0) < RETRY_AFTER:
        return False
    return now - (cfg.get("last_check") or 0) >= CHECK_EVERY


def cached(cfg: dict):
    """Остання знайдена новіша версія — щоб банер не зникав, якщо програму перезапустили до наступної перевірки."""
    info = (cfg or {}).get("latest")
    if isinstance(info, dict) and info.get("version") and vtuple(info["version"]) > vtuple(E.VERSION):
        return info
    return None


def snoozed(cfg: dict, version: str, now: float = None) -> bool:
    s = (cfg or {}).get("snooze") or {}
    now = time.time() if now is None else now
    return bool(version) and s.get("v") == version and now < (s.get("until") or 0)


def _open(url: str, timeout: int, accept: str = None):
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def _api_latest() -> dict:
    with _open(f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest", 15, "application/vnd.github+json") as r:
        return json.load(r)


def _page_latest() -> dict:
    """github.com/…/releases/latest переадресовує на сторінку тегу. На відміну від API, тут немає ліміту
    60 запитів на годину з однієї IP-адреси, який легко вичерпати за спільною адресою провайдера (CGNAT)."""
    with _open(f"https://github.com/{UPDATE_REPO}/releases/latest", 15) as r:
        final = r.geturl()
    m = re.search(r"/releases/tag/([^/?#]+)", final or "")
    if not m:
        raise RuntimeError(f"no release tag in {final}")
    tag = urllib.parse.unquote(m.group(1))
    ver = tag.lstrip("vV")
    base = f"https://github.com/{UPDATE_REPO}/releases/download/{urllib.parse.quote(tag)}/"
    return {"tag_name": tag, "html_url": final, "body": "",
            "assets": [{"name": n, "browser_download_url": base + n, "size": 0}
                       for n in (f"OptimaX-Setup-{ver}.exe", f"OptimaX-{ver}-portable.exe", SUMS_NAME)]}


def _ps_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _ps_api_latest() -> dict:
    """Через PowerShell (Schannel): Python бачить лише вже завантажені кореневі сертифікати Windows, а на свіжій
    системі потрібного кореня може ще не бути — тоді urllib падає з CERTIFICATE_VERIFY_FAILED."""
    url = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
    script = ("[Net.ServicePointManager]::SecurityProtocol=[Net.ServicePointManager]::SecurityProtocol -bor 3072;"
              f"$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 20 -UserAgent {_ps_quote(UA)} -Uri {_ps_quote(url)};"
              "[Console]::Out.Write($r.Content)")
    data = E.parse_json_out(E.ps(script, 40, ro=True)[1])
    if not isinstance(data, dict) or not data.get("tag_name"):
        raise RuntimeError("PowerShell: no release data")
    return data


def latest_release(log=lambda *_: None) -> dict:
    """Дані останнього релізу: API → сторінка релізу → PowerShell. Помилка — лише якщо не спрацювало жодне."""
    errors = []
    for fn in (_api_latest, _page_latest, _ps_api_latest):
        if fn is _ps_api_latest and not E.IS_WIN:
            continue
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — пробуємо наступний спосіб
            errors.append(f"{type(e).__name__}: {e}")
            log(f"  · {fn.__name__.strip('_')}: {type(e).__name__}: {str(e)[:120]}")
    raise RuntimeError(errors[0] if errors else "no update source")


def clean_notes(body: str, limit: int = 1500) -> str:
    """Нотатки релізу для вікна оновлення: без англійського блоку <details>, списку файлів і розмітки Markdown."""
    body = re.sub(r"(?s)<details>.*?</details>", "", (body or "").replace("\r\n", "\n"))
    body = body.split("\n---\n")[0]
    body = re.sub(r"^#+\s*", "", body, flags=re.M)
    body = re.sub(r"\*\*|`", "", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if len(body) > limit:
        body = body[:limit].rsplit("\n", 1)[0].rstrip() + "\n…"
    return body


def from_release(rel: dict, installed: bool):
    """Реліз GitHub -> {version, notes, page, url, size, kind} або None, якщо він не новіший за поточну версію."""
    ver = (rel.get("tag_name") or rel.get("name") or "").lstrip("vV")
    if vtuple(ver) <= vtuple(E.VERSION):
        return None
    pattern = SETUP_RE if installed else PORTABLE_RE
    assets = rel.get("assets", [])
    asset = next((a for a in assets if pattern.match(a.get("name", ""))), None)
    sums = next((a for a in assets if a.get("name", "").lower() == SUMS_NAME.lower()), None)
    import verify as V
    return dict(version=ver, notes=clean_notes(rel.get("body") or ""), page=rel.get("html_url", ""),
                url=asset["browser_download_url"] if asset else "", size=asset.get("size", 0) if asset else 0,
                kind="setup" if installed else "portable", name=asset.get("name", "") if asset else "",
                sha256=V.digest_of(asset), sums_url=sums["browser_download_url"] if sums else "")


def check(log=lambda *_: None):
    """-> {version, notes, page, url, size, kind} якщо є новіша версія, інакше None. Мережева помилка — виняток."""
    if not E.IS_WIN:  # демо: показати, як виглядає оновлення
        log(tr("upd.checking"))
        nxt = ".".join(map(str, vtuple(E.VERSION)[:1] + (vtuple(E.VERSION)[1:2] or (0,)))).split(".")
        nxt = f"{nxt[0]}.{int(nxt[1]) + 1}"
        return dict(version=nxt, notes="• Нові твіки для Windows 11 26H1\n• Швидший аналізатор диска\n• Виправлення",
                    page="https://github.com/", url="", size=48_200_000, kind="setup")
    if not UPDATE_REPO:
        return None
    rel = latest_release(log)
    log(tr("upd.latest", v=(rel.get("tag_name") or "?").lstrip("vV")))
    return from_release(rel, L.is_installed())


def download_dir() -> str:
    """Куди класти оновлення. OptimaX працює з правами адміністратора, тож файл, який вона запустить, не повинен
    лежати там, де його може підмінити будь-яка програма користувача (%TEMP%). Папку в ProgramData, створену
    адміністратором, звичайні програми лише читають."""
    if E.IS_WIN and not E.DRY_RUN and E.is_admin():
        d = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "OptimaX", "updates")
    else:
        d = os.path.join(tempfile.gettempdir(), "OptimaX-updates")
    os.makedirs(d, exist_ok=True)
    return d


def fetch_text(url: str, limit: int = 1 << 16) -> str:
    """Невеликий текстовий файл (SHA256SUMS.txt): Python, а якщо він не довіряє сертифікату — PowerShell."""
    try:
        with _open(url, 20) as r:
            return r.read(limit).decode("utf-8", "replace")
    except Exception:
        if not E.IS_WIN:
            raise
    script = ("[Net.ServicePointManager]::SecurityProtocol=[Net.ServicePointManager]::SecurityProtocol -bor 3072;"
              f"(Invoke-WebRequest -UseBasicParsing -TimeoutSec 20 -UserAgent {_ps_quote(UA)} -Uri {_ps_quote(url)}).Content")
    rc, out = E.ps(script, 40, ro=True)
    if rc != 0 or not out.strip():
        raise RuntimeError(f"{SUMS_NAME}: download failed")
    return out


def expected_sha256(info: dict, log=lambda *_: None) -> str:
    """Очікувана сума файлу оновлення з GitHub (digest) і SHA256SUMS.txt релізу; якщо є обидві — мусять збігтися."""
    import verify as V
    name = info.get("name") or urllib.parse.unquote(info["url"].rsplit("/", 1)[-1])
    sums = None
    sums_url = info.get("sums_url") or ""
    if not sums_url and "/releases/download/" in (info.get("url") or ""):  # той самий реліз, поруч із файлом
        sums_url = info["url"].rsplit("/", 1)[0] + "/" + SUMS_NAME
    if sums_url:
        try:
            sums = fetch_text(sums_url)
        except Exception as e:  # без файлу сум лишається digest із GitHub API (якщо він є)
            log(f"  · {SUMS_NAME}: {type(e).__name__}: {str(e)[:100]}")
    return V.expected_hash(name, info.get("sha256") or "", sums)


_VERIFIED: dict = {}  # шлях -> перевірена сума: launch() звіряє файл ще раз безпосередньо перед запуском


def download(info: dict, log, progress=None) -> str:
    import verify as V
    if not E.IS_WIN or E.DRY_RUN:
        for i in range(10):
            if progress:
                progress(i, 10, tr("upd.downloading", mb=f"{info.get('size', 0) / 2**20 * i / 10:.0f}"))
            time.sleep(0.01)
        log("  [dry-run] " + tr("upd.downloaded"))
        log("  [dry-run] " + tr("vf.ok", sig=tr("vf.sig.unknown")))
        return ""
    expected = expected_sha256(info, log)  # до завантаження: без суми файл однаково не запустимо
    name = urllib.parse.unquote(info["url"].rsplit("/", 1)[-1])
    dest = os.path.join(download_dir(), name)
    total = info.get("size") or 0
    for old in (dest, dest + ".part"):  # чужий файл із таким ім'ям (створений заздалегідь) не дописуємо — видаляємо
        try:
            os.remove(old)
        except FileNotFoundError:
            pass
    try:
        got = 0
        with _open(info["url"], 60) as r, open(dest + ".part", "xb") as f:
            total = total or int(r.headers.get("Content-Length") or 0)
            while True:
                if E.CANCEL.is_set():
                    raise InterruptedError(tr("e.stopped").strip())
                chunk = r.read(1 << 17)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if progress and total:
                    progress(got, total, tr("upd.downloading", mb=f"{got / 2**20:.0f}"))
    except InterruptedError as e:
        raise RuntimeError(str(e)) from None
    except (urllib.error.HTTPError, OSError) as e:
        if isinstance(e, urllib.error.HTTPError) and e.code == 404:
            raise
        # сертифікат, антивірус чи проксі, що ламають з'єднання Python, — пробуємо системним завантажувачем
        log(f"  · {type(e).__name__}: {str(e)[:120]}")
        try:
            os.remove(dest + ".part")
        except OSError:
            pass
        if progress:
            progress(0, 1, tr("upd.downloading", mb="…"))
        script = ("[Net.ServicePointManager]::SecurityProtocol=[Net.ServicePointManager]::SecurityProtocol -bor 3072;"
                  f"Invoke-WebRequest -UseBasicParsing -UserAgent {_ps_quote(UA)} -Uri {_ps_quote(info['url'])} "
                  f"-OutFile {_ps_quote(dest + '.part')}")
        E.ps(script, 900, ro=True)
        if not os.path.exists(dest + ".part") or not os.path.getsize(dest + ".part"):
            raise
    if total and os.path.getsize(dest + ".part") != total:
        raise RuntimeError(tr("fps.bad_download"))
    log(tr("upd.downloaded"))
    log(tr("vf.checking"))
    try:
        res = V.check_file(dest + ".part", expected, name=name)
    except V.VerifyError:
        try:
            os.remove(dest + ".part")  # файл, що не пройшов перевірку, не лишаємо на диску
        except OSError:
            pass
        raise
    os.replace(dest + ".part", dest)
    _VERIFIED[dest] = res["sha256"]
    log(tr("vf.ok", sig=tr(f"vf.sig.{res['signature']}") + (f" ({res['signer']})" if res.get("signer") else "")))
    return dest


LAST_ERROR = ""


def launch(path: str, kind: str) -> bool:
    """Запускає інсталятор у тихому режимі (він сам закриє OptimaX і запустить нову версію).
    Перед запуском файл перевіряється ще раз: сума та підпис мають бути тими самими, що й після завантаження."""
    global LAST_ERROR
    LAST_ERROR = ""
    if not path or not E.IS_WIN or E.DRY_RUN:
        return False
    import verify as V
    try:
        if path not in _VERIFIED:
            raise V.VerifyError("vf.no_hash", name=os.path.basename(path))
        V.check_file(path, _VERIFIED[path], name=os.path.basename(path))
    except (V.VerifyError, OSError) as e:
        LAST_ERROR = str(e)
        return False
    if kind == "setup":
        subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/UPDATE=1"],
                         creationflags=E.CREATE_NO_WINDOW)
    else:
        os.startfile(os.path.dirname(path))  # noqa: портативна версія — показуємо завантажений файл
    return True
