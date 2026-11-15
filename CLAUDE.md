# OptimaX — правила проєкту для Claude

OptimaX — безкоштовний оптимізатор Windows 10/11 (Python 3 + PyQt6, < Qt 6.13 заради Windows 10 1809+). Головна
обіцянка продукту: **кожна зміна вимірюється й повністю відкочується**. Автор — Ріхард (X44TO), спілкування
українською. Код, коментарі, коміти й CHANGELOG — українською (у CHANGELOG ще блок `<details>English</details>`).

## Запуск і тести

```
pip install -r requirements.txt pytest            # pip --break-system-packages у пісочниці
QT_QPA_PLATFORM=offscreen python3 -m pytest tests -q -p no:cacheprovider   # ~3 хв, усе має пройти
APPDATA=$(mktemp -d) OPTIMAX_DEMO=gaming|old|laptop python3 optimizer.py     # демо поза Windows
```

- Поза Windows `E.IS_WIN` = False, `E.DRY_RUN` = True: команди лише друкуються. `E.DEMO` — демо-залізо.
- `tests/scripts/fake_windows.py` — «фальшива Windows» (реєстр, служби, PowerShell у пам'яті) для перевірки
  журналу; `tests/scripts/ui_smoke.py` — проганяє весь інтерфейс на трьох демо-конфігураціях.
- Тест, якому потрібна справжня Windows, — `skip` поза нею; CI ганяє його на windows-2022 / windows-2025.
- CI (`.github/workflows/ci.yml`): Linux; Windows-тести; **кожен твік «застосувати → перевірити → відкотити»
  на справжній системі + відкат через OptimaX-Rescue.cmd** (`tests/windows/tweak_roundtrip.py`); інсталятор.
- Тест на справжній Windows: тимчасові шляхи — через `os.path.realpath` (8.3-імена `RUNNER~1`), а перевірку демо-
  режиму — з `IS_WIN=False`.

## Карта коду

| Файл | Що там |
| --- | --- |
| `engine.py` | Каталог твіків (`tw`, `TWEAKS`, `BY_ID`), виконавець (`run`, `ps`, `exec_op`, `apply_tweaks`), журнал (`Journal`, `valid_undo`), дії (`a_*`) |
| `optimizer.py` | Головне вікно `Main`, навігація (`NAV`), фоновий такт, `run_quick` / `RunDialog` |
| `features.py` | `CFG` (settings.json), режим гри `BOOSTER`, автозапуск |
| `pages_*.py` | Сторінки; `ui_kit.py` — віджети (`section_card`, `button`, `Ask`, `RunDialog`, `Worker`, `Ring`) |
| `lang_*.py` + `i18n.py` | Тексти; новий файл мов реєструється в `i18n._load()` |
| `rescue.py` | Генерує `OptimaX-Rescue.cmd` (аварійний відкат без Python, з безпечного режиму) |
| `secfs.py` | Довірені шляхи, захищені папки (`admin_dir`), `sysexe` |
| `healthcheck.py`, `crashlog.py`, `latencytest.py`, `freezecatch.py`… | Діагностика (лише читання) |

## Непорушні правила

1. **Зміна системи — лише через журнал.** Нова зміна = `tw(...)` у каталозі або `E.Tweak(..., custom=True)` +
   `E.apply_tweaks`. Ніяких «тихих» `reg add` / `sc config` поза ним.
2. **Запис відкату — до зміни** (`ctx.undo.append(rec)` перед командою; `ctx.undo.discard(rec)`, лише якщо
   команда точно відмовила, не за тайм-аутом). Команда, що змінює систему, — `stoppable=False`.
3. **Одна зміна за раз:** точки входу змін і відкатів обгорнуті `@_serial` (`CHANGE_LOCK`). Нова точка входу —
   теж.
4. **Чесний результат.** Крок не вдався → `ctx.fail(...)` → «частково». Не писати «готово», якщо команда
   повернула помилку; не ховати помилку в `except: pass`.
5. **Межа довіри.** OptimaX працює як адміністратор. Усе, що пише звичайна програма користувача (`%APPDATA%`
   і settings.json, HKCU, `%TEMP%`, PATH, змінні середовища), — **дані, а не шлях, команда чи адреса**:
   - exe запускати лише за повним шляхом із довіреного місця (`SF.sysexe`, `SF.trusted_location/owner`);
   - у PowerShell — `E._psq()` для рядків, `-EncodedCommand`; у .cmd — ніколи сирі значення (base64-PowerShell);
   - завантаження — лише з релізів репозиторію OptimaX (`updater.release_url`, `asset_name_ok`).
6. **Чесність каталогу.** Твік без доказу ефекту не обіцяє ефекту. Налагоджувальні параметри (bcdedit
   `disabledynamictick`, HPET) — не в профілях. Ніколи не пропонувати: вимкнення антивірусу чи виключення
   Defender, `MouseDataQueueSize`, `OverlayTestMode`, RWEverything/запис у пам'ять пристроїв.
7. **Три мови.** Кожен ключ — кортеж `(uk, ru, en)`, твік — `(uk-назва, uk-опис, ru-назва, ru-опис, en-назва,
   en-опис)`; плейсхолдери однакові в усіх мовах (це перевіряє `tests/test_i18n.py`).
8. **Новий модуль** — у `build.bat` і `build_installer.bat` (список файлів і `--hidden-import`).
9. Чужий код із закритою ліцензією не копіювати — лише ідеї.

## Випуск версії

1. `VERSION` в `engine.py`, `MyAppVersion` у `packaging/OptimaX.iss`, `python3 packaging/release.py version-info`,
   `python3 tools/gen_docs.py`.
2. `CHANGELOG.md` (розділ `## [x.y] — дата`, Додано / Виправлено / Змінено + English) і «Що нового»
   (`whatsnew.NOTES["x.y"]` + ключі `wn.xyz.*`).
3. Гілка → push → зелений CI → fast-forward у `main` (`git push origin <гілка>:main`).
4. Реліз: workflow `release.yml`. З пісочниці пуш тегів і зміна refs заборонені (403) — запускати
   `gh workflow run release.yml --ref main -f full_checks=true`; він сам створить тег. Тег, що вже стоїть на іншому
   коміті, сам не переміститься — сказати про це автору.

## Стиль

- Рядки ≤ 120 символів, коментарі пояснюють «чому», з номером версії для важливих виправлень (`# 6.17: …`).
- Мінімальна зміна, що повністю вирішує задачу; логіку й дизайн не міняти без потреби.
- Інтерфейс: темний, мінімалістичний, у стилі редизайну 6.13 (Octane-подібний), світла й темна теми.
