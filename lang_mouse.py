"""OptimaX — переклади розділу «Миша» в Hardware Center: частота опитування, налаштування вказівника Windows,
перерахунок чутливості між іграми."""

STRINGS = {
    "hwc.sec.mouse": ("Миша", "Мышь", "Mouse"),

    # ── частота опитування ──
    "mouse.poll.title": ("Частота опитування", "Частота опроса", "Polling rate"),
    "mouse.poll.sub": ("Скільки разів на секунду миша надсилає рух. Заміряємо через Raw Input — ті самі події, що "
                       "бачать ігри; паузи, коли миша стоїть, не рахуємо.",
                       "Сколько раз в секунду мышь отправляет движение. Замеряем через Raw Input — те же события, что "
                       "видят игры; паузы, когда мышь стоит, не считаем.",
                       "How many times per second the mouse reports movement. Measured with Raw Input — the same "
                       "events games see; pauses while the mouse stands still are not counted."),
    "mouse.poll.run": ("Почати тест", "Начать тест", "Start test"),
    "mouse.poll.again": ("Ще раз", "Ещё раз", "Run again"),
    "mouse.poll.none": ("Тест ще не запускали.", "Тест ещё не запускали.", "Not tested yet."),
    "mouse.poll.dlg": ("Тест частоти опитування", "Тест частоты опроса", "Polling rate test"),
    "mouse.poll.hint": ("Швидко водіть мишею колами весь час тесту ({s} с) — відлік почнеться з першого руху. "
                        "Повільний рух сенсор передає рідше, і частота вийде нижчою.",
                        "Быстро водите мышью кругами всё время теста ({s} с) — отсчёт начнётся с первого движения. "
                        "Медленное движение сенсор передаёт реже, и частота выйдет ниже.",
                        "Move the mouse quickly in circles for the whole test ({s} s) — it starts with the first "
                        "movement. Slow movement is reported less often and gives a lower rate."),
    "mouse.poll.wait": ("Чекаю на рух миші…", "Жду движения мыши…", "Waiting for mouse movement…"),
    "mouse.poll.live": ("Подій: {n} · лишилось {s} с", "Событий: {n} · осталось {s} с", "Events: {n} · {s} s left"),
    "mouse.poll.stop": ("Завершити", "Завершить", "Finish"),
    "mouse.poll.hz": ("{hz} Гц", "{hz} Гц", "{hz} Hz"),
    "mouse.poll.nearest": ("Стандарт: {hz} Гц", "Стандарт: {hz} Гц", "Standard: {hz} Hz"),
    "mouse.poll.avg": ("Середня", "Средняя", "Average"),
    "mouse.poll.median": ("Медіана", "Медиана", "Median"),
    "mouse.poll.stability": ("Стабільність", "Стабильность", "Stability"),
    "mouse.poll.stability_v": ("{p}% вікон у межах ±10 %", "{p}% окон в пределах ±10 %",
                               "{p}% of windows within ±10%"),
    "mouse.poll.events": ("Подій руху", "Событий движения", "Movement events"),
    "mouse.poll.active": ("Час руху", "Время движения", "Time moving"),
    "mouse.poll.active_v": ("{s} с", "{s} с", "{s} s"),
    "mouse.poll.devices": ("Пристроїв", "Устройств", "Devices"),
    "mouse.poll.few": ("Замало подій руху ({n} за {s} с), щоб чесно назвати частоту. Водіть мишею колами "
                       "безперервно весь тест.",
                       "Слишком мало событий движения ({n} за {s} с), чтобы честно назвать частоту. Водите мышью "
                       "кругами непрерывно весь тест.",
                       "Too few movement events ({n} in {s} s) to name a rate honestly. Keep moving the mouse in "
                       "circles for the whole test."),
    "mouse.poll.noraw": ("Raw Input недоступний: {err}", "Raw Input недоступен: {err}", "Raw Input unavailable: {err}"),
    "mouse.poll.absolute": ("Миша надсилає абсолютні координати (віддалений стіл, віртуальна машина чи планшет) — "
                            "частоту тут не заміряти.",
                            "Мышь отправляет абсолютные координаты (удалённый стол, виртуальная машина или планшет) "
                            "— частоту здесь не замерить.",
                            "The mouse sends absolute coordinates (remote desktop, virtual machine or tablet) — the "
                            "rate can't be measured here."),
    "mouse.poll.low": ("Заміряна частота нижча за стандарт {hz} Гц: рухайте швидше або перевірте частоту в програмі "
                       "миші.",
                       "Замеренная частота ниже стандарта {hz} Гц: двигайте быстрее или проверьте частоту в "
                       "программе мыши.",
                       "The measured rate is below the {hz} Hz standard: move faster or check the rate in the mouse "
                       "software."),
    "mouse.poll.high": ("Від 4000 Гц обробка повідомлень Windows може недораховувати події — звірте з програмою "
                        "виробника миші.",
                        "От 4000 Гц обработка сообщений Windows может недосчитывать события — сверьте с программой "
                        "производителя мыши.",
                        "From 4000 Hz, Windows message handling may miss events — compare with the mouse maker's "
                        "software."),
    "mouse.poll.unstable": ("Частота скаче: бездротовий приймач далеко, USB-хаб або завантажений процесор.",
                            "Частота скачет: беспроводной приёмник далеко, USB-хаб или загруженный процессор.",
                            "The rate jumps around: wireless receiver too far, a USB hub or a busy CPU."),
    "mouse.poll.demo": ("Режим перегляду: імітований потік подій, не ваша миша.",
                        "Режим просмотра: имитированный поток событий, не ваша мышь.",
                        "Preview mode: a simulated event stream, not your mouse."),

    # ── налаштування Windows ──
    "mouse.win.title": ("Налаштування вказівника Windows", "Настройки указателя Windows", "Windows pointer settings"),
    "mouse.win.sub": ("Читаємо з реєстру поточного користувача. Ігри з Raw Input (більшість сучасних шутерів) їх не "
                      "використовують — вони важливі для робочого столу й ігор без Raw Input.",
                      "Читаем из реестра текущего пользователя. Игры с Raw Input (большинство современных шутеров) их "
                      "не используют — они важны для рабочего стола и игр без Raw Input.",
                      "Read from the current user's registry. Games with Raw Input (most modern shooters) ignore them "
                      "— they matter for the desktop and games without Raw Input."),
    "mouse.win.speed": ("Швидкість вказівника", "Скорость указателя", "Pointer speed"),
    "mouse.win.speed_v": ("{v} з 20 · поділка {n} з 11 · ×{m}", "{v} из 20 · деление {n} из 11 · ×{m}",
                          "{v} of 20 · notch {n} of 11 · ×{m}"),
    "mouse.win.speed_d": ("MouseSensitivity 1–20. Значення 10 (6-та поділка) — множник 1.0: один відлік сенсора — "
                          "один піксель, без пропусків і повторів.",
                          "MouseSensitivity 1–20. Значение 10 (6-е деление) — множитель 1.0: один отсчёт сенсора — "
                          "один пиксель, без пропусков и повторов.",
                          "MouseSensitivity 1–20. Value 10 (the 6th notch) is a 1.0 multiplier: one sensor count is "
                          "one pixel, nothing skipped or repeated."),
    "mouse.win.accel": ("Підвищена точність (прискорення)", "Повышенная точность (ускорение)",
                        "Enhance pointer precision (acceleration)"),
    "mouse.win.accel_on": ("увімкнено · MouseSpeed {s}, пороги {a}/{b}", "включено · MouseSpeed {s}, пороги {a}/{b}",
                           "on · MouseSpeed {s}, thresholds {a}/{b}"),
    "mouse.win.accel_off": ("вимкнено · MouseSpeed 0", "выключено · MouseSpeed 0", "off · MouseSpeed 0"),
    "mouse.win.accel_d": ("Коли ввімкнено, швидкий рух переносить курсор далі, ніж повільний на ту саму відстань: "
                          "м'язова пам'ять не працює однаково.",
                          "Когда включено, быстрое движение переносит курсор дальше, чем медленное на то же "
                          "расстояние: мышечная память не работает одинаково.",
                          "When on, a fast movement carries the cursor further than a slow one over the same "
                          "distance, so muscle memory doesn't stay consistent."),
    "mouse.win.rec": ("Для ігор: швидкість 10 і прискорення вимкнено — рух 1:1, однаковий за будь-якої швидкості "
                      "руки. FPS це не додає.",
                      "Для игр: скорость 10 и ускорение выключено — движение 1:1, одинаковое при любой скорости "
                      "руки. FPS это не добавляет.",
                      "For games: speed 10 and acceleration off — 1:1 movement, the same at any hand speed. It "
                      "doesn't add FPS."),
    "mouse.win.ok": ("Як рекомендовано", "Как рекомендовано", "As recommended"),
    "mouse.win.differs": ("Відрізняється", "Отличается", "Differs"),
    "mouse.win.applied": ("Змінено через OptimaX — можна відкотити до ваших попередніх значень.",
                          "Изменено через OptimaX — можно откатить к вашим прежним значениям.",
                          "Changed by OptimaX — can be rolled back to your previous values."),
    "mouse.win.apply": ("Швидкість 10 + без прискорення", "Скорость 10 + без ускорения", "Speed 10 + no acceleration"),
    "mouse.win.apply_q": ("Буде записано MouseSensitivity = 10, MouseSpeed = 0, MouseThreshold1/2 = 0 і застосовано "
                          "одразу. Попередні значення збережуться в журналі відкату.",
                          "Будет записано MouseSensitivity = 10, MouseSpeed = 0, MouseThreshold1/2 = 0 и применено "
                          "сразу. Прежние значения сохранятся в журнале отката.",
                          "Sets MouseSensitivity = 10, MouseSpeed = 0, MouseThreshold1/2 = 0 and applies it right "
                          "away. Your previous values are kept in the rollback journal."),
    "mouse.win.undo": ("Відкотити", "Откатить", "Roll back"),

    # ── перерахунок чутливості ──
    "mouse.conv.title": ("Чутливість між іграми", "Чувствительность между играми", "Sensitivity between games"),
    "mouse.conv.sub": ("Та сама відстань руки на оберт 360° в іншій грі (огляд без прицілу). Лише ігри з точно "
                       "відомим кутом повороту на одиницю руху.",
                       "То же расстояние руки на оборот 360° в другой игре (обзор без прицела). Только игры с точно "
                       "известным углом поворота на единицу движения.",
                       "The same hand distance per 360° turn in another game (hip-fire view). Only games whose turn "
                       "angle per count is known exactly."),
    "mouse.conv.dpi": ("DPI миші", "DPI мыши", "Mouse DPI"),
    "mouse.conv.sens": ("Чутливість у грі", "Чувствительность в игре", "In-game sensitivity"),
    "mouse.conv.from": ("З гри", "Из игры", "From game"),
    "mouse.conv.to": ("У гру", "В игру", "To game"),
    "mouse.conv.result": ("Чутливість: {s}", "Чувствительность: {s}", "Sensitivity: {s}"),
    "mouse.conv.cm": ("См на 360°", "См на 360°", "cm per 360°"),
    "mouse.conv.in": ("Дюймів на 360°", "Дюймов на 360°", "Inches per 360°"),
    "mouse.conv.edpi": ("eDPI ({game})", "eDPI ({game})", "eDPI ({game})"),
    "mouse.conv.bad": ("Введіть DPI і чутливість більші за нуль.", "Введите DPI и чувствительность больше нуля.",
                       "Enter a DPI and sensitivity above zero."),
}
