"""OptimaX — переклади розділу «Датчики» в Hardware Center (sensors.py, pages_sensors.py)."""

STRINGS = {
    "hwc.sec.sensors": ("Датчики", "Датчики", "Sensors"),
    "sn.title": ("Датчики", "Датчики", "Sensors"),
    "sn.sub": ("Усі показники заліза в одній таблиці, як в AIDA64 чи HWiNFO: поточне, мінімум, максимум і середнє з "
               "моменту відкриття розділу (або скидання). Оновлення раз на секунду; лише читання.",
               "Все показатели железа в одной таблице, как в AIDA64 или HWiNFO: текущее, минимум, максимум и среднее "
               "с момента открытия раздела (или сброса). Обновление раз в секунду; только чтение.",
               "Every hardware reading in one table, like AIDA64 or HWiNFO: current, minimum, maximum and average "
               "since the section was opened (or reset). Updated once a second; read-only."),
    "sn.col.name": ("Датчик", "Датчик", "Sensor"),
    "sn.col.cur": ("Зараз", "Сейчас", "Current"),
    "sn.col.min": ("Мін.", "Мин.", "Min"),
    "sn.col.max": ("Макс.", "Макс.", "Max"),
    "sn.col.avg": ("Середнє", "Среднее", "Average"),
    "sn.k.cpu": ("процесор", "процессор", "CPU"),
    "sn.k.gpu": ("відеокарта", "видеокарта", "GPU"),
    "sn.k.ram": ("пам'ять", "память", "memory"),
    "sn.k.ssd": ("SSD", "SSD", "SSD"),
    "sn.k.hdd": ("HDD", "HDD", "HDD"),
    "sn.k.board": ("плата", "плата", "motherboard"),
    "sn.u.mhz": ("МГц", "МГц", "MHz"),
    "sn.u.w": ("Вт", "Вт", "W"),
    "sn.u.v": ("В", "В", "V"),
    "sn.u.mb": ("МБ", "МБ", "MB"),
    "sn.u.gb": ("ГБ", "ГБ", "GB"),
    "sn.u.rpm": ("об/хв", "об/мин", "RPM"),
    "sn.r.temp": ("Температура", "Температура", "Temperature"),
    "sn.r.core_max": ("Найгарячіше ядро", "Самое горячее ядро", "Hottest core"),
    "sn.r.load": ("Завантаження", "Загрузка", "Load"),
    "sn.r.clock_avg": ("Частота (середня)", "Частота (средняя)", "Clock (average)"),
    "sn.r.clock0": ("Частота ядра 0", "Частота ядра 0", "Core 0 clock"),
    "sn.r.vid": ("Напруга ядра (VID)", "Напряжение ядра (VID)", "Core voltage (VID)"),
    "sn.r.power_pkg": ("Споживання пакета", "Потребление пакета", "Package power"),
    "sn.r.power": ("Споживання", "Потребление", "Power"),
    "sn.r.core_clock": ("Частота ядра", "Частота ядра", "Core clock"),
    "sn.r.mem_clock": ("Частота пам'яті", "Частота памяти", "Memory clock"),
    "sn.r.vram": ("Відеопам'ять зайнято", "Видеопамять занято", "VRAM used"),
    "sn.r.shared": ("Спільна пам'ять зайнято", "Общая память занято", "Shared memory used"),
    "sn.r.of": ("(з {n} {u})", "(из {n} {u})", "(of {n} {u})"),
    "sn.r.fan": ("Вентилятор", "Вентилятор", "Fan"),
    "sn.r.ram_used": ("Зайнято", "Занято", "Used"),
    "sn.r.acpi": ("Теплова зона ACPI", "Тепловая зона ACPI", "ACPI thermal zone"),
    "sn.g.ram": ("Оперативна пам'ять", "Оперативная память", "System memory"),
    "sn.g.board": ("Системна плата (ACPI)", "Системная плата (ACPI)", "Motherboard (ACPI)"),
    "sn.reset": ("Скинути мін./макс.", "Сбросить мин./макс.", "Reset min/max"),
    "sn.rec": ("Записувати в CSV", "Записывать в CSV", "Record to CSV"),
    "sn.rec_stop": ("Зупинити запис", "Остановить запись", "Stop recording"),
    "sn.rec_on": ("Запис: {file} · рядків: {n}", "Запись: {file} · строк: {n}", "Recording: {file} · rows: {n}"),
    "sn.rec_saved": ("Запис збережено: рядків — {n}", "Запись сохранена: строк — {n}", "Recording saved: {n} rows"),
    "sn.rec_wait": ("Зачекайте секунду — показники ще не прочитано.",
                    "Подождите секунду — показатели ещё не прочитаны.",
                    "Wait a second — the readings have not been read yet."),
    "sn.rec_refused": ("Цей шлях — посилання (symlink чи junction) або папка. OptimaX працює з правами адміністратора "
                       "й за посиланнями не пише — виберіть звичайну папку.",
                       "Этот путь — ссылка (symlink или junction) или папка. OptimaX работает с правами администратора "
                       "и по ссылкам не пишет — выберите обычную папку.",
                       "This path is a link (symlink or junction) or a folder. OptimaX runs as administrator and does "
                       "not write through links — choose a regular folder."),
    "sn.rec_err": ("Запис у CSV не вдався: {err}", "Запись в CSV не удалась: {err}", "Writing the CSV failed: {err}"),
    "sn.note.pause": ("Поки розділ не на екрані чи вікно згорнуте, датчики не опитуються (мін./макс. теж). Виняток — "
                      "запис у CSV: він триває й зі згорнутим вікном, а сповіщення тоді приходять у трей.",
                      "Пока раздел не на экране или окно свёрнуто, датчики не опрашиваются (мин./макс. тоже). "
                      "Исключение — запись в CSV: она идёт и со свёрнутым окном, а уведомления приходят в трей.",
                      "While this section is not on screen or the window is minimized, sensors are not polled "
                      "(min/max too). The exception is CSV recording: it continues with the window minimized, and "
                      "alerts then go to the tray."),
    "sn.note.cpu_temp": ("Температуру процесора Windows без драйвера не віддає. Запустіть Core Temp, HWiNFO (Shared "
                         "Memory Support), AIDA64 (Shared memory) чи LibreHardwareMonitor (Remote Web Server) або "
                         "встановіть PawnIO — OptimaX прочитає її звідти.",
                         "Температуру процессора Windows без драйвера не отдаёт. Запустите Core Temp, HWiNFO (Shared "
                         "Memory Support), AIDA64 (Shared memory) или LibreHardwareMonitor (Remote Web Server) либо "
                         "установите PawnIO — OptimaX прочитает её оттуда.",
                         "Windows does not expose the CPU temperature without a driver. Run Core Temp, HWiNFO (Shared "
                         "Memory Support), AIDA64 (Shared memory) or LibreHardwareMonitor (Remote Web Server), or "
                         "install PawnIO — OptimaX will read it from there."),
    "sn.al.title": ("Сповіщення про перегрів", "Уведомления о перегреве", "Overheating alerts"),
    "sn.al.sub": ("Сповіщення — коли температура {n} с поспіль вище порога; знімається, коли охолоне на {h} °C нижче "
                  "порога. Поки перегрів триває, повторно не турбуємо.",
                  "Уведомление — когда температура {n} с подряд выше порога; снимается, когда остынет на {h} °C ниже "
                  "порога. Пока перегрев длится, повторно не беспокоим.",
                  "Alert when a temperature stays above the limit for {n} s in a row; it clears once it cools {h} °C "
                  "below the limit. No repeats while the overheating lasts."),
    "sn.al.on": ("Сповіщати", "Уведомлять", "Alerts on"),
    "sn.al.cpu": ("Процесор", "Процессор", "CPU"),
    "sn.al.gpu": ("Відеокарта", "Видеокарта", "GPU"),
    "sn.al.ssd": ("SSD / NVMe", "SSD / NVMe", "SSD / NVMe"),
    "sn.al.hdd": ("HDD", "HDD", "HDD"),
    "sn.al.defaults": ("Типові", "По умолчанию", "Defaults"),
    "sn.al.raised": ("Перегрів: {what} — {v} °C (поріг {lim} °C)", "Перегрев: {what} — {v} °C (порог {lim} °C)",
                     "Overheating: {what} — {v} °C (limit {lim} °C)"),
    "sn.al.cleared": ("[✓] Охололо: {what} — {v} °C", "[✓] Остыло: {what} — {v} °C",
                      "[✓] Cooled down: {what} — {v} °C"),
    "sn.al.banner": ("Вище порога: {what}", "Выше порога: {what}", "Above the limit: {what}"),
    "sn.log.reset": ("Датчики: мін./макс. скинуто", "Датчики: мин./макс. сброшены", "Sensors: min/max reset"),
    "sn.log.rec_on": ("[►] Датчики: запис у {path}", "[►] Датчики: запись в {path}",
                      "[►] Sensors: recording to {path}"),
    "sn.log.rec_off": ("[✓] Датчики: записано {n} рядків у {path}", "[✓] Датчики: записано {n} строк в {path}",
                       "[✓] Sensors: {n} rows written to {path}"),
    "sn.csv.time": ("Час", "Время", "Time"),
}
