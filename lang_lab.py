"""OptimaX — переклади сторінок «Бенчмарки» і «Блок реклами»."""

STRINGS = {
    "nav.bench": ("Бенчмарки", "Бенчмарки", "Benchmarks"),
    "nav.adblock": ("Блок реклами", "Блок рекламы", "Ad blocker"),
    "u.min_n": ("{n} хв", "{n} мин", "{n} min"),

    # ── власний тест відеокарти ──
    "gb.sub": ("Перевірте швидкість і стабільність відеокарти, порівняйте до й після оптимізації, драйвера чи розгону.",
               "Проверьте скорость и стабильность видеокарты, сравните до и после оптимизации, драйвера или разгона.",
               "Check your GPU's speed and stability, compare before and after tuning, drivers or overclocking."),
    "gb.title": ("GPU-тест OptimaX", "GPU-тест OptimaX", "OptimaX GPU Test"),
    "gb.text": ("Важка 3D-сцена з трасуванням променів у шейдері: м'які тіні, відбиття, неонове світло. Тест іде в "
                "окремому вікні, а бали — це середній FPS × 100, тож результати легко порівнювати.",
                "Тяжёлая 3D-сцена с трассировкой лучей в шейдере: мягкие тени, отражения, неоновый свет. Тест идёт в "
                "отдельном окне, а баллы — это средний FPS × 100, поэтому результаты легко сравнивать.",
                "A heavy 3D scene ray-marched in a shader: soft shadows, reflections, neon light. The test runs in its "
                "own window, and the score is the average FPS × 100, so results are easy to compare."),
    "gb.f1": ("OpenGL 3.3", "OpenGL 3.3", "OpenGL 3.3"),
    "gb.f2": ("1080p · 1440p · 4K", "1080p · 1440p · 4K", "1080p · 1440p · 4K"),
    "gb.f3": ("Перевірка стабільності", "Проверка стабильности", "Stability check"),
    "gb.res": ("Роздільність", "Разрешение", "Resolution"),
    "gb.mode": ("Режим", "Режим", "Mode"),
    "gb.mode_bench_s": ("Бенчмарк · 1 хв", "Бенчмарк · 1 мин", "Benchmark · 1 min"),
    "gb.mode_bench": ("бенчмарк", "бенчмарк", "benchmark"),
    "gb.mode_stress": ("Стрес-тест", "Стресс-тест", "Stress test"),
    "gb.minutes": ("Тривалість", "Длительность", "Duration"),
    "gb.fullscreen": ("На весь екран", "На весь экран", "Fullscreen"),
    "gb.start": ("Запустити тест", "Запустить тест", "Run test"),
    "gb.start_stress": ("Запустити стрес-тест", "Запустить стресс-тест", "Run stress test"),
    "gb.stress_t": ("Стрес-тест відеокарти", "Стресс-тест видеокарты", "GPU stress test"),
    "gb.stress_q": ("Відеокарта {m} хв працюватиме на 100%: вона нагріється, а вентилятори стануть гучнішими. Раз на 10 "
                    "секунд OptimaX перевірятиме, чи рахує вона без помилок. Зупинити тест — клавішею Esc.",
                    "Видеокарта {m} мин будет работать на 100%: она нагреется, а вентиляторы станут громче. Раз в 10 "
                    "секунд OptimaX будет проверять, считает ли она без ошибок. Остановить тест — клавишей Esc.",
                    "The GPU will run at 100% for {m} min: it will heat up and the fans will get louder. Every 10 "
                    "seconds OptimaX checks that it computes without errors. Press Esc to stop the test."),
    "gb.p_start": ("Відкриваю вікно тесту…", "Открываю окно теста…", "Opening the test window…"),
    "gb.p_warm": ("Прогрів…", "Прогрев…", "Warming up…"),
    "gb.p_run": ("Тест триває: {t} з {d}", "Тест идёт: {t} из {d}", "Running: {t} of {d}"),
    "gb.p_err": ("помилок: {n}", "ошибок: {n}", "errors: {n}"),
    "gb.hud_warm": ("Прогрів — результат ще не рахується", "Прогрев — результат ещё не считается",
                    "Warming up — not counted yet"),
    "gb.hud_line": ("{fps} FPS · залишилось {left}", "{fps} FPS · осталось {left}", "{fps} FPS · {left} left"),
    "gb.hud_err": ("Помилок рендеру: {n} з {c} перевірок", "Ошибок рендера: {n} из {c} проверок",
                   "Render errors: {n} of {c} checks"),
    "gb.hud_sens": ("{t} °C · {c} МГц · {w} Вт", "{t} °C · {c} МГц · {w} Вт", "{t} °C · {c} MHz · {w} W"),
    "gb.hud_esc": ("Esc — зупинити", "Esc — остановить", "Esc — stop"),
    "gb.hud_idle": ("⚠ Малює {gpu} — NVIDIA простоює", "⚠ Рисует {gpu} — NVIDIA простаивает",
                    "⚠ Rendering on {gpu} — NVIDIA is idle"),
    "gb.idle_gpu": ("Тест малювала {gpu}, а {dgpu} простоювала, тож це бали вбудованої графіки. Щоб оцінити ігрову "
                    "карту, міряйте FPS у самій грі.",
                    "Тест рисовала {gpu}, а {dgpu} простаивала, так что это баллы встроенной графики. Чтобы оценить "
                    "игровую карту, меряйте FPS в самой игре.",
                    "The test ran on {gpu} while {dgpu} sat idle, so this is the integrated graphics score. To judge "
                    "the gaming GPU, measure FPS in the game itself."),
    "gb.cancelled": ("Тест зупинено", "Тест остановлен", "Test stopped"),
    "gb.err_t": ("Тест не запустився", "Тест не запустился", "The test didn't start"),
    "gb.err_d": ("{err}\n\nПотрібна відеокарта з OpenGL 3.3 і свіжий драйвер. Через віддалений робочий стіл (RDP) "
                 "тест не працює.",
                 "{err}\n\nНужна видеокарта с OpenGL 3.3 и свежий драйвер. Через удалённый рабочий стол (RDP) "
                 "тест не работает.",
                 "{err}\n\nYou need a GPU with OpenGL 3.3 and an up-to-date driver. The test doesn't work over Remote "
                 "Desktop (RDP)."),
    "gb.result": ("Результат", "Результат", "Result"),
    "gb.points": ("балів", "баллов", "points"),
    "gb.v.bench.t": ("{score} балів у {preset}", "{score} баллов в {preset}", "{score} points at {preset}"),
    "gb.first": ("Перший результат у цьому режимі. Запустіть тест ще раз після оптимізації, оновлення драйвера чи "
                 "розгону — OptimaX покаже різницю.",
                 "Первый результат в этом режиме. Запустите тест ещё раз после оптимизации, обновления драйвера или "
                 "разгона — OptimaX покажет разницу.",
                 "First result in this mode. Run the test again after tuning, a driver update or overclocking — "
                 "OptimaX will show the difference."),
    "gb.delta_up": ("{d}% до попереднього тесту — стало швидше.", "{d}% к предыдущему тесту — стало быстрее.",
                    "{d}% vs. the previous run — faster."),
    "gb.delta_down": ("{d}% до попереднього тесту — стало повільніше. Перевірте температуру й фонові програми.",
                      "{d}% к предыдущему тесту — стало медленнее. Проверьте температуру и фоновые программы.",
                      "{d}% vs. the previous run — slower. Check temperatures and background apps."),
    "gb.delta_same": ("{d}% до попереднього тесту — у межах похибки.", "{d}% к предыдущему тесту — в пределах "
                      "погрешности.", "{d}% vs. the previous run — within the margin of error."),
    "gb.delta_changes": ("Між тестами OptimaX змінив налаштувань: {n}.", "Между тестами OptimaX изменил настроек: {n}.",
                         "OptimaX changed {n} settings between the runs."),
    "gb.v.stable.t": ("Стабільно: {m} хв без помилок", "Стабильно: {m} мин без ошибок", "Stable: {m} min without errors"),
    "gb.v.stable.d": ("Кожен контрольний кадр збігся до біта, FPS рівний (падіння {drop}%). Відеокарта готова до "
                      "довгих ігор.",
                      "Каждый контрольный кадр совпал до бита, FPS ровный (падение {drop}%). Видеокарта готова к "
                      "долгим играм.",
                      "Every check frame matched bit for bit and FPS stayed flat ({drop}% drop). The GPU is ready for "
                      "long gaming sessions."),
    "gb.v.errors.t": ("Знайдено помилки рендеру: {n}", "Найдены ошибки рендера: {n}", "Render errors found: {n}"),
    "gb.v.errors.d": ("Під навантаженням відеокарта рахує неправильно. Так буває через надто сильний розгін ядра чи "
                      "пам'яті, андервольт або перегрів відеопам'яті. Поверніть частоти за замовчуванням і повторіть тест.",
                      "Под нагрузкой видеокарта считает неправильно. Так бывает из-за слишком сильного разгона ядра или "
                      "памяти, андервольта или перегрева видеопамяти. Верните частоты по умолчанию и повторите тест.",
                      "Under load the GPU computes incorrectly. This happens with too aggressive core or memory "
                      "overclocks, undervolting or overheating VRAM. Restore default clocks and run the test again."),
    "gb.v.hot.t": ("Висока температура: {t} °C", "Высокая температура: {t} °C", "High temperature: {t} °C"),
    "gb.v.hot.d": ("Почистіть радіатор від пилу, перевірте вентилятори й криву обертів; ноутбуку допоможе підставка з "
                   "охолодженням.",
                   "Почистите радиатор от пыли, проверьте вентиляторы и кривую оборотов; ноутбуку поможет подставка с "
                   "охлаждением.",
                   "Clean the dust off the heatsink, check the fans and fan curve; a cooling pad helps laptops."),
    "gb.v.throttle.t": ("Продуктивність падає під навантаженням: −{drop}%", "Производительность падает под нагрузкой: "
                        "−{drop}%", "Performance drops under load: −{drop}%"),
    "gb.v.throttle.d": ("Відеокарта скидає частоти через нагрів або ліміт живлення. Покращіть охолодження чи профіль "
                        "вентиляторів; на ноутбуці ввімкніть режим живлення «Найкраща продуктивність».",
                        "Видеокарта сбрасывает частоты из-за нагрева или лимита питания. Улучшите охлаждение или профиль "
                        "вентиляторов; на ноутбуке включите режим питания «Максимальная производительность».",
                        "The GPU lowers its clocks because of heat or the power limit. Improve cooling or the fan "
                        "profile; on a laptop switch to the Best performance power mode."),
    "gb.v.crash.t": ("Тест обірвався", "Тест прервался", "The test crashed"),
    "gb.v.crash.d": ("Відеодрайвер перезапустився або вікно тесту закрилося з помилкою. Це ознака нестабільності: "
                     "розгін чи андервольт, перегрів, слабкий блок живлення або збійний драйвер.",
                     "Видеодрайвер перезапустился или окно теста закрылось с ошибкой. Это признак нестабильности: "
                     "разгон или андервольт, перегрев, слабый блок питания или сбойный драйвер.",
                     "The graphics driver restarted or the test window closed with an error. That's a sign of "
                     "instability: overclock or undervolt, overheating, a weak power supply or a faulty driver."),
    "gb.vs.bench": ("бенчмарк", "бенчмарк", "benchmark"),
    "gb.vs.stable": ("стабільно", "стабильно", "stable"),
    "gb.vs.errors": ("помилки", "ошибки", "errors"),
    "gb.vs.hot": ("гаряче", "горячо", "hot"),
    "gb.vs.throttle": ("скидає частоти", "сбрасывает частоты", "throttling"),
    "gb.vs.crash": ("збій", "сбой", "crash"),
    "gb.s.avg": ("Середній FPS", "Средний FPS", "Average FPS"),
    "gb.s.min": ("Мінімальний FPS", "Минимальный FPS", "Min FPS"),
    "gb.s.temp": ("Макс. температура", "Макс. температура", "Max temperature"),
    "gb.s.clock": ("Частота: сер. / мін.", "Частота: ср. / мин.", "Clock: avg / min"),
    "gb.s.power": ("Макс. споживання", "Макс. потребление", "Peak power"),
    "gb.s.checks": ("Помилки рендеру", "Ошибки рендера", "Render errors"),
    "gb.s.checks_v": ("{n} з {c}", "{n} из {c}", "{n} of {c}"),
    "gb.s.drop": ("Падіння FPS", "Падение FPS", "FPS drop"),
    "gb.s.dur": ("Тривалість", "Длительность", "Duration"),
    "gb.s.gpu": ("Відеокарта", "Видеокарта", "GPU"),
    "gb.legend": ("FPS щосекунди", "FPS ежесекундно", "FPS per second"),
    "gb.legend_t": ("Угорі — FPS щосекунди, внизу — температура відеокарти, °C",
                    "Вверху — FPS ежесекундно, внизу — температура видеокарты, °C",
                    "Top: FPS per second · bottom: GPU temperature, °C"),
    "gb.log_score": ("  ✓ {score} балів · {fps} FPS · 1% low {low}", "  ✓ {score} баллов · {fps} FPS · 1% low {low}",
                     "  ✓ {score} points · {fps} FPS · 1% low {low}"),
    "gb.toast_score": ("Результат: {score} балів", "Результат: {score} баллов", "Result: {score} points"),
    "gb.hist": ("Історія результатів", "История результатов", "Results history"),
    "gb.hist_d": ("Відсоток — різниця з попереднім таким самим тестом.", "Процент — разница с предыдущим таким же тестом.",
                  "The percentage is the difference from the previous run of the same test."),
    "gb.hist_clear": ("Очистити історію", "Очистить историю", "Clear history"),
    "gb.hist_clear_q": ("Видалити всі збережені результати тестів?", "Удалить все сохранённые результаты тестов?",
                        "Delete all saved test results?"),
    "gb.details": ("Деталі", "Детали", "Details"),

    # ── сторонні бенчмарки ──
    "gb.tools": ("Інші бенчмарки", "Другие бенчмарки", "Other benchmarks"),
    "gb.tools_d": ("Встановлення через winget і запуск в один клік. FurMark 2 OptimaX запускає сам і зберігає результат "
                   "в історію; в інших програмах результат видно в їхньому вікні.",
                   "Установка через winget и запуск в один клик. FurMark 2 OptimaX запускает сам и сохраняет результат "
                   "в историю; в других программах результат виден в их окне.",
                   "Install with winget and launch in one click. OptimaX runs FurMark 2 itself and saves the result to "
                   "the history; other apps show their results in their own window."),
    "gb.kind.gpu": ("відеокарта", "видеокарта", "GPU"),
    "gb.kind.cpu": ("процесор", "процессор", "CPU"),
    "gb.kind.stab": ("стабільність", "стабильность", "stability"),
    "gb.kind.disk": ("диск", "диск", "disk"),
    "gb.t.furmark": ("Класичний «бублик»: максимальне навантаження й нагрів відеокарти, бали для порівняння з іншими.",
                     "Классический «бублик»: максимальная нагрузка и нагрев видеокарты, баллы для сравнения с другими.",
                     "The classic \"fur donut\": maximum GPU load and heat, with a score to compare with others."),
    "gb.t.superposition": ("Красива сцена Unigine з оцінкою в балах і таблицею рекордів. Автоматичний режим є лише в "
                           "платній версії, тож тест запускається вручну.",
                           "Красивая сцена Unigine с оценкой в баллах и таблицей рекордов. Автоматический режим есть "
                           "только в платной версии, поэтому тест запускается вручную.",
                           "A beautiful Unigine scene with a score and leaderboards. Automation is only in the paid "
                           "edition, so you start the test yourself."),
    "gb.t.cinebench": ("Рендер сцени процесором: бали для одного й усіх ядер. Добре видно, чи не скидає процесор частоти.",
                       "Рендер сцены процессором: баллы для одного и всех ядер. Хорошо видно, не сбрасывает ли процессор "
                       "частоты.",
                       "Renders a scene on the CPU: single- and multi-core scores. Shows well whether the CPU throttles."),
    "gb.t.occt": ("Стабільність процесора, пам'яті, відеокарти й блока живлення з датчиками та пошуком помилок.",
                  "Стабильность процессора, памяти, видеокарты и блока питания с датчиками и поиском ошибок.",
                  "Stability of the CPU, memory, GPU and power supply, with sensors and error detection."),
    "gb.t.cdm": ("Швидкість читання й запису SSD і HDD: послідовна та випадкова.",
                 "Скорость чтения и записи SSD и HDD: последовательная и случайная.",
                 "SSD and HDD read/write speed: sequential and random."),
    "gb.t.3dmark": ("Найпопулярніший ігровий бенчмарк (Time Spy, Steel Nomad). Продається в Steam.",
                    "Самый популярный игровой бенчмарк (Time Spy, Steel Nomad). Продаётся в Steam.",
                    "The most popular gaming benchmark (Time Spy, Steel Nomad). Sold on Steam."),
    "gb.install": ("Встановити", "Установить", "Install"),
    "gb.open": ("Відкрити", "Открыть", "Open"),
    "gb.site": ("Сайт", "Сайт", "Website"),
    "gb.open_steam": ("Відкрити в Steam", "Открыть в Steam", "Open in Steam"),
    "gb.fm_run": ("Бенчмарк {preset}", "Бенчмарк {preset}", "Benchmark {preset}"),
    "gb.install_t": ("Встановлення {name}", "Установка {name}", "Installing {name}"),
    "gb.install_q": ("OptimaX встановить {name} через winget ({pkg}) з офіційного джерела.",
                     "OptimaX установит {name} через winget ({pkg}) из официального источника.",
                     "OptimaX will install {name} with winget ({pkg}) from the official source."),
    "gb.launched": ("{name} запущено", "{name} запущен", "{name} started"),
    "gb.fm_q": ("FurMark 2 проведе бенчмарк {preset} (близько хвилини) у власному вікні. OptimaX прочитає бали, FPS і "
                "температуру та збереже їх в історію.",
                "FurMark 2 проведёт бенчмарк {preset} (около минуты) в своём окне. OptimaX прочитает баллы, FPS и "
                "температуру и сохранит их в историю.",
                "FurMark 2 will run a {preset} benchmark (about a minute) in its own window. OptimaX will read the "
                "score, FPS and temperature and save them to the history."),
    "gb.fm_running": ("FurMark працює… ще ≈{s} с", "FurMark работает… ещё ≈{s} с", "FurMark is running… ≈{s} s left"),
    "gb.fm_missing": ("FurMark 2 не знайдено. Встановіть його кнопкою «Встановити».",
                      "FurMark 2 не найден. Установите его кнопкой «Установить».",
                      "FurMark 2 wasn't found. Install it with the Install button."),
    "gb.fm_timeout": ("FurMark працює занадто довго — зупинено.", "FurMark работает слишком долго — остановлен.",
                      "FurMark ran for too long and was stopped."),
    "gb.fm_result": ("  ✓ FurMark 2: {score} балів · {fps} FPS", "  ✓ FurMark 2: {score} баллов · {fps} FPS",
                     "  ✓ FurMark 2: {score} points · {fps} FPS"),
    "gb.fm_noscore": ("  · FurMark завершився, але бали не знайдено — подивіться їх у вікні FurMark.",
                      "  · FurMark завершился, но баллы не найдены — посмотрите их в окне FurMark.",
                      "  · FurMark finished but no score was found — check it in the FurMark window."),

    # ── блокування реклами ──
    "ab.sub": ("Як Pi-hole: DNS-фільтр прибирає рекламу, трекери й шкідливі сайти в усіх програмах і браузерах — "
               "і, за бажанням, на телефоні й телевізорі у вашій мережі.",
               "Как Pi-hole: DNS-фильтр убирает рекламу, трекеры и вредоносные сайты во всех программах и браузерах — "
               "и, по желанию, на телефоне и телевизоре в вашей сети.",
               "Like Pi-hole: a DNS filter removes ads, trackers and malicious sites in every app and browser — and, "
               "if you want, on phones and TVs on your network."),
    "ab.off_t": ("Блокування реклами вимкнено", "Блокировка рекламы выключена", "Ad blocking is off"),
    "ab.off_d": ("Увімкніть фільтр — OptimaX стане DNS-сервером цього комп'ютера й відкидатиме запити до рекламних і "
                 "стежувальних серверів.",
                 "Включите фильтр — OptimaX станет DNS-сервером этого компьютера и будет отбрасывать запросы к рекламным "
                 "и следящим серверам.",
                 "Turn on the filter and OptimaX becomes this PC's DNS server, dropping requests to ad and tracking "
                 "servers."),
    "ab.light_d2": ("Легкий режим: Windows отримає DNS-сервіс, який сам блокує рекламу. У фоні нічого не працює, але "
                    "немає статистики й власних списків.",
                    "Лёгкий режим: Windows получит DNS-сервис, который сам блокирует рекламу. В фоне ничего не работает, "
                    "но нет статистики и своих списков.",
                    "Light mode: Windows uses a DNS service that blocks ads by itself. Nothing runs in the background, "
                    "but there are no statistics or custom lists."),
    "ab.mode": ("Спосіб", "Способ", "Method"),
    "ab.mode_filter": ("Вбудований фільтр (як Pi-hole)", "Встроенный фильтр (как Pi-hole)", "Built-in filter (like Pi-hole)"),
    "ab.mode_light": ("Легкий режим", "Лёгкий режим", "Light mode"),
    "ab.step1": ("Фільтр працює у фоні як служба й стає DNS-сервером Windows для всіх програм і браузерів.",
                 "Фильтр работает в фоне как служба и становится DNS-сервером Windows для всех программ и браузеров.",
                 "The filter runs in the background as a service and becomes Windows' DNS server for every app."),
    "ab.step2": ("Домени зі списків (≈280 тис.) отримують відповідь «0.0.0.0» — реклама й трекери просто не "
                 "завантажуються.",
                 "Домены из списков (≈280 тыс.) получают ответ «0.0.0.0» — реклама и трекеры просто не загружаются.",
                 "Domains on the lists (≈280k) get the answer 0.0.0.0, so ads and trackers simply don't load."),
    "ab.step3": ("Решта запитів іде до Cloudflare чи Quad9 зашифровано й кешується — сайти відкриваються навіть швидше.",
                 "Остальные запросы идут к Cloudflare или Quad9 в зашифрованном виде и кешируются — сайты открываются "
                 "даже быстрее.",
                 "Everything else goes encrypted to Cloudflare or Quad9 and is cached, so sites open even faster."),
    "ab.enable": ("Увімкнути блокування", "Включить блокировку", "Turn on blocking"),
    "ab.enable_t": ("Блокування реклами", "Блокировка рекламы", "Ad blocking"),
    "ab.enable_q": ("OptimaX завантажить вибрані списки, запустить фоновий DNS-фільтр (задача планувальника «OptimaX "
                    "DNS») і вкаже його як DNS на мережевих адаптерах. Попередні DNS збережуться й повернуться, коли ви "
                    "вимкнете фільтр. Якщо фільтр зупиниться, Windows сама перейде на DNS роутера.",
                    "OptimaX загрузит выбранные списки, запустит фоновый DNS-фильтр (задача планировщика «OptimaX DNS») "
                    "и укажет его как DNS на сетевых адаптерах. Прежние DNS сохранятся и вернутся, когда вы выключите "
                    "фильтр. Если фильтр остановится, Windows сама перейдёт на DNS роутера.",
                    "OptimaX will download the chosen lists, start the background DNS filter (the \"OptimaX DNS\" "
                    "scheduled task) and set it as DNS on your network adapters. Your previous DNS is saved and comes "
                    "back when you turn the filter off. If the filter stops, Windows falls back to the router's DNS."),
    "ab.disable": ("Вимкнути", "Выключить", "Turn off"),
    "ab.disable_t": ("Вимкнути блокування реклами?", "Выключить блокировку рекламы?", "Turn off ad blocking?"),
    "ab.disable_q": ("Фільтр зупиниться, DNS адаптерів повернуться до попередніх, задачу планувальника буде видалено. "
                     "Списки й налаштування залишаться.",
                     "Фильтр остановится, DNS адаптеров вернутся к прежним, задача планировщика будет удалена. Списки и "
                     "настройки останутся.",
                     "The filter stops, adapters get their previous DNS back and the scheduled task is removed. Lists "
                     "and settings are kept."),
    "ab.disable_q_light": ("DNS адаптерів повернуться до тих, що були до легкого режиму.",
                           "DNS адаптеров вернутся к тем, что были до лёгкого режима.",
                           "Adapters get back the DNS they had before light mode."),
    "ab.disabled": ("Блокування реклами вимкнено", "Блокировка рекламы выключена", "Ad blocking turned off"),
    "ab.on_t": ("Захист увімкнено", "Защита включена", "Protection is on"),
    "ab.on_d": ("Дозволені запити йдуть до {up} {enc}.", "Разрешённые запросы идут к {up} {enc}.",
                "Allowed queries go to {up} {enc}."),
    "ab.enc_on": ("зашифровано (DNS-over-HTTPS)", "в зашифрованном виде (DNS-over-HTTPS)", "encrypted (DNS over HTTPS)"),
    "ab.enc_off": ("звичайним DNS", "обычным DNS", "over plain DNS"),
    "ab.on_lan": ("Для інших пристроїв: DNS {ip}.", "Для других устройств: DNS {ip}.", "Other devices: DNS {ip}."),
    "ab.waiting": ("Фільтр запускається або не відповідає — OptimaX перевіряє його…",
                   "Фильтр запускается или не отвечает — OptimaX проверяет его…",
                   "The filter is starting or not responding — OptimaX is checking it…"),
    "ab.paused_t": ("Призупинено до {time}", "Приостановлено до {time}", "Paused until {time}"),
    "ab.pause": ("Пауза", "Пауза", "Pause"),
    "ab.resume": ("Відновити", "Возобновить", "Resume"),
    "ab.p5": ("На 5 хвилин", "На 5 минут", "For 5 minutes"),
    "ab.p30": ("На 30 хвилин", "На 30 минут", "For 30 minutes"),
    "ab.p60": ("На годину", "На час", "For 1 hour"),
    "ab.p240": ("На 4 години", "На 4 часа", "For 4 hours"),
    "ab.paused": ("Блокування призупинено на {m} хв", "Блокировка приостановлена на {m} мин", "Blocking paused for {m} min"),
    "ab.resumed": ("Блокування відновлено", "Блокировка возобновлена", "Blocking resumed"),
    "ab.tile.total": ("Запитів сьогодні", "Запросов сегодня", "Queries today"),
    "ab.tile.total_s": ("з кешу: {n} · мережа: {local}", "из кэша: {n} · сеть: {local}", "cached: {n} · local: {local}"),
    "ab.tile.blocked": ("Заблоковано", "Заблокировано", "Blocked"),
    "ab.tile.blocked_s": ("{pct}% усіх запитів", "{pct}% всех запросов", "{pct}% of all queries"),
    "ab.tile.domains": ("Доменів у списках", "Доменов в списках", "Domains on lists"),
    "ab.tile.domains_s": ("списків: {n}", "списков: {n}", "lists: {n}"),
    "ab.tile.speed": ("Середня відповідь", "Средний ответ", "Average response"),
    "ab.tile.speed_s": ("миттєво з кешу: {pct}%", "мгновенно из кэша: {pct}%", "instant from cache: {pct}%"),
    "ab.chart_t": ("Запити за 24 години", "Запросы за 24 часа", "Queries over 24 hours"),
    "ab.legend_ok": ("Дозволено", "Разрешено", "Allowed"),
    "ab.legend_blocked": ("Заблоковано", "Заблокировано", "Blocked"),
    "ab.top_blocked": ("Найчастіше блокується", "Чаще всего блокируется", "Top blocked"),
    "ab.top_allowed": ("Найчастіші запити", "Самые частые запросы", "Top queries"),
    "ab.top_clients": ("Пристрої", "Устройства", "Devices"),
    "ab.this_pc": ("цей ПК", "этот ПК", "this PC"),
    "ab.nothing_yet": ("Поки нічого", "Пока ничего", "Nothing yet"),
    "ab.allow": ("Дозволити", "Разрешить", "Allow"),
    "ab.block": ("Блокувати", "Блокировать", "Block"),
    "ab.allowed": ("{d} — завжди дозволено", "{d} — всегда разрешён", "{d} is always allowed"),
    "ab.blocked_d": ("{d} — завжди блокується", "{d} — всегда блокируется", "{d} is always blocked"),
    "ab.log_t": ("Журнал запитів", "Журнал запросов", "Query log"),
    "ab.log_d": ("Останні запити з цього ПК і мережі. Якщо сайт чи гра не працює, знайдіть тут заблокований домен і "
                 "натисніть «Дозволити».",
                 "Последние запросы с этого ПК и сети. Если сайт или игра не работает, найдите здесь заблокированный "
                 "домен и нажмите «Разрешить».",
                 "Recent queries from this PC and the network. If a site or game breaks, find the blocked domain here "
                 "and press Allow."),
    "ab.search": ("Пошук домену або IP", "Поиск домена или IP", "Search a domain or IP"),
    "ab.f_all": ("Усі", "Все", "All"),
    "ab.f_blocked": ("Заблоковані", "Заблокированные", "Blocked"),
    "ab.f_allowed": ("Дозволені", "Разрешённые", "Allowed"),
    "ab.refresh": ("Оновити", "Обновить", "Refresh"),
    "ab.log_empty": ("Запитів поки немає (або журнал вимкнено в налаштуваннях).",
                     "Запросов пока нет (или журнал выключен в настройках).",
                     "No queries yet (or the log is turned off in settings)."),
    "ab.st.blocked": ("заблоковано", "заблокировано", "blocked"),
    "ab.st.cache": ("кеш", "кэш", "cache"),
    "ab.st.ok": ("OK", "OK", "OK"),
    "ab.st.local": ("мережа", "сеть", "local"),
    "ab.st.fail": ("помилка", "ошибка", "error"),
    "ab.src.custom": ("ваше правило", "ваше правило", "your rule"),
    "ab.src.canary": ("Firefox DoH", "Firefox DoH", "Firefox DoH"),
    "ab.lists_t": ("Списки блокування", "Списки блокировки", "Blocklists"),
    "ab.lists_d": ("Відкриті списки, які постійно оновлюють їхні автори; OptimaX оновлює їх сам раз на тиждень. Більше "
                   "списків — більше блокується, але й вища ймовірність, що зламається щось потрібне.",
                   "Открытые списки, которые постоянно обновляют их авторы; OptimaX обновляет их сам раз в неделю. "
                   "Больше списков — больше блокируется, но и выше вероятность, что сломается что-то нужное.",
                   "Open lists their authors keep updating; OptimaX refreshes them weekly. More lists block more, but "
                   "are also more likely to break something you need."),
    "ab.cat.ads": ("Реклама й трекери", "Реклама и трекеры", "Ads & trackers"),
    "ab.cat.security": ("Безпека", "Безопасность", "Security"),
    "ab.cat.telemetry": ("Телеметрія пристроїв", "Телеметрия устройств", "Device telemetry"),
    "ab.cat.content": ("Небажаний вміст", "Нежелательный контент", "Unwanted content"),
    "ab.l.stevenblack": ("Класичний список Pi-hole: реклама й шкідливі сайти.",
                         "Классический список Pi-hole: реклама и вредоносные сайты.",
                         "The classic Pi-hole list: ads and malicious sites."),
    "ab.l.hagezi_pro": ("Збалансований: реклама, трекери, аналітика, скам. Мало хибних спрацювань.",
                        "Сбалансированный: реклама, трекеры, аналитика, скам. Мало ложных срабатываний.",
                        "Balanced: ads, trackers, analytics, scams. Few false positives."),
    "ab.l.oisd_big": ("Великий і обережний список OISD — для тих, хто хоче більше.",
                      "Большой и аккуратный список OISD — для тех, кто хочет больше.",
                      "OISD's big but careful list, for those who want more."),
    "ab.l.adguard_dns": ("Список, на якому працює AdGuard DNS.", "Список, на котором работает AdGuard DNS.",
                         "The list behind AdGuard DNS."),
    "ab.l.hagezi_tif": ("Фішинг, шкідливе ПЗ, шахрайство. Великий: ще ≈50 МБ пам'яті.",
                        "Фишинг, вредоносное ПО, мошенничество. Большой: ещё ≈50 МБ памяти.",
                        "Phishing, malware, fraud. Large: about 50 MB more memory."),
    "ab.l.urlhaus": ("Сайти, що поширюють шкідливе ПЗ просто зараз.", "Сайты, распространяющие вредоносное ПО прямо сейчас.",
                     "Sites spreading malware right now."),
    "ab.l.hagezi_win": ("Телеметрія Windows і Office. Може вимкнути частину функцій Microsoft.",
                        "Телеметрия Windows и Office. Может отключить часть функций Microsoft.",
                        "Windows and Office telemetry. May turn off some Microsoft features."),
    "ab.l.hagezi_tv": ("Стеження й реклама смарт-телевізорів — корисно в режимі для всієї мережі.",
                       "Слежка и реклама смарт-телевизоров — полезно в режиме для всей сети.",
                       "Smart-TV tracking and ads — useful when protecting the whole network."),
    "ab.l.hagezi_phone": ("Телеметрія телефонів Xiaomi, Huawei, OPPO, vivo.", "Телеметрия телефонов Xiaomi, Huawei, OPPO, vivo.",
                          "Telemetry of Xiaomi, Huawei, OPPO and vivo phones."),
    "ab.l.hagezi_tiktok": ("Повністю блокує TikTok.", "Полностью блокирует TikTok.", "Blocks TikTok completely."),
    "ab.l.hagezi_gambling": ("Онлайн-казино й букмекери.", "Онлайн-казино и букмекеры.", "Online casinos and betting."),
    "ab.l.adult": ("Сайти для дорослих.", "Сайты для взрослых.", "Adult sites."),
    "ab.l.hagezi_social": ("Соцмережі (Facebook, Instagram, X та інші) — для фокусу чи дитячого ПК.",
                           "Соцсети (Facebook, Instagram, X и другие) — для фокуса или детского ПК.",
                           "Social networks (Facebook, Instagram, X and more) — for focus or a kid's PC."),
    "ab.count": ("{n} доменів", "{n} доменов", "{n} domains"),
    "ab.list_err": ("не завантажився", "не загрузился", "failed to load"),
    "ab.lists_state": ("Вибрано списків: {n} · {d} доменів · оновлено {when}",
                       "Выбрано списков: {n} · {d} доменов · обновлено {when}",
                       "Lists selected: {n} · {d} domains · updated {when}"),
    "ab.lists_never": ("Вибрано списків: {n}. Вони завантажаться, коли ви ввімкнете фільтр.",
                       "Выбрано списков: {n}. Они загрузятся, когда вы включите фильтр.",
                       "Lists selected: {n}. They'll be downloaded when you turn on the filter."),
    "ab.lists_update": ("Оновити зараз", "Обновить сейчас", "Update now"),
    "ab.lists_save": ("Застосувати списки", "Применить списки", "Apply lists"),
    "ab.lists_saved": ("  ✓ Списків увімкнено: {n}", "  ✓ Списков включено: {n}", "  ✓ Lists enabled: {n}"),
    "ab.dl_list": ("Завантажую {name}…", "Загружаю {name}…", "Downloading {name}…"),
    "ab.list_ok": ("  ✓ {name}: {n} доменів", "  ✓ {name}: {n} доменов", "  ✓ {name}: {n} domains"),
    "ab.list_fail": ("  ✗ {name}: не вдалося завантажити ({err})", "  ✗ {name}: не удалось загрузить ({err})",
                     "  ✗ {name}: download failed ({err})"),
    "ab.no_lists": ("Не вдалося завантажити жоден список. Перевірте інтернет і спробуйте ще раз.",
                    "Не удалось загрузить ни одного списка. Проверьте интернет и попробуйте ещё раз.",
                    "No list could be downloaded. Check your internet connection and try again."),
    "ab.rules_t": ("Власні правила", "Свои правила", "Your rules"),
    "ab.rules_d": ("По одному домену в рядку. example.com — лише цей домен; *.example.com — разом із піддоменами; "
                   "ads*.example.com — за шаблоном.",
                   "По одному домену в строке. example.com — только этот домен; *.example.com — вместе с поддоменами; "
                   "ads*.example.com — по шаблону.",
                   "One domain per line. example.com — just this domain; *.example.com — with subdomains; "
                   "ads*.example.com — a pattern."),
    "ab.rules.allow": ("Завжди дозволяти", "Всегда разрешать", "Always allow"),
    "ab.rules.block": ("Завжди блокувати", "Всегда блокировать", "Always block"),
    "ab.rules.allow_ph": ("наприклад:\ns.youtube.com\n*.mycompany.com", "например:\ns.youtube.com\n*.mycompany.com",
                          "for example:\ns.youtube.com\n*.mycompany.com"),
    "ab.rules.block_ph": ("наприклад:\n*.ads.example.com\ntracker.site", "например:\n*.ads.example.com\ntracker.site",
                          "for example:\n*.ads.example.com\ntracker.site"),
    "ab.rules_save": ("Зберегти правила", "Сохранить правила", "Save rules"),
    "ab.rules_saved": ("Правила збережено: дозволено {a}, заблоковано {b}", "Правила сохранены: разрешено {a}, "
                       "заблокировано {b}", "Rules saved: {a} allowed, {b} blocked"),
    "ab.set_t": ("Налаштування фільтра", "Настройки фильтра", "Filter settings"),
    "ab.upstream": ("Куди пересилати дозволені запити", "Куда пересылать разрешённые запросы",
                    "Where to send allowed queries"),
    "ab.upstream_d": ("Найшвидший для вас покаже «Мережа» → «Тест DNS».", "Самый быстрый для вас покажет «Сеть» → «Тест DNS».",
                      "Network → DNS test shows which one is fastest for you."),
    "ab.s.doh": ("Шифрувати запити (DNS-over-HTTPS)", "Шифровать запросы (DNS-over-HTTPS)", "Encrypt queries (DNS over HTTPS)"),
    "ab.s.doh_d": ("Провайдер і Wi-Fi у кафе не бачать, які сайти ви відкриваєте. Якщо мережа блокує DoH, фільтр сам "
                   "перейде на звичайний DNS.",
                   "Провайдер и Wi-Fi в кафе не видят, какие сайты вы открываете. Если сеть блокирует DoH, фильтр сам "
                   "перейдёт на обычный DNS.",
                   "Your ISP and café Wi-Fi can't see which sites you open. If the network blocks DoH, the filter "
                   "switches to plain DNS by itself."),
    "ab.s.lan": ("Захищати всю домашню мережу", "Защищать всю домашнюю сеть", "Protect the whole home network"),
    "ab.s.lan_d": ("Телефони, телевізори й консолі теж зможуть користуватися фільтром — вкажіть IP цього ПК як DNS у "
                   "роутері або в налаштуваннях Wi-Fi пристрою. Працює, поки ПК увімкнений.",
                   "Телефоны, телевизоры и консоли тоже смогут пользоваться фильтром — укажите IP этого ПК как DNS в "
                   "роутере или в настройках Wi-Fi устройства. Работает, пока ПК включён.",
                   "Phones, TVs and consoles can use the filter too — set this PC's IP as DNS on the router or in the "
                   "device's Wi-Fi settings. Works while the PC is on."),
    "ab.lan_q": ("Фільтр почне відповідати на DNS-запити з домашньої мережі, а брандмауер Windows відкриє порт 53 для "
                 "приватних мереж. Щоб пристрої не втрачали інтернет, коли ПК вимкнений, укажіть у роутері другим DNS "
                 "звичайний сервер (наприклад, 1.1.1.1).",
                 "Фильтр начнёт отвечать на DNS-запросы из домашней сети, а брандмауэр Windows откроет порт 53 для "
                 "частных сетей. Чтобы устройства не теряли интернет, когда ПК выключен, укажите в роутере вторым DNS "
                 "обычный сервер (например, 1.1.1.1).",
                 "The filter will answer DNS queries from your home network and Windows Firewall will open port 53 for "
                 "private networks. So devices keep internet when the PC is off, set a regular server (e.g. 1.1.1.1) "
                 "as the second DNS on the router."),
    "ab.lan_hint": ("Вкажіть DNS {ip} у роутері (розділ DHCP/LAN) або в налаштуваннях Wi-Fi телефона. Краще закріпити "
                    "за цим ПК постійну IP-адресу в роутері.",
                    "Укажите DNS {ip} в роутере (раздел DHCP/LAN) или в настройках Wi-Fi телефона. Лучше закрепить за "
                    "этим ПК постоянный IP-адрес в роутере.",
                    "Set DNS {ip} on the router (DHCP/LAN section) or in the phone's Wi-Fi settings. It's best to reserve "
                    "a fixed IP address for this PC on the router."),
    "ab.s.log_queries": ("Вести журнал запитів", "Вести журнал запросов", "Keep a query log"),
    "ab.s.log_queries_d": ("Останні 3000 запитів у пам'яті — щоб знайти, що зламалося. На диск не записується.",
                           "Последние 3000 запросов в памяти — чтобы найти, что сломалось. На диск не пишется.",
                           "The last 3,000 queries in memory to find what broke. Never written to disk."),
    "ab.s.strict": ("Суворий режим", "Строгий режим", "Strict mode"),
    "ab.s.strict_d": ("Без резервного DNS роутера: реклама не прослизне навіть зрідка, але якщо фільтр зупиниться, "
                      "інтернет пропаде, доки ви його не ввімкнете знову чи не вимкнете фільтр.",
                      "Без резервного DNS роутера: реклама не проскочит даже изредка, но если фильтр остановится, "
                      "интернет пропадёт, пока вы его снова не включите или не выключите фильтр.",
                      "No backup router DNS: ads never slip through, but if the filter stops, the internet goes down "
                      "until you start it again or turn the filter off."),
    "ab.saved": ("Збережено", "Сохранено", "Saved"),
    "ab.light_t": ("Легкий режим — DNS із блокуванням реклами", "Лёгкий режим — DNS с блокировкой рекламы",
                   "Light mode — DNS with ad blocking"),
    "ab.light_d": ("Windows питатиме адреси в сервісу, який сам відкидає рекламу. У фоні нічого не працює; статистики "
                   "й власних списків немає.",
                   "Windows будет спрашивать адреса у сервиса, который сам отбрасывает рекламу. В фоне ничего не "
                   "работает; статистики и своих списков нет.",
                   "Windows will ask a service that drops ads by itself. Nothing runs in the background; no statistics "
                   "or custom lists."),
    "ab.light.ads": ("реклама й трекери", "реклама и трекеры", "ads & trackers"),
    "ab.light.family": ("+ сайти для дорослих, безпечний пошук", "+ сайты для взрослых, безопасный поиск",
                        "+ adult sites, safe search"),
    "ab.light.malware": ("реклама й шкідливі сайти", "реклама и вредоносные сайты", "ads & malware"),
    "ab.light_active": ("активний", "активен", "active"),
    "ab.light_q": ("DNS усіх адаптерів зміняться на {name} ({ips}). Попередні збережуться в журналі змін і повернуться "
                   "кнопкою «Вимкнути».",
                   "DNS всех адаптеров сменятся на {name} ({ips}). Прежние сохранятся в журнале изменений и вернутся "
                   "кнопкой «Выключить».",
                   "All adapters will use {name} ({ips}) as DNS. The previous ones are saved in the change journal and "
                   "come back with Turn off."),
    "ab.light_ok": ("Легкий режим: {name}", "Лёгкий режим: {name}", "Light mode: {name}"),
    "ab.light_on_t": ("Легкий режим: {name}", "Лёгкий режим: {name}", "Light mode: {name}"),
    "ab.light_on_d": ("Рекламу відкидає DNS-сервіс. Для статистики й власних списків увімкніть вбудований фільтр.",
                      "Рекламу отбрасывает DNS-сервис. Для статистики и своих списков включите встроенный фильтр.",
                      "The DNS service drops ads. For statistics and custom lists, use the built-in filter."),
    "ab.yt_t": ("Чого DNS-фільтр не прибере", "Чего DNS-фильтр не уберёт", "What a DNS filter can't remove"),
    "ab.yt_d": ("Рекламу в YouTube і Twitch: вона приходить із тих самих серверів, що й відео. Так само й рекламу, "
                "вбудовану в саму сторінку. Для неї — розширення uBlock Origin у браузері; разом із фільтром вони "
                "доповнюють одне одного.",
                "Рекламу в YouTube и Twitch: она приходит с тех же серверов, что и видео. Так же и рекламу, встроенную "
                "в саму страницу. Для неё — расширение uBlock Origin в браузере; вместе с фильтром они дополняют друг "
                "друга.",
                "YouTube and Twitch ads: they come from the same servers as the video. Same for ads built into the page "
                "itself. For those use the uBlock Origin browser extension; together with the filter they complement "
                "each other."),
    "ab.yt_btn": ("uBlock Origin", "uBlock Origin", "uBlock Origin"),
    "ab.undo_light": ("  · повертаю DNS, змінені раніше", "  · возвращаю ранее изменённые DNS",
                      "  · restoring DNS changed earlier"),
    "ab.starting": ("Запускаю фільтр…", "Запускаю фильтр…", "Starting the filter…"),
    "ab.started": ("  ✓ Фільтр працює: {binds} · {n} доменів у списках", "  ✓ Фильтр работает: {binds} · {n} доменов в "
                   "списках", "  ✓ The filter is running: {binds} · {n} domains on lists"),
    "ab.start_fail": ("Фільтр не запустився: {err}", "Фильтр не запустился: {err}", "The filter didn't start: {err}"),
    "ab.task_fail": ("Не вдалося створити задачу планувальника «OptimaX DNS».",
                     "Не удалось создать задачу планировщика «OptimaX DNS».",
                     "Couldn't create the \"OptimaX DNS\" scheduled task."),
    "ab.port_busy": ("Порт 53 уже зайнятий: {who}. Закрийте іншу DNS-програму (AdGuard, Acrylic, dnscrypt-proxy) і "
                     "спробуйте ще раз.",
                     "Порт 53 уже занят: {who}. Закройте другую DNS-программу (AdGuard, Acrylic, dnscrypt-proxy) и "
                     "попробуйте ещё раз.",
                     "Port 53 is already in use: {who}. Close the other DNS app (AdGuard, Acrylic, dnscrypt-proxy) and "
                     "try again."),
    "ab.stopped": ("  ✓ Фільтр зупинено, DNS повернуто", "  ✓ Фильтр остановлен, DNS возвращены",
                   "  ✓ Filter stopped, DNS restored"),
    "ab.dns_restored": ("  ✓ DNS повернуто: {alias}", "  ✓ DNS возвращены: {alias}", "  ✓ DNS restored: {alias}"),
    "ab.tray_pause": ("Призупинити блокування реклами на 5 хв", "Приостановить блокировку рекламы на 5 мин",
                      "Pause ad blocking for 5 min"),
    "ab.upstream_set": ("Фільтр пересилатиме запити до {name}", "Фильтр будет пересылать запросы к {name}",
                        "The filter will forward queries to {name}"),
    "ab.net_conflict": ("Увімкнено блокування реклами — DNS керує фільтр. Змініть сервер на сторінці «Блок реклами».",
                        "Включена блокировка рекламы — DNS управляет фильтр. Смените сервер на странице «Блок рекламы».",
                        "Ad blocking is on, so the filter manages DNS. Change the server on the Ad blocker page."),
}
