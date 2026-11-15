# Модулі PawnIO

Тут під час збірки з'являються офіційні підписані модулі [PawnIO.Modules](https://github.com/namazso/PawnIO.Modules)
**0.2.11** (`IntelMSR.bin`, `AMDFamily17.bin`, `SmbusI801.bin`, `SmbusPIIX4.bin`). CI бере їх з релізу цієї версії й
звіряє SHA-256 з `MODULE_SHA256` у `pawnio.py`; у репозиторії їх немає (`*.bin` у `.gitignore`). Перед завантаженням
у драйвер OptimaX ще раз звіряє хеш уже прочитаного файлу.

- Copyright (C) namazso <admin@namazso.eu> та автори модулів. Ліцензія — GNU LGPL 2.1 (`COPYING.LGPL`).
- Вихідний код саме цієї версії: https://github.com/namazso/PawnIO.Modules/tree/0.2.11
- Драйвер [PawnIO](https://github.com/namazso/PawnIO) користувач встановлює сам з https://pawnio.eu. OptimaX драйвер не
  ставить і спілкується з ним лише через `DeviceIoControl` — саме це дозволяє виняток у ліцензії PawnIO.
- Драйвер сам перевіряє підпис модуля, тож змінений файл він не завантажить.

<details><summary>English</summary>

The build drops the official signed PawnIO.Modules **0.2.11** here
(source: https://github.com/namazso/PawnIO.Modules/tree/0.2.11), verified against `MODULE_SHA256` in `pawnio.py`
at build time and again before loading. Copyright (C) namazso and module authors, LGPL 2.1 (`COPYING.LGPL`). The PawnIO driver is installed by the user from https://pawnio.eu; OptimaX talks to it only through
`DeviceIoControl`, as the PawnIO licence exception allows. The driver verifies each module's signature itself.
</details>
