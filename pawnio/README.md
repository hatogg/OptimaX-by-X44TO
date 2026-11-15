# Модулі PawnIO

Тут під час збірки з'являються офіційні підписані модулі [PawnIO.Modules](https://github.com/namazso/PawnIO.Modules)
(`IntelMSR.bin`, `AMDFamily17.bin`, `SmbusI801.bin`, `SmbusPIIX4.bin`). CI бере їх з офіційного релізу; у репозиторії їх
немає (`*.bin` у `.gitignore`).

- Ліцензія модулів — GNU LGPL 2.1 (`COPYING.LGPL`), вихідний код — https://github.com/namazso/PawnIO.Modules
- Драйвер [PawnIO](https://github.com/namazso/PawnIO) користувач встановлює сам з https://pawnio.eu. OptimaX драйвер не
  ставить і спілкується з ним лише через `DeviceIoControl` — саме це дозволяє виняток у ліцензії PawnIO.
- Драйвер сам перевіряє підпис модуля, тож змінений файл він не завантажить.

<details><summary>English</summary>

The build drops the official signed [PawnIO.Modules](https://github.com/namazso/PawnIO.Modules) here. Modules are LGPL 2.1
(`COPYING.LGPL`). The PawnIO driver is installed by the user from https://pawnio.eu; OptimaX talks to it only through
`DeviceIoControl`, as the PawnIO licence exception allows. The driver verifies each module's signature itself.
</details>
