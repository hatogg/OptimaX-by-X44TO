# Історія змін · Changelog

Формат — за [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/), версії — `VERSION` в `engine.py`.

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

[6.3.4]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.4
[6.3.3]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.3
[6.3.2]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.2
[6.3.1]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3.1
[6.3]: https://github.com/hatogg/OptimaX-by-X44TO/releases/tag/v6.3
