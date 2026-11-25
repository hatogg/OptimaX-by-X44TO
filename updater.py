"""
OptimaX — оновлення через GitHub Releases.

У релізі мають лежати OptimaX-Setup-<версія>.exe (для встановленої програми) і, за бажанням,
OptimaX-<версія>-portable.exe. Тег релізу — версія: v6.1, 6.1 тощо.

Канали (7.2): «стабільний» — лише релізи без позначки pre-release (releases/latest); «бета» — найновіший з усіх
опублікованих, зокрема pre-release з тегом v<версія>-beta.<n> (v7.2.0-beta.1). Порядок версій:
7.2.0-beta.1 < 7.2.0-beta.2 < 7.2.0 < 7.2.1-beta.1 — бета передує своїй стабільній версії.

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
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

import engine as E
import lifecycle as L
from i18n import tr

# Репозиторій із релізами у форматі "власник/репозиторій". Порожньо — перевірка оновлень вимкнена.
# Збірка з CI записує його в buildinfo.py (packaging/release.py buildinfo); змінна середовища важливіша — але лише
# під час розробки (див. _configured_repo).
try:
    import buildinfo as _bi
    _BUILT_REPO = getattr(_bi, "UPDATE_REPO", "") or ""
except ImportError:
    _BUILT_REPO = ""
DEFAULT_REPO = "hatogg/OptimaX-by-X44TO"  # офіційний репозиторій (як packaging/release.py DEFAULT_REPO)
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")


def _configured_repo() -> str:
    """Звідки брати оновлення. 6.17: у зібраній програмі (frozen) змінну OPTIMAX_UPDATE_REPO не читаємо — будь-яка
    програма користувача може задати її в HKCU\\Environment, і OptimaX з правами адміністратора завантажила б
    «оновлення» з чужого репозиторію. Змінна лишається для розробки (запуск із вихідного коду)."""
    env = "" if getattr(sys, "frozen", False) else (os.environ.get("OPTIMAX_UPDATE_REPO", "") or "").strip()
    for repo in (env, (_BUILT_REPO or "").strip()):
        if repo and REPO_RE.match(repo) and repo.split("/")[1] not in (".", ".."):
            return repo
    return ""


UPDATE_REPO = _configured_repo()
SUMS_NAME = "SHA256SUMS.txt"
# 7.2: необов'язковий суфікс бети — лише «-beta.<число>», без нових символів, якими можна вийти з папки
SETUP_RE = re.compile(r"^OptimaX-Setup-[\d.]+(?:-beta\.\d{1,4})?\.exe$", re.I)
PORTABLE_RE = re.compile(r"^OptimaX-[\d.]+(?:-beta\.\d{1,4})?-portable\.exe$", re.I)
CHECK_EVERY = 6 * 3600   # автоматична перевірка не частіше
RETRY_AFTER = 30 * 60    # після невдалої спроби (немає мережі, GitHub недоступний)
SNOOZE = 24 * 3600       # «Пізніше» ховає повідомлення про цю версію на добу
UA = f"{E.APP_NAME}/{E.VERSION}"
_FRESH: dict = {}  # (версія, kind) -> дані релізу, отримані з GitHub у цьому процесі (from_release)


def enabled() -> bool:
    return bool(UPDATE_REPO) or not E.IS_WIN


def vtuple(v: str):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


# ───────────────────────── версії й канали (7.2) ─────────────────────────
CHANNELS = ("stable", "beta")
VERSION_RE = re.compile(r"^(\d{1,6}(?:\.\d{1,6}){0,3})(?:-beta\.(\d{1,4}))?$")


def parse_version(v):
    """'7.2.0-beta.1' -> ((7, 2, 0, 0), 0, 1); '7.2' -> ((7, 2, 0, 0), 1, 0); інше (сміттєвий тег) -> None.
    Другий елемент 0 у бети, 1 у стабільної — тож бета менша за свою стабільну версію й більша за попередні."""
    if not isinstance(v, str):
        return None
    m = VERSION_RE.fullmatch(v.strip().lstrip("vV"))
    if not m:
        return None
    nums = tuple(int(n) for n in m.group(1).split("."))
    nums += (0,) * (4 - len(nums))
    return (nums, 0, int(m.group(2))) if m.group(2) is not None else (nums, 1, 0)


def vkey(v):
    """Ключ для порівняння. Версія, яку не вдалося розібрати, — найменша (такий реліз ніколи не «новіший»)."""
    return parse_version(v) or ((-1,), 0, 0)


def newer(v, than) -> bool:
    """Чи v новіша за than. Нерозібрана v — ніколи; нерозібрана than (дивна поточна версія) — за цифрами."""
    a = parse_version(v)
    if a is None:
        return False
    b = parse_version(than)
    if b is None:
        b = ((vtuple(than) + (0,) * 4)[:4], 1, 0)
    return a > b


def is_beta(v) -> bool:
    p = parse_version(v)
    return bool(p) and p[1] == 0


def channel(cfg: dict = None) -> str:
    """Канал оновлень. settings.json може переписати будь-яка програма користувача — беремо лише значення з
    білого списку, усе інше (зокрема відсутнє) — «стабільний»."""
    if cfg is None:
        import features as F
        cfg = F.CFG["updates"]
    c = cfg.get("channel") if isinstance(cfg, dict) else None
    return "beta" if isinstance(c, str) and c == "beta" else "stable"


def shown(v: str) -> str:
    """Версія для інтерфейсу: бета — з позначкою «бета»."""
    v = str(v or "")
    return tr("ch.ver_beta", v=v) if is_beta(v) else v


def release_ok(rel, chan: str) -> bool:
    """Чи підходить реліз GitHub каналу: не чернетка, тег — версія; стабільний — без pre-release і без «-beta»."""
    if not isinstance(rel, dict) or rel.get("draft"):
        return False
    ver = str(rel.get("tag_name") or "")
    if parse_version(ver) is None:
        return False
    if chan == "beta":
        return True
    return not rel.get("prerelease") and not is_beta(ver)


def pick_release(rels, chan: str):
    """Найновіший за порядком версій реліз каналу зі списку GitHub (None — жодного)."""
    ok = [r for r in (rels if isinstance(rels, list) else []) if release_ok(r, chan)]
    return max(ok, key=lambda r: vkey(r.get("tag_name")), default=None)


def due(cfg: dict, now: float = None) -> bool:
    """Чи пора автоматично перевіряти. Невдала спроба не відкладає наступну на весь інтервал."""
    now = time.time() if now is None else now
    cfg = cfg or {}
    if now - (cfg.get("last_try") or 0) < RETRY_AFTER:
        return False
    return now - (cfg.get("last_check") or 0) >= CHECK_EVERY


def _trusted_repo() -> str:
    return UPDATE_REPO or DEFAULT_REPO


def release_page(url) -> str:
    """Сторінка релізу для браузера: лише github.com нашого репозиторію, інакше — сторінка останнього релізу.
    (webbrowser.open передає рядок у ShellExecute, тож шлях до програми замість адреси запустив би її.)"""
    base = f"https://github.com/{_trusted_repo()}/"
    if isinstance(url, str) and url[:len(base)].lower() == base.lower() and not re.search(r"[\s\\\"'<>]", url):
        return url
    return base + "releases/latest"


def cached(cfg: dict):
    """Остання знайдена новіша версія — щоб банер не зникав, якщо програму перезапустили до наступної перевірки.
    6.17: settings.json може переписати будь-яка програма користувача, тож звідси беремо лише те, що показується
    (версія, нотатки, сторінка релізу), — без адреси файлу, суми й імені. Завантаження (download) все одно бере
    дані релізу заново з GitHub."""
    info = (cfg or {}).get("latest")
    ver = info.get("version") if isinstance(info, dict) else None
    if not isinstance(ver, str) or not re.fullmatch(r"\d[\w.+-]{0,31}", ver) or not newer(ver, E.VERSION):
        return None
    if is_beta(ver) and channel(cfg) != "beta":  # 7.2: після переходу на стабільний знайдену раніше бету не пропонуємо
        return None
    out = {"version": ver}
    if "notes" in info:
        out["notes"] = clean_notes(str(info.get("notes") or ""))
    if "page" in info:
        out["page"] = release_page(info.get("page"))
    return out


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
    return _synth(urllib.parse.unquote(m.group(1)), final)


def _synth(tag: str, page: str, prerelease: bool = False) -> dict:
    """Реліз без API: імена файлів відомі заздалегідь, суму дасть SHA256SUMS.txt того самого релізу."""
    ver = tag.lstrip("vV")
    base = f"https://github.com/{UPDATE_REPO}/releases/download/{urllib.parse.quote(tag)}/"
    return {"tag_name": tag, "html_url": page, "body": "", "prerelease": prerelease,
            "assets": [{"name": n, "browser_download_url": base + n, "size": 0}
                       for n in (f"OptimaX-Setup-{ver}.exe", f"OptimaX-{ver}-portable.exe", SUMS_NAME)]}


def _api_releases() -> list:
    """Канал «бета»: список релізів (новіші спершу; чернетки API без токена не показує, але й їх відкидаємо)."""
    with _open(f"https://api.github.com/repos/{UPDATE_REPO}/releases?per_page=30", 15,
               "application/vnd.github+json") as r:
        data = json.load(r)
    if not isinstance(data, list):
        raise RuntimeError("API: no release list")
    return data


def _feed_releases() -> list:
    """Стрічка releases.atom — без ліміту API (CGNAT). Позначки pre-release у ній немає, тож бету впізнаємо за тегом
    (-beta.N); теги, що не є версіями, відкидаємо одразу, а адресу сторінки будуємо самі — не беремо зі стрічки."""
    with _open(f"https://github.com/{UPDATE_REPO}/releases.atom", 15) as r:
        text = r.read(1 << 20).decode("utf-8", "replace")
    out, seen = [], set()
    for raw in re.findall(r"/releases/tag/([^\"'<>\s/?#]+)", text):
        tag = urllib.parse.unquote(raw)
        if tag in seen or parse_version(tag) is None:
            continue
        seen.add(tag)
        page = f"https://github.com/{UPDATE_REPO}/releases/tag/{urllib.parse.quote(tag)}"
        out.append(_synth(tag, page, prerelease=is_beta(tag)))
    if not out:
        raise RuntimeError("releases.atom: no releases")
    return out


def _ps_quote(s: str) -> str:
    # 7.1.1: secfs.psq подвоює й типографські лапки ‘ ’ ‚ ‛ — PowerShell теж закінчує ними рядок
    import secfs as SF
    return SF.psq(s)


def _ps_get_json(url: str):
    script = ("[Net.ServicePointManager]::SecurityProtocol=[Net.ServicePointManager]::SecurityProtocol -bor 3072;"
              f"$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 20 -UserAgent {_ps_quote(UA)} -Uri {_ps_quote(url)};"
              "[Console]::Out.Write($r.Content)")
    return E.parse_json_out(E.ps(script, 40, ro=True)[1])


def _ps_api_latest() -> dict:
    """Через PowerShell (Schannel): Python бачить лише вже завантажені кореневі сертифікати Windows, а на свіжій
    системі потрібного кореня може ще не бути — тоді urllib падає з CERTIFICATE_VERIFY_FAILED."""
    data = _ps_get_json(f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest")
    if not isinstance(data, dict) or not data.get("tag_name"):
        raise RuntimeError("PowerShell: no release data")
    return data


def _ps_api_releases() -> list:
    data = _ps_get_json(f"https://api.github.com/repos/{UPDATE_REPO}/releases?per_page=30")
    if not isinstance(data, list):
        raise RuntimeError("PowerShell: no release list")
    return data


def latest_release(log=lambda *_: None) -> dict:
    """Дані останнього релізу: API → сторінка релізу → PowerShell. Помилка — лише якщо не спрацювало жодне."""
    return _first((_api_latest, _page_latest, _ps_api_latest), log)


def all_releases(log=lambda *_: None) -> list:
    """Канал «бета»: список релізів — API → releases.atom → PowerShell."""
    return _first((_api_releases, _feed_releases, _ps_api_releases), log)


def _first(fns, log):
    errors = []
    for fn in fns:
        if fn in (_ps_api_latest, _ps_api_releases) and not E.IS_WIN:
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


def from_release(rel: dict, installed: bool, chan: str = None):
    """Реліз GitHub -> {version, notes, page, url, size, kind} або None, якщо він не новіший за поточну версію чи
    не з цього каналу. 7.2: з бети на стабільний канал не «відкочуємося» — стабільна пропонується, лише коли вона
    новіша за встановлену бету (7.2.0 > 7.2.0-beta.3)."""
    chan = chan if chan in CHANNELS else channel()
    if not release_ok(rel, chan):
        return None
    ver = str(rel.get("tag_name") or "").lstrip("vV")
    if not newer(ver, E.VERSION):
        return None
    pattern = SETUP_RE if installed else PORTABLE_RE
    assets = rel.get("assets", [])
    asset = next((a for a in assets if pattern.match(a.get("name", ""))), None)
    sums = next((a for a in assets if a.get("name", "").lower() == SUMS_NAME.lower()), None)
    import verify as V
    info = dict(version=ver, notes=clean_notes(rel.get("body") or ""), page=rel.get("html_url", ""), beta=is_beta(ver),
                url=asset["browser_download_url"] if asset else "", size=asset.get("size", 0) if asset else 0,
                kind="setup" if installed else "portable", name=asset.get("name", "") if asset else "",
                sha256=V.digest_of(asset), sums_url=sums["browser_download_url"] if sums else "")
    # 6.17: download() бере адресу й суму лише звідси (дані, щойно отримані з GitHub у цьому процесі), а не з того,
    # що йому передали, — передане могло прийти з settings.json
    _FRESH[(info["version"], info["kind"])] = dict(info)
    return info


def check(log=lambda *_: None, chan: str = None):
    """-> {version, notes, page, url, size, kind} якщо є новіша версія, інакше None. Мережева помилка — виняток."""
    chan = chan if chan in CHANNELS else channel()
    if not E.IS_WIN:  # демо: показати, як виглядає оновлення
        log(tr("upd.checking"))
        nxt = ".".join(map(str, vtuple(E.VERSION)[:1] + (vtuple(E.VERSION)[1:2] or (0,)))).split(".")
        nxt = f"{nxt[0]}.{int(nxt[1]) + 1}" + (".0-beta.1" if chan == "beta" else "")
        return dict(version=nxt, notes="• Нові твіки для Windows 11 26H1\n• Швидший аналізатор диска\n• Виправлення",
                    page="https://github.com/", url="", size=48_200_000, kind="setup", beta=is_beta(nxt))
    if not UPDATE_REPO:
        return None
    log(tr("ch.log", ch=tr(f"ch.{chan}")))
    if chan == "beta":
        rel = pick_release(all_releases(log), "beta")
        if rel is None:
            return None
    else:
        rel = latest_release(log)
    log(tr("upd.latest", v=shown((rel.get("tag_name") or "?").lstrip("vV"))))
    return from_release(rel, L.is_installed(), chan)


def download_dir() -> str:
    """Куди класти оновлення. OptimaX працює з правами адміністратора, тож файл, який вона запустить, не повинен
    лежати там, де його може підмінити будь-яка програма користувача (%TEMP%). Папка в ProgramData — власність
    адміністраторів, звичайні програми її лише читають (secfs.secure_dir)."""
    if E.IS_WIN and not E.DRY_RUN and E.is_admin():
        # 6.7: папку захищаємо явно — у ProgramData будь-хто може створити її наперед і стати власником, а власник
        # міг би підмінити перевірений інсталятор між перевіркою й запуском
        return E.admin_dir("updates")
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
    if sums_url and not release_url(sums_url):  # 6.17: файл сум — лише з релізу нашого репозиторію
        sums_url = ""
    if sums_url:
        try:
            sums = fetch_text(sums_url)
        except Exception as e:  # без файлу сум лишається digest із GitHub API (якщо він є)
            log(f"  · {SUMS_NAME}: {type(e).__name__}: {str(e)[:100]}")
    return V.expected_hash(name, info.get("sha256") or "", sums)


_VERIFIED: dict = {}  # шлях -> перевірена сума: launch() звіряє файл ще раз безпосередньо перед запуском
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,150}$")  # інші файли релізу (архіви шарів mining.py)


def release_url(url, name: str = None) -> bool:
    """Адреса файлу з релізу нашого репозиторію: https://github.com/<репо>/releases/download/<тег>/<файл>.
    name — яким має бути останній сегмент (ім'я файлу)."""
    prefix = f"https://github.com/{_trusted_repo()}/releases/download/"
    if not isinstance(url, str) or url[:len(prefix)].lower() != prefix.lower() or re.search(r"[\s\\?#]", url):
        return False
    parts = [urllib.parse.unquote(p) for p in url[len(prefix):].split("/")]
    if len(parts) < 2 or any(not p or p in (".", "..") or re.search(r"[\\/:]", p) for p in parts):
        return False  # ..%5C, %2F та інші способи вийти з папки релізу
    return name is None or parts[-1] == name


def asset_name_ok(name, kind: str = None) -> bool:
    """Ім'я файлу, з якого складається шлях у папці завантажень: інсталятор/портативна OptimaX — лише за шаблоном
    SETUP_RE / PORTABLE_RE, інше — просте ім'я без папок і «..»."""
    if not isinstance(name, str) or not name:
        return False
    if kind == "setup":
        return bool(SETUP_RE.fullmatch(name))
    if kind == "portable":
        return bool(PORTABLE_RE.fullmatch(name))
    return bool(SAFE_NAME_RE.fullmatch(name)) and ".." not in name


def _trusted_info(info: dict, log) -> dict:
    """Дані для завантаження. Оновлення самої OptimaX (kind setup/portable або дані з cached() без адреси) — лише
    з релізу, отриманого з GitHub у цьому процесі; якщо такого немає — перевіряємо GitHub заново (check)."""
    import verify as V
    info = info if isinstance(info, dict) else {}
    kind = info.get("kind")
    if kind in ("setup", "portable") or not info.get("url"):
        own = kind if kind in ("setup", "portable") else "setup" if L.is_installed() else "portable"
        fresh = _FRESH.get((str(info.get("version") or ""), own))
        if fresh is None:
            new = check(log)
            fresh = _FRESH.get((new["version"], new["kind"])) if isinstance(new, dict) and new.get("url") else None
        if not fresh or not fresh.get("url"):
            raise V.VerifyError("vf.no_hash", name=f"{E.APP_NAME} {info.get('version') or ''}".strip())
        info = dict(fresh)
    kind = info.get("kind") if info.get("kind") in ("setup", "portable") else None
    name = info.get("name") or urllib.parse.unquote(str(info.get("url") or "").rsplit("/", 1)[-1])
    if not asset_name_ok(name, kind) or not release_url(info.get("url"), name):
        raise V.VerifyError("vf.no_hash", name=re.sub(r"[^\w.+-]", "_", str(name))[:80] or "?")
    sums_url = info.get("sums_url") or ""
    if sums_url and not release_url(sums_url):
        log(f"  · {SUMS_NAME}: ignored ({sums_url[:80]})")
        sums_url = ""
    return dict(info, name=name, sums_url=sums_url)


def download(info: dict, log, progress=None, publisher=None) -> str:
    """publisher: чий підпис вимагати (None — як у самої OptimaX; "" — лише сума, для архівів без підпису)."""
    import verify as V
    if not E.IS_WIN or E.DRY_RUN:
        for i in range(10):
            if progress:
                progress(i, 10, tr("upd.downloading", mb=f"{info.get('size', 0) / 2**20 * i / 10:.0f}"))
            time.sleep(0.01)
        log("  [dry-run] " + tr("upd.downloaded"))
        log("  [dry-run] " + tr("vf.ok", sig=tr("vf.sig.unknown")))
        return ""
    # 6.17: адреса, ім'я й сума — лише з перевірених даних релізу (не з settings.json); ім'я — за шаблоном, без
    # «..%5C», щоб файл (і видалення старого нижче) не вийшов за межі папки завантажень
    info = _trusted_info(info, log)
    name = info["name"]
    expected = expected_sha256(info, log)  # до завантаження: без суми файл однаково не запустимо
    ddir = download_dir()
    dest = os.path.join(ddir, name)
    if os.path.dirname(os.path.abspath(dest)) != os.path.abspath(ddir):
        raise V.VerifyError("vf.no_hash", name=os.path.basename(name) or "?")
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
        if E.CANCEL.is_set():  # «Зупинити» під час запасного завантаження — це зупинка, а не помилка мережі
            raise RuntimeError(tr("e.stopped").strip()) from None
        if not os.path.exists(dest + ".part") or not os.path.getsize(dest + ".part"):
            raise
    if total and os.path.getsize(dest + ".part") != total:
        raise RuntimeError(tr("fps.bad_download"))
    log(tr("upd.downloaded"))
    log(tr("vf.checking"))
    try:
        res = V.check_file(dest + ".part", expected, publisher=publisher, name=name)
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


def error_kind(e: BaseException) -> str:
    """Чому не вдалося завантажити оновлення: "cancelled" — зупинив користувач, "verify" — файл не пройшов
    перевірку суми чи підпису, "network" — не завантажився (мережа, сервер, обрив). Викликати в потоці завантаження:
    скасування — це токен саме цієї дії."""
    import verify as V
    if E.CANCEL.is_set():
        return "cancelled"
    if isinstance(e, V.VerifyError):
        return "verify"
    return "network"


def download_job(info: dict, log, progress=None) -> dict:
    """Завантаження для вікна виконання: {"path"} або {"error", "kind"}; зупинка — {"cancelled": True}, без error,
    щоб вікно показало «Зупинено», а не «Помилка»."""
    try:
        return {"path": download(info, log, progress)}
    except Exception as e:  # noqa: BLE001
        kind = error_kind(e)
        if kind == "cancelled":
            log(tr("e.stopped"))
            return {"cancelled": True, "kind": kind}
        log(tr("e.err", err=f"{type(e).__name__}: {e}"))
        return {"error": str(e) or type(e).__name__, "kind": kind}


def _hold(path: str):
    """7.1.1: дескриптор файлу, відкритого лише зі спільним читанням (без запису й видалення/перейменування). Поки він
    відкритий, файл у %TEMP% (так завантажує OptimaX без прав адміністратора) ніхто не підмінить між повторною
    перевіркою суми й запуском; сам запуск (лише читання й виконання) він не блокує. Не вдалося — OSError."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    # GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING
    h = k32.CreateFileW(os.path.abspath(path), 0x80000000, 0x1, None, 3, 0, None)
    if not h or h == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return h


def _release(h) -> None:
    if h:
        import ctypes
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(h))


def launch(path: str, kind: str) -> bool:
    """Запускає інсталятор у тихому режимі (він сам закриє OptimaX і запустить нову версію).
    Перед запуском файл перевіряється ще раз: сума та підпис мають бути тими самими, що й після завантаження."""
    global LAST_ERROR
    LAST_ERROR = ""
    if not path or not E.IS_WIN or E.DRY_RUN:
        return False
    # 6.17: kind приходить разом із даними про версію; тихий запуск — лише для перевіреного файлу з ім'ям інсталятора
    kind = "setup" if kind == "setup" and SETUP_RE.fullmatch(os.path.basename(path)) else "portable"
    import verify as V
    # 7.1.1: без прав адміністратора файл лежить у %TEMP% (download_dir) — тримаємо його відкритим від повторної
    # перевірки до запуску, щоб його не підмінили в проміжку. Папка оновлень адміністратора й так захищена.
    held = None
    try:
        if path not in _VERIFIED:
            raise V.VerifyError("vf.no_hash", name=os.path.basename(path))
        if os.name == "nt" and not E.is_admin():
            held = _hold(path)
        V.check_file(path, _VERIFIED[path], name=os.path.basename(path))
        if kind == "setup":
            subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/UPDATE=1"],
                             creationflags=E.CREATE_NO_WINDOW)
        else:
            os.startfile(os.path.dirname(path))  # портативна версія — показуємо завантажений файл
    except (V.VerifyError, OSError) as e:
        LAST_ERROR = str(e)
        return False
    finally:
        _release(held)
    return True
