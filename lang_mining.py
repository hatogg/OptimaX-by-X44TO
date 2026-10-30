"""OptimaX — переклади: ігри на майнінговій відеокарті (P106 / P104 / CMP), OpenGL через Mesa."""

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
    "mg.t_mesa": ("{game}: OpenGL через Mesa (папка {folder})", "{game}: OpenGL через Mesa (папка {folder})",
                  "{game}: OpenGL via Mesa (folder {folder})"),
    "mg.summary": ("Ігор знайдено: {games}. Призначено на {gpu}: {n}, уже було: {already}, ваш вибір не чіпали: "
                   "{kept}, DirectX 9 / Adobe AIR лишено на вбудованій: {dx9}.",
                   "Игр найдено: {games}. Назначено на {gpu}: {n}, уже было: {already}, ваш выбор не трогали: "
                   "{kept}, DirectX 9 / Adobe AIR оставлено на встроенной: {dx9}.",
                   "Games found: {games}. Assigned to {gpu}: {n}, already: {already}, your own choice kept: {kept}, "
                   "DirectX 9 / Adobe AIR left on the integrated graphics: {dx9}."),
    "mg.nothing": ("Змін OptimaX для майнінгової карти немає — повертати нічого.",
                   "Изменений OptimaX для майнинговой карты нет — возвращать нечего.",
                   "OptimaX made no mining-card changes — nothing to revert."),
    "mg.mesa_bad": ("Архів Mesa пошкоджений ({name}) — нічого не встановлено.",
                    "Архив Mesa повреждён ({name}) — ничего не установлено.",
                    "The Mesa archive is damaged ({name}) — nothing was installed."),
    "mg.busy": ("  · OptimaX уже змінює налаштування ігор — спробуйте за хвилину",
                "  · OptimaX уже меняет настройки игр — попробуйте через минуту",
                "  · OptimaX is already changing game settings — try again in a minute"),
    "mg.mesa_ready": ("Mesa {v} готова.", "Mesa {v} готова.", "Mesa {v} is ready."),
    "mg.mesa_not_found": ("Архів Mesa не знайдено в релізах OptimaX. Оновіть OptimaX і спробуйте ще раз.",
                          "Архив Mesa не найден в релизах OptimaX. Обновите OptimaX и попробуйте ещё раз.",
                          "The Mesa archive was not found in the OptimaX releases. Update OptimaX and try again."),
    "mg.mesa_dl": ("Завантаження {name} ({mb} МБ)…", "Загрузка {name} ({mb} МБ)…", "Downloading {name} ({mb} MB)…"),
    "mg.mesa_on": ("{game}: OpenGL тепер малює майнінгова карта (через Mesa). Перезапустіть лаунчер гри (Steam тощо), "
                   "щоб він побачив зміну.",
                   "{game}: OpenGL теперь рисует майнинговая карта (через Mesa). Перезапустите лаунчер игры (Steam и "
                   "т. п.), чтобы он увидел изменение.",
                   "{game}: OpenGL now renders on the mining card (via Mesa). Restart the game launcher (Steam etc.) "
                   "so it picks up the change."),

    # ── сторінка «Ігри» ──
    "mg.title": ("Ігри на {gpu}", "Игры на {gpu}", "Games on the {gpu}"),
    "mg.sub": ("У майнінгової карти немає відеовиходів: картинку виводить вбудована графіка, і без налаштувань ігри "
               "малює теж вона. OptimaX знаходить встановлені ігри (Steam, Epic, GOG, Ubisoft і «Мої ігри») і "
               "призначає їх на {gpu} — як «Висока продуктивність» у налаштуваннях «Графіка» Windows, тільки для всіх "
               "ігор одразу й з відкатом.",
               "У майнинговой карты нет видеовыходов: картинку выводит встроенная графика, и без настроек игры рисует "
               "тоже она. OptimaX находит установленные игры (Steam, Epic, GOG, Ubisoft и «Мои игры») и назначает их "
               "на {gpu} — как «Высокая производительность» в настройках «Графика» Windows, только для всех игр сразу "
               "и с откатом.",
               "A mining card has no video outputs: the integrated graphics show the picture and, unless told "
               "otherwise, render the games too. OptimaX finds installed games (Steam, Epic, GOG, Ubisoft and My "
               "games) and assigns them to the {gpu} — like “High performance” in Windows Graphics settings, but for "
               "every game at once and with rollback."),
    "mg.auto": ("Автоматично призначати нові ігри", "Автоматически назначать новые игры",
                "Assign new games automatically"),
    "mg.auto_d": ("Раз на 15 хвилин, поки OptimaX працює.", "Раз в 15 минут, пока OptimaX работает.",
                  "Every 15 minutes while OptimaX is running."),
    "mg.scan": ("Знайти й призначити ігри", "Найти и назначить игры", "Find and assign games"),
    "mg.revert": ("Повернути все", "Вернуть всё", "Revert all"),
    "mg.revert_q": ("Повернути ігри на налаштування Windows? Призначення OptimaX і Mesa в папках ігор буде прибрано.",
                    "Вернуть игры на настройки Windows? Назначения OptimaX и Mesa в папках игр будут убраны.",
                    "Return games to the Windows settings? OptimaX assignments and Mesa in game folders will be "
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
    "mg.st.dx9": ("DirectX 9 / Adobe AIR — лишено на вбудованій: на майнінговій карті такі ігри дають синій екран",
                  "DirectX 9 / Adobe AIR — оставлено на встроенной: на майнинговой карте такие игры дают синий экран",
                  "DirectX 9 / Adobe AIR — left on the integrated graphics: on a mining card such games blue-screen"),
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
    "mg.mesa_on_btn": ("Увімкнути Mesa", "Включить Mesa", "Enable Mesa"),
    "mg.mesa_off_btn": ("Вимкнути Mesa", "Выключить Mesa", "Disable Mesa"),
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
    "mg.mesa_none": ("Mesa ще не завантажена.", "Mesa ещё не загружена.", "Mesa is not downloaded yet."),
    "mg.mesa_have": ("Mesa {v} завантажена.", "Mesa {v} загружена.", "Mesa {v} is downloaded."),
    "mg.mesa_get": ("Завантажити Mesa", "Загрузить Mesa", "Download Mesa"),
    "mg.mesa_got": ("Mesa готова", "Mesa готова", "Mesa is ready"),
    "mg.mesa_q": ("Увімкнути Mesa для «{game}»? Якщо гра онлайн і з античитом, вона може не запуститися — тоді "
                  "вимкніть Mesa тут же.",
                  "Включить Mesa для «{game}»? Если игра онлайн и с античитом, она может не запуститься — тогда "
                  "выключите Mesa здесь же.",
                  "Enable Mesa for “{game}”? If it is an online game with anti-cheat, it may refuse to start — then "
                  "disable Mesa right here."),
    "mg.mesa_need": ("Спершу завантажте Mesa кнопкою вище.", "Сначала загрузите Mesa кнопкой выше.",
                     "Download Mesa with the button above first."),

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
