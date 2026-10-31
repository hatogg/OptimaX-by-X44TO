"""Переклади OptimaX 6.6: «Чому впав комп?», бібліотека ігор, простий вигляд, «Що нового», перенесення налаштувань,
монітор на телефоні, звіт про помилку (українська, російська, англійська)."""

STRINGS = {
    # ── «Чому впав комп?» ──
    "crash.title": ("Чому впав комп?", "Почему упал компьютер?", "Why did the PC crash?"),
    "crash.sub": ("Сині екрани й раптові перезавантаження за 30 днів — з журналу Windows, простими словами, з порадами.",
                  "Синие экраны и внезапные перезагрузки за 30 дней — из журнала Windows, простыми словами, с советами.",
                  "Blue screens and sudden restarts in the last 30 days — from the Windows log, in plain words, with "
                  "advice."),
    "crash.check": ("Перевірити", "Проверить", "Check"),
    "crash.memtest": ("Перевірити пам'ять", "Проверить память", "Test memory"),
    "crash.memtest_q": ("Відкриється перевірка пам'яті Windows. Вона працює після перезавантаження (10–20 хвилин), "
                        "тож збережіть роботу. Результат OptimaX покаже тут.",
                        "Откроется проверка памяти Windows. Она работает после перезагрузки (10–20 минут), поэтому "
                        "сохраните работу. Результат OptimaX покажет здесь.",
                        "Windows Memory Diagnostic will open. It runs after a restart (10–20 minutes), so save your "
                        "work. OptimaX shows the result here."),
    "crash.dumps": ("Папка дампів", "Папка дампов", "Dump folder"),
    "crash.head": ("Аварійних перезавантажень за {days} днів: {n} (перевірено {when}).",
                   "Аварийных перезагрузок за {days} дней: {n} (проверено {when}).",
                   "Crash restarts in {days} days: {n} (checked {when})."),
    "crash.none": ("За {days} днів комп не падав", "За {days} дней компьютер не падал",
                   "No crashes in the last {days} days"),
    "crash.t.bsod": ("{when} — синій екран {name}", "{when} — синий экран {name}", "{when} — blue screen {name}"),
    "crash.t.power": ("{when} — раптове вимкнення без синього екрана", "{when} — внезапное выключение без синего экрана",
                      "{when} — sudden shutdown without a blue screen"),
    "crash.t.button": ("{when} — вимкнено кнопкою живлення", "{when} — выключено кнопкой питания",
                       "{when} — turned off with the power button"),
    "crash.cat.gpu": ("Відеодрайвер або відеокарта перестали відповідати.",
                      "Видеодрайвер или видеокарта перестали отвечать.",
                      "The graphics driver or card stopped responding."),
    "crash.cat.memory": ("Помилка пам'яті: оперативна пам'ять, розгін (XMP) або драйвер.",
                         "Ошибка памяти: оперативная память, разгон (XMP) или драйвер.",
                         "A memory error: RAM, overclocking (XMP) or a driver."),
    "crash.cat.driver": ("Помилка драйвера (іноді через нестабільну пам'ять).",
                         "Ошибка драйвера (иногда из-за нестабильной памяти).",
                         "A driver error (sometimes caused by unstable memory)."),
    "crash.cat.hardware": ("Апаратна помилка: процесор, живлення, перегрів або розгін.",
                           "Аппаратная ошибка: процессор, питание, перегрев или разгон.",
                           "A hardware error: CPU, power, overheating or overclocking."),
    "crash.cat.cpu": ("Процесор перестав відповідати — найчастіше розгін або андервольт.",
                      "Процессор перестал отвечать — чаще всего разгон или андервольт.",
                      "The CPU stopped responding — usually an overclock or undervolt."),
    "crash.cat.disk": ("Не вдалося прочитати дані з диска.", "Не удалось прочитать данные с диска.",
                       "Data could not be read from the drive."),
    "crash.cat.power": ("Синього екрана не було: комп вимкнувся сам або завис намертво. Найчастіше — блок живлення, "
                        "перегрів або стрибок напруги.",
                        "Синего экрана не было: компьютер выключился сам или завис намертво. Чаще всего — блок "
                        "питания, перегрев или скачок напряжения.",
                        "No blue screen: the PC turned off by itself or froze solid. Most often the power supply, "
                        "overheating or a power surge."),
    "crash.cat.button": ("Комп завис, і його вимкнули кнопкою.", "Компьютер завис, и его выключили кнопкой.",
                         "The PC froze and was turned off with the button."),
    "crash.cat.system": ("Зупинився важливий системний процес.", "Остановился важный системный процесс.",
                         "A critical system process stopped."),
    "crash.cat.unknown": ("Рідкісний код — допоможе пошук за його назвою.", "Редкий код — поможет поиск по его "
                          "названию.", "A rare code — searching for its name helps."),
    "crash.game": ("У цей час працювала гра {game}.", "В это время работала игра {game}.",
                   "{game} was running at that moment."),
    "crash.a.game_mining": ("Поверніть {game} у режим «Оригінал» (кнопка праворуч) — гра могла впасти на майнінговій "
                            "карті.", "Верните {game} в режим «Оригинал» (кнопка справа) — игра могла упасть на "
                            "майнинговой карте.", "Return {game} to Original mode (button on the right) — the game may "
                            "have crashed on the mining card."),
    "crash.a.gpu_driver": ("Перевстановіть відеодрайвер (для майнінгової карти — пропатчений).",
                           "Переустановите видеодрайвер (для майнинговой карты — пропатченный).",
                           "Reinstall the graphics driver (a patched one for a mining card)."),
    "crash.a.gpu_heat": ("Перевірте температуру відеокарти під навантаженням (Бенчмарки → стрес-тест).",
                         "Проверьте температуру видеокарты под нагрузкой (Бенчмарки → стресс-тест).",
                         "Check GPU temperature under load (Benchmarks → stress test)."),
    "crash.a.gpu_oc": ("Якщо відеокарту розганяли — поверніть заводські частоти.",
                       "Если видеокарту разгоняли — верните заводские частоты.",
                       "If the GPU is overclocked, return it to stock clocks."),
    "crash.a.memtest": ("Перевірте пам'ять (кнопка «Перевірити пам'ять»).",
                        "Проверьте память (кнопка «Проверить память»).", "Test memory (the Test memory button)."),
    "crash.a.xmp": ("Якщо в BIOS увімкнено XMP / розгін пам'яті — спробуйте без нього.",
                    "Если в BIOS включён XMP / разгон памяти — попробуйте без него.",
                    "If XMP / memory overclocking is on in BIOS, try without it."),
    "crash.a.drivers": ("Оновіть драйвери чипсета й відеокарти; згадайте, що встановлювали перед першим збоєм.",
                        "Обновите драйверы чипсета и видеокарты; вспомните, что устанавливали перед первым сбоем.",
                        "Update chipset and graphics drivers; think about what you installed before the first crash."),
    "crash.a.oc_off": ("Скиньте розгін і андервольт процесора (у BIOS — Load Defaults).",
                       "Сбросьте разгон и андервольт процессора (в BIOS — Load Defaults).",
                       "Reset CPU overclock and undervolt (Load Defaults in BIOS)."),
    "crash.a.heat": ("Перевірте охолодження: пил, термопасту, вентилятори.",
                     "Проверьте охлаждение: пыль, термопасту, вентиляторы.",
                     "Check cooling: dust, thermal paste, fans."),
    "crash.a.psu": ("Блок живлення: чи вистачає потужності й чи не старий він; без подовжувачів і трійників.",
                    "Блок питания: хватает ли мощности и не старый ли он; без удлинителей и тройников.",
                    "Power supply: is it powerful enough and not too old; avoid extension strips and splitters."),
    "crash.a.disk_check": ("Перевірте диск: «Залізо» → стан дисків (SMART).", "Проверьте диск: «Железо» → состояние "
                           "дисков (SMART).", "Check the drive: Hardware → drive health (SMART)."),
    "crash.a.sata": ("Перепідключіть кабель SATA (або переставте M.2).", "Переподключите кабель SATA (или переставьте "
                     "M.2).", "Reseat the SATA cable (or the M.2 drive)."),
    "crash.a.hang": ("Якщо екран завмирав перед вимкненням — це зависання: перевірте драйвери й пам'ять.",
                     "Если экран замирал перед выключением — это зависание: проверьте драйверы и память.",
                     "If the screen froze before it turned off, it was a hang: check drivers and memory."),
    "crash.a.button": ("Якщо комп часто зависає — запустіть «Чому лагає?» під час гри й перевірте пам'ять.",
                       "Если компьютер часто зависает — запустите «Почему лагает?» во время игры и проверьте память.",
                       "If the PC freezes often, run Why lag? while playing and test memory."),
    "crash.a.sfc": ("Перевірте системні файли: «Очищення» → «Відновити системні файли».",
                    "Проверьте системные файлы: «Очистка» → «Восстановить системные файлы».",
                    "Check system files: Cleanup → Repair system files."),
    "crash.original": ("Повернути «Оригінал»", "Вернуть «Оригинал»", "Back to Original"),
    "crash.tdr": ("Відеодрайвер {driver} зависав і перезапускався: {n} разів",
                  "Видеодрайвер {driver} зависал и перезапускался: {n} раз",
                  "Graphics driver {driver} hung and restarted: {n} times"),
    "crash.tdr_d": ("Востаннє — {when}. Так буває через перегрів, розгін або нестабільний драйвер.",
                    "Последний раз — {when}. Так бывает из-за перегрева, разгона или нестабильного драйвера.",
                    "Last time: {when}. Caused by overheating, overclocking or an unstable driver."),
    "crash.whea": ("Апаратні помилки в журналі (WHEA): {n}", "Аппаратные ошибки в журнале (WHEA): {n}",
                   "Hardware errors in the log (WHEA): {n}"),
    "crash.whea_d": ("Востаннє — {when}. Виправлені помилки PCIe чи пам'яті — ознака нестабільного розгону, живлення "
                     "або поганого контакту (райзер, слот).",
                     "Последний раз — {when}. Исправленные ошибки PCIe или памяти — признак нестабильного разгона, "
                     "питания или плохого контакта (райзер, слот).",
                     "Last time: {when}. Corrected PCIe or memory errors point to an unstable overclock, power or a "
                     "bad contact (riser, slot)."),
    "crash.mem.ok": ("Перевірка пам'яті {when}: помилок немає", "Проверка памяти {when}: ошибок нет",
                     "Memory test {when}: no errors"),
    "crash.mem.bad": ("Перевірка пам'яті {when}: знайдено помилки", "Проверка памяти {when}: найдены ошибки",
                      "Memory test {when}: errors found"),
    "crash.mem.unknown": ("Перевірка пам'яті {when}", "Проверка памяти {when}", "Memory test {when}"),
    "crash.dumps_n": ("Дампів синіх екранів: {n} (коди: {codes})", "Дампов синих экранов: {n} (коды: {codes})",
                      "Blue screen dumps: {n} (codes: {codes})"),
    "crash.banner_t": ("Комп аварійно перезавантажувався", "Компьютер аварийно перезагружался",
                       "The PC restarted after a crash"),
    "crash.banner_btn": ("Чому?", "Почему?", "Why?"),

    # ── бібліотека ──
    "nav.library": ("Бібліотека", "Библиотека", "Library"),
    "lib.sub": ("Ваші ігри з усіх магазинів: запуск, час гри й FPS.", "Ваши игры из всех магазинов: запуск, время игры "
                "и FPS.", "Your games from every store: launch, play time and FPS."),
    "lib.refresh": ("Оновити список", "Обновить список", "Refresh"),
    "lib.empty": ("Ігор ще не знайдено. Натисніть «Оновити список» або додайте exe в «Іграх» → «Мої ігри».",
                  "Игр ещё не найдено. Нажмите «Обновить список» или добавьте exe в «Играх» → «Мои игры».",
                  "No games found yet. Press Refresh or add an exe under Games → My games."),
    "lib.play": ("▶  Грати", "▶  Играть", "▶  Play"),
    "lib.folder": ("Папка гри", "Папка игры", "Game folder"),
    "lib.mining": ("Режим на майнінговій карті", "Режим на майнинговой карте", "Mining card mode"),
    "lib.fps_title": ("FPS за останні заміри", "FPS за последние замеры", "FPS over recent measurements"),
    "lib.opt.boost": ("Режим гри під час запуску", "Режим игры при запуске", "Game mode on launch"),
    "lib.opt.boost.d": ("Гра з «Бібліотеки» запускається з увімкненим режимом гри; він вимкнеться сам, коли гра "
                        "закриється.", "Игра из «Библиотеки» запускается с включённым режимом игры; он выключится "
                        "сам, когда игра закроется.", "Games launched from the Library start with game mode on; it turns "
                        "off when the game closes."),
    "lib.opt.fps": ("Записувати FPS під час гри", "Записывать FPS во время игры", "Record FPS while playing"),
    "lib.opt.fps.d": ("Через PresentMon: 60 секунд через 2 хвилини гри й далі раз на 15 хвилин, поки гра на "
                      "передньому плані. Так видно, чи не впав FPS після оновлень.",
                      "Через PresentMon: 60 секунд через 2 минуты игры и дальше раз в 15 минут, пока игра на переднем "
                      "плане. Так видно, не упал ли FPS после обновлений.",
                      "Via PresentMon: 60 seconds after 2 minutes of play, then every 15 minutes while the game is in "
                      "front. Shows whether FPS dropped after updates."),
    "lib.time": ("Зіграно: {t}", "Сыграно: {t}", "Played: {t}"),
    "lib.never": ("Ще не грали з OptimaX", "Ещё не играли с OptimaX", "Not played with OptimaX yet"),
    "lib.last": ("востаннє {when}", "последний раз {when}", "last {when}"),
    "lib.sessions": ("сесій: {n}", "сессий: {n}", "sessions: {n}"),
    "lib.anticheat": ("античит {name}", "античит {name}", "anti-cheat {name}"),
    "lib.fps_last": ("Останній замір ({when}): {avg} FPS, 1% low {low}, фризів {st} / хв. Замірів: {n}.",
                     "Последний замер ({when}): {avg} FPS, 1% low {low}, фризов {st} / мин. Замеров: {n}.",
                     "Last measurement ({when}): {avg} FPS, 1% low {low}, {st} stutters / min. Measurements: {n}."),
    "lib.fps_none": ("Замірів ще немає — FPS запишеться під час гри.", "Замеров ещё нет — FPS запишется во время игры.",
                     "No measurements yet — FPS is recorded while you play."),
    "lib.fps_need_pm": ("Для запису FPS потрібен PresentMon — завантажте його кнопкою нижче.",
                        "Для записи FPS нужен PresentMon — загрузите его кнопкой ниже.",
                        "Recording FPS needs PresentMon — download it with the button below."),
    "lib.mode": ("На майнінговій карті: режим «{mode}»", "На майнинговой карте: режим «{mode}»",
                 "On the mining card: “{mode}” mode"),
    "lib.min": ("{n} хв", "{n} мин", "{n} min"),
    "lib.hours": ("{n} год", "{n} ч", "{n} h"),
    "lib.started": ("{game}: запуск…", "{game}: запуск…", "{game}: starting…"),
    "lib.start_fail": ("{game}: не вдалося запустити", "{game}: не удалось запустить", "{game}: could not start"),

    # ── простий вигляд ──
    "home.s.title": ("Ваш ПК", "Ваш ПК", "Your PC"),
    "home.s.state": ("Оптимізовано на {n}%. Ще можна покращити: {left}.", "Оптимизировано на {n}%. Ещё можно "
                     "улучшить: {left}.", "{n}% optimized. Still to improve: {left}."),
    "home.s.optimize": ("Оптимізувати", "Оптимизировать", "Optimize"),
    "home.s.lag": ("Чому лагає?", "Почему лагает?", "Why lag?"),
    "home.s.full": ("Усі можливості", "Все возможности", "All features"),
    "home.s.simple": ("Простий вигляд", "Простой вид", "Simple view"),
    "home.s.problems": ("Що варто виправити", "Что стоит исправить", "Worth fixing"),
    "home.s.no_problems": ("Проблем не знайдено ✓", "Проблем не найдено ✓", "No problems found ✓"),
    "set.more": ("Вигляд і допомога", "Вид и помощь", "View and help"),
    "set.more_d": ("Простий вигляд, що нового у версії, звіт про проблему.", "Простой вид, что нового в версии, отчёт "
                   "о проблеме.", "Simple view, what's new, report a problem."),
    "set.simple": ("Простий вигляд", "Простой вид", "Simple view"),
    "set.simple_d": ("У меню лише головне, а на головній — оцінка ПК, одна кнопка «Оптимізувати» й проблеми з "
                     "кнопкою «Виправити».", "В меню только главное, а на главной — оценка ПК, одна кнопка "
                     "«Оптимизировать» и проблемы с кнопкой «Исправить».",
                     "Only the essentials in the menu; the home page shows a PC score, one Optimize button and "
                     "problems with Fix."),
    "set.whats_new": ("Що нового", "Что нового", "What's new"),
    "set.report": ("Повідомити про проблему", "Сообщить о проблеме", "Report a problem"),

    # ── «Що нового» ──
    "wn.title": ("Що нового в OptimaX {v}", "Что нового в OptimaX {v}", "What's new in OptimaX {v}"),
    "wn.66.crash": ("«Чому впав комп?» — у «Діагностиці»: сині екрани й раптові вимкнення простими словами, яка гра "
                    "тоді працювала, і перевірка пам'яті.",
                    "«Почему упал компьютер?» — в «Диагностике»: синие экраны и внезапные выключения простыми словами, "
                    "какая игра тогда работала, и проверка памяти.",
                    "Why did the PC crash? — under Diagnostics: blue screens and sudden shutdowns in plain words, "
                    "which game was running, and a memory test."),
    "wn.66.library": ("Бібліотека ігор: усі ігри з обкладинками, запуск одним натисканням, час гри й історія FPS.",
                      "Библиотека игр: все игры с обложками, запуск одним нажатием, время игры и история FPS.",
                      "Game library: all your games with covers, one-click launch, play time and FPS history."),
    "wn.66.simple": ("Простий вигляд: оцінка ПК, одна кнопка «Оптимізувати» й список того, що виправити.",
                     "Простой вид: оценка ПК, одна кнопка «Оптимизировать» и список того, что исправить.",
                     "Simple view: a PC score, one Optimize button and a list of what to fix."),
    "wn.66.phone": ("Монітор на телефоні: скануйте QR-код і бачте температури, завантаження й FPS під час гри.",
                    "Монитор на телефоне: отсканируйте QR-код и смотрите температуры, загрузку и FPS во время игры.",
                    "Phone monitor: scan the QR code to see temperatures, load and FPS while you play."),
    "wn.66.transfer": ("Перенесення налаштувань: збережіть свій набір у файл і застосуйте на іншому ПК.",
                       "Перенос настроек: сохраните свой набор в файл и примените на другом ПК.",
                       "Settings transfer: save your setup to a file and apply it on another PC."),
    "wn.66.bug": ("Збій OptimaX більше не закриває програму, а звіт про нього відправляється одним натисканням.",
                  "Сбой OptimaX больше не закрывает программу, а отчёт о нём отправляется одним нажатием.",
                  "An OptimaX error no longer closes the app, and a report takes one click."),
    "wn.65.renderer": ("Ігри на майнінговій карті: режим для кожної гри (напряму, DXVK, Mesa, оригінал).",
                       "Игры на майнинговой карте: режим для каждой игры (напрямую, DXVK, Mesa, оригинал).",
                       "Games on a mining card: a mode for each game (native, DXVK, Mesa, original)."),
    "wn.65.check": ("Кнопка «Перевірити» показує, яка карта насправді малює гру.",
                    "Кнопка «Проверить» показывает, какая карта на самом деле рисует игру.",
                    "The Check button shows which card really renders the game."),
    "wn.65.diag": ("«Чому лагає?» бачить фризи, PCIe і відеопам'ять.", "«Почему лагает?» видит фризы, PCIe и "
                   "видеопамять.", "Why lag? sees stutters, PCIe and VRAM."),
    "wn.65.booster": ("Профілі режиму гри: «Мінімальна затримка» і «Стабільний frametime».",
                      "Профили режима игры: «Минимальная задержка» и «Стабильный frametime».",
                      "Game mode profiles: Lowest latency and Stable frametime."),

    # ── перенесення налаштувань ──
    "tr.title": ("Перенесення налаштувань", "Перенос настроек", "Settings transfer"),
    "tr.sub": ("Свій набір оптимізацій і налаштувань — у файл, а потім на інший ПК чи після перевстановлення Windows. "
               "Оптимізації відкриються в перегляді змін — застосуєте самі.",
               "Свой набор оптимизаций и настроек — в файл, а потом на другой ПК или после переустановки Windows. "
               "Оптимизации откроются в просмотре изменений — примените сами.",
               "Your optimizations and settings to a file, then onto another PC or after reinstalling Windows. "
               "Optimizations open in the change review — you apply them."),
    "tr.export": ("Зберегти у файл", "Сохранить в файл", "Save to file"),
    "tr.import": ("Завантажити з файлу", "Загрузить из файла", "Load from file"),
    "tr.exported": ("Збережено: оптимізацій {n}, ігор {g}", "Сохранено: оптимизаций {n}, игр {g}",
                    "Saved: {n} optimizations, {g} games"),
    "tr.bad": ("Це не файл налаштувань OptimaX ({err})", "Это не файл настроек OptimaX ({err})",
               "This is not an OptimaX settings file ({err})"),
    "tr.summary": ("Файл з OptimaX {ver}.\n\nОптимізацій до перегляду: {new} (уже застосовано: {done}, не для цього "
                   "ПК: {blocked}, невідомих цій версії: {unknown}).\nІгор: {games} (exe немає на цьому ПК: {missing})."
                   "\n\nНалаштування програми (режим гри, бібліотека, чистильник) застосуються одразу, а оптимізації "
                   "відкриються в перегляді змін.",
                   "Файл из OptimaX {ver}.\n\nОптимизаций к просмотру: {new} (уже применено: {done}, не для этого ПК: "
                   "{blocked}, неизвестных этой версии: {unknown}).\nИгр: {games} (exe нет на этом ПК: {missing})."
                   "\n\nНастройки программы (режим игры, библиотека, чистильщик) применятся сразу, а оптимизации "
                   "откроются в просмотре изменений.",
                   "File from OptimaX {ver}.\n\nOptimizations to review: {new} (already applied: {done}, not for this "
                   "PC: {blocked}, unknown to this version: {unknown}).\nGames: {games} (exe not on this PC: {missing})."
                   "\n\nApp settings (game mode, library, cleaner) apply right away; optimizations open in the change "
                   "review."),
    "tr.go": ("Продовжити", "Продолжить", "Continue"),
    "tr.imported": ("Налаштувань застосовано: {keys}, ігор додано: {games}", "Настроек применено: {keys}, игр "
                    "добавлено: {games}", "Settings applied: {keys}, games added: {games}"),

    # ── монітор на телефоні ──
    "ph.title": ("Монітор на телефоні", "Монитор на телефоне", "Phone monitor"),
    "ph.sub": ("Температури, завантаження й FPS — на телефоні в домашній мережі. Без додатків: лише відскануйте "
               "QR-код камерою.", "Температуры, загрузка и FPS — на телефоне в домашней сети. Без приложений: просто "
               "отсканируйте QR-код камерой.", "Temperatures, load and FPS on your phone over your home network. No "
               "app: just scan the QR code with the camera."),
    "ph.enable": ("Увімкнути", "Включить", "Turn on"),
    "ph.new_code": ("Новий код", "Новый код", "New code"),
    "ph.copy": ("Скопіювати посилання", "Скопировать ссылку", "Copy link"),
    "ph.copied": ("Посилання скопійовано", "Ссылка скопирована", "Link copied"),
    "ph.new_done": ("Старе посилання більше не працює", "Старая ссылка больше не работает",
                    "The old link no longer works"),
    "ph.fail": ("Не вдалося запустити монітор: {err}", "Не удалось запустить монитор: {err}",
                "Could not start the monitor: {err}"),
    "ph.hint": ("Телефон має бути в тій самій мережі Wi-Fi, що й ПК. Сторінка лише показує показники — керувати ПК з "
                "неї не можна. Посилання з секретним кодом не діліться; «Новий код» робить старе недійсним.",
                "Телефон должен быть в той же сети Wi-Fi, что и ПК. Страница только показывает показатели — "
                "управлять ПК с неё нельзя. Ссылкой с секретным кодом не делитесь; «Новый код» делает старую "
                "недействительной.",
                "The phone must be on the same Wi-Fi as the PC. The page only shows readings — it can't control the "
                "PC. Don't share the link with its secret code; New code invalidates the old one."),
    "ph.public": ("Мережу в Windows позначено як «Загальнодоступна» — телефон не підключиться. Змініть її на "
                  "«Приватна»: Параметри → Мережа та Інтернет → Властивості.",
                  "Сеть в Windows отмечена как «Общедоступная» — телефон не подключится. Смените её на «Частная»: "
                  "Параметры → Сеть и Интернет → Свойства.",
                  "Windows marks this network as Public — the phone won't connect. Switch it to Private: Settings → "
                  "Network & internet → Properties."),
    "ph.no_lan": ("ПК не підключений до домашньої мережі — телефону нема до чого підключатися.",
                  "ПК не подключён к домашней сети — телефону не к чему подключаться.",
                  "The PC isn't on a home network — there's nothing for the phone to connect to."),
    "ph.gpu_t": ("Відеокарта °C", "Видеокарта °C", "GPU °C"),
    "ph.gpu_l": ("Завантаження відеокарти", "Загрузка видеокарты", "GPU load"),
    "ph.cpu_l": ("Завантаження процесора", "Загрузка процессора", "CPU load"),
    "ph.cpu_t": ("Процесор °C", "Процессор °C", "CPU °C"),
    "ph.ram": ("Оперативна пам'ять", "Оперативная память", "RAM"),
    "ph.vram": ("Відеопам'ять", "Видеопамять", "VRAM"),
    "ph.clock": ("Частота відеокарти", "Частота видеокарты", "GPU clock"),
    "ph.power": ("Споживання відеокарти", "Потребление видеокарты", "GPU power"),
    "ph.no_game": ("Гра не запущена", "Игра не запущена", "No game running"),
    "ph.game": ("Гра:", "Игра:", "Game:"),
    "ph.offline": ("Немає зв'язку з ПК", "Нет связи с ПК", "No connection to the PC"),
    "ph.boost": ("режим гри", "режим игры", "game mode"),

    # ── звіт про помилку ──
    "bug.crash_t": ("В OptimaX сталася помилка", "В OptimaX произошла ошибка", "OptimaX ran into an error"),
    "bug.crash_d": ("Програма працює далі. Надіслати звіт розробнику? Відкриється сторінка GitHub з готовим текстом "
                    "(без імені користувача й особистих шляхів) — перегляньте його й натисніть «Submit».",
                    "Программа работает дальше. Отправить отчёт разработчику? Откроется страница GitHub с готовым "
                    "текстом (без имени пользователя и личных путей) — просмотрите его и нажмите «Submit».",
                    "The app keeps running. Send a report to the developer? A GitHub page opens with the text filled "
                    "in (no user name or personal paths) — review it and press Submit."),
    "bug.native_t": ("Минулого разу OptimaX аварійно закрилася", "Прошлый раз OptimaX аварийно закрылась",
                     "OptimaX closed unexpectedly last time"),
    "bug.native_d": ("Надіслати звіт розробнику? Відкриється сторінка GitHub з готовим текстом (без імені користувача "
                     "й особистих шляхів) — перегляньте його й натисніть «Submit».",
                     "Отправить отчёт разработчику? Откроется страница GitHub с готовым текстом (без имени "
                     "пользователя и личных путей) — просмотрите его и нажмите «Submit».",
                     "Send a report to the developer? A GitHub page opens with the text filled in (no user name or "
                     "personal paths) — review it and press Submit."),
    "bug.send": ("Надіслати звіт", "Отправить отчёт", "Send report"),
    "bug.preview": ("[перегляд] звіт готовий ({n} символів)", "[просмотр] отчёт готов ({n} символов)",
                    "[preview] report ready ({n} characters)"),
}
