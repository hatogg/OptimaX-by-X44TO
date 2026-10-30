"""Переклади OptimaX 6.5: Universal GPU Renderer, аналізатори карти, база сумісності, Game Booster 2.0
(українська, російська, англійська)."""

STRINGS = {
    # ── режими рендерингу ──
    "mg.mode.auto": ("Авто", "Авто", "Auto"),
    "mg.mode.native": ("Напряму на карту", "Напрямую на карту", "Native GPU"),
    "mg.mode.dxvk": ("DXVK", "DXVK", "DXVK"),
    "mg.mode.opengl": ("OpenGL через Mesa", "OpenGL через Mesa", "OpenGL translation"),
    "mg.mode.original": ("Оригінал", "Оригинал", "Original"),
    "mg.mode.auto.d": ("Найкращий сумісний спосіб: DirectX 10–12 і Vulkan — напряму на карту, DirectX 9 — через DXVK, "
                       "OpenGL — через Mesa. Шар — лише якщо він завантажений і перевірений, exe потрібної розрядності, "
                       "а гра без античиту.",
                       "Лучший совместимый способ: DirectX 10–12 и Vulkan — напрямую на карту, DirectX 9 — через DXVK, "
                       "OpenGL — через Mesa. Слой — только если он загружен и проверен, exe нужной разрядности, а игра "
                       "без античита.",
                       "The best compatible way: DirectX 10–12 and Vulkan go straight to the card, DirectX 9 via DXVK, "
                       "OpenGL via Mesa. A layer is used only if it is downloaded and verified, the exe has the right "
                       "bitness and the game has no anti-cheat."),
    "mg.mode.native.d": ("Лише «Висока продуктивність» у «Графіці» Windows для exe гри, без жодних бібліотек. Для "
                         "DirectX 10–12 і Vulkan цього досить; DirectX 9 і OpenGL так на карту без монітора не перейдуть.",
                         "Только «Высокая производительность» в «Графике» Windows для exe игры, без библиотек. Для "
                         "DirectX 10–12 и Vulkan этого достаточно; DirectX 9 и OpenGL так на карту без монитора не "
                         "перейдут.",
                         "Only “High performance” in Windows Graphics settings for the game's exe, no libraries. Enough "
                         "for DirectX 10–12 and Vulkan; DirectX 9 and OpenGL will not move to a card without a monitor "
                         "this way."),
    "mg.mode.dxvk.d": ("DXVK і для DirectX 10 / 11: допомагає, коли гра навіть із «Високою продуктивністю» малює на "
                       "вбудованій (наприклад, у справжньому повноекранному режимі). Не для онлайн-ігор з античитом.",
                       "DXVK и для DirectX 10 / 11: помогает, когда игра даже с «Высокой производительностью» рисует на "
                       "встроенной (например, в настоящем полноэкранном режиме). Не для онлайн-игр с античитом.",
                       "DXVK for DirectX 10 / 11 too: helps when a game still renders on the integrated GPU despite "
                       "“High performance” (for example, in exclusive fullscreen). Not for online games with "
                       "anti-cheat."),
    "mg.mode.opengl.d": ("OpenGL через Mesa (DirectX 12 або Zink — див. вибір вище), DirectX — напряму. Лише для "
                         "OpenGL-exe цієї гри: інші ігри OpenGL не змінюються.",
                         "OpenGL через Mesa (DirectX 12 или Zink — см. выбор выше), DirectX — напрямую. Только для "
                         "OpenGL-exe этой игры: другие игры OpenGL не меняются.",
                         "OpenGL via Mesa (DirectX 12 or Zink — see the choice above), DirectX goes direct. Only for "
                         "this game's OpenGL exe files; other OpenGL games are not changed."),
    "mg.mode.original.d": ("Жодних змін OptimaX у цій грі: усе, що OptimaX для неї зробила, повертається, а фонове "
                           "призначення ігор її оминає.",
                           "Никаких изменений OptimaX в этой игре: всё, что OptimaX для неё сделала, возвращается, а "
                           "фоновое назначение игр её обходит.",
                           "No OptimaX changes in this game: everything OptimaX did for it is reverted and background "
                           "assignment skips it."),
    "mg.mode_applied": ("{game}: режим «{mode}».", "{game}: режим «{mode}».", "{game}: “{mode}” mode."),
    "mg.mode_failed": ("{game}: не вдалося — повертаю попередній режим «{mode}».",
                       "{game}: не удалось — возвращаю предыдущий режим «{mode}».",
                       "{game}: failed — returning to the previous “{mode}” mode."),
    "mg.blocked": ("  · {what} не застосовано: {why}", "  · {what} не применён: {why}", "  · {what} not applied: {why}"),
    "mg.reset_done": ("{game}: профіль видалено, гра в оригінальному стані.",
                      "{game}: профиль удалён, игра в исходном состоянии.",
                      "{game}: profile removed, the game is back to its original state."),
    "mg.why.risk": ("Adobe AIR — на майнінгових картах ті самі сині екрани, що й старі DirectX 9",
                    "Adobe AIR — на майнинговых картах те же синие экраны, что и старые DirectX 9",
                    "Adobe AIR — the same blue screens on mining cards as old DirectX 9"),
    "mg.why.anticheat": ("в грі є античит — чужа d3d9 / d3d11 / opengl32.dll може не пустити гру або вважатися "
                         "втручанням",
                         "в игре есть античит — чужая d3d9 / d3d11 / opengl32.dll может не пустить игру или считаться "
                         "вмешательством",
                         "the game has anti-cheat — a foreign d3d9 / d3d11 / opengl32.dll may block it or count as "
                         "tampering"),
    "mg.why.arch": ("немає exe x64 / x86 з потрібним API", "нет exe x64 / x86 с нужным API",
                    "no x64 / x86 exe with that API"),
    "mg.why.no_layer": ("шар не завантажено або в ньому немає потрібних бібліотек (оновіть кнопкою нижче)",
                        "слой не загружен или в нём нет нужных библиотек (обновите кнопкой ниже)",
                        "the layer is not downloaded or lacks the needed libraries (update it below)"),
    "mg.why.no_vulkan": ("Vulkan на майнінговій карті не знайдено — DXVK і Zink без нього не працюють",
                         "Vulkan на майнинговой карте не найден — DXVK и Zink без него не работают",
                         "no Vulkan on the mining card — DXVK and Zink cannot work without it"),
    "mg.why.no_gpu": ("DirectX не бачить майнінгову карту (драйвер не встановлено, карту вимкнено або стандартний драйвер "
                      "вимкнув 3D) — див. Universal GPU Renderer",
                      "DirectX не видит майнинговую карту (драйвер не установлен, карта отключена или стандартный "
                      "драйвер отключил 3D) — см. Universal GPU Renderer",
                      "DirectX does not see the mining card (no driver, card disabled, or the stock driver disabled "
                      "3D) — see Universal GPU Renderer"),
    "mg.why.no_d3d12": ("карта не підтримала DirectX 12 — Mesa d3d12 не запуститься (спробуйте Zink)",
                        "карта не поддержала DirectX 12 — Mesa d3d12 не запустится (попробуйте Zink)",
                        "the card did not accept DirectX 12 — Mesa d3d12 will not start (try Zink)"),
    "mg.rec.air": ("Adobe AIR — лишити як є", "Adobe AIR — оставить как есть", "Adobe AIR — leave as is"),
    "mg.rec.db": ("так радить база сумісності", "так советует база совместимости", "the compatibility database says so"),
    "mg.rec.anticheat": ("античит — без шарів", "античит — без слоёв", "anti-cheat — no layers"),
    "mg.rec.dx9": ("DirectX 9 — лише через DXVK", "DirectX 9 — только через DXVK", "DirectX 9 — only via DXVK"),
    "mg.rec.gl": ("OpenGL — лише через Mesa", "OpenGL — только через Mesa", "OpenGL — only via Mesa"),
    "mg.rec.direct": ("DirectX 10+ / Vulkan Windows перемикає сам", "DirectX 10+ / Vulkan Windows переключает сам",
                      "Windows switches DirectX 10+ / Vulkan itself"),
    "mg.t_env_zink": ("Mesa: OpenGL через Zink (Vulkan) на майнінговій карті (змінні MESA_D3D12_DEFAULT_ADAPTER_NAME, "
                      "GALLIUM_DRIVER)",
                      "Mesa: OpenGL через Zink (Vulkan) на майнинговой карте (переменные "
                      "MESA_D3D12_DEFAULT_ADAPTER_NAME, GALLIUM_DRIVER)",
                      "Mesa: OpenGL via Zink (Vulkan) on the mining card (MESA_D3D12_DEFAULT_ADAPTER_NAME, "
                      "GALLIUM_DRIVER variables)"),
    "mg.new_games": ("Нові ігри ({n}): {names}. Режим для кожної — у розділі «Ігри».",
                     "Новые игры ({n}): {names}. Режим для каждой — в разделе «Игры».",
                     "New games ({n}): {names}. Pick a mode for each on the Games page."),

    # ── GPU Renderer Monitor ──
    "gr.title": ("Universal GPU Renderer", "Universal GPU Renderer", "Universal GPU Renderer"),
    "gr.probe_wait": ("Перевіряю, що бачать DirectX і Vulkan…", "Проверяю, что видят DirectX и Vulkan…",
                      "Checking what DirectX and Vulkan see…"),
    "gr.probe_btn": ("Перевірити ще раз", "Проверить ещё раз", "Check again"),
    "gr.probe": ("{model} — драйвер бачить її як «{name}», версія {driver}. DirectX 12: {dx12} · Vulkan: {vk} · "
                 "монітор: {display} (перевірено {when}).",
                 "{model} — драйвер видит её как «{name}», версия {driver}. DirectX 12: {dx12} · Vulkan: {vk} · "
                 "монитор: {display} (проверено {when}).",
                 "{model} — the driver sees it as “{name}”, version {driver}. DirectX 12: {dx12} · Vulkan: {vk} · "
                 "monitor: {display} (checked {when})."),
    "gr.probe_none": ("Ні DirectX, ні Vulkan майнінгової карти не бачать (перевірено {when}). Див. пояснення нижче.",
                      "Ни DirectX, ни Vulkan майнинговую карту не видят (проверено {when}). См. пояснение ниже.",
                      "Neither DirectX nor Vulkan sees the mining card (checked {when}). See below."),
    "gr.yes": ("так", "да", "yes"),
    "gr.no": ("ні", "нет", "no"),
    "gr.driver": ("драйвер", "драйвер", "driver"),
    "gr.v.mining": ("Малює {gpu}: 3D {d3}%, копіювання кадрів {copy}%, відеопам'ять гри {vram} ГБ.",
                    "Рисует {gpu}: 3D {d3}%, копирование кадров {copy}%, видеопамять игры {vram} ГБ.",
                    "The {gpu} renders: 3D {d3}%, frame copy {copy}%, game VRAM {vram} GB."),
    "gr.v.igpu": ("Гра малює НЕ на {gpu}: на майнінговій карті 3D-роботи немає — малює вбудована графіка.",
                  "Игра рисует НЕ на {gpu}: на майнинговой карте 3D-работы нет — рисует встроенная графика.",
                  "The game does NOT render on the {gpu}: no 3D work on the mining card — the integrated GPU renders."),
    "gr.v.warp": ("Гра малює програмно (Microsoft Basic Render / WARP або Mesa llvmpipe) — процесором, а не "
                  "відеокартою. Для Mesa: поверніть DirectX 12 замість Zink або вимкніть Mesa для гри.",
                  "Игра рисует программно (Microsoft Basic Render / WARP или Mesa llvmpipe) — процессором, а не "
                  "видеокартой. Для Mesa: верните DirectX 12 вместо Zink или выключите Mesa для игры.",
                  "The game renders in software (Microsoft Basic Render / WARP or Mesa llvmpipe) — on the CPU, not a "
                  "GPU. For Mesa: switch back from Zink to DirectX 12 or turn Mesa off for the game."),
    "gr.v.idle": ("Гра згорнута або нічого не малює — розгорніть її й перевірте ще раз.",
                  "Игра свёрнута или ничего не рисует — разверните её и проверьте ещё раз.",
                  "The game is minimised or not drawing — bring it to the front and check again."),
    "gr.v.none": ("Процес гри не знайдено.", "Процесс игры не найден.", "The game process was not found."),
    "gr.auto_igpu": ("{game} малює не на {gpu} — відкрийте «Ігри», щоб змінити режим.",
                     "{game} рисует не на {gpu} — откройте «Игры», чтобы сменить режим.",
                     "{game} is not rendering on the {gpu} — open Games to change its mode."),
    "gr.not_listed": ("{exe} немає в списку ігор. Натисніть «Знайти й призначити ігри» або додайте exe в «Мої ігри».",
                      "{exe} нет в списке игр. Нажмите «Найти и назначить игры» или добавьте exe в «Мои игры».",
                      "{exe} is not in the games list. Press “Find and assign games” or add the exe to My games."),
    "gr.mode_btn": ("Режим", "Режим", "Mode"),
    "gr.check_btn": ("Перевірити", "Проверить", "Check"),
    "gr.st.original": ("оригінал — OptimaX нічого не змінює", "оригинал — OptimaX ничего не меняет",
                       "original — OptimaX changes nothing"),
    "gr.st.dxvk_dx11": ("DirectX 11 через DXVK", "DirectX 11 через DXVK", "DirectX 11 via DXVK"),
    "gr.last.mining": ("✓ перевірено {when} ({mode}): малює {gpu}", "✓ проверено {when} ({mode}): рисует {gpu}",
                       "✓ checked {when} ({mode}): renders on the {gpu}"),
    "gr.last.igpu": ("✗ перевірено {when} ({mode}): малює вбудована, не {gpu}",
                     "✗ проверено {when} ({mode}): рисует встроенная, не {gpu}",
                     "✗ checked {when} ({mode}): the integrated GPU renders, not the {gpu}"),
    "gr.last.warp": ("✗ перевірено {when} ({mode}): програмний рендеринг (WARP)",
                     "✗ проверено {when} ({mode}): программный рендеринг (WARP)",
                     "✗ checked {when} ({mode}): software rendering (WARP)"),
    "gr.last.idle": ("перевірено {when} ({mode}): гра нічого не малювала", "проверено {when} ({mode}): игра ничего не рисовала",
                     "checked {when} ({mode}): the game was not drawing"),
    "gr.last.none": ("перевірено {when} ({mode}): гру не знайдено", "проверено {when} ({mode}): игра не найдена",
                     "checked {when} ({mode}): game not found"),
    "gr.rec": ("Ще не перевірено на цьому ПК. Рекомендовано: {mode} ({why}).",
               "Ещё не проверено на этом ПК. Рекомендуется: {mode} ({why}).",
               "Not checked on this PC yet. Recommended: {mode} ({why})."),
    "gr.gl_t": ("OpenGL через Mesa", "OpenGL через Mesa", "OpenGL via Mesa"),
    "gr.gl_d": ("Чим Mesa малює OpenGL-ігри, для яких її ввімкнено: DirectX 12 (перевірено в CI на WARP) або Zink "
                "(OpenGL → Vulkan, експериментально). Інші OpenGL-ігри не змінюються.",
                "Чем Mesa рисует OpenGL-игры, для которых она включена: DirectX 12 (проверено в CI на WARP) или Zink "
                "(OpenGL → Vulkan, экспериментально). Другие OpenGL-игры не меняются.",
                "What Mesa uses for the OpenGL games it is enabled for: DirectX 12 (verified in CI on WARP) or Zink "
                "(OpenGL → Vulkan, experimental). Other OpenGL games are not changed."),
    "gr.gl_d3d12": ("DirectX 12", "DirectX 12", "DirectX 12"),
    "gr.gl_zink": ("Zink (Vulkan)", "Zink (Vulkan)", "Zink (Vulkan)"),
    "gr.zink_q": ("Zink перекладає OpenGL на Vulkan. На Windows він експериментальний: частина ігор покаже артефакти "
                  "або не запуститься — тоді поверніть DirectX 12. Перемкнути всі ігри з Mesa на Zink? Перевірте "
                  "результат кнопкою «Перевірити» в рядку гри — вона покаже, чи малює {gpu}.",
                  "Zink переводит OpenGL на Vulkan. На Windows он экспериментальный: часть игр покажет артефакты или "
                  "не запустится — тогда верните DirectX 12. Переключить все игры с Mesa на Zink? Проверьте результат "
                  "кнопкой «Проверить» в строке игры — она покажет, рисует ли {gpu}.",
                  "Zink translates OpenGL to Vulkan. On Windows it is experimental: some games will show artefacts or "
                  "not start — then switch back to DirectX 12. Switch every Mesa game to Zink? Verify with the Check "
                  "button in the game's row — it shows whether the {gpu} renders."),
    "gr.watch": ("Перевіряти, на якій карті малює запущена гра", "Проверять, на какой карте рисует запущенная игра",
                 "Check which card a running game renders on"),
    "gr.watch_d": ("Через 40 секунд після запуску гри зі списку — 5-секундний замір лічильників і драйвера процесу. Якщо "
                   "гра малює на вбудованій, OptimaX попередить.",
                   "Через 40 секунд после запуска игры из списка — 5-секундный замер счётчиков и драйвера процесса. "
                   "Если игра рисует на встроенной, OptimaX предупредит.",
                   "40 seconds after a listed game starts: a 5-second measurement of counters and the process's "
                   "driver. OptimaX warns if the game renders on the integrated GPU."),
    "gr.export": ("Експорт профілів", "Экспорт профилей", "Export profiles"),
    "gr.import": ("Імпорт профілів", "Импорт профилей", "Import profiles"),
    "gr.exported": ("Профілів збережено: {n}", "Профилей сохранено: {n}", "Profiles saved: {n}"),
    "gr.imported": ("Профілів імпортовано: {n}. Режим застосовується, коли ви виберете його для гри.",
                    "Профилей импортировано: {n}. Режим применяется, когда вы выберете его для игры.",
                    "Profiles imported: {n}. A mode is applied when you pick it for a game."),
    "gr.import_bad": ("Файл не схожий на профілі OptimaX ({err})", "Файл не похож на профили OptimaX ({err})",
                      "This file does not look like OptimaX profiles ({err})"),
    "gr.fso_t": ("Вимкнено оптимізації на весь екран", "Отключены оптимизации во весь экран",
                 "Fullscreen optimizations are disabled"),
    "gr.fso_d": ("Так ігри переходять у справжній повноекранний режим, а він можливий лише на карті з монітором — гра "
                 "може перейти з {gpu} на вбудовану. На ПК з майнінговою картою це краще повернути.",
                 "Так игры переходят в настоящий полноэкранный режим, а он возможен только на карте с монитором — игра "
                 "может перейти с {gpu} на встроенную. На ПК с майнинговой картой это лучше вернуть.",
                 "This makes games use exclusive fullscreen, which only works on the card with the monitor — a game "
                 "may move from the {gpu} to the integrated GPU. Better revert it on a mining-card PC."),
    "gr.fso_q": ("Повернути оптимізації на весь екран (як у Windows за замовчуванням)?",
                 "Вернуть оптимизации во весь экран (как в Windows по умолчанию)?",
                 "Restore fullscreen optimizations (the Windows default)?"),
    "gr.fso_btn": ("Повернути", "Вернуть", "Revert"),
    "gr.fso_done": ("Оптимізації на весь екран повернуто", "Оптимизации во весь экран возвращены",
                    "Fullscreen optimizations restored"),
    "gr.dxvk_old": ("У цій версії лише DirectX 9 — завантажте ще раз для DirectX 10 / 11.",
                    "В этой версии только DirectX 9 — загрузите ещё раз для DirectX 10 / 11.",
                    "This version has DirectX 9 only — download again for DirectX 10 / 11."),
    "gr.recommended": ("рекомендовано", "рекомендуется", "recommended"),
    "gr.marked_bad": ("ви позначили «не працює»", "вы отметили «не работает»", "you marked it “not working”"),
    "gr.limited": ("частково недоступний", "частично недоступен", "partly unavailable"),
    "gr.mode_q": ("{game}: режим «{mode}»", "{game}: режим «{mode}»", "{game}: “{mode}” mode"),
    "gr.plan.original": ("Усе, що OptimaX зробила для цієї гри, буде повернуто.",
                         "Всё, что OptimaX сделала для этой игры, будет возвращено.",
                         "Everything OptimaX did for this game will be reverted."),
    "gr.plan.gpu": ("• exe на {gpu} («Висока продуктивність»): {n}", "• exe на {gpu} («Высокая производительность»): {n}",
                    "• exe set to the {gpu} (“High performance”): {n}"),
    "gr.plan.dxvk": ("• DXVK ({arch}) у {folder}: {files}", "• DXVK ({arch}) в {folder}: {files}",
                     "• DXVK ({arch}) in {folder}: {files}"),
    "gr.plan.mesa": ("• Mesa ({arch}, {drv}) у {folder}", "• Mesa ({arch}, {drv}) в {folder}",
                     "• Mesa ({arch}, {drv}) in {folder}"),
    "gr.plan.blocked": ("• {what} — ні: {why}", "• {what} — нет: {why}", "• {what} — no: {why}"),
    "gr.plan.online": ("Онлайн-гра: бібліотеки поруч з exe — на ваш ризик (античит може це не схвалити).",
                       "Онлайн-игра: библиотеки рядом с exe — на ваш риск (античит может это не одобрить).",
                       "Online game: libraries next to the exe are at your own risk (anti-cheat may object)."),
    "gr.plan.backup": ("Файли гри з такими самими назвами збережуться поруч як *.optimax-bak і повернуться під час "
                       "відкату — кнопкою «Оригінал», «Повернути все» або з OptimaX-Rescue.cmd. Системні бібліотеки "
                       "Windows не змінюються.",
                       "Файлы игры с такими же именами сохранятся рядом как *.optimax-bak и вернутся при откате — "
                       "кнопкой «Оригинал», «Вернуть всё» или из OptimaX-Rescue.cmd. Системные библиотеки Windows не "
                       "меняются.",
                       "Game files with the same names are kept next to them as *.optimax-bak and restored on revert — "
                       "with Original, Revert all or OptimaX-Rescue.cmd. Windows system libraries are not changed."),
    "gr.mode_done": ("{game}: режим «{mode}». Перезапустіть гру й натисніть «Перевірити».",
                     "{game}: режим «{mode}». Перезапустите игру и нажмите «Проверить».",
                     "{game}: “{mode}” mode. Restart the game and press Check."),
    "gr.mode_rolled": ("{game}: не вдалося — гру повернуто до попереднього стану", "{game}: не удалось — игра "
                       "возвращена в предыдущее состояние", "{game}: failed — the game was returned to its previous "
                       "state"),
    "gr.check_t": ("{game}: на якій карті малює", "{game}: на какой карте рисует", "{game}: which card renders"),
    "gr.check_run": ("Запустіть «{game}», дочекайтеся меню чи гри (не згортайте) і натисніть «Перевірити» ще раз. "
                     "OptimaX 6 секунд дивиться лічильники Windows і драйвер, який завантажила гра.",
                     "Запустите «{game}», дождитесь меню или игры (не сворачивайте) и нажмите «Проверить» ещё раз. "
                     "OptimaX 6 секунд смотрит счётчики Windows и драйвер, который загрузила игра.",
                     "Start “{game}”, wait for the menu or gameplay (do not minimise) and press Check again. OptimaX "
                     "watches Windows counters and the driver the game loaded for 6 seconds."),
    "gr.checking": ("Перевіряю, на якій карті малює {game}…", "Проверяю, на какой карте рисует {game}…",
                    "Checking which card renders {game}…"),
    "gr.path": ("Як малює: {path}", "Как рисует: {path}", "Render path: {path}"),
    "gr.fix_hint": ("Спробуйте режим «{mode}» (кнопка «Режим»), а для гри Unity / у повноекранному режимі — "
                    "вікно без рамки в налаштуваннях гри.",
                    "Попробуйте режим «{mode}» (кнопка «Режим»), а для игры Unity / в полноэкранном режиме — окно "
                    "без рамки в настройках игры.",
                    "Try the “{mode}” mode (Mode button); for Unity games or exclusive fullscreen — borderless window "
                    "in the game's settings."),
    "gr.rate_ok": ("Працює в режимі «{mode}»", "Работает в режиме «{mode}»", "Works in “{mode}” mode"),
    "gr.rate_bad": ("Не працює в режимі «{mode}»", "Не работает в режиме «{mode}»", "Doesn't work in “{mode}” mode"),
    "gr.rated": ("Збережено в базі сумісності", "Сохранено в базе совместимости", "Saved to the compatibility database"),
    "gr.back_q": ("Повернути «{game}» до режиму «{mode}»?", "Вернуть «{game}» к режиму «{mode}»?",
                  "Return “{game}” to the “{mode}” mode?"),
    "gr.params": ("Параметри запуску: {p} (скопіювати)", "Параметры запуска: {p} (скопировать)",
                  "Launch options: {p} (copy)"),
    "gr.params_copied": ("Скопійовано: {p} — вставте в параметри запуску гри (Steam → Властивості)",
                         "Скопировано: {p} — вставьте в параметры запуска игры (Steam → Свойства)",
                         "Copied: {p} — paste into the game's launch options (Steam → Properties)"),
    "gr.reset": ("Видалити профіль (оригінал)", "Удалить профиль (оригинал)", "Remove profile (original)"),
    "gr.reset_q": ("Повернути все, що OptimaX зробила для «{game}» (DXVK, Mesa, призначення exe), і видалити її "
                   "профіль та результати перевірок?",
                   "Вернуть всё, что OptimaX сделала для «{game}» (DXVK, Mesa, назначение exe), и удалить её профиль и "
                   "результаты проверок?",
                   "Revert everything OptimaX did for “{game}” (DXVK, Mesa, exe assignment) and delete its profile and "
                   "check results?"),

    # ── база сумісності ──
    "db.note.source": ("Source (DirectX 9): на майнінговій карті — лише через DXVK.",
                       "Source (DirectX 9): на майнинговой карте — только через DXVK.",
                       "Source (DirectX 9): only via DXVK on a mining card."),
    "db.note.vac": ("VAC: про блокування за DXVK не відомо, але це не гарантія — в онлайні на ваш ризик.",
                    "VAC: о блокировках за DXVK не известно, но это не гарантия — в онлайне на ваш риск.",
                    "VAC: no known bans for DXVK, but there is no guarantee — online at your own risk."),
    "db.note.cs2_vulkan": ("Має власний Vulkan (параметр -vulkan) — без жодних бібліотек.",
                           "Имеет собственный Vulkan (параметр -vulkan) — без библиотек.",
                           "Has its own Vulkan renderer (-vulkan) — no libraries needed."),
    "db.note.goldsrc": ("GoldSrc (OpenGL, x86): на майнінговій карті — лише через Mesa.",
                        "GoldSrc (OpenGL, x86): на майнинговой карте — только через Mesa.",
                        "GoldSrc (OpenGL, x86): only via Mesa on a mining card."),
    "db.note.dx8": ("DirectX 8 — DXVK перекладає його через d3d8.dll.", "DirectX 8 — DXVK переводит его через d3d8.dll.",
                    "DirectX 8 — DXVK translates it via d3d8.dll."),
    "db.note.gta4": ("DirectX 9 — з DXVK зазвичай ще й рівніші кадри.", "DirectX 9 — с DXVK обычно ещё и ровнее кадры.",
                     "DirectX 9 — usually smoother frame pacing with DXVK."),
    "db.note.anticheat_online": ("Онлайн з античитом: лише «Напряму на карту», без бібліотек.",
                                 "Онлайн с античитом: только «Напрямую на карту», без библиотек.",
                                 "Online with anti-cheat: Native GPU only, no libraries."),
    "db.note.unity": ("Unity: у справжньому повноекранному режимі може малювати карта з монітором — ставте вікно без "
                      "рамки (параметр -window-mode borderless).",
                      "Unity: в настоящем полноэкранном режиме может рисовать карта с монитором — ставьте окно без "
                      "рамки (параметр -window-mode borderless).",
                      "Unity: in exclusive fullscreen the card with the monitor may render — use borderless window "
                      "(-window-mode borderless)."),
    "db.note.java": ("Java (Minecraft): Mesa поруч з javaw.exe змінила б усі програми цієї Java — OptimaX цього не "
                     "робить.",
                     "Java (Minecraft): Mesa рядом с javaw.exe изменила бы все программы этой Java — OptimaX этого не "
                     "делает.",
                     "Java (Minecraft): Mesa next to javaw.exe would change every app on that Java — OptimaX doesn't "
                     "do it."),

    # ── «Чому лагає?»: нові висновки ──
    "fix.mining": ("Змінити режим", "Сменить режим", "Change mode"),
    "diag.f.render_igpu.t": ("{game} малює не на {gpu}", "{game} рисует не на {gpu}", "{game} is not rendering on the {gpu}"),
    "diag.f.render_igpu.d": ("Вимір показав: 3D-роботу гри виконує вбудована графіка ({path}). Найчастіше — справжній "
                             "повноекранний режим: поставте вікно без рамки або режим DXVK для гри.",
                             "Замер показал: 3D-работу игры выполняет встроенная графика ({path}). Чаще всего — "
                             "настоящий полноэкранный режим: поставьте окно без рамки или режим DXVK для игры.",
                             "Measured: the integrated GPU does the game's 3D work ({path}). Usually exclusive "
                             "fullscreen: use a borderless window or the DXVK mode for the game."),
    "diag.f.render_igpu_dx9.t": ("{game} (DirectX 9) малює не на {gpu}", "{game} (DirectX 9) рисует не на {gpu}",
                                 "{game} (DirectX 9) is not rendering on the {gpu}"),
    "diag.f.render_igpu_dx9.d": ("DirectX 9 бачить лише карту з монітором ({path}). Увімкніть для гри режим «Авто» або "
                                 "«DXVK» — тоді малюватиме {gpu}.",
                                 "DirectX 9 видит только карту с монитором ({path}). Включите для игры режим «Авто» "
                                 "или «DXVK» — тогда будет рисовать {gpu}.",
                                 "DirectX 9 only sees the card with the monitor ({path}). Set the game to Auto or DXVK "
                                 "mode — then the {gpu} renders."),
    "diag.f.render_igpu_gl.t": ("{game} (OpenGL) малює не на {gpu}", "{game} (OpenGL) рисует не на {gpu}",
                                "{game} (OpenGL) is not rendering on the {gpu}"),
    "diag.f.render_igpu_gl.d": ("OpenGL бачить лише карту з монітором ({path}). Увімкніть для гри режим «Авто» або "
                                "«OpenGL через Mesa».",
                                "OpenGL видит только карту с монитором ({path}). Включите для игры режим «Авто» или "
                                "«OpenGL через Mesa».",
                                "OpenGL only sees the card with the monitor ({path}). Set the game to Auto or OpenGL "
                                "translation mode."),
    "diag.f.render_warp.t": ("{game} малює процесором (WARP)", "{game} рисует процессором (WARP)",
                             "{game} renders on the CPU (WARP)"),
    "diag.f.render_warp.d": ("Гра використала програмний Microsoft Basic Render ({path}): драйвер {gpu} не дав їй "
                             "пристрою. Перевірте драйвер у розділі «Ігри» → Universal GPU Renderer.",
                             "Игра использовала программный Microsoft Basic Render ({path}): драйвер {gpu} не дал ей "
                             "устройства. Проверьте драйвер в разделе «Игры» → Universal GPU Renderer.",
                             "The game used the software Microsoft Basic Render ({path}): the {gpu} driver gave it no "
                             "device. Check the driver under Games → Universal GPU Renderer."),
    "diag.f.render_ok.t": ("Малює {gpu}", "Рисует {gpu}", "The {gpu} renders"),
    "diag.f.render_ok.d": ("Підтверджено виміром: 3D {d3}% на майнінговій карті · {path}.",
                           "Подтверждено замером: 3D {d3}% на майнинговой карте · {path}.",
                           "Confirmed by measurement: 3D {d3}% on the mining card · {path}."),
    "diag.f.vram_full.t": ("Відеопам'ять заповнена: {used} з {total} ГБ", "Видеопамять заполнена: {used} из {total} ГБ",
                           "VRAM is full: {used} of {total} GB"),
    "diag.f.vram_full.d": ("Коли пам'яті карти забракне, частина текстур піде в оперативну, і кожне звернення до неї — "
                           "через PCIe. Знизьте якість текстур або роздільність.",
                           "Когда памяти карты не хватит, часть текстур уйдёт в оперативную, и каждое обращение к ней "
                           "— через PCIe. Снизьте качество текстур или разрешение.",
                           "When the card runs out of memory, textures spill to system RAM and every access goes over "
                           "PCIe. Lower texture quality or resolution."),
    "diag.f.vram_spill.t": ("Гра вийшла за межі відеопам'яті: {mb} МБ у спільній пам'яті",
                            "Игра вышла за пределы видеопамяти: {mb} МБ в общей памяти",
                            "The game spilled out of VRAM: {mb} MB in shared memory"),
    "diag.f.vram_spill.d": ("Ресурси гри лежать в оперативній пам'яті й читаються через PCIe — звідси фризи. Знизьте "
                            "якість текстур на крок.",
                            "Ресурсы игры лежат в оперативной памяти и читаются через PCIe — отсюда фризы. Снизьте "
                            "качество текстур на шаг.",
                            "Game resources live in system RAM and are read over PCIe — hence the stutter. Lower "
                            "texture quality by one step."),
    "diag.f.ram_shared.t": ("Мало вільної RAM, а гра тримає {mb} МБ у спільній пам'яті",
                            "Мало свободной RAM, а игра держит {mb} МБ в общей памяти",
                            "Low free RAM while the game keeps {mb} MB in shared memory"),
    "diag.f.ram_shared.d": ("Вільно лише {free} ГБ: спільна пам'ять відеокарти теж займає оперативну. Закрийте фонові "
                            "програми або знизьте текстури.",
                            "Свободно лишь {free} ГБ: общая память видеокарты тоже занимает оперативную. Закройте "
                            "фоновые программы или снизьте текстуры.",
                            "Only {free} GB free: the GPU's shared memory also takes system RAM. Close background apps or "
                            "lower textures."),
    "diag.f.pcie_narrow.t": ("PCIe під навантаженням x{cur} замість x{max}", "PCIe под нагрузкой x{cur} вместо x{max}",
                             "PCIe under load is x{cur} instead of x{max}"),
    "diag.f.pcie_narrow.d": ("Карта стоїть у слоті з меншою кількістю ліній (або через райзер). Переставте її в "
                             "основний слот x16.",
                             "Карта стоит в слоте с меньшим числом линий (или через райзер). Переставьте её в основной "
                             "слот x16.",
                             "The card sits in a slot with fewer lanes (or on a riser). Move it to the main x16 slot."),
    "diag.f.pcie_slow.t": ("PCIe під навантаженням {cur}.0 замість {max}.0", "PCIe под нагрузкой {cur}.0 вместо {max}.0",
                           "PCIe under load is gen {cur} instead of gen {max}"),
    "diag.f.pcie_slow.d": ("Лінія працює на нижчому поколінні, ніж підтримує карта: перевірте налаштування PCIe у BIOS "
                           "і райзер.",
                           "Линия работает на поколении ниже, чем поддерживает карта: проверьте настройки PCIe в BIOS и "
                           "райзер.",
                           "The link runs below the card's generation: check PCIe settings in BIOS and any riser."),
    "diag.f.pcie_full.t": ("PCIe завантажено на {share}%", "PCIe загружен на {share}%", "PCIe is {share}% busy"),
    "diag.f.pcie_full.d": ("{mbps} з ~{link} МБ/с (PCIe {gen}.0 x{width}). Через цю лінію йдуть і текстури, і готові "
                           "кадри на вбудовану графіку з монітором. Обмеження FPS або нижча роздільність зменшать "
                           "трафік.",
                           "{mbps} из ~{link} МБ/с (PCIe {gen}.0 x{width}). Через эту линию идут и текстуры, и готовые "
                           "кадры на встроенную графику с монитором. Ограничение FPS или меньшее разрешение уменьшат "
                           "трафик.",
                           "{mbps} of ~{link} MB/s (PCIe {gen}.0 x{width}). Both textures and finished frames for the "
                           "integrated GPU with the monitor go over this link. An FPS cap or lower resolution reduces "
                           "the traffic."),
    "diag.f.pcie_copy.t": ("Кадри на монітор займають ~{mbps} МБ/с лінії PCIe", "Кадры на монитор занимают ~{mbps} МБ/с "
                           "линии PCIe", "Frames to the monitor take ~{mbps} MB/s of PCIe"),
    "diag.f.pcie_copy.d": ("Монітор підключено до вбудованої графіки, тож кожен із {fps} кадрів на секунду копіюється "
                           "через PCIe (~{link} МБ/с усього). Обмеження FPS до частоти монітора звільнить лінію.",
                           "Монитор подключён к встроенной графике, поэтому каждый из {fps} кадров в секунду копируется "
                           "через PCIe (~{link} МБ/с всего). Ограничение FPS до частоты монитора освободит линию.",
                           "The monitor is on the integrated GPU, so each of the {fps} frames per second is copied over "
                           "PCIe (~{link} MB/s total). Capping FPS at the refresh rate frees the link."),
    "diag.f.stutter_ram.t": ("Фризи: {pm} на хвилину — нестача оперативної пам'яті",
                             "Фризы: {pm} в минуту — нехватка оперативной памяти",
                             "Stutter: {pm} per minute — out of RAM"),
    "diag.f.stutter_ram.d": ("Більшість фризів ({n}) збігаються з підкачкою з диска. Закрийте фонові програми; 1% low — "
                             "{low} FPS при середніх {avg}.",
                             "Большинство фризов ({n}) совпадают с подкачкой с диска. Закройте фоновые программы; 1% "
                             "low — {low} FPS при средних {avg}.",
                             "Most stutters ({n}) coincide with paging from disk. Close background apps; 1% low is {low} "
                             "FPS at {avg} average."),
    "diag.f.stutter_disk.t": ("Фризи: {pm} на хвилину — диск", "Фризы: {pm} в минуту — диск",
                              "Stutter: {pm} per minute — disk"),
    "diag.f.stutter_disk.d": ("Фризи ({n}) збігаються з повним завантаженням диска: гра довантажує дані. Гра на SSD "
                              "допоможе; 1% low — {low} FPS при середніх {avg}.",
                              "Фризы ({n}) совпадают с полной загрузкой диска: игра подгружает данные. Игра на SSD "
                              "поможет; 1% low — {low} FPS при средних {avg}.",
                              "Stutters ({n}) coincide with the disk at 100%: the game streams data. An SSD helps; 1% "
                              "low is {low} FPS at {avg} average."),
    "diag.f.stutter_vram.t": ("Фризи: {pm} на хвилину — відеопам'ять", "Фризы: {pm} в минуту — видеопамять",
                              "Stutter: {pm} per minute — VRAM"),
    "diag.f.stutter_vram.d": ("Фризи ({n}) збігаються з переїздом ресурсів у спільну пам'ять. Знизьте якість текстур; "
                              "1% low — {low} FPS при середніх {avg}.",
                              "Фризы ({n}) совпадают с переездом ресурсов в общую память. Снизьте качество текстур; 1% "
                              "low — {low} FPS при средних {avg}.",
                              "Stutters ({n}) coincide with resources moving to shared memory. Lower texture quality; 1% "
                              "low is {low} FPS at {avg} average."),
    "diag.f.stutter_cpu.t": ("Фризи: {pm} на хвилину — процесор", "Фризы: {pm} в минуту — процессор",
                             "Stutter: {pm} per minute — CPU"),
    "diag.f.stutter_cpu.d": ("Фризи ({n}) збігаються з ядром на 97%+. Балансувальник фону й закриття фонових програм "
                             "допоможуть; 1% low — {low} FPS при середніх {avg}.",
                             "Фризы ({n}) совпадают с ядром на 97%+. Балансировщик фона и закрытие фоновых программ "
                             "помогут; 1% low — {low} FPS при средних {avg}.",
                             "Stutters ({n}) coincide with a core at 97%+. The background balancer and closing apps help; "
                             "1% low is {low} FPS at {avg} average."),
    "diag.f.stutter_shader.t": ("Фризи: {pm} на хвилину — компіляція шейдерів", "Фризы: {pm} в минуту — компиляция "
                                "шейдеров", "Stutter: {pm} per minute — shader compilation"),
    "diag.f.stutter_shader.d": ("Фризи ({n}) на початку гри без навантаження на систему — так гра (або DXVK) компілює "
                                "шейдери. Вони зникнуть після кількох хвилин гри; кеш шейдерів не очищайте без потреби.",
                                "Фризы ({n}) в начале игры без нагрузки на систему — так игра (или DXVK) компилирует "
                                "шейдеры. Они исчезнут после нескольких минут игры; кэш шейдеров не очищайте без "
                                "нужды.",
                                "Stutters ({n}) early in the game without system load — the game (or DXVK) is compiling "
                                "shaders. They go away after a few minutes; don't clear the shader cache needlessly."),
    "diag.f.stutter_other.t": ("Фризи: {pm} на хвилину", "Фризы: {pm} в минуту", "Stutter: {pm} per minute"),
    "diag.f.stutter_other.d": ("Фризів {n}, але жоден показник системи в ті секунди не був на межі: ймовірно, сама гра "
                               "(довантаження рівня, мережа). 1% low — {low} FPS при середніх {avg}.",
                               "Фризов {n}, но ни один показатель системы в те секунды не был на пределе: вероятно, "
                               "сама игра (подгрузка уровня, сеть). 1% low — {low} FPS при средних {avg}.",
                               "{n} stutters, but no system metric was maxed out at those moments: likely the game "
                               "itself (level streaming, network). 1% low is {low} FPS at {avg} average."),
    "diag.f.gd_no_dxgi.t": ("DirectX не бачить {model}", "DirectX не видит {model}", "DirectX does not see the {model}"),
    "diag.f.gd_no_dxgi.d": ("Ігри не зможуть на ній малювати. Найчастіше — стандартний драйвер NVIDIA вимкнув 3D: "
                            "потрібен пропатчений драйвер для майнінгових карт.",
                            "Игры не смогут на ней рисовать. Чаще всего — стандартный драйвер NVIDIA отключил 3D: нужен "
                            "пропатченный драйвер для майнинговых карт.",
                            "Games cannot render on it. Usually the stock NVIDIA driver disabled 3D: a patched driver "
                            "for mining cards is needed."),
    "diag.f.gd_no_vulkan.t": ("Vulkan на {model} не знайдено", "Vulkan на {model} не найден", "No Vulkan on the {model}"),
    "diag.f.gd_no_vulkan.d": ("DXVK (DirectX 9 → Vulkan) і Zink без Vulkan не працюють. Перевстановіть пропатчений "
                              "драйвер з Vulkan.",
                              "DXVK (DirectX 9 → Vulkan) и Zink без Vulkan не работают. Переустановите пропатченный "
                              "драйвер с Vulkan.",
                              "DXVK (DirectX 9 → Vulkan) and Zink need Vulkan. Reinstall a patched driver with Vulkan."),
    "diag.f.gd_no_dx12.t": ("{model} не підтримала DirectX 12", "{model} не поддержала DirectX 12",
                            "The {model} did not accept DirectX 12"),
    "diag.f.gd_no_dx12.d": ("Ігри DirectX 12 і Mesa d3d12 на ній не запустяться; для OpenGL лишається Zink.",
                            "Игры DirectX 12 и Mesa d3d12 на ней не запустятся; для OpenGL остаётся Zink.",
                            "DirectX 12 games and Mesa d3d12 will not run on it; Zink remains for OpenGL."),
    "diag.f.gd_igpu_basic.t": ("Вбудована графіка без драйвера ({name})", "Встроенная графика без драйвера ({name})",
                               "Integrated GPU has no driver ({name})"),
    "diag.f.gd_igpu_basic.d": ("Монітор підключено до вбудованої, а на ній стандартний драйвер Microsoft: кадри з "
                               "майнінгової карти виводяться повільно. Встановіть драйвер Intel / AMD для вбудованої.",
                               "Монитор подключён к встроенной, а на ней стандартный драйвер Microsoft: кадры с "
                               "майнинговой карты выводятся медленно. Установите драйвер Intel / AMD для встроенной.",
                               "The monitor is on the integrated GPU, which runs the basic Microsoft driver: frames from "
                               "the mining card are shown slowly. Install the Intel / AMD driver for it."),
    "diag.f.gd_vram_small.t": ("{model}: DirectX бачить лише {mb} МБ відеопам'яті",
                               "{model}: DirectX видит лишь {mb} МБ видеопамяти",
                               "{model}: DirectX sees only {mb} MB of VRAM"),
    "diag.f.gd_vram_small.d": ("У P106-100 — 6 ГБ. Можливо, це інша модифікація карти або драйвер працює неправильно.",
                               "У P106-100 — 6 ГБ. Возможно, это другая модификация карты или драйвер работает "
                               "неправильно.",
                               "A P106-100 has 6 GB. It may be another variant of the card, or the driver misbehaves."),

    # ── P106 Driver Analyzer ──
    "gd.pci.t": ("{model}: визначено за ідентифікатором PCI", "{model}: определена по идентификатору PCI",
                 "{model}: identified by PCI ID"),
    "gd.pci.d": ("", "", ""),
    "gd.pci_name.t": ("{model} (за PCI ID) — драйвер називає її «{name}»", "{model} (по PCI ID) — драйвер называет её "
                      "«{name}»", "{model} (by PCI ID) — the driver calls it “{name}”"),
    "gd.pci_name.d": ("Так працюють пропатчені драйвери для майнінгових карт — це нормально. OptimaX орієнтується на "
                      "PCI ID, а не на назву.",
                      "Так работают пропатченные драйверы для майнинговых карт — это нормально. OptimaX ориентируется "
                      "на PCI ID, а не на название.",
                      "That is how patched drivers for mining cards work — it's fine. OptimaX goes by the PCI ID, not "
                      "the name."),
    "gd.no_dxgi.t": ("DirectX не бачить {model}", "DirectX не видит {model}", "DirectX does not see the {model}"),
    "gd.no_dxgi.d": ("Без пропатченого драйвера 3D на майнінговій карті вимкнено — ігри не зможуть на ній малювати. "
                     "Драйвер з nvidia.com не встановлюйте: він вимикає 3D.",
                     "Без пропатченного драйвера 3D на майнинговой карте отключено — игры не смогут на ней рисовать. "
                     "Драйвер с nvidia.com не ставьте: он отключает 3D.",
                     "Without a patched driver 3D is disabled on a mining card — games cannot render on it. Don't "
                     "install the nvidia.com driver: it disables 3D."),
    "gd.dx12.t": ("DirectX 12: так", "DirectX 12: да", "DirectX 12: yes"),
    "gd.dx12.d": ("", "", ""),
    "gd.no_dx12.t": ("DirectX 12 на карті не створюється", "DirectX 12 на карте не создаётся",
                     "DirectX 12 cannot be created on the card"),
    "gd.no_dx12.d": ("Ігри DirectX 12 і Mesa d3d12 не працюватимуть; для OpenGL виберіть Zink.",
                     "Игры DirectX 12 и Mesa d3d12 не будут работать; для OpenGL выберите Zink.",
                     "DirectX 12 games and Mesa d3d12 won't work; choose Zink for OpenGL."),
    "gd.vulkan.t": ("Vulkan {api}, драйвер {driver}", "Vulkan {api}, драйвер {driver}", "Vulkan {api}, driver {driver}"),
    "gd.vulkan.d": ("", "", ""),
    "gd.no_vulkan.t": ("Vulkan на майнінговій карті не знайдено", "Vulkan на майнинговой карте не найден",
                       "No Vulkan on the mining card"),
    "gd.no_vulkan.d": ("DXVK і Zink без нього не працюють — режими DXVK і Zink недоступні. Перевстановіть драйвер з "
                       "Vulkan.",
                       "DXVK и Zink без него не работают — режимы DXVK и Zink недоступны. Переустановите драйвер с "
                       "Vulkan.",
                       "DXVK and Zink need it — those modes are unavailable. Reinstall a driver with Vulkan."),
    "gd.vram_small.t": ("DirectX бачить лише {mb} МБ відеопам'яті", "DirectX видит лишь {mb} МБ видеопамяти",
                        "DirectX sees only {mb} MB of VRAM"),
    "gd.vram_small.d": ("У P106-100 — 6 ГБ.", "У P106-100 — 6 ГБ.", "A P106-100 has 6 GB."),
    "gd.igpu_basic.t": ("Вбудована графіка без драйвера ({name})", "Встроенная графика без драйвера ({name})",
                        "Integrated GPU without a driver ({name})"),
    "gd.igpu_basic.d": ("Монітор на вбудованій, а драйвер — стандартний Microsoft: кадри виводяться повільно. "
                        "Встановіть драйвер Intel / AMD.",
                        "Монитор на встроенной, а драйвер — стандартный Microsoft: кадры выводятся медленно. "
                        "Установите драйвер Intel / AMD.",
                        "The monitor is on the integrated GPU running the basic Microsoft driver: frames are shown "
                        "slowly. Install the Intel / AMD driver."),
    "gd.display.t": ("Монітор: {name}", "Монитор: {name}", "Monitor: {name}"),
    "gd.display.d": ("", "", ""),
    "gd.no_display.t": ("Карту з монітором DirectX не знайшов", "Карту с монитором DirectX не нашёл",
                        "DirectX found no adapter with a monitor"),
    "gd.no_display.d": ("Так буває з віддаленим робочим столом або без драйвера вбудованої графіки.",
                        "Так бывает с удалённым рабочим столом или без драйвера встроенной графики.",
                        "This happens with Remote Desktop or without an integrated GPU driver."),
    "gd.multi_nv.t": ("Карт NVIDIA: {n}", "Карт NVIDIA: {n}", "NVIDIA cards: {n}"),
    "gd.multi_nv.d": ("Майнінговою вважається та, що без виходів.", "Майнинговой считается та, что без выходов.",
                      "The one without outputs is treated as the mining card."),
    "gd.probe_err.t": ("Перевірка DirectX / Vulkan завершилася з помилкою", "Проверка DirectX / Vulkan завершилась с "
                       "ошибкой", "The DirectX / Vulkan check failed"),
    "gd.probe_err.d": ("{err} — якщо повторюється, драйвер працює нестабільно.", "{err} — если повторяется, драйвер "
                       "работает нестабильно.", "{err} — if it repeats, the driver is unstable."),
    "gd.title": ("Аналізатор карти: PCIe і пам'ять", "Анализатор карты: PCIe и память", "Card analyzer: PCIe and memory"),
    "gd.sub": ("Запустіть гру й натисніть «Виміряти»: 10 секунд показників NVIDIA — лінія PCIe під навантаженням, "
               "відеопам'ять, температура, частота й споживання.",
               "Запустите игру и нажмите «Измерить»: 10 секунд показателей NVIDIA — линия PCIe под нагрузкой, "
               "видеопамять, температура, частота и потребление.",
               "Start a game and press Measure: 10 seconds of NVIDIA metrics — PCIe link under load, VRAM, temperature, "
               "clock and power."),
    "gd.measure": ("Виміряти", "Измерить", "Measure"),
    "gd.measuring": ("Вимірюю… {s} с", "Измеряю… {s} с", "Measuring… {s} s"),
    "gd.no_nvml": ("Показники NVIDIA (NVML) недоступні: драйвер без nvml.dll.", "Показатели NVIDIA (NVML) недоступны: "
                   "драйвер без nvml.dll.", "NVIDIA metrics (NVML) are unavailable: the driver has no nvml.dll."),
    "gd.pcie_t": ("Лінія PCIe", "Линия PCIe", "PCIe link"),
    "gd.pcie_d": ("Під навантаженням: PCIe {gen}.0 x{width} (карта вміє {mgen}.0 x{mwidth}). Трафік ~{mbps} з ~{link} "
                  "МБ/с ({share}%).",
                  "Под нагрузкой: PCIe {gen}.0 x{width} (карта умеет {mgen}.0 x{mwidth}). Трафик ~{mbps} из ~{link} "
                  "МБ/с ({share}%).",
                  "Under load: PCIe gen {gen} x{width} (the card supports gen {mgen} x{mwidth}). Traffic ~{mbps} of "
                  "~{link} MB/s ({share}%)."),
    "gd.pcie_idle": ("Зараз PCIe {gen}.0 x{width} (карта вміє {mgen}.0 x{mwidth}). У простої карта знижує покоління — "
                     "для висновку запустіть гру й виміряйте ще раз.",
                     "Сейчас PCIe {gen}.0 x{width} (карта умеет {mgen}.0 x{mwidth}). В простое карта снижает поколение "
                     "— для вывода запустите игру и измерьте ещё раз.",
                     "Now PCIe gen {gen} x{width} (the card supports gen {mgen} x{mwidth}). Idle cards drop the "
                     "generation — start a game and measure again."),
    "gd.mem_t": ("Відеопам'ять і датчики", "Видеопамять и датчики", "VRAM and sensors"),
    "gd.mem_d": ("{used} з {total} ГБ · {temp} °C · {clock} МГц · {power} Вт", "{used} из {total} ГБ · {temp} °C · "
                 "{clock} МГц · {power} Вт", "{used} of {total} GB · {temp} °C · {clock} MHz · {power} W"),

    # ── Shader Cache Manager ──
    "sc.title": ("Кеш шейдерів", "Кэш шейдеров", "Shader cache"),
    "sc.wait": ("Рахую…", "Считаю…", "Counting…"),
    "sc.summary": ("{mb} МБ у {n} папках (DirectX, NVIDIA, Intel, AMD, Mesa).", "{mb} МБ в {n} папках (DirectX, "
                   "NVIDIA, Intel, AMD, Mesa).", "{mb} MB in {n} folders (DirectX, NVIDIA, Intel, AMD, Mesa)."),
    "sc.clear": ("Очистити з резервною копією", "Очистить с резервной копией", "Clear with backup"),
    "sc.restore": ("Відновити копію", "Восстановить копию", "Restore backup"),
    "sc.backup": ("Резервна копія від {when}, {mb} МБ", "Резервная копия от {when}, {mb} МБ", "Backup from {when}, {mb} MB"),
    "sc.clear_q": ("Кеш перенесеться в резервну копію (одну, останню), і драйвер створить його заново: перші запуски "
                   "ігор будуть із фризами компіляції. Файли, зайняті запущеною грою, лишаться. Очищати варто, лише "
                   "якщо кеш пошкоджений або гра показує артефакти після оновлення драйвера.",
                   "Кэш перенесётся в резервную копию (одну, последнюю), и драйвер создаст его заново: первые запуски "
                   "игр будут с фризами компиляции. Файлы, занятые запущенной игрой, останутся. Очищать стоит, только "
                   "если кэш повреждён или игра показывает артефакты после обновления драйвера.",
                   "The cache moves into a backup (one, the latest) and the driver rebuilds it: the first game launches "
                   "will stutter while compiling. Files held by a running game stay. Clear it only if the cache is "
                   "damaged or a game shows artefacts after a driver update."),
    "sc.restore_q": ("Повернути кеш із резервної копії? Файли, які драйвер уже створив заново, не перезаписуються.",
                     "Вернуть кэш из резервной копии? Файлы, которые драйвер уже создал заново, не перезаписываются.",
                     "Restore the cache from the backup? Files the driver has already rebuilt are not overwritten."),
    "sc.cleared": ("Кеш шейдерів у резервній копії: {n} файлів, {mb} МБ (зайнятих пропущено: {skipped}).",
                   "Кэш шейдеров в резервной копии: {n} файлов, {mb} МБ (занятых пропущено: {skipped}).",
                   "Shader cache backed up: {n} files, {mb} MB (skipped in use: {skipped})."),
    "sc.restored": ("Відновлено файлів: {n} (новіших не чіпали: {kept}).", "Восстановлено файлов: {n} (более новые не "
                    "трогали: {kept}).", "Restored files: {n} (newer ones kept: {kept})."),
    "sc.a.damaged.t": ("Порожніх файлів у кеші: {n}", "Пустых файлов в кэше: {n}", "Empty files in the cache: {n}"),
    "sc.a.damaged.d": ("Так буває після аварійного завершення гри чи драйвера. Якщо гра показує артефакти або вилітає "
                       "на завантаженні — очистіть кеш (з резервною копією).",
                       "Так бывает после аварийного завершения игры или драйвера. Если игра показывает артефакты или "
                       "вылетает на загрузке — очистите кэш (с резервной копией).",
                       "This happens after a game or driver crash. If a game shows artefacts or crashes while loading, "
                       "clear the cache (with backup)."),
    "sc.a.driver.t": ("Драйвер оновлено: {old} → {new}", "Драйвер обновлён: {old} → {new}",
                      "Driver updated: {old} → {new}"),
    "sc.a.driver.d": ("Перші запуски ігор після оновлення — з фризами: шейдери компілюються заново. Це мине саме; "
                      "очищення кешу тут не допомагає.",
                      "Первые запуски игр после обновления — с фризами: шейдеры компилируются заново. Это пройдёт само; "
                      "очистка кэша тут не помогает.",
                      "The first game launches after an update stutter while shaders recompile. It passes by itself; "
                      "clearing the cache does not help here."),
    "sc.a.huge.t": ("Кеш великий: {gb} ГБ", "Кэш большой: {gb} ГБ", "The cache is large: {gb} GB"),
    "sc.a.huge.d": ("Це не шкодить продуктивності; очищайте, лише якщо бракує місця.", "Это не вредит "
                    "производительности; очищайте, только если не хватает места.",
                    "It doesn't hurt performance; clear it only if you need the space."),
    "sc.a.fine.t": ("Кеш у порядку ({mb} МБ)", "Кэш в порядке ({mb} МБ)", "The cache looks fine ({mb} MB)"),
    "sc.a.fine.d": ("Очищати не потрібно: з кешем ігри завантажуються швидше й з меншими фризами.",
                    "Очищать не нужно: с кэшем игры загружаются быстрее и с меньшими фризами.",
                    "No need to clear it: with the cache games load faster and stutter less."),
    "hint.shaders.t": ("Фризи компіляції шейдерів", "Фризы компиляции шейдеров", "Shader compilation stutter"),
    "hint.shaders.d": ("Перші хвилини гри (або після оновлення драйвера чи гри) кадри можуть смикатися: шейдери "
                       "компілюються. Пограйте кілька хвилин — далі кадри з кешу. Не очищайте кеш шейдерів без потреби; "
                       "у Steam залиште ввімкненим «Попереднє кешування шейдерів».",
                       "Первые минуты игры (или после обновления драйвера или игры) кадры могут дёргаться: шейдеры "
                       "компилируются. Поиграйте несколько минут — дальше кадры из кэша. Не очищайте кэш шейдеров без "
                       "нужды; в Steam оставьте включённым «Предварительное кэширование шейдеров».",
                       "In the first minutes of a game (or after a driver or game update) frames may hitch while shaders "
                       "compile. Play a few minutes — then they come from the cache. Don't clear the shader cache "
                       "needlessly; keep Steam's “Shader Pre-Caching” on."),

    # ── Game Booster 2.0 ──
    "g.profile": ("Профіль:", "Профиль:", "Profile:"),
    "g.prof.custom": ("Свій", "Свой", "Custom"),
    "g.prof.latency": ("Мінімальна затримка", "Минимальная задержка", "Lowest latency"),
    "g.prof.stable": ("Стабільний frametime", "Стабильный frametime", "Stable frametime"),
    "g.prof.tip": ("Мінімальна затримка — усі перемикачі й високий пріоритет гри на час режиму. Стабільний frametime — "
                   "без закриття фонових програм і без зміни пріоритету. Свій — перемикачі вище.",
                   "Минимальная задержка — все переключатели и высокий приоритет игры на время режима. Стабильный "
                   "frametime — без закрытия фоновых программ и без смены приоритета. Свой — переключатели выше.",
                   "Lowest latency — every switch plus high game priority while the mode is on. Stable frametime — no "
                   "closing background apps and no priority change. Custom — the switches above."),
    "g.prof.locked": ("Задано профілем «{name}». Змініть перемикач — профіль стане «Свій».",
                      "Задано профилем «{name}». Измените переключатель — профиль станет «Свой».",
                      "Set by the “{name}” profile. Flip a switch to turn it into Custom."),
    "g.prof_set": ("Профіль режиму гри: {name}", "Профиль режима игры: {name}", "Game mode profile: {name}"),
    "g.prio_high": ("  · високий пріоритет процесу гри ({n})", "  · высокий приоритет процесса игры ({n})",
                    "  · high priority for the game process ({n})"),
    "g.opt.found": ("Вмикати й для ігор зі Steam, Epic, GOG, Ubisoft", "Включать и для игр из Steam, Epic, GOG, Ubisoft",
                    "Also for games from Steam, Epic, GOG, Ubisoft"),
    "g.opt.found.d": ("Автоматичний режим гри впізнає встановлені ігри без додавання в «Мої ігри» (список оновлюється "
                      "раз на добу).",
                      "Автоматический режим игры узнаёт установленные игры без добавления в «Мои игры» (список "
                      "обновляется раз в сутки).",
                      "Auto game mode recognises installed games without adding them to My games (the list refreshes "
                      "daily)."),
    "games.prof": ("Профіль: {name}", "Профиль: {name}", "Profile: {name}"),
    "games.prof.global": ("як загальний", "как общий", "as global"),
    "games.prof.tip": ("Профіль режиму гри саме для цієї гри: коли режим гри вмикається автоматично через неї.",
                       "Профиль режима игры именно для этой игры: когда режим игры включается автоматически через неё.",
                       "A game-mode profile just for this game: used when game mode turns on automatically for it."),

    # ── блокування твіків ──
    "block.mining_display": ("Не для ПК з майнінговою картою: справжній повноекранний режим можливий лише на карті з "
                             "монітором, тож гра перейшла б на вбудовану графіку.",
                             "Не для ПК с майнинговой картой: настоящий полноэкранный режим возможен только на карте с "
                             "монитором, поэтому игра перешла бы на встроенную графику.",
                             "Not for PCs with a mining card: exclusive fullscreen only works on the card with the "
                             "monitor, so games would move to the integrated GPU."),
    # ── «Чому лагає?»: нові показники й історія ──
    "diag.s.fps": ("FPS (середній)", "FPS (средний)", "FPS (average)"),
    "diag.s.stutter": ("Фризів / хв", "Фризов / мин", "Stutters / min"),
    "diag.s.pcie": ("PCIe під навантаженням", "PCIe под нагрузкой", "PCIe under load"),
    "diag.s.power": ("Споживання GPU", "Потребление GPU", "GPU power"),
    "diag.s.render": ("Малює", "Рисует", "Renders on"),
    "diag.render.mining": ("майнінгова карта", "майнинговая карта", "mining card"),
    "diag.render.igpu": ("вбудована графіка", "встроенная графика", "integrated GPU"),
    "diag.render.warp": ("процесор (WARP)", "процессор (WARP)", "CPU (WARP)"),
    "hist.title": ("Історія замірів", "История замеров", "Measurement history"),
    "hist.note": ("Останні заміри «Чому лагає?»: що обмежувало FPS і на якій карті малювала гра.",
                  "Последние замеры «Почему лагает?»: что ограничивало FPS и на какой карте рисовала игра.",
                  "Recent “Why lag?” runs: what limited FPS and which card rendered the game."),
    "hist.regress": ("{game}: {metric} просіли на {pct}% ({was} → {now}) порівняно з попередніми замірами. Що "
                     "змінилося з того часу — драйвер, оновлення гри, оптимізації?",
                     "{game}: {metric} просели на {pct}% ({was} → {now}) по сравнению с предыдущими замерами. Что "
                     "изменилось с тех пор — драйвер, обновление игры, оптимизации?",
                     "{game}: {metric} dropped {pct}% ({was} → {now}) compared with earlier runs. What changed since — "
                     "driver, game update, optimizations?"),
    "hist.m.avg": ("середній FPS", "средний FPS", "average FPS"),
    "hist.m.low1": ("1% low", "1% low", "1% low"),
    "hist.when": ("Коли", "Когда", "When"),
    "hist.game": ("Гра", "Игра", "Game"),
    "hist.limit": ("Обмеження", "Ограничение", "Limit"),
    "rep.gpu": ("Universal GPU Renderer", "Universal GPU Renderer", "Universal GPU Renderer"),
    "rep.gpu_probe": ("Карта: {gpu}, драйвер {driver}, DirectX 12: {dx12}, Vulkan: {vk}, монітор: {display}",
                      "Карта: {gpu}, драйвер {driver}, DirectX 12: {dx12}, Vulkan: {vk}, монитор: {display}",
                      "Card: {gpu}, driver {driver}, DirectX 12: {dx12}, Vulkan: {vk}, monitor: {display}"),
    "rep.gpu_game": ("{game}: режим «{mode}», перевірка: {verdict}", "{game}: режим «{mode}», проверка: {verdict}",
                     "{game}: “{mode}” mode, check: {verdict}"),
}
