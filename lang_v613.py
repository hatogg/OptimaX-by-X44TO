"""OptimaX — переклади 6.13: новий дизайн (дашборд, бічне меню, теми, анімації) і сторінка «Пам'ять»."""

STRINGS = {
    # ── «Що нового» ──
    "wn.613.design": ("Новий вигляд: дашборд з оцінкою продуктивності й радаром, живі графіки процесора й пам'яті, "
                      "плавні переходи між сторінками і бічне меню, що розгортається, коли наводите мишу (його можна "
                      "закріпити кнопкою внизу).",
                      "Новый вид: дашборд с оценкой производительности и радаром, живые графики процессора и памяти, "
                      "плавные переходы между страницами и боковое меню, которое разворачивается при наведении мыши "
                      "(его можно закрепить кнопкой внизу).",
                      "A new look: a dashboard with a performance score and radar, live CPU and memory charts, smooth "
                      "page transitions and a side menu that slides out when you hover over it (pin it with the button "
                      "at the bottom)."),
    "wn.613.theme": ("Світла й темна тема — або як у Windows. Перемикається одразу, кнопкою внизу меню чи в "
                     "«Налаштуваннях → Вигляд». Там же можна вимкнути анімації.",
                     "Светлая и тёмная тема — или как в Windows. Переключается сразу, кнопкой внизу меню или в "
                     "«Настройках → Вид». Там же можно выключить анимации.",
                     "Light and dark themes, or follow Windows. Switch instantly with the button at the bottom of the "
                     "menu or in Settings → Appearance, where you can also turn animations off."),
    "wn.613.memory": ("Нова сторінка «Пам'ять»: скільки RAM зайнято насправді, хто її тримає, і «Звільнити пам'ять» — "
                      "стискає лише програми, що сплять у фоні, й очищує кеш, а гру не чіпає. Результат «до → після», а "
                      "через хвилину OptimaX чесно показує, скільки втрималося.",
                      "Новая страница «Память»: сколько RAM занято на самом деле, кто её держит, и «Освободить память» — "
                      "сжимает только спящие в фоне программы и очищает кэш, а игру не трогает. Результат «до → после», "
                      "а через минуту OptimaX честно показывает, сколько удержалось.",
                      "New Memory page: how much RAM is really in use, who holds it, and Free up memory — trims only "
                      "apps asleep in the background and clears the cache, never your game. You get a before → after "
                      "result, and a minute later OptimaX honestly shows how much stayed free."),

    # ── загальне ──
    "btn.done": ("Готово", "Готово", "Done"),
    "splash.sub": ("Оптимізація, яку видно в цифрах", "Оптимизация, которую видно в цифрах",
                   "Optimization you can see in numbers"),
    "nav.memory": ("Пам'ять", "Память", "Memory"),

    # ── бічне меню й теми ──
    "rail.pin": ("Закріпити меню", "Закрепить меню", "Pin the menu"),
    "rail.unpin": ("Згортати меню", "Сворачивать меню", "Collapse the menu"),
    "theme.to_light": ("Світла тема", "Светлая тема", "Light theme"),
    "theme.to_dark": ("Темна тема", "Тёмная тема", "Dark theme"),
    "theme.system": ("Як у Windows", "Как в Windows", "Same as Windows"),
    "theme.dark": ("Темна", "Тёмная", "Dark"),
    "theme.light": ("Світла", "Светлая", "Light"),
    "set.look": ("Вигляд", "Вид", "Appearance"),
    "set.look_d": ("Тема, анімації та бічне меню. Тема змінюється одразу, без перезапуску.",
                   "Тема, анимации и боковое меню. Тема меняется сразу, без перезапуска.",
                   "Theme, animations and the side menu. The theme changes right away, no restart needed."),
    "set.motion": ("Плавні анімації", "Плавные анимации", "Smooth animations"),
    "set.motion.d": ("Переходи між сторінками, лічильники, що набігають, живі графіки. Вимкніть на дуже слабкому "
                     "ПК або якщо рух відволікає.",
                     "Переходы между страницами, набегающие счётчики, живые графики. Выключите на очень слабом ПК "
                     "или если движение отвлекает.",
                     "Page transitions, counting numbers, live charts. Turn off on a very weak PC or if motion "
                     "distracts you."),
    "set.rail": ("Бічне меню завжди розгорнуте", "Боковое меню всегда развёрнуто", "Keep the side menu expanded"),
    "set.rail.d": ("Вимкнено — у меню лише іконки, а підписи з'являються, коли наводите мишу.",
                   "Выключено — в меню только иконки, а подписи появляются при наведении мыши.",
                   "Off: the menu shows icons only, and the labels slide out when you hover over it."),
    "set.splash": ("Заставка під час запуску", "Заставка при запуске", "Splash screen at start"),
    "set.splash.d": ("Логотип на пів секунди, поки OptimaX готує вікно.",
                     "Логотип на полсекунды, пока OptimaX готовит окно.",
                     "The logo for half a second while OptimaX prepares the window."),

    # ── дашборд ──
    "dash.title": ("Дашборд", "Дашборд", "Dashboard"),
    "dash.sub": ("Оцінка вашого ПК, що відбувається просто зараз і що можна покращити.",
                 "Оценка вашего ПК, что происходит прямо сейчас и что можно улучшить.",
                 "Your PC's score, what's happening right now and what can be improved."),
    "dash.score": ("Оцінка продуктивності", "Оценка производительности", "Performance score"),
    "dash.of100": ("/ 100", "/ 100", "/ 100"),
    "dash.how": ("З чого складається?", "Из чего складывается?", "How is it calculated?"),
    "dash.how_t": ("Оцінка {n} зі 100", "Оценка {n} из 100", "Score: {n} out of 100"),
    "dash.how_d": ("Оцінка складається лише з того, що OptimaX справді перевірив на цьому ПК. Найбільша вага — у "
                   "застосованих рекомендованих оптимізаціях (35 %), далі перевірка збірки (20 %), баланс заліза "
                   "(15 %), приватність, пам'ять і диск (по 10 %).\n",
                   "Оценка складывается только из того, что OptimaX действительно проверил на этом ПК. Наибольший "
                   "вес — у применённых рекомендованных оптимизациях (35 %), дальше проверка сборки (20 %), баланс "
                   "железа (15 %), приватность, память и диск (по 10 %).\n",
                   "The score is made only of what OptimaX actually checked on this PC. Applied recommended "
                   "optimizations weigh the most (35%), then the build check (20%), hardware balance (15%), privacy, "
                   "memory and disk (10% each).\n"),
    "dash.ax.opt": ("Оптимізація", "Оптимизация", "Optimization"),
    "dash.ax.opt.d": ("частка рекомендованих оптимізацій, які вже застосовано",
                      "доля рекомендованных оптимизаций, которые уже применены",
                      "share of the recommended optimizations already applied"),
    "dash.ax.privacy": ("Приватність", "Приватность", "Privacy"),
    "dash.ax.privacy.d": ("вимкнена телеметрія й стеження", "отключённая телеметрия и слежка",
                          "telemetry and tracking turned off"),
    "dash.ax.build": ("Збірка", "Сборка", "Build"),
    "dash.ax.build.d": ("попередження й поради перевірки збірки (частота пам'яті, монітор, драйвери…)",
                        "предупреждения и советы проверки сборки (частота памяти, монитор, драйверы…)",
                        "warnings and tips from the build check (memory speed, monitor, drivers…)"),
    "dash.ax.balance": ("Баланс", "Баланс", "Balance"),
    "dash.ax.balance.d": ("чи немає в залізі явно слабкого місця", "нет ли в железе явно слабого места",
                          "whether the hardware has an obvious weak spot"),
    "dash.ax.memory": ("Пам'ять", "Память", "Memory"),
    "dash.ax.memory.d": ("обсяг RAM і скільки її зайнято зараз", "объём RAM и сколько её занято сейчас",
                         "amount of RAM and how much of it is in use now"),
    "dash.ax.disk": ("Диск", "Диск", "Disk"),
    "dash.ax.disk.d": ("вільне місце на системному диску і чи це SSD", "свободное место на системном диске и SSD ли это",
                       "free space on the system drive and whether it's an SSD"),
    "dash.v.great": ("ПК добре налаштований", "ПК хорошо настроен", "Your PC is well tuned"),
    "dash.v.good": ("Непогано — є що покращити", "Неплохо — есть что улучшить", "Not bad — there's room to improve"),
    "dash.v.low": ("Багато можна прискорити", "Многое можно ускорить", "A lot can be sped up"),
    "dash.v.wait": ("Рахуємо оцінку…", "Считаем оценку…", "Calculating the score…"),
    "dash.optimize_all": ("Оптимізувати", "Оптимизировать", "Optimize"),
    "dash.profile": ("Профіль оцінки", "Профиль оценки", "Score profile"),
    "dash.your_pc": ("Ваш ПК", "Ваш ПК", "Your PC"),
    "dash.quick": ("Швидкі дії", "Быстрые действия", "Quick actions"),
    "dash.q.mem": ("Звільнити пам'ять", "Освободить память", "Free up memory"),
    "dash.q.mem_d": ("Програми, що сплять, і кеш", "Спящие программы и кэш", "Sleeping apps and cache"),
    "dash.q.clean": ("Очищення", "Очистка", "Cleanup"),
    "dash.q.clean_d": ("Тимчасові файли й кеші", "Временные файлы и кэши", "Temporary files and caches"),
    "dash.q.boost_d": ("Усе для гри — одним натисканням", "Всё для игры — одним нажатием", "Everything for gaming in one click"),
    "dash.q.boost_on": ("УВІМК.", "ВКЛ.", "ON"),
    "dash.q.lag": ("Чому лагає?", "Почему лагает?", "Why does it lag?"),
    "dash.q.lag_d": ("Знайти, що обмежує FPS", "Найти, что ограничивает FPS", "Find what limits your FPS"),
    "dash.live": ("Наживо", "Вживую", "Live"),

    # ── сторінка «Пам'ять» ──
    "mem.title": ("Пам'ять", "Память", "Memory"),
    "mem.sub": ("Скільки RAM зайнято насправді, хто її тримає, і звільнення з чесним заміром «до» і «після».",
                "Сколько RAM занято на самом деле, кто её держит, и освобождение с честным замером «до» и «после».",
                "How much RAM is really in use, who holds it, and freeing it with an honest before/after measurement."),
    "mem.in_use": ("у використанні", "используется", "in use"),
    "mem.live": ("Останні секунди, наживо", "Последние секунды, вживую", "Last seconds, live"),
    "mem.st.used": ("Використовується", "Используется", "In use"),
    "mem.st.avail": ("Доступно", "Доступно", "Available"),
    "mem.st.cache": ("Кеш (standby)", "Кэш (standby)", "Cache (standby)"),
    "mem.st.total": ("Усього", "Всего", "Total"),
    "mem.lvl.ok": ("Спокійно", "Спокойно", "Relaxed"),
    "mem.lvl.high": ("Зайнято багато", "Занято много", "Getting full"),
    "mem.lvl.full": ("Майже заповнена", "Почти заполнена", "Nearly full"),
    "mem.free_btn": ("Звільнити пам'ять", "Освободить память", "Free up memory"),
    "mem.free_note": ("Стискає лише програми, що сплять у фоні, й очищує кеш. Гру, активне вікно й системні процеси "
                      "не чіпає.",
                      "Сжимает только программы, спящие в фоне, и очищает кэш. Игру, активное окно и системные "
                      "процессы не трогает.",
                      "Trims only apps that are asleep in the background and clears the cache. Never touches your game, "
                      "the active window or system processes."),
    "mem.who": ("Хто займає пам'ять", "Кто занимает память", "What's using memory"),
    "mem.who_sub": ("{n} програм, разом {v}", "{n} программ, вместе {v}", "{n} apps, {v} together"),
    "mem.who_note": ("Робочий набір (те, що програма тримає в RAM просто зараз), усі процеси програми разом.",
                     "Рабочий набор (то, что программа держит в RAM прямо сейчас), все процессы программы вместе.",
                     "Working set (what the app holds in RAM right now), all of the app's processes together."),
    "mem.state.active": ("Активна", "Активна", "Active"),
    "mem.state.background": ("У фоні", "В фоне", "Background"),
    "mem.state.idle": ("Спить", "Спит", "Asleep"),
    "mem.procs": ("процесів: {n}", "процессов: {n}", "processes: {n}"),
    "mem.auto": ("Очищати кеш автоматично", "Очищать кэш автоматически", "Clear the cache automatically"),
    "mem.auto_d": ("Коли кеш більший за {standby}, а вільно менше {free}. Те саме налаштування, що й на сторінці «Ігри».",
                   "Когда кэш больше {standby}, а свободно меньше {free}. Та же настройка, что и на странице «Игры».",
                   "When the cache is over {standby} and less than {free} is free. Same setting as on the Games page."),
    "mem.auto_cfg": ("Пороги…", "Пороги…", "Thresholds…"),
    "mem.sheet.title": ("Звільняю пам'ять…", "Освобождаю память…", "Freeing memory…"),
    "mem.sheet.sub": ("Це займе кілька секунд.", "Это займёт несколько секунд.", "This takes a few seconds."),
    "mem.sheet.done": ("Пам'ять звільнено", "Память освобождена", "Memory freed"),
    "mem.step.trim": ("Стискаю програми, що сплять у фоні", "Сжимаю спящие в фоне программы",
                      "Trimming apps asleep in the background"),
    "mem.step.cache": ("Очищую кеш standby", "Очищаю кэш standby", "Clearing the standby cache"),
    "mem.step.measure": ("Міряю результат", "Измеряю результат", "Measuring the result"),
    "mem.freed": ("звільнено", "освобождено", "freed"),
    "mem.was": ("було {v}", "было {v}", "was {v}"),
    "mem.now": ("стало {v}", "стало {v}", "now {v}"),
    "mem.res.trimmed": ("Стиснуто програм: {n} ({names}).", "Сжато программ: {n} ({names}).",
                        "Apps trimmed: {n} ({names})."),
    "mem.res.cache": ("Кеш очищено: {v}.", "Кэш очищен: {v}.", "Cache cleared: {v}."),
    "mem.res.little": ("Звільнилося небагато — значить, пам'ять і так використовувалася розумно.",
                       "Освободилось немного — значит, память и так использовалась разумно.",
                       "Not much was freed, which means memory was already being used sensibly."),
    "mem.res.note": ("Через хвилину OptimaX ще раз заміряє, скільки втрималося: Windows і програми частину пам'яті "
                     "забирають назад — це нормально.",
                     "Через минуту OptimaX ещё раз замерит, сколько удержалось: Windows и программы часть памяти "
                     "забирают обратно — это нормально.",
                     "In a minute OptimaX measures again how much stayed free: Windows and apps take some memory back, "
                     "and that's normal."),
    "mem.res.line": ("Останнє звільнення о {when}: {v} ({was} → {now}).", "Последнее освобождение в {when}: {v} ({was} → {now}).",
                     "Last freed at {when}: {v} ({was} → {now})."),
    "mem.res.wait": ("Скільки втрималося — перевіримо через хвилину.", "Сколько удержалось — проверим через минуту.",
                     "We'll check in a minute how much stayed free."),
    "mem.res.rebound": ("Через хвилину втрималося {kept}, назад повернулося {back}.",
                        "Через минуту удержалось {kept}, обратно вернулось {back}.",
                        "A minute later {kept} stayed free and {back} came back."),
    "mem.toast.rebound": ("Пам'ять: через хвилину втрималося {kept} із {freed}", "Память: через минуту удержалось {kept} из {freed}",
                          "Memory: {kept} of {freed} stayed free after a minute"),
    "mem.fail": ("Не вдалося звільнити пам'ять — подробиці в журналі", "Не удалось освободить память — подробности в журнале",
                 "Couldn't free memory — see the log for details"),
    "mem.log.trimmed": ("  ✓ стиснуто програм, що сплять: {n} (≈{mb} МБ)", "  ✓ сжато спящих программ: {n} (≈{mb} МБ)",
                        "  ✓ trimmed sleeping apps: {n} (≈{mb} MB)"),
    "mem.log.dry": ("  [dry-run] програм, що сплять, які стиснулися б: {n}", "  [dry-run] спящих программ, которые сжались бы: {n}",
                    "  [dry-run] sleeping apps that would be trimmed: {n}"),
    "mem.log.cache_ok": ("  ✓ кеш standby очищено", "  ✓ кэш standby очищен", "  ✓ standby cache cleared"),
    "mem.log.cache_fail": ("  ⚠ кеш standby не очистився (потрібні права адміністратора)",
                           "  ⚠ кэш standby не очистился (нужны права администратора)",
                           "  ⚠ the standby cache wasn't cleared (administrator rights are needed)"),
    "mem.app.services": ("Служби Windows", "Службы Windows", "Windows services"),
    "mem.app.explorer": ("Провідник", "Проводник", "File Explorer"),
    "mem.app.compression": ("Стиснення пам'яті", "Сжатие памяти", "Memory compression"),
    "mem.app.search": ("Пошук Windows", "Поиск Windows", "Windows Search"),
    "mem.app.dwm": ("Диспетчер вікон", "Диспетчер окон", "Desktop Window Manager"),
    "mem.app.phone": ("Зв'язок із телефоном", "Связь с телефоном", "Phone Link"),
    "mem.app.widgets": ("Віджети Windows", "Виджеты Windows", "Windows widgets"),
}
