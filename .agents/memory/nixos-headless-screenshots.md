---
name: Headless browser screenshots on NixOS
description: Working recipe for Playwright screenshots in the Replit/NixOS environment; which chromium binary to use and which to avoid.
---

# Headless browser screenshots on NixOS (Replit)

**Rule:** Drive Playwright with the system Nix chromium via `executable_path`,
never Playwright's bundled chromium, and never an `ungoogled-chromium` store path.

**Why:** Playwright's downloaded chromium fails on NixOS with missing shared
libraries (installing nspr/nss/mesa/gtk3 does not fix it). The
`ungoogled-chromium-98` store path segfaults on launch (`SIGSEGV`); older plain
chromiums can be very slow. `/nix/store/*-chromium-138*/bin/chromium` (plain,
non-ungoogled, highest version) works reliably.

**How to apply:**
- Select the binary by filtering out "ungoogled" and picking the highest
  *version*, not the lexicographically-last store path (hash prefixes make path
  sort order meaningless):
  `max((p for p in glob("/nix/store/*-chromium-*/bin/chromium") if "ungoogled" not in p), key=version_from_path)`
- Launch: `p.chromium.launch(executable_path=..., args=["--no-sandbox"])`.
- For Streamlit apps wait for `[data-testid='stAppViewContainer']`; detect
  errors via `[data-testid='stException']`; upload files by
  `locator("input[type='file']").set_input_files(...)`; Streamlit tab labels
  include emoji, so match with `get_by_role("tab", name=re.compile(...))`.
- Run long browser scripts with `python3 -u` in the background writing to a log
  file, then poll — a foreground pipe killed by ShellExec's timeout loses all
  buffered output and hides the failure point.
