"""OptimaX — переклади 6.4: надійний відкат, перевірка оновлень, точні заміри FPS, діагностика, режими."""

STRINGS = {
    # ── ядро: помилки, права, конфлікти, журнал ──
    "e.need_admin": ("  · пропущено: потрібні права адміністратора",
                     "  · пропущено: нужны права администратора",
                     "  · skipped: administrator rights required"),
    "e.need_admin_all": ("⚠ OptimaX запущено без прав адміністратора: зміни системних параметрів буде пропущено. "
                         "Перезапустіть програму від імені адміністратора.",
                         "⚠ OptimaX запущен без прав администратора: изменения системных параметров будут пропущены. "
                         "Перезапустите программу от имени администратора.",
                         "⚠ OptimaX is running without administrator rights: system-wide changes will be skipped. "
                         "Restart the app as administrator."),
    "e.rolled_back": ("  ↩ те, що встигло змінитися, повернуто — система як до цього пункту",
                      "  ↩ то, что успело измениться, возвращено — система как до этого пункта",
                      "  ↩ what had already changed is reverted — the system is as before this item"),
    "e.rolled_back_part": ("  ⚠ повернуто не все: кроків лишилося {n} — вони в журналі, повторіть відкат пізніше",
                           "  ⚠ возвращено не всё: шагов осталось {n} — они в журнале, повторите откат позже",
                           "  ⚠ not everything was reverted: {n} step(s) left in the journal — retry the rollback later"),
    "e.conflict": ("  ⊘ «{title}» пропущено: суперечить «{other}» (друге просто перезаписало б перше)",
                   "  ⊘ «{title}» пропущено: противоречит «{other}» (второе просто перезаписало бы первое)",
                   "  ⊘ “{title}” skipped: it conflicts with “{other}” (one would simply overwrite the other)"),
    "e.journal_fail": ("  ✗ Журнал відкату не записується ({err}). Щоб кожну зміну можна було повернути, OptimaX "
                       "зупинився й більше нічого не змінює. Перевірте вільне місце на диску й антивірус.",
                       "  ✗ Журнал отката не записывается ({err}). Чтобы каждое изменение можно было вернуть, OptimaX "
                       "остановился и больше ничего не меняет. Проверьте свободное место на диске и антивирус.",
                       "  ✗ The rollback journal can't be written ({err}). So that every change stays reversible, "
                       "OptimaX stopped and changes nothing else. Check free disk space and your antivirus."),
    "e.undo_partial": ("  ⚠ не вдалося повернути кроків: {n} — вони лишаються в журналі; повторіть відкат пізніше "
                       "або скористайтеся OptimaX-Rescue.cmd",
                       "  ⚠ не удалось вернуть шагов: {n} — они остаются в журнале; повторите откат позже "
                       "или воспользуйтесь OptimaX-Rescue.cmd",
                       "  ⚠ {n} step(s) could not be reverted — they stay in the journal; retry later "
                       "or use OptimaX-Rescue.cmd"),
    "e.recover_tweak": ("[↩] «{title}»: застосування обірвалося під час аварійного закриття — повертаю те, що "
                        "встигло змінитися",
                        "[↩] «{title}»: применение оборвалось при аварийном закрытии — возвращаю то, что "
                        "успело измениться",
                        "[↩] “{title}”: applying was cut off by a crash — reverting what had already changed"),

    "opt.conflict_off": ("«{other}» вимкнено: суперечить «{title}»", "«{other}» отключено: противоречит «{title}»",
                         "“{other}” turned off: it conflicts with “{title}”"),
    "rv.conflict": ("суперечить «{other}» — буде пропущено", "противоречит «{other}» — будет пропущено",
                    "conflicts with “{other}” — will be skipped"),

    # ── відновлення після аварійного завершення OptimaX ──
    "rec.title": ("Відновлення після аварії", "Восстановление после сбоя", "Crash recovery"),
    "rec.tweak_done": ("«{title}» застосовувалася, коли OptimaX аварійно закрилася, — її повернуто",
                       "«{title}» применялась, когда OptimaX аварийно закрылась, — она возвращена",
                       "“{title}” was being applied when OptimaX crashed — it has been reverted"),
    "rec.apply_t": ("Застосування змін {when} обірвалося", "Применение изменений {when} оборвалось",
                    "Applying changes on {when} was cut off"),
    "rec.apply_d": ("OptimaX закрилася аварійно (збій, синій екран чи вимкнення світла), не завершивши пакет. "
                    "Змін цього пакета вже застосовано: {n}. Якщо ПК поводиться дивно — відкотіть їх.",
                    "OptimaX закрылась аварийно (сбой, синий экран или отключение света), не завершив пакет. "
                    "Изменений этого пакета уже применено: {n}. Если ПК ведёт себя странно — откатите их.",
                    "OptimaX closed unexpectedly (a crash, a blue screen or a power cut) before the batch finished. "
                    "{n} change(s) of that batch are already applied. If the PC acts up, roll them back."),
    "rec.undo_t": ("Відкат змін {when} не завершився", "Откат изменений {when} не завершился",
                   "Rolling back changes on {when} did not finish"),
    "rec.undo_d": ("OptimaX закрилася посеред відкату. Ще не повернуто змін: {n}.",
                   "OptimaX закрылась посреди отката. Ещё не возвращено изменений: {n}.",
                   "OptimaX closed in the middle of a rollback. {n} change(s) are not reverted yet."),
    "rec.revert": ("Відкотити ({n})", "Откатить ({n})", "Roll back ({n})"),
    "rec.finish": ("Завершити відкат ({n})", "Завершить откат ({n})", "Finish the rollback ({n})"),
    "rec.keep": ("Залишити", "Оставить", "Keep"),
    "rec.kept": ("Зміни залишено. Відкотити їх можна будь-коли в «Резервних копіях»",
                 "Изменения оставлены. Откатить их можно когда угодно в «Резервных копиях»",
                 "Changes kept. You can roll them back any time under Backups"),
    "rec.restored": ("Журнал відкату було пошкоджено — його відновлено з резервної копії",
                     "Журнал отката был повреждён — он восстановлен из резервной копии",
                     "The rollback journal was damaged — it has been restored from the backup copy"),
    "rec.lost_t": ("Журнал відкату пошкоджено", "Журнал отката повреждён", "The rollback journal is damaged"),
    "rec.lost_d": ("Файл журналу зіпсований, а резервної копії немає. OptimaX може знайти свої зміни за знімком "
                   "початкових налаштувань Windows і повернути їх.",
                   "Файл журнала испорчен, а резервной копии нет. OptimaX может найти свои изменения по снимку "
                   "исходных настроек Windows и вернуть их.",
                   "The journal file is corrupt and there is no backup copy. OptimaX can find its changes using the "
                   "snapshot of your original Windows settings and revert them."),
    "rec.lost_check": ("Перевірити", "Проверить", "Check"),

    # ── знімок початкових налаштувань ──
    "bl.title": ("Початкові налаштування Windows", "Исходные настройки Windows", "Original Windows settings"),
    "bl.card_d": ("Перед першою зміною OptimaX запам'ятовує, якими були всі параметри, що їх може змінити. "
                  "Якщо журнал відкату загубиться, за цим знімком OptimaX знайде свої зміни й поверне їх.",
                  "Перед первым изменением OptimaX запоминает, какими были все параметры, которые он может изменить. "
                  "Если журнал отката потеряется, по этому снимку OptimaX найдёт свои изменения и вернёт их.",
                  "Before its first change OptimaX records every setting it may change. If the rollback journal is "
                  "ever lost, OptimaX uses this snapshot to find its changes and revert them."),
    "bl.state": ("Знімок від {when}: параметрів — {n}", "Снимок от {when}: параметров — {n}",
                 "Snapshot from {when}: {n} settings"),
    "bl.none": ("Знімка ще немає — OptimaX зробить його перед першою зміною",
                "Снимка ещё нет — OptimaX сделает его перед первым изменением",
                "No snapshot yet — OptimaX takes one before its first change"),
    "bl.saved": ("  · знімок початкових налаштувань Windows збережено (параметрів: {n})",
                 "  · снимок исходных настроек Windows сохранён (параметров: {n})",
                 "  · snapshot of the original Windows settings saved ({n} settings)"),
    "bl.check": ("Знайти зміни без запису", "Найти изменения без записи", "Find unrecorded changes"),
    "bl.restore": ("Повернути початкові", "Вернуть исходные", "Restore the originals"),
    "bl.restore_n": ("Повернути початкові ({n})", "Вернуть исходные ({n})", "Restore the originals ({n})"),
    "bl.restore_q": ("Параметрів, які мають значення оптимізацій OptimaX, але відсутні в журналі відкату: {n}. "
                     "Повернути їм значення, які були до OptimaX?",
                     "Параметров, которые имеют значения оптимизаций OptimaX, но отсутствуют в журнале отката: {n}. "
                     "Вернуть им значения, которые были до OptimaX?",
                     "{n} setting(s) have OptimaX optimization values but no record in the rollback journal. "
                     "Restore the values they had before OptimaX?"),
    "bl.found": ("Знайдено змін без запису в журналі: {n}", "Найдено изменений без записи в журнале: {n}",
                 "Changes without a journal record found: {n}"),
    "bl.clean": ("Усе, що змінювала OptimaX, є в журналі відкату", "Всё, что меняла OptimaX, есть в журнале отката",
                 "Everything OptimaX changed is in the rollback journal"),
    "bl.more": ("…і ще {n}", "…и ещё {n}", "…and {n} more"),
    "bl.restored": ("\nПовернуто параметрів: {n}", "\nВозвращено параметров: {n}", "\nSettings restored: {n}"),
    # ── перевірка завантажених файлів (оновлення, PresentMon) ──
    "vf.checking": ("  · перевірка файлу: контрольна сума SHA-256 і цифровий підпис…",
                    "  · проверка файла: контрольная сумма SHA-256 и цифровая подпись…",
                    "  · verifying the file: SHA-256 checksum and digital signature…"),
    "vf.ok": ("  ✓ файл перевірено: SHA-256 збігається, підпис — {sig}",
              "  ✓ файл проверен: SHA-256 совпадает, подпись — {sig}",
              "  ✓ file verified: SHA-256 matches, signature: {sig}"),
    "vf.sig.valid": ("дійсний", "действительна", "valid"),
    "vf.sig.unsigned": ("відсутній (збірка без сертифіката)", "отсутствует (сборка без сертификата)",
                        "none (build without a certificate)"),
    "vf.sig.unknown": ("не перевірявся", "не проверялась", "not checked"),
    "vf.sig.invalid": ("недійсний", "недействительна", "invalid"),
    "vf.no_hash": ("Для {name} не опубліковано контрольної суми — запускати неперевірений файл з правами "
                   "адміністратора OptimaX не буде.",
                   "Для {name} не опубликована контрольная сумма — запускать непроверенный файл с правами "
                   "администратора OptimaX не будет.",
                   "No checksum is published for {name} — OptimaX won't run an unverified file with administrator "
                   "rights."),
    "vf.sources_differ": ("Контрольні суми {name} з GitHub і з SHA256SUMS.txt не збігаються — реліз пошкоджено "
                          "або підмінено.",
                          "Контрольные суммы {name} из GitHub и из SHA256SUMS.txt не совпадают — релиз повреждён "
                          "или подменён.",
                          "The {name} checksums from GitHub and from SHA256SUMS.txt differ — the release is damaged "
                          "or tampered with."),
    "vf.hash_mismatch": ("Файл {name} пошкоджено або підмінено: SHA-256 {got}… замість {exp}…",
                         "Файл {name} повреждён или подменён: SHA-256 {got}… вместо {exp}…",
                         "{name} is damaged or tampered with: SHA-256 {got}… instead of {exp}…"),
    "vf.sig_invalid": ("Цифровий підпис {name} недійсний ({code}) — файл змінено після підписання.",
                       "Цифровая подпись {name} недействительна ({code}) — файл изменён после подписания.",
                       "The digital signature of {name} is invalid ({code}) — the file was changed after signing."),
    "vf.sig_missing": ("{name} не має дійсного цифрового підпису, хоча ця збірка OptimaX підписана — "
                       "оновлення від когось іншого не встановлюється.",
                       "У {name} нет действительной цифровой подписи, хотя эта сборка OptimaX подписана — "
                       "обновление от кого-то другого не устанавливается.",
                       "{name} has no valid digital signature although this OptimaX build is signed — an update "
                       "from someone else is not installed."),
    "vf.sig_other": ("{name} підписано іншим видавцем ({who}), а не {want}.",
                     "{name} подписан другим издателем ({who}), а не {want}.",
                     "{name} is signed by a different publisher ({who}), not {want}."),
    "vf.fail_t": ("Оновлення не встановлено", "Обновление не установлено", "The update was not installed"),
    "vf.fail_d": ("{why}\n\nOptimaX не запускає файли, які не пройшли перевірку. Можна завантажити оновлення "
                  "вручну зі сторінки релізу й звірити контрольну суму з SHA256SUMS.txt.",
                  "{why}\n\nOptimaX не запускает файлы, которые не прошли проверку. Можно скачать обновление "
                  "вручную со страницы релиза и сверить контрольную сумму с SHA256SUMS.txt.",
                  "{why}\n\nOptimaX doesn't run files that fail verification. You can download the update "
                  "manually from the release page and compare its checksum with SHA256SUMS.txt."),

    # ── тест FPS: кілька прогонів, медіана, похибка ──
    "fps.runs_3": ("3 прогони", "3 прогона", "3 runs"),
    "fps.runs_5": ("5 прогонів", "5 прогонов", "5 runs"),
    "fps.runs_tip": ("Скільки разів поспіль міряти. Результат — медіана: один невдалий прогін її не зсуне, а розкид "
                     "між прогонами показує похибку вимірювання.",
                     "Сколько раз подряд мерить. Результат — медиана: один неудачный прогон её не сдвинет, а разброс "
                     "между прогонами показывает погрешность измерения.",
                     "How many times in a row to measure. The result is the median: one bad run won't shift it, and "
                     "the spread between runs shows the measurement error."),
    "fps.runs_q": ("Прогонів поспіль: {n}, з короткими паузами (разом ≈{total} хв). Увесь цей час лишайтеся в тій "
                   "самій сцені.",
                   "Прогонов подряд: {n}, с короткими паузами (всего ≈{total} мин). Всё это время оставайтесь в той "
                   "же сцене.",
                   "{n} runs in a row with short pauses (≈{total} min in total). Stay in the same scene the whole "
                   "time."),
    "fps.run_of": ("Прогін {i} з {n}", "Прогон {i} из {n}", "Run {i} of {n}"),
    "fps.run_failed": ("  ⚠ прогін {i} не вдався: {err}", "  ⚠ прогон {i} не удался: {err}", "  ⚠ run {i} failed: {err}"),
    "fps.runs_log": ("  ✓ медіана {n} прогонів: FPS {avg}, 1% low {low}, розкид FPS {sp}",
                     "  ✓ медиана {n} прогонов: FPS {avg}, 1% low {low}, разброс FPS {sp}",
                     "  ✓ median of {n} runs: FPS {avg}, 1% low {low}, FPS spread {sp}"),
    "fps.dropped": (" · відкинуто невдалих прогонів: {n}", " · отброшено неудачных прогонов: {n}",
                    " · bad runs dropped: {n}"),
    "fps.before_n": ("До (медіана {n})", "До (медиана {n})", "Before (median of {n})"),
    "fps.after_n": ("Після (медіана {n})", "После (медиана {n})", "After (median of {n})"),
    "fps.change": ("Зміна ± похибка", "Изменение ± погрешность", "Change ± error"),
    "fps.delta": ("{d}% ± {m}%", "{d}% ± {m}%", "{d}% ± {m}%"),
    "fps.sig": ("Зміна більша за похибку вимірювання — її не пояснити випадковістю",
                "Изменение больше погрешности измерения — его не объяснить случайностью",
                "The change exceeds the measurement error — chance can't explain it"),
    "fps.not_sig": ("Зміна в межах похибки — може бути випадковою", "Изменение в пределах погрешности — может быть "
                    "случайным", "The change is within the measurement error — it may be random"),
    "fps.stutters_pm": ("Фризи за хвилину", "Фризы в минуту", "Stutters per minute"),
    "fps.smooth": ("Плавність (100 — ідеально рівні кадри)", "Плавность (100 — идеально ровные кадры)",
                   "Smoothness (100 = perfectly even frames)"),
    "fps.v2.better": ("Приріст підтверджено: FPS {avg}%, 1% low {low}% — більше за похибку вимірювання ±{m}%",
                      "Прирост подтверждён: FPS {avg}%, 1% low {low}% — больше погрешности измерения ±{m}%",
                      "Gain confirmed: FPS {avg}%, 1% low {low}% — more than the ±{m}% measurement error"),
    "fps.v2.same": ("Різниці немає: FPS {avg}%, 1% low {low}% — у межах похибки вимірювання ±{m}%",
                    "Разницы нет: FPS {avg}%, 1% low {low}% — в пределах погрешности измерения ±{m}%",
                    "No real difference: FPS {avg}%, 1% low {low}% — within the ±{m}% measurement error"),
    "fps.v2.worse": ("Стало гірше: FPS {avg}%, 1% low {low}% — більше за похибку ±{m}%; можна відкотити зміни між "
                     "замірами",
                     "Стало хуже: FPS {avg}%, 1% low {low}% — больше погрешности ±{m}%; можно откатить изменения "
                     "между замерами",
                     "Got worse: FPS {avg}%, 1% low {low}% — more than the ±{m}% error; you can roll back the changes "
                     "made between the measurements"),
    "fps.smooth_up": ("Кадри рівніші (+{d} плавності).", "Кадры ровнее (+{d} плавности).",
                      "Frames are more even (+{d} smoothness)."),
    "fps.smooth_down": ("Кадри менш рівні (−{d} плавності).", "Кадры менее ровные (−{d} плавности).",
                        "Frames are less even (−{d} smoothness)."),
    "fps.low_conf": ("Один із замірів зроблено одним прогоном (до 6.4) — похибку оцінено приблизно. Повторіть "
                     "заміри, щоб висновок був точним.",
                     "Один из замеров сделан одним прогоном (до 6.4) — погрешность оценена приблизительно. Повторите "
                     "замеры, чтобы вывод был точным.",
                     "One of the measurements is a single run (before 6.4), so the error is only estimated. Measure "
                     "again for a precise verdict."),

    # ── розумна оптимізація: похибка й зміни без ефекту ──
    "sm.margin_sig": ("Похибка вимірювання ±{m}% (заміри: {nb} до, {na} після) — зміна більша за неї, це не "
                      "випадковість.",
                      "Погрешность измерения ±{m}% (замеры: {nb} до, {na} после) — изменение больше неё, это не "
                      "случайность.",
                      "Measurement error ±{m}% ({nb} runs before, {na} after) — the change exceeds it, so it's not "
                      "random."),
    "sm.margin_ns": ("Похибка вимірювання ±{m}% (заміри: {nb} до, {na} після) — зміна в її межах, доведеного "
                     "приросту немає.",
                     "Погрешность измерения ±{m}% (замеры: {nb} до, {na} после) — изменение в её пределах, "
                     "доказанного прироста нет.",
                     "Measurement error ±{m}% ({nb} runs before, {na} after) — the change is within it, so there's "
                     "no proven gain."),
    "sm.no_effect_btn": ("Прибрати зміни без ефекту", "Убрать изменения без эффекта", "Remove changes with no effect"),
    "sm.no_effect_btn_n": ("Прибрати зміни без ефекту ({n})", "Убрать изменения без эффекта ({n})",
                           "Remove changes with no effect ({n})"),
    "sm.no_effect_q": ("Заміри не показали приросту FPS понад похибку. Відкотити зміни продуктивності, які "
                       "перевірялися ({n})? Приватність, реклама й очищення залишаться. Зважте: частина змін "
                       "(таймер, миша) впливає на відгук, а не на FPS.",
                       "Замеры не показали прироста FPS сверх погрешности. Откатить изменения производительности, "
                       "которые проверялись ({n})? Приватность, реклама и очистка останутся. Учтите: часть изменений "
                       "(таймер, мышь) влияет на отклик, а не на FPS.",
                       "The measurements showed no FPS gain beyond the error. Roll back the performance changes that "
                       "were tested ({n})? Privacy, ads and cleanup stay. Note: some changes (timer, mouse) affect "
                       "responsiveness, not FPS."),

    # ── головне обмеження продуктивності ──
    "lim.head": ("Головне обмеження: {what} — {pct}% часу", "Главное ограничение: {what} — {pct}% времени",
                 "Main limit: {what} — {pct}% of the time"),
    "lim.head_fps": ("Під час заміру FPS обмежував: {what} ({pct}% часу)",
                     "Во время замера FPS ограничивал: {what} ({pct}% времени)",
                     "During the measurement FPS was limited by: {what} ({pct}% of the time)"),
    "lim.second": ("Інколи також: {what}.", "Иногда также: {what}.", "Sometimes also: {what}."),
    "lim.cpu": ("процесор", "процессор", "the CPU"),
    "lim.gpu": ("відеокарта", "видеокарта", "the graphics card"),
    "lim.ram": ("оперативна пам'ять", "оперативная память", "RAM"),
    "lim.disk": ("диск", "диск", "the drive"),
    "lim.thermal": ("перегрів", "перегрев", "overheating"),
    "lim.power": ("обмеження живлення", "ограничение питания", "the power limit"),
    "lim.none": ("ніщо із заліза", "ничто из железа", "nothing in the hardware"),
    "lim.mixed": ("різне, без явного лідера", "разное, без явного лидера", "a mix, no clear leader"),
    "lim.cpu.d": ("Відеокарта чекає на процесор. Допоможуть менше фонових програм, пріоритет гри, план живлення; "
                  "у грі — нижчі налаштування, що навантажують процесор (дальність, натовпи, фізика).",
                  "Видеокарта ждёт процессор. Помогут меньше фоновых программ, приоритет игры, план питания; "
                  "в игре — ниже настройки, нагружающие процессор (дальность, толпы, физика).",
                  "The graphics card waits for the CPU. Fewer background apps, game priority and the power plan "
                  "help; in game, lower CPU-heavy settings (draw distance, crowds, physics)."),
    "lim.gpu.d": ("Відеокарта працює на повну — це нормально для гри. Більше FPS дадуть нижча роздільність чи "
                  "якість, DLSS/FSR; твіки процесора тут FPS не додадуть.",
                  "Видеокарта работает на полную — это нормально для игры. Больше FPS дадут ниже разрешение или "
                  "качество, DLSS/FSR; твики процессора здесь FPS не добавят.",
                  "The graphics card is fully used — normal for a game. Lower resolution or quality, DLSS/FSR add "
                  "FPS; CPU tweaks won't."),
    "lim.ram.d": ("Пам'яті бракує, Windows підкачує з диска — звідси фризи. Закрийте браузер і фонові програми; "
                  "найкраще — додати пам'ять.",
                  "Памяти не хватает, Windows подкачивает с диска — отсюда фризы. Закройте браузер и фоновые "
                  "программы; лучше всего — добавить память.",
                  "RAM runs out and Windows pages to disk — hence the stutters. Close the browser and background "
                  "apps; adding RAM helps most."),
    "lim.disk.d": ("Диск зайнятий майже весь час — гра довантажує дані повільно. Допоможуть менше фонового "
                   "індексування й оновлень, а найбільше — SSD.",
                   "Диск занят почти всё время — игра подгружает данные медленно. Помогут меньше фоновой "
                   "индексации и обновлений, а больше всего — SSD.",
                   "The drive is busy nearly all the time and the game loads data slowly. Less background indexing "
                   "and updates help; an SSD helps most."),
    "lim.thermal.d": ("Залізо перегрівається й скидає частоти. Спершу охолодження: пил, термопаста, підставка для "
                      "ноутбука. Твіки, що підвищують частоти й нагрів, OptimaX не пропонуватиме.",
                      "Железо перегревается и сбрасывает частоты. Сначала охлаждение: пыль, термопаста, подставка для "
                      "ноутбука. Твики, повышающие частоты и нагрев, OptimaX предлагать не будет.",
                      "The hardware overheats and drops clocks. Cooling first: dust, thermal paste, a laptop stand. "
                      "OptimaX won't offer tweaks that raise clocks and heat."),
    "lim.power.d": ("Процесор обмежує план живлення чи режим енергозбереження. Допоможе план «Максимальна "
                    "продуктивність» (на ноутбуці — від розетки).",
                    "Процессор ограничивает план питания или режим энергосбережения. Поможет план «Максимальная "
                    "производительность» (на ноутбуке — от розетки).",
                    "The power plan or power saving limits the CPU. The Ultimate Performance plan helps (on a laptop, "
                    "when plugged in)."),
    "lim.none.d": ("Ні процесор, ні відеокарта не завантажені повністю — FPS, імовірно, обмежує ліміт кадрів, V-Sync "
                   "чи сама гра. Оптимізації Windows тут мало що змінять.",
                   "Ни процессор, ни видеокарта не загружены полностью — FPS, вероятно, ограничивает лимит кадров, "
                   "V-Sync или сама игра. Оптимизации Windows здесь мало что изменят.",
                   "Neither the CPU nor the GPU is fully loaded — FPS is probably capped by a frame limiter, V-Sync "
                   "or the game itself. Windows tweaks will change little here."),
    "lim.mixed.d": ("Обмеження змінюється від сцени до сцени — план лишається загальним.",
                    "Ограничение меняется от сцены к сцене — план остаётся общим.",
                    "The limit changes from scene to scene, so the plan stays general."),

    # ── режими оптимізації ──
    "opt.mode_modes": ("Режими", "Режимы", "Modes"),
    "mode.safe.t": ("Безпечний", "Безопасный", "Safe"),
    "mode.safe.sub": ("Мінімум ризику", "Минимум риска", "Minimal risk"),
    "mode.safe.d": ("Телеметрія, реклама, зайві фонові процеси. Лише зміни з низьким ризиком, кожну можна відкотити; "
                    "служби, живлення й драйвери не змінюються.",
                    "Телеметрия, реклама, лишние фоновые процессы. Только изменения с низким риском, каждое можно "
                    "откатить; службы, питание и драйверы не меняются.",
                    "Telemetry, ads, needless background work. Only low-risk changes, each one reversible; services, "
                    "power and drivers stay untouched."),
    "mode.gaming.t": ("Ігровий", "Игровой", "Gaming"),
    "mode.gaming.sub": ("Максимум FPS із доказом", "Максимум FPS с доказательством", "Max FPS, with proof"),
    "mode.gaming.d": ("Лише те, що допомагає саме вашому залізу і саме тому, що обмежує FPS. Після застосування "
                      "OptimaX заміряє результат і прибере зміни, які шкодять.",
                      "Только то, что помогает именно вашему железу и именно тому, что ограничивает FPS. После "
                      "применения OptimaX замерит результат и уберёт изменения, которые вредят.",
                      "Only what helps your hardware and what actually limits your FPS. After applying, OptimaX "
                      "measures the result and removes changes that hurt."),
    "mode.lowend.t": ("Слабкий ПК", "Слабый ПК", "Low-end PC"),
    "mode.lowend.sub": ("Мало пам'яті, HDD, старе залізо", "Мало памяти, HDD, старое железо",
                        "Little RAM, an HDD, old hardware"),
    "mode.lowend.d": ("Звільняє пам'ять і диск: без анімацій і прозорості, менше фонових програм та індексування. "
                      "Якщо діагностика бачить нестачу пам'яті чи диска — додає й зміни саме для них.",
                      "Освобождает память и диск: без анимаций и прозрачности, меньше фоновых программ и индексации. "
                      "Если диагностика видит нехватку памяти или диска — добавляет изменения именно для них.",
                      "Frees RAM and disk: no animations or transparency, fewer background apps and less indexing. If "
                      "the diagnosis sees RAM or disk running short, it adds changes for exactly that."),
    "mode.manual.t": ("Ручний", "Ручной", "Manual"),
    "mode.manual.sub": ("Повний контроль", "Полный контроль", "Full control"),
    "mode.manual.d": ("Усі оптимізації за розділами: пояснення, поточний стан і що саме зміниться. Вибираєте самі.",
                      "Все оптимизации по разделам: пояснения, текущее состояние и что именно изменится. Выбираете "
                      "сами.",
                      "All optimizations by section: explanations, current state and what exactly changes. You pick."),
    "mode.manual.count": ("Нічого не вибрано заздалегідь", "Ничего не выбрано заранее", "Nothing is preselected"),
    "mode.rec": ("рекомендовано", "рекомендуется", "recommended"),
    "mode.count": ("Для вашого ПК: змін — {n}", "Для вашего ПК: изменений — {n}", "For your PC: {n} changes"),
    "mode.proven": ("перевірено на цьому ПК — {n}", "проверено на этом ПК — {n}", "{n} proven on this PC"),
    "mode.smart_note": ("Результат буде заміряно: залишиться лише те, що не шкодить.",
                        "Результат будет замерен: останется только то, что не вредит.",
                        "The result will be measured: only changes that don't hurt stay."),
    "mode.view": ("Переглянути план", "Посмотреть план", "Review the plan"),
    "mode.open_expert": ("Відкрити експертне меню", "Открыть экспертное меню", "Open the expert menu"),
    "mode.why": ("Що не ввійшло ({n})", "Что не вошло ({n})", "Left out ({n})"),
    "mode.why_t": ("Що не ввійшло в план і чому", "Что не вошло в план и почему", "What was left out and why"),
    "mode.why_sub": ("План складено для вашого ПК: залізо, що обмежує FPS, і результати попередніх замірів.",
                     "План составлен для вашего ПК: железо, что ограничивает FPS, и результаты прошлых замеров.",
                     "The plan is built for your PC: hardware, what limits FPS and earlier measurements."),
    "mode.limit": ("За останнім заміром FPS обмежує {what} — «Ігровий» план враховує це.",
                   "По последнему замеру FPS ограничивает {what} — «Игровой» план учитывает это.",
                   "In the latest measurement FPS was limited by {what} — the Gaming plan takes this into account."),
    "mode.limit_weak": ("За останнім заміром явного обмеження немає (найчастіше — {what}), тож план загальний.",
                        "По последнему замеру явного ограничения нет (чаще всего — {what}), поэтому план общий.",
                        "The latest measurement shows no clear limit (most often {what}), so the plan is general."),
    "mode.limit_none": ("Ще невідомо, що обмежує FPS на цьому ПК. Запустіть «Чому лагає?» або тест FPS у грі — "
                        "і «Ігровий» план стане точнішим.",
                        "Ещё неизвестно, что ограничивает FPS на этом ПК. Запустите «Почему лагает?» или тест FPS в "
                        "игре — и «Игровой» план станет точнее.",
                        "It's not known yet what limits FPS on this PC. Run “Why does it lag?” or an in-game FPS test "
                        "and the Gaming plan gets more precise."),
    "mode.diag_btn": ("Діагностика", "Диагностика", "Diagnose"),
    "why.na": ("не підходить цьому залізу чи версії Windows", "не подходит этому железу или версии Windows",
               "doesn't fit this hardware or Windows version"),
    "why.block": ("шкодить на такому залізі", "вредит на таком железе", "harmful on this hardware"),
    "why.harmful": ("шкодило саме на цьому ПК — так показали заміри розумної оптимізації",
                    "вредило именно на этом ПК — так показали замеры умной оптимизации",
                    "hurt this very PC — smart optimization measurements showed it"),
    "why.no_effect": ("двічі не дало ефекту понад похибку в замірах на цьому ПК",
                      "дважды не дало эффекта сверх погрешности в замерах на этом ПК",
                      "twice showed no effect beyond the measurement error on this PC"),
    "why.limit": ("не допоможе: FPS обмежує {limit}", "не поможет: FPS ограничивает {limit}",
                  "won't help: FPS is limited by {limit}"),
    "why.hot": ("підвищує нагрів, а залізо вже перегрівається", "повышает нагрев, а железо уже перегревается",
                "adds heat, and the hardware already overheats"),
    "why.conflict": ("суперечить «{other}»", "противоречит «{other}»", "conflicts with “{other}”"),
    "why.not_reversible": ("не відкочується", "не откатывается", "can't be rolled back"),

    "bk.partial": ("відкат не завершено", "откат не завершён", "rollback incomplete"),
    "bk.partial_d": ("Частину кроків не вдалося повернути — повторіть відкат або скористайтеся OptimaX-Rescue.cmd",
                     "Часть шагов не удалось вернуть — повторите откат или воспользуйтесь OptimaX-Rescue.cmd",
                     "Some steps could not be reverted — retry the rollback or use OptimaX-Rescue.cmd"),
}
