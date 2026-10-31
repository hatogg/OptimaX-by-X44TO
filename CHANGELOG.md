# Історія змін · Changelog

Формат — за [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/), версії — `VERSION` в `engine.py`.

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
