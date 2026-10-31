# FAQ

[← Back to the main page](../../README.en.md) · [Guide](guide.md) · [All optimizations](tweaks.md) · [FAQ](faq.md) · [For developers](development.md) · [Українська](../uk/faq.md)

**Why does it need administrator rights?** Changes in HKLM, services, bcdedit, powercfg and the PresentMon counters are impossible without them.

**Do I need to restart?** Some changes work right away, some after a restart. Those are marked, and a restart button appears in the console.

**Can I undo everything?** Yes: any single change in Backups, trial changes with one decision after a restart, the whole system through a restore point.

**Windows doesn't start after the optimization. What do I do?** Start in Safe Mode and run `C:\ProgramData\OptimaX\rescue\OptimaX-Rescue.cmd`; step by step in [Emergency rollback](guide.md#emergency-rollback). If Windows starts but crashes, OptimaX offers to roll back the latest batch of changes on its own.

**Why did smart optimization remove a tweak that “should have helped”?** Because on your PC FPS was lower with it than without it, and the difference was larger than the spread of the measurements. You can always apply it by hand in the Expert menu.

**Where does PresentMon come from?** It's an open-source Intel tool (MIT). OptimaX downloads the console version from the official GameTechDev/PresentMon releases on GitHub, and only after you confirm.

**Why isn't ping measured with ping?** Most game companies don't answer ICMP ping, so OptimaX measures the TCP connection time to the data centres where game servers run.

**Why are some items unavailable on my PC?** OptimaX turns off what doesn't fit your hardware or Windows version (for example, NVIDIA settings without an NVIDIA card, Windows 10 items on Windows 11) or what harms it (Game Bar on AMD X3D). The reason is written under the item.

**Why does SmartScreen say “Unknown publisher”?** The installer isn't signed with a code signing certificate. Click More info → Run anyway, or sign the build with your own certificate ([Code signing](development.md#code-signing)).

**How do I update the portable version?** Download the new file from the release and replace the old one. Settings are kept separately in `%APPDATA%\OptimaX`.

**Is the stress test safe?** It loads the graphics card the same way a heavy game does, and the card's own overheating protection always works. You can stop the test any time with Esc. On laptops it's better to test on the charger and on a flat surface.

**Why doesn't my GPU test result look like 3DMark?** It's a different scene and a different API (OpenGL). OptimaX scores are for comparing your PC before and after, not with the tables of other benchmarks.

**What happens to my internet if the ad blocker stops?** Windows switches to the router's DNS as a fallback (except in strict mode), and OptimaX restarts the filter when it starts. Turning the filter off restores your previous DNS servers.

**A site or game stopped working after turning on the ad blocker?** Open Ad blocker → Query log, find the blocked domain and click Allow, or pause the filter for 5 minutes to check.

**How do I protect my phone and TV?** Turn on “Protect the whole home network” and set this PC's IP as the DNS server in the router or in the device's Wi-Fi settings. It works while the PC is on, so set an ordinary DNS server as the router's second DNS.

**Does it work on Windows 10?** Yes, from version 1809. Windows 11-only items are skipped on Windows 10, and the other way round; settings your build doesn't have yet are hidden too. On older Windows 10 builds the installer warns that they aren't tested and lets you choose whether to install.

**My antivirus or SmartScreen complains about OptimaX. Is it a virus?** No. Antiviruses often flag programs built with PyInstaller “just in case”, and OptimaX also changes the registry and services, exactly what antiviruses watch. All the code is open in this repository, and releases are built by GitHub Actions straight from it; file checksums are in `SHA256SUMS.txt` next to the release (`Get-FileHash OptimaX-Setup-<version>.exe` in PowerShell).

**My PC suddenly restarted or showed a blue screen. How do I find out why?** Diagnostics → Why did the PC crash? → Check: OptimaX reads the Windows log and explains what happened, what is usually to blame and what to do, and names the game if one was running. If memory is the suspect, Test memory is right there.

**Is the phone monitor safe?** The page only shows readings — it can't control the PC. It is reachable only from the home network and only through the link with its secret code (New code invalidates the old link), and the firewall rule applies to private networks only and is removed when the monitor is turned off. The page can't be opened over the internet.

**How much does it cost?** Nothing. OptimaX is open-source software under the MIT license: you can use, change and share it.

**Found a bug or have an idea?** Settings → Report a problem opens a GitHub issue with the version and system already filled in (no user name or personal paths), or open an [issue](https://github.com/hatogg/OptimaX-by-X44TO/issues/new/choose) yourself. Attach the forum report (Diagnostics → Report for a forum or technician) to a bug report: it has the hardware, Windows version and applied changes, with no personal data.
