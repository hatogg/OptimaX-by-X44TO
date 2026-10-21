"""
OptimaX — допоміжний скрипт збірки релізу.

    python packaging/release.py version              — надрукувати версію з engine.py
    python packaging/release.py version-info         — оновити version_info.txt під цю версію
    python packaging/release.py winget <Setup.exe>   — маніфести winget для цього інсталятора
    python packaging/release.py buildinfo            — buildinfo.py: репозиторій оновлень (DEFAULT_REPO або OPTIMAX_UPDATE_REPO),
                                                       коміт і дата збірки (у CI беруться з GitHub Actions)
    python packaging/release.py checksums <файли…>   — SHA256SUMS.txt для релізу

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
    else:
        print(__doc__)
        sys.exit(1)
