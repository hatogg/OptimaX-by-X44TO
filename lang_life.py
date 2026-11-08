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

    # ── «Чому зависає?» (freezecatch.py) ──
    "fz.title": ("Чому зависає?", "Почему зависает?", "Why does it freeze?"),
    "fz.sub": ("Ловить фризи на 1–5 секунд, коли зависає все одразу — картинка, відео й звук, — і показує, що в цей момент "
               "робила система: драйвер, диск, відеокарта чи щось поза Windows.",
               "Ловит фризы на 1–5 секунд, когда зависает всё сразу — картинка, видео и звук, — и показывает, что в этот "
               "момент делала система: драйвер, диск, видеокарта или что-то вне Windows.",
               "Catches 1–5 second freezes when everything hangs at once — picture, video and sound — and shows what the "
               "system was doing at that moment: a driver, the drive, the graphics card or something outside Windows."),
    "fz.enable": ("Ловити фризи у фоні", "Ловить фризы в фоне", "Catch freezes in the background"),
    "fz.enable_d": ("Окремий легкий процес стежить, поки OptimaX відкрита або згорнута в трей (менше 1% процесора). "
                    "Фризи рідкісні — залиште ловець на день-два.",
                    "Отдельный лёгкий процесс следит, пока OptimaX открыта или свёрнута в трей (меньше 1% процессора). "
                    "Фризы редкие — оставьте ловец на день-два.",
                    "A separate lightweight process watches while OptimaX is open or in the tray (under 1% CPU). "
                    "Freezes are rare, so leave it on for a day or two."),
    "fz.deep": ("Глибокий запис драйверів (WPR)", "Глубокая запись драйверов (WPR)", "Deep driver recording (WPR)"),
    "fz.deep_d": ("Вбудований у Windows записувач тримає в пам'яті останню хвилину DPC і переривань (до 64 МБ) і "
                  "зберігає її в момент фризу. Файл .etl відкривається у Windows Performance Analyzer — там видно, який "
                  "саме драйвер тримав процесор.",
                  "Встроенный в Windows записыватель держит в памяти последнюю минуту DPC и прерываний (до 64 МБ) и "
                  "сохраняет её в момент фриза. Файл .etl открывается в Windows Performance Analyzer — там видно, какой "
                  "именно драйвер держал процессор.",
                  "The recorder built into Windows keeps the last minute of DPCs and interrupts in memory (up to 64 MB) "
                  "and saves it when a freeze happens. The .etl file opens in Windows Performance Analyzer, which shows "
                  "exactly which driver held the CPU."),
    "fz.folder": ("Відкрити папку записів", "Открыть папку записей", "Open the recordings folder"),
    "fz.clear": ("Очистити список", "Очистить список", "Clear the list"),
    "fz.fail": ("Ловець не запустився: {err}", "Ловец не запустился: {err}", "The catcher didn't start: {err}"),
    "fz.started": ("Ловець фризів працює. Коли зависне — OptimaX повідомить, що знайшла.",
                   "Ловец фризов работает. Когда зависнет — OptimaX сообщит, что нашла.",
                   "The freeze catcher is on. When the PC freezes, OptimaX will tell you what it found."),
    "fz.etl": ("Запис WPR", "Запись WPR", "WPR recording"),
    "fz.state_on": ("Стежу з {since}. Зловлено фризів: {n}.", "Слежу с {since}. Поймано фризов: {n}.",
                    "Watching since {since}. Freezes caught: {n}."),
    "fz.state_off": ("Ловець вимкнено. Зловлено раніше: {n}.", "Ловец выключен. Поймано ранее: {n}.",
                     "The catcher is off. Caught earlier: {n}."),
    "fz.deep_on": ("Глибокий запис працює.", "Глубокая запись работает.", "Deep recording is on."),
    "fz.deep_err": ("Глибокий запис не запустився: {err}", "Глубокая запись не запустилась: {err}",
                    "Deep recording didn't start: {err}"),
    "fz.ftpm_t": ("Увімкнено AMD fTPM", "Включён AMD fTPM", "AMD fTPM is on"),
    "fz.ftpm_d": ("Модуль TPM вбудований у процесор AMD. На Ryzen це відома причина фризів на 1–2 секунди із заїканням "
                  "звуку: AMD виправляла це в прошивках BIOS 2022 року й новіших, але не всі виробники ноутбуків і плат "
                  "переносили виправлення. Дата вашого BIOS: {bios}.",
                  "Модуль TPM встроен в процессор AMD. На Ryzen это известная причина фризов на 1–2 секунды с заиканием "
                  "звука: AMD исправляла это в прошивках BIOS 2022 года и новее, но не все производители ноутбуков и плат "
                  "переносили исправление. Дата вашего BIOS: {bios}.",
                  "The TPM is built into the AMD processor. On Ryzen it's a known cause of 1–2 second freezes with "
                  "stuttering sound: AMD fixed it in BIOS firmware from 2022 onwards, but not every laptop and "
                  "motherboard maker shipped the fix. Your BIOS date: {bios}."),
    "fz.sum": ("Найчастіша причина: {cause} — {share}% із {n} фризів",
               "Самая частая причина: {cause} — {share}% из {n} фризов",
               "Most common cause: {cause} — {share}% of {n} freezes"),
    "fz.sum_mixed": ("Причини різні ({n} фризів): {causes}. Почніть із першої — вона найсерйозніша.",
                     "Причины разные ({n} фризов): {causes}. Начните с первой — она самая серьёзная.",
                     "Mixed causes ({n} freezes): {causes}. Start with the first — it's the most serious."),
    "fz.none_on": ("Фризів поки не було. Користуйтеся ПК як завжди — OptimaX запише кожен.",
                   "Фризов пока не было. Пользуйтесь ПК как обычно — OptimaX запишет каждый.",
                   "No freezes yet. Use the PC as usual — OptimaX will record each one."),
    "fz.none_off": ("Увімкніть ловець і користуйтеся ПК як завжди: коли все зависне на секунду-дві, тут з'явиться, що в "
                    "цей момент відбувалося.",
                    "Включите ловец и пользуйтесь ПК как обычно: когда всё зависнет на секунду-две, здесь появится, что "
                    "в этот момент происходило.",
                    "Turn the catcher on and use the PC as usual: when everything hangs for a second or two, what was "
                    "going on at that moment will show up here."),
    "fz.item": ("{when} — фриз {dur} с", "{when} — фриз {dur} с", "{when} — {dur} s freeze"),
    "fz.toast": ("Фриз {dur} с — ймовірна причина: {cause}", "Фриз {dur} с — вероятная причина: {cause}",
                 "{dur} s freeze — likely cause: {cause}"),
    "fz.banner_t": ("OptimaX зловила фриз", "OptimaX поймала фриз", "OptimaX caught a freeze"),
    # коротка назва причини (підсумок, сповіщення)
    "fz.short.hardware": ("апаратна помилка (WHEA)", "аппаратная ошибка (WHEA)", "hardware error (WHEA)"),
    "fz.short.disk": ("накопичувач", "накопитель", "the drive"),
    "fz.short.gpu": ("відеодрайвер", "видеодрайвер", "the graphics driver"),
    "fz.short.dpc": ("драйвер (DPC і переривання)", "драйвер (DPC и прерывания)", "a driver (DPCs and interrupts)"),
    "fz.short.net": ("мережевий драйвер", "сетевой драйвер", "the network driver"),
    "fz.short.usb": ("USB-пристрій", "USB-устройство", "a USB device"),
    "fz.short.io": ("перевантажений диск", "перегруженный диск", "an overloaded drive"),
    "fz.short.memory": ("брак пам'яті", "нехватка памяти", "low memory"),
    "fz.short.cpu": ("завантажений процесор", "загруженный процессор", "a fully loaded CPU"),
    "fz.short.ftpm": ("AMD fTPM", "AMD fTPM", "AMD fTPM"),
    "fz.short.firmware": ("поза Windows (BIOS чи залізо)", "вне Windows (BIOS или железо)",
                          "outside Windows (BIOS or hardware)"),
    "fz.short.unknown": ("не з'ясовано", "не выяснено", "not determined"),
    # пояснення причини
    "fz.cat.hardware": ("Поруч із фризом Windows записала апаратну помилку WHEA — процесор, пам'ять або шина PCIe. Це "
                        "залізо або нестабільний розгін.",
                        "Рядом с фризом Windows записала аппаратную ошибку WHEA — процессор, память или шина PCIe. Это "
                        "железо или нестабильный разгон.",
                        "Windows logged a WHEA hardware error next to the freeze — the CPU, memory or PCIe bus. That's "
                        "hardware or an unstable overclock."),
    "fz.cat.disk": ("Поруч із фризом накопичувач перестав відповідати, і контролер його скидав. Поки диск «думає», чекає "
                    "вся система.",
                    "Рядом с фризом накопитель перестал отвечать, и контроллер его сбрасывал. Пока диск «думает», ждёт "
                    "вся система.",
                    "Next to the freeze the drive stopped responding and the controller reset it. While the drive "
                    "\"thinks\", the whole system waits."),
    "fz.cat.gpu": ("Поруч із фризом відеодрайвер завис і перезапустився.",
                   "Рядом с фризом видеодрайвер завис и перезапустился.",
                   "Next to the freeze the graphics driver hung and restarted."),
    "fz.cat.dpc": ("Під час фризу одне ядро було зайняте обробкою DPC і переривань — так виглядає драйвер, що надовго "
                   "забирає процесор (часто Wi-Fi, звук, тачпад чи ACPI на ноутбуках).",
                   "Во время фриза одно ядро было занято обработкой DPC и прерываний — так выглядит драйвер, который "
                   "надолго забирает процессор (часто Wi-Fi, звук, тачпад или ACPI на ноутбуках).",
                   "During the freeze one core was busy handling DPCs and interrupts — that's what a driver hogging the "
                   "CPU looks like (often Wi-Fi, audio, the touchpad or ACPI on laptops)."),
    "fz.cat.net": ("Під час фризу ядро було зайняте DPC і перериваннями, а мережевий драйвер записав помилку — "
                   "найімовірніше, винен він.",
                   "Во время фриза ядро было занято DPC и прерываниями, а сетевой драйвер записал ошибку — скорее "
                   "всего, виноват он.",
                   "During the freeze a core was busy with DPCs and interrupts, and the network driver logged an error "
                   "— it's most likely to blame."),
    "fz.cat.usb": ("Під час фризу ядро було зайняте DPC і перериваннями, а поруч — помилка USB: пристрій, що "
                   "відвалюється, або його драйвер.",
                   "Во время фриза ядро было занято DPC и прерываниями, а рядом — ошибка USB: отваливающееся "
                   "устройство или его драйвер.",
                   "During the freeze a core was busy with DPCs and interrupts, with a USB error next to it: a device "
                   "that keeps dropping out, or its driver."),
    "fz.cat.io": ("Під час фризу диск був зайнятий на 100% з довгою чергою запитів — система чекала на нього.",
                  "Во время фриза диск был занят на 100% с длинной очередью запросов — система ждала его.",
                  "During the freeze the drive was 100% busy with a long request queue — the system was waiting for "
                  "it."),
    "fz.cat.memory": ("Під час фризу бракувало оперативної пам'яті, і Windows активно читала з файлу підкачки.",
                      "Во время фриза не хватало оперативной памяти, и Windows активно читала из файла подкачки.",
                      "During the freeze RAM ran short and Windows was busy reading from the page file."),
    "fz.cat.cpu": ("Під час фризу процесор був завантажений повністю.",
                   "Во время фриза процессор был загружен полностью.",
                   "During the freeze the CPU was fully loaded."),
    "fz.cat.ftpm": ("Під час фризу Windows нічого не робила: ні драйвери, ні диск, ні процесор не були зайняті, і журнал "
                    "порожній. Так виглядає зупинка на рівні прошивки, а на цьому ПК увімкнено AMD fTPM — найімовірніший "
                    "винуватець.",
                    "Во время фриза Windows ничего не делала: ни драйверы, ни диск, ни процессор не были заняты, и "
                    "журнал пуст. Так выглядит остановка на уровне прошивки, а на этом ПК включён AMD fTPM — самый "
                    "вероятный виновник.",
                    "During the freeze Windows was doing nothing: no drivers, drive or CPU were busy, and the log is "
                    "empty. That's what a firmware-level stall looks like, and this PC has AMD fTPM on — the most "
                    "likely culprit."),
    "fz.cat.firmware": ("Під час фризу Windows нічого не робила: ні драйвери, ні диск, ні процесор не були зайняті. "
                        "Систему зупинило щось поза Windows — прошивка (BIOS, SMM) або залізо.",
                        "Во время фриза Windows ничего не делала: ни драйверы, ни диск, ни процессор не были заняты. "
                        "Систему остановило что-то вне Windows — прошивка (BIOS, SMM) или железо.",
                        "During the freeze Windows was doing nothing: no drivers, drive or CPU were busy. Something "
                        "outside Windows stopped the system — firmware (BIOS, SMM) or hardware."),
    "fz.cat.unknown": ("Даних про цей момент замало, щоб назвати причину. Кілька наступних фризів зроблять картину ясною.",
                       "Данных об этом моменте мало, чтобы назвать причину. Несколько следующих фризов прояснят "
                       "картину.",
                       "There's too little data about this moment to name a cause. The next few freezes will make it "
                       "clear."),
    # рід причини (підсумок)
    "fz.kind.hw": ("Найімовірніше — залізо.", "Скорее всего — железо.", "Most likely hardware."),
    "fz.kind.driver": ("Найімовірніше — драйвер: програмна причина, що лікується оновленням чи заміною драйвера.",
                       "Скорее всего — драйвер: программная причина, которая лечится обновлением или заменой драйвера.",
                       "Most likely a driver: a software cause fixed by updating or replacing the driver."),
    "fz.kind.soft": ("Найімовірніше — програмна причина: навантаження, а не несправність.",
                     "Скорее всего — программная причина: нагрузка, а не неисправность.",
                     "Most likely a software cause: load, not a fault."),
    "fz.kind.firmware": ("Найімовірніше — прошивка (BIOS) або залізо, а не Windows.",
                         "Скорее всего — прошивка (BIOS) или железо, а не Windows.",
                         "Most likely firmware (BIOS) or hardware, not Windows."),
    "fz.kind.unknown": ("Причину поки не з'ясовано.", "Причина пока не выяснена.", "The cause isn't clear yet."),
    # докази
    "fz.e.event": ("Подія {src} {id}: {msg}", "Событие {src} {id}: {msg}", "Event {src} {id}: {msg}"),
    "fz.e.dpc": ("DPC і переривання: {pct}% часу ядра {core}", "DPC и прерывания: {pct}% времени ядра {core}",
                 "DPCs and interrupts: {pct}% of core {core}'s time"),
    "fz.e.quiet": ("DPC і переривання — {pct}%, процесор — {cpu}%: Windows не була зайнята",
                   "DPC и прерывания — {pct}%, процессор — {cpu}%: Windows не была занята",
                   "DPCs and interrupts {pct}%, CPU {cpu}%: Windows wasn't busy"),
    "fz.e.disk": ("Диск зайнятий на {busy}%, у черзі {q} запитів", "Диск занят на {busy}%, в очереди {q} запросов",
                  "Drive {busy}% busy, {q} requests queued"),
    "fz.e.mem": ("Вільно {mb} МБ пам'яті, читань із підкачки {pages}/с",
                 "Свободно {mb} МБ памяти, чтений из подкачки {pages}/с",
                 "{mb} MB of memory free, {pages} page-file reads/s"),
    "fz.e.cpu": ("Процесор {pct}%, найбільше — {proc}", "Процессор {pct}%, больше всего — {proc}",
                 "CPU {pct}%, mostly {proc}"),
    "fz.e.ftpm": ("Увімкнено AMD fTPM", "Включён AMD fTPM", "AMD fTPM is on"),
    "fz.e.nodata": ("Лічильники Windows не встигли зібратися", "Счётчики Windows не успели собраться",
                    "Windows counters weren't collected in time"),
    "fz.e.app": ("На екрані: {app}", "На экране: {app}", "On screen: {app}"),
    "fz.e.etl": ("Збережено запис WPR — кнопка праворуч", "Сохранена запись WPR — кнопка справа",
                 "A WPR recording was saved — button on the right"),
    # поради
    "fz.a.whea": ("Подивіться «Чому впав комп?» вище й Hardware Center: апаратні помилки WHEA, тести пам'яті й процесора.",
                  "Посмотрите «Почему упал компьютер?» выше и Hardware Center: аппаратные ошибки WHEA, тесты памяти и "
                  "процессора.",
                  "Check Why did the PC crash? above and Hardware Center: WHEA hardware errors, memory and CPU tests."),
    "fz.a.oc_off": ("Поверніть заводські частоти: вимкніть розгін процесора, пам'яті (XMP / EXPO) й відеокарти та "
                    "андервольт — і перевірте, чи зникнуть фризи.",
                    "Верните заводские частоты: отключите разгон процессора, памяти (XMP / EXPO) и видеокарты и "
                    "андервольт — и проверьте, исчезнут ли фризы.",
                    "Go back to stock clocks: turn off CPU, memory (XMP / EXPO) and GPU overclocks and undervolts, "
                    "then see whether the freezes stop."),
    "fz.a.heat": ("Перевірте температури під навантаженням (Hardware Center → датчики).",
                  "Проверьте температуры под нагрузкой (Hardware Center → датчики).",
                  "Check temperatures under load (Hardware Center → sensors)."),
    "fz.a.disk_fw": ("Оновіть прошивку SSD (утиліта виробника диска) і драйвер чипсета чи накопичувача з сайту "
                     "виробника ноутбука або плати.",
                     "Обновите прошивку SSD (утилита производителя диска) и драйвер чипсета или накопителя с сайта "
                     "производителя ноутбука или платы.",
                     "Update the SSD firmware (the drive maker's tool) and the chipset or storage driver from the laptop "
                     "or motherboard maker's site."),
    "fz.a.disk_smart": ("Перевірте здоров'я диска: Hardware Center → накопичувачі (SMART).",
                        "Проверьте здоровье диска: Hardware Center → накопители (SMART).",
                        "Check the drive's health: Hardware Center → drives (SMART)."),
    "fz.a.disk_aspm": ("Спробуйте оптимізацію «Вимкнути енергозбереження PCIe» — NVMe перестане засинати (її можна "
                       "відкотити).",
                       "Попробуйте оптимизацию «Отключить энергосбережение PCIe» — NVMe перестанет засыпать (её можно "
                       "откатить).",
                       "Try the Turn off PCIe power saving optimization — the NVMe drive will stop dozing off (it can be "
                       "rolled back)."),
    "fz.a.gpu_driver": ("Перевстановіть відеодрайвер начисто (DDU у безпечному режимі) й поверніть заводські частоти "
                        "карти.",
                        "Переустановите видеодрайвер начисто (DDU в безопасном режиме) и верните заводские частоты "
                        "карты.",
                        "Reinstall the graphics driver cleanly (DDU in Safe Mode) and return the card to stock clocks."),
    "fz.a.gpu_hybrid": ("На ноутбуці з двома відеокартами фриз буває під час перемикання між ними: у панелі NVIDIA чи AMD "
                        "закріпіть ігри за дискретною картою або ввімкніть режим лише дискретної (MUX), якщо він є.",
                        "На ноутбуке с двумя видеокартами фриз бывает при переключении между ними: в панели NVIDIA или "
                        "AMD закрепите игры за дискретной картой или включите режим только дискретной (MUX), если он "
                        "есть.",
                        "On a laptop with two GPUs a freeze can happen while switching between them: pin games to the "
                        "discrete card in the NVIDIA or AMD panel, or turn on discrete-only (MUX) mode if it has one."),
    "fz.a.deep": ("Увімкніть «Глибокий запис драйверів» вище — наступний фриз покаже, який саме драйвер винен.",
                  "Включите «Глубокую запись драйверов» выше — следующий фриз покажет, какой именно драйвер виноват.",
                  "Turn on Deep driver recording above — the next freeze will show exactly which driver is to blame."),
    "fz.a.drivers": ("Оновіть драйвери чипсета, Wi-Fi, звуку й тачпада з сайту виробника ноутбука чи плати (не через "
                     "Windows Update).",
                     "Обновите драйверы чипсета, Wi-Fi, звука и тачпада с сайта производителя ноутбука или платы (не "
                     "через Windows Update).",
                     "Update the chipset, Wi-Fi, audio and touchpad drivers from the laptop or motherboard maker's site "
                     "(not through Windows Update)."),
    "fz.a.latencymon": ("Для перевірки в реальному часі — LatencyMon (resplendence.com): він показує драйвер із "
                        "найдовшими DPC.",
                        "Для проверки в реальном времени — LatencyMon (resplendence.com): он показывает драйвер с самыми "
                        "долгими DPC.",
                        "For a live check, use LatencyMon (resplendence.com): it shows the driver with the longest "
                        "DPCs."),
    "fz.a.net_driver": ("Оновіть драйвер мережевої карти чи Wi-Fi з сайту виробника. Для перевірки на день вимкніть "
                        "адаптер Wi-Fi у диспетчері пристроїв і підключіться кабелем.",
                        "Обновите драйвер сетевой карты или Wi-Fi с сайта производителя. Для проверки на день отключите "
                        "адаптер Wi-Fi в диспетчере устройств и подключитесь кабелем.",
                        "Update the network or Wi-Fi driver from the maker's site. To test, disable the Wi-Fi adapter in "
                        "Device Manager for a day and use a cable."),
    "fz.a.usb_suspend": ("Спробуйте оптимізацію «Вимкнути призупинення USB».",
                         "Попробуйте оптимизацию «Отключить приостановку USB».",
                         "Try the Turn off USB suspend optimization."),
    "fz.a.usb_port": ("Від'єднуйте USB-пристрої по одному (хаби, донгли, гарнітури) або підключіть їх в інші порти.",
                      "Отключайте USB-устройства по одному (хабы, донглы, гарнитуры) или подключите их в другие порты.",
                      "Unplug USB devices one at a time (hubs, dongles, headsets) or move them to other ports."),
    "fz.a.io_proc": ("Подивіться, хто навантажує диск у такі моменти: Диспетчер задач → «Диск» або «Чому лагає?» вище.",
                     "Посмотрите, кто нагружает диск в такие моменты: Диспетчер задач → «Диск» или «Почему лагает?» "
                     "выше.",
                     "See what loads the drive at those moments: Task Manager → Disk, or Why is it lagging? above."),
    "fz.a.ram": ("Закрийте зайве або збільште файл підкачки; якщо таке часто — бракує оперативної пам'яті.",
                 "Закройте лишнее или увеличьте файл подкачки; если такое часто — не хватает оперативной памяти.",
                 "Close what you don't need or enlarge the page file; if it happens often, the PC needs more RAM."),
    "fz.a.cpu_proc": ("Подивіться на процес, що забирав процесор, і чи не працювали в цей час антивірус або оновлення.",
                      "Посмотрите на процесс, который забирал процессор, и не работали ли в это время антивирус или "
                      "обновления.",
                      "Look at the process that took the CPU, and whether the antivirus or updates were running then."),
    "fz.a.bios": ("Оновіть BIOS / UEFI з сайту виробника ноутбука чи плати — фризи на рівні прошивки лікуються саме так.",
                  "Обновите BIOS / UEFI с сайта производителя ноутбука или платы — фризы на уровне прошивки лечатся "
                  "именно так.",
                  "Update the BIOS / UEFI from the laptop or motherboard maker's site — that's how firmware-level "
                  "freezes get fixed."),
    "fz.a.ftpm_test": ("Перевірка fTPM: якщо диск не зашифровано BitLocker чи «Шифруванням пристрою» (або ключ "
                       "відновлення записано), вимкніть fTPM у BIOS на день-два. Фризи зникли — винен він. Windows Hello "
                       "може попросити налаштувати PIN заново; потім увімкніть fTPM назад або поставте BIOS із "
                       "виправленням.",
                       "Проверка fTPM: если диск не зашифрован BitLocker или «Шифрованием устройства» (или ключ "
                       "восстановления записан), отключите fTPM в BIOS на день-два. Фризы исчезли — виноват он. Windows "
                       "Hello может попросить настроить PIN заново; потом включите fTPM обратно или поставьте BIOS с "
                       "исправлением.",
                       "To test fTPM: if the drive isn't encrypted with BitLocker or Device Encryption (or you have the "
                       "recovery key written down), turn fTPM off in the BIOS for a day or two. If the freezes stop, it's "
                       "the culprit. Windows Hello may ask you to set up the PIN again; afterwards turn fTPM back on or "
                       "install a BIOS with the fix."),
    "fz.a.chipset": ("Встановіть драйвер чипсета з сайту AMD чи Intel або виробника ноутбука.",
                     "Установите драйвер чипсета с сайта AMD или Intel либо производителя ноутбука.",
                     "Install the chipset driver from AMD's or Intel's site, or the laptop maker's."),
    "fz.a.keep": ("Залиште ловець увімкненим ще на день-два — кілька фризів покажуть закономірність.",
                  "Оставьте ловец включённым ещё на день-два — несколько фризов покажут закономерность.",
                  "Leave the catcher on for another day or two — a few freezes will reveal the pattern."),

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
    "wn.69.honest": ("Чесніші режими: в «Ігровому» більше немає змін, що не прискорюють (очищення історії й пам'яті, "
                     "мережеві твіки для TCP, фіксована підкачка, прискорення миші). А «доведено» тепер означає, що "
                     "зміну заміряли окремо, а не що вона просто була в пакеті з приростом.",
                     "Честнее режимы: в «Игровом» больше нет изменений, которые не ускоряют (очистка истории и памяти, "
                     "сетевые твики для TCP, фиксированная подкачка, ускорение мыши). А «доказано» теперь значит, что "
                     "изменение замерили отдельно, а не что оно просто было в пакете с приростом.",
                     "More honest modes: Gaming no longer includes changes that don't speed anything up (history and "
                     "RAM cleanup, TCP network tweaks, a fixed page file, mouse acceleration). And “proven” now means "
                     "the change was measured on its own, not just that it was in a batch that gained FPS."),
    "wn.69.removed": ("Прибрано 7 змін, які не діють або шкодять: вимкнення Defender (Windows його ігнорує), примусовий "
                      "HPET, застарілі параметри пам'яті й мережі, дубль пріоритету процесора. Якщо щось із цього "
                      "застосовано, воно позначене в «Резервних копіях», і його можна відкотити.",
                      "Убрано 7 изменений, которые не работают или вредят: отключение Defender (Windows его "
                      "игнорирует), принудительный HPET, устаревшие параметры памяти и сети, дубль приоритета "
                      "процессора. Если что-то из этого применено, оно отмечено в «Резервных копиях», и его можно "
                      "откатить.",
                      "Removed 7 changes that don't work or do harm: turning off Defender (Windows ignores it), forced "
                      "HPET, obsolete memory and network settings, a duplicate CPU priority tweak. If any of them is "
                      "applied, it's marked in Backups and can be rolled back."),
    "wn.69.rollback": ("Надійніший відкат: кожне налаштування тепер змінює лише одна оптимізація, тож відкат однієї "
                       "більше не скасовує іншу, а пошук винної зміни не плутається. Оптимізації DirectX (вікна, VRR, "
                       "Auto HDR) повертають лише свій параметр.",
                       "Надёжнее откат: каждую настройку теперь меняет только одна оптимизация, поэтому откат одной "
                       "больше не отменяет другую, а поиск виновного изменения не путается. Оптимизации DirectX "
                       "(окна, VRR, Auto HDR) возвращают только свой параметр.",
                       "More reliable rollback: each setting is now changed by one optimization only, so rolling one "
                       "back no longer cancels another, and the culprit search no longer gets confused. The DirectX "
                       "optimizations (windowed, VRR, Auto HDR) restore only their own part."),
    "wn.612.freeze": ("Нове: «Чому зависає?» на сторінці «Діагностика». Ловець фризів у фоні помічає моменти, коли на "
                      "секунду-п'ять зависає все одразу — картинка й звук, — і показує, що в цей момент робила система: "
                      "драйвер, диск, відеокарта, AMD fTPM чи щось поза Windows.",
                      "Новое: «Почему зависает?» на странице «Диагностика». Ловец фризов в фоне замечает моменты, когда "
                      "на секунду-пять зависает всё сразу — картинка и звук, — и показывает, что в этот момент делала "
                      "система: драйвер, диск, видеокарта, AMD fTPM или что-то вне Windows.",
                      "New: Why does it freeze? on the Diagnostics page. The background freeze catcher notices when "
                      "everything hangs for one to five seconds — picture and sound — and shows what the system was "
                      "doing: a driver, the drive, the graphics card, AMD fTPM or something outside Windows."),
    "wn.612.deep": ("Щоб знайти конкретний драйвер — «Глибокий запис драйверів»: вбудований у Windows WPR зберігає DPC і "
                    "переривання саме в момент фризу. Дякуємо Dr34mChas3r за ідею!",
                    "Чтобы найти конкретный драйвер — «Глубокая запись драйверов»: встроенный в Windows WPR сохраняет DPC "
                    "и прерывания именно в момент фриза. Спасибо Dr34mChas3r за идею!",
                    "To pin down the exact driver, use Deep driver recording: WPR, built into Windows, saves DPCs and "
                    "interrupts right at the moment of the freeze. Thanks to Dr34mChas3r for the idea!"),
    "wn.611.menu": ("Менше пунктів у меню: «Залізо» тепер розділ Hardware Center «Перевірка збірки», а перемикачі "
                    "сторінки «Вигляд» — в експертному меню, у групі «Вигляд».",
                    "Меньше пунктов в меню: «Железо» теперь раздел Hardware Center «Проверка сборки», а переключатели "
                    "страницы «Внешний вид» — в экспертном меню, в группе «Внешний вид».",
                    "Fewer menu items: Hardware is now Hardware Center's Build check section, and the Appearance "
                    "switches are in the Expert menu under Appearance."),
    "wn.611.catalog": ("Чесний каталог: оптимізації поділено на «Швидкість» — те, що видно в замірах FPS, — і "
                       "«Зручність і приватність», від якої FPS не росте.",
                       "Честный каталог: оптимизации разделены на «Скорость» — то, что видно в замерах FPS, — и "
                       "«Удобство и приватность», от которой FPS не растёт.",
                       "An honest catalog: optimizations are split into Speed — what shows up in FPS measurements — "
                       "and Comfort and privacy, which doesn't raise FPS."),
    "wn.611.oc": ("Розгін відеокарти — чотири безпечні кроки з MSI Afterburner і стрес-тест OptimaX для перевірки "
                  "кожного кроку, без сторонніх AI-чатів.",
                  "Разгон видеокарты — четыре безопасных шага с MSI Afterburner и стресс-тест OptimaX для проверки "
                  "каждого шага, без сторонних AI-чатов.",
                  "GPU overclocking: four safe steps with MSI Afterburner and the OptimaX stress test to check each "
                  "step, with no third-party AI chats."),
    "wn.611.support": ("OptimaX безкоштовна й без реклами. Якщо вона вам допомогла, підтримати розробку можна через "
                       "банку — посилання «Підтримати» на сайті програми.",
                       "OptimaX бесплатна и без рекламы. Если она вам помогла, поддержать разработку можно через "
                       "банку — ссылка «Поддержать» на сайте программы.",
                       "OptimaX is free and ad-free. If it helped you, you can support development through the jar — "
                       "the Support link on the program's website."),
    "wn.6101.menu": ("Меню простіше: «Мережа» й «Блок реклами» тепер в «Інструментах», «Ноутбук» видно лише на ноутбуці, "
                     "а в «Діагностиці» першим іде «Чому лагає?» — «Чому впав комп?» і монітор на телефоні нижче.",
                     "Меню проще: «Сеть» и «Блок рекламы» теперь в «Инструментах», «Ноутбук» виден только на ноутбуке, "
                     "а в «Диагностике» первым идёт «Почему лагает?» — «Почему упал комп?» и монитор на телефоне ниже.",
                     "A simpler menu: Network and Ad blocker are now under Tools, Laptop shows on laptops only, and "
                     "Diagnostics opens with Why is it lagging? — Why did the PC crash? and the phone monitor are below."),
    "wn.6101.setup": ("Інсталятор: галочка «Запустити OptimaX» наприкінці встановлення більше не дає помилку 740 — "
                      "Windows просто спитає дозвіл, і програма відкриється.",
                      "Установщик: галочка «Запустить OptimaX» в конце установки больше не даёт ошибку 740 — Windows "
                      "просто спросит разрешение, и программа откроется.",
                      "Installer: the “Launch OptimaX” box at the end of setup no longer fails with error 740 — Windows "
                      "simply asks for permission and the program opens."),
    "wn.610.temp": ("Температура процесора в Hardware Center тепер справжня: OptimaX бере її з Core Temp, HWiNFO, AIDA64 "
                    "чи LibreHardwareMonitor, якщо котрась запущена. Теплова зона ACPI, яка на багатьох платах завжди "
                    "показує 27,8 °C, більше не видається за процесор.",
                    "Температура процессора в Hardware Center теперь настоящая: OptimaX берёт её из Core Temp, HWiNFO, "
                    "AIDA64 или LibreHardwareMonitor, если какая-то запущена. Тепловая зона ACPI, которая на многих "
                    "платах всегда показывает 27,8 °C, больше не выдаётся за процессор.",
                    "The CPU temperature in Hardware Center is now real: OptimaX reads it from Core Temp, HWiNFO, AIDA64 "
                    "or LibreHardwareMonitor if one is running. The ACPI thermal zone that reads 27.8 °C on many boards "
                    "no longer poses as the CPU."),
    "wn.610.gpu": ("Датчики відеокарти — тієї, що тестується чи малює гру. З двома картами NVIDIA (GT 710 + P106) "
                   "температура й частоти раніше бралися з першої на шині.",
                   "Датчики видеокарты — той, что тестируется или рисует игру. С двумя картами NVIDIA (GT 710 + P106) "
                   "температура и частоты раньше брались с первой на шине.",
                   "GPU sensors now belong to the card being tested or rendering the game. With two NVIDIA cards "
                   "(GT 710 + P106) temperature and clocks used to come from the first one on the bus."),
    "wn.610.info": ("Точніші відомості про залізо: швидкість кожного модуля пам'яті на старих платах більше не вдвічі "
                    "менша (DDR3-1333 замість 667), виробник замість коду на кшталт «80CE», правильний тип модуля, "
                    "відеопам'ять вбудованої графіки в МБ.",
                    "Точнее сведения о железе: скорость каждого модуля памяти на старых платах больше не вдвое меньше "
                    "(DDR3-1333 вместо 667), производитель вместо кода вроде «80CE», правильный тип модуля, видеопамять "
                    "встроенной графики в МБ.",
                    "More accurate hardware info: per-module memory speed on older boards is no longer halved "
                    "(DDR3-1333 instead of 667), the maker instead of a code like “80CE”, the right module type, and "
                    "integrated graphics memory in MB."),
    "wn.69.fast": ("Швидше: вікно з'являється, не чекаючи всіх сторінок, а вибрані вбудовані додатки видаляються одним "
                   "запуском PowerShell замість окремого для кожного.",
                   "Быстрее: окно появляется, не дожидаясь всех страниц, а выбранные встроенные приложения удаляются "
                   "одним запуском PowerShell вместо отдельного для каждого.",
                   "Faster: the window appears without waiting for every page, and the selected built-in apps are "
                   "removed in one PowerShell run instead of one per app."),
    "wn.681.nvpair": ("Монітор на іншій відеокарті NVIDIA (наприклад, GT 710) поруч з P106: OptimaX тепер прямо каже, що "
                      "для ігор це не працює, і що зробити — замість поради перевстановити драйвер.",
                      "Монитор на другой видеокарте NVIDIA (например, GT 710) рядом с P106: OptimaX теперь прямо "
                      "говорит, что для игр это не работает, и что сделать, — вместо совета переустановить драйвер.",
                      "Monitor on another NVIDIA card (say, a GT 710) next to a P106: OptimaX now says plainly that this "
                      "doesn't work for games and what to do, instead of telling you to reinstall the driver."),
    "wn.681.check": ("Перевірка «на якій карті малює гра» з двома картами NVIDIA більше не каже «малює P106», коли малює "
                     "карта з монітором.",
                     "Проверка «на какой карте рисует игра» с двумя картами NVIDIA больше не говорит «рисует P106», "
                     "когда рисует карта с монитором.",
                     "With two NVIDIA cards, the “which card renders the game” check no longer says “the P106” when the "
                     "card with the monitor renders."),
    "wn.68.hwc": ("Hardware Center у групі «Пристрій»: тести процесора, пам'яті, відеопам'яті, дисків (SMART і NVMe), "
                  "батареї, екрана й периферії, стрес-тести з аварійною зупинкою за температурою і звіти HTML, JSON "
                  "та PDF.",
                  "Hardware Center в группе «Устройство»: тесты процессора, памяти, видеопамяти, дисков (SMART и "
                  "NVMe), батареи, экрана и периферии, стресс-тесты с аварийной остановкой по температуре и отчёты "
                  "HTML, JSON и PDF.",
                  "Hardware Center in the Device group: CPU, RAM, VRAM, disk (SMART and NVMe), battery, screen and "
                  "peripheral tests, stress tests with an emergency stop on temperature, and HTML, JSON and PDF "
                  "reports."),
    "wn.68.overlay": ("FPS-оверлей в іграх: FPS, 1% low, час кадру й датчики поверх гри, без втручання в її процес. "
                      "Увімкнути — у Hardware Center, показати чи сховати — Ctrl+Shift+F10.",
                      "FPS-оверлей в играх: FPS, 1% low, время кадра и датчики поверх игры, без вмешательства в её "
                      "процесс. Включить — в Hardware Center, показать или скрыть — Ctrl+Shift+F10.",
                      "An in-game FPS overlay: FPS, 1% lows, frametime and sensors on top of the game without touching "
                      "its process. Turn it on in Hardware Center; Ctrl+Shift+F10 shows or hides it."),
    "wn.68.gpu": ("Ноутбук із двома відеокартами: у GPU-тесті можна вибрати дискретну, а OptimaX перевіряє, яка карта "
                  "справді малювала.",
                  "Ноутбук с двумя видеокартами: в GPU-тесте можно выбрать дискретную, а OptimaX проверяет, какая "
                  "карта действительно рисовала.",
                  "Laptops with two GPUs: the GPU test lets you pick the discrete card, and OptimaX checks which card "
                  "really rendered."),
    "wn.68.buy": ("Перевірка ПК перед покупкою: 14 кроків і порівняння з тим, що обіцяє продавець.",
                  "Проверка ПК перед покупкой: 14 шагов и сравнение с тем, что обещает продавец.",
                  "Pre-purchase PC check: 14 steps and a comparison with what the seller promises."),
    "wn.68.diag": ("Хто заважав грі у фоні, що обмежує продуктивність, аналіз дампів синіх екранів і SFC / DISM — "
                   "за вашим підтвердженням.",
                   "Кто мешал игре в фоне, что ограничивает производительность, анализ дампов синих экранов и "
                   "SFC / DISM — по вашему подтверждению.",
                   "What got in the game's way in the background, what limits performance, blue screen dump "
                   "analysis, and SFC / DISM after you confirm."),
    "wn.67.safe": ("Безпечніше: журнал відкату, PresentMon і оновлення тепер лежать у захищеній папці, куди інші "
                   "програми не можуть нічого підкинути.",
                   "Безопаснее: журнал отката, PresentMon и обновления теперь лежат в защищённой папке, куда другие "
                   "программы не могут ничего подбросить.",
                   "Safer: the rollback journal, PresentMon and updates now live in a protected folder where other "
                   "programs can't plant anything."),
    "wn.67.portable": ("Автозапуск, розклад і DNS-фільтр — лише у встановленій версії: файл портативної могла б "
                       "підмінити будь-яка програма.",
                       "Автозапуск, расписание и DNS-фильтр — только в установленной версии: файл портативной мог бы "
                       "подменить любая программа.",
                       "Autostart, the schedule and the DNS filter are for the installed version only: any program "
                       "could replace the portable one's file."),
    "wn.67.fast": ("Швидший повторний запуск: аналіз заліза не повторюється до перезавантаження ПК.",
                   "Быстрее повторный запуск: анализ железа не повторяется до перезагрузки ПК.",
                   "Faster restarts: hardware detection isn't repeated until the PC reboots."),
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
