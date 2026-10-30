"""OptimaX — переклади: ігри на майнінговій відеокарті (P106 / P104 / CMP), DirectX 9 через DXVK, OpenGL через Mesa."""

STRINGS = {
    # ── ядро ──
    "e.file_changed": ("  · {path}: файл уже не той, що поклала OptimaX (гра оновилася?) — лишаємо як є",
                       "  · {path}: файл уже не тот, что положил OptimaX (игра обновилась?) — оставляем как есть",
                       "  · {path}: the file is no longer the one OptimaX put there (game update?) — left as is"),

    # ── журнал і підсумки ──
    "mg.t_gpu": ("{game}: {exe} → {gpu}", "{game}: {exe} → {gpu}", "{game}: {exe} → {gpu}"),
    "mg.t_env": ("Mesa: OpenGL малює майнінгова карта (змінна MESA_D3D12_DEFAULT_ADAPTER_NAME)",
                 "Mesa: OpenGL рисует майнинговая карта (переменная MESA_D3D12_DEFAULT_ADAPTER_NAME)",
                 "Mesa: OpenGL renders on the mining card (MESA_D3D12_DEFAULT_ADAPTER_NAME variable)"),
    "mg.t_layer": ("{game}: {what} (папка {folder})", "{game}: {what} (папка {folder})",
                   "{game}: {what} (folder {folder})"),
    "mg.summary": ("Ігор знайдено: {games}. Призначено на {gpu}: {n}, уже було: {already}, ваш вибір не чіпали: "
                   "{kept}. DirectX 9 і Adobe AIR Windows на {gpu} не перемикає: {dx9} (для DirectX 9 є DXVK).",
                   "Игр найдено: {games}. Назначено на {gpu}: {n}, уже было: {already}, ваш выбор не трогали: "
                   "{kept}. DirectX 9 и Adobe AIR Windows на {gpu} не переключает: {dx9} (для DirectX 9 есть DXVK).",
                   "Games found: {games}. Assigned to the {gpu}: {n}, already: {already}, your own choice kept: "
                   "{kept}. Windows can't move DirectX 9 and Adobe AIR to the {gpu}: {dx9} (DXVK handles DirectX 9)."),
    "mg.nothing": ("Змін OptimaX для майнінгової карти немає — повертати нічого.",
                   "Изменений OptimaX для майнинговой карты нет — возвращать нечего.",
                   "OptimaX made no mining-card changes — nothing to revert."),
    "mg.busy": ("  · OptimaX уже змінює налаштування ігор — спробуйте за хвилину",
                "  · OptimaX уже меняет настройки игр — попробуйте через минуту",
                "  · OptimaX is already changing game settings — try again in a minute"),
    "mg.layer_bad": ("Архів пошкоджений ({name}) — нічого не встановлено.",
                     "Архив повреждён ({name}) — ничего не установлено.",
                     "The archive is damaged ({name}) — nothing was installed."),
    "mg.layer_ready": ("{what} {v} готова.", "{what} {v} готова.", "{what} {v} is ready."),
    "mg.layer_not_found": ("Архів {what} не знайдено в релізах OptimaX. Оновіть OptimaX і спробуйте ще раз.",
                           "Архив {what} не найден в релизах OptimaX. Обновите OptimaX и попробуйте ещё раз.",
                           "The {what} archive was not found in the OptimaX releases. Update OptimaX and try again."),
    "mg.mesa_dl": ("Завантаження {name} ({mb} МБ)…", "Загрузка {name} ({mb} МБ)…", "Downloading {name} ({mb} MB)…"),
    "mg.layer_on": ("{game}: тепер малює майнінгова карта (через {what}). Перезапустіть лаунчер гри (Steam тощо), "
                    "щоб він побачив зміну.",
                    "{game}: теперь рисует майнинговая карта (через {what}). Перезапустите лаунчер игры (Steam и т. п.), "
                    "чтобы он увидел изменение.",
                    "{game}: the mining card renders it now (via {what}). Restart the game launcher (Steam etc.) so it "
                    "picks up the change."),

    # ── сторінка «Ігри» ──
    "mg.title": ("Ігри на {gpu}", "Игры на {gpu}", "Games on the {gpu}"),
    "mg.sub": ("У майнінгової карти немає відеовиходів: картинку виводить вбудована графіка, і без налаштувань ігри "
               "малює теж вона. OptimaX знаходить встановлені ігри (Steam, Epic, GOG, Ubisoft і «Мої ігри») і "
               "призначає їх на {gpu} — як «Висока продуктивність» у налаштуваннях «Графіка» Windows, тільки для всіх "
               "ігор одразу й з відкатом. Ігри на DirectX 9 і OpenGL бачать лише карту з монітором — для них нижче "
               "є DXVK і Mesa.",
               "У майнинговой карты нет видеовыходов: картинку выводит встроенная графика, и без настроек игры рисует "
               "тоже она. OptimaX находит установленные игры (Steam, Epic, GOG, Ubisoft и «Мои игры») и назначает их "
               "на {gpu} — как «Высокая производительность» в настройках «Графика» Windows, только для всех игр сразу "
               "и с откатом. Игры на DirectX 9 и OpenGL видят только карту с монитором — для них ниже есть DXVK и "
               "Mesa.",
               "A mining card has no video outputs: the integrated graphics show the picture and, unless told "
               "otherwise, render the games too. OptimaX finds installed games (Steam, Epic, GOG, Ubisoft and My "
               "games) and assigns them to the {gpu} — like “High performance” in Windows Graphics settings, but for "
               "every game at once and with rollback. DirectX 9 and OpenGL games only see the card the monitor is "
               "plugged into — DXVK and Mesa below handle those."),
    "mg.auto": ("Автоматично призначати нові ігри", "Автоматически назначать новые игры",
                "Assign new games automatically"),
    "mg.auto_d": ("Раз на 15 хвилин, поки OptimaX працює.", "Раз в 15 минут, пока OptimaX работает.",
                  "Every 15 minutes while OptimaX is running."),
    "mg.scan": ("Знайти й призначити ігри", "Найти и назначить игры", "Find and assign games"),
    "mg.revert": ("Повернути все", "Вернуть всё", "Revert all"),
    "mg.revert_q": ("Повернути ігри на налаштування Windows? Призначення OptimaX, DXVK і Mesa в папках ігор буде "
                    "прибрано.",
                    "Вернуть игры на настройки Windows? Назначения OptimaX, DXVK и Mesa в папках игр будут убраны.",
                    "Return games to the Windows settings? OptimaX assignments and DXVK / Mesa in game folders will be "
                    "removed."),
    "mg.reverted": ("Повернуто: ігри знову на налаштуваннях Windows", "Возвращено: игры снова на настройках Windows",
                    "Reverted: games are back on the Windows settings"),
    "mg.done": ("Призначено на {gpu}: {n}", "Назначено на {gpu}: {n}", "Assigned to the {gpu}: {n}"),
    "mg.empty": ("Натисніть «Знайти й призначити ігри» — OptimaX покаже встановлені ігри й те, що з ними зроблено.",
                 "Нажмите «Найти и назначить игры» — OptimaX покажет установленные игры и то, что с ними сделано.",
                 "Press “Find and assign games” — OptimaX will list your installed games and what was done to each."),
    "mg.none_found": ("Ігор не знайдено. Додайте exe гри в «Мої ігри» нижче й повторіть.",
                      "Игр не найдено. Добавьте exe игры в «Мои игры» ниже и повторите.",
                      "No games found. Add the game's exe to My games below and try again."),
    "mg.st.on": ("малює {gpu}", "рисует {gpu}", "renders on the {gpu}"),
    "mg.st.part": ("малює {gpu} ({n} з {total} exe)", "рисует {gpu} ({n} из {total} exe)",
                   "renders on the {gpu} ({n} of {total} exe)"),
    "mg.st.kept": ("ваше налаштування в «Графіці» — не чіпаємо", "ваша настройка в «Графике» — не трогаем",
                   "your own Graphics setting — left alone"),
    "mg.st.free": ("ще не призначено", "ещё не назначено", "not assigned yet"),
    "mg.st.dx9": ("DirectX 9: Windows таку гру на {gpu} не перемикає (DirectX 9 бачить лише карту з монітором) — "
                  "лише через DXVK",
                  "DirectX 9: Windows такую игру на {gpu} не переключает (DirectX 9 видит только карту с монитором) — "
                  "только через DXVK",
                  "DirectX 9: Windows can't move such a game to the {gpu} (DirectX 9 only sees the card with the "
                  "monitor) — only DXVK can"),
    "mg.st.dx9_on": ("DirectX 9 через DXVK — малює {gpu}", "DirectX 9 через DXVK — рисует {gpu}",
                     "DirectX 9 via DXVK — renders on the {gpu}"),
    "mg.st.dx9_na": ("DirectX 9, але DXVK для цього exe немає (лише x64 і x86)",
                     "DirectX 9, но DXVK для этого exe нет (только x64 и x86)",
                     "DirectX 9, but there is no DXVK for this exe (x64 and x86 only)"),
    "mg.st.air": ("Adobe AIR — лишається на вбудованій графіці", "Adobe AIR — остаётся на встроенной графике",
                  "Adobe AIR — stays on the integrated graphics"),
    "mg.st.gl": ("OpenGL: Windows таку гру на {gpu} не перемикає — лише через Mesa",
                 "OpenGL: Windows такую игру на {gpu} не переключает — только через Mesa",
                 "OpenGL: Windows can't move such a game to the {gpu} — only Mesa can"),
    "mg.st.gl_on": ("OpenGL через Mesa — малює {gpu}", "OpenGL через Mesa — рисует {gpu}",
                    "OpenGL via Mesa — renders on the {gpu}"),
    "mg.st.gl_na": ("OpenGL, але Mesa для цього exe немає (лише x64 і x86)",
                    "OpenGL, но Mesa для этого exe нет (только x64 и x86)",
                    "OpenGL, but there is no Mesa for this exe (x64 and x86 only)"),
    "mg.store.steam": ("Steam", "Steam", "Steam"),
    "mg.store.epic": ("Epic", "Epic", "Epic"),
    "mg.store.gog": ("GOG", "GOG", "GOG"),
    "mg.store.ubisoft": ("Ubisoft", "Ubisoft", "Ubisoft"),
    "mg.store.mine": ("Мої ігри", "Мои игры", "My games"),

    # ── шари: DXVK і Mesa ──
    "mg.on_btn": ("Увімкнути {what}", "Включить {what}", "Enable {what}"),
    "mg.off_btn": ("Вимкнути {what}", "Выключить {what}", "Disable {what}"),
    "mg.get": ("Завантажити {what}", "Загрузить {what}", "Download {what}"),
    "mg.got": ("{what} готова", "{what} готова", "{what} is ready"),
    "mg.have": ("{what} {v} завантажена.", "{what} {v} загружена.", "{what} {v} is downloaded."),
    "mg.none": ("{what} ще не завантажена.", "{what} ещё не загружена.", "{what} is not downloaded yet."),
    "mg.need": ("Спершу завантажте {what} кнопкою вище.", "Сначала загрузите {what} кнопкой выше.",
                "Download {what} with the button above first."),
    "mg.dxvk_t": ("DirectX 9 через DXVK", "DirectX 9 через DXVK", "DirectX 9 via DXVK"),
    "mg.dxvk_d": ("DirectX 9 (і 8) бачить лише відеокарту з монітором, тож «Графіка» Windows на такі ігри (CS:Source, "
                  "Half-Life 2, старі ігри) не діє. DXVK перекладає DirectX 9 на Vulkan, а Vulkan бачить {gpu}. "
                  "Вмикається для кожної гри окремо: d3d9.dll кладеться в папку гри й прибирається відкатом. DXVK "
                  "зроблений передусім для Linux — на Windows не кожна гра з ним запуститься, а онлайн-ігри з "
                  "античитом можуть не пустити чужу d3d9.dll; тоді просто вимкніть DXVK.",
                  "DirectX 9 (и 8) видит только видеокарту с монитором, поэтому «Графика» Windows на такие игры "
                  "(CS:Source, Half-Life 2, старые игры) не действует. DXVK переводит DirectX 9 на Vulkan, а Vulkan видит "
                  "{gpu}. Включается для каждой игры отдельно: d3d9.dll кладётся в папку игры и убирается откатом. DXVK "
                  "сделан прежде всего для Linux — на Windows не каждая игра с ним запустится, а онлайн-игры с "
                  "античитом могут не пустить чужую d3d9.dll; тогда просто выключите DXVK.",
                  "DirectX 9 (and 8) only sees the card the monitor is plugged into, so Windows Graphics settings don't "
                  "apply to such games (CS:Source, Half-Life 2, older titles). DXVK translates DirectX 9 to Vulkan, "
                  "and Vulkan sees the {gpu}. It is enabled per game: d3d9.dll goes into the game folder and is "
                  "removed by rollback. DXVK is made mainly for Linux — not every game starts with it on Windows, and "
                  "online games with anti-cheat may refuse a foreign d3d9.dll; then just disable DXVK."),
    "mg.dxvk_q": ("Увімкнути DXVK для «{game}»? Якщо гра не запуститься, покаже чорний екран або це онлайн-гра з "
                  "античитом — вимкніть DXVK тут же.",
                  "Включить DXVK для «{game}»? Если игра не запустится, покажет чёрный экран или это онлайн-игра с "
                  "античитом — выключите DXVK здесь же.",
                  "Enable DXVK for “{game}”? If the game doesn't start, shows a black screen or is an online game "
                  "with anti-cheat — disable DXVK right here."),
    "mg.mesa_t": ("OpenGL через Mesa", "OpenGL через Mesa", "OpenGL via Mesa"),
    "mg.mesa_d": ("Налаштування «Графіка» Windows на OpenGL не діє. Mesa перекладає OpenGL на DirectX 12, і тоді гру "
                  "малює {gpu}. Вмикається для кожної гри окремо: бібліотеки кладуться в папку гри й прибираються "
                  "відкатом. Онлайн-ігри з античитом можуть не пустити гру з чужою opengl32.dll — для них не вмикайте. "
                  "Mesa потрібна й GPU-тесту OptimaX, щоб його малювала {gpu}.",
                  "Настройка «Графика» Windows на OpenGL не действует. Mesa переводит OpenGL на DirectX 12, и тогда "
                  "игру рисует {gpu}. Включается для каждой игры отдельно: библиотеки кладутся в папку игры и убираются "
                  "откатом. Онлайн-игры с античитом могут не пустить игру с чужой opengl32.dll — для них не включайте. "
                  "Mesa нужна и GPU-тесту OptimaX, чтобы его рисовала {gpu}.",
                  "Windows Graphics settings don't apply to OpenGL. Mesa translates OpenGL to DirectX 12, and then the "
                  "{gpu} renders the game. It is enabled per game: the libraries go into the game folder and are "
                  "removed by rollback. Online games with anti-cheat may refuse to start with a foreign opengl32.dll — "
                  "don't enable it for those. The OptimaX GPU test also needs Mesa to render on the {gpu}."),
    "mg.mesa_q": ("Увімкнути Mesa для «{game}»? Якщо гра онлайн і з античитом, вона може не запуститися — тоді "
                  "вимкніть Mesa тут же.",
                  "Включить Mesa для «{game}»? Если игра онлайн и с античитом, она может не запуститься — тогда "
                  "выключите Mesa здесь же.",
                  "Enable Mesa for “{game}”? If it is an online game with anti-cheat, it may refuse to start — then "
                  "disable Mesa right here."),

    # ── GPU-тест ──
    "gb.mesa_note": ("Тест на OpenGL, тож на ПК з {gpu} його малює вбудована графіка. Завантажте Mesa на сторінці "
                     "«Ігри», і тест малюватиме {gpu}.",
                     "Тест на OpenGL, поэтому на ПК с {gpu} его рисует встроенная графика. Загрузите Mesa на странице "
                     "«Игры», и тест будет рисовать {gpu}.",
                     "The test uses OpenGL, so on a PC with a {gpu} the integrated graphics render it. Download Mesa "
                     "on the Games page and the test will render on the {gpu}."),
    "gb.mesa_on": ("Тест малюватиме {gpu} через Mesa (OpenGL → DirectX 12). Бали з Mesa порівнюються лише з балами "
                   "з Mesa.",
                   "Тест будет рисовать {gpu} через Mesa (OpenGL → DirectX 12). Баллы с Mesa сравниваются только с "
                   "баллами с Mesa.",
                   "The test will render on the {gpu} via Mesa (OpenGL → DirectX 12). Mesa scores are compared only "
                   "with other Mesa scores."),
}
