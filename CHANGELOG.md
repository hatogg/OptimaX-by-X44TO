# Історія змін · Changelog

Формат — за [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/), версії — `VERSION` в `engine.py`.

## [6.13.1] — 2026-11-11

Виправлення 6.13: програма зависала на заставці під час запуску.

### Виправлено

- **Заставка під час запуску більше не зависає.** У 6.13 після заставки головне вікно лишалося повністю прозорим, а сама заставка висіла поверх усього: анімація, що передає місце вікну, жила в тимчасовій змінній і зникала раніше, ніж встигала спрацювати. Запуск у трей (автозапуск) це не зачіпало. Тепер анімація тримається до кінця, а якщо комп'ютер у цю мить зайнятий — вікно все одно з'являється за півтори секунди.
- Якщо головне вікно не вдалося створити, заставка закривається, а не лишається на екрані.
- Новий тест перевіряє саме цей шлях запуску — із заставкою, зокрема на зайнятому комп'ютері. Раніше самоперевірка створювала вікно без заставки, тож помилку не ловила.

**Якщо у вас 6.13 і вона «висить» на заставці:** закрийте OptimaX через «Диспетчер завдань» і встановіть 6.13.1 з цієї сторінки поверх. Налаштування й журнал змін залишаться.

<details>
<summary>English</summary>

**Fixed:** the program hung on the startup splash screen in 6.13 — the main window stayed fully transparent under the splash, because the hand-over animation lived in a temporary variable and was destroyed before it could run (starting to the tray was not affected). The animation is now kept alive, the window appears within a second and a half even if the PC is busy at that moment, and a failure to create the main window closes the splash instead of leaving it on screen. A new test covers this exact startup path. If your 6.13 is stuck on the splash: end OptimaX in Task Manager and install 6.13.1 over it — settings and the change journal are kept.

</details>

## [6.13] — 2026-11-11

Новий дизайн: дашборд, бічне меню, що розгортається, плавні анімації, світла й темна тема — і сторінка «Пам'ять». А ще надійніший відкат: крок, який не вдалося повернути, більше не губиться.

### Додано

- **Світла й темна тема — або як у Windows.** «Налаштування → Вигляд» з мініатюрами тем і кнопка внизу меню. Тема перемикається одразу, без перезапуску: нова розходиться колом від кнопки. Заголовок вікна Windows теж світлий або темний. Обидві палітри — в `ui_kit.THEMES`, кожен колір унікальний, тож перемикання перефарбовує навіть уже підставлені в стилі кольори (`remap_hex`).
- **Сторінка «Пам'ять».** Кільце-шкала зайнятої RAM і живий графік останньої хвилини, «Використовується / Доступно / Кеш (standby) / Усього» — так само, як рахує «Диспетчер завдань». Список «Хто займає пам'ять»: програми з усіма процесами разом і станом — активна, у фоні чи спить.
- **«Звільнити пам'ять» — чесно.** Скляне вікно з кроками: стиснути робочі набори лише програм, що сплять у фоні (майже не брали процесор, не активне вікно, не гра з бібліотеки чи Steam/Epic/GOG, не системний процес, не антивірус і не звук), очистити кеш standby, заміряти. Результат «було → стало», а через хвилину — скільки втрималося і скільки Windows забрала назад. Примусово стискати все підряд, як деякі «прискорювачі», OptimaX не стане: велика цифра «звільнено» потім обертається фризами в грі. Новий модуль `memtools.py`.
- **Дашборд замість «Аналізу».** Оцінка продуктивності з 0 до 100 з анімованою шкалою і радаром складових: оптимізація, приватність, перевірка збірки, баланс заліза, пам'ять і диск. «З чого складається?» показує кожну складову та її вагу — оцінка лише з того, що OptimaX справді перевірив. Швидкі дії (звільнити пам'ять, очищення, режим гри, «Чому лагає?») і живі графіки процесора, пам'яті, диска й температури відеокарти.
- **Рух.** Сторінки змінюються плавно (стара тане, нова підіймається), числа набігають, графіки прокручуються, сповіщення виїжджають, діалоги проявляються, вибраний пункт меню переїжджає, а не перестрибує. Заставка під час запуску. «Плавні анімації» і заставку можна вимкнути в «Налаштуваннях → Вигляд».
- Нові модулі `ui_motion.py` (анімації й нові елементи) і `pages_memory.py`.

### Змінено

- **Бічне меню**: згорнуте — лише іконки, при наведенні розгортається поверх сторінки з підписами. Кнопкою «Закріпити меню» (або в налаштуваннях) воно лишається розгорнутим, як раніше. Версія — під назвою програми.
- Нова палітра: глибший синій, м'ятний для «добре», скло й світіння на головних картках.
- **Файл підкачки, заданий вручну, OptimaX більше не змінює.** Раніше «Оптимізувати файл підкачки» міняла розмір і в цьому випадку, а повернути ваші значення було нічим.

### Виправлено

- **Відкат, який не спрацював, більше не вважається виконаним.** Якщо крок відкату — команда, задача планувальника, PowerShell чи параметр живлення — завершився помилкою, зупинкою або тайм-аутом, він лишається в журналі як частковий, і відкат можна повторити. Раніше код повернення перевірявся лише для реєстру та служб: такий пункт зникав із журналу, хоча система не поверталась. Команда, якій уже нічого повертати (значення чи задачі більше немає), як і раніше, не помилка.
- **Приховані параметри живлення тепер мають запис відкату.** `powercfg /query` не показує приховані параметри (наприклад, паркування ядер), тож старе значення не читалося, і зміна лишалася без запису. Тепер значення читається через `powercfg /qh`, запис відкату робиться до зміни, а параметр, старе значення якого прочитати не вдалося, не змінюється.
- **Мережеві адаптери:** попередження PowerShell перед відповіддю більше не лишає зміни без запису відкату.
- Якщо після відкату журнал не вдалося записати на диск, про це сказано в журналі виконання.

### Безпека

- **Режим гри не довіряє своєму стану з файла налаштувань.** Служби та схема живлення, які він повертає після гри, беруться лише зі свого списку й передаються без `cmd.exe`. Раніше рядок із `settings.json`, куди може писати будь-яка програма користувача, потрапляв у команду з правами адміністратора — зокрема автоматично під час запуску.
- **OneDrive після режиму гри запускається зі звичайними правами користувача**, а не з правами адміністратора, з якими працює OptimaX.
- Знімок початкових налаштувань: режим служби приймається лише з відомих значень, команда — без `cmd.exe`.
- Очищення ніколи не видаляє власні дані OptimaX (журнал відкату, Rescue), навіть якщо `%TEMP%` вказує на них.

<details>
<summary>English</summary>

**Fixed:** a rollback step that failed (a command, a scheduled task, PowerShell or a power setting) is no longer counted as done — it stays in the journal as partial and can be retried; before, only registry and service steps were checked, so the entry vanished while the system was not restored. Hidden power settings (such as core parking) now get a rollback record: they are read with `powercfg /qh`, the record is written before the change, and a setting whose old value cannot be read is left alone. A PowerShell warning no longer leaves network adapter changes without a rollback record. A manually sized page file is no longer changed.

**Security:** Game Mode no longer trusts its saved state from the settings file — services and the power plan are taken only from its own list and passed without `cmd.exe` (a line from `settings.json`, writable by any user program, used to reach an administrator command line, even automatically at startup). OneDrive is restarted with normal user rights after Game Mode, not as administrator. The baseline snapshot accepts only known service modes. Cleanup never deletes OptimaX's own data (rollback journal, Rescue).

**Added:** light and dark themes (or follow Windows) in Settings → Appearance and on a button at the bottom of the menu; the theme switches instantly with a circular reveal, including the Windows title bar. New Memory page: a gauge and a live chart of RAM in use, In use / Available / Standby cache / Total as Task Manager counts it, and the apps holding memory with their state (active, background, asleep). Free up memory works honestly: it trims working sets only of apps asleep in the background (never the active window, games, system processes, antivirus or audio), clears the standby cache and measures before → after, then checks a minute later how much stayed free. New module `memtools.py`. The Analysis page became a Dashboard: a 0–100 performance score with an animated scale and a radar of its parts (optimization, privacy, build check, hardware balance, memory, disk), explained by “How is it calculated?”, quick actions and live CPU, memory, disk and GPU temperature charts. Motion everywhere: page transitions, counting numbers, scrolling charts, sliding toasts, fading dialogs, a sliding menu highlight and a splash screen; animations and the splash can be turned off. New modules `ui_motion.py` and `pages_memory.py`.

**Changed:** the side menu shows icons only and slides out on hover over the page; pin it to keep it expanded. New palette: deeper blue, mint for “good”, glass and glow on the main cards.

</details>

## [6.12] — 2026-11-08

«Чому зависає?» — ловець фризів, коли на 1–5 секунд зависає все одразу: картинка, відео й звук ([#10](https://github.com/hatogg/OptimaX-by-X44TO/issues/10)).

### Додано

- **Картка «Чому зависає?» на сторінці «Діагностика».** Перемикач «Ловити фризи у фоні» запускає окремий легкий процес (`OptimaX.exe --freeze-watch`, без Qt), поки OptimaX відкрита або в треї. Потік із пріоритетом TIME_CRITICAL прокидається кожні 50 мс і міряє запізнення за QueryUnbiasedInterruptTime: звичайне навантаження його не затримує, а сон і гібернація не рахуються. Окремий процес — щоб «фризом» не вважався зайнятий інтерфейс самої OptimaX.
- **Чорна скринька й вердикт.** Щосекунди лічильники Windows: DPC і переривання (усього й на найгарячішому ядрі), процесор, черга й зайнятість диска, вільна пам'ять, читання з підкачки, найактивніший процес. Збір, що охоплює фриз, і журнал System за хвилину до й пів хвилини після (WHEA, скидання накопичувача 129 / 153, відеодрайвер 4101 і nvlddmkm, USB, ACPI, TPM, мережеві драйвери) дають причину: апаратна помилка, накопичувач, відеодрайвер, шторм DPC драйвера (мережевого, USB чи іншого), перевантажений диск, брак пам'яті, процесор — або «Windows нічого не робила»: зупинка поза Windows (прошивка чи залізо). Сон і modern standby поруч — не фриз, такі записи відкидаються. Підсумок — найчастіша причина й рід: залізо, драйвер, програма чи прошивка — з порадами.
- **Перевірка AMD fTPM.** Якщо TPM вбудований у процесор AMD (Win32_Tpm: виробник «AMD»), картка попереджає про відомі фризи fTPM із заїканням звуку, показує дату BIOS і пояснює, як безпечно перевірити (з попередженням про BitLocker), а «тихі» фризи на такому ПК позначаються як fTPM.
- **Глибокий запис драйверів (WPR).** За бажанням вбудований у Windows WPR тримає DPC, переривання й завантажені драйвери в кільцевому буфері (64 МБ, профіль `OptimaX.wprp`) і зберігає `.etl` саме в момент фризу — для Windows Performance Analyzer чи звіту. Лишаються три останні записи; ловець сам скасовує запис, коли зупиняється.
- Про новий фриз — банер на головній і сповіщення (з трею теж). Самоперевірка на Windows перевіряє годинник, запит журналу, TPM і що WPR приймає профіль OptimaX. Новий модуль `freezecatch.py`.

<details>
<summary>English</summary>

**Added:** Why does it freeze? on the Diagnostics page — a background freeze catcher for 1–5 second hangs where picture, video and sound stop at once (#10). A separate lightweight process (`OptimaX.exe --freeze-watch`, no Qt) runs a TIME_CRITICAL thread that wakes every 50 ms and measures lateness with QueryUnbiasedInterruptTime, so ordinary load doesn't trip it and sleep doesn't count. A per-second black box of Windows counters (DPCs and interrupts in total and on the hottest core, CPU, disk queue and busy time, free memory, page-file reads, top process) plus the System log around the freeze (WHEA, storage resets 129/153, graphics driver 4101 and nvlddmkm, USB, ACPI, TPM, network drivers) give a cause: hardware error, drive, graphics driver, a driver's DPC storm, overloaded disk, low memory, CPU, or “Windows was doing nothing” — a stall outside Windows (firmware or hardware). Sleep and modern standby are filtered out. A summary names the most common cause and whether it's hardware, a driver, software or firmware, with advice. AMD fTPM is detected (Win32_Tpm) with a warning, the BIOS date and a safe way to test it; quiet freezes on such PCs are marked as fTPM. Optional deep recording keeps DPCs, interrupts and loaded drivers in a 64 MB WPR ring buffer and saves an `.etl` at the moment of the freeze for Windows Performance Analyzer. New freezes show a home banner and a notification. The self-test on Windows checks the clock, the event query, the TPM and that WPR accepts the profile. New module `freezecatch.py`.

</details>

## [6.11] — 2026-11-08

Прибрано зайве — за стратегією «головне нагорі» — і чесний каталог оптимізацій.

### Змінено

- **Сторінка «Залізо» стала розділом Hardware Center «Перевірка збірки».** Характеристики вона дублювала з розділу «Залізо» Hardware Center, а перевірку збірки з кнопками «Виправити», особливості платформи, MSI Mode й розгін відеокарти тепер видно поруч із тестами заліза. Кнопка «Усі перевірки» на головній веде туди. У меню на один пункт менше.
- **Сторінку «Вигляд» прибрано.** Перемикачі Провідника й панелі завдань і так були в експертному меню, а значки, розширення файлів, тема, Alt+Tab, Aero Shake і залипання клавіш тепер там у новій групі «Вигляд» — з переглядом змін перед застосуванням, як усі оптимізації. Редактора кольорів виділення більше немає; застосовані раніше кольори видно й відкочуються в «Резервних копіях».
- **Розгін відеокарти — без DeepSeek.** Замість кнопки, що копіювала характеристики й відкривала сторонній AI-чат, — чотири безпечні кроки з MSI Afterburner і кнопка стрес-тесту OptimaX для перевірки кожного кроку.
- **Каталог чесно поділено на дві частини.** «Швидкість» — те, що видно в замірах (процесор і пам'ять, ігри, залізо й драйвери, мережа, ноутбук, легкість, служби); «Зручність і приватність» — менше реклами, стеження й зайвого (AI і реклама Windows 11, конфіденційність, Провідник, вигляд, оновлення, звук, система, місце на диску, обслуговування, вбудовані додатки). В експертному меню й у [списку оптимізацій](docs/uk/tweaks.md) — окремими частинами з поясненням, що від другої FPS не росте. Обіцянка «доводимо цифрами» тепер стосується саме першої.
- Чипи розділів Hardware Center переносяться за шириною й не обрізають назви («Діагностика Windows», «Перевірка перед покупкою»).

### Сайт

- Розділ «Чого OptimaX не робить»: без телеметрії, нічого без підтвердження, захист Windows лишається, без реклами й нав'язаних програм; як перевірити файл за `SHA256SUMS.txt` і посилання на [політику приватності й підпису коду](docs/uk/code-signing.md).
- Підтримка розробки — банка Монобанку: кнопка Sponsor на GitHub, розділ «Підтримати» в README, посилання й питання в FAQ на сайті. У програмі — лише один раз, у «Що нового» цієї версії.

<details>
<summary>English</summary>

**Changed:** the Hardware page is now the Build check section of Hardware Center (its specs duplicated Hardware info; the build check with Fix buttons, platform notes, MSI Mode and GPU overclocking now sit next to the hardware tests), so the menu is one item shorter. The Appearance page is gone: File Explorer and taskbar switches were already in the Expert menu, and icons, file extensions, theme, Alt+Tab, Aero Shake and Sticky Keys move there as a new Appearance group with a preview before applying; the selection colour editor is removed, and colours applied earlier stay visible and reversible in Backups. GPU overclocking no longer copies a prompt for DeepSeek: four safe steps with MSI Afterburner and a button for the OptimaX stress test instead. The catalog is split honestly into Speed (what shows up in measurements) and Comfort and privacy (fewer ads, less tracking and clutter — no FPS promised), in the Expert menu and in the list of optimizations. Hardware Center section chips wrap instead of cutting their names.

**Site:** a “What OptimaX never does” section (no telemetry, nothing without your OK, Windows protection stays on, no ads or bundled apps) with how to check a file against `SHA256SUMS.txt` and a link to the privacy and code signing policy; a Monobank jar for supporting development — a Sponsor button on GitHub, a Support section in the README, a site link and FAQ entry, and once in this version's What's new.

</details>

## [6.10.1] — 2026-11-08

Виправлення інсталятора, простіше меню й підготовка до підпису коду.

### Виправлено

- **Помилка 740 наприкінці встановлення.** Галочку «Запустити OptimaX» Inno Setup виконував від імені звичайного користувача через `CreateProcess`, а `OptimaX.exe` вимагає прав адміністратора — Windows відповідала «CreateProcess збій; код 740. The requested operation requires elevation». Тепер запуск іде через ShellExecute (`shellexec`): Windows показує запит UAC, і програма відкривається від того самого користувача. Тихе встановлення в CI цей крок пропускає, тож додано окрему перевірку в `test_static.py`.

### Змінено

- **Меню.** «Мережа» й «Блок реклами» перенесено з «Пристрою» в «Інструменти»; «Ноутбук» видно лише на ноутбуці (поки залізо не визначене — пункт лишається); у «Діагностиці» першим іде «Чому лагає?», а «Чому впав комп?» і монітор на телефоні — нижче. Банер про збій ПК і кнопка в Hardware Center прокручують сторінку саме до картки збоїв.

### Додано

- **Підготовка до підпису коду через SignPath** (безкоштовно для відкритого коду): job «Code signing (SignPath)» у `release.yml` підписує `OptimaX.exe` і портативну версію, збирає інсталятор із підписаним exe, підписує його й перераховує `SHA256SUMS.txt` і маніфести winget. Вмикається змінною `SIGNPATH_ORGANIZATION_ID` і секретом `SIGNPATH_API_TOKEN` після схвалення заявки; без них реліз виходить, як і раніше. Політика підпису й приватності — [docs/uk/code-signing.md](docs/uk/code-signing.md), конфігурації артефактів — `.signpath/artifact-configurations`.

<details>
<summary>English</summary>

**Fixed:** the “Launch OptimaX” box at the end of setup failed with “CreateProcess failed; code 740. The requested operation requires elevation” because Inno Setup ran the admin-manifested exe as the original user through `CreateProcess`; it now uses ShellExecute (`shellexec`), so Windows shows a UAC prompt. Silent installs in CI skip this step, so `test_static.py` now checks it.

**Changed:** Network and Ad blocker moved from Device to Tools; Laptop shows on laptops only; Diagnostics opens with Why is it lagging?, with Why did the PC crash? and the phone monitor below; the crash banner and the Hardware Center button scroll straight to the crash card.

**Added:** groundwork for free open-source code signing through SignPath: a “Code signing (SignPath)” job in `release.yml` signs `OptimaX.exe` and the portable version, rebuilds the installer with the signed exe, signs it and recomputes `SHA256SUMS.txt` and the winget manifests. It turns on with the `SIGNPATH_ORGANIZATION_ID` variable and the `SIGNPATH_API_TOKEN` secret once the application is approved; without them releases go out as before. Policy and privacy: [docs/en/code-signing.md](docs/en/code-signing.md).

</details>

## [6.10] — 2026-11-07

Точність Hardware Center: справжня температура процесора, датчики потрібної відеокарти, точніші відомості про пам'ять.

### Виправлено

- **Температура процесора бралася з теплової зони ACPI** і підписувалась як «CPU». На більшості настільних плат це датчик плати або стала — на H67/Z77 часто рівно 27,8 °C, — тож під стрес-тестом процесор «мав» 28 °C, а перевірка збірки писала «температура в простої в нормі». Тепер OptimaX читає справжню температуру з програм датчиків, які вже запущені: Core Temp (спільна пам'ять, увімкнена за замовчуванням), HWiNFO («Shared Memory Support»), AIDA64 і LibreHardwareMonitor (вебсервер). Без них теплова зона показується з підписом «ACPI», а зона, що за весь тест під навантаженням не зрушила й на пів градуса, відкидається з поясненням, що запустити. Так само в «Чому лагає?», стрес-тестах, розділі «Ноутбук», оверлеї (там зону не показуємо зовсім) і звітах. Новий модуль `cpusensors.py`.
- **Датчики NVIDIA бралися з першої карти на шині.** У збірці з GT 710 для картинки й P106 для ігор температура, частоти й споживання в Hardware Center, тесті GPU, оверлеї й аналізаторі майнінгових карт належали GT 710. Тепер — карта, вибрана для тесту, та, на якій справді малює тест чи гра, або майнінгова карта; без назви — карта з найбільшою пам'яттю.
- **Швидкість модулів пам'яті вдвічі менша.** SMBIOS до 3.1 пише «налаштовану швидкість» у МГц, і таблиця модулів показувала DDR3-1333 як 667 МТ/с (загальна швидкість уже це враховувала, таблиця — ні).
- **Тип модуля** визначався за кодами WMI замість кодів SMBIOS: RIMM показувався як SODIMM. **Виробник** — назва замість коду JEDEC зі старих BIOS («80CE000080CE» → Samsung, «0198» → Kingston). Порожні слоти без типу й виробника.
- Відеопам'ять вбудованої графіки — «64 МБ», а не «0.1 GB», у Hardware Center і звітах.
- Висновки зі збережених тестів старших версій показуються з типовими підстановками замість «{src}».

### Сайт і пошук

- Сайт збирається в окрему статичну сторінку для кожної мови з текстом прямо в HTML (`tools/build_site.py`): раніше пошуковий робот бачив порожні заголовки або англійський текст під українською сторінкою. Власні заголовки й описи, canonical, hreflang, Open Graph, schema.org і `sitemap.xml`.

<details>
<summary>English</summary>

**Fixed:** the CPU temperature came from the ACPI thermal zone labelled as “CPU”; on most desktop boards that's a motherboard sensor or a constant (often exactly 27.8 °C on H67/Z77), so a stress-tested CPU “ran” at 28 °C. OptimaX now reads the real temperature from sensor programs that are already running — Core Temp (shared memory, on by default), HWiNFO (“Shared Memory Support”), AIDA64 and LibreHardwareMonitor (web server). Without them the zone is labelled “ACPI”, and a zone that didn't move by half a degree under load is discarded with a hint on what to run; the same in Why is it lagging?, stress tests, the Laptop section, the overlay (which hides the zone) and reports. NVIDIA sensors came from the first card on the bus (the GT 710 in a GT 710 + P106 build); now they come from the card picked for the test, the one actually rendering, or the mining card. Per-module memory speed was halved on SMBIOS < 3.1 boards (DDR3-1333 shown as 667); module form factor used WMI codes instead of SMBIOS ones; JEDEC vendor codes from old BIOSes are decoded; integrated GPU memory shows in MB; findings saved by older versions render without “{src}”.

**Site and search:** the site is built into a static page per language with the text in the HTML, its own titles and descriptions, canonical, hreflang, Open Graph, schema.org and `sitemap.xml`.

</details>

## [6.9] — 2026-11-07

Ревізія каталогу оптимізацій: чесніші режими, надійніший відкат, нічого, що не діє.

### Виправлено

- **Дві оптимізації змінювали те саме значення** (7 пар в «Ігровому» режимі: `cpu_scheduling` і `rt_boost` — обидві Win32PrioritySeparation, `timer_resolution` і `dynamic_tick` — той самий `bcdedit`, мережеві пакети, Cortana, служби телеметрії тощо). Друга записувала в журнал як «початкове» значення, яке вже поставила перша, тож відкат однієї з пари або нічого не змінював, або мовчки скасовував іншу, а пошук винної зміни половинним поділом міг помилитися. Тепер кожне налаштування має одну оптимізацію-власника, а взаємовиключні режими ноутбука позначені як конфліктні. Тест `test_catalog.py` не дасть цьому повторитися.
- **Оптимізації DirectX** («Оптимізація вікон», VRR у вікні, Auto HDR) пишуть у спільний рядок `DirectXUserGlobalSettings`, і відкат однієї повертав увесь рядок, скасовуючи інші. Нова операція `KV` змінює й повертає лише свій параметр, зберігаючи порядок решти, і так само працює в `OptimaX-Rescue.cmd`.
- **«Доведено» отримувала кожна зміна пакета**, якщо пакет загалом дав приріст: одна справжня зміна робила доведеними й сусідні. Тепер «допомогла» — лише зміна, яку заміряли окремо, а приріст пакета рахується окремо («були в пакетах із приростом»). Старі записи вважаються приростом пакета.
- **README обіцяв «залишає лише те, що допомогло»**, хоча розумна оптимізація залишає все, що не шкодить. Текст виправлено.
- Опис фіксованої підкачки згадував очищення під час вимкнення, якого немає з 6.3.2; «Очистити дані пристроїв» стирала історію UserAssist, хоча обіцяла лише сканування пристроїв.

### Змінено

- **Не в планах за замовчуванням**: «Очистити історію Провідника» (стирає й вигляд папок — це приватність, а не швидкість) та «Очистити оперативну пам'ять» (ефект на хвилини) — обидві невідворотні; «Вимкнути Nagle» й «Прибрати обмеження мережі» (TCP, а шутери працюють через UDP); фіксована підкачка (без запасу важкій грі може забракнути пам'яті); прискорення миші (звичка — додає лише мета «мінімальна затримка»); вимкнення індексування (лише для старих ПК). Усе це лишається в експертному меню.
- **Прибрано з каталогу** (застосоване раніше позначене в «Резервних копіях» і відкочується як завжди; сторож не пропонує застосувати знову): «Вимкнути Windows Defender» (захист від підробки ігнорує ці політики), «Примусовий HPET» (знижує FPS), «Ядро Windows завжди в пам'яті» (IoPageLockLimit — параметр часів XP), «Оптимізація TCP/IP і DNS», «Прискорення мережевого стеку», «Compound TCP» (значення за замовчуванням, застарілі параметри або заміна CUBIC), «Real-Time Thread Boost» (дубль двох інших).
- Пакет служб більше не вимикає DiagTrack і dmwappushservice — це робить «Вимкнути телеметрію».

### Швидкодія

- Вікно з'являється з головною сторінкою, а решта шістнадцяти добудовується у вільні проходи циклу подій (або в момент першого звернення).
- Вибрані вбудовані додатки видаляються одним запуском PowerShell на весь пакет змін замість окремого PowerShell і `Get-AppxPackage` для кожного.

### Прибирання

- Мертві обгортки в `mining.py`, `phonemon.demo_url`, невикористані імпорти, некоректні `# noqa`.

<details>
<summary>English</summary>

**Fixed:** pairs of optimizations changing the same value (7 in the Gaming mode) — the second recorded the first one's value as the “original”, so rolling one back either did nothing or silently cancelled the other, and the culprit search could go wrong; every setting now has a single owner, mutually exclusive laptop modes are marked as conflicts, and `test_catalog.py` keeps it that way. The DirectX optimizations (windowed, VRR, Auto HDR) share the `DirectXUserGlobalSettings` string and rolling one back restored the whole string; the new `KV` operation changes and restores only its own part, also in `OptimaX-Rescue.cmd`. “Proven” went to every change in a batch that gained FPS; now only a change measured on its own is proven, and batch gains are counted separately. The README promised “keeps only what helped” while smart optimization keeps everything that doesn't hurt — fixed. Stale texts for the fixed page file and “Clean device data” (which also wiped UserAssist).

**Changed:** no longer in default plans — clearing Explorer history and RAM (both irreversible), Nagle and network throttling (TCP only; shooters use UDP), the fixed page file, mouse acceleration (added only by the “lowest latency” goal), search indexing (old PCs only); all stay in the expert menu. **Removed from the catalog** (already applied ones are marked in Backups and roll back as usual; the guard won't re-apply them): turning off Defender (Tamper Protection ignores it), forced HPET, IoPageLockLimit, three network packs, and a duplicate CPU priority tweak. The services pack no longer touches DiagTrack and dmwappushservice.

**Performance:** the window appears with the home page while the other pages are built in idle event-loop passes; selected built-in apps are removed in one PowerShell run per batch.

</details>

## [6.8.1] — 2026-11-06

Майнінгова карта поруч з другою відеокартою NVIDIA, до якої підключено монітор (P106 + GT 710).

### Додано

- **Чесне попередження для пари NVIDIA + NVIDIA.** Офіційний драйвер NVIDIA дає майнінговій карті малювати лише разом з вбудованою графікою Intel / AMD. Поруч з іншою NVIDIA вона працює тільки для обчислень (режим TCC, DirectX її не бачить), а переведена в WDDM (`nvidia-smi -dm 0`) зупиняється з кодом 43; `EnableMsHybrid` (1 — майнінговій, 2 — карті з монітором) цього не змінює. Перевірено на P106-100 + GT 710 з драйвером 472.12. Тепер Universal GPU Renderer і «Чому лагає?» в такому разі кажуть «P106 поруч з GT 710: для ігор не працює» з порадою (монітор — на материнську плату, у BIOS Primary Display = iGPU), а пошук ігор, призначивши їх, попереджає, що діяти це почне лише тоді. P106 знаходиться за PCI ID у розділах драйверів, навіть коли DirectX її не бачить. OptimaX нічого не пише в розділи драйверів.

### Виправлено

- **Карту з монітором NVIDIA OptimaX вважала майнінговою**, коли DirectX бачив лише її: Universal GPU Renderer показував «P106-100 — драйвер бачить її як GeForce GT 710», радив перевстановити драйвер, а перевірка гри міряла не ту карту. Тепер єдина карта з виходами ніколи не стає «майнінговою».
- **З двома картами NVIDIA перевірка «на якій карті малює гра» могла сказати «малює P106»**, коли малювала інша: вона вірила тому, що гра завантажила драйвер NVIDIA, а він в обох карт той самий. Тепер у такій парі вирішують лише лічильники «GPU Engine» за LUID карти. Повідомлення «малює вбудована» стали «малює карта з монітором».
- **Перевірка DirectX / Vulkan більше не живе в кеші довше, ніж до перезавантаження** — після зміни драйвера чи режиму карти (TCC / WDDM) OptimaX бачить актуальний стан.

<details>
<summary>English</summary>

**Added — an honest warning for an NVIDIA + NVIDIA pair.** The official NVIDIA driver lets a mining card render only together with Intel / AMD integrated graphics. Next to another NVIDIA card it works for compute only (TCC mode, invisible to DirectX), and switched to WDDM (`nvidia-smi -dm 0`) it stops with code 43; `EnableMsHybrid` (1 for the mining card, 2 for the card with the monitor) doesn't change that — tested on a P106-100 + GT 710 with driver 472.12. Universal GPU Renderer and “Why does it lag?” now say “P106 next to GT 710: doesn't work for games” with advice (monitor to the motherboard, Primary Display = iGPU in the BIOS), and the game scan warns that its assignments only take effect then. The P106 is found by PCI ID among the driver keys even when DirectX can't see it. OptimaX writes nothing to the driver keys.

**Fixed:** when DirectX saw only the NVIDIA card with the monitor, OptimaX took it for the mining card (“P106-100 — the driver sees it as GeForce GT 710”), suggested reinstalling the driver, and the game check measured the wrong card — a lone card with outputs is never treated as the mining card now. With two NVIDIA cards the “which card renders the game” check could say “the P106” while the other card rendered — it trusted the loaded NVIDIA driver, which both cards share; in such a pair only the GPU Engine counters per card LUID decide now, and “the integrated GPU renders” messages now say “the card with the monitor”. The DirectX / Vulkan check no longer outlives a restart in the cache.

</details>

## [6.8] — 2026-11-06

Hardware Center: діагностика, тести й звіти про залізо в одному місці, FPS-оверлей в іграх і перевірка ПК перед покупкою. Докладно — [docs/uk/hardware-center.md](docs/uk/hardware-center.md).

### Додано

- **Hardware Center** (група «Пристрій»): відомості про залізо (інструкції процесора, слоти пам'яті, плата, BIOS/UEFI і Secure Boot, EDID моніторів з оцінкою колірного охоплення, мережеві адаптери), тести процесора (одне ядро, усі ядра, стрес-тест із самоперевіркою обчислень, тротлінгом, Power Limit і нестабільною частотою), оперативної пам'яті (6 шаблонів), відеопам'яті (буфери OpenGL на вибраній карті), дисків (SMART, журнал NVMe, швидкість без кешу Windows лише у власному тимчасовому файлі, читання поверхні, chkdsk лише для читання), батареї, монітора (кольоровий тест), клавіатури, миші, динаміків, камери й мікрофона; комбіновані стрес-тести (CPU, GPU, CPU + GPU, RAM, VRAM, диск) з аварійною зупинкою за температурою. Кожен тест — окремим процесом, з прогресом і зупинкою; результат PASS / WARN / FAIL / SKIPPED / N/A.
- **Фонові процеси під час ігор**: хто навантажував процесор, пам'ять, диск і відеокарту, збіг піків із падіннями FPS, що можна зробити (OptimaX нічого не закриває сама). **Що обмежує продуктивність** — з доказами, впевненістю, очікуванням і ризиками; **поради щодо андервольтингу** без змін у системі.
- **Діагностика Windows**: сині екрани, раптові вимкнення, TDR, WHEA, пристрої з помилкою драйвера; аналіз дампів через cdb.exe, якщо він встановлений; SFC і DISM за підтвердженням.
- **Перевірка ПК перед покупкою**: 14 кроків, порівняння із заявленою конфігурацією, на гібридному ноутбуці — обидві відеокарти й підтвердження, що дискретна справді малює.
- **Звіти**: HTML, JSON, PDF, перегляд, історія, порівняння двох звітів; без назви ПК та імені користувача, якщо не дозволити.
- **FPS-оверлей в іграх**: FPS, 1% / 0.1% low, час кадру, датчики, режим показу; без DLL-ін'єкції (PresentMon + прозоре вікно поверх гри), гарячі клавіші, запис сесії в CSV/JSON зі звітом.

### Обмеження

- cdb.exe у складі OptimaX немає — аналіз дампів працює, якщо встановлено Debugging Tools for Windows.
- Температуру ядер процесора Windows без драйвера датчиків не дає — показується «н/д».
- Відеопам'ять і оперативна пам'ять перевіряються частково; мережа по процесах — лише для всієї системи.

### Виправлено

- **GPU-тест на ноутбуці з двома відеокартами малював вбудована графіка**, а RTX 4060 простоювала, і перемкнути це було ніяк (відгук користувача портативної версії). На сторінці «Бенчмарки» тепер є рядок **«Відеокарта»** (коли карт кілька): «Автоматично — висока продуктивність» або конкретна карта. Вибір зберігається за моделлю карти (VEN/DEV/SUBSYS), а не за LUID, який змінюється після перезавантаження. OptimaX просить карту способом, що їй підходить: NVIDIA Optimus — змінна драйвера лише для процесу тесту (система не змінюється); AMD / Intel Arc — налаштування «Графіка» Windows для exe OptimaX за згодою й через журнал відкату; майнінгова карта — Mesa, як і раніше. Після заміру OptimaX звіряє GL_RENDERER з вибраною картою і лічильники Windows «GPU Engine» процесу тесту (3D за LUID адаптера) й підписує результат «підтверджено», «за драйвером OpenGL», «ймовірно» або «не та карта». Результат на не тій карті не порівнюється з іншими (ні в історії, ні в розумній оптимізації), а під ним з'являються кнопки «Спробувати через Mesa», «Дозволити «Високу продуктивність»» і «Вибрати відеокарту». Ноутбук від батареї — попередження й позначка в результаті. Розумна оптимізація міряє на тій самій вибраній карті.
- **Датчики NVIDIA не читалися** в «Чому лагає?» і в моніторі на телефоні, а «Виміряти» на ПК з майнінговою картою завжди завершувався помилкою: `Nvml.ok` — властивість, а її викликали як функцію, і виняток тихо ковтався.

<details>
<summary>English</summary>

**Added — Hardware Center** (Device group, see [docs/en/hardware-center.md](docs/en/hardware-center.md)): hardware info (CPU instruction sets, memory slots, board, BIOS/UEFI and Secure Boot, monitor EDID with a color gamut estimate, network adapters); CPU tests (single core, all cores, a self-checking stress test with throttling, power-limit and unstable-clock detection), RAM (6 patterns), VRAM (OpenGL buffers on the chosen card), disks (SMART, the NVMe log, cache-bypassing speed in its own temporary file only, surface read, read-only chkdsk), battery, display (color test), keyboard, mouse, speakers, camera and microphone; combined stress tests (CPU, GPU, CPU + GPU, RAM, VRAM, disk) with a temperature emergency stop. Each test runs as its own process with progress and stop; results are PASS / WARN / FAIL / SKIPPED / N/A. Background processes during games (who loaded the system, peaks vs FPS drops, options — OptimaX closes nothing itself); what limits performance (evidence, confidence, expectations, risks); undervolting advice with no system changes. Windows diagnostics (blue screens, sudden shutdowns, TDR, WHEA, devices with driver errors), dump analysis via cdb.exe when installed, SFC and DISM after confirmation. A 14-step pre-purchase PC check with an advertised-configuration comparison and, on hybrid laptops, proof that the discrete GPU really renders. Reports: HTML, JSON, PDF, preview, history, comparing two reports, without the PC and user name unless allowed. **FPS overlay**: FPS, 1% / 0.1% lows, frametime, sensors, present mode; no DLL injection (PresentMon + a transparent window over the game), hotkeys, session recording to CSV/JSON with a report. **Limits:** OptimaX doesn't ship cdb.exe; CPU core temperatures need a sensor driver (shown as N/A); VRAM and RAM are tested partly; network is per system, not per process.

**Fixed:** on a laptop with two GPUs the GPU test ran on the integrated graphics while the RTX 4060 sat idle, with no way to switch (a portable-version user report). The Benchmarks page now has a **Graphics card** row when there is more than one card: “Auto — high performance” or a specific card, remembered by the card's model (VEN/DEV/SUBSYS) rather than the LUID, which changes after a reboot. OptimaX asks for the card the way that suits it: NVIDIA Optimus — a driver variable for the test process only (nothing in the system changes); AMD / Intel Arc — the Windows Graphics setting for the OptimaX exe, with consent and through the rollback journal; a mining card — Mesa, as before. After the run OptimaX matches GL_RENDERER with the chosen card and reads the Windows “GPU Engine” counters of the test process (3D per adapter LUID), labelling the result confirmed / per the OpenGL driver / likely / wrong card. A run on the wrong card is never compared with others (in the history or in smart optimization), and Try via Mesa, Allow High performance and Pick a graphics card buttons appear under it. On battery the laptop shows a warning and the result is marked. Smart optimization measures on the same chosen card. NVIDIA sensors were never read in Why is it lagging? and the phone monitor, and Measure on a mining-card PC always failed: `Nvml.ok` is a property but was called as a function, and the exception was swallowed.

</details>

## [6.7] — 2026-11-02

Безпека й швидкість самої програми: усе, що OptimaX з правами адміністратора читає й запускає, тепер лежить у захищеній папці.

### Безпека

- **Журнал відкату** переїхав з `%APPDATA%\OptimaX` у `%ProgramData%\OptimaX\state`, куди звичайні програми писати не можуть. Під час першого запуску журнал переноситься сам. Кожен запис перед відкатом перевіряється, а пошкоджений чи чужий не виконується й не потрапляє в OptimaX-Rescue.cmd. Команди відкату служб, задач і живлення передаються списком аргументів, а не рядком для cmd.
- **Задачі планувальника з правами адміністратора** (автозапуск, пробний період, Safety, обслуговування за розкладом, розумна оптимізація, DNS-фільтр від SYSTEM) створюються лише для OptimaX, встановленої в Program Files. Портативна копія про це повідомляє. Задачі старіших версій, що запускали exe поза Program Files, прибираються під час запуску, а DNS-фільтр при цьому вимикається коректно, з поверненням DNS.
- **PresentMon** лежить у `%ProgramData%\OptimaX\tools`. Сума записується під час завантаження й звіряється перед кожним запуском. Копія, завантажена старішою версією, береться лише з дійсним підписом Intel.
- **Папки в ProgramData** (`state`, `tools`, `updates`, `rescue`, `adblock`, шари для майнінгових карт) захищаються однаково (новий модуль `secfs.py`): власник — адміністратори, запис — лише адміністраторам і SYSTEM, а посилання на місці папки відкладається вбік.
- **Системні програми** (powershell.exe, schtasks, icacls, taskkill…) запускаються за повним шляхом із System32, а системні змінні середовища процесу беруться з Windows. PowerShell завантажує лише системні модулі.
- **Файли для ігор** (DXVK, Mesa) не кладуться в системні папки Windows, навіть якщо «папка гри» веде туди.
- **«Вимкнути ізоляцію ядра (VBS / HVCI)»** більше не входить у профіль Full і в ціль «FPS» майстра — лише вручну.
- Збірка: версія PyInstaller обмежена (`>=6.10,<7`). У релізі право запису має лише крок публікації.

### Швидше

- Аналіз заліза під час запуску не запускає три процеси PowerShell повторно до перезавантаження ПК. Кеш скидається раніше, якщо змінився драйвер відеокарти, диски чи мережеві адаптери.
- Перелік задач планувальника (перевірка твіків, задачі NVIDIA) іде через COM-інтерфейс планувальника, а не через Get-ScheduledTask.

<details>
<summary>English</summary>

**Security:** the rollback journal moved from `%APPDATA%\OptimaX` to `%ProgramData%\OptimaX\state`, which ordinary programs can't write to (migrated automatically on first start). Every record is validated before rollback; a damaged or foreign one is neither run nor written into OptimaX-Rescue.cmd. Service, task and power rollbacks pass argument lists instead of cmd strings. Scheduled tasks with administrator or SYSTEM rights (autostart, trial, Safety, scheduled maintenance, smart optimization, DNS filter) are created only for OptimaX installed in Program Files; older tasks that ran an exe outside Program Files are removed on start, and the DNS filter is turned off properly, restoring DNS. PresentMon lives in `%ProgramData%\OptimaX\tools`, its hash is recorded at download and checked before every launch; a copy downloaded by an older version is adopted only with a valid Intel signature. ProgramData folders (`state`, `tools`, `updates`, `rescue`, `adblock`, mining-card layers) are secured the same way by the new `secfs.py`: owned by Administrators, writable only by Administrators and SYSTEM, and a link in place of the folder is moved aside. System programs run by full System32 path, the process's system environment variables come from Windows, and PowerShell loads only system modules. Game files (DXVK, Mesa) are never placed into Windows folders. “Turn off core isolation (VBS / HVCI)” is no longer part of the Full profile or the wizard's FPS goal — manual only. Build: PyInstaller is bounded to `>=6.10,<7`; in the release workflow only the publish job can write. **Faster:** hardware detection at start reuses the three PowerShell queries until the next reboot (sooner if the GPU driver, disks or network adapters change); scheduled-task listing uses the Task Scheduler COM interface instead of Get-ScheduledTask.

</details>

## [6.6] — 2026-10-31

«Чому впав комп?», бібліотека ігор, простий вигляд, монітор ПК на телефоні, перенесення налаштувань і звіт про помилку одним натисканням.

### Додано

- **«Чому впав комп?»** (сторінка «Діагностика»): сині екрани й раптові перезавантаження за 30 днів із журналу Windows простими словами — що сталося (синій екран з кодом і назвою, раптове вимкнення без синього екрана, вимкнення кнопкою), що найчастіше винне (відеодрайвер чи карта, пам'ять, драйвер пристрою, диск, процесор, живлення, перегрів) і що зробити. А також скидання відеодрайвера (Display 4101, nvlddmkm), апаратні помилки WHEA, коди з дампів у `C:\Windows\Minidump`, результат перевірки пам'яті Windows і кнопка «Перевірити пам'ять». OptimaX знає, яка гра працювала в момент збою; на ПК з майнінговою картою порада повернути грі режим «Оригінал» відкриває саме цей вибір. Про новий збій OptimaX повідомляє на головній після запуску.
- **Бібліотека ігор**: ігри зі Steam, Epic, GOG, Ubisoft і «Моїх ігор» з обкладинками (лише локальний кеш Steam; для інших — іконка exe), кнопкою «Грати» (через лаунчер гри й від імені користувача, а не адміністратора) і режимом гри, що вмикається під час запуску й вимикається сам, коли гра закриється. Час гри, останній запуск і сесії; запис FPS під час гри через PresentMon (60 секунд через 2 хвилини гри, далі раз на 15 хвилин) і графік середнього FPS та 1% low для кожної гри; на ПК з майнінговою картою — режим рендерингу гри й остання перевірка.
- **Простий вигляд** (Налаштування → «Вигляд і допомога» чи кнопка на головній): у меню лише головне, а на головній — оцінка ПК, одна кнопка «Оптимізувати» (план рекомендованого режиму у звичайному перегляді змін) і проблеми з кнопкою «Виправити».
- **«Що нового»** — коротке вікно один раз після оновлення (не після першого встановлення) і кнопка в налаштуваннях.
- **Перенесення налаштувань**: набір застосованих оптимізацій і налаштування програми (режим гри, чистильник пам'яті, бібліотека, «Мої ігри», режими ігор на майнінговій карті) — у файл, а потім на інший ПК чи після перевстановлення Windows. Під час завантаження оптимізації відкриваються в перегляді змін із перевіркою сумісності з цим залізом, «Мої ігри» додаються лише ті, чий exe є на цьому ПК, а позначки, що змінюють систему, проходять через журнал відкату.
- **Монітор ПК на телефоні**: температури, завантаження процесора й відеокарти, відеопам'ять, частота, споживання й FPS гри — на телефоні в домашній мережі, без додатків, за QR-кодом. Сторінка лише показує показники; адреса з секретним кодом («Новий код» робить старий недійсним), відповідає лише пристроям домашньої мережі; правило брандмауера — лише для приватних мереж і локальної підмережі, прибирається, коли монітор вимкнути, і під час видалення OptimaX.
- **Звіт про помилку одним натисканням**: помилка в інтерфейсі більше не закриває програму — OptimaX пропонує надіслати звіт: сторінка нового issue на GitHub із готовим текстом, з якого прибрано ім'я користувача, ім'я ПК, шляхи профілю й пошту; надсилаєте ви самі. Аварійне закриття самої програми записується, і звіт пропонується під час наступного запуску (вимкнення ПК з OptimaX у треї збоєм не вважається). «Повідомити про проблему» — у налаштуваннях.

### Виправлено

- На ПК з майнінговою картою перевірка карти показувала монітор на P106 («монітор: NVIDIA GeForce GTX 1060 6GB»): на гібридному ПК DirectX показує виходи вбудованої графіки на тій карті, на якій працює процес. Карта відомої майнінгової моделі (за ID пристрою PCI) монітором більше не вважається.
- Балансувальник фону на час гри передавав перевірці рендерингу список «Моїх ігор» замість запущених процесів.

### Обмеження

- Причина синього екрана називається за кодом і категорією: «винного драйвера» з дампу без символів налагодження OptimaX не визначає.
- Обкладинки — лише з локального кешу Steam; FPS записується, лише якщо завантажено PresentMon.
- Монітор на телефоні працює лише в одній мережі з ПК (не через інтернет) і в мережі, яку Windows вважає приватною.

<details>
<summary>English</summary>

Why did the PC crash?, a game library, a simple view, a phone monitor, settings transfer and one-click error reports. **Why did the PC crash?** (Diagnostics page): blue screens and sudden restarts of the last 30 days from the Windows log in plain words — what happened (a blue screen with its code and name, a sudden shutdown without one, a power-button shutdown), what is usually to blame (graphics driver or card, memory, a device driver, disk, CPU, power, overheating) and what to do; plus graphics driver resets (Display 4101, nvlddmkm), WHEA hardware errors, codes from the dumps in `C:\Windows\Minidump`, the Windows memory test result and a Test memory button. OptimaX knows which game was running at the moment of the crash; on a PC with a mining card the advice to return the game to the Original mode opens exactly that choice; a new crash is reported on the home page after start. **Game library**: games from Steam, Epic, GOG, Ubisoft and My games with covers (Steam's local cache only; other games get the exe's icon), a Play button (through the game's launcher and as the user, not the administrator) and game mode that turns on at launch and off when the game closes; play time, last played and sessions; FPS recorded while playing through PresentMon (60 seconds after 2 minutes of play, then every 15 minutes) and a chart of average FPS and 1% lows per game; on a PC with a mining card, the game's render mode and its last check. **Simple view** (Settings → View and help, or the button on the home page): only the essentials in the menu, and on the home page a PC score, one Optimize button (the recommended mode's plan in the usual change review) and problems with a Fix button. **What's new** — a short window once after an update (not after the first install) and a button in Settings. **Settings transfer**: the applied optimizations and the program's settings (game mode, memory cleaner, library, My games, render modes of games on a mining card) to a file, then onto another PC or after reinstalling Windows; on loading, optimizations open in the change review with a compatibility check against this hardware, My games are added only when the exe exists on this PC, and flags that change the system go through the rollback journal. **Phone monitor**: temperatures, CPU and GPU load, video memory, clock, power draw and the game's FPS on your phone over the home network, no app, via a QR code; the page only shows readings, the address carries a secret code (New code invalidates the old one), only home-network devices get answers, and the firewall rule covers private networks and the local subnet only and is removed when the monitor is turned off and on uninstall. **One-click error reports**: an error in the interface no longer closes the program — OptimaX offers to send a report: a new GitHub issue page with the text filled in and the user name, PC name, profile paths and email removed; you send it yourself. A crash of the program itself is recorded and the report is offered on the next start (shutting the PC down with OptimaX in the tray is not a crash); Report a problem is in Settings. **Fixed:** on a PC with a mining card the card check showed the monitor on the P106 (“monitor: NVIDIA GeForce GTX 1060 6GB”) — on a hybrid PC DirectX reports the integrated GPU's outputs on the card the process runs on, so a card of a known mining model (by PCI device ID) is no longer taken for the display; the background balancer passed the list of My games instead of the running processes to the render check. **Limits:** a blue screen's cause is named by its code and category — OptimaX doesn't find the “guilty driver” in a dump without debug symbols; covers come only from Steam's local cache and FPS is recorded only when PresentMon is downloaded; the phone monitor works only on the same network as the PC (not over the internet) and on a network Windows treats as private.

</details>

## [6.5] — 2026-10-31

Universal GPU Renderer: ігри на майнінговій карті (P106 / P104 / CMP) — режим рендерингу для кожної гри, перевірка, на якій карті гра малює насправді, аналізатори драйвера, PCIe, пам'яті й кешу шейдерів.

### Додано

- **Режим рендерингу для кожної гри** (кнопка «Режим» у розділі «Ігри на P106»): «Авто» (DirectX 10–12 і Vulkan — напряму, DirectX 9 — через DXVK, OpenGL — через Mesa), «Напряму на карту», «DXVK» (і для DirectX 10 / 11), «OpenGL через Mesa» та «Оригінал» (OptimaX повертає все, що зробила для гри, і більше її не чіпає). Режим, результати перевірок і позначки «працює / не працює» зберігаються в профілі гри; профілі експортуються й імпортуються (JSON), «Видалити профіль» повертає оригінальний стан.
- **Перевірка сумісності до змін.** Перед застосуванням видно, що саме зміниться. Шар кладеться лише якщо він завантажений і звірений із сумами, є exe потрібної розрядності, у грі немає античиту (EasyAntiCheat, BattlEye, XIGNCODE3, GameGuard, PunkBuster, Vanguard), DirectX бачить майнінгову карту, а на ній є Vulkan (DXVK, Zink) чи DirectX 12 (Mesa d3d12). Для DirectX 9 — лише d3d9 / d3d8, для DirectX 10 / 11 — dxgi / d3d11 / d3d10core. Якщо щось не вдалося посеред зміни, гра повертається до попереднього режиму.
- **Визначення API кожного exe**: DirectX 9 / 10 / 11 / 12, OpenGL, Vulkan — з таблиці імпорту exe і рушія (UnityPlayer.dll, shaderapidx9.dll у Source); розрядність x64 / x86.
- **GPU Renderer Monitor — на якій карті гра малює насправді.** Кнопка «Перевірити» (і автоматично через 40 секунд після запуску гри) дивиться лічильники Windows «GPU Engine» процесу гри й те, драйвер якої карти гра завантажила (NVIDIA / Intel / AMD / WARP) і через що малює (DXVK, Mesa d3d12 / Zink, нативний DirectX, OpenGL, Vulkan). Для HD 4000 та інших драйверів WDDM 1.x, у яких лічильників немає, вирішує драйвер у процесі. «Висока продуктивність» у «Графіці» доказом не вважається.
- **Перевірка DirectX і Vulkan** в окремому процесі (збій драйвера не закриє OptimaX): адаптери DXGI з виходами й відеопам'яттю, чи створюється DirectX 12 на кожному, пристрої Vulkan з версіями API й драйвера та LUID.
- **P106 Driver Analyzer**: модель за PCI ID і назва від драйвера, версія драйвера, DirectX 12, Vulkan, карта з монітором; проблеми — DirectX не бачить карту (стандартний драйвер вимкнув 3D), немає Vulkan, вбудована графіка без драйвера.
- **PCIe Link Analyzer і GPU Memory Analyzer** («Виміряти» з запущеною грою, а також у «Чому лагає?»): покоління й ширина PCIe під навантаженням проти можливих, трафік лінії, скільки займає передача кадрів на вбудовану графіку з монітором; заповнення відеопам'яті, вихід гри в спільну пам'ять, вільна RAM.
- **Shader Cache Manager**: розмір кешів DirectX / NVIDIA / Intel / AMD / Mesa, порожні (пошкоджені) файли, зміна драйвера; очищення з резервною копією й відновлення.
- **Game Compatibility Database**: відоме про рушій і API популярних ігор (рекомендований режим, античит, параметри запуску на кшталт `-vulkan` чи `-window-mode borderless`) і ваші результати — окремо. Ваші позначки мають перевагу.
- **Zink**: OpenGL через Mesa можна перемкнути з DirectX 12 на Zink (Vulkan) — експериментально, для ігор, у яких Mesa ввімкнено.
- **Нові ігри**: фоновий пошук повідомляє про нові встановлені ігри.
- **«Чому лагає?» 2.0**: на якій карті малювала гра (DirectX 9 / OpenGL без шару, повноекранний режим — з кнопкою вибору режиму, без змін без підтвердження), кадри PresentMon усіх процесів паралельно із заміром (якщо PresentMon завантажено) і причини фризів (підкачка, диск, відеопам'ять, процесор, компіляція шейдерів), PCIe, пам'ять і драйвер карти NVIDIA, споживання й частота. **Історія замірів** (GPU Bottleneck History) з виявленням просідань FPS.
- **Game Booster 2.0**: профілі «Мінімальна затримка» (усі перемикачі + високий пріоритет процесу гри на час режиму) і «Стабільний frametime» (без закриття фонових програм і зміни пріоритету) — загальні або для окремої гри; авторежим гри і для ігор зі Steam / Epic / GOG / Ubisoft без додавання в «Мої ігри».

### Змінено

- Твік «Вимкнути Fullscreen Optimizations» заблоковано на ПК з майнінговою картою: справжній повноекранний режим можливий лише на карті з монітором, і гра переходила на вбудовану графіку. Якщо його вже застосовано, розділ «Ігри на P106» пропонує повернути.
- Архів DXVK у релізі містить і бібліотеки DirectX 10 / 11 (dxgi, d3d11, d3d10core). Встановлений раніше DXVK лише з DirectX 9 працює як і раніше; для режиму DXVK у DirectX 10 / 11 його можна завантажити ще раз.

### Обмеження

- DirectX 12 працює напряму: VKD3D-Proton не використовується. Системні DirectX / Vulkan / OpenGL-бібліотеки й драйвери Windows не змінюються — шари лише в папках ігор.
- Zink на Windows експериментальний; DXVK і Mesa працюють не з кожною грою. Результат перевіряє «Перевірити», невдалий режим позначається й повертається.
- Автоматичні тести перевіряють логіку на фальшивій Windows і в CI на Windows Server; на справжній P106-100 з HD 4000 цю версію перевірено не повністю.

<details>
<summary>English</summary>

Universal GPU Renderer: games on a mining card (P106 / P104 / CMP) — a render mode per game, a check of which card really renders it, and driver, PCIe, memory and shader cache analyzers. **A render mode per game** (the Mode button in “Games on the P106”): Auto (DirectX 10–12 and Vulkan natively, DirectX 9 via DXVK, OpenGL via Mesa), Native GPU, DXVK (for DirectX 10 / 11 too), OpenGL translation, and Original (OptimaX reverts everything it did for the game and leaves it alone); mode, check results and “works / doesn't work” marks live in the game's profile, profiles export and import as JSON, and “Remove profile” restores the original state. **Compatibility is checked before any change** and the exact changes are shown: a layer is used only if it is downloaded and matches its checksums, the exe has the right bitness, the game has no anti-cheat (EasyAntiCheat, BattlEye, XIGNCODE3, GameGuard, PunkBuster, Vanguard) and the card has Vulkan (DXVK, Zink) or DirectX 12 (Mesa d3d12); DirectX 9 gets only d3d9 / d3d8, DirectX 10 / 11 — dxgi / d3d11 / d3d10core; if something fails midway the game returns to its previous mode. **API detection per exe** (DirectX 9 / 10 / 11 / 12, OpenGL, Vulkan, from the exe's and the engine's import tables) and bitness. **GPU Renderer Monitor** — the Check button (and automatically 40 seconds after a game starts) reads the Windows “GPU Engine” counters of the game's process and which GPU's driver the game loaded (NVIDIA / Intel / AMD / WARP) and what it renders through (DXVK, Mesa d3d12 / Zink, native DirectX, OpenGL, Vulkan); for HD 4000 and other WDDM 1.x drivers without counters the driver in the process decides; the Graphics “High performance” setting is never taken as proof. **DirectX and Vulkan probe** in a separate process. **P106 Driver Analyzer**, **PCIe Link Analyzer** and **GPU Memory Analyzer** (generation and width under load, link traffic, the frame copy to the integrated GPU, VRAM, spill to shared memory, free RAM), **Shader Cache Manager** (sizes, empty files, driver changes, clearing with a backup and restore), **Game Compatibility Database** (known engine / API facts and launch options, kept apart from your own results, which take precedence), **Zink** as an experimental alternative to Mesa's DirectX 12 driver, **new game notifications**. **Why lag? 2.0**: which card rendered the game (with a button to pick a mode; nothing changes without confirmation), PresentMon frames of all processes alongside the run and stutter causes (paging, disk, VRAM, CPU, shader compilation), PCIe, memory and NVIDIA driver findings, plus a **measurement history** with FPS regression detection. **Game Booster 2.0**: “Lowest latency” and “Stable frametime” profiles, global or per game, and auto game mode for Steam / Epic / GOG / Ubisoft games too. **Changed:** “Disable Fullscreen Optimizations” is blocked on mining-card PCs (exclusive fullscreen moved games to the integrated GPU), with an offer to revert it if applied; the DXVK release archive now includes the DirectX 10 / 11 libraries. **Limits:** DirectX 12 runs natively (no VKD3D-Proton); Windows system libraries and drivers are never changed; Zink is experimental and DXVK / Mesa don't work with every game, so results are verified with Check; automated tests cover the logic on a fake Windows and in CI on Windows Server — this version is not yet fully verified on a real P106-100 with HD 4000.

</details>

## [6.4.3] — 2026-10-30

Ігри на майнінговій відеокарті: OptimaX сама переносить їх із вбудованої графіки на P106 / P104 / CMP — і DirectX 10–12, і (через перекладачі) DirectX 9 та OpenGL.

### Додано

- **Ігри на P106-100** (з'являється на сторінці «Ігри», якщо в ПК майнінгова карта без відеовиходів). OptimaX знаходить встановлені ігри (Steam, Epic, GOG, Ubisoft і «Мої ігри») і призначає кожен їхній exe на майнінгову карту — як «Висока продуктивність» у налаштуваннях «Графіка» Windows, тільки для всіх ігор одразу й з відкатом. Ваш власний вибір у «Графіці» не перезаписується. Перемикач «Автоматично призначати нові ігри» перевіряє нові ігри раз на 15 хвилин.
- **DirectX 9 через DXVK.** Ігри на DirectX 9 (CS:Source, Half-Life 2, старі ігри) бачать лише відеокарту з монітором, тож «Графіка» Windows на них не діє. Для кожної такої гри тепер можна ввімкнути DXVK: він перекладає DirectX 9 на Vulkan, і гру малює майнінгова карта. На Windows DXVK працює не з кожною грою — тоді його просто вимкнути тією ж кнопкою.
- **OpenGL через Mesa.** Так само для OpenGL: Mesa перекладає OpenGL на DirectX 12.
- DXVK і Mesa завантажуються одним натисканням з релізу OptimaX (з перевіркою суми), лежать у папці, куди може писати лише адміністратор, і звіряються із сумами перед кожним копіюванням. Бібліотеки тієї ж розрядності, що й гра (x64 чи x86), кладуться поруч з exe, а файл, що лежав там раніше, відкладається й повертається відкатом (і через OptimaX-Rescue.cmd).
- **GPU-тест і розумна оптимізація на майнінговій карті.** Коли Mesa завантажена, тест малює P106, а не вбудована графіка. Бали з Mesa порівнюються лише з балами з Mesa.

### Виправлено

- Підказка «Як грати на майнінговій карті» помилково пояснювала, що ігри на DirectX 9 дають синій екран на майнінговій карті. Насправді DirectX 9 (як і OpenGL) просто не бачить карту без монітора; підказка тепер веде до DXVK і Mesa.

<details>
<summary>English</summary>

Games on a mining graphics card: OptimaX moves them from the integrated graphics to the P106 / P104 / CMP by itself — DirectX 10–12 directly, DirectX 9 and OpenGL through translation layers. **Games on the P106-100** (on the Games page when the PC has a mining card without video outputs): OptimaX finds installed games (Steam, Epic, GOG, Ubisoft and My games) and assigns each of their exe files to the mining card — like “High performance” in Windows Graphics settings, but for every game at once and with rollback. Your own Graphics choice is never overwritten. The “Assign new games automatically” switch checks for new games every 15 minutes. **DirectX 9 via DXVK:** DirectX 9 games (CS:Source, Half-Life 2, older titles) only see the card with the monitor, so Windows Graphics settings don't apply; DXVK can now be enabled per game to translate DirectX 9 to Vulkan so the mining card renders it (not every game runs with DXVK on Windows — then disable it with the same button). **OpenGL via Mesa:** the same for OpenGL, translated to DirectX 12. DXVK and Mesa download in one click from the OptimaX release (checksum verified), live in an admin-only folder and are re-verified before every copy; libraries of the game's bitness (x64 or x86) go next to the exe, and any file already there is set aside and restored by rollback (and by OptimaX-Rescue.cmd). **GPU test and smart optimization on the mining card:** with Mesa downloaded the test renders on the P106 instead of the integrated graphics; Mesa scores are compared only with other Mesa scores. **Fixed:** the “How to game on a mining card” tip wrongly said DirectX 9 games blue-screen on mining cards; DirectX 9 (like OpenGL) simply can't see a card without a monitor, and the tip now points to DXVK and Mesa.

</details>

## [6.4.2] — 2026-10-30

GPU-тест без обмеження FPS частотою монітора.

### Змінено

- Підказка «Як грати на майнінговій карті» більше не каже, що FPS обмежений частотою вбудованої графіки, і не радить обмежувати його через RTSS.

### Виправлено

- **GPU-тест на весь екран більше не впирається в 60 FPS.** Повноекранне вікно тесту Windows виводила в обхід композиції, і драйвер синхронізував кадри з частотою монітора, хоч тест і вимикає вертикальну синхронізацію: у вікні було 100+ FPS, на весь екран — рівно 60. Тепер вікно лишається під композицією (рамка в 1 px, як радить Qt), і на весь екран FPS такий самий, як у вікні.
- **Без паузи між кадрами.** Qt чекав 5 мс перед кожним наступним кадром (а таймер Windows міг ще й подовжити цю паузу), тож потужні відеокарти не розкривалися навіть у вікні. Тепер новий кадр починається одразу.
- Бали виправленого тесту не порівнюються зі старими замірами — ні в історії, ні в картці «було → стало», щоб виправлення тесту не виглядало як приріст від оптимізації. Перший замір після оновлення стає новою точкою відліку.

<details>
<summary>English</summary>

The GPU test without an FPS cap at the monitor refresh rate. **The fullscreen GPU test is no longer capped at 60 FPS.** Windows presented the fullscreen test window bypassing composition, and the driver synced frames to the monitor refresh rate even though the test turns vsync off: 100+ FPS in a window, exactly 60 in fullscreen. The window now stays composited (a 1 px border, as Qt recommends), so fullscreen FPS matches windowed. Qt also waited 5 ms before every next frame (which the Windows timer could stretch further), holding back fast GPUs even in a window; the next frame now starts right away. Scores of the fixed test are not compared with older runs, neither in the history nor on the before/after card, so the fix does not look like an optimization gain; the first run after the update is the new baseline. The “How to game on a mining card” tip no longer says FPS is capped by the integrated graphics refresh rate or suggests capping it with RTSS.

</details>

## [6.4.1] — 2026-10-30

Майнінгові відеокарти та чесний GPU-тест на ПК, де картинку виводить вбудована графіка.

### Додано

- **Майнінгові відеокарти.** OptimaX розпізнає P106-090/100, P104-100/101, P102-100 і CMP 30HX–170HX за ідентифікатором PCI — навіть коли пропатчений драйвер показує їх як GeForce (P106-100 — «GTX 1060 6GB»). На сторінці «Залізо» карта підписана як майнінгова без відеовиходів, а перевірка ПК замість хибного «перекиньте кабель монітора у відеокарту» пояснює, як на ній грати: призначити ігри на карту, лише пропатчений драйвер, обмеження FPS частотою вбудованої графіки, старі ігри (DirectX 9, Adobe AIR) — на вбудованій, заміри — у грі.
- Для майнінгових карт OptimaX не радить оновлювати драйвер з nvidia.com (звичайний драйвер вимикає 3D), не пропонує й блокує апаратне планування GPU (з пропатченими драйверами воно часто закінчується синім екраном).

### Виправлено

- **GPU-тест на гібридних системах.** Якщо вікно тесту малює вбудована графіка, а NVIDIA простоює (ноутбуки з Optimus, майнінгові P106/P104/CMP, картинка з яких іде через вбудоване відео), результат тепер підписаний картою, що справді малювала, а датчики NVIDIA, що простоює, не показуються поруч із FPS вбудованої графіки. У вікні тесту з'являється попередження, у картці результату — пояснення. Раніше такий результат підписувався іменем NVIDIA з її «холодними» датчиками.
- **Розумна оптимізація** не приймає замір GPU-тесту, зроблений на вбудованій графіці при наявній NVIDIA, і пропонує міряти у грі (PresentMon) — інакше рішення про твіки ухвалювалися б за швидкодією не тієї відеокарти.
- **Історія балів** порівнює результат лише з попереднім заміром на тій самій відеокарті.
- Рядки датчиків і помилок у вікні тесту більше не накладаються на смугу прогресу в стрес-тесті з NVIDIA.

<details>
<summary>English</summary>

Mining graphics cards and an honest GPU test on PCs where the integrated graphics display the picture. **Mining cards:** OptimaX recognises P106-090/100, P104-100/101, P102-100 and CMP 30HX–170HX by their PCI ID, even when a patched driver presents them as GeForce (a P106-100 shows up as “GTX 1060 6GB”). The Hardware page labels the card as a mining card without video outputs, and the PC check explains how to game on it instead of the wrong “move the monitor cable to the graphics card”: assign games to the card, use only the patched driver, FPS is capped by the integrated graphics refresh rate, run old games (DirectX 9, Adobe AIR) on the integrated graphics, measure in the game. OptimaX no longer suggests a driver from nvidia.com for these cards (the regular driver disables 3D) and blocks hardware-accelerated GPU scheduling on them (with patched drivers it often ends in a blue screen). **GPU test on hybrid systems:** when the test window is rendered by the integrated graphics while an NVIDIA card sits idle (Optimus laptops, mining cards), the result is labelled with the GPU that actually rendered it and the idle card’s sensors are no longer shown; the test window warns about it and the result card explains it. Smart optimization rejects such a measurement and suggests measuring in the game (PresentMon). Scores are compared only with a previous run on the same GPU. The sensor line no longer overlaps the progress bar in the stress test.

</details>

## [6.4] — 2026-10-30

OptimaX не просто змінює Windows, а доводить, що кожна оптимізація справді допомагає, — і ще надійніше повертає все назад.

### Безпека й відкат

- **Жодної зміни без запису.** Запис відкату тепер потрапляє на диск *до* того, як зміниться система. Якщо OptimaX аварійно закриється посеред оптимізації (виліт, синій екран, зникло світло), під час наступного запуску вона сама поверне те, що встигло змінитися, а пакет змін, який не дійшов до кінця, запропонує відкотити. Раніше частина змін могла лишитися в системі без запису.
- **Оптимізація або вся, або ніяк.** Якщо посеред пункту трапилася помилка (немає доступу до ключа реєстру тощо), уже змінене в цьому пункті одразу повертається, а пакет продовжується.
- **Журнал не загубиться.** Попередня версія журналу зберігається як резервна копія; пошкоджений файл відкладається, а журнал відновлюється з копії. Раніше пошкоджений журнал мовчки заміщувався порожнім, і відкат ставав неможливим. Якщо журнал не вдається записати (диск повний, антивірус), OptimaX зупиняється й нічого не змінює.
- **Знімок початкових налаштувань Windows.** Перед першою зміною OptimaX запам'ятовує всі параметри, які може змінити. Навіть якщо журнал загубиться, «Резервні копії» → «Початкові налаштування Windows» знайде зміни OptimaX без запису й поверне їх.
- **Частковий відкат більше не губить кроки.** Те, що не вдалося повернути, лишається в журналі з позначкою — відкат можна повторити або скористатися OptimaX-Rescue.cmd.
- **Конфлікти.** Зміни, що перезаписують одна одну (наприклад, «Агресивний Turbo» і «Тихий режим»), ніколи не застосовуються разом: в експертному меню друга вимикається, у перегляді — позначається, а в пакеті пропускається з поясненням.
- **Права адміністратора** перевіряються для кожної зміни: без них системні параметри пропускаються з поясненням, а не ламаються на півдорозі.
- **Безпечне оновлення.** Завантажене оновлення запускається лише після перевірки SHA-256 (сума з GitHub і `SHA256SUMS.txt` релізу — мусять збігатися) і цифрового підпису Windows. Пошкоджений або чужий підпис — ніколи; підписана OptimaX приймає лише оновлення того самого видавця. Файл лежить у папці, куди звичайні програми не можуть писати, і перевіряється ще раз безпосередньо перед запуском. PresentMon перевіряється так само.

### Точні заміри

- **Тест FPS: 3 або 5 прогонів** поспіль, медіана (один невдалий прогін її не зсуне), явно невдалий прогін відкидається. Видно розкид між прогонами, 0.1% low, фризи за хвилину й плавність кадрів.
- **Порівняння «до/після» з похибкою.** Для FPS, 1% і 0.1% low показано зміну ± похибку вимірювання (95%, з урахуванням кількості прогонів). «Приріст підтверджено» — лише коли зміна більша за похибку, інакше «різниці немає».
- **Розумна оптимізація:** по 3 заміри до і після, медіана, 0.1% low; у результаті — похибка й чи перевищує її приріст. Якщо доведеного приросту немає, одна кнопка прибирає зміни продуктивності без ефекту.

### Діагностика й режими

- **Що обмежує продуктивність.** «Чому лагає?» класифікує кожну секунду (процесор, відеокарта, пам'ять, диск, перегрів, ліміт живлення) і називає головне обмеження з часткою часу та порадою. Тест FPS у грі визначає це автоматично, паралельно із записом кадрів.
- **Режими оптимізації:** «Безпечний», «Ігровий», «Слабкий ПК», «Ручний» — нова вкладка на сторінці «Оптимізація». План складається під конкретний ПК: залізо, головне обмеження (наприклад, на ПК, що впирається у відеокарту, твіки процесора не застосовуються, а на перегрітому — нічого, що гріє) і результати розумної оптимізації (шкідливе на цьому ПК не пропонується ніколи). Для кожної виключеної зміни видно причину. «Ігровий» і «Слабкий ПК» за замовчуванням перевіряють результат замірами.

### Перевірки

- Нові автотести: аварія посеред оптимізації й пакета, помилка посеред пункту, незаписуваний і пошкоджений журнал, частковий відкат, знімок початкових налаштувань, конфлікти, права адміністратора (на фальшивій Windows); підміна оновлення до й після завантаження, розбіжні суми, політика підпису, WinVerifyTrust на справжній Windows; статистика FPS (хибне «краще/гірше» на чистому шумі — не частіше ~5% у кожен бік); режими й визначення обмеження. Самоперевірка `--selftest` зібраного exe перевіряє журнал, перевірку файлів, режими й похибку FPS.

<details>
<summary>English</summary>

OptimaX doesn't just change Windows — it proves that every optimization actually helps, and rolls everything back even more reliably. **Safety and rollback:** the rollback record now reaches the disk *before* the system changes; if OptimaX crashes in the middle of a change (a crash, a blue screen, a power cut), it reverts what had already changed on the next start and offers to roll back the unfinished batch (some changes used to stay in the system without a record). An item is applied entirely or not at all: if an error hits in the middle (no access to a registry key and so on), what that item had already changed is reverted at once and the batch goes on. The journal keeps a backup copy; a damaged file is set aside and the journal is restored from the copy (a damaged journal used to be silently replaced by an empty one). If the journal can't be written (disk full, antivirus), OptimaX stops and changes nothing. Before its first change OptimaX records every setting it may change, so even if the journal is lost, Backups → Original Windows settings finds OptimaX changes without a record and reverts them. A partial rollback no longer loses steps: what couldn't be reverted stays in the journal, marked, to retry or to revert with OptimaX-Rescue.cmd. Conflicting changes (such as Aggressive Turbo and Cool mode) are never applied together. Administrator rights are checked per change. Updates run only after a SHA-256 check (the GitHub digest and the release's `SHA256SUMS.txt` must agree) and a Windows digital signature check; a broken or foreign signature is never accepted, and a signed OptimaX only accepts updates from the same publisher; the file is stored where regular apps can't write and re-checked right before launch; PresentMon is checked the same way. **Precise measurements:** the FPS test does 3 or 5 runs and takes the median, drops an obviously bad run, and shows the run-to-run spread, 0.1% lows, stutters per minute and frame pacing; before/after shows each change ± the measurement error (95%, depending on the number of runs) and only calls it a confirmed gain when it exceeds the error; smart optimization measures 3 times before and after, uses medians and 0.1% lows, shows the error, and offers to remove performance changes with no proven effect. **Diagnosis and modes:** “Why does it lag?” classifies every second (CPU, GPU, memory, drive, overheating, power limit) and names the main limit with its share of time and advice; the in-game FPS test detects it automatically while recording frames. New Safe, Gaming, Low-end PC and Manual modes build the plan for your PC: hardware, the main limit (CPU tweaks are skipped on a GPU-bound PC, nothing that adds heat on an overheating one) and smart-optimization results (what hurt this PC is never offered); every left-out change shows why. **Checks:** new automated tests cover crashes and errors mid-change, unwritable and damaged journals, partial rollback, the settings snapshot, conflicts, admin rights, update tampering, checksum and signature policy, WinVerifyTrust on real Windows, FPS statistics (false better/worse on pure noise stays at ~5% each way), modes and bottleneck detection; `--selftest` of the built exe checks them too.

</details>

## [6.3.5] — 2026-10-25

### Виправлено

- **Залізо більше не показується як «Не визначено».** Раніше всі характеристики збиралися одним великим запитом PowerShell: якщо служба дисків Windows відповідала довго (часто на ПК з HDD чи USB-дисками), антивірус або політика компанії обмежували PowerShell чи WMI, увесь запит не вдавався — і процесор, пам'ять, відеокарта й диск ставали «Не визначено». Тепер запити розділено й виконуються одночасно, а все головне OptimaX додатково читає напряму з Windows — з таблиць SMBIOS, реєстру й драйверів пристроїв — без PowerShell.
- **Правильні цифри заліза:**
  - частота процесора підписана як базова: Windows повідомляє саме її, а не частоту прискорення, тож «до 3,40 ГГц» для процесора з турбо 5,4 ГГц вводило в оману;
  - на ПК із двома процесорами (Xeon на платах X99 тощо) ядра й потоки рахуються для обох, а не лише для першого;
  - тип пам'яті визначається для LPDDR4/LPDDR5 і DDR2 (раніше поле лишалося порожнім, а частина кодів SMBIOS розпізнавалася неправильно);
  - частота пам'яті на старих BIOS більше не показується вдвічі меншою (1600 замість 3200 МГц) — і перевірка збірки не радить увімкнути XMP, який уже ввімкнено;
  - обсяг відеопам'яті береться з драйвера саме цієї відеокарти, а не обрізається до 4 ГБ; невеликий обсяг показується в МБ, а не як «0 ГБ»;
  - тип системного диска (SSD чи HDD) визначається, навіть коли Windows його не повідомляє; шина показується назвою (SATA, NVMe, USB), а не числом; невідомий стан диска більше не вважається несправністю;
  - назва Windows без «Майкрософт», а замість «To be filled by O.E.M.» — виробник материнської плати;
  - коли щось справді не вдалося визначити, програма не показує «0 ГБ», «? МГц» чи «модулів: 0» і не робить за такими даними висновків у перевірці збірки.
- **Повідомлення про нову версію знову з'являється.**
  - Перевірка оновлень більше не чекає на аналіз заліза (якщо аналіз не вдавався, вона не відбувалася зовсім) і виконується під час запуску та кожні 6 годин, а не раз на 20 годин — програма часто тижнями працює в треї.
  - Невдала перевірка (немає інтернету) більше не відкладає наступну на 20 годин, а ручна перевірка в такому разі не пише «У вас найновіша версія».
  - Знайдена версія запам'ятовується: після перезапуску банер не зникає.
  - Про нову версію сповіщає спливаюче повідомлення — у вікні або в треї (натискання відкриває OptimaX), а в бічному меню на кожній сторінці з'являється кнопка «Оновити до …», навіть коли головну сторінку займає інший банер.
  - Кнопка «Пропустити» стала «Пізніше» й ховає повідомлення на добу, а не назавжди.
  - Якщо GitHub API недоступний (ліміт запитів на спільну IP-адресу провайдера) або Python не довіряє сертифікату, OptimaX перевіряє сторінку релізу напряму чи через системний завантажувач Windows; так само докачується й саме оновлення.

<details>
<summary>English</summary>

**Fixed: hardware no longer shows up as “Unknown”.** All specs used to come from one big PowerShell query: if the Windows storage service was slow to answer (common on PCs with HDDs or USB drives), or an antivirus or company policy restricted PowerShell or WMI, the whole query failed and the CPU, memory, graphics card and drive all became “Unknown”. The queries are now split and run in parallel, and OptimaX also reads everything important straight from Windows — SMBIOS tables, the registry and device drivers — without PowerShell. **Correct hardware numbers:** the CPU clock is labelled as the base clock (that's what Windows reports, so “up to 3.40 GHz” for a CPU that boosts to 5.4 GHz was misleading); dual-CPU systems (X99 Xeon boards and the like) count cores and threads of both CPUs; LPDDR4/LPDDR5 and DDR2 memory types are recognised (the field used to be empty, and some SMBIOS codes were mapped wrong); memory speed on older BIOSes is no longer shown at half (1600 instead of 3200 MHz), so the build check no longer suggests enabling XMP that is already on; VRAM comes from that graphics card's own driver instead of being capped at 4 GB, and small amounts show in MB rather than “0 GB”; the system drive type (SSD or HDD) is detected even when Windows doesn't report it, the bus is shown by name (SATA, NVMe, USB) instead of a number, and an unknown drive health is no longer treated as a fault; the Windows name drops the localised “Microsoft”, and “To be filled by O.E.M.” is replaced by the motherboard maker; when something really can't be detected, the app no longer shows “0 GB”, “? MHz” or “0 modules” or draws build-check conclusions from it. **The new version notice shows up again:** the update check no longer waits for the hardware analysis (if that failed, the check never ran) and runs at startup and every 6 hours instead of once per 20 hours, since the app often lives in the tray for weeks; a failed check (no internet) no longer postpones the next one by 20 hours, and a manual check no longer says “You have the latest version” when it failed; a found version is remembered, so the banner survives a restart; a pop-up notice appears in the window or the tray (clicking it opens OptimaX), and an “Update to …” button shows in the sidebar on every page even when another banner occupies the home page; “Skip” is now “Later” and hides the notice for a day instead of forever; when the GitHub API is unavailable (the request limit of a shared ISP address) or Python doesn't trust the certificate, OptimaX checks the release page directly or through the Windows downloader, and downloads the update itself the same way.

</details>

## [6.3.4] — 2026-10-22

Перша версія, у якій повна перевірка на справжній Windows (Server 2022 і 2025) проходить від початку до кінця: кожна оптимізація застосовується, перевіряється й відкочується поодинці і пакетом — через журнал програми та через `OptimaX-Rescue.cmd` — і система щоразу повертається точно в початковий стан.

### Виправлено

- **Відкат «Вимкнути гібернацію» більше не вмикає гібернацію, якщо до OptimaX вона була вимкнена.** Раніше після відкату на диску несподівано з'являвся файл hiberfil.sys на кілька гігабайтів, а на ПК без підтримки гібернації відкат завершувався помилкою.
- **Оптимізації NTFS** (оновлення часу доступу, короткі імена 8.3) тепер відкочуються до вашого точного початкового значення, а не до стандартного.
- **`OptimaX-Rescue.cmd`** записує кожен крок, який не вдалося повернути, у `failed.txt` поруч із собою: після аварійного відкату (зокрема в безпечному режимі) видно, що саме не повернулося.

<details>
<summary>English</summary>

The first version whose full check on real Windows (Server 2022 and 2025) runs from start to finish: every tweak is applied, verified and rolled back on its own and as a batch — via the program's journal and via `OptimaX-Rescue.cmd` — and the system returns exactly to its original state each time. **Fixed:** rolling back “Turn off hibernation” no longer turns hibernation on when it was off before OptimaX (a multi-GB hiberfil.sys used to appear after rollback, and on PCs without hibernation support the rollback failed). The NTFS tweaks (last access updates, 8.3 short names) now roll back to your exact original value instead of the default. `OptimaX-Rescue.cmd` writes every step it couldn't restore to `failed.txt` next to itself, so after an emergency rollback (including in Safe Mode) you can see what didn't go back.

</details>

## [6.3.3] — 2026-10-21

### Виправлено

- **Застосування змін могло «висіти» 20–40 хвилин на останньому кроці.** «Глибоке очищення сміття» запускало `DISM /StartComponentCleanup`, яке на ноутбуках із HDD триває до години, а обмеження часу для команд на Windows не спрацьовувало: програма чекала, доки DISM та його дочірні процеси закінчать самі. Кнопка «Зупинити» теж не могла їх перервати.
- Тепер довгі команди справді зупиняються після тайм-ауту або кнопкою «Зупинити» — разом з усіма дочірніми процесами.
- «Глибоке очищення сміття» займає до хвилини: кеш оновлень Windows, Edge і тимчасові файли. Прибирання старих копій оновлень (WinSxS) — окрема дія «Прибрати старі копії оновлень» у розділі «Очищення», з прогресом і кнопкою «Зупинити». Очищення більше не відкриває вікно Microsoft Store (wsreset) і не видаляє Prefetch, за яким Windows швидше запускає програми.

<details>
<summary>English</summary>

**Fixed:** applying changes could sit on the last step for 20–40 minutes. “Deep junk cleanup” ran `DISM /StartComponentCleanup`, which takes up to an hour on laptops with an HDD, and command timeouts didn't work on Windows: the program waited until DISM and its child processes finished by themselves, and Stop couldn't interrupt them. Long commands now really stop on timeout or Stop, together with all their child processes. Deep junk cleanup takes up to a minute (Windows Update and Edge caches, temporary files); removing old update copies (WinSxS) is a separate “Remove old update copies” action under Cleanup, with progress and Stop. The cleanup no longer opens the Microsoft Store window (wsreset) and no longer deletes Prefetch, which Windows uses to start programs faster.

</details>

## [6.3.2] — 2026-10-21

Перевірка безпеки всього каталогу оптимізацій. Готові профілі й майстер більше не роблять нічого, що важко відкотити або що ламає звичні речі.

### Виправлено

- **Майстер і профіль «Full» більше не вимикають Windows Defender і не видаляють OneDrive.** Зі стороннім антивірусом Defender і так сам переходить у пасивний режим, а вимкнений політикою лишив би ПК без захисту, якщо той антивірус видалити. Видалення OneDrive робило недоступними файли, які зберігаються лише в хмарі. Обидва пункти лишилися в експертному меню з червоним попередженням.
- **«Скинути DNS і Winsock» прибрано з усіх профілів:** `netsh int ip reset` стирає статичну IP-адресу, ручні DNS і ламає частину VPN. Тепер лише вручну.
- **Оптимізація файлу підкачки більше не вмикає його очищення під час кожного вимкнення** — через це вимкнення й перезавантаження ставали повільними.
- **MSI Mode** показує лише відеокарти, мережу й звук. Контролери дисків (SATA, NVMe) і USB прибрано: змінений режим переривань на них міг зробити Windows такою, що не завантажується, або вимкнути USB-клавіатуру й мишу.
- **Ноутбуки:** блокування схеми живлення на ноутбуках не застосовується (заважало економії батареї); профіль «Ноутбук» більше не вимикає прискорення вказівника (тачпад ставав незручним); завдання, яке налаштовує мобільний інтернет LTE, більше не вимикається.
- Примусовий HPET прибрано з профілю «Full»: на сучасних ПК він зазвичай знижує FPS.
- Мережеві оптимізації більше не викликають команди `chimney` і `netdma`, яких у Windows 10 і 11 уже немає.
- **Після відновлення системи** сторож налаштувань більше не пропонує першим ділом «Застосувати знову»: якщо не діє більшість змін, він пояснює, що це схоже на відновлення системи, і пропонує забути ці записи журналу, не чіпаючи систему.
- **Автоматичне виправлення:** якщо раніше застосували очищення файлу підкачки або вимкнення завдання LTE, OptimaX під час запуску повертає їх до ваших початкових значень (разом зі службами з 6.3.1).

<details>
<summary>English</summary>

A safety review of the whole tweak catalogue: ready-made profiles and the wizard no longer do anything that is hard to roll back or breaks everyday things. **Fixed:** the wizard and the Full profile no longer turn off Windows Defender or remove OneDrive (with another antivirus Defender goes passive by itself; a policy-disabled Defender would leave the PC unprotected if that antivirus is removed; removing OneDrive made cloud-only files unavailable) — both stay in the expert menu with a red warning. “Reset DNS and Winsock” is no longer in any profile: `netsh int ip reset` wipes static IP and manual DNS settings and breaks some VPNs. The page file optimization no longer clears the page file at every shutdown, which made shutdowns and restarts slow. MSI Mode lists only graphics, network and audio devices: storage (SATA, NVMe) and USB controllers are gone, since a changed interrupt mode there could leave Windows unbootable or disable USB keyboards and mice. Laptops: the power plan lock no longer applies (it got in the way of battery saver), the Laptop profile no longer turns off pointer acceleration (it made touchpads awkward), and the LTE provisioning task is no longer disabled. Forced HPET is out of the Full profile, as it usually lowers FPS on modern PCs. Network tweaks no longer call the `chimney` and `netdma` options that Windows 10 and 11 no longer have. After a System Restore the settings guard no longer leads with “Re-apply”: when most changes are no longer in effect it explains this looks like a restore and offers to forget those journal records without touching the system. If you applied page file clearing or the LTE task change earlier, OptimaX restores your original values on start (together with the 6.3.1 service fix).

</details>

## [6.3.1] — 2026-10-21

### Виправлено

- **Клавіатура, клавіші Fn або тачпад могли перестати працювати на ноутбуках** після оптимізації «Вимкнути зайві служби». У 6.3 вона переводила в ручний запуск *усі* служби з автозапуском, які не працювали в мить застосування, — серед них бувають службові програми виробника ноутбука. Тепер оптимізація вимикає лише фіксований список служб Windows (телеметрія, звіти про помилки, факс, демо-режим, офлайн-карти, віддалений реєстр, геолокація, гаманець тощо).
- **Автоматичне виправлення:** якщо цю оптимізацію застосували у 6.3, OptimaX 6.3.1 під час першого запуску сам повертає зачепленим службам їхній початковий тип запуску з журналу змін і просить перезавантажити ПК. Решта ваших оптимізацій лишається.
- Оптимізація більше не вимикає «Спільний доступ до інтернету» (SharedAccess): без нього не працює мобільна точка доступу.

<details>
<summary>English</summary>

**Fixed:** the keyboard, Fn keys or touchpad could stop working on laptops after the “Turn off unneeded services” optimization. In 6.3 it switched *every* automatic service that wasn't running at that moment to manual start, which can include laptop maker services. It now turns off only a fixed list of Windows services (telemetry, error reporting, fax, retail demo, offline maps, remote registry, location, wallet and so on). If you applied it in 6.3, OptimaX 6.3.1 restores the original start type of the affected services from the change journal on first start and asks you to restart; your other optimizations stay. The optimization no longer turns off Internet Connection Sharing (SharedAccess), which Mobile hotspot needs.

</details>

## [6.3] — 2026-10-21

### Нове

- **Розумна оптимізація.** Заміри FPS до і після (GPU-тест OptimaX або ваша гра через PresentMon); залишається лише те, що допомогло, а шкідливу зміну програма знаходить половинним поділом і прибирає. Режим «Перевірити мої зміни» для вже застосованого. Продовжує роботу після перезавантаження.
- **Аварійний відкат.** Після змін OptimaX три дні стежить за синіми екранами, аварійними перезавантаженнями й збоями відеодрайвера і пропонує відкотити саме останній пакет.
- **OptimaX-Rescue.cmd** повертає зміни без програми, також із безпечного режиму; ярлик «OptimaX — аварійний відкат» у меню «Пуск». Без меню: `/last` або `/all`.
- **Картка результату** для соцмереж і форумів: FPS до/після, завантаження, процеси, пам'ять, служби, пінг, заблокована реклама.
- **Самоперевірка** `--selftest` / `--selftest-ui` — для зібраного exe і CI.
- **CI на справжній Windows:** кожен твік застосовується, перевіряється й відкочується на Windows Server 2022 і 2025; збірка інсталятора й портативної версії, тихе встановлення й видалення; реліз за тегом.

### Виправлено

- Відкат кількох змін, застосованих у ту саму секунду, тепер завжди йде від новішої до старішої: значення, яке змінили два твіки, повертається до початкового, а не до проміжного. Стосувалося відкату з журналу, пробного режиму, «змін між тестами FPS» і Rescue-файлу.
- Rescue-файл більше не рахує збоєм видалення, яке не знайшло що видаляти.
- Запускач Rescue повертає правильний код виходу.
- Попередній перегляд картки результату показує всю картку.
- Звіт для форуму показує лише ім'я файлу гри, без шляху з іменем користувача Windows.
- Зібрана програма падала одразу після запуску (код 0xC000041D) — через реєстрацію гарячих клавіш на вікні. Тепер клавіші працюють в окремому потоці.
- Інсталятор відмовлявся ставитися на Windows 10 старші за 1903. Тепер підходить будь-яка 64-бітна Windows 10 і 11; на збірках, старших за 1809, інсталятор попереджає й дає вибір. Збірка тепер бере PyQt6 не новіший за 6.12: Qt 6.13+ уже не працює на Windows 10. Параметри, яких немає у вашій збірці Windows (планування GPU і вимкнення зарезервованого сховища — з 2004, схема «Максимальна продуктивність» — з 1803), позначаються недоступними.

<details>
<summary>English</summary>

**New:** smart optimization (before/after FPS measurements, keeps what helps, finds a harmful change by halving, resumes after a restart, “Check my changes”); emergency rollback with crash watch for three days after changes; OptimaX-Rescue.cmd that rolls back without the program, also from Safe Mode, plus a Start menu shortcut and `/last` / `/all` switches; a result card for social networks; `--selftest` / `--selftest-ui`; CI that applies, verifies and rolls back every tweak on Windows Server 2022 and 2025, builds the installer and portable version, tests silent install/uninstall and publishes releases from tags.

**Fixed:** rolling back several changes applied within the same second now always goes newest to oldest, so a value changed by two tweaks returns to its original state (journal rollback, trial mode, “changes between FPS tests” and the Rescue file); the Rescue file no longer counts a delete that found nothing to delete as a failure; the Rescue launcher returns the right exit code; the result card preview shows the whole card; the forum report shows only the game's file name, without a path containing the Windows user name. The built program no longer crashes right after start (0xC000041D, hotkey registration on the window; hotkeys now run in their own thread). The installer no longer refuses Windows 10 older than 1903: any 64-bit Windows 10 or 11 is accepted, builds older than 1809 get a warning and a choice, and settings your Windows build doesn't have (GPU scheduling and turning off reserved storage need 2004, the Ultimate Performance plan needs 1803) are shown as unavailable.

</details>

## 6.2

### Нове

- **GPU-тест OptimaX** — власна 3D-сцена з балами, 1% low і порівнянням «до/після» (1080p, 1440p, 4K) та **стрес-тест** 5–60 хв із покадровою перевіркою стабільності й датчиками.
- Інші бенчмарки в один клік: FurMark 2 з автоматичним результатом, Unigine Superposition, Cinebench R23, OCCT, CrystalDiskMark, 3DMark.
- **Блок реклами як Pi-hole:** власний DNS-фільтр на ПК зі статистикою, журналом запитів, 13 списками, DNS-over-HTTPS і захистом домашньої мережі; **легкий режим** — AdGuard DNS чи Control D в один клік.

<details>
<summary>English</summary>

**New:** the OptimaX GPU test (own 3D scene, score, 1% low, before/after at 1080p, 1440p, 4K) and a 5–60 minute stress test with frame-exact stability checks and sensors; one-click third-party benchmarks (FurMark 2 with an automatic result, Unigine Superposition, Cinebench R23, OCCT, CrystalDiskMark, 3DMark); a Pi-hole-style ad blocker on the PC with statistics, query log, 13 lists, DNS-over-HTTPS and home network protection, plus a light mode with AdGuard DNS or Control D.

</details>

## 6.1

### Нове

- Повноцінна програма для Windows: **інсталятор** (Inno Setup) українською, російською й англійською, меню «Пуск», запис у «Програмах», автозапуск у трей.
- **Видалення** з вибором: повернути всі зміни чи залишити; прибирання задач планувальника.
- Одна копія програми, **оновлення** з GitHub Releases, портативна версія, підпис коду, маніфести winget.

<details>
<summary>English</summary>

**New:** a full Windows app: an installer (Inno Setup) in Ukrainian, Russian and English, Start menu, Apps entry, autostart to the tray; uninstall with a choice to roll back all changes or keep them, and cleanup of scheduled tasks; single instance, updates from GitHub Releases, a portable version, code signing, winget manifests.

</details>

## 6.0

### Нове

- Велике оновлення каталогу: 46 нових оптимізацій і функцій.

<details>
<summary>English</summary>

**New:** a big catalogue update with 46 new optimizations and features.

</details>

[6.8]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.8
[6.7]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.7
[6.6]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.6
[6.5]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.5
[6.4.3]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.4.3
[6.4.2]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.4.2
[6.4.1]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.4.1
[6.4]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.4
[6.3.5]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.5
[6.3.4]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.4
[6.3.3]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.3
[6.3.2]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.2
[6.3.1]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.1
[6.3]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3
