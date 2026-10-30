# OptimaX guide

[← Back to the main page](../../README.en.md) · [Guide](guide.md) · [All optimizations](tweaks.md) · [FAQ](faq.md) · [For developers](development.md) · [Українська](../uk/guide.md)

Everything the program can do, from the first analysis to the emergency rollback. The full list of changes is in [All optimizations](tweaks.md), answers to common questions are in the [FAQ](faq.md).

## Contents

- [How it works](#how-it-works)
- [What other optimizers don't have](#what-other-optimizers-dont-have)
- [Sections of the program](#sections-of-the-program)
- [Optimization modes](#optimization-modes)
- [Profiles](#profiles)
- [Smart optimization](#smart-optimization)
- [Emergency rollback](#emergency-rollback)
- [Benchmarks](#benchmarks)
- [Mining graphics card (P106, P104, CMP)](#mining-graphics-card-p106-p104-cmp)
- [Ad blocker (like Pi-hole)](#ad-blocker-like-pi-hole)
- [Result card](#result-card)
- [Installation](#installation)
- [Safety and rollback](#safety-and-rollback)
- [System requirements](#system-requirements)

## How it works

1. **Analysis.** OptimaX detects the CPU (including P/E cores, AMD X3D and Xeon), graphics cards, memory, drives, monitor and battery, and shows the optimization and privacy levels, the speed-up potential and the weakest spot of the build.
2. **Choose a path.** The *Wizard* asks a few simple questions and builds a plan for you. The *Expert menu* has 136 optimizations in 16 sections, each with an explanation, its current state and the exact list of changes.
3. **Review the changes.** Before anything is applied, the plan is colour-coded: red affects everyday habits, yellow is a moderate change, blue is safe.
4. **Apply.** First a Windows restore point, then the changes with a console, progress and a Stop button. Optionally, **Trial mode**: after a restart OptimaX asks whether to keep the changes and puts everything back if nobody answers.
5. **Check.** The **Before/after FPS test** shows whether things really got better, and **Why is it lagging?** explains what slows a game down. **Smart optimization** does this on its own: it measures before and after, keeps only what helped and finds a harmful change by splitting the changes in halves, then removes it.
6. **Rollback and guard.** Every change is written to a journal and restored to *your* original value. The **Settings guard** notices when a Windows update brings back ads, Copilot or telemetry and offers to apply your settings again.
7. **Emergency rollback.** If the PC crashes with a blue screen or freezes after the changes, OptimaX offers to roll back the latest batch. The **OptimaX-Rescue.cmd** file rolls everything back even from Safe Mode, without starting the program.

OptimaX won't let you turn on something that harms your particular hardware. For example, on AMD Ryzen 7950X3D / 7900X3D / 9950X3D / 9900X3D it blocks turning off Game Bar, core parking and Ultimate Performance: the AMD driver relies on them to keep games on the 3D V-Cache die.

## What other optimizers don't have

| Feature | What it does |
| --- | --- |
| **Why is it lagging?** | Watches the CPU, GPU, memory, video memory, disk, temperatures and background processes for 30–120 seconds while you play, then explains in plain words: overheating and throttling, CPU bottleneck, not enough memory, a background app eating the CPU, disk at 100% |
| **Before/after FPS test** | Average FPS, 1% and 0.1% lows, stutters and a frame-time graph through PresentMon (Intel, MIT). If things got worse, one button rolls back the changes made between the two measurements |
| **Settings guard** | After Windows updates and every 6 hours it checks that your changes still apply; anything Windows reverted is applied again with the same backups |
| **Trial mode** | Changes last until a restart; then OptimaX asks whether to keep them and rolls them back if there is no answer within 2 minutes |
| **Cores for each game** | Pins the game to the 3D V-Cache die on Ryzen X3D, to the P-cores on Intel 12th–14th gen and Core Ultra, and to one NUMA node on dual-socket Xeons |
| **Background balancer** | Like ProBalance in Process Lasso, but free: while you play it lowers the priority of apps that suddenly load the CPU, then restores it |
| **Refresh rate by power source** | 60 Hz on battery, the maximum on the charger |
| **Build check** | Monitor plugged into the motherboard, graphics card running at PCIe x4/x8, Resizable BAR off, SSD wear and temperature, games on an HDD, overheating at idle |
| **Forum report** | Hardware, build check, changes, diagnostics and tests in one HTML file or as text for a chat |
| **Own GPU test and stress test** | A heavy 3D scene with a score, 1% lows and a before/after comparison; every 10 seconds the stress test compares a check frame bit for bit, so an unstable overclock or undervolt shows up, not only overheating |
| **Ad blocker like Pi-hole** | A DNS filter right on your PC: statistics, query log, StevenBlack/HaGeZi/OISD lists, encrypted DNS, protection for the whole home network, without a Raspberry Pi or a separate server |
| **Smart optimization (A/B)** | Measures FPS before and after and keeps only what helps; if things got worse it finds the culprit by splitting the changes in halves and removes it. It can also check changes applied earlier |
| **Emergency rollback** | Watches for blue screens, crash restarts and graphics driver failures after the changes and offers to roll back exactly that batch. OptimaX-Rescue.cmd rolls everything back from Safe Mode without the program |
| **Result card** | An image for social networks and forums: FPS before/after, Windows boot time, processes, memory, services, ping, blocked ads. Only numbers that were actually measured |
| **Tested on real Windows** | Before every release, CI on clean Windows Server 2022 and 2025 applies every tweak, checks that it worked, rolls it back and checks that everything returned exactly, and once more as a batch through OptimaX-Rescue.cmd |

## Sections of the program

| Section | What's there |
| --- | --- |
| **Analysis** | Optimization and privacy levels, speed-up potential, weakest spot, your PC, build check, live readings, before and after with a card for social networks, notices from the settings guard, trial mode and emergency rollback |
| **Optimization** | Wizard and Expert menu, 6 profiles, search, 16 sections, “What will change” for every item, colour-coded review before applying, trial mode, smart optimization |
| **Games** | Game mode (services, background apps, memory, power, timer, Do Not Disturb, background balancer, auto mode); per game: priority, discrete GPU, no Fullscreen Optimizations, cores; an ISLC-style memory cleaner; 0.5 ms timer; on a PC with a mining card — “Games on the P106” (every game on the card, OpenGL via Mesa) |
| **Diagnostics** | Why is it lagging?, before/after FPS test with a graph, forum report |
| **Benchmarks** | Smart optimization (an A/B test of changes on the GPU test or your game), OptimaX GPU test (1080p, 1440p, 4K), 5–60 minute stress test with a stability check and sensors, result history; FurMark 2 with an automatic result, Superposition, Cinebench, OCCT, CrystalDiskMark, 3DMark |
| **Hardware** | Specifications, build check with fix buttons, MSI Mode for graphics, network and audio devices, GPU overclocking (a prompt for DeepSeek, MSI Afterburner) |
| **Laptop** | Battery wear, power on AC and battery, cool mode, sleep without drain, classic S3 sleep, refresh rate by power source, charge limit (ASUS and Dell right from the program, for other makers where to find it in their utility) |
| **Network** | Fastest DNS (Cloudflare, Google, Quad9, AdGuard, OpenDNS against yours) with DNS-over-HTTPS, ping and jitter to 12 data-centre regions and to your own server, bufferbloat test graded A+…F |
| **Ad blocker** | A Pi-hole-style DNS filter: 24-hour statistics, query log, top blocked domains, devices, 13 lists, custom rules, pause, whole-network mode; light mode with AdGuard DNS or Control D in one click |
| **Cleanup** | Cleanup and repair, shader cache, freeing space; the “What takes up space” tab (disk analyzer) and “Old drivers” (old versions in the driver store) |
| **Apps** | Update all apps through winget, install popular apps for gaming and work |
| **Startup apps** | Apps from the registry, startup folders and Task Scheduler, with switches |
| **Appearance** | File Explorer and taskbar (classic context menu, End task, fast folders…), selection colours |
| **Backups** | Change journal with rollback, emergency rollback and OptimaX-Rescue.cmd, settings guard, Windows restore points, settings profiles |
| **Settings** | Language, tray, autostart, scheduled maintenance, hotkeys (Ctrl+Alt+G for game mode, Ctrl+Alt+M to clean memory) |

## Optimization modes

The Modes tab on the Optimize page. A mode is not a fixed list: the plan is built for your PC.

| Mode | For whom | What it considers |
| --- | --- | --- |
| **Safe** | Minimal risk | Only low-risk changes, each one reversible; services, power and drivers stay untouched |
| **Gaming** | Max FPS, with proof | The profile for your hardware + what limits FPS: on a GPU-bound PC CPU tweaks are skipped; on an overheating one, nothing that adds heat. After applying, it measures and removes what hurts |
| **Low-end PC** | Little RAM, an HDD, old hardware | Frees RAM and disk; if the diagnosis sees RAM or disk running short, it adds changes for exactly that |
| **Manual** | Full control | The expert menu with nothing preselected |

**What limits FPS** comes from “Why does it lag?” or from the in-game FPS test (the diagnosis runs alongside the frame capture); the newest result is used. A limit counts only if it held for at least half of the measurement.

**What smart optimization proved on this PC:** a change found harmful is never offered in any mode; a change that twice showed no effect beyond the measurement error is not offered in Gaming. Under each mode, “Left out” lists every excluded change with the reason.

## Profiles

| Profile | For whom |
| --- | --- |
| **Full** | A gaming PC, maximum FPS: CPU, GPU, network, timers. Leaves Defender and OneDrive alone |
| **Medium** | Most people: a balance of speed and stability |
| **Light** | A first try: only safe cleanup and privacy |
| **Laptop** | Laptops: full speed on the charger, saving on battery, no aggressive CPU tweaks |
| **Old PC** | 2–4 GB of memory, an HDD, Celeron / Pentium: no animations or background apps, frees up space |
| **Xeon / X99** | Server CPUs on Chinese X99 / X79 boards: aggressive Turbo, 100% minimum processor state |

The recommended profile for your PC is marked automatically.

## Smart optimization

A regular optimizer applies everything and hopes for the best. Smart optimization checks:

1. **Measure before**, three times: the median (one bad run can't shift it) and how much results vary on your PC — the measurement error.
2. **Apply** the plan. If it contains changes that work only after a restart, OptimaX asks you to restart and continues on its own after you sign in.
3. **Measure after**, also three times. A gain counts as proven only if it exceeds the measurement error (95%, depending on the number of runs). Better: the changes stay. Worse, or “hidden worse” (some changes help while one hurts): the search starts. No proven gain: one button removes the performance changes with no effect.
4. **Find the culprit by halving:** temporarily turn off half of the changes, measure, compare. A few measurements are enough to find one or two harmful changes among 20–40; they are removed and the rest stay. A difference within the error (at least ±2%) doesn't count as harm; on pure noise a false “better” or “found harm” happens in no more than ~5% of sessions.

You can measure with the **OptimaX GPU test** (30 seconds, 1280×720, lighter quality) or with **your own game** through PresentMon (45 seconds, just play as usual). **Check my changes** does the same with what you applied earlier. Stopping in the middle of the search brings back everything that was turned off temporarily.

Turn it on with the “Smart optimization — measure before and after” switch on the review screen, or from the card at the top of the Benchmarks section.

## Emergency rollback

After every batch of changes OptimaX watches the Windows event log for three days: a blue screen (event 1001), a crash restart or power loss (41, 6008), a graphics driver failure (4101). If that happens after the changes, a red banner appears on Analysis, and after you sign in to Windows OptimaX asks on its own: **“Roll back these changes?”** Only the latest batch is rolled back; the “It wasn't OptimaX” button dismisses the warning.

**OptimaX-Rescue.cmd** is a plain command file that OptimaX rewrites after every change. It contains all rollback commands from the journal (`reg`, `sc`, `schtasks`, `powercfg`, `bcdedit`, PowerShell) and needs neither Python, nor Qt, nor the program itself.

**If Windows doesn't start normally:**

1. Interrupt the boot three times with the power button, or hold Shift and click Restart on the sign-in screen.
2. Troubleshoot → Advanced options → Startup Settings → Restart → **4** (Safe Mode).
3. Open `C:\ProgramData\OptimaX\rescue\OptimaX-Rescue.cmd` (or the “OptimaX — Emergency rollback” shortcut in the Start menu).
4. Choose **1** for the latest batch of changes or **2** for everything OptimaX changed. Restart.

Without the menu: `OptimaX-Rescue.cmd /last` or `/all` (the exit code is the number of failed steps). When OptimaX starts again it sees what the file has already rolled back and removes those entries from the journal.

## Benchmarks

The **OptimaX GPU test** is a scene of its own: a neon city with the OptimaX logo, ray tracing in a fragment shader, soft shadows, reflections and glow. The test runs as a separate process in its own window (Esc stops it), so even a graphics driver crash won't close the program.

| Mode | What is measured |
| --- | --- |
| **Benchmark** (1 min, 1080p / 1440p / 4K) | Score = average FPS × 100, minimum FPS, 1% low, temperature, clocks and power draw (NVIDIA). The scene renders at a fixed resolution whatever the window size, so results are comparable |
| **Stress test** (5, 15, 30, 60 min) | Every 10 seconds a check frame that matches bit for bit on a healthy card. Verdict: stable / rendering errors / overheating / clocks dropping (from sensors and FPS drops) / driver crash |

Every result is kept in the history with the percentage against the previous run of the same test and the number of OptimaX changes between them, so you can see what the optimization gave.

**Other benchmarks** install through winget and start in one click: FurMark 2 (OptimaX runs the benchmark and reads the score, FPS and temperature), Unigine Superposition, Cinebench R23, OCCT, CrystalDiskMark and 3DMark (through Steam).

## Mining graphics card (P106, P104, CMP)

Mining cards (P106-090/100, P104-100/101, P102-100, CMP 30HX–170HX) have no video outputs: the monitor is plugged into the motherboard, the integrated graphics show the picture and, unless told otherwise, render the games too. When OptimaX sees such a card, the **Games** page gets a “Games on the P106-100” section (with your card's model):

- **Find and assign games.** OptimaX finds installed games (Steam, Epic, GOG, Ubisoft and My games) and assigns every one of their exe files to the mining card — the same as “High performance” in Settings → System → Display → Graphics, but for all games at once. Your own choice in Graphics settings is never overwritten. Old DirectX 9 and Adobe AIR games stay on the integrated graphics: on mining cards with patched drivers they blue-screen. The “Assign new games automatically” switch checks for new games every 15 minutes.
- **OpenGL via Mesa.** Windows Graphics settings don't apply to OpenGL — such games (and the OptimaX GPU test) render on whichever card shows the picture. The workaround is [Mesa](https://mesa3d.org): it translates OpenGL to DirectX 12, which Windows can hand to the mining card. Mesa downloads in one click from the OptimaX release (checked against SHA256SUMS.txt) and is enabled per game: the libraries go into the game folder, and any file that was already there is set aside and restored by rollback. Online games with anti-cheat may refuse to start with a foreign opengl32.dll — don't enable Mesa for those. Restart the launcher (Steam etc.) after enabling it.
- **GPU test on the card.** With Mesa downloaded, the OptimaX GPU test and smart optimization render on the mining card instead of the integrated graphics. Mesa scores are compared only with other Mesa scores.
- **Revert all** removes every assignment and the Mesa libraries; each change is also in the Backups journal and in OptimaX-Rescue.cmd.

## Ad blocker (like Pi-hole)

OptimaX runs its own DNS server on `127.0.0.1:53` (the “OptimaX DNS” scheduled task as SYSTEM, starting with Windows) and sets it as the DNS server of your network adapters.

- Domains from the lists get `0.0.0.0` / `::`, so ads, trackers and malicious sites don't load in any app.
- Allowed queries go to Cloudflare, Quad9, Google or AdGuard **encrypted (DNS-over-HTTPS)** and are cached. If the network blocks DoH, the filter switches to plain DNS on its own.
- Home network names (router, NAS, printer, `*.lan`, `*.home.arpa`, your company domain) and hotel captive portals go to the router's DNS.
- Firefox gets the `use-application-dns.net` canary, so it doesn't bypass the filter with its own DoH.
- **Safe for your internet:** the router's DNS is the adapter's second DNS server, so if the filter stops, Windows switches to it. Your previous DNS servers are saved and restored when you turn the filter off (and when you uninstall the program).
- **For the whole network:** the filter can answer phones, TVs and consoles (only from private addresses); the firewall rule opens only for private networks.

The panel: queries and blocked queries for 24 hours, the blocked share, response speed and cache, top blocked domains and devices, a log of the last 3000 queries with Allow / Block buttons, a pause from 5 min to 4 h, custom rules (`*.example.com`, patterns), choice of lists and weekly list updates.

| List | What it blocks | By default |
| --- | --- | --- |
| StevenBlack Unified | ads and malicious sites (the classic Pi-hole list) | yes |
| HaGeZi Multi PRO | ads, trackers, analytics, scams | yes |
| URLhaus | sites that spread malware | yes |
| OISD Big, AdGuard DNS filter | additional large ad lists | no |
| HaGeZi Threat Intelligence | phishing, malware, fraud (≈600k domains) | no |
| HaGeZi Windows/Office, Smart TV, Xiaomi/Huawei/OPPO/vivo, TikTok | device telemetry | no |
| HaGeZi Gambling, Social, StevenBlack Adult | unwanted content | no |

The default set is ≈280k domains, ≈26 MB of memory, and a domain check takes a few microseconds.

**Light mode** has no background process: Windows simply gets a DNS server that blocks ads itself (AdGuard DNS, AdGuard DNS Family, Control D), with DNS-over-HTTPS if you like. One button turns it off, and your previous DNS servers come back from the change journal.

> A DNS filter doesn't remove ads on YouTube and Twitch (they come from the same servers as the video) or ads built into the page itself. For those you need the [uBlock Origin](https://ublockorigin.com/) extension.

## Result card

The **Share the result** button on the Before and after card (Analysis) and in the Benchmarks results creates a 1200×675 image (PNG at double resolution). The main number is FPS before → after in your game, in smart optimization or in the GPU test, plus up to four tiles: Windows boot time, processes, memory, services, ping, blocked ads. The card shows only what OptimaX actually measured; the hardware line (CPU, GPU, memory) can be hidden. **Save PNG** or **Copy**, then paste it into Telegram, Discord or a forum.

## Installation

### Installer (recommended)

Run `OptimaX-Setup-<version>.exe`:

- the installer speaks Ukrainian, Russian or English, and the language you pick becomes the program's language;
- the program goes to `C:\Program Files\OptimaX` and appears in the Start menu together with the “OptimaX — Emergency rollback” shortcut, and on the desktop if you want;
- the “Start OptimaX with Windows” checkbox starts it minimized to the tray without a UAC prompt;
- OptimaX appears in Settings → Apps → Installed apps with its icon, version and publisher;
- a new installer over the old one updates the program and keeps your settings, games and change journal.

**Uninstalling** works through Settings → Apps or the Control Panel. The uninstaller asks:

1. *Roll back every change OptimaX made to your original values?* Yes rolls back every optimization in the journal; No keeps them in the system.
2. *Also delete OptimaX settings and the change journal?* No by default, so everything is in place if you install it again.

Either way the scheduled tasks (autostart, trial mode, maintenance, crash watch, smart optimization) are removed, game mode is turned off and the charge limit is reset. If you keep the changes, `C:\ProgramData\OptimaX\rescue\OptimaX-Rescue.cmd` stays too, so you can roll them back without the program.

Silent install for administrators: `OptimaX-Setup-<version>.exe /VERYSILENT /SUPPRESSMSGBOXES /TASKS="desktopicon,autostart"`.

### Portable version

`OptimaX-<version>-portable.exe` is a single file that runs without installation (from a USB stick, for example). It only downloads updates; it doesn't install them itself.

### One copy of the program

Starting OptimaX again doesn't open a second window; it shows the one already running, even if it's minimized to the tray.

### Updates

Once a day OptimaX checks GitHub for a new release. If there is one, a “new version is available” banner appears on Analysis and an Update button in Settings. The program downloads the installer, installs the new version silently and starts again. You can turn the check off in Settings.

The downloaded file runs only after verification: its SHA-256 must match the GitHub checksum and the release's `SHA256SUMS.txt` (when both exist they must agree), and its digital signature must not be broken. If OptimaX itself is signed, the update must be signed by the same publisher. The file is stored in `C:\ProgramData\OptimaX\updates` (regular apps can't write there) and checked again right before launch. If it fails, it doesn't run and OptimaX offers the release page.

## Safety and rollback

- A Windows restore point before every apply.
- Every change goes to the journal `%APPDATA%\OptimaX\back.json` and is restored on the Backups tab to your original value. Rollback goes strictly from newest to oldest, so even if two tweaks changed the same value, it returns to the original.
- The rollback record reaches the disk **before** the change (`back.pending.json`). If OptimaX crashes in the middle of a change, it reverts what had already changed on the next start and offers to roll back the interrupted batch. An error in the middle of an item reverts what that item had changed at once.
- The previous journal version is `back.json.bak`; a damaged journal is set aside as `back.json.corrupt-…` and restored from the copy. If the journal can't be written, OptimaX changes nothing.
- Before its first change OptimaX saves a snapshot of your original Windows settings (`baseline.json`). Backups → Original Windows settings finds OptimaX changes missing from the journal and reverts them.
- Conflicting changes are never applied together; without administrator rights, system-wide settings are skipped with an explanation.
- `C:\ProgramData\OptimaX\rescue\OptimaX-Rescue.cmd` duplicates the journal as Windows commands and rolls everything back without the program, also from Safe Mode. After changes OptimaX watches for blue screens and crash restarts for three days.
- Smart optimization removes changes after which FPS dropped, and brings back what it turned off temporarily if you stop the search.
- Trial mode rolls the changes back on its own if you don't confirm them after a restart.
- Game mode is temporary: if the program was closed by a crash, the next start restores services, the power plan and notifications.
- The only things not rolled back are one-off actions (cleanup, CHKDSK, removing old drivers) and removing built-in apps, which you can reinstall from the Microsoft Store.
- The ad blocker saves the DNS servers of every adapter before changing them and restores them when you turn it off or uninstall the program; while the filter isn't running, Windows uses the router's DNS.
- `--dry-run` shows every command without changing anything.

## System requirements

| Item | Requirement |
| --- | --- |
| OS | Windows 10 (1809+) / Windows 11, 64-bit (on Arm64 through x64 emulation in Windows 11) |
| Rights | Administrator (the program asks on its own) |
| Python | 3.10+ (only to run from source or build) |
| Optional | PresentMon for the FPS test (OptimaX downloads it), winget for Apps |
