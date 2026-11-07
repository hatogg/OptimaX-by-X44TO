# Code signing and privacy

[← Back to the main page](../../README.en.md) · [Guide](guide.md) · [All optimizations](tweaks.md) · [FAQ](faq.md) · [For developers](development.md) · [Українська](../uk/code-signing.md)

## Contents

- [Code signing policy](#code-signing-policy)
- [Privacy](#privacy)
- [Turning signing on (for the repository owner)](#turning-signing-on-for-the-repository-owner)

## Code signing policy

OptimaX's Windows files (the installer, the portable version and `OptimaX.exe` itself) are signed with free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org). Signed releases start with the first release after SignPath Foundation approves the application; earlier releases are unsigned and have `SHA256SUMS.txt`.

- **What gets signed.** Only files built by GitHub Actions from this repository (`.github/workflows/release.yml`): first `OptimaX.exe` and the portable version, then the installer, which already contains the signed `OptimaX.exe`. Files built anywhere else are never signed.
- **Every signature is approved by hand** in SignPath, for each release separately.
- **Roles:**
  - committers (may change the code): [X44TO (@hatogg)](https://github.com/hatogg);
  - reviewers (review other people's changes before they are merged): [X44TO (@hatogg)](https://github.com/hatogg);
  - approvers (approve each signing request): [X44TO (@hatogg)](https://github.com/hatogg).
- Other people's changes reach the code only through a reviewed pull request.
- GitHub and SignPath sign-ins use two-factor authentication.

## Privacy

OptimaX collects and sends no personal data and no telemetry. It goes online only for its own features:

| What | Where | When |
| --- | --- | --- |
| Update check | `api.github.com` — this repository's release list | At start and at most once every 6 hours |
| Tool downloads | GitHub (PresentMon, Mesa and DXVK for mining cards), winget, ad-blocking lists | Only when you press the button or turn the feature on |
| Network tests | DNS servers (Cloudflare, Google, Quad9, AdGuard, OpenDNS), `speed.cloudflare.com`, data-centre regions | Only when you run a test |
| Dump analysis | Microsoft symbol server `msdl.microsoft.com` | Only while analysing a dump, if Debugging Tools for Windows is installed |
| Phone monitor | A server on your home network only | Only when you turn it on |
| Bug report | A new GitHub issue page in your browser | Only when you press Send yourself: you see the whole text, with the user name and profile paths removed |

OptimaX shows every system change before applying it, records it in a journal and can roll it back; the program can be removed from Windows' Apps & features.

## Turning signing on (for the repository owner)

1. Turn on two-factor authentication in GitHub.
2. Apply to SignPath Foundation for free open-source code signing ([terms](https://signpath.org/terms)) and wait for approval.
3. In SignPath, create the `OptimaX` project, connect GitHub as a trusted build system and add two artifact configurations with the slugs `app` and `installer` — their contents are in [`.signpath/artifact-configurations`](../../.signpath/artifact-configurations). The signing policy is `release-signing` with manual approval.
4. In GitHub → Settings → Secrets and variables → Actions, add the variable `SIGNPATH_ORGANIZATION_ID` and the secret `SIGNPATH_API_TOKEN` (other slugs go into the `SIGNPATH_PROJECT_SLUG` and `SIGNPATH_POLICY_SLUG` variables if they differ).
5. Run a release as usual: the “Code signing (SignPath)” job sends two requests, and each must be approved in SignPath (the job waits up to 3 hours). Without the `SIGNPATH_ORGANIZATION_ID` variable the release goes out unsigned, as before.
