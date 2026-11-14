"""Рядки 6.15: тест затримки системи (Hardware Center) і керування відеокартою (кулери, андервольт)."""

STRINGS = {
    # ── тест затримки системи ──
    "hwc.sec.latency": ("Затримки", "Задержки", "Latency"),
    "hwc.t.latency": ("Затримка системи", "Задержка системы", "System latency"),
    "lat.title": ("Тест затримки системи", "Тест задержки системы", "System latency test"),
    "lat.sub": ("Чи встигає Windows вчасно віддати процесор грі, звуку й уводу: найдовші зупинки програми, найдовші DPC "
                "і переривання (ISR) та драйвери, які їх дають.",
                "Успевает ли Windows вовремя отдать процессор игре, звуку и вводу: самые долгие остановки программы, "
                "самые долгие DPC и прерывания (ISR) и драйверы, которые их дают.",
                "Whether Windows hands the CPU to games, audio and input in time: the longest program stalls, the "
                "longest DPCs and interrupts (ISRs) and the drivers behind them."),
    "lat.note": ("Користуйтеся ПК як зазвичай: запустіть гру, музику чи відео, Wi-Fi — так видно справжні проблеми. "
                 "Драйвер OptimaX не встановлює і нічого в системі не змінює; під час тесту одне ядро завантажене "
                 "повністю — так міряються зупинки.",
                 "Пользуйтесь ПК как обычно: запустите игру, музыку или видео, Wi-Fi — так видны настоящие проблемы. "
                 "Драйвер OptimaX не устанавливает и ничего в системе не меняет; во время теста одно ядро загружено "
                 "полностью — так измеряются остановки.",
                 "Use the PC as usual: run a game, music or video, Wi-Fi — that's how real problems show up. OptimaX "
                 "installs no driver and changes nothing in the system; one core is fully loaded during the test — "
                 "that's how stalls are measured."),
    "lat.no_admin": ("Без прав адміністратора будуть лише зупинки програми. DPC, переривання й драйвери видно, якщо "
                     "запустити OptimaX від імені адміністратора.",
                     "Без прав администратора будут только остановки программы. DPC, прерывания и драйверы видны, "
                     "если запустить OptimaX от имени администратора.",
                     "Without administrator rights only program stalls are measured. DPCs, interrupts and drivers need "
                     "OptimaX running as administrator."),
    "lat.dur": ("Тривалість", "Длительность", "Duration"),
    "lat.us": ("{v} мкс", "{v} мкс", "{v} µs"),
    "lat.ms": ("{v} мс", "{v} мс", "{v} ms"),
    "lat.sec": ("{n} с", "{n} с", "{n} s"),
    "hwc.p.latency": ("{t} / {d} с · зупинки програми: макс. {stall} · DPC/ISR: макс. {exec}",
                      "{t} / {d} с · остановки программы: макс. {stall} · DPC/ISR: макс. {exec}",
                      "{t} / {d} s · program stalls: max {stall} · DPC/ISR: max {exec}"),
    "hwc.chart.lat": ("Найдовша зупинка програми за секунду, мкс", "Самая долгая остановка программы за секунду, мкс",
                      "Longest program stall per second, µs"),
    "hwc.chart.dpc": ("Найдовший DPC / ISR за секунду, мкс", "Самый долгий DPC / ISR за секунду, мкс",
                      "Longest DPC / ISR per second, µs"),
    "lat.sum.pass": ("Затримки в нормі — система підходить для ігор і звуку в реальному часі.",
                     "Задержки в норме — система подходит для игр и звука в реальном времени.",
                     "Latency is fine — the system is suitable for games and real-time audio."),
    "lat.sum.warn": ("Є помітні затримки — можливі мікрофризи, тріск звуку чи запізнення вводу.",
                     "Есть заметные задержки — возможны микрофризы, треск звука или запаздывание ввода.",
                     "There are noticeable delays — micro-stutter, audio crackles or input lag are possible."),
    "lat.sum.fail": ("Великі затримки — система не встигає: тріск звуку, фризи й запізнення вводу дуже ймовірні.",
                     "Большие задержки — система не успевает: треск звука, фризы и запаздывание ввода очень вероятны.",
                     "High latency — the system can't keep up: audio crackles, stutter and input lag are very likely."),
    "lat.sum.na": ("Затримку виміряти не вдалося.", "Задержку измерить не удалось.", "Latency could not be measured."),
    "lat.r.stall_max": ("Найдовша зупинка програми", "Самая долгая остановка программы", "Longest program stall"),
    "lat.r.stall_n": ("Зупинок від 1 мс / усього", "Остановок от 1 мс / всего", "Stalls of 1 ms+ / total"),
    "lat.r.stall_pct": ("Час, забраний у програми", "Время, отнятое у программы", "Time taken from the program"),
    "lat.r.dpc_max": ("Найдовший DPC", "Самый долгий DPC", "Longest DPC"),
    "lat.r.isr_max": ("Найдовше переривання (ISR)", "Самое долгое прерывание (ISR)", "Longest interrupt (ISR)"),
    "lat.r.burst": ("Найдовша безперервна робота DPC/ISR на ядрі", "Самая долгая непрерывная работа DPC/ISR на ядре",
                    "Longest continuous DPC/ISR run on a core"),
    "lat.r.cpu_pct": ("Час ядра в DPC/ISR (пік за секунду)", "Время ядра в DPC/ISR (пик за секунду)",
                      "Core time in DPC/ISR (peak per second)"),
    "lat.r.duration": ("Тривалість", "Длительность", "Duration"),
    "lat.f.stall": ("Програма стояла до {us}: процесор забирали переривання, драйвери чи інші процеси. Зупинок від "
                    "{lim}: {n}.",
                    "Программа стояла до {us}: процессор забирали прерывания, драйверы или другие процессы. Остановок "
                    "от {lim}: {n}.",
                    "The program stalled for up to {us}: interrupts, drivers or other processes took the CPU. Stalls "
                    "of {lim} or more: {n}."),
    "lat.f.driver": ("{drv} ({kind}): {what} до {us}.", "{drv} ({kind}): {what} до {us}.",
                     "{drv} ({kind}): {what} up to {us}."),
    "lat.f.no_admin": ("DPC і переривання не виміряно: потрібні права адміністратора.",
                       "DPC и прерывания не измерены: нужны права администратора.",
                       "DPCs and interrupts weren't measured: administrator rights are needed."),
    "lat.f.etw_busy": ("DPC і переривання не виміряно: журнал подій ядра зайнятий іншою програмою (LatencyMon, WPR, "
                       "xperf). Закрийте її й повторіть.",
                       "DPC и прерывания не измерены: журнал событий ядра занят другой программой (LatencyMon, WPR, "
                       "xperf). Закройте её и повторите.",
                       "DPCs and interrupts weren't measured: the kernel event log is busy with another program "
                       "(LatencyMon, WPR, xperf). Close it and try again."),
    "lat.f.etw_err": ("DPC і переривання не виміряно: помилка журналу подій ядра ({code}).",
                      "DPC и прерывания не измерены: ошибка журнала событий ядра ({code}).",
                      "DPCs and interrupts weren't measured: kernel event log error ({code})."),
    "lat.f.lost": ("Частину подій ядра втрачено ({n}) — система була дуже завантажена, дані DPC/ISR неповні.",
                   "Часть событий ядра потеряна ({n}) — система была сильно загружена, данные DPC/ISR неполные.",
                   "Some kernel events were lost ({n}) — the system was very busy, DPC/ISR data is incomplete."),
    "lat.f.stall_err": ("Зупинки програми не виміряно: збій процесу тесту ({code}).",
                        "Остановки программы не измерены: сбой процесса теста ({code}).",
                        "Program stalls weren't measured: the test process failed ({code})."),
    "lat.adv.stall_other": ("Програма стояла вдвічі довше, ніж драйвери безперервно тримали ядро (DPC і переривання "
                            "поспіль), — процесор забирали не драйвери Windows, а BIOS (SMI), гіпервізор чи програми з "
                            "пріоритетом реального часу (звукові студії, захоплення відео). Оновіть BIOS і драйвер "
                            "чипсета, закрийте такі програми.",
                            "Программа стояла вдвое дольше, чем драйверы непрерывно держали ядро (DPC и прерывания "
                            "подряд), — процессор забирали не драйверы Windows, а BIOS (SMI), гипервизор или программы "
                            "с приоритетом реального времени (звуковые студии, захват видео). Обновите BIOS и драйвер "
                            "чипсета, закройте такие программы.",
                            "The program stalled twice as long as drivers kept a core busy in a row (back-to-back DPCs "
                            "and interrupts) — the CPU was taken not by Windows drivers but by the BIOS (SMI), a "
                            "hypervisor or real-time priority programs (audio workstations, video capture). Update the "
                            "BIOS and chipset driver, close such programs."),
    "lat.kind.net":("мережа", "сеть", "network"),
    "lat.kind.gpu": ("відеокарта", "видеокарта", "graphics"),
    "lat.kind.audio": ("звук", "звук", "audio"),
    "lat.kind.storage": ("накопичувач", "накопитель", "storage"),
    "lat.kind.usb": ("USB і пристрої вводу", "USB и устройства ввода", "USB and input devices"),
    "lat.kind.power": ("живлення / ACPI", "питание / ACPI", "power / ACPI"),
    "lat.kind.security": ("антивірус", "антивирус", "antivirus"),
    "lat.kind.wdf": ("каркас драйверів WDF", "каркас драйверов WDF", "WDF driver framework"),
    "lat.kind.system": ("ядро Windows", "ядро Windows", "Windows kernel"),
    "lat.kind.other": ("інший драйвер", "другой драйвер", "other driver"),
    "lat.adv.net": ("Мережа: оновіть драйвер адаптера з сайту виробника, вимкніть енергозбереження адаптера; для Wi-Fi "
                    "— фоновий пошук мереж (розділ «Мережа» в OptimaX).",
                    "Сеть: обновите драйвер адаптера с сайта производителя, отключите энергосбережение адаптера; для "
                    "Wi-Fi — фоновый поиск сетей (раздел «Сеть» в OptimaX).",
                    "Network: update the adapter driver from the vendor's site, turn off the adapter's power saving; "
                    "for Wi-Fi — background network scanning (the Network section in OptimaX)."),
    "lat.adv.gpu": ("Відеокарта: чисте встановлення свіжого драйвера; від'єднайте зайві монітори й вимкніть те, що "
                    "постійно перемикає режим екрана.",
                    "Видеокарта: чистая установка свежего драйвера; отключите лишние мониторы и то, что постоянно "
                    "переключает режим экрана.",
                    "Graphics: clean-install a fresh driver; disconnect extra monitors and anything that keeps switching "
                    "the display mode."),
    "lat.adv.audio": ("Звук: оновіть звуковий драйвер; вимкніть невикористані аудіопристрої (звук HDMI / DisplayPort "
                      "відеокарти) у налаштуваннях звуку.",
                      "Звук: обновите звуковой драйвер; отключите неиспользуемые аудиоустройства (звук HDMI / "
                      "DisplayPort видеокарты) в настройках звука.",
                      "Audio: update the audio driver; disable unused audio devices (the graphics card's HDMI / "
                      "DisplayPort audio) in sound settings."),
    "lat.adv.storage": ("Накопичувач: оновіть драйвер контролера й прошивку SSD; стан диска — у розділі «Диски».",
                        "Накопитель: обновите драйвер контроллера и прошивку SSD; состояние диска — в разделе «Диски».",
                        "Storage: update the controller driver and the SSD firmware; disk health is in the Storage "
                        "section."),
    "lat.adv.usb": ("USB: від'єднайте зайві пристрої, оновіть драйвер чипсета, вимкніть енергозбереження USB у схемі "
                    "живлення.",
                    "USB: отключите лишние устройства, обновите драйвер чипсета, отключите энергосбережение USB в "
                    "схеме питания.",
                    "USB: unplug unneeded devices, update the chipset driver, turn off USB power saving in the power "
                    "plan."),
    "lat.adv.power": ("Живлення: схема «Висока продуктивність», свіжі BIOS і драйвер чипсета; ноутбук — від мережі.",
                      "Питание: схема «Высокая производительность», свежие BIOS и драйвер чипсета; ноутбук — от сети.",
                      "Power: the High performance plan, up-to-date BIOS and chipset driver; laptops — on AC power."),
    "lat.adv.security": ("Антивірус: перевірка в реальному часі навантажує систему — додайте папки ігор до винятків.",
                         "Антивирус: проверка в реальном времени нагружает систему — добавьте папки игр в исключения.",
                         "Antivirus: real-time scanning loads the system — add your game folders to the exclusions."),
    "lat.adv.wdf": ("Wdf01000.sys — каркас, на якому працюють інші драйвери (тачпад, USB, мережа, датчики). Вимикайте "
                    "пристрої в Диспетчері пристроїв по одному й повторюйте тест.",
                    "Wdf01000.sys — каркас, на котором работают другие драйверы (тачпад, USB, сеть, датчики). "
                    "Отключайте устройства в Диспетчере устройств по одному и повторяйте тест.",
                    "Wdf01000.sys is the framework other drivers run on (touchpad, USB, network, sensors). Disable "
                    "devices in Device Manager one at a time and repeat the test."),
    "lat.adv.system": ("ntoskrnl.exe / hal.dll — ядро Windows (таймери, планувальник); зазвичай це наслідок, а не "
                       "причина — дивіться інші драйвери в списку.",
                       "ntoskrnl.exe / hal.dll — ядро Windows (таймеры, планировщик); обычно это следствие, а не "
                       "причина — смотрите другие драйверы в списке.",
                       "ntoskrnl.exe / hal.dll is the Windows kernel (timers, scheduler); it is usually a symptom, not "
                       "the cause — look at the other drivers in the list."),
    "lat.adv.other": ("Оновіть цей драйвер або тимчасово вимкніть його пристрій у Диспетчері пристроїв і повторіть тест.",
                      "Обновите этот драйвер или временно отключите его устройство в Диспетчере устройств и повторите "
                      "тест.",
                      "Update this driver or temporarily disable its device in Device Manager and repeat the test."),
    # ── кулери й андервольт відеокарти ──
    "hwc.sec.gputune": ("Кулери й андервольт · тест", "Кулеры и андервольт · тест", "Fans & undervolt · test"),
    "gt.test_badge": ("Тестовий режим", "Тестовый режим", "Test mode"),
    "gt.test_note": ("Цей розділ працює в тестовому режимі: на справжніх картах NVIDIA й AMD його ще перевіряють. "
                     "Можливі помилки драйвера, а на AMD — і аварійне закриття OptimaX під час звернення до драйвера. "
                     "Заводські значення завжди можна повернути: «Скинути до заводських», відкат у журналі, "
                     "OptimaX-Rescue.cmd; налаштування NVIDIA скидаються й після перезавантаження. Поки розділ вимкнено, "
                     "OptimaX драйвера відеокарти не чіпає.",
                     "Этот раздел работает в тестовом режиме: на настоящих картах NVIDIA и AMD его ещё проверяют. "
                     "Возможны ошибки драйвера, а на AMD — и аварийное закрытие OptimaX при обращении к драйверу. "
                     "Заводские значения всегда можно вернуть: «Сбросить до заводских», откат в журнале, "
                     "OptimaX-Rescue.cmd; настройки NVIDIA сбрасываются и после перезагрузки. Пока раздел выключен, "
                     "OptimaX драйвер видеокарты не трогает.",
                     "This section works in test mode: it is still being checked on real NVIDIA and AMD cards. Driver "
                     "errors are possible, and on AMD OptimaX may even close unexpectedly while talking to the driver. "
                     "The factory values can always be restored: Reset to factory, journal rollback, OptimaX-Rescue.cmd; "
                     "NVIDIA settings also reset after a restart. While the section is off, OptimaX doesn't touch the "
                     "graphics driver."),
    "gt.test_enable": ("Увімкнути розділ (тестовий режим)", "Включить раздел (тестовый режим)",
                       "Turn the section on (test mode)"),
    "gt.test_off": ("Розділ вимкнено — увімкніть його вище, щоб побачити, що дозволяє ваша відеокарта.",
                    "Раздел выключен — включите его выше, чтобы увидеть, что позволяет ваша видеокарта.",
                    "The section is off — turn it on above to see what your graphics card allows."),
    "gt.test_ask": ("Кулери й андервольт працюють у тестовому режимі: на справжніх картах їх ще перевіряють, тож "
                    "можливі помилки драйвера, а на AMD — і аварійне закриття OptimaX. Нічого не зміниться, доки ви не "
                    "натиснете «Застосувати», а заводські значення завжди можна повернути. Увімкнути?",
                    "Кулеры и андервольт работают в тестовом режиме: на настоящих картах их ещё проверяют, поэтому "
                    "возможны ошибки драйвера, а на AMD — и аварийное закрытие OptimaX. Ничего не изменится, пока вы не "
                    "нажмёте «Применить», а заводские значения всегда можно вернуть. Включить?",
                    "Fans & undervolt work in test mode: they are still being checked on real cards, so driver errors "
                    "are possible, and on AMD OptimaX may even close unexpectedly. Nothing changes until you press "
                    "Apply, and the factory values can always be restored. Turn it on?"),
    "gt.test_on_btn": ("Увімкнути", "Включить", "Turn on"),
    "gt.log.test_on": ("[GPU] Кулери й андервольт увімкнено (тестовий режим)",
                       "[GPU] Кулеры и андервольт включены (тестовый режим)",
                       "[GPU] Fans & undervolt turned on (test mode)"),
    "gt.log.test_off": ("[GPU] Кулери й андервольт вимкнено, заводські значення повернуто",
                        "[GPU] Кулеры и андервольт выключены, заводские значения возвращены",
                        "[GPU] Fans & undervolt turned off, factory values restored"),
    "wn.615.latency": ("Тест затримки системи (Hardware Center → «Затримки»): найдовші зупинки програми на кожному ядрі "
                       "й драйвери, які затримують гру та звук, — з порадою, що з ними робити. Без драйвера.",
                       "Тест задержки системы (Hardware Center → «Задержки»): самые долгие остановки программы на "
                       "каждом ядре и драйверы, которые задерживают игру и звук, — с советом, что с ними делать. Без "
                       "драйвера.",
                       "A system latency test (Hardware Center → Latency): the longest program stalls on every core and "
                       "the drivers that delay games and audio, with advice on what to do. No driver needed."),
    "wn.615.gpu": ("Кулери й андервольт відеокарти NVIDIA й AMD — у тестовому режимі (вмикається в Hardware Center): "
                   "крива вентиляторів, ліміт потужності, автопідбір андервольту з перевіркою стабільності й "
                   "поверненням заводських значень.",
                   "Кулеры и андервольт видеокарт NVIDIA и AMD — в тестовом режиме (включается в Hardware Center): "
                   "кривая вентиляторов, лимит мощности, автоподбор андервольта с проверкой стабильности и возвратом "
                   "заводских значений.",
                   "NVIDIA and AMD graphics fans & undervolt — in test mode (turned on in Hardware Center): a fan "
                   "curve, power limit, undervolt auto-tune with a stability check and restorable factory values."),
    "gt.title": ("Кулери й андервольт відеокарти", "Кулеры и андервольт видеокарты", "GPU fans & undervolt"),
    "gt.sub": ("Через офіційні бібліотеки драйвера (NVIDIA NVML, AMD ADLX), без драйвера ядра. Нічого не змінюється "
               "без «Застосувати»; заводські значення завжди можна повернути.",
               "Через официальные библиотеки драйвера (NVIDIA NVML, AMD ADLX), без драйвера ядра. Ничего не меняется "
               "без «Применить»; заводские значения всегда можно вернуть.",
               "Through the driver's official libraries (NVIDIA NVML, AMD ADLX), without a kernel driver. Nothing "
               "changes until you press Apply; the factory values can always be restored."),
    "gt.loading": ("Шукаю відеокарту…", "Ищу видеокарту…", "Looking for the graphics card…"),
    "gt.none": ("Відеокарти, якою можна керувати, не знайдено.", "Видеокарты, которой можно управлять, не найдено.",
                "No controllable graphics card found."),
    "gt.admin": ("Щоб змінювати налаштування відеокарти, запустіть OptimaX від імені адміністратора.",
                 "Чтобы менять настройки видеокарты, запустите OptimaX от имени администратора.",
                 "Run OptimaX as administrator to change graphics card settings."),
    "gt.safety": ("Захист: від 85 °C вентилятори на 100 %; після зміни частоти чи напруги OptimaX стежить за збоями — "
                  "якщо програма чи система впаде, під час наступного запуску повернуться заводські значення.",
                  "Защита: от 85 °C вентиляторы на 100 %; после изменения частоты или напряжения OptimaX следит за "
                  "сбоями — если программа или система упадёт, при следующем запуске вернутся заводские значения.",
                  "Safety: fans go to 100 % from 85 °C; after a clock or voltage change OptimaX watches for crashes — if "
                  "the program or the system crashes, the factory values come back on the next start."),
    "gt.part.fan": ("Вентилятори", "Вентиляторы", "Fans"),
    "gt.part.power": ("Ліміт потужності", "Лимит мощности", "Power limit"),
    "gt.part.clock": ("Обмеження частоти", "Ограничение частоты", "Clock limit"),
    "gt.part.offset": ("Зсув частоти (андервольт)", "Сдвиг частоты (андервольт)", "Clock offset (undervolt)"),
    "gt.part.voltage": ("Напруга (андервольт)", "Напряжение (андервольт)", "Voltage (undervolt)"),
    "gt.why.unsupported": ("драйвер цієї карти не дозволяє", "драйвер этой карты не позволяет",
                           "this card's driver doesn't allow it"),
    "gt.why.admin": ("потрібні права адміністратора", "нужны права администратора", "administrator rights are needed"),
    "gt.why.old_driver": ("потрібен новіший драйвер", "нужен более новый драйвер", "a newer driver is needed"),
    "gt.why.error": ("помилка драйвера", "ошибка драйвера", "driver error"),
    "gt.why.no_fans": ("у карти немає керованих вентиляторів (часто — ноутбук)",
                       "у карты нет управляемых вентиляторов (часто — ноутбук)",
                       "the card has no controllable fans (often a laptop)"),
    "gt.why.locked": ("виробник заблокував зміну", "производитель заблокировал изменение",
                      "the manufacturer has locked it"),
    "gt.why.nv_voltage": ("NVIDIA не дає змінювати напругу напряму — андервольт робиться зсувом частоти",
                          "NVIDIA не даёт менять напряжение напрямую — андервольт делается сдвигом частоты",
                          "NVIDIA doesn't allow direct voltage changes — undervolting is done with the clock offset"),
    "gt.why.amd_old": ("для старших карт AMD — лише в Adrenalin", "для старых карт AMD — только в Adrenalin",
                       "older AMD cards — only in Adrenalin"),
    "gt.why.amd_offset": ("у AMD андервольт — через напругу", "у AMD андервольт — через напряжение",
                          "AMD undervolting is done through the voltage"),
    "gt.why.amd_auto": ("увімкнено автоматичне налаштування Adrenalin — спершу скиньте його",
                        "включена автоматическая настройка Adrenalin — сначала сбросьте её",
                        "Adrenalin automatic tuning is on — reset it first"),
    "gt.why.no_gpu": ("немає відеокарти NVIDIA чи AMD з драйвером виробника",
                      "нет видеокарты NVIDIA или AMD с драйвером производителя",
                      "no NVIDIA or AMD graphics card with the vendor's driver"),
    "gt.live.temp": ("{v} °C", "{v} °C", "{v} °C"),
    "gt.live.fan": ("вентилятор {v} %", "вентилятор {v} %", "fan {v} %"),
    "gt.live.power": ("{v} W", "{v} W", "{v} W"),
    "gt.live.clock": ("{v} MHz", "{v} MHz", "{v} MHz"),
    "gt.live.none": ("Показники недоступні.", "Показатели недоступны.", "Readings unavailable."),
    "gt.fan.title": ("Вентилятори", "Вентиляторы", "Fans"),
    "gt.fan.sub": ("Авто — як вирішить драйвер; крива — швидкість за температурою; фіксовано — стала швидкість.",
                   "Авто — как решит драйвер; кривая — скорость по температуре; фиксированно — постоянная скорость.",
                   "Auto — the driver decides; curve — speed by temperature; fixed — a constant speed."),
    "gt.fan.mode": ("Режим", "Режим", "Mode"),
    "gt.fan.auto": ("Авто", "Авто", "Auto"),
    "gt.fan.curve": ("Крива", "Кривая", "Curve"),
    "gt.fan.fixed": ("Фіксовано", "Фиксированно", "Fixed"),
    "gt.fan.preset": ("Крива", "Кривая", "Curve"),
    "gt.preset.quiet": ("Тиха", "Тихая", "Quiet"),
    "gt.preset.balanced": ("Збалансована", "Сбалансированная", "Balanced"),
    "gt.preset.cool": ("Холодна", "Холодная", "Cool"),
    "gt.preset.custom": ("Своя", "Своя", "Custom"),
    "gt.fan.temp": ("Температура", "Температура", "Temperature"),
    "gt.fan.speed": ("Швидкість", "Скорость", "Speed"),
    "gt.fan.fixed_l": ("Швидкість", "Скорость", "Speed"),
    "gt.fan.bad_curve": ("Температури мають іти за зростанням і не повторюватися, швидкість — не спадати.",
                         "Температуры должны идти по возрастанию и не повторяться, скорость — не уменьшаться.",
                         "Temperatures must go up without repeats, and the speed must not go down."),
    "gt.fan.note_nv": ("Крива працює, поки працює OptimaX; закриєте програму чи вона впаде — вентилятори повернуться "
                       "драйверу. Від {t} °C — 100 %, нижче {m} % крива не опускається.",
                       "Кривая работает, пока работает OptimaX; закроете программу или она упадёт — вентиляторы "
                       "вернутся драйверу. От {t} °C — 100 %, ниже {m} % кривая не опускается.",
                       "The curve runs while OptimaX runs; if you close the program or it crashes, the fans go back to "
                       "the driver. From {t} °C — 100 %, the curve never goes below {m} %."),
    "gt.fan.note_native": ("Точки кривої записуються в драйвер AMD і працюють і без OptimaX. Від {t} °C — 100 %, нижче "
                           "{m} % крива не опускається.",
                           "Точки кривой записываются в драйвер AMD и работают и без OptimaX. От {t} °C — 100 %, ниже "
                           "{m} % кривая не опускается.",
                           "The curve points go into the AMD driver and work without OptimaX too. From {t} °C — 100 %, "
                           "the curve never goes below {m} %."),
    "gt.fan.applied": ("Режим вентиляторів застосовано.", "Режим вентиляторов применён.", "Fan mode applied."),
    "gt.fan.running": ("Крива OptimaX працює.", "Кривая OptimaX работает.", "The OptimaX curve is running."),
    "gt.fan.stopped": ("Крива зупинилася ({e}) — вентилятори повернуто драйверу.",
                       "Кривая остановилась ({e}) — вентиляторы возвращены драйверу.",
                       "The curve stopped ({e}) — the fans are back with the driver."),
    "gt.fan.driver": ("Вентиляторами керує драйвер.", "Вентиляторами управляет драйвер.", "The driver controls the fans."),
    "gt.uv.title": ("Потужність і андервольт", "Мощность и андервольт", "Power & undervolt"),
    "gt.uv.sub": ("Менша напруга на тій самій частоті — менше тепла й шуму, та сама продуктивність. Найпростіше — "
                  "«Підібрати автоматично».",
                  "Меньшее напряжение на той же частоте — меньше тепла и шума, та же производительность. Проще всего — "
                  "«Подобрать автоматически».",
                  "Lower voltage at the same clock — less heat and noise, the same performance. The easiest way is "
                  "Auto-tune."),
    "gt.power": ("Ліміт потужності", "Лимит мощности", "Power limit"),
    "gt.cap": ("Найвища частота", "Наибольшая частота", "Max clock"),
    "gt.offset": ("Зсув частоти", "Сдвиг частоты", "Clock offset"),
    "gt.maxfreq": ("Найвища частота", "Наибольшая частота", "Max clock"),
    "gt.voltage": ("Напруга", "Напряжение", "Voltage"),
    "gt.apply": ("Застосувати", "Применить", "Apply"),
    "gt.verify": ("Перевірити стабільність", "Проверить стабильность", "Check stability"),
    "gt.autotune": ("Підібрати автоматично", "Подобрать автоматически", "Auto-tune"),
    "gt.reset": ("Скинути до заводських", "Сбросить до заводских", "Reset to factory"),
    "gt.on_start": ("Застосовувати під час запуску OptimaX", "Применять при запуске OptimaX",
                    "Apply when OptimaX starts"),
    "gt.on_start_need": ("Застосовувати під час запуску можна лише профіль, що пройшов перевірку стабільності.",
                         "Применять при запуске можно только профиль, прошедший проверку стабильности.",
                         "Only a profile that passed the stability check can be applied at start."),
    "gt.uv.note": ("NVIDIA скидає ці налаштування після перезавантаження. Відкат у журналі OptimaX і OptimaX-Rescue.cmd "
                   "повертають заводські значення.",
                   "NVIDIA сбрасывает эти настройки после перезагрузки. Откат в журнале OptimaX и OptimaX-Rescue.cmd "
                   "возвращают заводские значения.",
                   "NVIDIA resets these settings after a restart. Rollback in the OptimaX journal and "
                   "OptimaX-Rescue.cmd restore the factory values."),
    "gt.uv.ask": ("Нижча напруга може зробити роботу нестабільною: гра чи драйвер можуть вилетіти. Після застосування "
                  "запустіть «Перевірити стабільність». Застосувати?",
                  "Меньшее напряжение может сделать работу нестабильной: игра или драйвер могут вылететь. После "
                  "применения запустите «Проверить стабильность». Применить?",
                  "Lower voltage can make things unstable: a game or the driver may crash. After applying, run Check "
                  "stability. Apply?"),
    "gt.ok": ("готово", "готово", "done"),
    "gt.fail": ("не вдалося", "не удалось", "failed"),
    "gt.fail_d": ("Не вдалося: {e}", "Не удалось: {e}", "Failed: {e}"),
    "gt.applied": ("Налаштування відеокарти застосовано.", "Настройки видеокарты применены.",
                   "Graphics card settings applied."),
    "gt.partial": ("Застосовано частково, не вдалося: {what}.", "Применено частично, не удалось: {what}.",
                   "Partly applied, failed: {what}."),
    "gt.reset_done": ("Відеокарту повернуто до заводських значень.", "Видеокарта возвращена к заводским значениям.",
                      "The graphics card is back to factory values."),
    "gt.log.fans": ("[GPU] Вентилятори: {mode} — {st}", "[GPU] Вентиляторы: {mode} — {st}", "[GPU] Fans: {mode} — {st}"),
    "gt.log.reset": ("[GPU] Заводські значення — {st}", "[GPU] Заводские значения — {st}", "[GPU] Factory values — {st}"),
    "gt.log.crashed": ("[GPU] Минулого разу після зміни частоти чи напруги був збій — повернуто заводські значення.",
                       "[GPU] В прошлый раз после изменения частоты или напряжения был сбой — возвращены заводские "
                       "значения.",
                       "[GPU] Last time there was a crash after a clock or voltage change — factory values restored."),
    "gt.crashed_toast": ("Після зміни налаштувань відеокарти був збій — повернуто заводські значення.",
                         "После изменения настроек видеокарты был сбой — возвращены заводские значения.",
                         "There was a crash after the graphics card settings changed — factory values restored."),
    "gt.applied_toast": ("Профіль відеокарти застосовано.", "Профиль видеокарты применён.",
                         "Graphics card profile applied."),
    "gt.journal": ("Відеокарта {gpu}: кулери й андервольт", "Видеокарта {gpu}: кулеры и андервольт",
                   "Graphics card {gpu}: fans & undervolt"),
    "gt.err.journal": ("журнал відкату недоступний ({e}) — нічого не змінено",
                       "журнал отката недоступен ({e}) — ничего не изменено",
                       "the rollback journal is unavailable ({e}) — nothing was changed"),
    "gt.verify_q": ("Стрес-тест відеокарти {m} хв із поточними налаштуваннями. Не вдасться — повернуться заводські "
                    "значення. Почати?",
                    "Стресс-тест видеокарты {m} мин с текущими настройками. Не пройдёт — вернутся заводские значения. "
                    "Начать?",
                    "A {m}-minute GPU stress test with the current settings. If it fails, the factory values come back. "
                    "Start?"),
    "gt.verify_run": ("Перевірка стабільності: {t} / {d} с", "Проверка стабильности: {t} / {d} с",
                      "Stability check: {t} / {d} s"),
    "gt.verify_ok": ("Стабільно. Середня потужність {w} W, найвища температура {t} °C.",
                     "Стабильно. Средняя мощность {w} W, наибольшая температура {t} °C.",
                     "Stable. Average power {w} W, highest temperature {t} °C."),
    "gt.verify_ok_t": ("Налаштування відеокарти стабільні.", "Настройки видеокарты стабильны.",
                       "The graphics card settings are stable."),
    "gt.verify_bad": ("Нестабільно — повернуто заводські значення.", "Нестабильно — возвращены заводские значения.",
                      "Unstable — factory values restored."),
    "gt.verify_cancel": ("Перевірку зупинено.", "Проверка остановлена.", "The check was stopped."),
    "gt.tune_q": ("Автопідбір займе приблизно {m} хв: кроки зі стрес-тестом відеокарти, на кожному — перевірка кадру до "
                  "біта. Не користуйтеся ПК для ігор у цей час. За першої помилки OptimaX відступить на безпечне "
                  "значення; якщо щось піде не так — заводські. Почати?",
                  "Автоподбор займёт около {m} мин: шаги со стресс-тестом видеокарты, на каждом — проверка кадра до "
                  "бита. Не используйте ПК для игр в это время. При первой ошибке OptimaX отступит на безопасное "
                  "значение; если что-то пойдёт не так — заводские. Начать?",
                  "Auto-tune takes about {m} min: steps with a GPU stress test, each checking the frame bit for bit. "
                  "Don't game on the PC meanwhile. At the first error OptimaX backs off to a safe value; if anything "
                  "goes wrong — factory values. Start?"),
    "gt.tune_run": ("Автопідбір: {phase} {v} · {t} с", "Автоподбор: {phase} {v} · {t} с", "Auto-tune: {phase} {v} · {t} s"),
    "gt.phase.idle": ("очікування", "ожидание", "waiting"),
    "gt.phase.baseline": ("заводський замір", "заводской замер", "factory baseline"),
    "gt.phase.step": ("крок", "шаг", "step"),
    "gt.phase.verify": ("фінальна перевірка", "финальная проверка", "final check"),
    "gt.phase.done": ("готово", "готово", "done"),
    "gt.phase.failed": ("не вдалося", "не удалось", "failed"),
    "gt.phase.cancelled": ("зупинено", "остановлено", "stopped"),
    "gt.tune.unsupported": ("Автопідбір для цієї карти недоступний.", "Автоподбор для этой карты недоступен.",
                            "Auto-tune isn't available for this card."),
    "gt.tune.step": ("[GPU] Автопідбір {v}: {st}", "[GPU] Автоподбор {v}: {st}", "[GPU] Auto-tune {v}: {st}"),
    "gt.tune.ok": ("стабільно", "стабильно", "stable"),
    "gt.tune.bad": ("помилка", "ошибка", "error"),
    "gt.tune.base_bad": ("Карта нестабільна вже на заводських налаштуваннях — андервольт не підбираємо; перевірте "
                         "охолодження й драйвер.",
                         "Карта нестабильна уже на заводских настройках — андервольт не подбираем; проверьте охлаждение "
                         "и драйвер.",
                         "The card is unstable even at factory settings — no undervolt; check the cooling and the "
                         "driver."),
    "gt.tune.done": ("[GPU] Автопідбір завершено: {v}", "[GPU] Автоподбор завершён: {v}", "[GPU] Auto-tune finished: {v}"),
    "gt.tune.verify_bad": ("Фінальна перевірка не пройшла — повернуто заводські значення.",
                           "Финальная проверка не прошла — возвращены заводские значения.",
                           "The final check failed — factory values restored."),
    "gt.tune.apply_bad": ("Драйвер не прийняв значення — повернуто заводські.",
                          "Драйвер не принял значение — возвращены заводские.",
                          "The driver didn't accept the value — factory values restored."),
    "gt.tune.no_margin": ("Запасу для андервольту немає: помилка вже на першому кроці.",
                          "Запаса для андервольта нет: ошибка уже на первом шаге.",
                          "There's no undervolt headroom: an error on the very first step."),
    "gt.tune.end.done": ("Андервольт підібрано й перевірено.", "Андервольт подобран и проверен.",
                         "Undervolt found and verified."),
    "gt.tune.end.failed": ("Андервольт не підібрано — заводські значення.", "Андервольт не подобран — заводские "
                           "значения.", "No undervolt found — factory values."),
    "gt.tune.end.cancelled": ("Автопідбір зупинено — заводські значення.", "Автоподбор остановлен — заводские значения.",
                              "Auto-tune stopped — factory values."),
    "gt.r.value": ("Знайдено", "Найдено", "Found"),
    "gt.r.power": ("Потужність під навантаженням", "Мощность под нагрузкой", "Power under load"),
    "gt.r.temp": ("Найвища температура", "Наибольшая температура", "Highest temperature"),
    "gt.r.score": ("Бали тесту", "Баллы теста", "Test score"),
    "lat.drivers": ("Драйвери з найдовшими DPC / ISR", "Драйверы с самыми долгими DPC / ISR",
                    "Drivers with the longest DPCs / ISRs"),
    "lat.drv_row": ("DPC: {dpc} ({dn}) · ISR: {isr} ({inn})", "DPC: {dpc} ({dn}) · ISR: {isr} ({inn})",
                    "DPC: {dpc} ({dn}) · ISR: {isr} ({inn})"),
}
