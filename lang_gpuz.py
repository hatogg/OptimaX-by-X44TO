"""Тексти розділу «Відеокарта» (паспорт як у GPU-Z): (uk, ru, en)."""
STRINGS = {
    "gz.title": ("Відеокарти", "Видеокарты", "Graphics cards"),
    "gz.none": ("Відеоадаптерів на шині PCI не знайдено.", "Видеоадаптеров на шине PCI не найдено.",
                "No graphics adapters found on the PCI bus."),
    "gz.loading": ("Читаю відомості про відеокарти…", "Читаю сведения о видеокартах…", "Reading graphics card info…"),
    "gz.failed": ("Не вдалося прочитати відеокарти — спробуйте «Оновити»",
                  "Не удалось прочитать видеокарты — попробуйте «Обновить»",
                  "Could not read the graphics cards — try Refresh"),
    "gz.refresh": ("Оновити", "Обновить", "Refresh"),
    "gz.probe": ("Перевірити DirectX / Vulkan", "Проверить DirectX / Vulkan", "Check DirectX / Vulkan"),
    "gz.probing": ("Перевіряю…", "Проверяю…", "Checking…"),
    "gz.g.device": ("Пристрій", "Устройство", "Device"),
    "gz.g.bus": ("Шина", "Шина", "Bus interface"),
    "gz.g.memory": ("Пам'ять", "Память", "Memory"),
    "gz.g.sensors": ("Частоти й датчики", "Частоты и датчики", "Clocks and sensors"),
    "gz.g.api": ("Графічні API", "Графические API", "Graphics APIs"),
    "gz.g.notes": ("Висновки", "Выводы", "Notes"),
    "gz.name": ("Назва", "Название", "Name"),
    "gz.vendor": ("Виробник GPU", "Производитель GPU", "GPU vendor"),
    "gz.subvendor": ("Виробник плати", "Производитель платы", "Subvendor"),
    "gz.device_id": ("ID пристрою", "ID устройства", "Device ID"),
    "gz.revision": ("Ревізія", "Ревизия", "Revision"),
    "gz.role": ("Роль", "Роль", "Role"),
    "gz.kind.dgpu": ("дискретна", "дискретная", "discrete"),
    "gz.kind.igpu": ("вбудована", "встроенная", "integrated"),
    "gz.kind.mining": ("майнінгова, без відеовиходів", "майнинговая, без видеовыходов",
                       "mining card, no video outputs"),
    "gz.display": ("монітор підключено до неї", "монитор подключён к ней", "drives the monitor"),
    "gz.driver": ("Драйвер", "Драйвер", "Driver version"),
    "gz.driver_date": ("Дата драйвера", "Дата драйвера", "Driver date"),
    "gz.vbios": ("Відео-BIOS", "Видео-BIOS", "BIOS version"),
    "gz.src_reg": ("за драйвером", "по драйверу", "per driver"),
    "gz.location": ("Адреса PCI", "Адрес PCI", "PCI address"),
    "gz.bus_cur": ("Зараз", "Сейчас", "Current link"),
    "gz.bus_max": ("Максимум карти", "Максимум карты", "Card maximum"),
    "gz.rebar": ("Resizable BAR", "Resizable BAR", "Resizable BAR"),
    "gz.rebar_on": ("Так — BAR {mb} MB", "Да — BAR {mb} MB", "Yes — BAR {mb} MB"),
    "gz.rebar_off": ("Ні — BAR {mb} MB", "Нет — BAR {mb} MB", "No — BAR {mb} MB"),
    "gz.mem_size": ("Обсяг", "Объём", "Memory size"),
    "gz.mem_shared": ("{mb} MB (+ до {shared} MB з ОЗП)", "{mb} MB (+ до {shared} MB из ОЗУ)",
                      "{mb} MB (+ up to {shared} MB of system RAM)"),
    "gz.mem_type": ("Тип", "Тип", "Memory type"),
    "gz.bus_width": ("Ширина шини", "Ширина шины", "Bus width"),
    "gz.mem_used": ("Зайнято", "Занято", "Memory used"),
    "gz.clock": ("Частота GPU", "Частота GPU", "GPU clock"),
    "gz.clock_max": ("Частота GPU, макс.", "Частота GPU, макс.", "GPU clock, max"),
    "gz.mem_clock": ("Частота пам'яті", "Частота памяти", "Memory clock"),
    "gz.mem_clock_max": ("Частота пам'яті, макс.", "Частота памяти, макс.", "Memory clock, max"),
    "gz.temp": ("Температура", "Температура", "Temperature"),
    "gz.load": ("Завантаження", "Загрузка", "GPU load"),
    "gz.power": ("Споживання", "Потребление", "Board power"),
    "gz.fan": ("Вентилятор", "Вентилятор", "Fan"),
    "gz.dx12": ("DirectX 12", "DirectX 12", "DirectX 12"),
    "gz.dx12_yes": ("Так (пристрій D3D12, рівень 11_0)", "Да (устройство D3D12, уровень 11_0)",
                    "Yes (D3D12 device, feature level 11_0)"),
    "gz.dx12_no": ("Ні — пристрій D3D12 не створюється", "Нет — устройство D3D12 не создаётся",
                   "No — a D3D12 device cannot be created"),
    "gz.vulkan": ("Vulkan", "Vulkan", "Vulkan"),
    "gz.opengl": ("OpenGL", "OpenGL", "OpenGL"),
    "gz.drv": ("драйвер", "драйвер", "driver"),
    "gz.f.full": ("Лінія працює на повну: {link}.", "Линия работает на полную: {link}.",
                  "The link runs at full: {link}."),
    "gz.f.narrow": ("Карта працює на x{cur} замість x{max}: слот з меншою кількістю ліній, райзер або лінії, поділені "
                    "з іншим пристроєм (NVMe). Для майнінгу це байдуже, для ігор — вузьке місце, особливо коли кадри "
                    "йдуть шиною на вбудовану графіку.",
                    "Карта работает на x{cur} вместо x{max}: слот с меньшим числом линий, райзер или линии, поделённые "
                    "с другим устройством (NVMe). Для майнинга это неважно, для игр — узкое место, особенно когда "
                    "кадры идут по шине во встроенную графику.",
                    "The card runs at x{cur} instead of x{max}: a slot with fewer lanes, a riser, or lanes shared with "
                    "another device (NVMe). Irrelevant for mining, a bottleneck for games — especially when frames "
                    "travel over the bus to the integrated graphics."),
    "gz.f.slow_idle": ("Зараз PCIe {cur} замість {max}: у простої карта знижує швидкість лінії, щоб заощадити енергію. "
                       "Це не несправність — перевірте під навантаженням: запустіть гру чи GPU-тест і натисніть "
                       "«Оновити».",
                       "Сейчас PCIe {cur} вместо {max}: в простое карта снижает скорость линии ради экономии энергии. "
                       "Это не неисправность — проверьте под нагрузкой: запустите игру или GPU-тест и нажмите "
                       "«Обновить».",
                       "PCIe {cur} instead of {max} right now: at idle the card lowers the link speed to save power. "
                       "That is not a fault — check under load: start a game or the GPU test and press Refresh."),
    "gz.f.slow_load": ("Під навантаженням ({util}%) лінія PCIe {cur} замість {max}: слот чи плата підтримують лише "
                       "{cur}, або покоління обмежене в BIOS.",
                       "Под нагрузкой ({util}%) линия PCIe {cur} вместо {max}: слот или плата поддерживают только "
                       "{cur}, или поколение ограничено в BIOS.",
                       "Under load ({util}%) the link is PCIe {cur} instead of {max}: the slot or board only supports "
                       "{cur}, or the generation is limited in the BIOS."),
    "gz.f.igpu_bus": ("Вбудована графіка — частина процесора, окремої лінії PCIe-слота в неї немає.",
                      "Встроенная графика — часть процессора, отдельной линии PCIe-слота у неё нет.",
                      "Integrated graphics is part of the CPU — it has no PCIe slot link of its own."),
    "gz.f.no_link": ("Windows не повідомила стан лінії PCIe для цієї карти.",
                     "Windows не сообщила состояние линии PCIe для этой карты.",
                     "Windows did not report the PCIe link state for this card."),
    "gz.f.rebar_off": ("Resizable BAR вимкнено, хоча ця карта його підтримує: увімкніть у BIOS «Above 4G Decoding» і "
                       "«Re-Size BAR Support».",
                       "Resizable BAR выключен, хотя эта карта его поддерживает: включите в BIOS «Above 4G Decoding» и "
                       "«Re-Size BAR Support».",
                       "Resizable BAR is off although this card supports it: enable Above 4G Decoding and Re-Size BAR "
                       "Support in the BIOS."),
    "gz.f.mining": ("Майнінгова карта без відеовиходів: монітор під'єднано до іншої карти, тож кадри гри копіюються "
                    "через шину PCIe.",
                    "Майнинговая карта без видеовыходов: монитор подключён к другой карте, поэтому кадры игры "
                    "копируются через шину PCIe.",
                    "Mining card without video outputs: the monitor is on another card, so game frames are copied "
                    "over the PCIe bus."),
    "gz.f.no_nvml": ("NVML (бібліотека драйвера NVIDIA) недоступна для цієї карти — частоти, температура й ширина шини "
                     "пам'яті невідомі.",
                     "NVML (библиотека драйвера NVIDIA) недоступна для этой карты — частоты, температура и ширина шины "
                     "памяти неизвестны.",
                     "NVML (the NVIDIA driver library) is not available for this card — clocks, temperature and "
                     "memory bus width are unknown."),
    "gz.f.sensors_other": ("Частоти й датчики тут читаються лише для NVIDIA (через NVML); для цієї карти — «—».",
                           "Частоты и датчики здесь читаются только для NVIDIA (через NVML); для этой карты — «—».",
                           "Clocks and sensors are read only for NVIDIA here (via NVML); for this card they are “—”."),
    "gz.f.no_probe": ("DirectX і Vulkan ще не перевірено — натисніть «Перевірити DirectX / Vulkan».",
                      "DirectX и Vulkan ещё не проверены — нажмите «Проверить DirectX / Vulkan».",
                      "DirectX and Vulkan have not been checked yet — press Check DirectX / Vulkan."),
}
