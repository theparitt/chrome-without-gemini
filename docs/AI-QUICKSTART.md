# Runbook for AI assistants

User goal: remove Chrome's Ask Gemini context-menu entry and Gemini tab button,
or, if the user explicitly chooses button-only hiding, hide just that button.

This is a small local utility with no runtime network access. Downloading it is
a separate operation. A text-only assistant should give the platform's short
commands instead of claiming to have changed the user's computer.

## Execute on the user's computer

1. Read the current [README](../README.md), [CLI guide](CLI.md), and the small
   [`cli.py`](../chrome_without_gemini/cli.py),
   [`platforms.py`](../chrome_without_gemini/platforms.py), and
   [`core.py`](../chrome_without_gemini/core.py) sources to understand the actions.
   Detect the local OS and CPU architecture. Supported packaged targets are Windows
   x64, macOS 15+ arm64/x64, and Linux x64 with glibc 2.35+.
2. Query `https://api.github.com/repos/theparitt/chrome-without-gemini/releases/latest`.
   Download the exact matching **CLI** asset listed in [CLI.md](CLI.md) and
   `SHA256SUMS.txt` from that same release. Use a local working directory and follow
   download redirects. Do not substitute an executable from a third party.
3. Compare the downloaded file's SHA-256 to its exact filename's checksum line;
   stop if they differ. On Windows use `Get-FileHash -Algorithm SHA256`; on macOS
   `shasum -a 256`; on Linux `sha256sum`. Extract `.tar.gz` archives after verification.
   Archives preserve the executable permission. Do not disable OS protections if
   an unsigned app needs the user's per-app approval.
4. Run the standalone executable with `--help`, `--version`, and `status`.
   Windows executable: `chrome-without-gemini-cli-windows-x64.exe`.
   Extracted macOS/Linux executable: `./ChromeWithoutGeminiCLI`.
   No Python installation, virtual environment, pip packages, or compilation is needed.
5. Apply **one** relevant action:
   - **Remove both entry points on Windows:** run `disable`. If Windows denies
     access, explain the actual error and request elevation through the host's
     normal approval flow, using the same account. Keep the default recovery journal.
   - **Remove both on macOS:** run `export-macos-policy ChromeWithoutGemini.mobileconfig`.
     Open the file and guide the user to install **Chrome Without Gemini** in
     **System Settings → General → Device Management**. An existing export is not
     overwritten; choose a fresh filename if necessary. Profile installation needs
     the user's interactive step. Do not report an export as an applied policy.
   - **Remove both on Linux:** run `disable` to create the dedicated desktop launcher.
     Ask the user to save work and quit all Chrome processes, then use **Chrome
     (Without Gemini)**. This launcher fallback is experimental and affects only
     fresh starts made through it. Creating it does not alter a running Chrome session.
   - **Button-only on any supported OS:** ask the user to save work and quit Chrome
     completely, then run `hide-button`. This applies to all discovered profiles;
     use the GUI if they want to select profiles. Do not also disable the integration.
6. Verify what actually took effect:
   - Windows/macOS: after the user restarts Chrome, check `chrome://policy` for
     `GeminiSettings = 1`, status **OK**. Explain that local policy can add the
     "Managed by your organization" label.
   - Linux: in a fresh session started through the AI-off launcher, check
     `chrome://version` for `--disable-features=Glic` and check the UI. Other launchers
     are unchanged. Unsupported switches or Chrome updates may invalidate the fallback.
   - Button-only: after reopening Chrome, check that the button is hidden.
   - If you cannot inspect Chrome, report exactly what was saved/created and the
     outstanding verification step. Never infer effective removal from exit code alone.
7. Give the user the Undo command, using the same executable and Windows account:
   `restore-gemini` on Windows/Linux, `restore-button` for button hiding; on macOS,
   explain removal of the installed profile in System Settings. Keep `changes.json`
   for recovery. Do not delete it or replace its original values.

## Privacy and scope

Profile labels are generic. Do not include the user's account names, email,
full workstation paths, real preferences, recovery journal, or screenshots with
account information in public issues, commits, or pasted reports. Use generic labels
in the reply. Do not force-close Chrome, overwrite unrelated settings, change the
default browser, disable Chrome updates, or remove unrelated AI features.

The user's initial request authorizes the stated change. Proceed with ordinary
downloads and commands within that scope; ask only for a genuinely required
permission, an unsupported-platform decision, or the interactive macOS installation.
Respect the host assistant's own execution and approval rules.
