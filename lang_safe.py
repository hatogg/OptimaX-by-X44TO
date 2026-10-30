"""OptimaX — переклади: аварійний відкат, розумна оптимізація, картка результату."""

STRINGS = {
    # ── аварійний відкат ──
    "rs.title": ("Аварійний відкат", "Аварийный откат", "Emergency rollback"),
    "rs.card_d": ("Якщо після змін ПК почне падати чи зависати, OptimaX помітить це за журналом подій Windows і "
                  "запропонує відкотити останні зміни. А файл OptimaX-Rescue.cmd поверне все навіть із безпечного "
                  "режиму — без запуску програми.",
                  "Если после изменений ПК начнёт падать или зависать, OptimaX заметит это по журналу событий Windows и "
                  "предложит откатить последние изменения. А файл OptimaX-Rescue.cmd вернёт всё даже из безопасного "
                  "режима — без запуска программы.",
                  "If the PC starts crashing or freezing after changes, OptimaX notices it in the Windows event log and "
                  "offers to roll back the latest changes. And OptimaX-Rescue.cmd reverts everything even from Safe "
                  "Mode, without starting the program."),
    "rs.state": ("У файлі змін: {n} (останній пакет — {last}) · оновлено {when}\n{path}",
                 "В файле изменений: {n} (последний пакет — {last}) · обновлён {when}\n{path}",
                 "Changes in the file: {n} (latest batch: {last}) · updated {when}\n{path}"),
    "rs.check": ("Перевірити збої", "Проверить сбои", "Check for crashes"),
    "rs.open": ("Показати файл", "Показать файл", "Show the file"),
    "rs.howto": ("Як користуватися", "Как пользоваться", "How to use it"),
    "rs.howto_t": ("Аварійний відкат без програми", "Аварийный откат без программы", "Rollback without the program"),
    "rs.howto_d": ("Якщо Windows не завантажується нормально:\n\n"
                   "1. Тричі перервіть завантаження або натисніть «Перезавантажити» з затиснутим Shift.\n"
                   "2. «Пошук і усунення несправностей» → «Додаткові параметри» → «Параметри завантаження» → "
                   "«Перезавантажити» → 4 (безпечний режим).\n"
                   "3. Відкрийте C:\\ProgramData\\OptimaX\\rescue\\OptimaX-Rescue.cmd (або «OptimaX — аварійний "
                   "відкат» у меню «Пуск») і виберіть 1 — останні зміни, або 2 — усі.\n"
                   "4. Перезавантажте ПК.\n\n"
                   "Якщо не запускається навіть безпечний режим — «Додаткові параметри» → «Відновлення системи» і точка "
                   "відновлення, яку OptimaX створює перед змінами.",
                   "Если Windows не загружается нормально:\n\n"
                   "1. Трижды прервите загрузку или нажмите «Перезагрузка» с зажатым Shift.\n"
                   "2. «Поиск и устранение неисправностей» → «Дополнительные параметры» → «Параметры загрузки» → "
                   "«Перезагрузить» → 4 (безопасный режим).\n"
                   "3. Откройте C:\\ProgramData\\OptimaX\\rescue\\OptimaX-Rescue.cmd (или «OptimaX — аварийный откат» "
                   "в меню «Пуск») и выберите 1 — последние изменения, или 2 — все.\n"
                   "4. Перезагрузите ПК.\n\n"
                   "Если не запускается даже безопасный режим — «Дополнительные параметры» → «Восстановление системы» "
                   "и точка восстановления, которую OptimaX создаёт перед изменениями.",
                   "If Windows doesn't start normally:\n\n"
                   "1. Interrupt the boot three times, or hold Shift and click Restart.\n"
                   "2. Troubleshoot → Advanced options → Startup Settings → Restart → 4 (Safe Mode).\n"
                   "3. Open C:\\ProgramData\\OptimaX\\rescue\\OptimaX-Rescue.cmd (or \"OptimaX — Emergency rollback\" in "
                   "the Start menu) and choose 1 for the latest changes or 2 for all of them.\n"
                   "4. Restart the PC.\n\n"
                   "If even Safe Mode doesn't start, use Advanced options → System Restore with the restore point "
                   "OptimaX creates before applying changes."),
    "rs.banner_t": ("Після змін {when} комп'ютер аварійно перезавантажився", "После изменений {when} компьютер "
                    "аварийно перезагрузился", "The PC crashed after the changes made on {when}"),
    "rs.banner_d": ("У журналі Windows: {what}. Якщо раніше все працювало стабільно, причиною можуть бути нові "
                    "налаштування — їх можна відкотити одним кліком.",
                    "В журнале Windows: {what}. Если раньше всё работало стабильно, причиной могут быть новые настройки "
                    "— их можно откатить одним кликом.",
                    "The Windows log shows: {what}. If everything was stable before, the new settings may be the cause — "
                    "you can roll them back in one click."),
    "rs.revert": ("Відкотити ці зміни ({n})", "Откатить эти изменения ({n})", "Roll back these changes ({n})"),
    "rs.not_us": ("Це не через OptimaX", "Это не из-за OptimaX", "It wasn't OptimaX"),
    "rs.ask_t": ("Схоже, ПК став нестабільним", "Похоже, ПК стал нестабильным", "The PC seems unstable"),
    "rs.ask_d": ("Після змін OptimaX ({when}) Windows зафіксувала: {what}.\n\nВідкотити ці {n} змін до ваших початкових "
                 "значень? Якщо збій стався через інше (вимкнули світло, нова гра чи драйвер), натисніть «Скасувати».",
                 "После изменений OptimaX ({when}) Windows зафиксировала: {what}.\n\nОткатить эти {n} изменений к вашим "
                 "исходным значениям? Если сбой случился по другой причине (отключили свет, новая игра или драйвер), "
                 "нажмите «Отмена».",
                 "After the OptimaX changes ({when}) Windows recorded: {what}.\n\nRoll back these {n} changes to your "
                 "original values? If the crash had another cause (power cut, a new game or driver), press Cancel."),
    "rs.kind.bsod": ("синій екран", "синий экран", "a blue screen"),
    "rs.kind.power": ("аварійне перезавантаження чи зникнення живлення", "аварийная перезагрузка или пропадание "
                      "питания", "an unexpected restart or power loss"),
    "rs.kind.shutdown": ("вимкнення без завершення роботи", "выключение без завершения работы",
                         "a shutdown without closing Windows"),
    "rs.kind.gpu": ("перезапуск відеодрайвера", "перезапуск видеодрайвера", "a graphics driver reset"),
    "rs.synced": ("Аварійний файл уже повернув змін: {n} — журнал оновлено", "Аварийный файл уже вернул изменений: {n} "
                  "— журнал обновлён", "The rescue file already rolled back {n} changes — the journal is updated"),
    "rs.found": ("Після останніх змін були збої — див. банер на головній", "После последних изменений были сбои — см. "
                 "баннер на главной", "There were crashes after the latest changes — see the banner on the home page"),
    "rs.clean": ("Збоїв після останніх змін не знайдено", "Сбоев после последних изменений не найдено",
                 "No crashes after the latest changes"),
    "rs.dismissed": ("Добре, зміни залишаються", "Хорошо, изменения остаются", "OK, the changes stay"),
    "rs.cmd_admin": ("Потрібні права адміністратора — зараз Windows їх попросить.",
                     "Нужны права администратора — сейчас Windows их запросит.",
                     "Administrator rights are needed — Windows will ask for them now."),
    "rs.cmd_title": ("аварійний відкат змін", "аварийный откат изменений", "emergency rollback"),
    "rs.cmd_state": ("Змін у журналі: {n}. Останній пакет: {last} змін від {when}.",
                     "Изменений в журнале: {n}. Последний пакет: {last} изменений от {when}.",
                     "Changes in the journal: {n}. Latest batch: {last} changes from {when}."),
    "rs.cmd_nothing": ("Повертати нічого — змін OptimaX немає.", "Возвращать нечего — изменений OptimaX нет.",
                       "Nothing to roll back — there are no OptimaX changes."),
    "rs.cmd_last": ("повернути останній пакет змін: {n}", "вернуть последний пакет изменений: {n}",
                    "roll back the latest batch: {n}"),
    "rs.cmd_all": ("повернути ВСІ зміни OptimaX: {n}", "вернуть ВСЕ изменения OptimaX: {n}",
                   "roll back ALL OptimaX changes: {n}"),
    "rs.cmd_exit": ("вийти без змін", "выйти без изменений", "exit without changes"),
    "rs.cmd_done": ("Готово.", "Готово.", "Done."),
    "rs.cmd_fail": ("Частину команд не вдалося виконати — це нормально в безпечному режимі.",
                    "Часть команд выполнить не удалось — это нормально в безопасном режиме.",
                    "Some commands failed — that's normal in Safe Mode."),
    "rs.cmd_reboot": ("Перезавантажте комп'ютер, щоб зміни повністю повернулися.",
                      "Перезагрузите компьютер, чтобы изменения полностью вернулись.",
                      "Restart the PC so the changes are fully restored."),
    "rs.shortcut": ("OptimaX — аварійний відкат", "OptimaX — аварийный откат", "OptimaX — Emergency rollback"),

    # ── розумна оптимізація ──
    "rv.smart": ("Розумна оптимізація — заміряти до і після", "Умная оптимизация — замерить до и после",
                 "Smart optimization — measure before and after"),
    "rv.smart_d": ("OptimaX заміряє FPS до змін, застосує їх і заміряє знову. Якщо щось погіршує роботу саме вашого ПК, "
                   "він знайде це й прибере, а решту залишить. Займає 3–8 хвилин.",
                   "OptimaX замерит FPS до изменений, применит их и замерит снова. Если что-то ухудшает работу именно "
                   "вашего ПК, он найдёт это и уберёт, а остальное оставит. Занимает 3–8 минут.",
                   "OptimaX measures FPS before the changes, applies them and measures again. If something makes your "
                   "PC slower, it finds and removes it and keeps the rest. Takes 3–8 minutes."),
    "sm.title": ("Розумна оптимізація", "Умная оптимизация", "Smart optimization"),
    "sm.card_d": ("Оптимізація з доказом: заміри до і після, і в системі лишаються тільки зміни, що не шкодять саме "
                  "вашому залізу.",
                  "Оптимизация с доказательством: замеры до и после, и в системе остаются только изменения, которые не "
                  "вредят именно вашему железу.",
                  "Optimization with proof: measurements before and after, and only changes that don't hurt your "
                  "hardware stay in the system."),
    "sm.card_s1": ("Три заміри до змін — медіана й звичайний розкид результатів, тобто похибка вимірювання.",
                   "Три замера до изменений — медиана и обычный разброс результатов, то есть погрешность измерения.",
                   "Three measurements before — the median and the normal run-to-run spread, i.e. the measurement "
                   "error."),
    "sm.card_s2": ("Застосування й замір після — з перезавантаженням, якщо потрібно.",
                   "Применение и замер после — с перезагрузкой, если нужно.",
                   "Apply and measure after — with a restart if needed."),
    "sm.card_s3": ("Стало гірше? Половину змін тимчасово відкочуємо й міряємо знову, поки не знайдемо винну.",
                   "Стало хуже? Половину изменений временно откатываем и меряем снова, пока не найдём виновную.",
                   "Got worse? Half of the changes are rolled back temporarily and measured again until the culprit is "
                   "found."),
    "sm.measure_by": ("Чим міряти", "Чем мерить", "Measure with"),
    "sm.by_gpu": ("GPU-тест OptimaX (сам)", "GPU-тест OptimaX (сам)", "OptimaX GPU test (automatic)"),
    "sm.by_game": ("Моя гра (PresentMon)", "Моя игра (PresentMon)", "My game (PresentMon)"),
    "sm.audit_btn": ("Перевірити мої зміни", "Проверить мои изменения", "Check my changes"),
    "sm.new_btn": ("Оптимізувати з замірами", "Оптимизировать с замерами", "Optimize with measurements"),
    "sm.audit_t": ("перевірка застосованих змін", "проверка применённых изменений", "checking applied changes"),
    "sm.audit_q": ("OptimaX тимчасово відкотить {n} уже застосованих змін продуктивності, двічі заміряє ПК без них, "
                   "поверне їх і заміряє знову. Так буде видно, чи вони справді допомагають, і що з них шкодить.",
                   "OptimaX временно откатит {n} уже применённых изменений производительности, дважды замерит ПК без них, "
                   "вернёт их и замерит снова. Так будет видно, помогают ли они на самом деле и что из них вредит.",
                   "OptimaX will temporarily roll back {n} applied performance changes, measure the PC twice without "
                   "them, re-apply them and measure again — to show whether they really help and which ones hurt."),
    "sm.audit_none": ("Немає застосованих змін продуктивності, які можна перевірити без перезавантаження",
                      "Нет применённых изменений производительности, которые можно проверить без перезагрузки",
                      "There are no applied performance changes that can be checked without a restart"),
    "sm.no_perf": ("У плані немає змін продуктивності — застосовую без замірів",
                   "В плане нет изменений производительности — применяю без замеров",
                   "The plan has no performance changes — applying without measurements"),
    "sm.never": ("Ще не запускалась. Найкраще — одразу після встановлення, до будь-яких змін.",
                 "Ещё не запускалась. Лучше всего — сразу после установки, до любых изменений.",
                 "Not run yet. Best right after installation, before any changes."),
    "sm.last": ("Остання: {when} · {res} · FPS {d}% · прибрано змін: {n}",
                "Последняя: {when} · {res} · FPS {d}% · убрано изменений: {n}",
                "Last run: {when} · {res} · FPS {d}% · changes removed: {n}"),
    "sm.how_gpu": ("Кожен замір — 30 секунд GPU-тесту OptimaX в окремому вікні. Не користуйтеся ПК під час замірів, "
                   "щоб результати були точними.",
                   "Каждый замер — 30 секунд GPU-теста OptimaX в отдельном окне. Не пользуйтесь ПК во время замеров, "
                   "чтобы результаты были точными.",
                   "Each measurement is 30 seconds of the OptimaX GPU test in its own window. Don't use the PC during "
                   "measurements so the results are accurate."),
    "sm.how_game": ("Кожен замір — {s} секунд вашої гри через PresentMon. Грайте в той самий спосіб і в тому самому "
                    "місці щоразу — тоді порівняння чесне.",
                    "Каждый замер — {s} секунд вашей игры через PresentMon. Играйте одинаково и в одном и том же месте "
                    "каждый раз — тогда сравнение честное.",
                    "Each measurement is {s} seconds of your game via PresentMon. Play the same way in the same spot "
                    "every time so the comparison is fair."),
    "sm.step.base": ("Замір до", "Замер до", "Before"),
    "sm.step.apply": ("Застосування", "Применение", "Apply"),
    "sm.step.after": ("Замір після", "Замер после", "After"),
    "sm.step.search": ("Пошук шкоди", "Поиск вреда", "Find harm"),
    "sm.step.done": ("Підсумок", "Итог", "Result"),
    "sm.m.base": ("Замір до змін ({n} з 3)", "Замер до изменений ({n} из 3)", "Measuring before changes ({n} of 3)"),
    "sm.m.after": ("Замір після змін ({n} з 3)", "Замер после изменений ({n} из 3)",
                   "Measuring after changes ({n} of 3)"),
    "sm.m.probe": ("Перевірка: частину змін тимчасово відкочено (замір {n})",
                   "Проверка: часть изменений временно откачена (замер {n})",
                   "Check: some changes are temporarily rolled back (measurement {n})"),
    "sm.m.check": ("Підтвердження: без підозрюваної зміни (замір {n})", "Подтверждение: без подозреваемого изменения "
                   "(замер {n})", "Confirming: without the suspected change (measurement {n})"),
    "sm.j.apply_apply": ("Застосовую зміни: {n}", "Применяю изменения: {n}", "Applying changes: {n}"),
    "sm.j.undo_audit": ("Тимчасово відкочую застосовані зміни: {n}", "Временно откатываю применённые изменения: {n}",
                        "Temporarily rolling back applied changes: {n}"),
    "sm.j.undo_probe": ("Тимчасово відкочую половину змін: {n}", "Временно откатываю половину изменений: {n}",
                        "Temporarily rolling back half of the changes: {n}"),
    "sm.j.apply_reapply": ("Повертаю тимчасово відкочені зміни: {n}", "Возвращаю временно откаченные изменения: {n}",
                           "Re-applying temporarily rolled-back changes: {n}"),
    "sm.j.undo_culprit": ("Відкочую підозрювану зміну", "Откатываю подозреваемое изменение",
                          "Rolling back the suspected change"),
    "sm.j.apply_restore": ("Повертаю зміну — підозра не підтвердилась", "Возвращаю изменение — подозрение не "
                           "подтвердилось", "Re-applying the change — the suspicion wasn't confirmed"),
    "sm.l.measured": ("  ✓ {avg} FPS · 1% low {low}", "  ✓ {avg} FPS · 1% low {low}", "  ✓ {avg} FPS · 1% low {low}"),
    "sm.ev_base": ("  · замір до №{n}: {avg} FPS", "  · замер до №{n}: {avg} FPS", "  · before #{n}: {avg} FPS"),
    "sm.ev_after": ("  · після змін: {avg} FPS ({d}%)", "  · после изменений: {avg} FPS ({d}%)", "  · after: {avg} FPS ({d}%)"),
    "sm.ev_applied": ("  · застосовано змін: {n}", "  · применено изменений: {n}", "  · changes applied: {n}"),
    "sm.ev_worse": ("  ⚠ стало гірше: FPS {avg}%, 1% low {low1}% — шукаю причину",
                    "  ⚠ стало хуже: FPS {avg}%, 1% low {low1}% — ищу причину",
                    "  ⚠ worse: FPS {avg}%, 1% low {low1}% — looking for the cause"),
    "sm.ev_probe_hit": ("  · без цих {n} змін стало краще — шукаю серед них", "  · без этих {n} изменений стало лучше — "
                        "ищу среди них", "  · better without these {n} changes — searching among them"),
    "sm.ev_probe_miss": ("  · ці {n} змін не винні", "  · эти {n} изменений не виноваты", "  · these {n} changes are fine"),
    "sm.ev_culprit": ("  ✗ шкодить вашому ПК: {title} — залишаю відкоченою", "  ✗ вредит вашему ПК: {title} — оставляю "
                      "откаченным", "  ✗ hurts your PC: {title} — keeping it rolled back"),
    "sm.ev_false": ("  · {title} — не винна, повертаю", "  · {title} — не виновато, возвращаю", "  · {title} isn't the cause, "
                    "re-applying"),
    "sm.ev_better": ("  ✓ підсумок: стало краще", "  ✓ итог: стало лучше", "  ✓ result: better"),
    "sm.ev_same": ("  ✓ підсумок: у межах похибки", "  ✓ итог: в пределах погрешности", "  ✓ result: within the margin"),
    "sm.ev_fixed": ("  ✓ підсумок: прибрано змін, що шкодили: {n}", "  ✓ итог: убрано вредных изменений: {n}",
                    "  ✓ result: harmful changes removed: {n}"),
    "sm.ev_unexplained": ("  ⚠ підсумок: стало гірше, але окрему винну зміну не знайдено",
                          "  ⚠ итог: стало хуже, но отдельное виновное изменение не найдено",
                          "  ⚠ result: worse, but no single culprit was found"),
    "sm.r.better.badge": ("краще", "лучше", "better"),
    "sm.r.same.badge": ("без змін", "без изменений", "no change"),
    "sm.r.fixed.badge": ("шкідливі прибрано", "вредные убраны", "harmful removed"),
    "sm.r.unexplained.badge": ("гірше", "хуже", "worse"),
    "sm.r.better.t": ("Стало швидше — усі зміни залишено", "Стало быстрее — все изменения оставлены",
                      "Faster — all changes kept"),
    "sm.r.same.t": ("FPS у межах похибки — зміни залишено", "FPS в пределах погрешности — изменения оставлены",
                    "FPS within the margin of error — changes kept"),
    "sm.r.fixed.t": ("Прибрано змін, що шкодили вашому ПК: {n}", "Убрано изменений, вредивших вашему ПК: {n}",
                     "Changes that hurt your PC removed: {n}"),
    "sm.r.unexplained.t": ("Стало гірше, але окрему причину не знайдено", "Стало хуже, но отдельную причину не нашли",
                           "Worse, but no single cause was found"),
    "sm.r.better.d": ("", "", ""),
    "sm.r.same.d": ("Для потужних ПК це нормально: зміни зменшують фонове навантаження й затримки, навіть коли FPS "
                    "майже не змінюється.",
                    "Для мощных ПК это нормально: изменения уменьшают фоновую нагрузку и задержки, даже когда FPS почти "
                    "не меняется.",
                    "That's normal for fast PCs: the changes reduce background load and latency even when FPS barely moves."),
    "sm.r.fixed.d": ("Решта змін залишилась. Їх і прибрані можна будь-коли повернути в «Резервних копіях».",
                     "Остальные изменения остались. Их и убранные можно в любой момент вернуть в «Резервных копиях».",
                     "The rest stay applied. Everything can be changed back any time in Backups."),
    "sm.r.unexplained.d": ("Можливо, винні кілька змін разом або зміни, що діють після перезавантаження. Можна відкотити "
                           "всі зміни продуктивності однією кнопкою.",
                           "Возможно, виноваты несколько изменений вместе или изменения, действующие после перезагрузки. "
                           "Можно откатить все изменения производительности одной кнопкой.",
                           "Several changes together or changes that apply after a restart may be the cause. You can roll "
                           "back all performance changes with one button."),
    "sm.r.detail": ("FPS {avg0} → {avg1}, 1% low {low}% · замірів: {n}.", "FPS {avg0} → {avg1}, 1% low {low}% · "
                    "замеров: {n}.", "FPS {avg0} → {avg1}, 1% low {low}% · measurements: {n}."),
    "sm.removed": ("Прибрано: {items}", "Убрано: {items}", "Removed: {items}"),
    "sm.done_status": ("Готово. Залишено змін: {kept}", "Готово. Оставлено изменений: {kept}", "Done. Changes kept: {kept}"),
    "sm.done_log": ("[✓] Розумна оптимізація: {res}, FPS {d}%", "[✓] Умная оптимизация: {res}, FPS {d}%",
                    "[✓] Smart optimization: {res}, FPS {d}%"),
    "sm.revert_all": ("Відкотити всі зміни продуктивності", "Откатить все изменения производительности",
                      "Roll back all performance changes"),
    "sm.revert_all_q": ("Відкотити {n} змін продуктивності до ваших початкових значень?",
                        "Откатить {n} изменений производительности к вашим исходным значениям?",
                        "Roll back {n} performance changes to your original values?"),
    "sm.reverted": ("Відкочено змін: {n}", "Откачено изменений: {n}", "Changes rolled back: {n}"),
    "sm.reboot_t": ("Потрібне перезавантаження", "Нужна перезагрузка", "A restart is needed"),
    "sm.reboot_q": ("Частина змін почне діяти лише після перезавантаження. Після нього OptimaX сам відкриється й продовжить "
                    "заміри. Перезавантажити зараз?",
                    "Часть изменений начнёт действовать только после перезагрузки. После неё OptimaX сам откроется и "
                    "продолжит замеры. Перезагрузить сейчас?",
                    "Some changes take effect only after a restart. After it, OptimaX opens by itself and continues the "
                    "measurements. Restart now?"),
    "sm.reboot_log": ("[►] Перезавантаження — після нього OptimaX продовжить сам", "[►] Перезагрузка — после неё OptimaX "
                      "продолжит сам", "[►] Restart — OptimaX continues afterwards"),
    "sm.wait_reboot": ("чекає перезавантаження", "ждёт перезагрузки", "waiting for restart"),
    "sm.resume_t": ("Продовжити розумну оптимізацію?", "Продолжить умную оптимизацию?", "Continue smart optimization?"),
    "sm.resume_q": ("Перезавантаження пройшло — лишилося заміряти, як ПК працює після змін.",
                    "Перезагрузка прошла — осталось замерить, как ПК работает после изменений.",
                    "The restart is done — now OptimaX measures how the PC runs after the changes."),
    "sm.resume_btn": ("Продовжити", "Продолжить", "Continue"),
    "sm.game_t": ("Замір у грі", "Замер в игре", "In-game measurement"),
    "sm.game_q": ("Запустіть {game} і станьте в те саме місце, що й минулого разу. Після «Почати» грайте як зазвичай — "
                  "замір триває {s} секунд.",
                  "Запустите {game} и встаньте в то же место, что и в прошлый раз. После «Начать» играйте как обычно — "
                  "замер длится {s} секунд.",
                  "Start {game} and stand in the same spot as last time. After Start, play as usual — the measurement "
                  "takes {s} seconds."),
    "sm.stopped": ("Зупинено. Тимчасово відкочені зміни повернуто — система в тому ж стані, що й до пошуку.",
                   "Остановлено. Временно откаченные изменения возвращены — система в том же состоянии, что и до поиска.",
                   "Stopped. Temporarily rolled-back changes were re-applied — the system is as it was before the search."),
    "sm.failed": ("Не вдалося: {err}. Тимчасово відкочені зміни повернуто.", "Не удалось: {err}. Временно откаченные "
                  "изменения возвращены.", "Failed: {err}. Temporarily rolled-back changes were re-applied."),

    # ── картка результату ──
    "sc.share": ("Поділитися результатом", "Поделиться результатом", "Share the result"),
    "sc.title_dlg": ("Картка результату", "Карточка результата", "Result card"),
    "sc.sub": ("Лише виміряне на цьому ПК. Ім'я користувача й комп'ютера на картку не потрапляють.",
               "Только измеренное на этом ПК. Имя пользователя и компьютера на карточку не попадают.",
               "Only what was measured on this PC. Your user and computer names are never shown."),
    "sc.show_hw": ("Показати процесор, відеокарту й пам'ять", "Показать процессор, видеокарту и память",
                   "Show CPU, GPU and memory"),
    "sc.copy": ("Копіювати", "Копировать", "Copy"),
    "sc.save": ("Зберегти PNG", "Сохранить PNG", "Save PNG"),
    "sc.saved": ("Картку збережено", "Карточка сохранена", "Card saved"),
    "sc.save_fail": ("Не вдалося зберегти картку", "Не удалось сохранить карточку", "Couldn't save the card"),
    "sc.copied": ("Картку скопійовано — вставте її в чат", "Карточка скопирована — вставьте её в чат",
                  "Card copied — paste it into a chat"),
    "sc.title": ("Мій ПК після OptimaX", "Мой ПК после OptimaX", "My PC after OptimaX"),
    "sc.hero_smart": ("Розумна оптимізація · GPU-тест OptimaX", "Умная оптимизация · GPU-тест OptimaX",
                      "Smart optimization · OptimaX GPU test"),
    "sc.hero_smart_d": ("замірів: {n} · прибрано шкідливих змін: {r}", "замеров: {n} · убрано вредных изменений: {r}",
                        "measurements: {n} · harmful changes removed: {r}"),
    "sc.hero_bench": ("GPU-тест OptimaX · {preset}", "GPU-тест OptimaX · {preset}", "OptimaX GPU test · {preset}"),
    "sc.low1": ("1% low {b} → {a}", "1% low {b} → {a}", "1% low {b} → {a}"),
    "sc.no_hero_t": ("Змін OptimaX: {n}", "Изменений OptimaX: {n}", "OptimaX changes: {n}"),
    "sc.no_hero_d": ("Зробіть тест FPS чи GPU-тест до і після — тут з'явиться приріст.",
                     "Сделайте тест FPS или GPU-тест до и после — здесь появится прирост.",
                     "Run an FPS test or the GPU test before and after — the gain will appear here."),
    "sc.t.boot": ("Завантаження Windows", "Загрузка Windows", "Windows boot"),
    "sc.t.processes": ("Фонові процеси", "Фоновые процессы", "Background processes"),
    "sc.t.ram": ("Зайнято пам'яті", "Занято памяти", "Memory in use"),
    "sc.t.services": ("Запущені служби", "Запущенные службы", "Running services"),
    "sc.t.ads": ("Реклами заблоковано сьогодні", "Рекламы заблокировано сегодня", "Ads blocked today"),
    "sc.t.ads_d": ("{pct}% усіх запитів", "{pct}% всех запросов", "{pct}% of all queries"),
    "sc.t.ping": ("Пінг · {name}", "Пинг · {name}", "Ping · {name}"),
    "sc.t.ping_d": ("джитер {j} мс", "джиттер {j} мс", "jitter {j} ms"),
    "sc.t.tweaks": ("Змін OptimaX", "Изменений OptimaX", "OptimaX changes"),
    "sc.t.tweaks_d": ("усі можна повернути", "все можно вернуть", "all reversible"),
    "sc.footer": ("Перевірено замірами · кожну зміну можна повернути одним кліком",
                  "Проверено замерами · каждое изменение можно вернуть одним кликом",
                  "Verified by measurements · every change can be undone in one click"),
}
