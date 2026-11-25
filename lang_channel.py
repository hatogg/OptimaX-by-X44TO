"""Переклади OptimaX 7.2: канал оновлень «Стабільний / Бета» (українська, російська, англійська)."""

STRINGS = {
    "ch.title": ("Канал оновлень", "Канал обновлений", "Update channel"),
    "ch.stable": ("Стабільний", "Стабильный", "Stable"),
    "ch.beta": ("Бета", "Бета", "Beta"),
    "ch.badge": ("бета", "бета", "beta"),
    "ch.ver_beta": ("{v} (бета)", "{v} (бета)", "{v} (beta)"),
    "ch.stable_d": ("Лише перевірені випуски — рекомендовано для всіх.",
                    "Только проверенные выпуски — рекомендуется для всех.",
                    "Only finished releases — recommended for everyone."),
    "ch.beta_d": ("Нові версії раніше за всіх, для тих, хто хоче допомогти з тестуванням. Бета може містити помилки; "
                  "відкат змін і OptimaX-Rescue працюють як завжди.",
                  "Новые версии раньше всех, для тех, кто хочет помочь с тестированием. Бета может содержать ошибки; "
                  "откат изменений и OptimaX-Rescue работают как всегда.",
                  "New versions before everyone else, for those who want to help with testing. A beta may have bugs; "
                  "rollback and OptimaX-Rescue work as always."),
    "ch.downgrade": ("Зараз встановлено бету {v}. На стабільному каналі OptimaX не повертає старішу версію сама: "
                     "стабільну буде запропоновано, щойно вийде новіша за цю бету (наприклад, {base}).",
                     "Сейчас установлена бета {v}. На стабильном канале OptimaX не возвращает более старую версию "
                     "сама: стабильную предложим, как только выйдет более новая, чем эта бета (например, {base}).",
                     "Beta {v} is installed. On the stable channel OptimaX doesn't roll back to an older version: "
                     "you'll be offered a stable one as soon as it is newer than this beta (for example, {base})."),
    "ch.ask_beta": ("Це бета-версія для тестувальників — вона може містити помилки. Відкат змін і OptimaX-Rescue "
                    "працюють як завжди; повернутися на стабільний канал можна в налаштуваннях.",
                    "Это бета-версия для тестировщиков — она может содержать ошибки. Откат изменений и OptimaX-Rescue "
                    "работают как всегда; вернуться на стабильный канал можно в настройках.",
                    "This is a beta for testers — it may have bugs. Rollback and OptimaX-Rescue work as always; you "
                    "can switch back to the stable channel in Settings."),
    "ch.wn_beta": ("Це бета-версія — дякуємо, що тестуєте! Помітили помилку — «Повідомити про проблему» в "
                   "налаштуваннях.",
                   "Это бета-версия — спасибо, что тестируете! Заметили ошибку — «Сообщить о проблеме» в "
                   "настройках.",
                   "This is a beta — thanks for testing! Found a bug? Use «Report a problem» in Settings."),
    "ch.switched": ("Канал оновлень: {ch}", "Канал обновлений: {ch}", "Update channel: {ch}"),
    "ch.log": ("  · канал оновлень: {ch}", "  · канал обновлений: {ch}", "  · update channel: {ch}"),
}
