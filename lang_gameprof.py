"""Переклади профілів ігор (Game Booster 2.0, gameprof.py / pages_gameprof.py): українська, російська, англійська."""

STRINGS = {
    # ── значення профілю ──
    "gprof.power.keep": ("Не змінювати", "Не менять", "Keep current"),
    "gprof.power.high": ("Висока продуктивність", "Высокая производительность", "High performance"),
    "gprof.power.ultimate": ("Максимальна продуктивність", "Максимальная производительность", "Ultimate Performance"),
    "gprof.gpu.keep": ("Не змінювати", "Не менять", "Keep current"),
    "gprof.gpu.high": ("Висока продуктивність", "Высокая производительность", "High performance"),
    "gprof.gpu.saving": ("Енергозбереження", "Энергосбережение", "Power saving"),
    "gprof.prio.keep": ("Не змінювати", "Не менять", "Keep current"),
    "gprof.prio.normal": ("Звичайний", "Обычный", "Normal"),
    "gprof.prio.above": ("Вище звичайного", "Выше обычного", "Above normal"),
    "gprof.prio.high": ("Високий", "Высокий", "High"),
    "gprof.none": ("Нічого не змінює", "Ничего не меняет", "Changes nothing"),
    "gprof.sum_gpu": ("відеокарта: {v}", "видеокарта: {v}", "GPU: {v}"),
    "gprof.sum_prio": ("пріоритет: {v}", "приоритет: {v}", "priority: {v}"),
    "gprof.sum_boost": ("режим гри", "игровой режим", "game mode"),
    "gprof.sum_off": ("вимкнено ({v})", "выключен ({v})", "off ({v})"),
    # ── журнал ──
    "gprof.t_power": ("Профіль гри: схема живлення «{plan}»", "Профиль игры: схема питания «{plan}»",
                      "Game profile: power plan “{plan}”"),
    "gprof.t_gpu": ("Профіль гри {game}: відеокарта для {exe} — {mode}", "Профиль игры {game}: видеокарта для {exe} — "
                    "{mode}", "Game profile {game}: GPU for {exe} — {mode}"),
    "gprof.power_on": ("  ✓ схема живлення: {plan}", "  ✓ схема питания: {plan}", "  ✓ power plan: {plan}"),
    "gprof.power_same": ("  потрібна схема живлення вже активна — нічого не змінено",
                         "  нужная схема питания уже активна — ничего не изменено",
                         "  the required power plan is already active — nothing changed"),
    "gprof.power_booster": ("  схему живлення вже змінив режим гри — профіль її не чіпає, поверне режим гри",
                            "  схему питания уже изменил игровой режим — профиль её не трогает, вернёт игровой режим",
                            "  game mode already changed the power plan — the profile leaves it, game mode restores "
                            "it"),
    "gprof.power_undo_fail": ("  ⚠ схему живлення повернути не вдалося — запис лишився в журналі відкату (повтор "
                              "пізніше або OptimaX-Rescue.cmd)",
                              "  ⚠ схему питания вернуть не удалось — запись осталась в журнале отката (повтор "
                              "позже или OptimaX-Rescue.cmd)",
                              "  ⚠ could not restore the power plan — the record stays in the undo journal (retry "
                              "later or OptimaX-Rescue.cmd)"),
    "gprof.gpu_mine": ("  {exe}: висока продуктивність уже задана в «Моїх іграх»",
                       "  {exe}: высокая производительность уже задана в «Моих играх»",
                       "  {exe}: high performance is already set in My games"),
    "gprof.gpu_clash": ("  ⚠ {exe}: відеокарту для цього exe задано в «Моїх іграх» — зніміть там позначку, щоб "
                        "профіль міг її змінити",
                        "  ⚠ {exe}: видеокарта для этого exe задана в «Моих играх» — снимите там отметку, чтобы "
                        "профиль мог её изменить",
                        "  ⚠ {exe}: the GPU for this exe is set in My games — clear it there so the profile can "
                        "change it"),
    "gprof.gpu_mining": ("  {exe}: уже призначено на майнінгову карту (висока продуктивність)",
                         "  {exe}: уже назначено на майнинговую карту (высокая производительность)",
                         "  {exe}: already assigned to the mining card (high performance)"),
    "gprof.gpu_undo_fail": ("  ⚠ попереднє налаштування відеокарти повернути не вдалося — нове не застосовано",
                            "  ⚠ прежнюю настройку видеокарты вернуть не удалось — новая не применена",
                            "  ⚠ could not restore the previous GPU setting — the new one was not applied"),
    "gprof.saved": ("  Профіль гри {game} збережено.", "  Профиль игры {game} сохранён.",
                    "  Game profile {game} saved."),
    "gprof.removed": ("  Профіль гри {game} видалено.", "  Профиль игры {game} удалён.",
                      "  Game profile {game} removed."),
    "gprof.log_on": ("[►] Профіль гри: {game} запущено", "[►] Профиль игры: {game} запущена",
                     "[►] Game profile: {game} started"),
    "gprof.log_off": ("[↩] Профіль гри: {game} закрито — повертаю як було", "[↩] Профиль игры: {game} закрыта — "
                      "возвращаю как было", "[↩] Game profile: {game} closed — restoring"),
    "gprof.prio_set": ("  ✓ пріоритет {exe}: {prio}", "  ✓ приоритет {exe}: {prio}", "  ✓ {exe} priority: {prio}"),
    "gprof.prio_back": ("  ↩ пріоритет {exe} — як був", "  ↩ приоритет {exe} — как был", "  ↩ {exe} priority restored"),
    "gprof.prio_fail": ("  ⚠ пріоритет {exe} змінити не вдалося (захищений процес чи античит)",
                        "  ⚠ приоритет {exe} изменить не удалось (защищённый процесс или античит)",
                        "  ⚠ could not change {exe} priority (protected process or anti-cheat)"),
    "gprof.prio_skip": ("  {exe}: нестандартний пріоритет задано не OptimaX — не чіпаю",
                        "  {exe}: нестандартный приоритет задан не OptimaX — не трогаю",
                        "  {exe}: an unusual priority was set by something else — leaving it"),
    # ── інтерфейс ──
    "gprof.btn": ("Профіль", "Профиль", "Profile"),
    "gprof.title_short": ("Профіль гри", "Профиль игры", "Game profile"),
    "gprof.title": ("Профіль гри: {game}", "Профиль игры: {game}", "Game profile: {game}"),
    "gprof.sub": ("Вмикається сам, коли гра запускається, і повертає все як було, коли вона закривається (а після "
                  "аварійного закриття — під час наступного запуску OptimaX або через OptimaX-Rescue.cmd).",
                  "Включается сам, когда игра запускается, и возвращает всё как было, когда она закрывается (а после "
                  "аварийного закрытия — при следующем запуске OptimaX или через OptimaX-Rescue.cmd).",
                  "Turns on by itself when the game starts and restores everything when it closes (after a crash — "
                  "on the next OptimaX start or via OptimaX-Rescue.cmd)."),
    "gprof.enabled": ("Профіль увімкнено", "Профиль включён", "Profile on"),
    "gprof.enabled_d": ("Вимкнений профіль нічого не змінює, але налаштування зберігаються.",
                        "Выключенный профиль ничего не меняет, но настройки сохраняются.",
                        "A disabled profile changes nothing but keeps its settings."),
    "gprof.power_t": ("Схема живлення під час гри", "Схема питания во время игры", "Power plan while playing"),
    "gprof.power_d": ("Перемикається, коли гра запускається, і повертається, коли закривається. Кілька ігор "
                      "одночасно — найсильніша з потрібних.",
                      "Переключается при запуске игры и возвращается при закрытии. Несколько игр одновременно — "
                      "самая сильная из нужных.",
                      "Switches when the game starts and is restored when it closes. Several games at once — the "
                      "strongest one requested."),
    "gprof.gpu_t": ("Відеокарта для гри", "Видеокарта для игры", "GPU for the game"),
    "gprof.gpu_d": ("Налаштування «Графіка» Windows для exe гри. Windows читає його під час запуску гри, тож воно "
                    "діє з наступного запуску й лишається, поки є профіль (відкат — у «Змінах»).",
                    "Настройка «Графика» Windows для exe игры. Windows читает её при запуске игры, поэтому она "
                    "действует со следующего запуска и остаётся, пока есть профиль (откат — в «Изменениях»).",
                    "Windows Graphics setting for the game exe. Windows reads it when the game starts, so it applies "
                    "from the next launch and stays while the profile exists (undo — in Changes)."),
    "gprof.gpu_d_mining": ("На цьому ПК «висока продуктивність» — це майнінгова карта {gpu}.",
                           "На этом ПК «высокая производительность» — это майнинговая карта {gpu}.",
                           "On this PC “high performance” means the mining card {gpu}."),
    "gprof.prio_t": ("Пріоритет процесу гри", "Приоритет процесса игры", "Game process priority"),
    "gprof.prio_d": ("Лише для процесів з папки цієї гри. «Реального часу» немає навмисно: він може заморозити "
                     "систему. Ігри з античитом можуть не дозволити зміну — про це буде в журналі.",
                     "Только для процессов из папки этой игры. «Реального времени» нет намеренно: он может "
                     "заморозить систему. Игры с античитом могут не разрешить изменение — это будет в журнале.",
                     "Only for processes from this game's folder. Realtime is left out on purpose: it can freeze "
                     "the system. Anti-cheat games may refuse the change — the log will say so."),
    "gprof.boost_t": ("Режим гри", "Игровой режим", "Game mode"),
    "gprof.boost_d": ("Увімкнути режим гри (його налаштування — у розділі «Ігри»), якщо він ще не ввімкнений, і "
                      "вимкнути, коли закриється остання гра, якій він потрібен.",
                      "Включить игровой режим (его настройки — в разделе «Игры»), если он ещё не включён, и "
                      "выключить, когда закроется последняя игра, которой он нужен.",
                      "Turn on game mode (its settings are on the Games page) if it is not on yet, and turn it off "
                      "when the last game that needs it closes."),
    "gprof.fps_t": ("FPS цієї гри", "FPS этой игры", "This game's FPS"),
    "gprof.fps_none": ("Замірів ще немає. Тест «до» і «після» — у розділі «Діагностика»; фонові заміри робить "
                       "бібліотека, якщо є PresentMon.",
                       "Замеров ещё нет. Тест «до» и «после» — в разделе «Диагностика»; фоновые замеры делает "
                       "библиотека, если есть PresentMon.",
                       "No measurements yet. The before/after test is on the Diagnostics page; the library records "
                       "in the background if PresentMon is installed."),
    "gprof.fps_side": ("{what}: {avg} FPS · 1% low {low} · {when}", "{what}: {avg} FPS · 1% low {low} · {when}",
                       "{what}: {avg} FPS · 1% low {low} · {when}"),
    "gprof.fps_before": ("До", "До", "Before"),
    "gprof.fps_after": ("Після", "После", "After"),
    "gprof.fps_v.better": ("Після змін: {d}% FPS — більше за похибку вимірювання.",
                           "После изменений: {d}% FPS — больше погрешности измерения.",
                           "After the changes: {d}% FPS — more than the measurement error."),
    "gprof.fps_v.same": ("Після змін: {d}% FPS — у межах похибки вимірювання.",
                         "После изменений: {d}% FPS — в пределах погрешности измерения.",
                         "After the changes: {d}% FPS — within the measurement error."),
    "gprof.fps_v.worse": ("Після змін: {d}% FPS — гірше, ніж до.", "После изменений: {d}% FPS — хуже, чем до.",
                          "After the changes: {d}% FPS — worse than before."),
    "gprof.fps_bg": ("Фонові заміри бібліотеки", "Фоновые замеры библиотеки", "Library background measurements"),
    "gprof.fps_row": ("{when} · {avg} FPS · 1% low {low}", "{when} · {avg} FPS · 1% low {low}",
                      "{when} · {avg} FPS · 1% low {low}"),
    "gprof.fps_prof": ("з профілем", "с профилем", "with profile"),
    "gprof.fps_open": ("Тест FPS", "Тест FPS", "FPS test"),
    "gprof.save": ("Зберегти", "Сохранить", "Save"),
    "gprof.remove": ("Видалити профіль", "Удалить профиль", "Remove profile"),
    "gprof.remove_q": ("Профіль гри {game} буде видалено, а налаштування відеокарти для неї — повернуто як до "
                       "OptimaX. Якщо гра зараз запущена, решта повернеться одразу.",
                       "Профиль игры {game} будет удалён, а настройка видеокарты для неё — возвращена как до "
                       "OptimaX. Если игра сейчас запущена, остальное вернётся сразу.",
                       "The {game} profile will be removed and its GPU setting restored to how it was before "
                       "OptimaX. If the game is running now, the rest is restored right away."),
    "gprof.badge_on": ("● Профіль активний", "● Профиль активен", "● Profile active"),
    "gprof.badge_set": ("Профіль", "Профиль", "Profile"),
    "gprof.active_since": ("Активний з {when}.", "Активен с {when}.", "Active since {when}."),
    "gprof.toast_on": ("Профіль гри {game} увімкнено", "Профиль игры {game} включён", "Game profile {game} on"),
    "gprof.toast_off": ("Профіль гри {game}: усе повернуто", "Профиль игры {game}: всё возвращено",
                        "Game profile {game}: everything restored"),
    "gprof.toast_fail": ("Профіль гри {game}: частину змін не вдалося виконати — подробиці в журналі",
                         "Профиль игры {game}: часть изменений выполнить не удалось — подробности в журнале",
                         "Game profile {game}: some changes failed — see the log"),
    "gprof.recovered": ("Профіль гри: після аварійного закриття все повернуто",
                        "Профиль игры: после аварийного закрытия всё возвращено",
                        "Game profile: everything restored after the crash"),
}
