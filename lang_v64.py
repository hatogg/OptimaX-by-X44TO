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

    "bk.partial": ("відкат не завершено", "откат не завершён", "rollback incomplete"),
    "bk.partial_d": ("Частину кроків не вдалося повернути — повторіть відкат або скористайтеся OptimaX-Rescue.cmd",
                     "Часть шагов не удалось вернуть — повторите откат или воспользуйтесь OptimaX-Rescue.cmd",
                     "Some steps could not be reverted — retry the rollback or use OptimaX-Rescue.cmd"),
}
