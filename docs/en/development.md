# For developers

[← Back to the main page](../../README.en.md) · [Guide](guide.md) · [All optimizations](tweaks.md) · [FAQ](faq.md) · [For developers](development.md) · [Українська](../uk/development.md)

How to run OptimaX from source, build the installer, run the tests and publish a release. Before a pull request, read [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Running from source

```bash
pip install -r requirements.txt
python optimizer.py              # normal start
python optimizer.py --dry-run    # preview: shows every command, changes nothing
python optimizer.py --lang=en    # language: uk, ru or en
python optimizer.py --tray       # start minimized to the tray
python optimizer.py --selftest=report.json --selftest-ui   # self-test (changes nothing)
```

Service modes (called by the installer and Task Scheduler): `--maintenance`, `--set-autostart`, `--no-autostart`, `--uninstall [--revert-all]`, `--check-crash` (the “OptimaX Safety” task after changes).

The **self-test** `--selftest` runs with a temporary settings folder and in preview mode: modules, translations, every tweak (reading state only), hardware detection, Rescue file generation, smart optimization logic, the ad blocker, and with `--selftest-ui` the main window with all sections and the result card. Next to the JSON report there is a short `report.md` and screenshots of the sections. The built `OptimaX.exe` can be checked the same way.

## Building

| Script | What it does | Result |
| --- | --- | --- |
| `build_installer.bat` | Builds the program folder (PyInstaller, onedir) and the installer (Inno Setup) | `Output\OptimaX-Setup-<version>.exe` and winget manifests |
| `build.bat` | A single portable file (PyInstaller, onefile) | `Output\OptimaX-<version>-portable.exe` |

You need Python 3.10+, and for the installer [Inno Setup](https://jrsoftware.org/isdl.php) 6.3+ or 7 (`winget install JRSoftware.InnoSetup`). The version is set in one place, `VERSION` in `engine.py`; `version_info.txt`, the installer and the manifests pick it up themselves.

The `packaging/` folder: `OptimaX.iss` (installer script), `OptimaX-Rescue.cmd` (the emergency rollback launcher for the Start menu), installer wizard images, `release.py` (version, `version_info.txt`, `buildinfo.py`, winget manifests, SHA256SUMS). In CI neither build script waits for a key press (the `CI` variable).

The built program checks for updates in the releases of `hatogg/OptimaX-by-X44TO`. For a fork, set `set OPTIMAX_UPDATE_REPO=owner/repo` before building.

### Code signing

Without a digital signature Windows SmartScreen shows “Unknown publisher”, and some antiviruses are wary of PyInstaller programs. If you have a certificate (Azure Trusted Signing, OV or EV):

```bat
set OPTIMAX_PFX=C:\certs\x44to.pfx
set OPTIMAX_PFX_PASS=password
build_installer.bat
```

The script signs `OptimaX.exe`, the installer and the uninstaller (`signtool` from the Windows SDK).

### Publishing a release

**Your own build:** run `build_installer.bat` and `build.bat`, then `tools\publish_github.ps1 -Release`. The script creates the `v<version>` release with the files from `Output\` and their `SHA256SUMS.txt`; the CI release workflow sees that the release already exists and leaves your files as they are.

**Built by GitHub Actions:** the Actions tab → **Release** → **Run workflow** releases the version from `VERSION` in `engine.py`, and the workflow creates the `v<version>` tag itself. Or with a tag:

1. Bump `VERSION` in `engine.py`, run `python packaging/release.py version-info` and commit.
2. `git tag v6.3 && git push origin v6.3`, or in one step together with the code: `tools\publish_github.ps1 -Tag`.
3. The **Release** workflow checks that the tag matches the version, runs the whole CI (including the tweaks on real Windows), builds the installer and the portable version and publishes the release: `OptimaX-Setup-<version>.exe`, `OptimaX-<version>-portable.exe`, `OptimaX-Rescue.cmd`, `SHA256SUMS.txt`, winget manifests. Installed copies see the update within a day.

For signing in CI, add the repository secrets `OPTIMAX_PFX_BASE64` (the .pfx file in base64: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("x44to.pfx"))`) and `OPTIMAX_PFX_PASS`.

To make the program installable with `winget install X44TO.OptimaX`, submit the manifests from `Output\winget\<version>\` to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs); the easiest way is `wingetcreate submit`.

## Tests and CI

`.github/workflows/ci.yml` runs on every push and pull request:

| Job | Where | What it checks |
| --- | --- | --- |
| **linux** | Ubuntu 24.04 | Translations, every tweak on five demo configurations (apply → journal → roll back), the Rescue file and rollback order, smart optimization logic, the live DNS filter (sockets, cache, TCP, API, DoH), the GPU test scene on Mesa OpenGL, the main window on real PyQt6 (offscreen) with all scenarios, a fake Windows that checks the checker itself, documentation links |
| **windows-tests** | Windows Server 2022 and 2025 | The same tests, plus the self-test from source on real hardware and Qt, in preview mode only |
| **windows-tweaks** | Windows Server 2022 and 2025 | **The real system.** Every tweak: apply → the values really changed → roll back → *every* journal record restored the original state (registry, services, tasks, power) + side effects (power scheme, BCD, TCP, services). Then as a batch, like in the program: rollback through `OptimaX-Rescue.cmd /all` and separately through the journal |
| **windows-build** | Windows Server 2022 | The installer and the portable version, `--selftest-ui` of both exe files, silent install → files, shortcuts, the Apps entry → the Rescue launcher → silent uninstall → nothing left behind |

Each job's summary is on the run page; reports and window screenshots are in the artifacts.

Not checked in CI: network tweaks that reconnect adapters (the machine would lose its connection), removing OneDrive and CompactOS. Defender, Recall, reserved storage and hibernation may not apply on a virtual machine; the report shows them separately without failing the build.

Locally:

```bash
pip install -r requirements.txt pytest cryptography
python -m pytest tests -v          # or without pytest: python tests/run_tests.py
```

The tests run only in preview mode with a temporary settings folder and change nothing. The exception is `tests/windows/tweak_roundtrip.py`: it **changes the system** and refuses to run without the `CI` variable (for a disposable virtual machine there is the `--yes-change-this-pc` flag).

## Project structure

```
OptimaX/
├── optimizer.py        ← main window, sidebar, tray, background timers, hotkeys
├── pages_optimize.py   ← Analysis, wizard, expert menu, review of changes
├── pages_tools.py      ← Games, Hardware, Laptop, Cleanup, Startup apps, Appearance, Backups, Settings
├── pages_extra.py      ← Diagnostics, Network, Apps, disk analyzer, old drivers
├── pages_lab.py        ← Benchmarks, Ad blocker
├── ui_kit.py           ← theme, switches, cards, charts, dialogs, run console
├── engine.py           ← optimization catalogue, execution, rollback journal, hardware compatibility
├── hardware.py         ← hardware detection, analysis, build check, MSI Mode, battery, metrics
├── hwnative.py         ← hardware detection without PowerShell: SMBIOS, registry, SetupAPI, disk IOCTLs
├── features.py         ← game mode, games, startup, autostart, profiles, wizard
├── monitor.py          ← Windows counters, Why is it lagging?, background balancer, cores for games
├── fpstest.py          ← FPS test through PresentMon
├── netlab.py           ← DNS, ping to regions, bufferbloat
├── gpubench.py         ← GPU test: shader, OpenGL, test window, stress test, NVIDIA sensors
├── benchtools.py       ← FurMark 2, Superposition, Cinebench, OCCT, CrystalDiskMark, 3DMark
├── adblock.py          ← DNS filter: server, lists, cache, DoH, statistics, service, system DNS
├── guard.py            ← settings guard, trial mode, scheduled maintenance
├── rescue.py           ← emergency rollback: change batches, crash watch, OptimaX-Rescue.cmd
├── abtest.py           ← smart optimization logic: measurements, noise, halving
├── smart_ui.py         ← smart optimization window and card
├── sharecard.py        ← result card for social networks
├── selftest.py         ← build self-test (--selftest)
├── apps.py             ← winget, old drivers, disk analyzer
├── power.py            ← refresh rate by power source, charge limit
├── report.py           ← forum report
├── lifecycle.py        ← single instance, installer modes, uninstall
├── updater.py          ← updates through GitHub Releases
├── hotkeys.py          ← global hotkeys
├── i18n.py             ← language selection
├── lang_*.py           ← translations (uk, ru, en)
├── icon.ico, icon.png  ← program icon
├── bench.png           ← GPU test scene preview
├── packaging/          ← Inno Setup installer, OptimaX-Rescue.cmd, wizard images, release.py
├── tests/              ← tests (pytest); tests/windows/ is the real-Windows check for CI
├── .github/            ← ci.yml, release.yml, pages.yml, issue and PR templates
├── docs/               ← guide, FAQ, optimization list (uk, en), images
├── site/               ← the program's page for GitHub Pages
├── tools/              ← gen_docs.py (optimization list from code), publish_github.ps1
├── build_installer.bat ← installer
├── build.bat           ← portable version
├── version_info.txt, requirements.txt
```

To add your own optimization, one `tw(...)` line in `engine.py` and a line with its title and description in `lang_tweaks.py` are enough: the interface, profiles, search, review, guard and rollback pick it up on their own.

## Optimization list in the docs

`docs/uk/tweaks.md` and `docs/en/tweaks.md` are generated from the code: `python tools/gen_docs.py`. CI checks that they are current, so after changing a tweak run the script and commit both files.
