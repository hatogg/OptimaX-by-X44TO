"""
OptimaX — допоміжний скрипт збірки релізу.

    python packaging/release.py version              — надрукувати версію з engine.py
    python packaging/release.py version-info         — оновити version_info.txt під цю версію
    python packaging/release.py winget <Setup.exe>   — маніфести winget для цього інсталятора
    python packaging/release.py buildinfo            — buildinfo.py: репозиторій оновлень (DEFAULT_REPO або OPTIMAX_UPDATE_REPO),
                                                       коміт і дата збірки (у CI беруться з GitHub Actions)
    python packaging/release.py checksums <файли…>   — SHA256SUMS.txt для релізу
    python packaging/release.py mesa <папка>         — OptimaX-Mesa-<версія>.zip для майнінгових карт (mining.py):
                                                       x64- і x86-бібліотеки з релізу pal1000/mesa-dist-win + mesa.json
    python packaging/release.py dxvk <папка>         — OptimaX-DXVK-<версія>.zip: бібліотеки DirectX (x64, x86) з релізу
                                                       doitsujin/dxvk + dxvk.json
    python packaging/release.py winget-app <папка>   — OptimaX-WinGet-<версія>.zip: «Інсталятор програм» (winget) і його
                                                       залежності з релізу microsoft/winget-cli + winget.json

Версія береться лише з engine.py (VERSION = "..."), тож змінювати її треба в одному місці.
"""
import hashlib
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Репозиторій із релізами за замовчуванням (звідти програма бере оновлення). Для форку: OPTIMAX_UPDATE_REPO=власник/репо
DEFAULT_REPO = "hatogg/OptimaX-by-X44TO"


def update_repo() -> str:
    return os.environ.get("OPTIMAX_UPDATE_REPO", "").strip() or DEFAULT_REPO


def version() -> str:
    with open(os.path.join(ROOT, "engine.py"), encoding="utf-8") as f:
        return re.search(r'^VERSION = "([^"]+)"', f.read(), re.M).group(1)


def quad(v: str) -> tuple:
    nums = [int(x) for x in re.findall(r"\d+", v)][:4]
    return tuple(nums + [0] * (4 - len(nums)))


def write_version_info() -> None:
    v = version()
    q = quad(v)
    s = ".".join(map(str, q))
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={q},
    prodvers={q},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('042204B0', [
        StringStruct('CompanyName', 'X44TO'),
        StringStruct('FileDescription', 'OptimaX by X44TO - Windows 10/11 optimizer'),
        StringStruct('FileVersion', '{s}'),
        StringStruct('InternalName', 'OptimaX'),
        StringStruct('LegalCopyright', 'MIT License, X44TO'),
        StringStruct('OriginalFilename', 'OptimaX.exe'),
        StringStruct('ProductName', 'OptimaX'),
        StringStruct('ProductVersion', '{s}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1058, 1200])])
  ]
)
"""
    with open(os.path.join(ROOT, "version_info.txt"), "w", encoding="utf-8") as f:
        f.write(text)


MANIFEST_VERSION = "1.9.0"
PKG = "X44TO.OptimaX"


def write_winget(setup_path: str) -> str:
    v = version()
    with open(setup_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest().upper()
    repo = update_repo()
    url = f"https://github.com/{repo}/releases/download/v{v}/{os.path.basename(setup_path)}"
    out = os.path.join(ROOT, "Output", "winget", v)
    os.makedirs(out, exist_ok=True)
    head = f"# yaml-language-server: $schema=https://aka.ms/winget-manifest.{{kind}}.{MANIFEST_VERSION}.schema.json\n"
    files = {
        f"{PKG}.yaml": ("version", f"""PackageIdentifier: {PKG}
PackageVersion: {v}
DefaultLocale: en-US
ManifestType: version
ManifestVersion: {MANIFEST_VERSION}
"""),
        f"{PKG}.installer.yaml": ("installer", f"""PackageIdentifier: {PKG}
PackageVersion: {v}
InstallerType: inno
Scope: machine
ElevationRequirement: elevatesSelf
UpgradeBehavior: install
MinimumOSVersion: 10.0.17763.0
Installers:
- Architecture: x64
  InstallerUrl: {url}
  InstallerSha256: {sha}
ManifestType: installer
ManifestVersion: {MANIFEST_VERSION}
"""),
        f"{PKG}.locale.en-US.yaml": ("defaultLocale", f"""PackageIdentifier: {PKG}
PackageVersion: {v}
PackageLocale: en-US
Publisher: X44TO
PublisherUrl: https://github.com/{repo.split("/")[0]}
PublisherSupportUrl: https://github.com/{repo}/issues
PackageName: OptimaX
PackageUrl: https://github.com/{repo}
License: MIT
LicenseUrl: https://github.com/{repo}/blob/main/LICENSE
ReleaseNotesUrl: https://github.com/{repo}/releases/tag/v{v}
ShortDescription: Windows 10/11 optimizer for gaming PCs, laptops, custom builds and old computers.
Description: Hardware-aware tweaks with a preview and full rollback, lag diagnostics, before/after FPS tests, a settings guard for Windows updates, DNS and ping tools.
Tags:
- optimizer
- gaming
- fps
- windows-11
- privacy
ManifestType: defaultLocale
ManifestVersion: {MANIFEST_VERSION}
"""),
        f"{PKG}.locale.uk-UA.yaml": ("locale", f"""PackageIdentifier: {PKG}
PackageVersion: {v}
PackageLocale: uk-UA
Publisher: X44TO
PackageName: OptimaX
License: MIT
ShortDescription: Оптимізація Windows 10/11 для ігрових ПК, ноутбуків, нестандартних збірок і старих комп'ютерів.
ManifestType: locale
ManifestVersion: {MANIFEST_VERSION}
"""),
    }
    for name, (kind, body) in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(head.replace("{kind}", kind) + body)
    return out


def write_buildinfo() -> str:
    """Те, що треба знати зібраній програмі: звідки брати оновлення і з якого коміту її зібрано."""
    repo = update_repo()
    if repo and not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise SystemExit(f"OPTIMAX_UPDATE_REPO must look like owner/repo, got {repo!r}")
    sha = (os.environ.get("GITHUB_SHA") or "")[:12]
    text = (f'"""Створено packaging/release.py buildinfo під час збірки — не редагуйте вручну."""\n'
            f"UPDATE_REPO = {repo!r}\n"
            f"BUILD = {sha!r}\n"
            f"BUILT = {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())!r}\n"
            f"VERSION = {version()!r}\n")
    path = os.path.join(ROOT, "buildinfo.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


MESA_REPO = "pal1000/mesa-dist-win"
MESA_ASSET = re.compile(r"^mesa3d-([\d.]+)-release-msvc\.7z$", re.I)
MESA_FILES = ("opengl32.dll", "libgallium_wgl.dll", "libglapi.dll", "dxil.dll")  # як у mining.MESA_FILES
MESA_REQUIRED = ("opengl32.dll", "libgallium_wgl.dll")
MESA_ARCHES = ("x64", "x86")  # бібліотеки тієї ж розрядності, що й exe гри


def _get(url: str, api: bool = False):
    import urllib.request
    headers = {"User-Agent": "OptimaX-build"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if token:  # без токена API GitHub на спільних раннерах швидко впирається в ліміт запитів
            headers["Authorization"] = f"Bearer {token}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)


def _seven_zip() -> str:
    import shutil
    for p in (shutil.which("7z"), shutil.which("7za"), r"C:\Program Files\7-Zip\7z.exe"):
        if p and os.path.exists(p):
            return p
    raise SystemExit("7-Zip not found (7z / 7za)")


DXVK_REPO = "doitsujin/dxvk"
DXVK_ASSET = re.compile(r"^dxvk-([\d.]+)\.tar\.gz$", re.I)
DXVK_FILES = ("d3d9.dll", "d3d8.dll", "dxgi.dll", "d3d11.dll", "d3d10core.dll")  # як у mining.DXVK_FILES
DXVK_DIRS = {"x64": "x64", "x86": "x32"}  # розрядність у OptimaX -> папка в архіві DXVK


# 7.1.1: SHA-256 архівів закріплених версій (ci.yml: OPTIMAX_MESA_TAG / OPTIMAX_DXVK_TAG). Тег на GitHub можна
# перевипустити з іншим файлом — тоді збірка падає, а не кладе в реліз чужі DLL. Нова версія → нова сума тут.
PINNED_SHA256 = {
    (MESA_REPO, "mesa3d-26.2.0-release-msvc.7z"): "dcb2719ef346dab5b609fcb193a5f13cfc4b0502e3f4de1ad43d349477402f47",
    (DXVK_REPO, "dxvk-2.6.2.tar.gz"): "17761876556afd55736cb895d184f5a1c55d43350f1b1e3b129f8d28706d7992",
}


def _check_digest(repo: str, name: str, digest, sha: str) -> None:
    """Звіряє завантажений архів із digest GitHub (обов'язковий) і з закріпленою сумою, якщо вона є."""
    digest = str(digest or "")
    # 7.1.1: без digest перевірки немає зовсім — раніше її мовчки пропускали; тепер це помилка збірки
    if not digest.lower().startswith("sha256:"):
        raise SystemExit(f"{name}: GitHub gives no sha256 digest for this asset — refusing to use it")
    if digest[7:].lower() != sha:
        raise SystemExit(f"{name}: SHA-256 differs from the GitHub digest")
    want = PINNED_SHA256.get((repo, name))
    if want and want != sha:
        raise SystemExit(f"{name}: SHA-256 {sha} differs from the pinned {want}")


def _release_asset(repo: str, tag: str, rx, work: str) -> tuple:
    """Реліз repo (тег або останній), ресурс за rx, завантажений у work і звірений з digest GitHub.
    -> (шлях, версія, тег, sha256)."""
    import json
    with _get(f"https://api.github.com/repos/{repo}/releases/" + (f"tags/{tag}" if tag else "latest"), True) as r:
        rel = json.load(r)
    asset = next((a for a in rel.get("assets") or [] if rx.match(a.get("name") or "")), None)
    if not asset:
        raise SystemExit(f"{repo} {rel.get('tag_name')}: no asset matching {rx.pattern}")
    path = os.path.join(work, asset["name"])
    h = hashlib.sha256()
    with _get(asset["browser_download_url"]) as r, open(path, "wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            h.update(chunk)
            f.write(chunk)
    _check_digest(repo, asset["name"], asset.get("digest"), h.hexdigest())
    return path, rx.match(asset["name"]).group(1), rel.get("tag_name"), h.hexdigest()


def build_dxvk(out_dir: str) -> str:
    """Перепаковує DXVK (DirectX 8 / 9 / 10 / 11 → Vulkan) для ігор на майнінгових картах: лише бібліотеки DirectX
    (без setup-скриптів); у папку гри OptimaX кладе тільки ті, що потрібні її API.
    OPTIMAX_DXVK_TAG=<тег> — конкретний реліз (за замовчуванням останній)."""
    import json
    import tarfile
    import tempfile
    import zipfile
    work = tempfile.mkdtemp(prefix="dxvk_")
    arc, ver, tag, sha = _release_asset(DXVK_REPO, os.environ.get("OPTIMAX_DXVK_TAG", "").strip(), DXVK_ASSET, work)
    blobs = {}
    with tarfile.open(arc, "r:gz") as t:
        for m in t.getmembers():
            parts = m.name.replace("\\", "/").split("/")
            if not m.isfile() or len(parts) < 2 or parts[-1].lower() not in DXVK_FILES:
                continue
            arch = next((a for a, d in DXVK_DIRS.items() if parts[-2].lower() == d), None)
            if arch:
                blobs[f"{arch}/{parts[-1].lower()}"] = t.extractfile(m).read()
    missing = [f"{a}/{n}" for a in DXVK_DIRS for n in DXVK_FILES if f"{a}/{n}" not in blobs and n != "d3d8.dll"]
    if missing:  # d3d8.dll є лише з DXVK 2.4; решта — обов'язкові
        raise SystemExit(f"{os.path.basename(arc)}: not found {', '.join(missing)}")
    man = {"dxvk": ver, "source": f"https://github.com/{DXVK_REPO}/releases/tag/{tag}",
           "archive": os.path.basename(arc), "archive_sha256": sha,
           "files": {k: hashlib.sha256(b).hexdigest() for k, b in sorted(blobs.items())}}
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"OptimaX-DXVK-{ver}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dxvk.json", json.dumps(man, indent=1))
        z.writestr("README.txt", f"DXVK {ver} (https://github.com/{DXVK_REPO}, zlib license)\n"
                                 f"from {man['source']}\n"
                                 "OptimaX uses it on PCs with a mining graphics card (no video outputs): DirectX 9 sees "
                                 "only the card with the monitor, DXVK translates it to Vulkan, which sees the mining "
                                 "card. DirectX 10 / 11 libraries are used only in the DXVK mode chosen per game.\n")
        for k, b in sorted(blobs.items()):
            z.writestr(k, b)
    return out


def build_mesa(out_dir: str) -> str:
    """Перепаковує Mesa для майнінгових карт: драйвер d3d12 (OpenGL поверх DirectX 12) з релізу mesa-dist-win.
    OPTIMAX_MESA_TAG=<тег> — конкретний реліз (за замовчуванням останній). Сума архіву звіряється з digest GitHub."""
    import json
    import subprocess
    import tempfile
    import zipfile
    tag = os.environ.get("OPTIMAX_MESA_TAG", "").strip()
    with _get(f"https://api.github.com/repos/{MESA_REPO}/releases/" + (f"tags/{tag}" if tag else "latest"), True) as r:
        rel = json.load(r)
    asset = next((a for a in rel.get("assets") or [] if MESA_ASSET.match(a.get("name") or "")), None)
    if not asset:
        raise SystemExit(f"{MESA_REPO} {rel.get('tag_name')}: no *-release-msvc.7z asset")
    ver = MESA_ASSET.match(asset["name"]).group(1)
    work = tempfile.mkdtemp(prefix="mesa_")
    arc = os.path.join(work, asset["name"])
    h = hashlib.sha256()
    with _get(asset["browser_download_url"]) as r, open(arc, "wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            h.update(chunk)
            f.write(chunk)
    _check_digest(MESA_REPO, asset["name"], asset.get("digest"), h.hexdigest())
    out_dir_x = os.path.join(work, "out")
    subprocess.run([_seven_zip(), "x", arc, f"-o{out_dir_x}", "-y"] + [f"{a}/{n}" for a in MESA_ARCHES for n in MESA_FILES],
                   check=False, stdout=subprocess.DEVNULL)
    files = {}
    for a in MESA_ARCHES:
        for n in MESA_FILES:
            p = os.path.join(out_dir_x, a, n)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    files[f"{a}/{n}"] = hashlib.sha256(f.read()).hexdigest()
    missing = [f"x64/{n}" for n in MESA_REQUIRED if f"x64/{n}" not in files]
    if missing:
        raise SystemExit(f"{asset['name']}: {', '.join(missing)} not found")
    for a in MESA_ARCHES:
        if f"{a}/dxil.dll" not in files:
            print(f"::warning::Mesa: {a}/dxil.dll is missing — the d3d12 driver may not start without it",
                  file=sys.stderr)
        if any(f"{a}/{n}" not in files for n in MESA_REQUIRED):
            print(f"::warning::Mesa: no {a} build — OpenGL games of that bitness get no Mesa", file=sys.stderr)
    man = {"mesa": ver, "source": f"https://github.com/{MESA_REPO}/releases/tag/{rel.get('tag_name')}",
           "archive": asset["name"], "archive_sha256": h.hexdigest(), "files": files}
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"OptimaX-Mesa-{ver}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mesa.json", json.dumps(man, indent=1))
        z.writestr("README.txt", f"Mesa {ver} (https://mesa3d.org, MIT license: https://docs.mesa3d.org/license.html)\n"
                                 f"built by {man['source']}\n"
                                 "OptimaX uses it on PCs with a mining graphics card (no video outputs) so that OpenGL "
                                 "games and the OptimaX GPU test render on that card via the d3d12 driver.\n")
        for key in files:
            z.write(os.path.join(out_dir_x, *key.split("/")), key)
    return out


# 7.2: «Інсталятор програм» (winget) для систем, де пакета немає зовсім (LTSC, Server, видалений). OptimaX бере його
# лише з власного релізу (wingetfix.py), тож сюди кладемо офіційні файли релізу microsoft/winget-cli, звірені з digest
# GitHub, з закріпленою сумою (release.yml: OPTIMAX_WINGET_TAG) і з сумою з Microsoft.DesktopAppInstaller_*.txt.
WINGET_REPO = "microsoft/winget-cli"
WINGET_BUNDLE = "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle"  # як у wingetfix.BUNDLE
WINGET_BUNDLE_SUM = "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.txt"
WINGET_DEPS_ZIP = "DesktopAppInstaller_Dependencies.zip"
WINGET_DEPS_JSON = "DesktopAppInstaller_Dependencies.json"
WINGET_ARCHES = ("x64", "x86", "arm64")  # як у wingetfix.ARCHES
WINGET_DEP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(appx|msix)$", re.I)  # як у wingetfix.DEP_RE
PINNED_SHA256.update({
    (WINGET_REPO, "v1.29.380/" + WINGET_BUNDLE): "65dea9c01ce08ee7b763366b27c0e651f97db857c11ca9b9c301826c10092f2e",
    (WINGET_REPO, "v1.29.380/" + WINGET_DEPS_ZIP): "ba875afe9d190f61218985ac0292a99d1db710bf93e13c68944ca9d89f0d82d1",
})


def _download_asset(repo: str, tag: str, rel: dict, name: str, work: str) -> tuple:
    """Ресурс name з уже отриманого релізу rel, звірений з digest GitHub і закріпленою сумою. -> (шлях, sha256)."""
    asset = next((a for a in rel.get("assets") or [] if a.get("name") == name), None)
    if not asset:
        raise SystemExit(f"{repo} {rel.get('tag_name')}: no asset {name}")
    path = os.path.join(work, name)
    h = hashlib.sha256()
    with _get(asset["browser_download_url"]) as r, open(path, "wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            h.update(chunk)
            f.write(chunk)
    # закріплена сума — за тегом і ім'ям (імена файлів winget-cli однакові в усіх релізах)
    _check_digest(repo, f"{tag}/{name}", asset.get("digest"), h.hexdigest())
    return path, h.hexdigest()


def winget_dependencies(text: str) -> list:
    """Імена пакетів-залежностей з DesktopAppInstaller_Dependencies.json (VCLibs, UI.Xaml, WindowsAppRuntime…)."""
    import json
    names = []

    def walk(x):
        if isinstance(x, dict):
            n = x.get("Name") or x.get("name")
            if isinstance(n, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}", n):
                names.append(n)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(json.loads(text))
    return sorted(set(names))


def winget_dep_files(names) -> dict:
    """Імена файлів з DesktopAppInstaller_Dependencies.zip -> {"<arch>/<файл>": ім'я в архіві}: лише .appx / .msix
    з папки x64 / x86 / arm64 (будь-якої глибини), без «..» і чужих розширень."""
    out = {}
    for n in names:
        parts = n.replace("\\", "/").split("/")
        if len(parts) < 2 or ".." in parts or not WINGET_DEP_RE.match(parts[-1]):
            continue
        arch = parts[-2].lower()
        if arch in WINGET_ARCHES:
            out[f"{arch}/{parts[-1]}"] = n
    return out


def build_winget(out_dir: str) -> str:
    """OptimaX-WinGet-<версія>.zip: msixbundle «Інсталятора програм» і залежності для x64 / x86 / arm64 з релізу
    microsoft/winget-cli + winget.json із сумою кожного файлу. OPTIMAX_WINGET_TAG=<тег> — конкретний реліз."""
    import json
    import tempfile
    import zipfile
    tag = os.environ.get("OPTIMAX_WINGET_TAG", "").strip()
    with _get(f"https://api.github.com/repos/{WINGET_REPO}/releases/" + (f"tags/{tag}" if tag else "latest"),
              True) as r:
        rel = json.load(r)
    tag = rel.get("tag_name") or tag
    m = re.fullmatch(r"v?(\d+(?:\.\d+){1,3})", tag or "")
    if not m:
        raise SystemExit(f"{WINGET_REPO}: unexpected tag {tag!r}")
    ver = m.group(1)
    work = tempfile.mkdtemp(prefix="winget_")
    bundle, bundle_sha = _download_asset(WINGET_REPO, tag, rel, WINGET_BUNDLE, work)
    deps_zip, deps_sha = _download_asset(WINGET_REPO, tag, rel, WINGET_DEPS_ZIP, work)
    deps_json, _ = _download_asset(WINGET_REPO, tag, rel, WINGET_DEPS_JSON, work)
    txt, _ = _download_asset(WINGET_REPO, tag, rel, WINGET_BUNDLE_SUM, work)
    with open(txt, encoding="utf-8-sig") as f:  # третє джерело суми: файл, який Microsoft кладе поруч із bundle
        listed = re.findall(r"\b[0-9a-fA-F]{64}\b", f.read())
    if bundle_sha not in {s.lower() for s in listed}:
        raise SystemExit(f"{WINGET_BUNDLE}: SHA-256 differs from {WINGET_BUNDLE_SUM}")
    with open(deps_json, encoding="utf-8-sig") as f:
        need = winget_dependencies(f.read())
    if not need:
        raise SystemExit(f"{WINGET_DEPS_JSON}: no dependencies listed")
    files = {WINGET_BUNDLE: bundle_sha}
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"OptimaX-WinGet-{ver}.zip")
    with zipfile.ZipFile(deps_zip) as dz:
        picked = winget_dep_files(dz.namelist())
        for arch in WINGET_ARCHES:
            have = [k.split("/", 1)[1].lower() for k in picked if k.startswith(arch + "/")]
            missing = [n for n in need if not any(h.startswith(n.lower() + "_") for h in have)]
            if missing and arch == "x64":
                raise SystemExit(f"{WINGET_DEPS_ZIP}: x64 lacks {', '.join(missing)}")
            if missing:
                print(f"::warning::WinGet: {arch} lacks {', '.join(missing)} — that arch gets no offline install",
                      file=sys.stderr)
                picked = {k: v for k, v in picked.items() if not k.startswith(arch + "/")}
        # msix — уже стиснуті архіви: ZIP_STORED, щоб не витрачати час на повторне стискання
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
            z.write(bundle, WINGET_BUNDLE)
            for key, src in sorted(picked.items()):
                data = dz.read(src)
                files[key] = hashlib.sha256(data).hexdigest()
                z.writestr(key, data)
            man = {"winget": ver, "source": f"https://github.com/{WINGET_REPO}/releases/tag/{tag}",
                   "bundle": WINGET_BUNDLE, "dependencies": need, "archives": {WINGET_DEPS_ZIP: deps_sha},
                   "files": files}
            z.writestr("winget.json", json.dumps(man, indent=1))
            z.writestr("README.txt", f"Windows Package Manager (winget) {ver}, App Installer and its dependencies\n"
                                     f"from {man['source']} (MIT license, Microsoft-signed packages)\n"
                                     "OptimaX installs them only when App Installer is missing from Windows "
                                     "(LTSC, Server, removed) and the user asks to restore winget.\n")
    return out


def write_checksums(paths) -> str:
    out = os.path.join(ROOT, "Output", "SHA256SUMS.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    lines = []
    for p in paths:
        with open(p, "rb") as f:
            lines.append(f"{hashlib.sha256(f.read()).hexdigest()}  {os.path.basename(p)}")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "version"
    if cmd == "version":
        print(version())
    elif cmd == "version-info":
        write_version_info()
        print("version_info.txt ->", version())
    elif cmd == "winget" and len(sys.argv) > 2:
        print(write_winget(sys.argv[2]))
    elif cmd == "buildinfo":
        print(write_buildinfo())
    elif cmd == "checksums" and len(sys.argv) > 2:
        print(write_checksums(sys.argv[2:]))
    elif cmd == "mesa" and len(sys.argv) > 2:
        print(build_mesa(sys.argv[2]))
    elif cmd == "dxvk" and len(sys.argv) > 2:
        print(build_dxvk(sys.argv[2]))
    elif cmd == "winget-app" and len(sys.argv) > 2:
        print(build_winget(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(1)
