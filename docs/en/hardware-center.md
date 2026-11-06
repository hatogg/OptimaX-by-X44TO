# Hardware Center

[← Back to the main page](../../README.en.md) · [Guide](guide.md) · [All optimizations](tweaks.md) · [FAQ](faq.md) · [For developers](development.md) · [Hardware Center](hardware-center.md) · [Українська](../uk/hardware-center.md)

Hardware Center is a page in the Device group that brings hardware diagnostics, tests and reports together. Sections open from the chips at the top of the page and are built only the first time you open them, so the program doesn't start any slower.

## Contents

- [Sections](#sections)
- [Result statuses](#result-statuses)
- [How the tests work](#how-the-tests-work)
- [FPS overlay](#fps-overlay)
- [Pre-purchase PC check](#pre-purchase-pc-check)
- [Reports](#reports)
- [Safety](#safety)
- [Limitations](#limitations)
- [What OptimaX already had and what was added](#what-optimax-already-had-and-what-was-added)

## Sections

| Section | What's there |
| --- | --- |
| **Overview** | The latest status of each check, plus Pre-purchase PC check and Create a report |
| **Hardware info** | CPU (architecture, cores and threads, hybrid cores, clock, SSE2…AVX-512), graphics cards, memory per slot (size, type, speed, maker, part number), motherboard, BIOS/UEFI and Secure Boot, disks, network adapters, monitors with EDID, battery |
| **CPU** | Single-core and all-core tests (scores to compare), a 1–60 min stress test: thermal throttling, power limit, unstable clocks, wrong results, crashes |
| **GPU** | The cards DirectX sees, the latest GPU test and stress test, graphics driver resets (TDR) in 30 days; the test itself lives on the Benchmarks page with the graphics card picker |
| **VRAM** | Writes and verifies patterns in GPU buffers on the chosen card |
| **RAM** | Six patterns in the free part of system memory, plus Windows Memory Diagnostic for a full check |
| **Storage** | SMART / NVMe for each disk (“what the disk reports”), a speed test, a sampled surface read and a read-only file system check (“what OptimaX confirmed”) |
| **Display** | Resolution, refresh rate and scaling of each screen, EDID, full-screen colors for dead and stuck pixels |
| **Laptop** | Battery (design vs full capacity, wear, cycles), power source, hybrid graphics, throttling from the latest CPU test |
| **Peripherals** | Keyboard, mouse (buttons and wheel), speakers (left and right channel), camera, microphone, network adapters |
| **Stress testing** | CPU only, GPU only, CPU + GPU, RAM, VRAM, storage — with sensors, charts and an emergency stop |
| **Background processes** | Who loaded the system during a game, whether their peaks matched FPS drops and what you can do; What limits performance and undervolting advice |
| **Windows diagnostics** | Blue screens, sudden shutdowns, TDR, WHEA, devices with driver errors; dump analysis via cdb.exe; SFC and DISM after confirmation |
| **Pre-purchase check** | A 14-step wizard with a comparison against the advertised configuration |
| **Reports** | HTML, JSON, PDF, preview, history, comparing two reports |
| **FPS overlay** | Overlay settings and recorded game sessions |

## Result statuses

| Status | Meaning |
| --- | --- |
| **PASS** | Passed |
| **WARN** | A warning (throttling, high temperature, wear, a slow disk) |
| **FAIL** | A problem (computation or memory errors, an emergency stop, a failing disk) |
| **SKIPPED** | Skipped or stopped |
| **N/A** | Hardware or feature unavailable |

Each result shows its findings in plain words, values and charts. “Demo, not real hardware” means the test ran on demo hardware outside Windows and says nothing about a real PC.

## How the tests work

- **CPU.** A separate process computes SHA-256 and BLAKE2b of a 1 MB block and compresses and decompresses data with zlib. Every result is checked against a reference (the majority of three computations), so an unstable overclock or undervolt shows up as “computed a wrong result”, not just “the CPU was busy”. The clock comes from `% Processor Performance`, the limit from `% Performance Limit`, thermal throttling from the thermal zones' `% Passive Limit`. Windows doesn't expose core temperatures without a sensor driver, so it shows N/A rather than an invented number. This is an integer load, not a replacement for Prime95 / OCCT with AVX.
- **RAM.** A separate process takes a share of free memory (at least 1.5 GB stays for Windows), writes and verifies patterns: zeros, ones, checkerboard, walking ones, random data and the block number inside each block (addressing errors). Programs can't safely take all the RAM — that's what Windows Memory Diagnostic is for.
- **VRAM.** A separate process creates an OpenGL context on the chosen card, allocates 64 MB buffers (until it reaches the share of free VRAM or the driver runs out), writes every buffer for each pattern, copies each one with the GPU into a check buffer and reads it back.
- **Disk.** Only its own temporary file in `X:\OptimaX-DiskTest`, bypassing the Windows cache (`FILE_FLAG_NO_BUFFERING`): sequential write and read in 1 MB blocks, random 4K at queue depth 1 (IOPS, latency). Free space is checked first (at least 2 GB must stay free after the file), and the file and folder are deleted after the test and when stopped. The surface read reads random areas of the physical disk for 30 seconds, read-only.
- **SMART / NVMe.** NVMe — the Health Information log (critical warnings, spare blocks, wear, data written, hours, power cycles, unsafe shutdowns, Media and Data Integrity Errors). SATA — SMART attributes and thresholds (reallocated, pending, uncorrectable sectors, CRC, hours, temperature, data written). USB disks — Windows reliability counters.
- **Emergency stop.** During stress tests the sensors are read every second; the CPU at 95 °C (thermal zone) or the GPU at 92 °C for three seconds in a row stops every test and the result is FAIL.
- **Stopping and timeouts.** Each test is a separate process: stopping asks it to exit (and clean up), and after 8–10 seconds it is terminated. A crash under load doesn't close the program; it is shown as a crash.

## FPS overlay

Turn it on in Hardware Center → FPS overlay. It shows FPS, 1% and 0.1% lows over the last 10 seconds, frametime, CPU and GPU load and temperature; the extended layout adds clocks, VRAM, RAM, power draw, the GPU rendering the game, the present mode and a frametime graph.

- **No injection.** Frames come from PresentMon (ETW) and the overlay is a separate transparent window: always on top, click-through, never takes focus and stays out of Alt+Tab. OptimaX puts nothing into the game process, so anti-cheats have nothing to see, but compatibility with every anti-cheat isn't guaranteed without testing.
- **Exclusive fullscreen** (present mode “Hardware: Legacy Flip”) covers external windows — OptimaX notices and suggests borderless. If the game moved from Independent Flip to Composed after the overlay appeared, OptimaX tells you once.
- **The game is found automatically**: the foreground window whose process is in the library, My games or the detected games, or an unknown program covering the whole monitor (except browsers, Explorer and players). There are allow and block lists.
- **Hotkeys** (pick a set; taken keys are reported): Ctrl+Shift+F10 shows / hides, Ctrl+Shift+F11 starts / stops session recording.
- **Session recording** saves a CSV of frames and a JSON report to `%APPDATA%\OptimaX\sessions`: FPS, 1% / 0.1% lows, stutters, sensors, background processes and the “what limits performance” verdict.
- Numbers update 4 times a second, sensors once a second; OptimaX's own load is shown in the overlay settings.

## Pre-purchase PC check

14 steps: specs → matches the advert (CPU, GPU, memory, storage — enter what the seller promises) → CPU → GPU → VRAM → RAM → disk health → disk speed → battery (laptop) → screen → keyboard → camera, microphone and audio → combined stress test → summary and report.

A step uses a test result made after the check started, so old runs don't mix in. You mark the visual steps yourself. On a laptop with two GPUs the GPU step needs two tests — discrete and integrated — and passes only if the discrete card actually rendered under load: a dead or disabled discrete GPU is the most common trick with used laptops.

## Reports

HTML (with charts), JSON and PDF (made with Qt, no new dependencies). A report has the hardware, BIOS, disks with SMART, temperatures under load, test results, errors and warnings, charts, the overall status and recommendations. The computer name is included only if you tick the box, the user name and profile paths are replaced, and OptimaX doesn't collect serial numbers. Reports are kept in `%APPDATA%\OptimaX\reports`; two reports can be compared (statuses and score change in percent).

## Safety

- No destructive disk tests, no formatting, no writes outside its own temporary file.
- No BIOS, voltage or undervolting changes — only advice with the reasons and how to check stability.
- No automatic process termination: background processes are only shown, with options for you.
- SFC, DISM and chkdsk run only after confirmation (chkdsk without switches is read-only).
- The Windows Graphics setting for the GPU test is set only with consent and through the rollback journal.
- cdb.exe and PresentMon are never installed without your consent (OptimaX only looks for cdb).

## Limitations

- **OptimaX doesn't ship cdb.exe.** Dump analysis works if Debugging Tools for Windows (Windows SDK) is installed; otherwise the cause is shown by the error code on the Why did the PC crash? page.
- Windows doesn't give CPU core temperatures without a sensor driver (LibreHardwareMonitor and the like) — N/A.
- VRAM and RAM are tested partly (Windows, the driver and apps use some of it).
- Per-process network data needs ETW — Background processes shows it for the whole system.
- The color gamut is an estimate from the EDID coordinates, not a colorimeter measurement.
- Real-hardware runs (P106-100, Intel HD, Optimus laptops, AMD Hybrid) still need the matching PCs; CI checks everything on demo hardware, Mesa OpenGL and Windows Server without a GPU.

## What OptimaX already had and what was added

| Capability | Before Hardware Center | Now |
| --- | --- | --- |
| Hardware information | Partly (Hardware, Laptop) | Extended: instruction sets, memory slots, BIOS/UEFI, EDID, network |
| CPU test | None (only third-party tools) | Added |
| GPU test and stress test | Yes | Fixed the card choice on hybrid laptops, checks who rendered |
| VRAM check | None | Added |
| RAM check | Only launching Windows Memory Diagnostic | Added its own check |
| SMART / NVMe | Partly (health, wear, temperature from Windows) | Added SMART attributes and the NVMe log |
| Disk speed test | Only CrystalDiskMark (third-party) | Added its own |
| Battery | Yes (wear, report) | Integrated with a verdict |
| Display | Primary monitor refresh rate | Added EDID, all screens, color test |
| Peripherals | None | Added |
| Combined stress test | None | Added |
| Process monitoring | Partly (balancer, Why is it lagging?) | Added background recording during games and FPS-drop correlation |
| Performance diagnosis | Yes (Why is it lagging?) | Extended: VRAM, integrated GPU, background, driver; confidence, risks |
| Undervolting | None | Added advice (no system changes) |
| BSOD analysis | Yes (by error code) | Added cdb.exe when installed |
| SFC / DISM | None | Added, with confirmation |
| Pre-purchase check | None | Added |
| Reports | Forum report | Added Hardware Center reports: HTML, JSON, PDF, history, comparison |
| FPS overlay | None (FPS recorded in the background only) | Added |

The audit also found and fixed a bug: NVIDIA sensors were never read in Why is it lagging? and the phone monitor, and Measure on a mining-card PC always failed (`Nvml.ok` was called as a function).
