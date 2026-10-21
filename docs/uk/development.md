# Для розробників

[← На головну](../../README.md) · [Посібник](guide.md) · [Усі оптимізації](tweaks.md) · [Часті питання](faq.md) · [Для розробників](development.md) · [English](../en/development.md)

Як запустити OptimaX із коду, зібрати інсталятор, прогнати тести й випустити реліз. Перед pull request прочитайте [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Запуск із коду

```bash
pip install -r requirements.txt
python optimizer.py              # звичайний запуск
python optimizer.py --dry-run    # перегляд: показує всі команди, нічого не змінює
python optimizer.py --lang=en    # мова: uk, ru або en
python optimizer.py --tray       # старт згорнутим у трей
python optimizer.py --selftest=report.json --selftest-ui   # самоперевірка (нічого не змінює)
```

Службові режими (їх викликають інсталятор і планувальник): `--maintenance`, `--set-autostart`, `--no-autostart`, `--uninstall [--revert-all]`, `--check-crash` (задача «OptimaX Safety» після змін).

**Самоперевірка** `--selftest` працює з тимчасовою папкою налаштувань і в режимі перегляду: модулі, переклади, усі твіки (лише читання стану), визначення заліза, генерація Rescue-файлу, логіка розумної оптимізації, фільтр реклами, а з `--selftest-ui` — головне вікно з усіма розділами й карткою результату. Поруч зі звітом JSON — короткий `report.md` і знімки розділів. Так само можна перевірити зібраний `OptimaX.exe`.

## Збірка

| Скрипт | Що робить | Результат |
| --- | --- | --- |
| `build_installer.bat` | Збирає папку програми (PyInstaller, onedir) та інсталятор (Inno Setup) | `Output\OptimaX-Setup-<версія>.exe` і маніфести winget |
| `build.bat` | Портативний один файл (PyInstaller, onefile) | `Output\OptimaX-<версія>-portable.exe` |

Потрібні Python 3.10+, а для інсталятора — [Inno Setup](https://jrsoftware.org/isdl.php) 6.3+ або 7 (`winget install JRSoftware.InnoSetup`). Версія задається в одному місці — `VERSION` в `engine.py`; `version_info.txt`, інсталятор і маніфести підхоплюють її самі.

Папка `packaging/`: `OptimaX.iss` (скрипт інсталятора), `OptimaX-Rescue.cmd` (запускач аварійного відкату для меню «Пуск»), картинки майстра встановлення, `release.py` (версія, `version_info.txt`, `buildinfo.py`, маніфести winget, SHA256SUMS). Обидва скрипти збірки в CI не чекають натискання клавіші (змінна `CI`).

Зібрана програма шукає оновлення в релізах `hatogg/OptimaX-by-X44TO`. Для форку перед збіркою задайте `set OPTIMAX_UPDATE_REPO=власник/репозиторій`.

### Підпис коду

Без цифрового підпису Windows SmartScreen показує «Невідомий видавець», а частина антивірусів насторожено ставиться до програм на PyInstaller. Якщо є сертифікат (Azure Trusted Signing, OV чи EV):

```bat
set OPTIMAX_PFX=C:\certs\x44to.pfx
set OPTIMAX_PFX_PASS=пароль
build_installer.bat
```

Скрипт підпише `OptimaX.exe`, інсталятор і деінсталятор (`signtool` із Windows SDK).

### Публікація релізу

**Своя збірка:** запустіть `build_installer.bat` і `build.bat`, потім `tools\publish_github.ps1 -Release`. Скрипт створить реліз `v<версія>` з файлами з `Output\` і їхніми `SHA256SUMS.txt`; workflow релізу в CI побачить, що реліз уже є, і ваші файли не чіпатиме.

**Збірка в GitHub Actions:** вкладка Actions → **Release** → **Run workflow** — реліз версії з `VERSION` в `engine.py`, тег `v<версія>` workflow створить сам. Або тегом:

1. Підніміть `VERSION` в `engine.py`, виконайте `python packaging/release.py version-info` і закомітьте.
2. `git tag v6.3 && git push origin v6.3` — або одним кроком разом із кодом: `tools\publish_github.ps1 -Tag`.
3. Workflow **Release** перевірить, що тег збігається з версією, прожене весь CI (зокрема твіки на справжній Windows), збере інсталятор і портативну версію з репозиторієм оновлень = цей репозиторій і опублікує реліз: `OptimaX-Setup-<версія>.exe`, `OptimaX-<версія>-portable.exe`, `OptimaX-Rescue.cmd`, `SHA256SUMS.txt`, маніфести winget. Встановлені копії побачать оновлення протягом доби.

Для підпису в CI додайте секрети репозиторію `OPTIMAX_PFX_BASE64` (файл .pfx у base64: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("x44to.pfx"))`) і `OPTIMAX_PFX_PASS`.

Щоб програму можна було ставити командою `winget install X44TO.OptimaX`, надішліть маніфести з `Output\winget\<версія>\` у [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) — найпростіше через `wingetcreate submit`.

## Тести й CI

`.github/workflows/ci.yml` запускається на кожен push і pull request:

| Завдання | Де | Що перевіряє |
| --- | --- | --- |
| **linux** | Ubuntu 24.04 | Переклади, усі твіки на п'яти демо-конфігураціях (застосувати → журнал → відкотити), Rescue-файл і порядок відкату, логіка розумної оптимізації, DNS-фільтр наживо (сокети, кеш, TCP, API, DoH), сцена GPU-тесту на Mesa OpenGL, головне вікно на справжньому PyQt6 (offscreen) з усіма сценаріями, фальшива Windows для перевірки самої перевірки, посилання в документації |
| **windows-tests** | Windows Server 2022 і 2025 | Ті самі тести, а також самоперевірка з вихідних файлів на справжньому залізі й Qt — лише в режимі перегляду |
| **windows-tweaks** | Windows Server 2022 і 2025 | **Справжня система.** Кожен твік: застосувати → значення справді змінились → відкотити → *кожен* запис журналу повернув початковий стан (реєстр, служби, задачі, живлення) + побічні зміни (схема живлення, BCD, TCP, служби). Потім пакетом, як у програмі: відкат через `OptimaX-Rescue.cmd /all` і окремо через журнал |
| **windows-build** | Windows Server 2022 | Інсталятор і портативна версія, `--selftest-ui` обох exe, тихе встановлення → файли, ярлики, запис у «Програмах» → запускач Rescue → тихе видалення → нічого не лишилось |

Підсумки кожного завдання видно на сторінці запуску, звіти й знімки вікна — в артефактах.

Не перевіряються на CI мережеві твіки, що перепідключають адаптери (машина втратила б зв'язок), видалення OneDrive і CompactOS; Defender, Recall, зарезервоване місце й гібернація можуть не застосуватися на віртуальній машині — звіт показує їх окремо, не валячи збірку.

Локально:

```bash
pip install -r requirements.txt pytest cryptography
python -m pytest tests -v          # або без pytest: python tests/run_tests.py
```

Тести працюють лише в режимі перегляду з тимчасовою папкою налаштувань і нічого не змінюють. Виняток — `tests/windows/tweak_roundtrip.py`: він **змінює систему** і без змінної `CI` відмовиться запускатися (для одноразової віртуальної машини є прапорець `--yes-change-this-pc`).

## Структура проєкту

```
OptimaX/
├── optimizer.py        ← головне вікно, бічне меню, трей, фонові таймери, гарячі клавіші
├── pages_optimize.py   ← «Аналіз», майстер, експертне меню, перегляд змін
├── pages_tools.py      ← Ігри, Залізо, Ноутбук, Очищення, Автозавантаження, Вигляд, Резервні копії, Налаштування
├── pages_extra.py      ← Діагностика, Мережа, Програми, аналізатор місця, старі драйвери
├── pages_lab.py        ← Бенчмарки, Блок реклами
├── ui_kit.py           ← тема, перемикачі, картки, графіки, діалоги, консоль виконання
├── engine.py           ← каталог оптимізацій, виконання, журнал відкату, сумісність із залізом
├── hardware.py         ← визначення заліза, аналіз, перевірка збірки, MSI Mode, батарея, заміри
├── features.py         ← режим гри, ігри, автозавантаження, автозапуск, профілі, майстер
├── monitor.py          ← лічильники Windows, «Чому лагає?», балансувальник фону, ядра для ігор
├── fpstest.py          ← тест FPS через PresentMon
├── netlab.py           ← DNS, пінг до регіонів, bufferbloat
├── gpubench.py         ← GPU-тест: шейдер, OpenGL, вікно тесту, стрес-тест, датчики NVIDIA
├── benchtools.py       ← FurMark 2, Superposition, Cinebench, OCCT, CrystalDiskMark, 3DMark
├── adblock.py          ← DNS-фільтр: сервер, списки, кеш, DoH, статистика, служба, системні DNS
├── guard.py            ← сторож налаштувань, пробний режим, обслуговування за розкладом
├── rescue.py           ← аварійний відкат: пакети змін, стеження за збоями, OptimaX-Rescue.cmd
├── abtest.py           ← логіка розумної оптимізації: заміри, шум, половинний поділ
├── smart_ui.py         ← вікно й картка розумної оптимізації
├── sharecard.py        ← картка результату для соцмереж
├── selftest.py         ← самоперевірка збірки (--selftest)
├── apps.py             ← winget, старі драйвери, аналізатор місця
├── power.py            ← частота екрана від живлення, ліміт заряду
├── report.py           ← звіт для форуму
├── lifecycle.py        ← одна копія програми, режими для інсталятора, видалення
├── updater.py          ← оновлення через GitHub Releases
├── hotkeys.py          ← глобальні гарячі клавіші
├── i18n.py             ← вибір мови
├── lang_*.py           ← переклади (uk, ru, en)
├── icon.ico, icon.png  ← іконка програми
├── bench.png           ← прев'ю сцени GPU-тесту
├── packaging/          ← інсталятор Inno Setup, OptimaX-Rescue.cmd, картинки майстра, release.py
├── tests/              ← тести (pytest), tests/windows/ — перевірка на справжній Windows для CI
├── .github/           ← ci.yml, release.yml, pages.yml, шаблони issues і PR
├── docs/              ← посібник, часті питання, список оптимізацій (uk, en), картинки
├── site/              ← сторінка програми для GitHub Pages
├── tools/             ← gen_docs.py (список оптимізацій з коду), publish_github.ps1
├── build_installer.bat ← інсталятор
├── build.bat           ← портативна версія
├── version_info.txt, requirements.txt
```

Щоб додати свою оптимізацію, достатньо одного рядка `tw(...)` в `engine.py` і рядка з назвою та описом у `lang_tweaks.py` — інтерфейс, профілі, пошук, перегляд змін, сторож і відкат підхоплять її самі.

## Список оптимізацій у документації

`docs/uk/tweaks.md` і `docs/en/tweaks.md` створюються з коду: `python tools/gen_docs.py`. CI перевіряє, що вони актуальні, тож після зміни твіка запустіть скрипт і закомітьте обидва файли.
