"""
OptimaX — допоміжний скрипт збірки релізу.

    python packaging/release.py version              — надрукувати версію з engine.py
    python packaging/release.py version-info         — оновити version_info.txt під цю версію
    python packaging/release.py winget <Setup.exe>   — маніфести winget для цього інсталятора
    python packaging/release.py buildinfo            — buildinfo.py: репозиторій оновлень (DEFAULT_REPO або OPTIMAX_UPDATE_REPO),
                                                       коміт і дата збірки (у CI беруться з GitHub Actions)
    python packaging/release.py checksums <файли…>   — SHA256SUMS.txt для релізу
    python packaging/release.py mesa <папка>         — OptimaX-Mesa-<версія>-x64.zip для майнінгових карт (mining.py):
                                                       x64-бібліотеки з релізу pal1000/mesa-dist-win + mesa.json

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
    digest = str(asset.get("digest") or "")
    if digest.lower().startswith("sha256:") and digest[7:].lower() != h.hexdigest():
        raise SystemExit(f"{asset['name']}: SHA-256 differs from the GitHub digest")
    x64 = os.path.join(work, "x64")
    subprocess.run([_seven_zip(), "e", arc, f"-o{x64}", "-y"] + [f"x64/{n}" for n in MESA_FILES],
                   check=False, stdout=subprocess.DEVNULL)
    files = {}
    for n in MESA_FILES:
        p = os.path.join(x64, n)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                files[n] = hashlib.sha256(f.read()).hexdigest()
    missing = [n for n in MESA_REQUIRED if n not in files]
    if missing:
        raise SystemExit(f"{asset['name']}: x64/{', '.join(missing)} not found")
    if "dxil.dll" not in files:
        print("::warning::Mesa: x64/dxil.dll is missing — the d3d12 driver may not start without it", file=sys.stderr)
    man = {"mesa": ver, "source": f"https://github.com/{MESA_REPO}/releases/tag/{rel.get('tag_name')}",
           "archive": asset["name"], "archive_sha256": h.hexdigest(), "files": files}
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"OptimaX-Mesa-{ver}-x64.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mesa.json", json.dumps(man, indent=1))
        z.writestr("README.txt", f"Mesa {ver} (https://mesa3d.org, MIT license: https://docs.mesa3d.org/license.html)\n"
                                 f"built by {man['source']}\n"
                                 "OptimaX uses it on PCs with a mining graphics card (no video outputs) so that OpenGL "
                                 "games and the OptimaX GPU test render on that card via the d3d12 driver.\n")
        for n in files:
            z.write(os.path.join(x64, n), n)
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
    else:
        print(__doc__)
        sys.exit(1)
