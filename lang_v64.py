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

    "bk.partial": ("відкат не завершено", "откат не завершён", "rollback incomplete"),
    "bk.partial_d": ("Частину кроків не вдалося повернути — повторіть відкат або скористайтеся OptimaX-Rescue.cmd",
                     "Часть шагов не удалось вернуть — повторите откат или воспользуйтесь OptimaX-Rescue.cmd",
                     "Some steps could not be reverted — retry the rollback or use OptimaX-Rescue.cmd"),
}
