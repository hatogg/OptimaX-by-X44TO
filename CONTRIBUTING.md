# Як долучитися · Contributing

[Українська](#українська) · [English](#english)

## Українська

Дякуємо, що хочете зробити OptimaX кращим. Найкорисніше:

- **Звіт про помилку.** [Відкрийте issue](https://github.com/hatogg/OptimaX-by-X44TO/issues/new/choose) і додайте звіт із програми: Діагностика → «Звіт для форуму чи майстра» → «Скопіювати як текст». Там залізо, версія Windows і застосовані зміни, без особистих даних.
- **Нова оптимізація.** Опишіть, що вона змінює (ключ реєстру, служба, команда), навіщо це, як її повернути і звідки відомо, що це працює.
- **Переклад.** Кожен рядок інтерфейсу має українську, російську й англійську версії.
- **Код.** Pull request вітаються — нижче як підготувати середовище й що перевірити.

### Середовище

```bash
pip install -r requirements.txt pytest cryptography
python optimizer.py --dry-run          # режим перегляду: показує команди, нічого не змінює
python -m pytest tests -v              # або python tests/run_tests.py
```

Поза Windows програма працює на демо-залізі (`OPTIMAX_DEMO=gaming|laptop|old|x3d|xeon`), тож інтерфейс і логіку можна розробляти й на Linux чи macOS.

### Як додати оптимізацію

1. Рядок `tw(...)` у `engine.py`, у потрібному розділі:

   ```python
   tw("w10_ink_off", "lite", [R(r"HKLM\SOFTWARE\Policies\Microsoft\WindowsInkWorkspace", "AllowWindowsInkWorkspace", 0)],
      p="FMOX", win10=True)
   ```

   `p` — профілі (F, M, L, T — ноутбук, O — старий ПК, X — Xeon), `impact` — `safe` / `medium` / `habits`, `reboot=True`, якщо діє після перезавантаження. Для заліза — `needs`, `warn_on`, `block_on`.
2. Назва й опис трьома мовами в `lang_tweaks.py`: `(uk назва, uk опис, ru назва, ru опис, en назва, en опис)`.
3. `python tools/gen_docs.py` — оновить список у `docs/uk/tweaks.md` і `docs/en/tweaks.md`.
4. `python -m pytest tests`.

Реєстр (`R`, `RD`), служби (`S`), задачі (`TK`) і параметри живлення (`P`) самі записують, що повертати. Для команди `C(...)` обов'язково вкажіть команду відкату. Оптимізацію, яку неможливо повернути, позначайте `reversible=False` і пишіть про це в описі.

### Перед pull request

- [ ] `python -m pytest tests` проходить.
- [ ] Нові рядки інтерфейсу є всіма трьома мовами з однаковими `{підстановками}`.
- [ ] Кожна зміна системи потрапляє в журнал відкату.
- [ ] `build.bat` і `build_installer.bat` лише ASCII з CRLF; новий модуль доданий в обидва списки файлів і `--hidden-import` (це перевіряє `tests/test_static.py`).
- [ ] Список оптимізацій оновлено (`tools/gen_docs.py`), якщо змінювались твіки.

> `tests/windows/tweak_roundtrip.py` **змінює систему** — він для одноразових машин CI. Не запускайте його на своєму ПК.

## English

Thanks for wanting to make OptimaX better. The most useful things:

- **Bug report.** [Open an issue](https://github.com/hatogg/OptimaX-by-X44TO/issues/new/choose) and attach the report from the program: Diagnostics → “Report for a forum or technician” → “Copy as text”. It has the hardware, Windows version and applied changes, with no personal data.
- **New optimization.** Describe what it changes (registry key, service, command), why, how to roll it back, and how we know it works.
- **Translation.** Every interface string has Ukrainian, Russian and English versions.
- **Code.** Pull requests are welcome; below is how to set up and what to check.

### Setup

```bash
pip install -r requirements.txt pytest cryptography
python optimizer.py --dry-run          # preview mode: shows commands, changes nothing
python -m pytest tests -v              # or python tests/run_tests.py
```

Outside Windows the program runs on demo hardware (`OPTIMAX_DEMO=gaming|laptop|old|x3d|xeon`), so you can work on the interface and logic on Linux or macOS too.

### Adding an optimization

1. A `tw(...)` line in `engine.py`, in the right section:

   ```python
   tw("w10_ink_off", "lite", [R(r"HKLM\SOFTWARE\Policies\Microsoft\WindowsInkWorkspace", "AllowWindowsInkWorkspace", 0)],
      p="FMOX", win10=True)
   ```

   `p` is the profiles (F, M, L, T for laptop, O for old PC, X for Xeon), `impact` is `safe` / `medium` / `habits`, `reboot=True` if it works after a restart. For hardware: `needs`, `warn_on`, `block_on`.
2. A title and description in three languages in `lang_tweaks.py`: `(uk title, uk description, ru title, ru description, en title, en description)`.
3. `python tools/gen_docs.py` updates the list in `docs/uk/tweaks.md` and `docs/en/tweaks.md`.
4. `python -m pytest tests`.

The registry (`R`, `RD`), services (`S`), tasks (`TK`) and power settings (`P`) record what to restore on their own. For a command `C(...)` you must give the rollback command. Mark an optimization that can't be rolled back with `reversible=False` and say so in its description.

### Before a pull request

- [ ] `python -m pytest tests` passes.
- [ ] New interface strings exist in all three languages with the same `{placeholders}`.
- [ ] Every system change goes to the rollback journal.
- [ ] `build.bat` and `build_installer.bat` are ASCII with CRLF; a new module is in both file lists and `--hidden-import` (`tests/test_static.py` checks this).
- [ ] The optimization list is updated (`tools/gen_docs.py`) if tweaks changed.

> `tests/windows/tweak_roundtrip.py` **changes the system**; it's for disposable CI machines. Don't run it on your PC.
