"""OptimaX — тексти «Відновити winget» (wingetfix.py): (uk, ru, en)."""

STRINGS = {
    "wg.title": ("Відновити winget", "Восстановить winget", "Restore winget"),
    "wg.btn": ("Відновити winget", "Восстановить winget", "Restore winget"),
    "wg.banner_d": (
        "winget входить до «Інсталятора програм» (App Installer). OptimaX може відновити його сама: повторно "
        "зареєструвати пакет, який уже є в Windows, а якщо його немає — встановити офіційні файли Microsoft "
        "з релізу OptimaX із перевіркою суми.",
        "winget входит в «Установщик приложений» (App Installer). OptimaX может восстановить его сама: повторно "
        "зарегистрировать пакет, который уже есть в Windows, а если его нет — установить официальные файлы "
        "Microsoft из релиза OptimaX с проверкой суммы.",
        "winget comes with App Installer. OptimaX can restore it for you: re-register the package that is already "
        "in Windows or, if it is missing, install the official Microsoft files from the OptimaX release with a "
        "checksum check."),
    "wg.diag": ("winget: {what}", "winget: {what}", "winget: {what}"),
    "wg.d.ok": ("працює", "работает", "works"),
    "wg.d.register": ("«Інсталятор програм» є в Windows, але не зареєстрований для цього користувача",
                      "«Установщик приложений» есть в Windows, но не зарегистрирован для этого пользователя",
                      "App Installer is in Windows but not registered for this user"),
    "wg.d.install": ("«Інсталятора програм» у Windows немає", "«Установщика приложений» в Windows нет",
                     "App Installer is missing from Windows"),
    "wg.d.unsupported": ("winget працює лише з Windows 10 1809 (збірка 17763) і новіших — на цій версії Windows "
                         "його не встановити.",
                         "winget работает только с Windows 10 1809 (сборка 17763) и новее — на этой версии Windows "
                         "его не установить.",
                         "winget needs Windows 10 1809 (build 17763) or newer — it cannot be installed on this "
                         "version of Windows."),
    "wg.d.unknown": ("Не вдалося перевірити стан «Інсталятора програм» (PowerShell не відповів). Нічого не змінено.",
                     "Не удалось проверить состояние «Установщика приложений» (PowerShell не ответил). Ничего не "
                     "изменено.",
                     "Could not check App Installer (PowerShell gave no answer). Nothing was changed."),
    "wg.d.other_user": ("OptimaX запущена від іншого облікового запису", "OptimaX запущена от другой учётной записи",
                        "OptimaX runs under another account"),
    "wg.other_user": (
        "OptimaX працює від імені {me}, а за комп'ютером — {desk}. winget реєструється для кожного користувача "
        "окремо, тож він з'явився б у {me}, а не у вас. Нічого не змінено. Увійдіть у Windows як адміністратор "
        "або запустіть OptimaX зі свого облікового запису й повторіть.",
        "OptimaX работает от имени {me}, а за компьютером — {desk}. winget регистрируется для каждого "
        "пользователя отдельно, поэтому он появился бы у {me}, а не у вас. Ничего не изменено. Войдите в Windows "
        "как администратор или запустите OptimaX из своей учётной записи и повторите.",
        "OptimaX runs as {me}, but {desk} is signed in at this PC. winget is registered per user, so it would "
        "appear for {me}, not for you. Nothing was changed. Sign in to Windows as an administrator or run OptimaX "
        "from your own account and try again."),
    "wg.no_desk": ("  · власника робочого столу визначити не вдалося — реєструємо для {me}",
                   "  · владельца рабочего стола определить не удалось — регистрируем для {me}",
                   "  · could not tell who owns the desktop — registering for {me}"),
    "wg.q_register": (
        "Крок 1, без завантаження: «Інсталятор програм» уже є в Windows — OptimaX повторно зареєструє його для "
        "{me} (Add-AppxPackage -RegisterByFamilyName) і перевірить, що winget запускається.",
        "Шаг 1, без загрузки: «Установщик приложений» уже есть в Windows — OptimaX повторно зарегистрирует его "
        "для {me} (Add-AppxPackage -RegisterByFamilyName) и проверит, что winget запускается.",
        "Step 1, no download: App Installer is already in Windows — OptimaX will re-register it for {me} "
        "(Add-AppxPackage -RegisterByFamilyName) and check that winget starts."),
    "wg.q_install": (
        "Крок 2: «Інсталятора програм» у Windows немає (LTSC, Server або його видалили). OptimaX завантажить "
        "близько {mb} МБ з власного релізу на GitHub — офіційні пакети Microsoft з релізу winget-cli "
        "(App Installer, VCLibs, UI.Xaml), перевірить SHA-256 кожного файлу і встановить їх для вашого "
        "облікового запису.",
        "Шаг 2: «Установщика приложений» в Windows нет (LTSC, Server или его удалили). OptimaX загрузит около "
        "{mb} МБ из собственного релиза на GitHub — официальные пакеты Microsoft из релиза winget-cli "
        "(App Installer, VCLibs, UI.Xaml), проверит SHA-256 каждого файла и установит их для вашей учётной "
        "записи.",
        "Step 2: App Installer is missing from Windows (LTSC, Server or removed). OptimaX will download about "
        "{mb} MB from its own GitHub release — the official Microsoft packages from the winget-cli release "
        "(App Installer, VCLibs, UI.Xaml), check the SHA-256 of every file and install them for your account."),
    "wg.btn_register": ("Зареєструвати", "Зарегистрировать", "Register"),
    "wg.btn_install": ("Завантажити й встановити", "Загрузить и установить", "Download and install"),
    "wg.s_check": ("Перевірка winget", "Проверка winget", "Checking winget"),
    "wg.s_register": ("Реєстрація «Інсталятора програм»", "Регистрация «Установщика приложений»",
                      "Registering App Installer"),
    "wg.s_verify": ("Перевірка winget --version", "Проверка winget --version", "Checking winget --version"),
    "wg.s_download": ("Завантаження з релізу OptimaX", "Загрузка из релиза OptimaX", "Downloading from the OptimaX "
                      "release"),
    "wg.s_unpack": ("Перевірка файлів", "Проверка файлов", "Checking files"),
    "wg.s_install": ("Встановлення «Інсталятора програм»", "Установка «Установщика приложений»",
                     "Installing App Installer"),
    "wg.registering": ("[►] Реєстрація «Інсталятора програм» для {me}",
                       "[►] Регистрация «Установщика приложений» для {me}",
                       "[►] Registering App Installer for {me}"),
    "wg.installing": ("[►] Встановлення «Інсталятора програм» для {me}",
                      "[►] Установка «Установщика приложений» для {me}",
                      "[►] Installing App Installer for {me}"),
    "wg.absent": ("  · пакета в Windows немає — потрібне завантаження (крок 2)",
                  "  · пакета в Windows нет — нужна загрузка (шаг 2)",
                  "  · the package is not in Windows — a download is needed (step 2)"),
    "wg.works": ("  ✓ winget працює {v}", "  ✓ winget работает {v}", "  ✓ winget works {v}"),
    "wg.ps_fail": ("  ✗ Add-AppxPackage: {err}", "  ✗ Add-AppxPackage: {err}", "  ✗ Add-AppxPackage: {err}"),
    "wg.reg_fail": ("Не вдалося зареєструвати «Інсталятор програм» — подробиці в журналі.",
                    "Не удалось зарегистрировать «Установщик приложений» — подробности в журнале.",
                    "Could not register App Installer — see the log for details."),
    "wg.inst_fail": ("Не вдалося встановити «Інсталятор програм» — подробиці в журналі.",
                     "Не удалось установить «Установщик приложений» — подробности в журнале.",
                     "Could not install App Installer — see the log for details."),
    "wg.not_found_after": ("Команда виконалась, але winget так і не знайдено в папці пакета (або він не "
                           "запускається). Спробуйте перезавантажити ПК і повторити.",
                           "Команда выполнилась, но winget так и не найден в папке пакета (или он не "
                           "запускается). Попробуйте перезагрузить ПК и повторить.",
                           "The command finished, but winget is still not found in the package folder (or does "
                           "not start). Restart the PC and try again."),
    "wg.no_asset": ("У релізах OptimaX немає файлів winget (OptimaX-WinGet-*.zip) — встановіть «Інсталятор "
                    "програм» з Microsoft Store.",
                    "В релизах OptimaX нет файлов winget (OptimaX-WinGet-*.zip) — установите «Установщик "
                    "приложений» из Microsoft Store.",
                    "The OptimaX releases have no winget files (OptimaX-WinGet-*.zip) — install App Installer "
                    "from the Microsoft Store."),
    "wg.downloading": ("[►] Завантаження {name} ({mb} МБ)", "[►] Загрузка {name} ({mb} МБ)",
                       "[►] Downloading {name} ({mb} MB)"),
    "wg.bad_file": ("Файл {name} не збігся із сумою — не встановлюємо.",
                    "Файл {name} не совпал с суммой — не устанавливаем.",
                    "{name} does not match its checksum — not installing."),
    "wg.arch": ("Для архітектури {arch} файлів winget немає.", "Для архитектуры {arch} файлов winget нет.",
                "There are no winget files for the {arch} architecture."),
    "wg.no_deps": ("  · залежностей для {arch} у релізі немає — встановлюємо лише пакет",
                   "  · зависимостей для {arch} в релизе нет — устанавливаем только пакет",
                   "  · the release has no dependencies for {arch} — installing the package alone"),
}
