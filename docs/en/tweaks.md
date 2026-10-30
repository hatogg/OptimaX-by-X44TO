# All OptimaX optimizations

[← Back to the main page](../../README.en.md) · [Українська](../uk/tweaks.md)

Generated from the program code (136 optimizations in 16 sections, version 6.4.3). Marks: 🔴 affects everyday habits, 🟡 moderate impact, 🔵 safe. “Rollback” tells whether OptimaX restores the change to your own original value.

Before applying, OptimaX checks compatibility with your hardware and Windows version: irrelevant items are disabled, items harmful to your PC (for example, turning off Game Bar on AMD X3D) are blocked, and the reason is shown under the item.

## CPU and memory

Power plan, core parking, priorities, page file, memory compression.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | Ultimate Performance power plan | Hidden Windows plan: turns off CPU power saving and keeps clocks at maximum. | Full, Medium, Xeon / X99 | yes |
| 🟡 | Disable processor idle (C-states) | The CPU never naps between tasks — lower DPC latency, but more heat. | Full, Xeon / X99 | yes |
| 🔵 | Disable core parking | All cores stay awake and never waste time waking up. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Disable Power Throttling | Windows stops capping CPU speed for background apps. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Aggressive Turbo Boost | The CPU ramps up to its top clocks faster and more often. | Full, Xeon / X99 | yes |
| 🟡 | 100% minimum processor state | Clocks never drop below base — server Xeons stop dozing off in games. | Xeon / X99 | yes |
| 🔵 | Lock the power plan | Drivers and Windows updates can't quietly switch your power plan. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Foreground window priority <sub>(Windows 11)</sub> | The app in front gets a bigger slice of CPU time. | Full, Medium | yes |
| 🔵 | Real-Time Thread Boost | The active app gets top priority and isn't pushed aside by background tasks. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Give resources to games (System Responsiveness) | The multimedia scheduler hands games as much CPU and GPU as possible. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Keep the Windows kernel in memory <sub>(restart)</sub> | Kernel and driver code is never paged to disk — lower latency. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Fixed page file (4–8 GB) <sub>(restart)</sub> | No fragmentation or resize stalls; cleared at shutdown. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Memory compression by RAM size <sub>(restart)</sub> | 32+ GB — compression off (plenty of RAM, less CPU work); up to 12 GB — on, so Windows pages to disk less. | Full, Medium, Laptop, Old PC, Xeon / X99 | yes |
| 🔴 | Turn off Spectre and Meltdown mitigations <sub>(restart, lowers security)</sub> | A noticeable boost on old Intel CPUs (up to 8th–9th gen), but the PC becomes more exposed to malicious sites and apps. Only if you accept the risk. | — | yes |

## Gaming

Game Bar, fullscreen, timers, mouse and keyboard, VRR, Auto HDR, GPU scheduling.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | Hardware-accelerated GPU scheduling (HAGS) <sub>(restart)</sub> | The GPU manages its own command queue — lower latency. Required for DLSS Frame Generation. | Full, Medium | yes |
| 🔵 | Turn on Windows Game Mode | The game gets priority and Windows Update stays out of the way while you play. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔴 | Turn off Xbox Game Bar and recording | Removes the background overlay and DVR capture — less input lag. Win+G will stop working. | Full, Medium, Xeon / X99 | yes |
| 🟡 | Disable fullscreen optimizations for all games | True exclusive fullscreen instead of the hybrid mode — lower latency in some games. | Full, Xeon / X99 | yes |
| 🔵 | Optimizations for windowed games <sub>(Windows 11)</sub> | Modern flip model for windowed and borderless games: lower latency and VRR support. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Precise 0.5 ms timer <sub>(restart)</sub> | 0.5 ms system timer instead of 15.6 ms — lower DPC latency, smoother frame times. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Disable Dynamic Tick <sub>(restart)</sub> | The timer ticks steadily instead of changing rate — less jitter. | Full, Medium, Xeon / X99 | yes |
| 🟡 | Forced HPET + TSC sync <sub>(restart, may lower FPS)</sub> | A hardware time counter. Steadier frame times on some PCs, lower FPS on others — test in your games. | — | yes |
| 🟡 | Turn off mouse acceleration | Linear cursor movement: every millimeter of motion covers the same distance on screen. | Full, Medium, Light, Old PC, Xeon / X99 | yes |
| 🔵 | Variable refresh rate (VRR) in windowed games <sub>(Windows 11)</sub> | G-Sync and FreeSync also work in games without their own VRR support — less tearing and judder. | Full, Medium, Xeon / X99 | yes |
| 🟡 | Auto HDR <sub>(Windows 11)</sub> | Windows adds HDR to older DirectX 11/12 games. HDR monitors only. | — | yes |
| 🟡 | Fast keyboard repeat | Minimum repeat delay and maximum rate — a held key reacts instantly in games and text. | Full | yes |

## Hardware and drivers

For your CPU and GPU: P/E-cores, MSI Mode, NVIDIA, AMD, VBS, PCIe, USB.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | Games on P-cores (Intel 12th–14th gen, Core Ultra) | Windows sends games to performance cores instead of efficiency cores; P-cores never park. | Full, Medium, Laptop | yes |
| 🟡 | MSI Mode for the graphics card <sub>(restart)</sub> | Message-signaled interrupts for the GPU — lower latency. Other devices are under Hardware. | Full | yes |
| 🔵 | Turn off NVIDIA telemetry | The NVIDIA driver's data collection service and tasks. Doesn't affect the GPU. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Turn off AMD ULPS <sub>(restart)</sub> | Radeon ultra-low power state sometimes causes stutter and black screens — turning it off. | Full, Medium, Xeon / X99 | yes |
| 🔴 | Turn off core isolation (VBS / HVCI) <sub>(restart, lowers security)</sub> | +5–15% FPS on some systems. Protection against vulnerable drivers will be off. | Full | yes |
| 🔵 | Turn off PCIe power saving | The GPU and NVMe drives never enter power saving — fewer micro-stutters. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Turn off USB selective suspend | Mice, keyboards and headsets stop dropping out or going to sleep. | Full, Medium, Laptop, Xeon / X99 | yes |

## Network

Ping, Nagle, buffers, adapter power saving, Wi-Fi and Ethernet for gaming.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | TCP/IP and DNS optimization <sub>(restart)</sub> | TCPNoDelay, a bigger DNS cache, window auto-tuning, RSS, DCA and a DNS flush. | Full, Medium, Laptop, Xeon / X99 | yes |
| 🔵 | Turn off Nagle's algorithm | Nagle bundles small packets and adds up to 200 ms of lag in online games. Turned off per adapter. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Network stack boost | Packet processing on all cores, data straight to CPU cache, TCP offload to the network card. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Remove network throttling | Windows stops holding back the network for multimedia. | Full, Medium, Laptop, Xeon / X99 | yes |
| 🔵 | Compound TCP | Uses bandwidth more efficiently; ECN is off for compatibility with most routers. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Turn off network adapter power saving <sub>(restart)</sub> | Energy Efficient Ethernet, Green Ethernet, Wi-Fi power saving and system power-off — lower ping, fewer drops. | Full, Medium, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Don't share updates with other PCs | Windows stops uploading updates to other computers online — your bandwidth and disk stay free. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔴 | Reset DNS and Winsock <sub>(restart)</sub> | Rebuilds the network stack — fixes problems after VPNs and antiviruses. One-time action. | — | no |
| 🔵 | Wi-Fi for gaming: less roaming <sub>(restart)</sub> | The adapter scans for other access points less often mid-game — fewer ping spikes. Best for a home with one router. | Full, Medium | yes |
| 🟡 | Ethernet: minimum latency <sub>(restart)</sub> | Turns off Interrupt Moderation and Flow Control — packets are handled at once. Slightly more CPU load. | Full | yes |

## Laptop

Plugged-in and battery power, heat, sleep that doesn't drain the battery.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | Full speed when plugged in | On the charger — maximum performance and aggressive Turbo. | Laptop | yes |
| 🔵 | Save power on battery | On battery — no Turbo, efficiency mode, battery saver from 30%. An extra 1–2 hours. | Laptop, Old PC | yes |
| 🟡 | Cool mode | Turns off Turbo Boost and spins fans up earlier — 10–20 °C cooler with almost no FPS loss. | — | yes |
| 🔵 | No network during sleep | Stops the laptop draining in your bag: network turns off in Modern Standby. | Laptop, Old PC | yes |
| 🔵 | No wake timers | Updates and tasks won't wake the laptop on battery. | Laptop, Old PC | yes |
| 🟡 | Classic sleep (S3) instead of Modern Standby <sub>(restart)</sub> | The laptop stops draining and heating up in a bag. Works only if the firmware supports S3 — otherwise just roll back. | — | yes |

## Lightweight

For weak and old PCs: animations, background apps, widgets, Defender, NTFS, Windows 10 clutter.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔴 | Visual effects for speed <sub>(sign out and in)</sub> | No animations, shadows or window transparency — like “Best performance” but with smooth fonts. | Old PC | yes |
| 🔴 | Turn off transparency | Taskbar and menus without the glass effect — less load on weak graphics. | Old PC | yes |
| 🔴 | Block background apps | Microsoft Store apps don't run in the background. Their notifications may arrive later. | Laptop, Old PC | yes |
| 🟡 | Turn off Widgets and news <sub>(sign out and in)</sub> | Removes the Widgets board (Windows 11) and News and interests (Windows 10). | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Stop Edge running in the background | Turns off Edge startup boost and background mode — a few processes and hundreds of MB freed. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Smart SysMain | Turns SysMain (Superfetch) off on SSDs and tunes prefetch on HDDs, where it speeds up launches. | Full, Medium, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Limit Defender to 20% CPU | Protection stays on, but scans don't slow the PC and only run when it's idle. | Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Remove startup delay | Startup apps launch right away, without Windows' artificial pause. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Don't record last access time (NTFS) <sub>(restart)</sub> | Opening a file no longer triggers a disk write — noticeable on HDDs. | Old PC | yes |
| 🔵 | No 8.3 short names (NTFS) <sub>(restart)</sub> | Windows stops creating an extra DOS-style name for every new file — faster in folders with thousands of files. | Old PC | yes |
| 🔵 | Remove News and interests <sub>(Windows 10)</sub> | Weather and news leave the taskbar and stop loading in the background. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Turn off Cortana <sub>(Windows 10)</sub> | The Cortana button disappears and the assistant stops running in the background. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Turn off Windows Ink Workspace <sub>(Windows 10)</sub> | The pen workspace no longer starts. Skip this if you draw with a pen. | Full, Medium, Old PC, Xeon / X99 | yes |
| 🔵 | Remove Meet Now <sub>(Windows 10)</sub> | The Skype Meet Now button leaves the taskbar. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |

## Windows 11: AI and ads

Copilot, Recall, Click to Do, AI in apps, Start recommendations, tips, Bing in search.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔴 | Turn off Copilot <sub>(Windows 11)</sub> | The Copilot button and pane go away and the Copilot key no longer opens it. The app itself can be removed under Built-in apps. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🟡 | Turn off Recall <sub>(restart, Windows 11)</sub> | Windows stops taking screen snapshots for its "memory" and removes the Recall component. Applies to Copilot+ PCs. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🟡 | Turn off Click to Do <sub>(Windows 11)</sub> | AI actions on screen content (Win + click) no longer start. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🟡 | No AI in Paint, Notepad and Settings <sub>(Windows 11)</sub> | Removes Cocreator, Generative fill and Image Creator in Paint, Notepad's AI features and the Settings AI agent. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🟡 | No Copilot in Edge | The sidebar and Copilot button go away; Edge stops reading pages for AI and offering to rewrite text. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | No Start recommendations <sub>(Windows 11)</sub> | Recommended no longer advertises apps and the account icon stops showing Microsoft prompts. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | No tips, suggestions or silent installs | Windows stops pushing tips, suggesting apps in Start and Settings, and silently installing promoted games and apps. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | No OneDrive ads in File Explorer | File Explorer stops showing "try OneDrive" and Microsoft 365 banners. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | No "Finish setting up your device" screen | After updates Windows no longer opens full-screen Microsoft 365, OneDrive and Game Pass offers. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | No fun facts on the lock screen | The lock screen shows only the picture — no tips or ads. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🟡 | Search without Bing <sub>(sign out and in)</sub> | Start search looks only for files and apps on the PC — faster, and nothing is sent to the web. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |

## Privacy

Telemetry, advertising ID, data collection and tracking tasks.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | Turn off telemetry and keylogger | DiagTrack and dmwappushservice services, typing and inking data collection. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Turn off ads and profiling | Advertising ID, diagnostic-based personalization and Cortana. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Turn off telemetry tasks, Copilot and Recall | 14 data-collection scheduled tasks, Copilot, Windows AI analysis and Recall. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🟡 | Turn off tracking tasks | Maps, Family Safety, location and the background app broker. | Full, Medium, Laptop, Old PC, Xeon / X99 | yes |

## File Explorer and taskbar

Classic context menu, fast folders, End task, less clutter in menus.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🟡 | Classic context menu <sub>(Windows 11)</sub> | The full right-click menu like Windows 10 — no "Show more options" step. | — | yes |
| 🔵 | End task on the taskbar <sub>(Windows 11)</sub> | Right-click a frozen app on the taskbar to close it without Task Manager. | — | yes |
| 🟡 | File Explorer opens to This PC | You see your drives right away instead of recent files and Home. | — | yes |
| 🔵 | Fast folders in File Explorer | Explorer stops guessing each folder's type (Music, Pictures) — huge folders open without the green loading bar. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔵 | Remove Gallery from File Explorer <sub>(Windows 11)</sub> | Gallery leaves the navigation pane — less background photo scanning. | — | yes |
| 🟡 | No recent files or frequent folders | Quick access stops listing what you opened recently — more private and a little faster. | — | yes |
| 🟡 | Less context-menu clutter | Removes Share, Give access to, Restore previous versions, Cast to Device and Ask Copilot. | — | yes |

## Windows Update

No driver swaps, no restarts mid-work, pause and version lock.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🟡 | No drivers from Windows Update | Windows Update stops replacing your GPU or audio driver with an older one. Update drivers from the vendor's site. | Full, Medium, Xeon / X99 | yes |
| 🔵 | No restarts while you're signed in | Windows won't restart on its own mid-game or mid-work; it waits until you sign out. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |
| 🔴 | Pause updates for 5 weeks | No updates for 35 days — handy before a tournament or deadline. Security patches wait too, so don't keep it paused forever. | — | yes |
| 🟡 | Lock the current Windows version | Windows stays on its current version (e.g., 24H2) and gets only security patches — no big feature updates that reset settings. | — | yes |

## Audio

Lower audio latency and no game ducking during calls.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🟡 | Turn off audio enhancements | No driver "enhancements" (virtual surround, EQ) — lower latency and less crackling. If the sound gets worse, roll back. | Full, Medium | yes |
| 🔵 | Don't lower volume during calls | When someone talks in Discord or Teams, the game and music stay at full volume. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |

## System

Defender, OneDrive, classic photo viewer, fast startup.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔴 | Turn off Windows Defender <sub>(restart, risky)</sub> | Only if another antivirus is installed. Otherwise the PC is left unprotected. | — | yes |
| 🔴 | Remove OneDrive <sub>(removes the app)</sub> | Uninstalls OneDrive, removes it from Explorer and blocks reinstallation. | — | yes |
| 🔵 | Turn off Fast Startup | Shut down really powers off: fewer driver glitches, proper dual boot, updates install correctly. On an SSD the boot-time difference is barely noticeable. | Full, Medium, Xeon / X99 | yes |
| 🔵 | Classic photo viewer | Brings back the fast Windows Photo Viewer for JPG, PNG, BMP, GIF and TIFF. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | yes |

## Services

Background services and search indexing.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🟡 | Turn off unneeded services | Turns off Windows services most people don't need: telemetry, error reporting, fax, retail demo, offline maps, remote registry, location, wallet. PC and laptop maker services, drivers, anti-cheats and VPNs are left alone. | Full, Medium, Old PC, Xeon / X99 | yes |
| 🔴 | Turn off search indexing | The drive isn't scanned in the background. Searching files from Start gets slower. | Full, Medium, Laptop, Old PC, Xeon / X99 | yes |

## Disk space

Windows compression, hibernation file, reserved storage.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | Compress Windows (Compact OS) <sub>(takes time)</sub> | Frees 2–4 GB on small SSDs and eMMC. Takes 10–30 minutes; speed barely changes. | Old PC | yes |
| 🔴 | Turn off hibernation | Deletes hiberfil.sys (nearly the size of your RAM). Hibernate and Fast Startup go away. | Old PC | yes |
| 🔵 | Turn off reserved storage | Gives back the ~7 GB Windows keeps aside for updates. | Old PC | yes |

## Maintenance

One-time actions: cleanup, disk and driver checks.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | Clear RAM | Frees cached memory (standby and modified) like RAMMap. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | no |
| 🔵 | Check disk (CHKDSK) <sub>(restart)</sub> | Checks and repairs the file system at the next restart. | — | no |
| 🔵 | Clean device data | Resets UserAssist and rescans devices. | — | no |
| 🔵 | Check drivers | Lists devices with errors in the log. | — | no |
| 🔵 | Clear registry history | Recent documents, Run, typed paths, UserAssist, ShellBags. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | no |
| 🔵 | Deep junk cleanup | Windows Update and Edge caches and temporary files, up to a minute. Old update copies (WinSxS) are a separate action under Cleanup because they take long on laptops. | Full, Medium, Light, Laptop, Old PC, Xeon / X99 | no |

## Built-in apps

Remove unneeded Windows 10 and 11 apps: from Clipchamp and Teams to Copilot.

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔴 | Remove 3D Builder <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove Camera <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove Mail, Calendar and Maps <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove Money and Sports <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove Groove and Movies & TV <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove People and OneNote <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove Phone Companion and Photos <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove Solitaire Collection <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove Voice Recorder <sub>(irreversible)</sub> |  | — | no |
| 🔴 | Remove Xbox (all components) <sub>(breaks Xbox game sign-in)</sub> |  | — | no |
| 🔴 | Remove Clipchamp <sub>(irreversible)</sub> | Microsoft's video editor, including its context-menu entry. | — | no |
| 🔴 | Remove News, Weather and Bing <sub>(irreversible)</sub> | The Microsoft News, Weather and Bing Search apps. | — | no |
| 🔴 | Remove Teams (personal) <sub>(irreversible)</sub> | The free Teams that starts with Windows. A work Teams from your company is left alone. | — | no |
| 🔴 | Remove the new Outlook <sub>(irreversible)</sub> | The Outlook (new) app that replaced Mail. | — | no |
| 🔴 | Remove Dev Home <sub>(irreversible)</sub> | A developer dashboard most people don't need. | — | no |
| 🔴 | Remove Microsoft To Do <sub>(irreversible)</sub> | Microsoft's to-do list app. | — | no |
| 🔴 | Remove Microsoft Family <sub>(irreversible)</sub> | Parental controls. Keep it if you use them. | — | no |
| 🔴 | Remove the Copilot app <sub>(irreversible)</sub> | The Copilot app itself. You can get it back from the Microsoft Store. | — | no |
| 🔴 | Remove Quick Assist <sub>(irreversible)</sub> | Microsoft's remote help. Scammers often ask people to open it. | — | no |
| 🔴 | Remove Feedback Hub <sub>(irreversible)</sub> | Microsoft's feedback app. | — | no |
| 🔴 | Remove Tips and Get Help <sub>(irreversible)</sub> | The Tips (Get Started) and Get Help apps. | — | no |
| 🔴 | Remove Power Automate <sub>(irreversible)</sub> | Office task automation. | — | no |
| 🔴 | Remove the Cortana app <sub>(irreversible)</sub> | The Cortana assistant (Windows 10 and early Windows 11). | — | no |

## Appearance

| | Optimization | What it does | Profiles | Rollback |
| --- | --- | --- | --- | --- |
| 🔵 | Remove shortcut arrows | Clean icons without the arrow. | — | yes |
| 🔵 | Show file extensions | .exe, .mp4 and other extensions are always visible. | — | yes |
| 🔵 | Show hidden files | Folders and files with the Hidden attribute. | — | yes |
| 🔵 | Windows dark mode | Dark theme for the system and apps. | — | yes |
| 🔵 | Turn off Aero Shake | Shaking a window no longer minimizes the others. | — | yes |
| 🔵 | Fast Alt+Tab and menus | No window animations or menu and preview delays. | — | yes |
| 🔵 | Turn off Sticky Keys | No Sticky Keys prompt after pressing Shift five times. | — | yes |
| 🔵 | Mouse selection color | The file selection box and fill. | — | yes |
| 🔵 | Selected text color | Text color inside a selection. | — | yes |
