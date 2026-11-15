"""Переклади OptimaX 6.16: «Здоров'я ПК» — перевірка Windows з оцінкою, поясненнями й виправленнями
(українська, російська, англійська)."""

STRINGS = {
    # ── «Що нового» 7.0.1 ──
    "wn.701.rebar": ("Resizable BAR (AMD SmartAccess Memory) більше не показується вимкненим, коли він увімкнений.",
                     "Resizable BAR (AMD SmartAccess Memory) больше не показывается выключенным, когда он включён.",
                     "Resizable BAR (AMD SmartAccess Memory) is no longer shown as off when it is on."),
    "wn.701.smart": ("«Здоров'я ПК» читає SMART SATA-дисків: зношений SSD чи диск на порозі відмови тепер видно, "
                     "навіть коли Windows пише «Healthy».",
                     "«Здоровье ПК» читает SMART SATA-дисков: изношенный SSD или диск на пороге отказа теперь видно, "
                     "даже когда Windows пишет «Healthy».",
                     "PC health reads SMART on SATA drives: a worn-out SSD or a drive at its failure threshold now "
                     "shows up even when Windows says “Healthy”."),
    "wn.701.nic": ("Interrupt Moderation і Flow Control, вимкнені вручну, тепер видно й на адаптерах Realtek 2.5G "
                   "і USB.",
                   "Interrupt Moderation и Flow Control, выключенные вручную, теперь видно и на адаптерах Realtek 2.5G "
                   "и USB.",
                   "Interrupt Moderation and Flow Control turned off by hand now show up on Realtek 2.5G and USB "
                   "adapters too."),
    # ── «Що нового» 7.0.0 ──
    "wn.700.design": ("Новий вигляд: графіт і один червоний акцент замість синьо-фіолетових градієнтів, без світіння й "
                      "кольорових плиток. Показники — як на приладі, з одиницями, а основна кнопка на кожному екрані одна. "
                      "Новий логотип OptimaX.",
                      "Новый вид: графит и один красный акцент вместо сине-фиолетовых градиентов, без свечения и цветных "
                      "плиток. Показатели — как на приборе, с единицами, а основная кнопка на каждом экране одна. "
                      "Новый логотип OptimaX.",
                      "New look: graphite and a single red accent instead of blue-violet gradients, with no glow or "
                      "colored tiles. Readings look like an instrument's, with units, and every screen has one primary "
                      "button. A new OptimaX logo."),
    # ── «Що нового» 6.17 ──
    "wn.617.safety": ("Захист і відкат: незалежний аудит коду знайшов місця, де стороння програма могла б підсунути "
                      "OptimaX чуже «оновлення» чи команду для аварійного відкату. Усе закрито; OptimaX-Rescue.cmd більше "
                      "не позначає відкат виконаним, якщо якийсь крок не вдався.",
                      "Защита и откат: независимый аудит кода нашёл места, где посторонняя программа могла бы подсунуть "
                      "OptimaX чужое «обновление» или команду для аварийного отката. Всё закрыто; OptimaX-Rescue.cmd "
                      "больше не отмечает откат выполненным, если какой-то шаг не удался.",
                      "Safety and rollback: an independent code audit found places where another program could slip "
                      "OptimaX a fake “update” or a command for the emergency rollback. All closed; OptimaX-Rescue.cmd "
                      "no longer marks a rollback done when a step failed."),
    "wn.617.honest": ("Надійніший відкат: зміни застосовуються строго по одній, запис для відкату з'являється до зміни, "
                      "а «Зупинити» не обриває команду посередині. Скидання Windows Update, файл підкачки й DNS кажуть "
                      "«частково», якщо щось не вдалося.",
                      "Надёжнее откат: изменения применяются строго по одному, запись для отката появляется до "
                      "изменения, а «Остановить» не обрывает команду посередине. Сброс Windows Update, файл подкачки и "
                      "DNS говорят «частично», если что-то не удалось.",
                      "Sturdier rollback: changes apply strictly one at a time, the undo record exists before the "
                      "change, and Stop never cuts a command in half. Windows Update reset, page file and DNS say "
                      "“partial” when something failed."),
    "wn.617.tweaks": ("Чесніші оптимізації: «Точний таймер» — лише на Windows 11 (на Windows 10 він не діє), Dynamic "
                      "Tick і заборона простою процесора — лише вручну, System Responsiveness тепер справді діє (10 "
                      "замість 0, яке Windows ігнорувала).",
                      "Честнее оптимизации: «Точный таймер» — только на Windows 11 (на Windows 10 он не действует), "
                      "Dynamic Tick и запрет простоя процессора — только вручную, System Responsiveness теперь "
                      "действительно работает (10 вместо 0, которое Windows игнорировала).",
                      "More honest optimizations: Precise timer is Windows 11 only (it has no effect on Windows 10), "
                      "Dynamic Tick and disabling CPU idle are manual only, and System Responsiveness now actually works "
                      "(10 instead of 0, which Windows ignored)."),
    # ── «Що нового» 6.16 ──
    "wn.616.health": ("«Здоров'я ПК» (Діагностика): одна перевірка Windows з оцінкою 0–100 — диски, збої, драйвери, "
                      "оновлення, антивірус, брандмауер, UAC, SMBv1, час і звук. Кожна картка пояснює, чому це важливо "
                      "й що робити, і показує команду, якою можна перевірити самому.",
                      "«Здоровье ПК» (Диагностика): одна проверка Windows с оценкой 0–100 — диски, сбои, драйверы, "
                      "обновления, антивирус, брандмауэр, UAC, SMBv1, время и звук. Каждая карточка объясняет, почему "
                      "это важно и что делать, и показывает команду, которой можно проверить самому.",
                      "PC health (Diagnostics): one Windows check-up with a 0–100 score — drives, crashes, drivers, "
                      "updates, antivirus, firewall, UAC, SMBv1, time and sound. Every card says why it matters and "
                      "what to do, and shows the command to check it yourself."),
    "wn.616.fix": ("«Виправити все безпечне» — один план, з якого можна прибрати будь-що, і повторна перевірка: "
                   "«Виправлено», «Досі проблема» чи «Не вдалося». Зміни налаштувань — з відкатом у «Резервних копіях».",
                   "«Исправить всё безопасное» — один план, из которого можно убрать что угодно, и повторная проверка: "
                   "«Исправлено», «Всё ещё проблема» или «Не удалось». Изменения настроек — с откатом в «Резервных "
                   "копиях».",
                   "Fix all safe issues — one plan you can untick anything from, then a re-check: Fixed, Still a "
                   "problem or Failed. Settings changes can be undone on the Backup page."),
    # ── картка ──
    "hc.title": ("Здоров'я ПК", "Здоровье ПК", "PC health"),
    "hc.sub": ("Одна перевірка Windows: диски, збої, драйвери, оновлення, антивірус, брандмауер, налаштування безпеки, "
               "час і звук. Пояснює простими словами й пропонує безпечні виправлення з відкатом.",
               "Одна проверка Windows: диски, сбои, драйверы, обновления, антивирус, брандмауэр, настройки безопасности, "
               "время и звук. Объясняет простыми словами и предлагает безопасные исправления с откатом.",
               "One Windows check-up: drives, crashes, drivers, updates, antivirus, firewall, security settings, time "
               "and sound. Explained in plain words, with safe fixes you can roll back."),
    "hc.check": ("Перевірити", "Проверить", "Check"),
    "hc.fix_all": ("Виправити все безпечне ({n})", "Исправить всё безопасное ({n})", "Fix all safe issues ({n})"),
    "hc.never": ("Ще не перевіряли. Перевірка триває до хвилини й нічого не змінює.",
                 "Ещё не проверяли. Проверка длится до минуты и ничего не меняет.",
                 "Not checked yet. The check takes up to a minute and changes nothing."),
    "hc.summary": ("Проблем: {bad} · уваги: {warn} · гаразд: {ok} · перевірено {when}",
                   "Проблем: {bad} · внимания: {warn} · в порядке: {ok} · проверено {when}",
                   "Problems: {bad} · warnings: {warn} · OK: {ok} · checked {when}"),
    "hc.verdict.ok": ("Windows у доброму стані", "Windows в хорошем состоянии", "Windows is in good shape"),
    "hc.verdict.warn": ("Є що покращити", "Есть что улучшить", "Some things need attention"),
    "hc.verdict.bad": ("Є проблеми, які варто виправити", "Есть проблемы, которые стоит исправить",
                       "There are problems worth fixing"),
    "hc.show_ok": ("Показати, що гаразд ({n})", "Показать, что в порядке ({n})", "Show what's OK ({n})"),
    "hc.hide_ok": ("Сховати, що гаразд", "Скрыть, что в порядке", "Hide what's OK"),
    "hc.not_admin": ("OptimaX запущено без прав адміністратора: частину налаштувань безпеки Windows не показує, а "
                     "виправлення не спрацюють.",
                     "OptimaX запущен без прав администратора: часть настроек безопасности Windows не показывает, а "
                     "исправления не сработают.",
                     "OptimaX is running without administrator rights: Windows hides some security settings, and fixes "
                     "won't work."),
    "hc.why_l": ("Чому це важливо: {text}", "Почему это важно: {text}", "Why it matters: {text}"),
    "hc.todo_l": ("Що робити: {text}", "Что делать: {text}", "What to do: {text}"),
    "hc.cmd": ("Перевірити самому: {cmd}", "Проверить самому: {cmd}", "Check it yourself: {cmd}"),
    "hc.err": ("Не вдалося оцінити: {err}", "Не удалось оценить: {err}", "Could not evaluate: {err}"),
    "hc.recheck": ("Перевіряємо знову…", "Проверяем снова…", "Checking again…"),
    "hc.log.system": ("Читаємо налаштування Windows (оновлення, захист, служби)…",
                      "Читаем настройки Windows (обновления, защита, службы)…",
                      "Reading Windows settings (updates, protection, services)…"),
    "hc.log.time": ("Звіряємо годинник із time.windows.com…", "Сверяем часы с time.windows.com…",
                    "Comparing the clock with time.windows.com…"),
    "hc.log.devices": ("Шукаємо пристрої з помилкою…", "Ищем устройства с ошибкой…", "Looking for devices with errors…"),
    "hc.log.stability": ("Читаємо журнал збоїв за 30 днів…", "Читаем журнал сбоев за 30 дней…",
                         "Reading the crash log for the last 30 days…"),
    "hc.st.ok": ("Гаразд", "В порядке", "OK"),
    "hc.st.info": ("До відома", "К сведению", "Info"),
    "hc.st.warn": ("Увага", "Внимание", "Warning"),
    "hc.st.bad": ("Проблема", "Проблема", "Problem"),
    "hc.st.unknown": ("Не вдалося перевірити", "Не удалось проверить", "Could not check"),

    # ── план «Виправити все безпечне» і окреме виправлення ──
    "hc.plan.title": ("Виправити все безпечне", "Исправить всё безопасное", "Fix all safe issues"),
    "hc.plan.text": ("Ці дії нічого не вимикають і не ламають. Зніміть позначку з того, що не потрібно. Після них "
                     "OptimaX перевірить усе знову й покаже, що спрацювало.",
                     "Эти действия ничего не отключают и не ломают. Снимите отметку с того, что не нужно. После них "
                     "OptimaX проверит всё снова и покажет, что сработало.",
                     "These steps turn nothing off and break nothing. Untick anything you don't want. Afterwards "
                     "OptimaX checks again and shows what worked."),
    "hc.plan.run": ("Виправити", "Исправить", "Fix"),
    "hc.plan.none": ("Безпечних виправлень зараз немає.", "Безопасных исправлений сейчас нет.",
                     "There are no safe fixes right now."),
    "hc.ask.cmd": ("Команда: {cmd}", "Команда: {cmd}", "Command: {cmd}"),
    "hc.ask.undo": ("Зміна потрапить у журнал: повернути її можна на сторінці «Резервні копії».",
                    "Изменение попадёт в журнал: вернуть его можно на странице «Резервные копии».",
                    "The change goes to the journal: you can undo it on the Backup page."),
    "hc.ask.act": ("Налаштування не змінюються — відкочувати нічого.", "Настройки не меняются — откатывать нечего.",
                   "No settings change, so there's nothing to undo."),
    "hc.ask.reboot": ("Діє після перезавантаження.", "Действует после перезагрузки.", "Takes effect after a restart."),
    "hc.res.title": ("Результат виправлень", "Результат исправлений", "Fix results"),
    "hc.res.reboot": ("Частина змін запрацює після перезавантаження — тоді перевірте ще раз.",
                      "Часть изменений заработает после перезагрузки — тогда проверьте ещё раз.",
                      "Some changes work after a restart — check again then."),
    "hc.out.fixed": ("Виправлено ✅", "Исправлено ✅", "Fixed ✅"),
    "hc.out.still": ("Досі проблема ⚠️", "Всё ещё проблема ⚠️", "Still a problem ⚠️"),
    "hc.out.failed": ("Не вдалося ❌", "Не удалось ❌", "Failed ❌"),
    "hc.out.reboot": ("Після перезавантаження 🔄", "После перезагрузки 🔄", "After a restart 🔄"),
    "hc.out.done": ("Виконано", "Выполнено", "Done"),

    # ── кнопки «відкрити» (нічого не змінюють) ──
    "hc.o.wu": ("Windows Update", "Windows Update", "Windows Update"),
    "hc.o.sec": ("Безпека Windows", "Безопасность Windows", "Windows Security"),
    "hc.o.threat": ("Загрози", "Угрозы", "Threats"),
    "hc.o.fw": ("Брандмауер", "Брандмауэр", "Firewall"),
    "hc.o.devmgr": ("Диспетчер пристроїв", "Диспетчер устройств", "Device Manager"),
    "hc.o.time": ("Дата й час", "Дата и время", "Date & time"),
    "hc.o.sound": ("Параметри звуку", "Параметры звука", "Sound settings"),
    "hc.o.def_limit": ("Обмежити Defender до 20% процесора", "Ограничить Defender до 20% процессора",
                       "Limit Defender to 20% CPU"),
    "hc.def.limit_hint": ("Defender гальмує ігри? Не вимикайте його, а обмежте: сканування займатиме до 20% "
                          "процесора й запускатиметься, лише коли ПК простоює.",
                          "Defender тормозит игры? Не отключайте его, а ограничьте: сканирование будет занимать до "
                          "20% процессора и запускаться, только когда ПК простаивает.",
                          "Defender slowing your games? Don't turn it off — limit it: scans use up to 20% CPU and "
                          "only run while the PC is idle."),
    "hc.o.cleanup": ("Очищення", "Очистка", "Cleanup"),
    "hc.o.backup": ("Резервні копії", "Резервные копии", "Backup"),
    "hc.o.storage": ("Накопичувачі", "Накопители", "Storage"),
    "hc.o.crash": ("Чому впав комп?", "Почему упал компьютер?", "Why did the PC crash?"),

    # ── назви перевірок ──
    "hc.c.disk": ("Диски", "Диски", "Drives"),
    "hc.c.stability": ("Стабільність", "Стабильность", "Stability"),
    "hc.c.devices": ("Пристрої", "Устройства", "Devices"),
    "hc.c.wu": ("Windows Update", "Windows Update", "Windows Update"),
    "hc.c.defender": ("Антивірус", "Антивирус", "Antivirus"),
    "hc.c.firewall": ("Брандмауер", "Брандмауэр", "Firewall"),
    "hc.c.uac": ("Контроль облікових записів (UAC)", "Контроль учётных записей (UAC)", "User Account Control (UAC)"),
    "hc.c.smb1": ("SMBv1", "SMBv1", "SMBv1"),
    "hc.c.rdp": ("Віддалений робочий стіл", "Удалённый рабочий стол", "Remote Desktop"),
    "hc.c.autologon": ("Автовхід", "Автовход", "Automatic sign-in"),
    "hc.c.time": ("Час", "Время", "Time"),
    "hc.c.audio": ("Звук", "Звук", "Sound"),
    "hc.c.uptime": ("Без перезавантаження", "Без перезагрузки", "Uptime"),
    "hc.c.autorun": ("Автозапуск з USB і дисків", "Автозапуск с USB и дисков", "AutoPlay for USB and discs"),

    # ── чому це важливо / що робити ──
    "hc.why.disk": ("Коли вільного місця менше 10 ГБ, Windows не встановлює оновлення, ігри не оновлюються, а система "
                    "гальмує. Зношений чи гарячий диск — ризик втратити файли.",
                    "Когда свободного места меньше 10 ГБ, Windows не устанавливает обновления, игры не обновляются, а "
                    "система тормозит. Изношенный или горячий диск — риск потерять файлы.",
                    "With less than 10 GB free, Windows can't install updates, games can't update and the system "
                    "slows down. A worn or hot drive risks losing files."),
    "hc.todo.disk": ("Звільніть місце («Очищення») або перенесіть ігри на інший диск. Якщо стан диска не «Справний» — "
                     "збережіть важливі файли й відкрийте «Накопичувачі» в Hardware Center.",
                     "Освободите место («Очистка») или перенесите игры на другой диск. Если состояние диска не "
                     "«Исправен» — сохраните важные файлы и откройте «Накопители» в Hardware Center.",
                     "Free up space (Cleanup) or move games to another drive. If the drive isn't Healthy, back up "
                     "important files and open Storage in Hardware Center."),
    "hc.why.stability": ("Сині екрани й раптові вимкнення — ознака проблем із драйвером, пам'яттю, живленням чи "
                         "перегрівом. Кожне таке вимкнення може пошкодити файли.",
                         "Синие экраны и внезапные выключения — признак проблем с драйвером, памятью, питанием или "
                         "перегревом. Каждое такое выключение может повредить файлы.",
                         "Blue screens and sudden shutdowns point to driver, memory, power or overheating problems. "
                         "Each one can damage files."),
    "hc.todo.stability": ("Відкрийте «Чому впав комп?» нижче: там код збою, що було запущено, і що робити.",
                          "Откройте «Почему упал компьютер?» ниже: там код сбоя, что было запущено и что делать.",
                          "Open “Why did the PC crash?” below: it shows the crash code, what was running and what to "
                          "do."),
    "hc.why.devices": ("Пристрій із помилкою не працює взагалі або працює без драйвера: може не бути звуку, Wi-Fi, USB "
                       "чи повної швидкості відеокарти.",
                       "Устройство с ошибкой не работает вовсе или работает без драйвера: может не быть звука, Wi-Fi, "
                       "USB или полной скорости видеокарты.",
                       "A device with an error doesn't work at all or runs without a driver: you may lose sound, "
                       "Wi-Fi, USB or full graphics speed."),
    "hc.todo.devices": ("Спробуйте «Пошук нового обладнання». Не допомогло — встановіть драйвер із сайту виробника "
                        "ноутбука чи материнської плати.",
                        "Попробуйте «Поиск нового оборудования». Не помогло — установите драйвер с сайта "
                        "производителя ноутбука или материнской платы.",
                        "Try “Scan for hardware changes”. If that doesn't help, install the driver from the laptop or "
                        "motherboard maker's website."),
    "hc.why.wu": ("Оновлення Windows закривають діри, через які віруси заходять без вашої участі. Пропущені оновлення "
                  "також ламають античити й нові ігри.",
                  "Обновления Windows закрывают дыры, через которые вирусы проникают без вашего участия. Пропущенные "
                  "обновления также ломают античиты и новые игры.",
                  "Windows updates close holes that malware uses to get in without you doing anything. Missed "
                  "updates also break anti-cheats and new games."),
    "hc.todo.wu": ("Відкрийте Windows Update і встановіть оновлення. Якщо те саме оновлення раз у раз не "
                   "встановлюється — скиньте компоненти оновлення.",
                   "Откройте Windows Update и установите обновления. Если одно и то же обновление раз за разом не "
                   "устанавливается — сбросьте компоненты обновления.",
                   "Open Windows Update and install updates. If the same update keeps failing, reset the update "
                   "components."),
    "hc.why.defender": ("Без захисту в реальному часі й свіжих сигнатур антивірус не помітить нових загроз.",
                        "Без защиты в реальном времени и свежих сигнатур антивирус не заметит новых угроз.",
                        "Without real-time protection and fresh signatures, the antivirus misses new threats."),
    "hc.todo.defender": ("Увімкніть захист і оновіть сигнатури — це безпечно й займає хвилину.",
                         "Включите защиту и обновите сигнатуры — это безопасно и занимает минуту.",
                         "Turn protection on and update signatures — it's safe and takes a minute."),
    "hc.why.firewall": ("Брандмауер не пускає в комп'ютер з'єднання, яких ви не просили. Без нього в публічній мережі "
                        "(кафе, гуртожиток) ваш ПК видно всім.",
                        "Брандмауэр не пускает в компьютер соединения, которых вы не просили. Без него в публичной "
                        "сети (кафе, общежитие) ваш ПК виден всем.",
                        "The firewall blocks connections you didn't ask for. Without it, on a public network (café, "
                        "dorm) everyone can see your PC."),
    "hc.todo.firewall": ("Увімкніть брандмауер. Гра чи програма сама попросить дозволу, якщо їй потрібні вхідні "
                         "з'єднання.",
                         "Включите брандмауэр. Игра или программа сама попросит разрешения, если ей нужны входящие "
                         "соединения.",
                         "Turn the firewall on. A game or app will ask for permission itself if it needs incoming "
                         "connections."),
    "hc.why.uac": ("UAC питає, перш ніж програма отримає права адміністратора. Без нього будь-яка програма тихо змінює "
                   "систему.",
                   "UAC спрашивает, прежде чем программа получит права администратора. Без него любая программа тихо "
                   "меняет систему.",
                   "UAC asks before an app gets administrator rights. Without it, any app can quietly change the "
                   "system."),
    "hc.todo.uac": ("Увімкніть UAC. Запит з'являтиметься лише для програм, яким справді потрібні права.",
                    "Включите UAC. Запрос будет появляться только для программ, которым действительно нужны права.",
                    "Turn UAC on. The prompt only appears for apps that really need the rights."),
    "hc.why.smb1": ("SMBv1 — мережевий протокол 1990-х без захисту від сучасних атак. Через нього поширилися WannaCry "
                    "і NotPetya.",
                    "SMBv1 — сетевой протокол 1990-х без защиты от современных атак. Через него распространились "
                    "WannaCry и NotPetya.",
                    "SMBv1 is a 1990s network protocol with no protection against modern attacks. WannaCry and "
                    "NotPetya spread through it."),
    "hc.todo.smb1": ("Вимкніть, якщо у вас немає дуже старого NAS чи принтера, який уміє лише SMBv1.",
                     "Отключите, если у вас нет очень старого NAS или принтера, который умеет только SMBv1.",
                     "Turn it off unless you have a very old NAS or printer that only speaks SMBv1."),
    "hc.why.rdp": ("Віддалений робочий стіл без NLA показує екран входу будь-кому в мережі — улюблена ціль для підбору "
                   "паролів.",
                   "Удалённый рабочий стол без NLA показывает экран входа любому в сети — любимая цель для подбора "
                   "паролей.",
                   "Remote Desktop without NLA shows the sign-in screen to anyone on the network — a favourite target "
                   "for password guessing."),
    "hc.todo.rdp": ("Увімкніть NLA або вимкніть віддалений робочий стіл у Параметрах, якщо він не потрібен.",
                    "Включите NLA или отключите удалённый рабочий стол в Параметрах, если он не нужен.",
                    "Turn NLA on, or switch Remote Desktop off in Settings if you don't use it."),
    "hc.why.autologon": ("Пароль для автовходу лежить у реєстрі відкритим текстом — його прочитає будь-яка програма з "
                         "правами адміністратора.",
                         "Пароль для автовхода лежит в реестре открытым текстом — его прочитает любая программа с "
                         "правами администратора.",
                         "The automatic sign-in password sits in the registry in plain text — any app with "
                         "administrator rights can read it."),
    "hc.todo.autologon": ("Вимкніть автовхід, якщо ПК не кіоск і не медіацентр. Швидкий вхід дає Windows Hello (PIN).",
                          "Отключите автовход, если ПК не киоск и не медиацентр. Быстрый вход даёт Windows Hello "
                          "(PIN).",
                          "Turn automatic sign-in off unless the PC is a kiosk or media centre. Windows Hello (PIN) "
                          "gives you a quick sign-in."),
    "hc.why.time": ("Якщо годинник відстає чи поспішає, сайти пишуть про небезпечне з'єднання, а лаунчери ігор і "
                    "двофакторні коди не працюють.",
                    "Если часы отстают или спешат, сайты пишут о небезопасном соединении, а лаунчеры игр и "
                    "двухфакторные коды не работают.",
                    "If the clock is off, websites show security warnings, and game launchers and two-factor codes "
                    "stop working."),
    "hc.todo.time": ("Синхронізуйте час. Якщо годинник збивається після кожного вимкнення — сідає батарейка CMOS на "
                     "материнській платі.",
                     "Синхронизируйте время. Если часы сбиваются после каждого выключения — садится батарейка CMOS на "
                     "материнской плате.",
                     "Sync the time. If the clock is wrong after every shutdown, the motherboard's CMOS battery is "
                     "running out."),
    "hc.why.audio": ("Коли служби звуку зупинені, звуку немає ніде, навіть якщо драйвер у порядку.",
                     "Когда службы звука остановлены, звука нет нигде, даже если драйвер в порядке.",
                     "When the audio services are stopped there's no sound anywhere, even with a working driver."),
    "hc.todo.audio": ("Перезапустіть звук. Немає пристроїв відтворення — перевірте кабель і драйвер звукової карти.",
                      "Перезапустите звук. Нет устройств воспроизведения — проверьте кабель и драйвер звуковой карты.",
                      "Restart sound. No playback devices — check the cable and the sound card driver."),
    "hc.why.uptime": ("За тижні без перезавантаження накопичуються витоки пам'яті драйверів, а частина оновлень чекає "
                      "перезапуску.",
                      "За недели без перезагрузки накапливаются утечки памяти драйверов, а часть обновлений ждёт "
                      "перезапуска.",
                      "After weeks without a restart, driver memory leaks pile up and some updates wait for a "
                      "restart."),
    "hc.todo.uptime": ("Перезавантажте ПК. З «Швидким запуском» «Завершення роботи» не перезапускає систему повністю — "
                       "потрібне саме «Перезавантаження».",
                       "Перезагрузите ПК. С «Быстрым запуском» «Завершение работы» не перезапускает систему "
                       "полностью — нужна именно «Перезагрузка».",
                       "Restart the PC. With Fast Startup, Shut down doesn't fully restart the system — use "
                       "Restart."),
    "hc.why.autorun": ("Флешки й диски самі пропонують, що відкрити. Сучасна Windows уже не запускає autorun.inf із "
                       "флешок, тож це радше зручність, ніж діра.",
                       "Флешки и диски сами предлагают, что открыть. Современная Windows уже не запускает "
                       "autorun.inf с флешек, так что это скорее удобство, чем дыра.",
                       "USB sticks and discs offer what to open by themselves. Modern Windows no longer runs "
                       "autorun.inf from USB sticks, so this is more convenience than a hole."),
    "hc.todo.autorun": ("Вимкніть, якщо до ПК підключають чужі флешки.",
                        "Отключите, если к ПК подключают чужие флешки.",
                        "Turn it off if other people plug their USB sticks into this PC."),

    # ── диски ──
    "hc.disk.na": ("Диски не знайдено", "Диски не найдены", "No drives found"),
    "hc.disk.ok": ("Дисків: {n} — стан і вільне місце в нормі", "Дисков: {n} — состояние и свободное место в норме",
                   "{n} drive(s) — health and free space are fine"),
    "hc.disk.warn": ("Диски потребують уваги", "Диски требуют внимания", "Drives need attention"),
    "hc.disk.bad": ("Проблема з диском", "Проблема с диском", "Drive problem"),
    "hc.disk.health": ("{name}: стан «{health}»", "{name}: состояние «{health}»", "{name}: health “{health}”"),
    "hc.disk.wear": ("{name}: використано {n}% ресурсу записів", "{name}: использовано {n}% ресурса записи",
                     "{name}: {n}% of its write endurance used"),
    "hc.disk.worn": ("{name}: лишилося {n}% ресурсу записів — скопіюйте важливе й плануйте заміну диска",
                     "{name}: осталось {n}% ресурса записи — скопируйте важное и планируйте замену диска",
                     "{name}: {n}% of its write endurance left — back up what matters and plan to replace the drive"),
    "hc.disk.smart": ("{name}: атрибут SMART {ids} на порозі відмови — скопіюйте важливе",
                      "{name}: атрибут SMART {ids} на пороге отказа — скопируйте важное",
                      "{name}: SMART attribute {ids} is at its failure threshold — back up what matters"),
    "hc.disk.temp": ("{name}: {t} °C — гарячий", "{name}: {t} °C — горячий", "{name}: {t} °C — hot"),
    "hc.disk.free_ok": ("{l}: вільно {free} з {total} ГБ", "{l}: свободно {free} из {total} ГБ",
                        "{l}: {free} of {total} GB free"),
    "hc.disk.free_low": ("{l}: вільно лише {free} з {total} ГБ", "{l}: свободно всего {free} из {total} ГБ",
                         "{l}: only {free} of {total} GB free"),

    # ── стабільність ──
    "hc.stab.na": ("Журнал збоїв не прочитався", "Журнал сбоев не прочитался", "Could not read the crash log"),
    "hc.stab.ok": ("За {days} днів без синіх екранів і апаратних помилок", "За {days} дней без синих экранов и "
                   "аппаратных ошибок", "No blue screens or hardware errors in {days} days"),
    "hc.stab.warn": ("Були збої за {days} днів", "Были сбои за {days} дней", "Some crashes in {days} days"),
    "hc.stab.bad": ("Комп нестабільний", "Компьютер нестабилен", "The PC is unstable"),
    "hc.stab.bsod": ("Синіх екранів за {days} днів: {n}, останній {last}", "Синих экранов за {days} дней: {n}, "
                     "последний {last}", "Blue screens in {days} days: {n}, last on {last}"),
    "hc.stab.power": ("Раптових вимкнень без синього екрана за {days} днів: {n}",
                      "Внезапных выключений без синего экрана за {days} дней: {n}",
                      "Sudden shutdowns without a blue screen in {days} days: {n}"),
    "hc.stab.whea": ("Апаратних помилок WHEA: {n}", "Аппаратных ошибок WHEA: {n}", "WHEA hardware errors: {n}"),
    "hc.stab.tdr": ("Відеодрайвер перезапускався: {n} разів", "Видеодрайвер перезапускался: {n} раз",
                    "The graphics driver restarted {n} times"),
    "hc.stab.mem": ("Перевірка пам'яті Windows знайшла помилки", "Проверка памяти Windows нашла ошибки",
                    "Windows Memory Diagnostic found errors"),

    # ── пристрої ──
    "hc.dev.na": ("Не вдалося прочитати список пристроїв", "Не удалось прочитать список устройств",
                  "Could not read the device list"),
    "hc.dev.ok": ("Усі пристрої працюють", "Все устройства работают", "All devices work"),
    "hc.dev.bad": ("Пристроїв із помилкою: {n}", "Устройств с ошибкой: {n}", "Devices with an error: {n}"),
    "hc.dev.item": ("{name} — код {code}: {why}", "{name} — код {code}: {why}", "{name} — code {code}: {why}"),
    "hc.dev.disabled": ("Вимкнено вручну: {n} (це не помилка)", "Отключено вручную: {n} (это не ошибка)",
                        "Turned off by hand: {n} (not an error)"),
    "hc.dev.cx": ("помилка драйвера", "ошибка драйвера", "driver error"),
    "hc.dev.c1": ("пристрій не налаштовано", "устройство не настроено", "the device isn't configured"),
    "hc.dev.c3": ("драйвер пошкоджено або бракує пам'яті", "драйвер повреждён или не хватает памяти",
                  "the driver is damaged or memory is short"),
    "hc.dev.c10": ("пристрій не запускається", "устройство не запускается", "the device can't start"),
    "hc.dev.c12": ("бракує ресурсів (конфлікт)", "не хватает ресурсов (конфликт)", "not enough resources (conflict)"),
    "hc.dev.c14": ("потрібне перезавантаження", "нужна перезагрузка", "a restart is needed"),
    "hc.dev.c18": ("драйвер треба перевстановити", "драйвер нужно переустановить", "the driver must be reinstalled"),
    "hc.dev.c19": ("пошкоджено запис у реєстрі", "повреждена запись в реестре", "a registry entry is damaged"),
    "hc.dev.c21": ("Windows видаляє пристрій", "Windows удаляет устройство", "Windows is removing the device"),
    "hc.dev.c24": ("пристрій не знайдено або він не працює", "устройство не найдено или не работает",
                   "the device is missing or not working"),
    "hc.dev.c28": ("драйвер не встановлено", "драйвер не установлен", "no driver installed"),
    "hc.dev.c31": ("драйвер не завантажився", "драйвер не загрузился", "the driver didn't load"),
    "hc.dev.c32": ("служба драйвера вимкнена", "служба драйвера отключена", "the driver's service is disabled"),
    "hc.dev.c37": ("драйвер повернув помилку", "драйвер вернул ошибку", "the driver returned an error"),
    "hc.dev.c39": ("драйвер пошкоджений або відсутній", "драйвер повреждён или отсутствует",
                   "the driver is damaged or missing"),
    "hc.dev.c40": ("пошкоджено запис служби драйвера", "повреждена запись службы драйвера",
                   "the driver's service entry is damaged"),
    "hc.dev.c41": ("обладнання не знайдено", "оборудование не найдено", "the hardware isn't found"),
    "hc.dev.c43": ("Windows зупинила пристрій через помилку", "Windows остановила устройство из-за ошибки",
                   "Windows stopped the device after it reported a problem"),
    "hc.dev.c48": ("драйвер заблоковано як несумісний", "драйвер заблокирован как несовместимый",
                   "the driver is blocked as incompatible"),
    "hc.dev.c52": ("драйвер без цифрового підпису", "драйвер без цифровой подписи", "the driver isn't signed"),

    # ── Windows Update ──
    "hc.wu.na": ("Історія оновлень не прочиталася", "История обновлений не прочиталась",
                 "Could not read the update history"),
    "hc.wu.ok": ("Оновлення встановлюються вчасно", "Обновления устанавливаются вовремя", "Updates are up to date"),
    "hc.wu.info": ("Оновлення призупинено", "Обновления приостановлены", "Updates are paused"),
    "hc.wu.warn": ("Оновлення потребують уваги", "Обновления требуют внимания", "Updates need attention"),
    "hc.wu.bad": ("Windows давно не оновлювалася", "Windows давно не обновлялась", "Windows hasn't updated in a "
                  "long time"),
    "hc.wu.last": ("Останнє оновлення встановлено {date} ({n} дн. тому)", "Последнее обновление установлено {date} "
                   "({n} дн. назад)", "Last update installed on {date} ({n} days ago)"),
    "hc.wu.failed": ("Не встановилося за 30 днів: {n}, код {code} — {title}",
                     "Не установилось за 30 дней: {n}, код {code} — {title}",
                     "Failed in the last 30 days: {n}, code {code} — {title}"),
    "hc.wu.reboot": ("Оновлення чекають перезавантаження", "Обновления ждут перезагрузки",
                     "Updates are waiting for a restart"),
    "hc.wu.svc_off": ("Служба Windows Update вимкнена", "Служба Windows Update отключена",
                      "The Windows Update service is disabled"),
    "hc.wu.paused": ("Призупинено до {date}", "Приостановлено до {date}", "Paused until {date}"),
    "hc.wu.paused_by_us": ("Призупинила OptimaX (зміна «Призупинити оновлення») — повернути можна в «Резервних копіях».",
                           "Приостановил OptimaX (изменение «Приостановить обновления») — вернуть можно в "
                           "«Резервных копиях».",
                           "OptimaX paused them (the “Pause updates” change) — you can undo it on the Backup page."),

    # ── антивірус ──
    "hc.def.na": ("Стан антивіруса не прочитався", "Состояние антивируса не прочиталось",
                  "Could not read the antivirus state"),
    "hc.def.ok": ("Defender увімкнений, сигнатури свіжі", "Defender включён, сигнатуры свежие",
                  "Defender is on, signatures are fresh"),
    "hc.def.ok_sc": ("Антивірус увімкнений (за Центром безпеки)", "Антивирус включён (по Центру безопасности)",
                     "Antivirus is on (per Security Center)"),
    "hc.def.other": ("Захищає {name}", "Защищает {name}", "Protected by {name}"),
    "hc.def.warn": ("Defender потребує уваги", "Defender требует внимания", "Defender needs attention"),
    "hc.def.bad": ("Захист від вірусів не працює як слід", "Защита от вирусов работает не так, как нужно",
                   "Virus protection isn't working properly"),
    "hc.def.off": ("Defender вимкнено політикою", "Defender отключён политикой", "Defender is turned off by policy"),
    "hc.def.policy": ("Захист вимкнено груповою політикою — звичайним перемикачем його не ввімкнути.",
                      "Защита отключена групповой политикой — обычным переключателем её не включить.",
                      "Protection is turned off by group policy — the normal switch can't turn it on."),
    "hc.def.policy_ours": ("Це зробила давня зміна OptimaX «Вимкнути Defender» — відкотіть її в «Резервних копіях».",
                           "Это сделало давнее изменение OptimaX «Отключить Defender» — откатите его в «Резервных "
                           "копиях».",
                           "An old OptimaX change, “Turn off Defender”, did this — undo it on the Backup page."),
    "hc.def.rtp_off": ("Захист у реальному часі вимкнено", "Защита в реальном времени отключена",
                       "Real-time protection is off"),
    "hc.def.sig_old": ("Сигнатури не оновлювалися {n} дн.", "Сигнатуры не обновлялись {n} дн.",
                       "Signatures not updated for {n} days"),
    "hc.def.sig_ok": ("Сигнатури оновлено {n} дн. тому", "Сигнатуры обновлены {n} дн. назад",
                      "Signatures updated {n} days ago"),
    "hc.def.scan_never": ("Швидкого сканування не було жодного разу", "Быстрого сканирования не было ни разу",
                          "No quick scan has ever run"),
    "hc.def.scan_old": ("Останнє швидке сканування — {n} дн. тому", "Последнее быстрое сканирование — {n} дн. назад",
                        "Last quick scan {n} days ago"),
    "hc.def.threats": ("Активних загроз: {n}", "Активных угроз: {n}", "Active threats: {n}"),

    # ── брандмауер ──
    "hc.fw.na": ("Стан брандмауера не прочитався", "Состояние брандмауэра не прочиталось",
                 "Could not read the firewall state"),
    "hc.fw.ok": ("Брандмауер Windows увімкнений у всіх мережах", "Брандмауэр Windows включён во всех сетях",
                 "Windows Firewall is on for all networks"),
    "hc.fw.other": ("Захищає {name}", "Защищает {name}", "Protected by {name}"),
    "hc.fw.off": ("Брандмауер вимкнений: {names}", "Брандмауэр отключён: {names}", "Firewall is off: {names}"),
    "hc.fw.p.domain": ("мережа домену", "сеть домена", "domain network"),
    "hc.fw.p.private": ("приватна мережа", "частная сеть", "private network"),
    "hc.fw.p.public": ("публічна мережа", "общественная сеть", "public network"),
    "hc.fw.policy": ("Керується груповою політикою — змінити можна лише в ній.",
                     "Управляется групповой политикой — изменить можно только в ней.",
                     "Set by group policy — it can only be changed there."),

    # ── UAC, SMBv1, RDP, автовхід, автозапуск ──
    "hc.uac.na": ("Стан UAC не прочитався", "Состояние UAC не прочиталось", "Could not read the UAC state"),
    "hc.uac.ok": ("UAC увімкнений", "UAC включён", "UAC is on"),
    "hc.uac.off": ("UAC вимкнений", "UAC отключён", "UAC is off"),
    "hc.uac.silent": ("UAC не питає адміністраторів — програми отримують права мовчки",
                      "UAC не спрашивает администраторов — программы получают права молча",
                      "UAC never asks administrators — apps get rights silently"),
    "hc.smb1.na": ("Стан SMBv1 не прочитався", "Состояние SMBv1 не прочиталось", "Could not read the SMBv1 state"),
    "hc.smb1.ok": ("SMBv1 вимкнено", "SMBv1 отключён", "SMBv1 is off"),
    "hc.smb1.on": ("Застарілий протокол SMBv1 увімкнено", "Устаревший протокол SMBv1 включён",
                   "The outdated SMBv1 protocol is on"),
    "hc.rdp.na": ("Стан віддаленого робочого столу не прочитався", "Состояние удалённого рабочего стола не "
                  "прочиталось", "Could not read the Remote Desktop state"),
    "hc.rdp.off": ("Віддалений робочий стіл вимкнено", "Удалённый рабочий стол отключён", "Remote Desktop is off"),
    "hc.rdp.on": ("Віддалений робочий стіл увімкнено (з NLA)", "Удалённый рабочий стол включён (с NLA)",
                  "Remote Desktop is on (with NLA)"),
    "hc.rdp.no_nla": ("Віддалений робочий стіл увімкнено без NLA", "Удалённый рабочий стол включён без NLA",
                      "Remote Desktop is on without NLA"),
    "hc.rdp.policy": ("NLA задає групова політика — змінити можна лише в ній.",
                      "NLA задаёт групповая политика — изменить можно только в ней.",
                      "NLA is set by group policy — it can only be changed there."),
    "hc.al.na": ("Налаштування входу не прочиталися", "Настройки входа не прочитались",
                 "Could not read the sign-in settings"),
    "hc.al.ok": ("Автовхід вимкнено", "Автовход отключён", "Automatic sign-in is off"),
    "hc.al.on": ("Увімкнено автовхід (пароля в реєстрі немає)", "Включён автовход (пароля в реестре нет)",
                 "Automatic sign-in is on (no password in the registry)"),
    "hc.al.pwd": ("Автовхід із паролем, збереженим у реєстрі", "Автовход с паролем, сохранённым в реестре",
                  "Automatic sign-in with a password stored in the registry"),
    "hc.ar.na": ("Налаштування автозапуску не прочиталися", "Настройки автозапуска не прочитались",
                 "Could not read the AutoPlay settings"),
    "hc.ar.ok": ("Автозапуск з USB і дисків вимкнено", "Автозапуск с USB и дисков отключён",
                 "AutoPlay for USB and discs is off"),
    "hc.ar.on": ("Флешки й диски пропонують, що відкрити", "Флешки и диски предлагают, что открыть",
                 "USB sticks and discs offer what to open"),

    # ── час ──
    "hc.time.ok": ("Годинник точний", "Часы точные", "The clock is accurate"),
    "hc.time.na": ("Не вдалося звірити годинник", "Не удалось сверить часы", "Could not check the clock"),
    "hc.time.warn": ("Годинник потребує уваги", "Часы требуют внимания", "The clock needs attention"),
    "hc.time.bad": ("Годинник дуже неточний", "Часы сильно неточные", "The clock is badly off"),
    "hc.time.offset": ("Розбіжність із time.windows.com: {s} с", "Расхождение с time.windows.com: {s} с",
                       "Difference from time.windows.com: {s} s"),
    "hc.time.no_server": ("time.windows.com не відповів (немає інтернету чи порт 123 закритий)",
                          "time.windows.com не ответил (нет интернета или порт 123 закрыт)",
                          "time.windows.com didn't answer (no internet, or port 123 is blocked)"),
    "hc.time.svc_off": ("Служба часу Windows вимкнена — годинник не синхронізується",
                        "Служба времени Windows отключена — часы не синхронизируются",
                        "The Windows Time service is disabled — the clock never syncs"),

    # ── звук ──
    "hc.au.na": ("Стан звуку не прочитався", "Состояние звука не прочиталось", "Could not read the sound state"),
    "hc.au.ok": ("Служби звуку працюють", "Службы звука работают", "Audio services are running"),
    "hc.au.warn": ("Звук потребує уваги", "Звук требует внимания", "Sound needs attention"),
    "hc.au.bad": ("Служби звуку зупинені", "Службы звука остановлены", "Audio services are stopped"),
    "hc.au.stopped": ("Зупинено: {names}", "Остановлено: {names}", "Stopped: {names}"),
    "hc.au.no_out": ("Немає жодного активного пристрою відтворення", "Нет ни одного активного устройства "
                     "воспроизведения", "No active playback device"),
    "hc.au.devs": ("Пристроїв відтворення: {out}, запису: {inp}", "Устройств воспроизведения: {out}, записи: {inp}",
                   "Playback devices: {out}, recording: {inp}"),

    # ── час роботи ──
    "hc.up.na": ("Час роботи не прочитався", "Время работы не прочиталось", "Could not read the uptime"),
    "hc.up.ok": ("Без перезавантаження: {n} дн.", "Без перезагрузки: {n} дн.", "Running for {n} days"),
    "hc.up.long": ("Без перезавантаження вже {n} дн.", "Без перезагрузки уже {n} дн.", "No restart for {n} days"),
    "hc.up.fast": ("«Швидкий запуск» увімкнено.", "«Быстрый запуск» включён.", "Fast Startup is on."),

    # ── виправлення: назва й що зміниться (з ризиком) ──
    "hc.fix.def_sig": ("Оновити сигнатури Defender", "Обновить сигнатуры Defender", "Update Defender signatures"),
    "hc.fixd.def_sig": ("Завантажує свіжі сигнатури вірусів від Microsoft. Нічого не вимикає, потрібен інтернет.",
                        "Загружает свежие сигнатуры вирусов от Microsoft. Ничего не отключает, нужен интернет.",
                        "Downloads fresh virus signatures from Microsoft. Turns nothing off; needs internet."),
    "hc.fix.def_scan": ("Швидке сканування Defender", "Быстрое сканирование Defender", "Defender quick scan"),
    "hc.fixd.def_scan": ("Перевіряє місця, де найчастіше ховаються загрози. 5–15 хвилин навантажує диск і процесор, "
                         "тож запускайте, коли не граєте.",
                         "Проверяет места, где чаще всего прячутся угрозы. 5–15 минут нагружает диск и процессор, "
                         "поэтому запускайте, когда не играете.",
                         "Checks the places threats hide most often. It loads the drive and CPU for 5–15 minutes, so "
                         "run it when you're not gaming."),
    "hc.fix.def_rtp": ("Увімкнути захист у реальному часі", "Включить защиту в реальном времени",
                       "Turn on real-time protection"),
    "hc.fixd.def_rtp": ("Defender знову перевірятиме файли під час відкриття. Якщо його вимикає «Захист від "
                        "підробки» чи інший антивірус, Windows може не дати змінити — повторна перевірка це покаже.",
                        "Defender снова будет проверять файлы при открытии. Если его отключает «Защита от "
                        "подделки» или другой антивирус, Windows может не дать изменить — повторная проверка это "
                        "покажет.",
                        "Defender checks files as they open again. If Tamper Protection or another antivirus turned "
                        "it off, Windows may refuse — the re-check will show it."),
    "hc.fix.time_sync": ("Синхронізувати час", "Синхронизировать время", "Sync time now"),
    "hc.fixd.time_sync": ("Запускає службу часу Windows і звіряє годинник із сервером Microsoft. Налаштування не "
                          "змінюються.",
                          "Запускает службу времени Windows и сверяет часы с сервером Microsoft. Настройки не "
                          "меняются.",
                          "Starts the Windows Time service and syncs the clock with Microsoft's server. No settings "
                          "change."),
    "hc.fix.dev_scan": ("Пошук нового обладнання", "Поиск нового оборудования", "Scan for hardware changes"),
    "hc.fixd.dev_scan": ("Те саме, що «Оновити конфігурацію обладнання» в Диспетчері пристроїв: Windows ще раз шукає "
                         "драйвери. Нічого не видаляє.",
                         "То же, что «Обновить конфигурацию оборудования» в Диспетчере устройств: Windows ещё раз "
                         "ищет драйверы. Ничего не удаляет.",
                         "Same as “Scan for hardware changes” in Device Manager: Windows looks for drivers again. "
                         "Deletes nothing."),
    "hc.fix.audio_restart": ("Перезапустити звук", "Перезапустить звук", "Restart sound"),
    "hc.fixd.audio_restart": ("Перезапускає служби звуку Windows. Звук зникне на кілька секунд; програми, що грають "
                              "звук, можливо, доведеться перезапустити.",
                              "Перезапускает службы звука Windows. Звук пропадёт на несколько секунд; программы, "
                              "которые играют звук, возможно, придётся перезапустить.",
                              "Restarts the Windows audio services. Sound drops for a few seconds; apps playing sound "
                              "may need a restart."),
    "hc.fix.wu_reset": ("Скинути компоненти Windows Update", "Сбросить компоненты Windows Update",
                        "Reset Windows Update components"),
    "hc.fixd.wu_reset": ("Зупиняє служби оновлення, перейменовує папки SoftwareDistribution і catroot2 (старі копії "
                         "лишаються поруч) і запускає служби знову. Історія оновлень у Параметрах стане порожньою, а "
                         "наступний пошук оновлень триватиме довше. Допомагає, коли оновлення раз у раз не "
                         "встановлюється.",
                         "Останавливает службы обновления, переименовывает папки SoftwareDistribution и catroot2 "
                         "(старые копии остаются рядом) и запускает службы снова. История обновлений в Параметрах "
                         "станет пустой, а следующий поиск обновлений займёт больше времени. Помогает, когда "
                         "обновление раз за разом не устанавливается.",
                         "Stops the update services, renames the SoftwareDistribution and catroot2 folders (the old "
                         "copies stay next to them) and starts the services again. The update history in Settings "
                         "becomes empty and the next update search takes longer. Helps when an update keeps "
                         "failing."),
    "hc.fix.time_svc": ("Увімкнути службу часу Windows", "Включить службу времени Windows",
                        "Turn on the Windows Time service"),
    "hc.fixd.time_svc": ("Служба часу вимкнена — вмикаємо її запуск за потреби й синхронізуємо годинник. Відкат "
                         "поверне службу у вимкнений стан.",
                         "Служба времени отключена — включаем её запуск по требованию и синхронизируем часы. Откат "
                         "вернёт службу в отключённое состояние.",
                         "The time service is disabled — we set it to start on demand and sync the clock. Undo puts "
                         "the service back to disabled."),
    "hc.fix.fw_on": ("Увімкнути брандмауер Windows", "Включить брандмауэр Windows", "Turn on Windows Firewall"),
    "hc.fixd.fw_on": ("Вмикає брандмауер для мереж, де він вимкнений. Може перестати працювати те, що чекає вхідних "
                      "з'єднань: віддалений доступ до цього ПК, спільні папки, мережеві принтери, свої сервери ігор.",
                      "Включает брандмауэр для сетей, где он отключён. Может перестать работать то, что ждёт "
                      "входящих соединений: удалённый доступ к этому ПК, общие папки, сетевые принтеры, свои "
                      "серверы игр.",
                      "Turns the firewall on where it's off. Things waiting for incoming connections may stop "
                      "working: remote access to this PC, shared folders, network printers, your own game servers."),
    "hc.fix.uac_on": ("Увімкнути контроль облікових записів (UAC)", "Включить контроль учётных записей (UAC)",
                      "Turn on User Account Control (UAC)"),
    "hc.fixd.uac_on": ("Windows знову питатиме дозволу, перш ніж програма отримає права адміністратора. Старі "
                       "програми, які чекають прав без запиту, можуть питати або не запуститися.",
                       "Windows снова будет спрашивать разрешения, прежде чем программа получит права "
                       "администратора. Старые программы, которые ждут прав без запроса, могут спрашивать или не "
                       "запуститься.",
                       "Windows asks again before an app gets administrator rights. Old apps that expect rights "
                       "without asking may prompt or fail to start."),
    "hc.fix.smb1_off": ("Вимкнути SMBv1", "Отключить SMBv1", "Turn off SMBv1"),
    "hc.fixd.smb1_off": ("Прибирає застарілий протокол SMBv1 (1–3 хвилини). Перестануть відкриватися дуже старі "
                         "мережеві диски (NAS), принтери зі скануванням у папку та спільні папки Windows XP.",
                         "Убирает устаревший протокол SMBv1 (1–3 минуты). Перестанут открываться очень старые "
                         "сетевые диски (NAS), принтеры со сканированием в папку и общие папки Windows XP.",
                         "Removes the outdated SMBv1 protocol (1–3 minutes). Very old network drives (NAS), "
                         "scan-to-folder printers and Windows XP shares will stop opening."),
    "hc.fix.rdp_nla": ("Вимагати NLA для віддаленого робочого столу", "Требовать NLA для удалённого рабочего стола",
                       "Require NLA for Remote Desktop"),
    "hc.fixd.rdp_nla": ("Пароль треба буде ввести ще до появи екрана входу — так закриваються атаки на сам екран "
                        "входу. Дуже старі клієнти RDP не підключаться.",
                        "Пароль нужно будет ввести ещё до появления экрана входа — так закрываются атаки на сам "
                        "экран входа. Очень старые клиенты RDP не подключатся.",
                        "The password is asked before the sign-in screen appears, which closes attacks on the "
                        "sign-in screen itself. Very old RDP clients won't connect."),
    "hc.fix.autologon_off": ("Вимкнути автовхід і видалити збережений пароль",
                             "Отключить автовход и удалить сохранённый пароль",
                             "Turn off automatic sign-in and delete the stored password"),
    "hc.fixd.autologon_off": ("Windows перестане входити без пароля, а пароль із реєстру буде видалено. OptimaX його "
                              "не читає й не зберігає, тож відкат поверне лише налаштування — пароль для автовходу "
                              "доведеться ввести знову (netplwiz).",
                              "Windows перестанет входить без пароля, а пароль из реестра будет удалён. OptimaX его "
                              "не читает и не сохраняет, поэтому откат вернёт только настройку — пароль для автовхода "
                              "придётся ввести снова (netplwiz).",
                              "Windows stops signing in without a password, and the password is deleted from the "
                              "registry. OptimaX never reads or stores it, so undo only restores the setting — you'll "
                              "have to enter the auto sign-in password again (netplwiz)."),
    "hc.fix.autorun_off": ("Вимкнути автозапуск з USB і дисків", "Отключить автозапуск с USB и дисков",
                           "Turn off AutoPlay for USB and discs"),
    "hc.fixd.autorun_off": ("Флешки, диски й телефони більше не відкриватимуть нічого самі й не показуватимуть меню "
                            "«Що зробити?». Відкривайте їх через Провідник.",
                            "Флешки, диски и телефоны больше не будут ничего открывать сами и показывать меню «Что "
                            "сделать?». Открывайте их через Проводник.",
                            "USB sticks, discs and phones no longer open anything themselves or show the “What to "
                            "do?” menu. Open them from File Explorer."),
}
