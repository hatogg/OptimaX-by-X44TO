"""OptimaX — переклади нових розділів: діагностика, тест FPS, мережа, програми, місце на диску, драйвери,
сторож, пробний режим, розклад, гарячі клавіші, ноутбук, нові перевірки збірки."""

STRINGS = {
    # ── меню, одиниці, спільне ──
    "nav.diagnose": ("Діагностика", "Диагностика", "Diagnostics"),
    "nav.network": ("Мережа", "Сеть", "Network"),
    "nav.apps": ("Програми", "Программы", "Apps"),
    "u.ms": ("{v} мс", "{v} мс", "{v} ms"),
    "u.hz": ("Гц", "Гц", "Hz"),
    "u.sec_n": ("{n} с", "{n} с", "{n} s"),
    "busy.wait": ("Зачекайте — попередня перевірка ще триває", "Подождите — предыдущая проверка ещё идёт",
                  "Please wait — the previous check is still running"),
    "e.on": ("увімкнено", "включено", "on"),
    "e.off": ("вимкнено", "выключено", "off"),
    "e.win10_only": ("  · лише для Windows 10 — пропуск", "  · только для Windows 10 — пропуск",
                     "  · Windows 10 only — skipped"),
    "need.win11": ("Лише для Windows 11.", "Только для Windows 11.", "Windows 11 only."),
    "block.laptop": ("На ноутбуках не застосовується: заважає Windows перемикати живлення від батареї та режим "
                     "економії.", "На ноутбуках не применяется: мешает Windows переключать питание от батареи и режим "
                     "экономии.", "Not applied on laptops: it stops Windows from switching power on battery and battery "
                     "saver."),
    "svc.repair_t": ("Виправлення змін старіших версій", "Исправление изменений старых версий",
                     "Fixing changes made by older versions"),
    "svc.repaired": ("Повернуто до ваших початкових значень: {n}. Старіші версії OptimaX змінювали служби виробника "
                     "ноутбука, очищення файлу підкачки та мобільний інтернет — це могло заважати. Перезавантажте ПК.",
                     "Возвращено к вашим исходным значениям: {n}. Старые версии OptimaX меняли службы производителя "
                     "ноутбука, очистку файла подкачки и мобильный интернет — это могло мешать. Перезагрузите ПК.",
                     "Restored to your original values: {n}. Older OptimaX versions changed laptop maker services, "
                     "page file clearing and mobile broadband setup, which could cause problems. Restart the PC."),
    "need.build": ("Потрібна Windows 10 версії {ver} або новіша — у вашій збірці цього параметра немає.",
                   "Нужна Windows 10 версии {ver} или новее — в вашей сборке этого параметра нет.",
                   "Needs Windows 10 version {ver} or later — your build doesn't have this setting."),
    "need.win10": ("Лише для Windows 10 — у Windows 11 цього елемента немає.",
                   "Только для Windows 10 — в Windows 11 этого элемента нет.",
                   "Windows 10 only — Windows 11 doesn't have this."),
    "need.wifi": ("Wi-Fi-адаптер не знайдено.", "Wi-Fi-адаптер не найден.", "No Wi-Fi adapter found."),
    "need.ethernet": ("Дротовий мережевий адаптер не знайдено.", "Проводной сетевой адаптер не найден.",
                      "No wired network adapter found."),
    "e.mc_keep": ("  · {gb} ГБ пам'яті — стиснення лишаємо як є (корисне, але не критичне)",
                  "  · {gb} ГБ памяти — сжатие оставляем как есть (полезно, но не критично)",
                  "  · {gb} GB of RAM — leaving memory compression as is (useful, not critical)"),
    "e.mc_already": ("  · стиснення пам'яті вже {state}", "  · сжатие памяти уже {state}",
                     "  · memory compression is already {state}"),
    "e.mc_set": ("  · {gb} ГБ пам'яті → стиснення {state}", "  · {gb} ГБ памяти → сжатие {state}",
                 "  · {gb} GB of RAM → compression {state}"),
    "e.audio_fx": ("  · покращення звуку вимкнено для пристроїв: {n}", "  · улучшения звука отключены для устройств: {n}",
                   "  · audio enhancements turned off for devices: {n}"),
    "e.audio_denied": ("  ⚠ {n} пристр. захищені Windows — вимкніть «Покращення звуку» вручну: Параметри → Звук → "
                       "пристрій → Покращення звуку",
                       "  ⚠ {n} устр. защищены Windows — отключите «Улучшения звука» вручную: Параметры → Звук → "
                       "устройство → Улучшения звука",
                       "  ⚠ {n} device(s) are protected by Windows — turn off Audio enhancements manually: "
                       "Settings → Sound → device → Audio enhancements"),
    "e.shaders_note": ("  · ігри перезберуть шейдери під час першого запуску — це нормально",
                       "  · игры пересоберут шейдеры при первом запуске — это нормально",
                       "  · games will rebuild shaders on first launch — that's normal"),
    "fix.booster": ("Увімкнути", "Включить", "Turn on"),
    "act.fu_shaders.t": ("Очистити кеш шейдерів", "Очистить кеш шейдеров", "Clear shader cache"),
    "act.fu_shaders.d": ("DirectX, NVIDIA, AMD та Intel. Лікує фризи й артефакти після оновлення драйвера; перший "
                         "запуск ігор буде трохи довшим.",
                         "DirectX, NVIDIA, AMD и Intel. Лечит фризы и артефакты после обновления драйвера; первый "
                         "запуск игр будет чуть дольше.",
                         "DirectX, NVIDIA, AMD and Intel. Fixes stutters and artifacts after a driver update; the "
                         "first game launch takes a bit longer."),
    "g.opt.dnd": ("Не турбувати", "Не беспокоить", "Do not disturb"),
    "g.opt.dnd.d": ("Сповіщення Windows не спливають поверх гри.", "Уведомления Windows не всплывают поверх игры.",
                    "Windows notifications don't pop up over the game."),
    "g.opt.balance": ("Балансувальник фону", "Балансировщик фона", "Background balancer"),
    "g.opt.balance.d": ("Програма, що раптово забирає процесор, тимчасово отримує нижчий пріоритет.",
                        "Программа, которая внезапно нагружает процессор, временно получает низкий приоритет.",
                        "An app that suddenly hogs the CPU temporarily gets a lower priority."),
    "g.dnd": ("  · сповіщення приглушено до кінця гри", "  · уведомления приглушены до конца игры",
              "  · notifications muted until the game ends"),
    "g.opt_enabled": ("Увімкнено: {opt}", "Включено: {opt}", "Turned on: {opt}"),
    "bal.lowered": ("⚖ {name}: пріоритет знижено ({pct}% процесора)", "⚖ {name}: приоритет снижен ({pct}% процессора)",
                    "⚖ {name}: priority lowered ({pct}% CPU)"),
    "bal.restored": ("⚖ {name}: пріоритет повернуто", "⚖ {name}: приоритет возвращён", "⚖ {name}: priority restored"),
    "games.opt.cores": ("Ядра", "Ядра", "Cores"),
    "games.opt.cores.tip": ("Прив'язати гру до найкращих ядер цього процесора.",
                            "Привязать игру к лучшим ядрам этого процессора.", "Pin the game to this CPU's best cores."),
    "games.opt.cores.tip.vcache": ("Гра працюватиме на кристалі з 3D V-Cache — так, як задумала AMD, але без Game Bar.",
                                   "Игра будет работать на кристалле с 3D V-Cache — как задумала AMD, но без Game Bar.",
                                   "The game runs on the 3D V-Cache die — the way AMD intended, without Game Bar."),
    "games.opt.cores.tip.pcores": ("Гра працюватиме лише на продуктивних P-ядрах, без енергоефективних E-ядер.",
                                   "Игра будет работать только на производительных P-ядрах, без E-ядер.",
                                   "The game runs only on performance P-cores, not efficiency E-cores."),
    "games.opt.cores.tip.numa": ("Гра працюватиме на одному процесорі (NUMA-вузлі) — без затримок між сокетами.",
                                 "Игра будет работать на одном процессоре (NUMA-узле) — без задержек между сокетами.",
                                 "The game runs on one CPU (NUMA node) — no cross-socket latency."),
    "games.opt.cores.na": ("Для цього процесора не потрібно: усі ядра однакові.",
                           "Для этого процессора не нужно: все ядра одинаковые.",
                           "Not needed for this CPU: all cores are equal."),
    "games.cores_on": ("Під час запуску гра отримає {mode}", "При запуске игра получит {mode}",
                       "On launch the game will get {mode}"),
    "games.cores_off": ("Гра працюватиме на всіх ядрах", "Игра будет работать на всех ядрах",
                        "The game will use all cores"),
    "cores.mode.vcache": ("ядра з 3D V-Cache", "ядра с 3D V-Cache", "3D V-Cache cores"),
    "cores.mode.pcores": ("P-ядра", "P-ядра", "P-cores"),
    "cores.mode.numa": ("ядра першого процесора", "ядра первого процессора", "first-CPU cores"),
    "cores.applied": ("⚙ {game}: {mode} (логічні {cpus})", "⚙ {game}: {mode} (логические {cpus})",
                      "⚙ {game}: {mode} (logical {cpus})"),
    "cores.failed": ("⚠ {game}: не вдалося змінити ядра (можливо, блокує античит)",
                     "⚠ {game}: не удалось изменить ядра (возможно, блокирует античит)",
                     "⚠ {game}: couldn't change cores (an anti-cheat may block it)"),
    "wz.ms.copilot": ("Copilot і функції AI", "Copilot и функции AI", "Copilot and AI features"),
    "wz.ms.copilot.d": ("Користуюся Copilot, Recall або AI у Paint і Блокноті.",
                        "Пользуюсь Copilot, Recall или AI в Paint и Блокноте.",
                        "I use Copilot, Recall or AI in Paint and Notepad."),

    # ── нові розділи оптимізації ──
    "grp.ai": ("Windows 11: AI і реклама", "Windows 11: AI и реклама", "Windows 11: AI and ads"),
    "grp.ai.d": ("Copilot, Recall, Click to Do, AI у програмах, рекомендації в «Пуск», поради, Bing у пошуку.",
                 "Copilot, Recall, Click to Do, AI в программах, рекомендации в «Пуск», советы, Bing в поиске.",
                 "Copilot, Recall, Click to Do, AI in apps, Start recommendations, tips, Bing in search."),
    "grp.explorer": ("Провідник і панель завдань", "Проводник и панель задач", "File Explorer and taskbar"),
    "grp.explorer.d": ("Класичне контекстне меню, швидкі папки, «Завершити завдання», менше зайвого в меню.",
                       "Классическое контекстное меню, быстрые папки, «Завершить задачу», меньше лишнего в меню.",
                       "Classic context menu, fast folders, End task, less clutter in menus."),
    "grp.wu": ("Оновлення Windows", "Обновления Windows", "Windows Update"),
    "grp.wu.d": ("Без підміни драйверів, без перезавантаження посеред роботи, пауза й фіксація версії.",
                 "Без подмены драйверов, без перезагрузки посреди работы, пауза и фиксация версии.",
                 "No driver swaps, no restarts mid-work, pause and version lock."),
    "grp.audio": ("Звук", "Звук", "Audio"),
    "grp.audio.d": ("Менша затримка звуку і без приглушення гри під час дзвінків.",
                    "Меньше задержка звука и без приглушения игры во время звонков.",
                    "Lower audio latency and no game ducking during calls."),

    # ── перегляд змін: пробний режим ──
    "rv.trial": ("Пробний режим", "Пробный режим", "Trial mode"),
    "rv.trial_d": ("Після перезавантаження OptimaX запитає, чи залишити зміни. Без відповіді за 2 хвилини — "
                   "усе повернеться як було.",
                   "После перезагрузки OptimaX спросит, оставить ли изменения. Без ответа за 2 минуты — "
                   "всё вернётся как было.",
                   "After a restart OptimaX asks whether to keep the changes. No answer within 2 minutes — "
                   "everything goes back."),
    "trial.title": ("Пробний режим", "Пробный режим", "Trial mode"),
    "trial.active": ("Змін на пробу: {n}. Перезавантажте ПК, перевірте, як усе працює, — і вирішіть.",
        "Изменений на пробу: {n}. Перезагрузите ПК, проверьте, как всё работает, — и решите.",
        "Changes on trial: {n}. Restart, check how everything works, then decide."),
    "trial.decide": ("ПК перезавантажено. Залишити пробні зміни ({n}) чи повернути все як було?",
        "ПК перезагружен. Оставить пробные изменения ({n}) или вернуть всё как было?",
        "The PC has restarted. Keep the trial changes ({n}) or put everything back?"),
    "trial.ask_t": ("Пробний режим: залишити зміни?", "Пробный режим: оставить изменения?", "Trial mode: keep the changes?"),
    "trial.ask_d": ("Ви перезавантажили ПК після пробних змін ({n}). Якщо все працює добре — залиште їх. Якщо щось зламалося або стало гірше — поверніть. Без відповіді за 2 хвилини зміни відкотяться.",
        "Вы перезагрузили ПК после пробных изменений ({n}). Если всё работает хорошо — оставьте их. Если что-то сломалось или стало хуже — верните. Без ответа за 2 минуты изменения откатятся.",
        "You restarted after the trial changes ({n}). If everything works well, keep them. If something broke or got worse, roll back. With no answer in 2 minutes they're rolled back."),
    "trial.keep": ("Залишити зміни", "Оставить изменения", "Keep changes"),
    "trial.revert": ("Відкотити", "Откатить", "Roll back"),
    "trial.started": ("  · пробний режим: зміни ({n}) відкотяться після перезавантаження, якщо їх не підтвердити",
        "  · пробный режим: изменения ({n}) откатятся после перезагрузки, если их не подтвердить",
        "  · trial mode: the changes ({n}) roll back after a restart unless confirmed"),
    "trial.kept": ("Зміни залишено", "Изменения оставлены", "Changes kept"),
    "trial.reverted": ("Пробні зміни відкочено", "Пробные изменения откачены", "Trial changes rolled back"),

    # ── сторож налаштувань ──
    "guard.title": ("Сторож налаштувань", "Сторож настроек", "Settings guard"),
    "guard.sub": ("Оновлення Windows іноді повертають рекламу, Copilot чи телеметрію. Сторож помічає це й пропонує "
                  "застосувати знову — з тими самими резервними копіями.",
                  "Обновления Windows иногда возвращают рекламу, Copilot или телеметрию. Сторож замечает это и "
                  "предлагает применить снова — с теми же резервными копиями.",
                  "Windows updates sometimes bring back ads, Copilot or telemetry. The guard notices and offers to "
                  "re-apply — keeping the same backups."),
    "guard.enable": ("Перевіряти після оновлень Windows і кожні 6 годин",
                     "Проверять после обновлений Windows и каждые 6 часов",
                     "Check after Windows updates and every 6 hours"),
    "guard.check": ("Перевірити зараз", "Проверить сейчас", "Check now"),
    "guard.never": ("Ще не перевіряли.", "Ещё не проверяли.", "Not checked yet."),
    "guard.state_ok": ("Остання перевірка: {when} · Windows {os} · усі зміни на місці.",
                       "Последняя проверка: {when} · Windows {os} · все изменения на месте.",
                       "Last check: {when} · Windows {os} · all changes in place."),
    "guard.state_bad": ("Остання перевірка: {when} · Windows {os} · повернуто налаштувань: {n}.",
                        "Последняя проверка: {when} · Windows {os} · возвращено настроек: {n}.",
                        "Last check: {when} · Windows {os} · settings reverted: {n}."),
    "guard.reapply": ("Застосувати знову", "Применить снова", "Re-apply"),
    "guard.reapply_n": ("Застосувати знову ({n})", "Применить снова ({n})", "Re-apply ({n})"),
    "guard.found": ("Windows повернула налаштування: {n}",
        "Windows вернула настройки: {n}",
        "Settings reverted by Windows: {n}"),
    "guard.clean": ("Сторож: усі зміни на місці", "Сторож: все изменения на месте", "Guard: all changes in place"),
    "guard.on": ("Сторож увімкнено", "Сторож включён", "Guard on"),
    "guard.off": ("Сторож вимкнено", "Сторож выключен", "Guard off"),
    "guard.banner_t": ("Оновлення Windows повернуло налаштування ({n})",
        "Обновление Windows вернуло настройки ({n})",
        "A Windows update reverted settings ({n})"),
    "guard.banner_d": ("Наприклад, рекламу чи Copilot. Можна застосувати їх знову одним кліком.",
                       "Например, рекламу или Copilot. Можно применить их снова одним кликом.",
                       "Such as ads or Copilot. You can re-apply them in one click."),
    "guard.details": ("Що саме", "Что именно", "Details"),
    "guard.restore_t": ("Більшість змін OptimaX уже не діють ({n})", "Большинство изменений OptimaX уже не действуют ({n})",
                        "Most OptimaX changes are no longer in effect ({n})"),
    "guard.restore_d": ("Так буває після відновлення системи. Якщо ви відновлювали систему через проблему, не "
                        "застосовуйте їх знову — краще забути ці записи.",
                        "Так бывает после восстановления системы. Если вы восстанавливали систему из-за проблемы, не "
                        "применяйте их снова — лучше забыть эти записи.",
                        "This happens after a System Restore. If you restored the system because of a problem, don't "
                        "re-apply them; forget these records instead."),
    "guard.forget": ("Забути ці зміни", "Забыть эти изменения", "Forget these changes"),
    "guard.forget_q": ("Забути змін: {n}?", "Забыть изменений: {n}?", "Forget {n} change(s)?"),
    "guard.forget_d": ("Записи зникнуть із журналу змін. Систему це не змінює: ці налаштування вже такі, як до OptimaX.",
                       "Записи исчезнут из журнала изменений. Систему это не меняет: эти настройки уже такие, как до "
                       "OptimaX.", "The records leave the change log. The system isn't touched: these settings are "
                       "already as they were before OptimaX."),
    "guard.forgotten": ("Забуто змін: {n}", "Забыто изменений: {n}", "Forgot {n} change(s)"),

    # ── обслуговування за розкладом ──
    "sched.title": ("Обслуговування за розкладом", "Обслуживание по расписанию", "Scheduled maintenance"),
    "sched.sub": ("Раз на тиждень OptimaX тихо прибирає тимчасові файли та звіти про збої і перевіряє сторожем, "
                  "чи не повернула Windows налаштування. Без перезавантажень і вікон.",
                  "Раз в неделю OptimaX тихо удаляет временные файлы и отчёты о сбоях и проверяет сторожем, не "
                  "вернула ли Windows настройки. Без перезагрузок и окон.",
                  "Once a week OptimaX quietly clears temp files and crash reports and runs the guard to see if "
                  "Windows reverted settings. No restarts, no windows."),
    "sched.enable": ("Щотижневе обслуговування", "Еженедельное обслуживание", "Weekly maintenance"),
    "sched.day": ("День", "День", "Day"),
    "sched.hour": ("Час", "Время", "Time"),
    "sched.run_now": ("Запустити зараз", "Запустить сейчас", "Run now"),
    "sched.never": ("Ще не запускалося.", "Ещё не запускалось.", "Hasn't run yet."),
    "sched.last": ("Останній раз: {when} · звільнено {mb} МБ · повернутих налаштувань: {n}.",
                   "Последний раз: {when} · освобождено {mb} МБ · возвращённых настроек: {n}.",
                   "Last run: {when} · freed {mb} MB · reverted settings: {n}."),
    "sched.on": ("Обслуговування: щотижня, {day} о {hour}:00", "Обслуживание: еженедельно, {day} в {hour}:00",
                 "Maintenance: weekly, {day} at {hour}:00"),
    "sched.off": ("Обслуговування за розкладом вимкнено", "Обслуживание по расписанию выключено",
                  "Scheduled maintenance off"),
    "maint.start": ("[►] Обслуговування: тимчасові файли, звіти про збої, перевірка налаштувань",
                    "[►] Обслуживание: временные файлы, отчёты о сбоях, проверка настроек",
                    "[►] Maintenance: temp files, crash reports, settings check"),
    "maint.done": ("  ✓ обслуговування завершено", "  ✓ обслуживание завершено", "  ✓ maintenance finished"),
    "day.0": ("Пн", "Пн", "Mon"), "day.1": ("Вт", "Вт", "Tue"), "day.2": ("Ср", "Ср", "Wed"),
    "day.3": ("Чт", "Чт", "Thu"), "day.4": ("Пт", "Пт", "Fri"), "day.5": ("Сб", "Сб", "Sat"),
    "day.6": ("Нд", "Вс", "Sun"),

    # ── гарячі клавіші ──
    "hk.title": ("Гарячі клавіші", "Горячие клавиши", "Hotkeys"),
    "hk.sub": ("Працюють у будь-якій програмі, навіть коли OptimaX згорнутий у трей.",
               "Работают в любой программе, даже когда OptimaX свёрнут в трей.",
               "Work in any app, even when OptimaX is minimized to the tray."),
    "hk.enable": ("Увімкнути гарячі клавіші", "Включить горячие клавиши", "Enable hotkeys"),
    "hk.boost": ("Увімкнути або вимкнути режим гри", "Включить или выключить режим игры", "Toggle game mode"),
    "hk.clean": ("Очистити оперативну пам'ять", "Очистить оперативную память", "Clean RAM"),
    "hk.on": ("Гарячі клавіші увімкнено", "Горячие клавиши включены", "Hotkeys on"),
    "hk.off": ("Гарячі клавіші вимкнено", "Горячие клавиши выключены", "Hotkeys off"),
    "hk.busy": ("Ці клавіші вже зайняті іншою програмою: {keys}", "Эти клавиши уже заняты другой программой: {keys}",
                "These keys are already taken by another app: {keys}"),

    # ── «Чому лагає?» ──
    "diag.sub": ("Що саме гальмує в грі, чи допомогли оптимізації, і звіт для форуму.",
                 "Что именно тормозит в игре, помогли ли оптимизации, и отчёт для форума.",
                 "What exactly slows your game down, whether tweaks helped, and a report for forums."),
    "diag.title": ("Чому лагає?", "Почему лагает?", "Why is it lagging?"),
    "diag.text": ("OptimaX стежить за процесором, відеокартою, пам'яттю, диском і температурами, поки ви граєте, "
                  "а потім пояснює простими словами, що саме заважає.",
                  "OptimaX следит за процессором, видеокартой, памятью, диском и температурами, пока вы играете, "
                  "а потом объясняет простыми словами, что именно мешает.",
                  "OptimaX watches the CPU, GPU, memory, disk and temperatures while you play, then explains in "
                  "plain words what is holding you back."),
    "diag.step1": ("Запустіть гру, яка лагає", "Запустите игру, которая лагает", "Launch the game that lags"),
    "diag.step2": ("Натисніть «Почати» тут", "Нажмите «Начать» здесь", "Press Start here"),
    "diag.step3": ("Грайте як зазвичай — гру визначимо за активним вікном",
                   "Играйте как обычно — игру определим по активному окну",
                   "Play as usual — the game is detected from the active window"),
    "diag.duration": ("Тривалість:", "Длительность:", "Duration:"),
    "diag.start": ("Почати діагностику", "Начать диагностику", "Start diagnostics"),
    "diag.collecting": ("Збираю показники… залишилось {s} с. Перейдіть у гру.",
                        "Собираю показатели… осталось {s} с. Перейдите в игру.",
                        "Collecting data… {s} s left. Switch to the game."),
    "diag.analyzing": ("Аналізую…", "Анализирую…", "Analyzing…"),
    "diag.done_log": ("  ✓ зібрано замірів: {n}, гра: {game}", "  ✓ собрано замеров: {n}, игра: {game}",
                      "  ✓ samples collected: {n}, game: {game}"),
    "diag.ready": ("Діагностику завершено — результат нижче", "Диагностика завершена — результат ниже",
                   "Diagnostics finished — see the results below"),
    "diag.result": ("Результат", "Результат", "Result"),
    "diag.head": ("Гра: {game} · замірів: {n}", "Игра: {game} · замеров: {n}", "Game: {game} · samples: {n}"),
    "diag.game_unknown": ("не визначено", "не определена", "not detected"),
    "diag.s.cpu": ("Процесор (середнє)", "Процессор (среднее)", "CPU (average)"),
    "diag.s.core": ("Найзавантаженіше ядро", "Самое загруженное ядро", "Busiest core"),
    "diag.s.gpu": ("Відеокарта", "Видеокарта", "GPU"),
    "diag.s.ram": ("Вільна пам'ять", "Свободная память", "Free RAM"),
    "diag.s.vram": ("Відеопам'ять", "Видеопамять", "VRAM"),
    "diag.s.disk": ("Диск зайнятий", "Диск занят", "Disk busy"),
    "diag.s.temp": ("Температура (макс.)", "Температура (макс.)", "Temperature (max)"),
    "diag.s.gpu_t": ("Відеокарта (макс.)", "Видеокарта (макс.)", "GPU temp (max)"),
    "diag.s.bg": ("Фонові процеси", "Фоновые процессы", "Background apps"),
    "diag.f.thermal.t": ("Перегрів: до {t}°C, система знижує частоту", "Перегрев: до {t}°C, система снижает частоту",
                         "Overheating: up to {t}°C, the system is throttling"),
    "diag.f.thermal.d": ("Процесор працює лише на {pct}% можливої частоти, щоб не перегрітися. Почистіть систему "
                         "охолодження від пилу, замініть термопасту, для ноутбука — підставка з вентилятором.",
                         "Процессор работает лишь на {pct}% возможной частоты, чтобы не перегреться. Почистите "
                         "охлаждение от пыли, замените термопасту, для ноутбука — подставка с вентилятором.",
                         "The CPU runs at only {pct}% of its possible clock to avoid overheating. Clean the cooler, "
                         "replace the thermal paste; for a laptop, use a cooling pad."),
    "diag.f.gpu_hot.t": ("Відеокарта гріється до {t}°C", "Видеокарта греется до {t}°C", "GPU reaches {t}°C"),
    "diag.f.gpu_hot.d": ("На такій температурі карта скидає частоти. Перевірте вентилятори й обдув корпусу, "
                         "налаштуйте криву кулерів в MSI Afterburner.",
                         "При такой температуре карта сбрасывает частоты. Проверьте вентиляторы и продув корпуса, "
                         "настройте кривую кулеров в MSI Afterburner.",
                         "At this temperature the card lowers clocks. Check fans and case airflow; set a fan curve "
                         "in MSI Afterburner."),
    "diag.f.power_limit.t": ("Процесор обмежено живленням ({pct}%)", "Процессор ограничен питанием ({pct}%)",
                             "CPU is power-limited ({pct}%)"),
    "diag.f.power_limit.d": ("Не через нагрів, а через план живлення або роботу від батареї. Увімкніть максимальну "
                             "продуктивність і грайте від розетки.",
                             "Не из-за нагрева, а из-за плана питания или работы от батареи. Включите максимальную "
                             "производительность и играйте от розетки.",
                             "Not heat — the power plan or running on battery. Turn on maximum performance and play "
                             "plugged in."),
    "diag.f.ram.t": ("Бракує оперативної пам'яті: вільно {free} з {total} ГБ",
                     "Не хватает оперативной памяти: свободно {free} из {total} ГБ",
                     "Not enough RAM: {free} of {total} GB free"),
    "diag.f.ram.d": ("Гра підвантажує дані з диска — звідси фризи. Закрийте браузер і зайві програми, увімкніть "
                     "чистильник пам'яті в «Іграх», а надовго допоможе більше пам'яті.",
                     "Игра подгружает данные с диска — отсюда фризы. Закройте браузер и лишние программы, включите "
                     "чистильщик памяти в «Играх», а надолго поможет больше памяти.",
                     "The game is paging to disk — that causes stutters. Close the browser and extra apps, turn on "
                     "the memory cleaner in Games; long-term, add more RAM."),
    "diag.f.vram.t": ("Закінчується відеопам'ять: {used} з {total} ГБ", "Заканчивается видеопамять: {used} из {total} ГБ",
                      "Running out of VRAM: {used} of {total} GB"),
    "diag.f.vram.d": ("Знизьте якість текстур на один рівень — це прибирає фризи майже без втрати картинки.",
                      "Снизьте качество текстур на один уровень — это убирает фризы почти без потери картинки.",
                      "Lower texture quality by one step — it removes stutters with almost no visual loss."),
    "diag.f.bg_hog.t": ("{name} забирає {pct}% процесора", "{name} забирает {pct}% процессора",
                        "{name} uses {pct}% of the CPU"),
    "diag.f.bg_hog.d": ("Фонова програма конкурує з грою. Закрийте її або увімкніть балансувальник фону в режимі "
                        "гри — він тимчасово знизить їй пріоритет.",
                        "Фоновая программа конкурирует с игрой. Закройте её или включите балансировщик фона в "
                        "режиме игры — он временно снизит ей приоритет.",
                        "A background app competes with the game. Close it or turn on the background balancer in "
                        "game mode — it lowers that app's priority for a while."),
    "diag.f.disk.t": ("Диск завантажений на {pct}%", "Диск загружен на {pct}%", "Disk is {pct}% busy"),
    "diag.f.disk.d": ("Гра чекає на диск. На HDD це головна причина фризів — перенесіть гру на SSD. Також "
                      "перевірте, чи не качаються оновлення.",
                      "Игра ждёт диск. На HDD это главная причина фризов — перенесите игру на SSD. Также "
                      "проверьте, не качаются ли обновления.",
                      "The game waits for the disk. On an HDD this is the main cause of stutters — move the game "
                      "to an SSD. Also check for downloads in progress."),
    "diag.f.cpu_bound.t": ("Упор у процесор: відеокарта завантажена лише на {gpu}%",
                           "Упор в процессор: видеокарта загружена лишь на {gpu}%",
                           "CPU-bound: the GPU is only {gpu}% busy"),
    "diag.f.cpu_bound.d": ("Процесор у середньому {cpu}%, найзавантаженіше ядро {core}%. Знизьте налаштування, що "
                           "вантажать процесор (дальність промальовки, натовпи, тіні), увімкніть режим гри й "
                           "«Ядра» для гри.",
                           "Процессор в среднем {cpu}%, самое загруженное ядро {core}%. Снизьте настройки, нагружающие "
                           "процессор (дальность прорисовки, толпы, тени), включите режим игры и «Ядра» для игры.",
                           "CPU averages {cpu}%, busiest core {core}%. Lower CPU-heavy settings (view distance, "
                           "crowds, shadows), turn on game mode and Cores for the game."),
    "diag.f.gpu_bound.t": ("Відеокарта працює на {gpu}% — так і має бути", "Видеокарта работает на {gpu}% — так и "
                           "должно быть", "The GPU runs at {gpu}% — as it should"),
    "diag.f.gpu_bound.d": ("Система не гальмує відеокарту. Більше FPS дадуть нижча роздільність, DLSS/FSR/XeSS або "
                           "простіші налаштування графіки.",
                           "Система не тормозит видеокарту. Больше FPS дадут меньшее разрешение, DLSS/FSR/XeSS или "
                           "более простые настройки графики.",
                           "Nothing holds the GPU back. For more FPS use a lower resolution, DLSS/FSR/XeSS or lighter "
                           "graphics settings."),
    "diag.f.none.t": ("Явних проблем не знайдено", "Явных проблем не найдено", "No obvious problems found"),
    "diag.f.none.d": ("Ні перегріву, ні нестачі пам'яті, ні фонових програм. Якщо гра все одно смикається — "
                      "зробіть тест FPS нижче й перевірте мережу на сторінці «Мережа».",
                      "Ни перегрева, ни нехватки памяти, ни фоновых программ. Если игра всё равно дёргается — "
                      "сделайте тест FPS ниже и проверьте сеть на странице «Сеть».",
                      "No overheating, memory shortage or background apps. If the game still stutters, run the FPS "
                      "test below and check the Network page."),

    # ── тест FPS ──
    "fps.title": ("Тест FPS «до і після»", "Тест FPS «до и после»", "Before/after FPS test"),
    "fps.sub": ("Замір середнього FPS, 1% і 0.1% low та фризів через PresentMon (відкритий інструмент Intel). "
                "Покаже, чи справді допомогли оптимізації.",
                "Замер среднего FPS, 1% и 0.1% low и фризов через PresentMon (открытый инструмент Intel). "
                "Покажет, действительно ли помогли оптимизации.",
                "Measures average FPS, 1% and 0.1% lows and stutters with PresentMon (Intel's open-source tool). "
                "Shows whether the tweaks actually helped."),
    "fps.pm_ok": ("PresentMon знайдено.", "PresentMon найден.", "PresentMon found."),
    "fps.pm_missing": ("Потрібен PresentMon (≈5 МБ, офіційний реліз на GitHub).",
                       "Нужен PresentMon (≈5 МБ, официальный релиз на GitHub).",
                       "PresentMon is needed (≈5 MB, official GitHub release)."),
    "fps.get_pm": ("Завантажити PresentMon", "Скачать PresentMon", "Download PresentMon"),
    "fps.get_pm_q": ("OptimaX завантажить консольну версію PresentMon з офіційної сторінки GameTechDev/PresentMon на "
                     "GitHub у папку даних програми.",
                     "OptimaX скачает консольную версию PresentMon с официальной страницы GameTechDev/PresentMon на "
                     "GitHub в папку данных программы.",
                     "OptimaX will download the console version of PresentMon from the official GameTechDev/PresentMon "
                     "GitHub page into its data folder."),
    "fps.download": ("Завантажити", "Скачать", "Download"),
    "fps.downloading": ("  · завантажую {name} ({mb} МБ)…", "  · скачиваю {name} ({mb} МБ)…",
                        "  · downloading {name} ({mb} MB)…"),
    "fps.downloaded": ("PresentMon готовий", "PresentMon готов", "PresentMon is ready"),
    "fps.no_asset": ("У релізі немає консольної версії PresentMon", "В релизе нет консольной версии PresentMon",
                     "The release has no console PresentMon build"),
    "fps.bad_download": ("Файл завантажився не повністю", "Файл скачался не полностью", "The download is incomplete"),
    "fps.dl_fail_t": ("Не вдалося завантажити PresentMon", "Не удалось скачать PresentMon", "Couldn't download PresentMon"),
    "fps.dl_fail_d": ("Відкрийте сторінку релізів, завантажте файл PresentMon-…-x64.exe і покладіть його в папку "
                      "tools поруч з OptimaX.",
                      "Откройте страницу релизов, скачайте файл PresentMon-…-x64.exe и положите его в папку tools "
                      "рядом с OptimaX.",
                      "Open the releases page, download PresentMon-…-x64.exe and put it in a tools folder next to "
                      "OptimaX."),
    "fps.open_page": ("Відкрити сторінку", "Открыть страницу", "Open page"),
    "fps.pick_game": ("Вибрати гру", "Выбрать игру", "Choose a game"),
    "fps.game": ("Гра: {name}", "Игра: {name}", "Game: {name}"),
    "fps.no_games": ("Додайте гру на сторінці «Ігри» або запустіть її — тоді вона з'явиться в списку.",
                     "Добавьте игру на странице «Игры» или запустите её — тогда она появится в списке.",
                     "Add a game on the Games page or launch it — then it appears in the list."),
    "fps.run_before": ("Замір «до»", "Замер «до»", "Measure before"),
    "fps.run_after": ("Замір «після»", "Замер «после»", "Measure after"),
    "fps.run_q": ("Запустіть {game} і зайдіть у звичну сцену (матч, локацію). Після «Почати» перейдіть у гру — "
                  "запис триватиме {s} с. Для чесного порівняння робіть заміри в одній і тій самій сцені.",
                  "Запустите {game} и зайдите в привычную сцену (матч, локацию). После «Начать» перейдите в игру — "
                  "запись продлится {s} с. Для честного сравнения делайте замеры в одной и той же сцене.",
                  "Launch {game} and go to a typical scene (match, area). After Start, switch to the game — recording "
                  "lasts {s} s. For a fair comparison, measure in the same scene both times."),
    "fps.start": ("Почати", "Начать", "Start"),
    "fps.recording": ("Записую кадри… залишилось {s} с", "Записываю кадры… осталось {s} с", "Recording frames… {s} s left"),
    "fps.result_log": ("  ✓ середній FPS {avg}, 1% low {low}", "  ✓ средний FPS {avg}, 1% low {low}",
                       "  ✓ average FPS {avg}, 1% low {low}"),
    "fps.saved": ("Замір збережено: {avg} FPS", "Замер сохранён: {avg} FPS", "Measurement saved: {avg} FPS"),
    "fps.no_pm": ("PresentMon не знайдено", "PresentMon не найден", "PresentMon not found"),
    "fps.no_frames": ("Немає кадрів від {exe} — гра запущена й не згорнута?", "Нет кадров от {exe} — игра запущена "
                      "и не свёрнута?", "No frames from {exe} — is the game running and not minimized?"),
    "fps.before": ("До", "До", "Before"),
    "fps.after": ("Після", "После", "After"),
    "fps.avg": ("Середній FPS", "Средний FPS", "Average FPS"),
    "fps.stutters": ("Фризи", "Фризы", "Stutters"),
    "fps.legend": ("Час кадру, мс: сіре — «до», синє — «після». Нижче й рівніше — краще.",
                   "Время кадра, мс: серое — «до», синее — «после». Ниже и ровнее — лучше.",
                   "Frame time, ms: grey — before, blue — after. Lower and flatter is better."),
    "fps.hint": ("Зробіть замір «до», застосуйте оптимізації, перезавантажтеся й зробіть замір «після».",
                 "Сделайте замер «до», примените оптимизации, перезагрузитесь и сделайте замер «после».",
                 "Measure before, apply tweaks, restart, then measure after."),
    "fps.v.better": ("Стало краще: FPS {avg}%, 1% low {low}%", "Стало лучше: FPS {avg}%, 1% low {low}%",
                     "Better: FPS {avg}%, 1% low {low}%"),
    "fps.v.same": ("Різниця в межах похибки: FPS {avg}%, 1% low {low}%", "Разница в пределах погрешности: FPS {avg}%, "
                   "1% low {low}%", "Within the margin of error: FPS {avg}%, 1% low {low}%"),
    "fps.v.worse": ("Стало гірше: FPS {avg}%, 1% low {low}% — можна відкотити зміни між замірами",
                    "Стало хуже: FPS {avg}%, 1% low {low}% — можно откатить изменения между замерами",
                    "Worse: FPS {avg}%, 1% low {low}% — you can roll back changes made between tests"),
    "fps.revert": ("Відкотити зміни між замірами", "Откатить изменения между замерами", "Roll back changes between tests"),
    "fps.revert_q": ("Між замірами «до» і «після» застосовано змін: {n}. Повернути їх як було?",
        "Между замерами «до» и «после» применено изменений: {n}. Вернуть их как было?",
        "Changes applied between the before and after tests: {n}. Roll them back?"),

    # ── звіт ──
    "rep.card": ("Звіт для форуму чи майстра", "Отчёт для форума или мастера", "Report for a forum or technician"),
    "rep.card_d": ("Залізо, перевірка збірки, застосовані зміни, остання діагностика, тести FPS і мережі — в одному "
                   "файлі. Без імені користувача й ключів.",
                   "Железо, проверка сборки, применённые изменения, последняя диагностика, тесты FPS и сети — в одном "
                   "файле. Без имени пользователя и ключей.",
                   "Hardware, build check, applied changes, last diagnostics, FPS and network tests — in one file. "
                   "No user name or keys."),
    "rep.save": ("Зберегти звіт (HTML)", "Сохранить отчёт (HTML)", "Save report (HTML)"),
    "rep.copy": ("Скопіювати як текст", "Скопировать как текст", "Copy as text"),
    "rep.saved": ("Звіт збережено", "Отчёт сохранён", "Report saved"),
    "rep.copied": ("Звіт скопійовано — вставте його в чат чи на форум", "Отчёт скопирован — вставьте его в чат или на "
                   "форум", "Report copied — paste it into a chat or forum"),
    "rep.title": ("звіт про систему", "отчёт о системе", "system report"),
    "rep.spec": ("Залізо", "Железо", "Hardware"),
    "rep.vendor": ("Виробник і модель", "Производитель и модель", "Vendor and model"),
    "rep.wear": ("знос", "износ", "wear"),
    "rep.analysis": ("Аналіз", "Анализ", "Analysis"),
    "rep.applied": ("Застосовані зміни ({n})", "Применённые изменения ({n})", "Applied changes ({n})"),
    "rep.none": ("немає", "нет", "none"),
    "rep.diag": ("Остання діагностика", "Последняя диагностика", "Last diagnostics"),
    "rep.game": ("Гра", "Игра", "Game"),
    "rep.fps": ("Тести FPS", "Тесты FPS", "FPS tests"),
    "rep.dns_best": ("Найшвидший DNS: {name}, {ms} мс", "Самый быстрый DNS: {name}, {ms} мс", "Fastest DNS: {name}, {ms} ms"),
    "rep.bb": ("Bufferbloat: {grade} (пінг {idle} → {loaded} мс під навантаженням)",
               "Bufferbloat: {grade} (пинг {idle} → {loaded} мс под нагрузкой)",
               "Bufferbloat: {grade} (ping {idle} → {loaded} ms under load)"),

    # ── мережа ──
    "net.sub": ("Найшвидший DNS, пінг до регіонів ігрових серверів і стабільність каналу під навантаженням.",
                "Самый быстрый DNS, пинг до регионов игровых серверов и стабильность канала под нагрузкой.",
                "Fastest DNS, ping to game-server regions and how stable your line is under load."),
    "net.dns.title": ("Найшвидший DNS", "Самый быстрый DNS", "Fastest DNS"),
    "net.dns.sub": ("DNS перетворює адреси сайтів і серверів на IP. Повільний DNS — довше відкриваються сайти, "
                    "лаунчери й підключення до матчів.",
                    "DNS превращает адреса сайтов и серверов в IP. Медленный DNS — дольше открываются сайты, "
                    "лаунчеры и подключение к матчам.",
                    "DNS turns site and server names into IPs. A slow DNS means slower sites, launchers and match "
                    "connections."),
    "net.dns.test": ("Перевірити DNS", "Проверить DNS", "Test DNS"),
    "net.dns.doh": ("Шифрувати запити (DNS-over-HTTPS, Windows 11)", "Шифровать запросы (DNS-over-HTTPS, Windows 11)",
                    "Encrypt lookups (DNS-over-HTTPS, Windows 11)"),
    "net.dns.restore": ("Повернути мій DNS", "Вернуть мой DNS", "Restore my DNS"),
    "net.dns.restored": ("DNS повернуто як було", "DNS возвращён как был", "DNS restored"),
    "net.dns.testing": ("Перевіряю {name}…", "Проверяю {name}…", "Testing {name}…"),
    "net.dns.result": ("  · {name}: {ms} мс, відповідей {ok}%", "  · {name}: {ms} мс, ответов {ok}%",
                       "  · {name}: {ms} ms, {ok}% answered"),
    "net.dns.current": ("Ваш поточний DNS", "Ваш текущий DNS", "Your current DNS"),
    "net.dns.best": ("найшвидший", "самый быстрый", "fastest"),
    "net.dns.yours": ("зараз", "сейчас", "current"),
    "net.dns.ok": ("{pct}% відповідей", "{pct}% ответов", "{pct}% answered"),
    "net.dns.use": ("Увімкнути", "Включить", "Use"),
    "net.dns.gain": ("{name} відповідає на {ms} мс швидше за ваш поточний DNS.",
                     "{name} отвечает на {ms} мс быстрее вашего текущего DNS.",
                     "{name} answers {ms} ms faster than your current DNS."),
    "net.dns.tweak": ("DNS: {name}", "DNS: {name}", "DNS: {name}"),
    "net.dns.set_iface": ("  · {alias}: DNS {ips}", "  · {alias}: DNS {ips}", "  · {alias}: DNS {ips}"),
    "net.dns.doh_on": ("  · DNS-over-HTTPS увімкнено (з резервом на звичайний DNS)",
                       "  · DNS-over-HTTPS включён (с резервом на обычный DNS)",
                       "  · DNS-over-HTTPS on (falls back to plain DNS)"),
    "net.dns.applied": ("DNS {name} увімкнено", "DNS {name} включён", "{name} DNS is on"),
    "net.ping.title": ("Пінг до регіонів ігрових серверів", "Пинг до регионов игровых серверов", "Ping to game-server regions"),
    "net.ping.sub": ("Час з'єднання з дата-центрами, де стоять сервери більшості онлайн-ігор, плюс джитер (стрибки "
                     "пінгу) і втрати. Ігрові компанії зазвичай не відповідають на звичайний ping, тому міряємо через "
                     "TCP-з'єднання.",
                     "Время соединения с дата-центрами, где стоят серверы большинства онлайн-игр, плюс джиттер "
                     "(скачки пинга) и потери. Игровые компании обычно не отвечают на обычный ping, поэтому меряем "
                     "через TCP-соединение.",
                     "Connection time to data centers that host most online games, plus jitter and loss. Game "
                     "companies usually ignore plain ping, so we measure TCP connection time."),
    "net.ping.run": ("Виміряти", "Измерить", "Measure"),
    "net.ping.custom_ph": ("IP або адреса сервера (можна :порт)", "IP или адрес сервера (можно :порт)",
                           "Server IP or address (optional :port)"),
    "net.ping.custom": ("Пінг", "Пинг", "Ping"),
    "net.ping.testing": ("Вимірюю {name}…", "Измеряю {name}…", "Measuring {name}…"),
    "net.ping.result": ("  · {name}: {avg} мс, джитер {jitter} мс, втрати {loss}%",
                        "  · {name}: {avg} мс, джиттер {jitter} мс, потери {loss}%",
                        "  · {name}: {avg} ms, jitter {jitter} ms, loss {loss}%"),
    "net.ping.jl": ("джитер {j} мс · втрати {l}%", "джиттер {j} мс · потери {l}%", "jitter {j} ms · loss {l}%"),
    "net.ping.base": ("найближчий вузол", "ближайший узел", "nearest node"),
    "net.r.cloudflare": ("Cloudflare", "Cloudflare", "Cloudflare"),
    "net.r.google": ("Google", "Google", "Google"),
    "net.r.custom": ("Свій сервер", "Свой сервер", "Custom server"),
    "net.r.eu-central-1": ("Франкфурт", "Франкфурт", "Frankfurt"),
    "net.r.eu-north-1": ("Стокгольм", "Стокгольм", "Stockholm"),
    "net.r.eu-west-1": ("Ірландія", "Ирландия", "Ireland"),
    "net.r.eu-west-2": ("Лондон", "Лондон", "London"),
    "net.r.eu-west-3": ("Париж", "Париж", "Paris"),
    "net.r.eu-south-1": ("Мілан", "Милан", "Milan"),
    "net.r.me-central-1": ("ОАЕ", "ОАЭ", "UAE"),
    "net.r.us-east-1": ("США, схід", "США, восток", "US East"),
    "net.r.us-west-2": ("США, захід", "США, запад", "US West"),
    "net.r.ap-southeast-1": ("Сінгапур", "Сингапур", "Singapore"),
    "net.r.ap-northeast-1": ("Токіо", "Токио", "Tokyo"),
    "net.r.sa-east-1": ("Сан-Паулу", "Сан-Паулу", "São Paulo"),
    "net.bb.title": ("Bufferbloat: пінг під навантаженням", "Bufferbloat: пинг под нагрузкой", "Bufferbloat: ping under load"),
    "net.bb.sub": ("Коли хтось вдома дивиться відео чи качає гру, пінг у вас може стрибати в рази. Тест "
                   "завантажує канал на ~10 секунд і дивиться, наскільки зростає затримка.",
                   "Когда кто-то дома смотрит видео или качает игру, пинг у вас может прыгать в разы. Тест "
                   "загружает канал на ~10 секунд и смотрит, насколько растёт задержка.",
                   "When someone at home streams or downloads, your ping can spike. The test loads your line for "
                   "~10 seconds and checks how much latency grows."),
    "net.bb.run": ("Почати тест (~15 с)", "Начать тест (~15 с)", "Start test (~15 s)"),
    "net.bb.idle": ("Міряю пінг без навантаження…", "Меряю пинг без нагрузки…", "Measuring idle ping…"),
    "net.bb.loaded": ("Міряю пінг під час завантаження…", "Меряю пинг во время загрузки…",
                      "Measuring ping during a download…"),
    "net.bb.running": ("Тест триває…", "Тест идёт…", "Testing…"),
    "net.bb.fail": ("Не вдалося виміряти — перевірте підключення до інтернету",
                    "Не удалось измерить — проверьте подключение к интернету",
                    "Measurement failed — check your internet connection"),
    "net.bb.result": ("  ✓ оцінка {grade}: пінг {idle} → {loaded} мс (+{increase}), швидкість {mbps} Мбіт/с",
                      "  ✓ оценка {grade}: пинг {idle} → {loaded} мс (+{increase}), скорость {mbps} Мбит/с",
                      "  ✓ grade {grade}: ping {idle} → {loaded} ms (+{increase}), speed {mbps} Mbit/s"),
    "net.bb.line": ("Пінг {idle} мс у спокої → {loaded} мс під навантаженням (+{inc} мс). Швидкість ~{mbps} Мбіт/с.",
                    "Пинг {idle} мс в покое → {loaded} мс под нагрузкой (+{inc} мс). Скорость ~{mbps} Мбит/с.",
                    "Ping {idle} ms idle → {loaded} ms under load (+{inc} ms). Speed ~{mbps} Mbit/s."),
    "net.bb.tip_good": ("Канал тримає навантаження — можна грати, навіть коли вдома дивляться відео.",
                        "Канал держит нагрузку — можно играть, даже когда дома смотрят видео.",
                        "Your line handles load well — you can play while others stream."),
    "net.bb.tip_bad": ("Пінг сильно росте під навантаженням. Увімкніть у роутері SQM / Smart QoS / «пріоритет ігор» "
                       "або обмежте швидкість завантажень на ~90% від тарифу.",
                       "Пинг сильно растёт под нагрузкой. Включите в роутере SQM / Smart QoS / «приоритет игр» "
                       "или ограничьте скорость загрузок до ~90% от тарифа.",
                       "Ping rises a lot under load. Turn on SQM / Smart QoS / gaming priority in your router or cap "
                       "downloads at ~90% of your plan."),
    "net.tweaks_t": ("Мережеві оптимізації", "Сетевые оптимизации", "Network tweaks"),
    "net.tweaks_d": ("Nagle, буфери, енергозбереження адаптерів, Wi-Fi і Ethernet для ігор — у експертному меню.",
                     "Nagle, буферы, энергосбережение адаптеров, Wi-Fi и Ethernet для игр — в экспертном меню.",
                     "Nagle, buffers, adapter power saving, Wi-Fi and Ethernet for gaming — in the expert menu."),
    "net.tweaks_btn": ("Відкрити розділ «Мережа»", "Открыть раздел «Сеть»", "Open the Network section"),

    # ── програми ──
    "apps.sub": ("Оновлення всіх програм одним кліком і встановлення потрібного на нову систему — через winget, "
                 "без пошуку інсталяторів по сайтах.",
                 "Обновление всех программ одним кликом и установка нужного на новую систему — через winget, без "
                 "поиска установщиков по сайтам.",
                 "Update all apps in one click and install essentials on a fresh system — via winget, no hunting "
                 "for installers."),
    "apps.no_winget": ("winget не знайдено", "winget не найден", "winget not found"),
    "apps.no_winget_d": ("Встановіть «Інсталятор програм» (App Installer) з Microsoft Store — winget входить до нього.",
                         "Установите «Установщик приложений» (App Installer) из Microsoft Store — winget входит в него.",
                         "Install App Installer from the Microsoft Store — winget comes with it."),
    "apps.get_winget": ("Відкрити Microsoft Store", "Открыть Microsoft Store", "Open Microsoft Store"),
    "apps.upd": ("Оновлення програм", "Обновления программ", "App updates"),
    "apps.upd_d": ("Знайдемо застарілі версії встановлених програм і оновимо вибрані або всі.",
                   "Найдём устаревшие версии установленных программ и обновим выбранные или все.",
                   "Find outdated installed apps and update the selected ones or all of them."),
    "apps.check": ("Перевірити оновлення", "Проверить обновления", "Check for updates"),
    "apps.checking": ("Перевіряю оновлення…", "Проверяю обновления…", "Checking for updates…"),
    "apps.found_upd": ("  · знайдено оновлень: {n}", "  · найдено обновлений: {n}", "  · updates found: {n}"),
    "apps.all_fresh": ("Усі програми оновлені.", "Все программы обновлены.", "All apps are up to date."),
    "apps.upd_sel": ("Оновити вибрані", "Обновить выбранные", "Update selected"),
    "apps.upd_sel_n": ("Оновити вибрані ({n})", "Обновить выбранные ({n})", "Update selected ({n})"),
    "apps.upd_all": ("Оновити все", "Обновить всё", "Update all"),
    "apps.upd_title": ("Оновлення програм", "Обновление программ", "Updating apps"),
    "apps.inst": ("Встановити програми", "Установить программы", "Install apps"),
    "apps.inst_d": ("Популярні програми для ігор і роботи з офіційних джерел. Встановлені вже позначено.",
                    "Популярные программы для игр и работы из официальных источников. Установленные уже отмечены.",
                    "Popular apps for gaming and work from official sources. Installed ones are marked."),
    "apps.inst_state": ("Перевіряю, що вже встановлено…", "Проверяю, что уже установлено…", "Checking what's installed…"),
    "apps.inst_found": ("Уже встановлено: {n} з {total}.", "Уже установлено: {n} из {total}.",
                        "Already installed: {n} of {total}."),
    "apps.installed": ("Уже встановлено", "Уже установлено", "Already installed"),
    "apps.scan": ("Оновити список", "Обновить список", "Refresh list"),
    "apps.install": ("Встановити вибрані", "Установить выбранные", "Install selected"),
    "apps.install_n": ("Встановити вибрані ({n})", "Установить выбранные ({n})", "Install selected ({n})"),
    "apps.inst_title": ("Встановлення програм", "Установка программ", "Installing apps"),
    "apps.fail_code": ("  ✗ winget повернув код {rc}", "  ✗ winget вернул код {rc}", "  ✗ winget returned code {rc}"),
    "apps.summary": (" Готово: успішно {ok}, з помилкою {fail}.", " Готово: успешно {ok}, с ошибкой {fail}.",
                     " Done: {ok} succeeded, {fail} failed."),
    "apps.cat.games": ("Ігрові лаунчери", "Игровые лаунчеры", "Game launchers"),
    "apps.cat.chat": ("Спілкування", "Общение", "Chat"),
    "apps.cat.browsers": ("Браузери", "Браузеры", "Browsers"),
    "apps.cat.tools": ("Утиліти", "Утилиты", "Utilities"),
    "apps.cat.hw": ("Залізо й моніторинг", "Железо и мониторинг", "Hardware and monitoring"),
    "apps.cat.runtime": ("Бібліотеки для ігор", "Библиотеки для игр", "Game runtimes"),

    # ── очищення: вкладки, місце на диску, драйвери ──
    "cl.tab.clean": ("Очищення", "Очистка", "Cleanup"),
    "cl.tab.disk": ("Що займає місце", "Что занимает место", "What uses space"),
    "cl.tab.drivers": ("Старі драйвери", "Старые драйверы", "Old drivers"),
    "disk.title": ("Що займає місце", "Что занимает место", "What uses space"),
    "disk.sub": ("Найбільші папки й файли на диску — як у WizTree. Нічого не видаляє, лише показує.",
                 "Самые большие папки и файлы на диске — как в WizTree. Ничего не удаляет, только показывает.",
                 "The largest folders and files on a drive — like WizTree. Shows only, deletes nothing."),
    "disk.pick": ("Вибрати папку", "Выбрать папку", "Choose folder"),
    "disk.scan": ("Сканувати", "Сканировать", "Scan"),
    "disk.scanning": ("Сканую… файлів: {n} · {path}", "Сканирую… файлов: {n} · {path}", "Scanning… files: {n} · {path}"),
    "disk.done": ("Готово: файлів {n}, разом {size}",
        "Готово: файлов {n}, всего {size}",
        "Done: {n} files, {size} total"),
    "disk.up": ("↑ Вгору", "↑ Вверх", "↑ Up"),
    "disk.open": ("Відкрити в Провіднику", "Открыть в Проводнике", "Open in Explorer"),
    "disk.enter": ("Відкрити", "Открыть", "Open"),
    "disk.here": ("Файли в цій папці", "Файлы в этой папке", "Files in this folder"),
    "disk.empty": ("Папка порожня або недоступна.", "Папка пуста или недоступна.", "The folder is empty or inaccessible."),
    "disk.files": ("Найбільші файли", "Самые большие файлы", "Largest files"),
    "disk.files_d": ("Часто це забуті архіви, образи дисків і записи відео.",
                     "Часто это забытые архивы, образы дисков и записи видео.",
                     "Often forgotten archives, disk images and video recordings."),
    "drv.title": ("Старі версії драйверів", "Старые версии драйверов", "Old driver versions"),
    "drv.sub": ("Після кожного оновлення драйвера Windows залишає попередню версію у сховищі драйверів. Особливо "
                "багато місця займають старі драйвери відеокарти.",
                "После каждого обновления драйвера Windows оставляет предыдущую версию в хранилище драйверов. "
                "Особенно много места занимают старые драйверы видеокарты.",
                "After every driver update Windows keeps the previous version in the driver store. Old GPU drivers "
                "take the most space."),
    "drv.find": ("Знайти старі драйвери", "Найти старые драйверы", "Find old drivers"),
    "drv.searching": ("Шукаю в сховищі драйверів… (до хвилини)", "Ищу в хранилище драйверов… (до минуты)",
                      "Searching the driver store… (up to a minute)"),
    "drv.found": ("  · старих версій: {n}, разом {mb} МБ", "  · старых версий: {n}, всего {mb} МБ",
                  "  · old versions: {n}, {mb} MB total"),
    "drv.row": ("версія {ver} від {date} · {inf} ({orig})", "версия {ver} от {date} · {inf} ({orig})",
                "version {ver} from {date} · {inf} ({orig})"),
    "drv.none": ("Старих версій не знайдено — сховище в порядку.", "Старых версий не найдено — хранилище в порядке.",
                 "No old versions found — the store is clean."),
    "drv.total": ("Вибрано: {n} · {size}",
        "Выбрано: {n} · {size}",
        "Selected: {n} · {size}"),
    "drv.delete": ("Видалити вибрані", "Удалить выбранные", "Delete selected"),
    "drv.delete_q": ("Видалити старі версії драйверів ({n})? Найновіші й ті, що використовуються пристроями, OptimaX не чіпає. Відкотити видалення не можна.",
        "Удалить старые версии драйверов ({n})? Самые новые и используемые устройствами OptimaX не трогает. Отменить удаление нельзя.",
        "Delete old driver versions ({n})? The newest ones and those in use are never touched. This can't be undone."),
    "drv.deleted": ("  ✓ {inf}: {prov} {ver} видалено", "  ✓ {inf}: {prov} {ver} удалён", "  ✓ {inf}: {prov} {ver} deleted"),
    "drv.kept": ("  · {inf}: Windows не дала видалити (використовується) — залишено",
                 "  · {inf}: Windows не дала удалить (используется) — оставлен",
                 "  · {inf}: Windows refused (in use) — kept"),
    "drv.summary": (" Видалено версій: {n}", " Удалено версий: {n}", " Versions deleted: {n}"),
    "drv.note": ("Видаляються лише старі версії, які не використовує жоден пристрій. Найновіша версія кожного "
                 "драйвера завжди залишається.",
                 "Удаляются только старые версии, которые не использует ни одно устройство. Самая новая версия "
                 "каждого драйвера всегда остаётся.",
                 "Only old versions not used by any device are removed. The newest version of every driver always "
                 "stays."),

    # ── ноутбук: частота екрана й ліміт заряду ──
    "rfp.title": ("Частота екрана від живлення", "Частота экрана от питания", "Refresh rate by power source"),
    "rfp.sub": ("На батареї екран працює на 60 Гц, від зарядки — на максимальній частоті. 120–240 Гц помітно "
                "з'їдають заряд. Працює, поки OptimaX запущений (можна в треї).",
                "На батарее экран работает на 60 Гц, от зарядки — на максимальной частоте. 120–240 Гц заметно "
                "съедают заряд. Работает, пока OptimaX запущен (можно в трее).",
                "On battery the screen runs at 60 Hz, plugged in — at its maximum. 120–240 Hz drain the battery "
                "noticeably. Works while OptimaX is running (tray is fine)."),
    "rfp.enable": ("Перемикати частоту автоматично", "Переключать частоту автоматически", "Switch refresh rate automatically"),
    "rfp.battery_hz": ("На батареї:", "На батарее:", "On battery:"),
    "rfp.state": ("Зараз {hz} Гц, {src}. Доступно: {rates} Гц.", "Сейчас {hz} Гц, {src}. Доступно: {rates} Гц.",
                  "Now {hz} Hz, {src}. Available: {rates} Hz."),
    "rfp.ac": ("від мережі", "от сети", "plugged in"),
    "rfp.dc": ("від батареї", "от батареи", "on battery"),
    "rfp.on": ("Частота перемикатиметься автоматично", "Частота будет переключаться автоматически",
               "Refresh rate will switch automatically"),
    "rfp.off": ("Автоматичне перемикання частоти вимкнено", "Автоматическое переключение частоты выключено",
                "Automatic refresh switching off"),
    "rfp.switched": ("🖥 Екран: {hz} Гц ({src})", "🖥 Экран: {hz} Гц ({src})", "🖥 Display: {hz} Hz ({src})"),
    "chg.title": ("Ліміт заряду батареї", "Лимит заряда батареи", "Battery charge limit"),
    "chg.sub": ("Якщо ноутбук майже завжди на зарядці, заряд до 80% уповільнює знос батареї в рази.",
                "Если ноутбук почти всегда на зарядке, заряд до 80% замедляет износ батареи в разы.",
                "If the laptop is almost always plugged in, charging to 80% slows battery wear several times."),
    "chg.limit": ("Заряджати до:", "Заряжать до:", "Charge up to:"),
    "chg.limit_set": ("Ліміт заряду: {pct}%", "Лимит заряда: {pct}%", "Charge limit: {pct}%"),
    "chg.limit_fail": ("  ⚠ не вдалося змінити ліміт: {msg}", "  ⚠ не удалось изменить лимит: {msg}",
                       "  ⚠ couldn't change the limit: {msg}"),
    "chg.note.asus": ("Через ASUS ATK WMI, як у MyASUS. Частина моделей скидає ліміт після перезавантаження — "
                      "OptimaX повторює налаштування під час кожного запуску.",
                      "Через ASUS ATK WMI, как в MyASUS. Часть моделей сбрасывает лимит после перезагрузки — "
                      "OptimaX повторяет настройку при каждом запуске.",
                      "Via ASUS ATK WMI, like MyASUS. Some models reset the limit after a restart — OptimaX re-applies "
                      "it on every launch."),
    "chg.note.dell": ("Через Dell Command | Configure. 80% — це режим Custom 50–80%.",
                      "Через Dell Command | Configure. 80% — это режим Custom 50–80%.",
                      "Via Dell Command | Configure. 80% means Custom 50–80% mode."),
    "chg.hint.lenovo": ("Lenovo: відкрийте Lenovo Vantage → Пристрій → Живлення → «Режим збереження» "
                        "(Conservation mode) — заряд до 55–80%.",
                        "Lenovo: откройте Lenovo Vantage → Устройство → Питание → «Режим сбережения» (Conservation "
                        "mode) — заряд до 55–80%.",
                        "Lenovo: open Lenovo Vantage → Device → Power → Conservation mode — charges to 55–80%."),
    "chg.hint.hp": ("HP: увімкніть «Adaptive Battery Optimizer» або «Battery Care» у BIOS (F10) чи в HP Support "
                    "Assistant.", "HP: включите «Adaptive Battery Optimizer» или «Battery Care» в BIOS (F10) или в "
                    "HP Support Assistant.", "HP: turn on Adaptive Battery Optimizer or Battery Care in BIOS (F10) "
                    "or HP Support Assistant."),
    "chg.hint.msi": ("MSI: MSI Center → Battery Master → «Best for Battery» (заряд до 60–80%).",
                     "MSI: MSI Center → Battery Master → «Best for Battery» (заряд до 60–80%).",
                     "MSI: MSI Center → Battery Master → Best for Battery (charges to 60–80%)."),
    "chg.hint.huawei": ("Huawei/Honor: PC Manager → Налаштування → Батарея → «Розумна зарядка».",
                        "Huawei/Honor: PC Manager → Настройки → Батарея → «Умная зарядка».",
                        "Huawei/Honor: PC Manager → Settings → Battery → Smart charging."),
    "chg.hint.samsung": ("Samsung: Samsung Settings → Батарея → «Захист батареї» (до 85%).",
                         "Samsung: Samsung Settings → Батарея → «Защита батареи» (до 85%).",
                         "Samsung: Samsung Settings → Battery → Protect battery (up to 85%)."),
    "chg.hint.acer": ("Acer: Acer Care Center → Battery → «Battery Charge Limit» (до 80%).",
                      "Acer: Acer Care Center → Battery → «Battery Charge Limit» (до 80%).",
                      "Acer: Acer Care Center → Battery → Battery Charge Limit (80%)."),
    "chg.hint.gigabyte": ("Gigabyte/Aorus: Control Center → Battery → «Custom Mode» з лімітом заряду.",
                          "Gigabyte/Aorus: Control Center → Battery → «Custom Mode» с лимитом заряда.",
                          "Gigabyte/Aorus: Control Center → Battery → Custom Mode with a charge limit."),
    "chg.hint.surface": ("Surface: увімкніть «Battery Limit» (до 50%) в UEFI або «Smart Charging» у Surface app.",
                         "Surface: включите «Battery Limit» (до 50%) в UEFI или «Smart Charging» в Surface app.",
                         "Surface: turn on Battery Limit (50%) in UEFI or Smart Charging in the Surface app."),
    "chg.hint.razer": ("Razer: Razer Synapse → Продуктивність → «Battery Health Optimizer».",
                       "Razer: Razer Synapse → Производительность → «Battery Health Optimizer».",
                       "Razer: Razer Synapse → Performance → Battery Health Optimizer."),
    "chg.hint.xiaomi": ("Xiaomi/RedmiBook: Xiaomi PC Manager → Батарея → «Режим захисту батареї».",
                        "Xiaomi/RedmiBook: Xiaomi PC Manager → Батарея → «Режим защиты батареи».",
                        "Xiaomi/RedmiBook: Xiaomi PC Manager → Battery → Battery protection mode."),
    "chg.hint.dell": ("Dell: встановіть Dell Command | Configure або використайте Dell Power Manager → «Переважно "
                      "від мережі» — тоді OptimaX зможе змінювати ліміт сам.",
                      "Dell: установите Dell Command | Configure или используйте Dell Power Manager → «Преимущественно "
                      "от сети» — тогда OptimaX сможет менять лимит сам.",
                      "Dell: install Dell Command | Configure or use Dell Power Manager → Primarily AC — then OptimaX "
                      "can change the limit itself."),
    "chg.hint.asus": ("ASUS: не знайдено драйвер ATK. Встановіть «ASUS System Control Interface» або використайте "
                      "MyASUS → Battery Health Charging.",
                      "ASUS: не найден драйвер ATK. Установите «ASUS System Control Interface» или используйте "
                      "MyASUS → Battery Health Charging.",
                      "ASUS: the ATK driver wasn't found. Install ASUS System Control Interface or use MyASUS → "
                      "Battery Health Charging."),
    "chg.hint.other": ("Цей виробник не дає змінювати ліміт із Windows. Пошукайте «Battery Care», «Battery Health» "
                       "чи «Charge Limit» у фірмовій утиліті ноутбука або в BIOS.",
                       "Этот производитель не даёт менять лимит из Windows. Поищите «Battery Care», «Battery Health» "
                       "или «Charge Limit» в фирменной утилите ноутбука или в BIOS.",
                       "This vendor doesn't let Windows change the limit. Look for Battery Care, Battery Health or "
                       "Charge Limit in the laptop's own utility or BIOS."),

    # ── нові перевірки збірки ──
    "bc.disk.info.t": ("Windows стоїть на HDD, хоча є SSD", "Windows стоит на HDD, хотя есть SSD",
                       "Windows is on an HDD although you have an SSD"),
    "bc.disk.info.d": ("{ssd} простоює. Перенесення Windows на SSD — найбільше прискорення для цього ПК.",
                       "{ssd} простаивает. Перенос Windows на SSD — самое большое ускорение для этого ПК.",
                       "{ssd} sits idle. Moving Windows to the SSD is the biggest speed-up for this PC."),
    "bc.health.ok.t": ("Диски в нормі ({n})", "Диски в норме ({n})", "Drives are healthy ({n})"),
    "bc.health.ok.d": ("SMART не повідомляє про проблеми, знос і температура в межах норми.",
                       "SMART не сообщает о проблемах, износ и температура в норме.",
                       "SMART reports no problems; wear and temperature are normal."),
    "bc.health.health_bad.t": ("Диск {name}: стан «{state}»", "Диск {name}: состояние «{state}»",
                               "Drive {name}: status \"{state}\""),
    "bc.health.health_bad.d": ("Диск повідомляє про несправність. Негайно скопіюйте важливі файли.",
                               "Диск сообщает о неисправности. Немедленно скопируйте важные файлы.",
                               "The drive reports a fault. Back up important files now."),
    "bc.health.wear_high.t": ("SSD {name} зношений на {wear}%", "SSD {name} изношен на {wear}%",
                              "SSD {name} is {wear}% worn"),
    "bc.health.wear_high.d": ("Ресурс запису майже вичерпано. Плануйте заміну й тримайте резервні копії.",
                              "Ресурс записи почти исчерпан. Планируйте замену и держите резервные копии.",
                              "Write endurance is nearly used up. Plan a replacement and keep backups."),
    "bc.health.wear_mid.t": ("SSD {name}: використано {wear}% ресурсу", "SSD {name}: использовано {wear}% ресурса",
                             "SSD {name}: {wear}% of endurance used"),
    "bc.health.wear_mid.d": ("Ще попрацює, але варто стежити й не тримати диск заповненим під зав'язку.",
                             "Ещё поработает, но стоит следить и не держать диск заполненным под завязку.",
                             "It will last a while, but keep an eye on it and don't fill it to the brim."),
    "bc.health.hot.t": ("Диск {name} гріється до {temp}°C", "Диск {name} греется до {temp}°C",
                        "Drive {name} reaches {temp}°C"),
    "bc.health.hot.d": ("На такій температурі NVMe скидає швидкість. Допоможе радіатор на SSD або обдув.",
                        "При такой температуре NVMe сбрасывает скорость. Поможет радиатор на SSD или продув.",
                        "At this temperature NVMe drives slow down. A heatsink or airflow helps."),
    "bc.games_hdd.info.t": ("Ігри на HDD: {games}", "Игры на HDD: {games}", "Games on an HDD: {games}"),
    "bc.games_hdd.info.d": ("На SSD ({ssd}) вони завантажуватимуться в рази швидше й менше фризитимуть. Steam і інші "
                            "лаунчери вміють переносити ігри без перевстановлення.",
                            "На SSD ({ssd}) они будут загружаться в разы быстрее и меньше фризить. Steam и другие "
                            "лаунчеры умеют переносить игры без переустановки.",
                            "On the SSD ({ssd}) they'd load several times faster and stutter less. Steam and other "
                            "launchers can move games without reinstalling."),
    "bc.display.warn.t": ("Монітор під'єднано до материнської плати", "Монитор подключён к материнской плате",
                          "The monitor is plugged into the motherboard"),
    "bc.display.warn.d": ("Зображення йде через вбудовану графіку ({igpu}), а {dgpu} майже не працює. Перекиньте "
                          "кабель монітора у роз'єм відеокарти — FPS виросте в рази.",
                          "Изображение идёт через встроенную графику ({igpu}), а {dgpu} почти не работает. "
                          "Переключите кабель монитора в разъём видеокарты — FPS вырастет в разы.",
                          "The picture goes through integrated graphics ({igpu}) while {dgpu} barely works. Move the "
                          "monitor cable to the graphics card — FPS will multiply."),
    "bc.display.ok.t": ("Монітор під'єднано до відеокарти", "Монитор подключён к видеокарте",
                        "The monitor is plugged into the graphics card"),
    "bc.display.ok.d": ("{gpu}", "{gpu}", "{gpu}"),
    "bc.mining.info.t": ("Майнінгова відеокарта {model}", "Майнинговая видеокарта {model}", "Mining graphics card {model}"),
    "bc.mining.info.d": ("{gpu} — це {model} без власних відеовиходів, тож монітор у материнській платі ({shown}) — "
                         "правильно. Ігри мають іти на {model}: як це налаштувати й чого уникати — у підказці.",
                         "{gpu} — это {model} без собственных видеовыходов, так что монитор в материнской плате "
                         "({shown}) — правильно. Игры должны идти на {model}: как это настроить и чего избегать — "
                         "в подсказке.",
                         "{gpu} is a {model} with no video outputs of its own, so the monitor belongs in the "
                         "motherboard ({shown}). Games should run on the {model}: see the hint for how to set it up "
                         "and what to avoid."),
    "bc.pcie.warn.t": ("Відеокарта працює на PCIe x{cur} замість x{max}", "Видеокарта работает на PCIe x{cur} вместо "
                       "x{max}", "The graphics card runs at PCIe x{cur} instead of x{max}"),
    "bc.pcie.warn.d": ("{gpu} отримує менше ліній, ніж може. Зазвичай карта стоїть не в тому слоті, заважає "
                       "райзер або поганий контакт.",
                       "{gpu} получает меньше линий, чем может. Обычно карта стоит не в том слоте, мешает райзер или "
                       "плохой контакт.",
                       "{gpu} gets fewer lanes than it can use. Usually it's in the wrong slot, on a riser or has a "
                       "poor contact."),
    "bc.pcie.ok.t": ("PCIe відеокарти: x{cur}", "PCIe видеокарты: x{cur}", "Graphics card PCIe: x{cur}"),
    "bc.pcie.ok.d": ("Лінія працює на повну ширину. Швидкість у простої знижується — це нормально.",
                     "Линия работает на полную ширину. Скорость в простое снижается — это нормально.",
                     "The link runs at full width. Speed drops at idle — that's normal."),
    "bc.rebar.ok.t": ("Resizable BAR увімкнено", "Resizable BAR включён", "Resizable BAR is on"),
    "bc.rebar.ok.d": ("{gpu} бачить усю відеопам'ять одразу.", "{gpu} видит всю видеопамять сразу.",
                      "{gpu} can see all of its VRAM at once."),
    "bc.rebar.warn.t": ("Resizable BAR вимкнено — Intel Arc втрачає багато FPS", "Resizable BAR выключен — Intel Arc "
                        "теряет много FPS", "Resizable BAR is off — Intel Arc loses a lot of FPS"),
    "bc.rebar.warn.d": ("Для {gpu} це обов'язково: увімкніть у BIOS «Above 4G Decoding» і «Re-Size BAR Support».",
                        "Для {gpu} это обязательно: включите в BIOS «Above 4G Decoding» и «Re-Size BAR Support».",
                        "For {gpu} it's essential: enable Above 4G Decoding and Re-Size BAR Support in BIOS."),
    "bc.rebar.info.t": ("Resizable BAR вимкнено", "Resizable BAR выключен", "Resizable BAR is off"),
    "bc.rebar.info.d": ("{gpu} підтримує його: у частині ігор це +2–10% FPS. Увімкніть у BIOS «Above 4G Decoding» і "
                        "«Re-Size BAR» (у AMD — Smart Access Memory).",
                        "{gpu} поддерживает его: в части игр это +2–10% FPS. Включите в BIOS «Above 4G Decoding» и "
                        "«Re-Size BAR» (у AMD — Smart Access Memory).",
                        "{gpu} supports it: +2–10% FPS in some games. Enable Above 4G Decoding and Re-Size BAR (Smart "
                        "Access Memory on AMD) in BIOS."),
    "bc.thermal.warn.t": ("Система вже знижує частоту через нагрів ({pct}%)", "Система уже снижает частоту из-за "
                          "нагрева ({pct}%)", "The system is already throttling from heat ({pct}%)"),
    "bc.thermal.warn.d": ("Навіть без навантаження. Запустіть «Чому лагає?» під час гри, щоб побачити, наскільки "
                          "все погано.", "Даже без нагрузки. Запустите «Почему лагает?» во время игры, чтобы увидеть, "
                          "насколько всё плохо.", "Even at idle. Run Why is it lagging? during a game to see how bad "
                          "it gets."),
    "bc.thermal.hot.t": ("{t}°C без навантаження", "{t}°C без нагрузки", "{t}°C at idle"),
    "bc.thermal.hot.d": ("Це забагато для простою: найімовірніше, пил у радіаторі або висохла термопаста.",
                         "Это слишком много для простоя: скорее всего, пыль в радиаторе или высохшая термопаста.",
                         "Too hot for idle: most likely dust in the heatsink or dried thermal paste."),
    "bc.thermal.info.t": ("Тепло в простої: {t}°C", "Тепло в простое: {t}°C", "Warm at idle: {t}°C"),
    "bc.thermal.info.d": ("Ще не критично, але під навантаженням може почати скидати частоти.",
                          "Ещё не критично, но под нагрузкой может начать сбрасывать частоты.",
                          "Not critical yet, but it may throttle under load."),
    "bc.thermal.gpu.t": ("Відеокарта в простої: {t}°C", "Видеокарта в простое: {t}°C", "GPU at idle: {t}°C"),
    "bc.thermal.gpu.d": ("Для простою тепло. Перевірте, чи крутяться вентилятори й чи є обдув корпусу.",
                         "Для простоя тепло. Проверьте, крутятся ли вентиляторы и есть ли продув корпуса.",
                         "Warm for idle. Check that the fans spin and the case has airflow."),
    "bc.thermal.ok.t": ("Температура в простої: {t}°C", "Температура в простое: {t}°C", "Idle temperature: {t}°C"),
    "bc.thermal.ok.d": ("У нормі.", "В норме.", "Normal."),
    "hint.move_ssd.t": ("Як перенести на SSD", "Как перенести на SSD", "How to move to an SSD"),
    "hint.move_ssd.d": ("Ігри: у Steam — Властивості гри → Встановлені файли → «Перемістити теку»; в Epic, EA і "
                        "Battle.net — схожі кнопки в налаштуваннях гри.\nWindows: найпростіше — чисте встановлення "
                        "на SSD або клонування диска програмою виробника SSD (Samsung Data Migration, "
                        "Crucial/Kingston Acronis тощо).",
                        "Игры: в Steam — Свойства игры → Установленные файлы → «Переместить папку»; в Epic, EA и "
                        "Battle.net — похожие кнопки в настройках игры.\nWindows: проще всего — чистая установка на "
                        "SSD или клонирование диска программой производителя SSD (Samsung Data Migration, "
                        "Crucial/Kingston Acronis и т. п.).",
                        "Games: in Steam — game Properties → Installed files → Move install folder; Epic, EA and "
                        "Battle.net have similar buttons.\nWindows: easiest is a clean install on the SSD or cloning "
                        "with the SSD maker's tool (Samsung Data Migration, Crucial/Kingston Acronis, etc.)."),
    "hint.backup.t": ("Що робити з диском", "Что делать с диском", "What to do about the drive"),
    "hint.backup.d": ("1. Скопіюйте важливі файли на інший диск або в хмару.\n2. Подивіться подробиці в "
                      "CrystalDiskInfo (його можна встановити на сторінці «Програми»).\n3. Плануйте заміну диска.",
                      "1. Скопируйте важные файлы на другой диск или в облако.\n2. Посмотрите подробности в "
                      "CrystalDiskInfo (его можно установить на странице «Программы»).\n3. Планируйте замену диска.",
                      "1. Copy important files to another drive or the cloud.\n2. See details in CrystalDiskInfo "
                      "(installable on the Apps page).\n3. Plan a replacement."),
    "hint.display_cable.t": ("Куди під'єднати монітор", "Куда подключить монитор", "Where to plug the monitor"),
    "hint.display_cable.d": ("Ззаду корпусу є два набори роз'ємів. Верхні, поруч із USB, — материнська плата. "
                             "Потрібні нижні, горизонтальні — на самій відеокарті. Перекиньте туди кабель "
                             "HDMI/DisplayPort і перезапустіть гру.",
                             "Сзади корпуса есть два набора разъёмов. Верхние, рядом с USB, — материнская плата. "
                             "Нужны нижние, горизонтальные — на самой видеокарте. Переключите туда кабель "
                             "HDMI/DisplayPort и перезапустите игру.",
                             "The back of the case has two sets of ports. The upper ones near the USB belong to the "
                             "motherboard. Use the lower horizontal ones on the graphics card itself. Move the "
                             "HDMI/DisplayPort cable there and restart the game."),
    "hint.mining.t": ("Як грати на майнінговій карті", "Как играть на майнинговой карте", "How to game on a mining card"),
    "hint.mining.d": ("1. Монітор лишайте в материнській платі — у карти немає виходів, картинку виводить вбудована "
                      "графіка.\n2. Ігри треба призначити на майнінгову карту. OptimaX робить це сама: «Ігри» → «Ігри на "
                      "{model}» → «Знайти й призначити ігри» (вручну — Параметри → Система → Дисплей → Графіка → "
                      "«Висока продуктивність»).\n3. Драйвер — лише пропатчений (dartraiden/NVIDIA-patcher): "
                      "звичайний з nvidia.com вимкне 3D. Забороніть Windows Update оновлювати драйвери.\n4. Старі ігри "
                      "(DirectX 9, Adobe AIR) на такій карті можуть давати синій екран у dxgmms1.sys — запускайте "
                      "їх на вбудованій графіці.\n5. OpenGL-ігри (і GPU-тест OptimaX) Windows на майнінгову карту не "
                      "перемикає — для них є Mesa в тому ж розділі «Ігри».",
                      "1. Монитор оставляйте в материнской плате — у карты нет выходов, картинку выводит встроенная "
                      "графика.\n2. Игры нужно назначить на майнинговую карту. OptimaX делает это сама: «Игры» → «Игры на "
                      "{model}» → «Найти и назначить игры» (вручную — Параметры → Система → Дисплей → Графика → "
                      "«Высокая производительность»).\n3. Драйвер — только пропатченный "
                      "(dartraiden/NVIDIA-patcher): обычный с nvidia.com отключит 3D. Запретите Windows Update "
                      "обновлять драйверы.\n4. Старые игры (DirectX 9, Adobe AIR) на такой карте могут давать синий "
                      "экран в dxgmms1.sys — запускайте их на встроенной графике.\n5. OpenGL-игры (и GPU-тест OptimaX) "
                      "Windows на майнинговую карту не переключает — для них есть Mesa в том же разделе «Игры».",
                      "1. Keep the monitor in the motherboard — the card has no outputs, the integrated graphics "
                      "display the picture.\n2. Games must be assigned to the mining card. OptimaX does it for you: Games → "
                      "Games on the {model} → Find and assign games (by hand: Settings → System → Display → Graphics → "
                      "High performance).\n3. Use only the patched driver (dartraiden/NVIDIA-patcher): "
                      "the regular one from nvidia.com disables 3D. Stop Windows Update from updating drivers.\n"
                      "4. Old games (DirectX 9, Adobe AIR) can blue-screen in dxgmms1.sys on such a card — run them "
                      "on the integrated graphics.\n5. Windows can't move OpenGL games (or the OptimaX GPU "
                      "test) to the mining card — use Mesa in the same Games section."),
    "hint.pcie.t": ("Як повернути повну швидкість PCIe", "Как вернуть полную скорость PCIe", "How to restore full PCIe speed"),
    "hint.pcie.d": ("1. Поставте відеокарту у верхній довгий слот, найближчий до процесора.\n2. Якщо є райзер — "
                    "спробуйте без нього.\n3. Вийміть карту, протріть контакти й вставте до клацання.\n4. У BIOS "
                    "для слота поставте Auto або Gen4/Gen3 замість Gen1.",
                    "1. Поставьте видеокарту в верхний длинный слот, ближайший к процессору.\n2. Если есть райзер — "
                    "попробуйте без него.\n3. Выньте карту, протрите контакты и вставьте до щелчка.\n4. В BIOS для "
                    "слота поставьте Auto или Gen4/Gen3 вместо Gen1.",
                    "1. Put the card in the top long slot closest to the CPU.\n2. If there's a riser, try without "
                    "it.\n3. Reseat the card until it clicks.\n4. In BIOS set the slot to Auto or Gen4/Gen3 instead "
                    "of Gen1."),
    "hint.rebar.t": ("Як увімкнути Resizable BAR", "Как включить Resizable BAR", "How to enable Resizable BAR"),
    "hint.rebar.d": ("1. Оновіть BIOS материнської плати.\n2. У BIOS: вимкніть CSM (потрібен режим UEFI), увімкніть "
                     "«Above 4G Decoding» і «Re-Size BAR Support» (AMD: Smart Access Memory).\n3. Оновіть драйвер "
                     "відеокарти. Після перезавантаження OptimaX покаже, чи вийшло.",
                     "1. Обновите BIOS материнской платы.\n2. В BIOS: выключите CSM (нужен режим UEFI), включите "
                     "«Above 4G Decoding» и «Re-Size BAR Support» (AMD: Smart Access Memory).\n3. Обновите драйвер "
                     "видеокарты. После перезагрузки OptimaX покажет, получилось ли.",
                     "1. Update the motherboard BIOS.\n2. In BIOS: disable CSM (UEFI mode needed), enable Above 4G "
                     "Decoding and Re-Size BAR Support (AMD: Smart Access Memory).\n3. Update the GPU driver. After a "
                     "restart OptimaX will show whether it worked."),
    "hint.thermal.t": ("Як знизити температуру", "Как снизить температуру", "How to bring temperatures down"),
    "hint.thermal.d": ("1. Почистіть радіатори й вентилятори від пилу (стиснене повітря).\n2. Замініть термопасту, "
                       "якщо ПК старший за 3–4 роки.\n3. Ноутбук — на тверду поверхню або підставку, не на ковдру.\n"
                       "4. Для ПК — перевірте, що корпусні вентилятори дують у правильному напрямку.\n5. Увімкніть "
                       "«Холодний режим» на сторінці «Ноутбук» — мінус 10–20 °C.",
                       "1. Почистите радиаторы и вентиляторы от пыли (сжатый воздух).\n2. Замените термопасту, если "
                       "ПК старше 3–4 лет.\n3. Ноутбук — на твёрдую поверхность или подставку, не на одеяло.\n4. Для "
                       "ПК — проверьте, что корпусные вентиляторы дуют в правильную сторону.\n5. Включите «Холодный "
                       "режим» на странице «Ноутбук» — минус 10–20 °C.",
                       "1. Clean heatsinks and fans (compressed air).\n2. Replace the thermal paste if the PC is over "
                       "3–4 years old.\n3. Put a laptop on a hard surface or stand, not a blanket.\n4. On a desktop, "
                       "check that case fans blow the right way.\n5. Turn on Cool mode on the Laptop page — "
                       "10–20 °C cooler."),
}
