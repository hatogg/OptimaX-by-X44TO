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
    "lat.r.cpu_pct": ("Час ядра в DPC/ISR (пік за секунду)", "Время ядра в DPC/ISR (пик за секунду)",
                      "Core time in DPC/ISR (peak per second)"),
    "lat.r.duration": ("Тривалість", "Длительность", "Duration"),
    "lat.f.stall": ("Програма стояла до {us}: процесор забирали переривання, драйвери чи інші процеси ({n} разів "
                    "від {lim}).",
                    "Программа стояла до {us}: процессор забирали прерывания, драйверы или другие процессы ({n} раз "
                    "от {lim}).",
                    "The program stalled for up to {us}: interrupts, drivers or other processes took the CPU ({n} "
                    "times of {lim} or more)."),
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
    "lat.adv.stall_other": ("Програма стояла довше, ніж тривав найдовший DPC чи переривання, — процесор забирали не "
                            "драйвери Windows, а BIOS (SMI), гіпервізор чи програми з пріоритетом реального часу "
                            "(звукові студії, захоплення відео). Оновіть BIOS і драйвер чипсета, закрийте такі програми.",
                            "Программа стояла дольше, чем длился самый долгий DPC или прерывание, — процессор забирали "
                            "не драйверы Windows, а BIOS (SMI), гипервизор или программы с приоритетом реального "
                            "времени (звуковые студии, захват видео). Обновите BIOS и драйвер чипсета, закройте такие "
                            "программы.",
                            "The program stalled longer than the longest DPC or interrupt — the CPU was taken not by "
                            "Windows drivers but by the BIOS (SMI), a hypervisor or real-time priority programs (audio "
                            "workstations, video capture). Update the BIOS and chipset driver, close such programs."),
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
    "lat.drivers": ("Драйвери з найдовшими DPC / ISR", "Драйверы с самыми долгими DPC / ISR",
                    "Drivers with the longest DPCs / ISRs"),
    "lat.drv_row": ("DPC: {dpc} ({dn}) · ISR: {isr} ({inn})", "DPC: {dpc} ({dn}) · ISR: {isr} ({inn})",
                    "DPC: {dpc} ({dn}) · ISR: {isr} ({inn})"),
}
