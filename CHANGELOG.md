# Історія змін · Changelog

Формат — за [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/), версії — `VERSION` в `engine.py`.

## [Unreleased]

### Змінено

- Підказка «Як грати на майнінговій карті» більше не каже, що FPS обмежений частотою вбудованої графіки, і не радить обмежувати його через RTSS.

### Виправлено

- **GPU-тест на весь екран більше не впирається в 60 FPS.** Повноекранне вікно тесту Windows виводила в обхід композиції, і драйвер синхронізував кадри з частотою монітора, хоч тест і вимикає вертикальну синхронізацію: у вікні було 100+ FPS, на весь екран — рівно 60. Тепер вікно лишається під композицією (рамка в 1 px, як радить Qt), і на весь екран FPS такий самий, як у вікні.
- **Без паузи між кадрами.** Qt чекав 5 мс перед кожним наступним кадром (а таймер Windows міг ще й подовжити цю паузу), тож потужні відеокарти не розкривалися навіть у вікні. Тепер новий кадр починається одразу.
- Бали виправленого тесту не порівнюються зі старими замірами — ні в історії, ні в картці «було → стало», щоб виправлення тесту не виглядало як приріст від оптимізації. Перший замір після оновлення стає новою точкою відліку.

<details>
<summary>English</summary>

**The fullscreen GPU test is no longer capped at 60 FPS.** Windows presented the fullscreen test window bypassing composition, and the driver synced frames to the monitor refresh rate even though the test turns vsync off: 100+ FPS in a window, exactly 60 in fullscreen. The window now stays composited (a 1 px border, as Qt recommends), so fullscreen FPS matches windowed. Qt also waited 5 ms before every next frame (which the Windows timer could stretch further), holding back fast GPUs even in a window; the next frame now starts right away. Scores of the fixed test are not compared with older runs, neither in the history nor on the before/after card, so the fix does not look like an optimization gain; the first run after the update is the new baseline. The “How to game on a mining card” tip no longer says FPS is capped by the integrated graphics refresh rate or suggests capping it with RTSS.

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

[6.4.1]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.4.1
[6.4]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.4
[6.3.5]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.5
[6.3.4]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.4
[6.3.3]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.3
[6.3.2]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.2
[6.3.1]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.1
[6.3]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3
