# CLI quick start

Download the **standalone CLI** from the
[latest release](https://github.com/theparitt/chrome-without-gemini/releases/latest).
You do not need to install Python, Git, or Tk, or compile the project.

| Platform | Release file |
| --- | --- |
| Windows 10/11 x64 | `chrome-without-gemini-cli-windows-x64.exe` |
| macOS 15+ Apple Silicon | `chrome-without-gemini-cli-macos-arm64.tar.gz` |
| macOS 15+ Intel | `chrome-without-gemini-cli-macos-x64.tar.gz` |
| Linux x64, glibc 2.35+ | `chrome-without-gemini-cli-linux-x64.tar.gz` |

For archives, extract first. The executable inside is `ChromeWithoutGeminiCLI`.
Run the commands from the folder containing the executable. See the main README
for unsigned-build information. The CLI performs no downloads or network requests;
you or your assistant download the release before running it.

## Windows: one action to disable Gemini and Google Lens

```powershell
.\chrome-without-gemini-cli-windows-x64.exe status
.\chrome-without-gemini-cli-windows-x64.exe disable
```

Save your work and restart Chrome. Open `chrome://policy` and verify
**GeminiSettings = 1** and **SearchContentSharingSettings = 1**, status **OK**.
The default now blocks both Gemini and Lens. No second hide command is needed.
Lens also blocks Chrome's AI Mode context-sharing entry points. Some Chrome builds
can retain ordinary image search or a fallback image-search label.
If access is denied, rerun from an administrator terminal using the same Windows
account. Chrome may show its local-policy management label.

Undo:

```powershell
.\chrome-without-gemini-cli-windows-x64.exe restore
```

## macOS: export, then install the profile

```bash
./ChromeWithoutGeminiCLI export-macos-policy ChromeWithoutGemini.mobileconfig
open ChromeWithoutGemini.mobileconfig
```

Install **Chrome Without Gemini** in **System Settings → General → Device Management**.
Restart Chrome and verify both selected policies, status **OK**, at `chrome://policy`.
Exporting alone does not disable Gemini. Installation requires an interactive
System Settings step; the CLI does not silently install profiles.

Undo by removing that profile in System Settings. The command
`./ChromeWithoutGeminiCLI restore` prints those instructions. To undo one block,
remove the combined profile and install a new export with only the feature you want
to keep blocked, using `--only gemini` or `--only lens`.

## Linux: create the AI-off launcher

```bash
./ChromeWithoutGeminiCLI disable
```

Quit every Chrome process, then launch **Chrome (Without Gemini)** from your desktop's
application menu. Check `chrome://version` for
`--disable-features=Glic,LensOverlay,LensStandalone` with the default selection.
This experimental fallback only affects starts through that launcher. It requires
standard Google Chrome stable and does not handle Flatpak, Snap, or Chromium.
Creating the launcher does not change an existing Chrome process. On a headless
machine, you can create the launcher but need a desktop session to use it.

Undo:

```bash
./ChromeWithoutGeminiCLI restore
```

Then fully quit Chrome and start it with your normal launcher.

## Choose just one integration

`disable` and macOS export select **Gemini + Lens by default**. Use `--only` to
limit an operation; an unselected integration is left unchanged.

```powershell
# Windows
.\chrome-without-gemini-cli-windows-x64.exe disable --only gemini
.\chrome-without-gemini-cli-windows-x64.exe disable --only lens
.\chrome-without-gemini-cli-windows-x64.exe restore --only lens
```

```bash
# Linux: disable just Lens, or undo just Lens while keeping Gemini blocked.
./ChromeWithoutGeminiCLI disable --only lens
./ChromeWithoutGeminiCLI restore --only lens

# Mac: export a profile containing just the Lens policy.
./ChromeWithoutGeminiCLI export-macos-policy LensOnly.mobileconfig --only lens
```

On Linux, adding a feature updates the same launcher. Selective Undo retains the
other feature's switches. Windows retains separate original values for both policies.
On macOS, installation/removal is at profile level, so selective Undo needs a replacement
profile. Do not assume exporting a new selection removes an older installed block.

## Hide only the top-right button

Quit Chrome completely first. This changes **all discovered Chrome stable profiles**.
Use the desktop app if you want to choose particular profiles.

```powershell
# Windows
.\chrome-without-gemini-cli-windows-x64.exe hide-button
.\chrome-without-gemini-cli-windows-x64.exe restore-button  # Undo
```

```bash
# Mac or Linux
./ChromeWithoutGeminiCLI hide-button
./ChromeWithoutGeminiCLI restore-button  # Undo
```

Hiding the button leaves the right-click menu and other Gemini entry points available.
The app refuses this edit while Chrome is running and never force-closes Chrome.

## Command reference

| Argument / command | Effect |
| --- | --- |
| `--help` | Show commands without changing anything |
| `--version` | Show the app version |
| `status` | Show the local control and generic profile labels; no changes |
| `disable [--only all\|gemini\|lens]` | Default: block both. Windows saves policies; Linux creates/updates the launcher |
| `restore [--only all\|gemini\|lens]` | Default: Undo both; macOS prints profile-removal instructions |
| `restore-gemini` / `restore-lens` | Undo only the named integration (macOS prints profile instructions) |
| `hide-button` | Hide the tab button in every discovered profile; Chrome must be closed |
| `restore-button` | Restore the original button settings; Chrome must be closed |
| `export-macos-policy FILE [--only all\|gemini\|lens]` | Export selected policies; default both, without installing |

Global options go **before** the command:

```bash
./ChromeWithoutGeminiCLI --chrome-root "/path/to/Chrome user data" status
```

`--state-root PATH` changes where the recovery journal is stored. Keep the same
state location for future Undo operations; the default is normally best. Keep
`changes.json` until you undo the changes. Exit code `0` means the command completed;
`1` means an operation failed; `2` means invalid command-line arguments. A successful
file export or launcher creation is not verification of effective Gemini removal.

## Use source instead (optional)

If Python 3.11+ and Git are already installed:

```bash
git clone https://github.com/theparitt/chrome-without-gemini.git
cd chrome-without-gemini
python -m chrome_without_gemini.cli --help
python -m chrome_without_gemini.cli status
```

On systems where Python is named `python3`, use that instead. No `pip install`
step is needed for the source CLI. Then use the same commands, such as
`python -m chrome_without_gemini.cli disable` on Windows/Linux, or
`python -m chrome_without_gemini.cli export-macos-policy ChromeWithoutGemini.mobileconfig`
on macOS.

The [AI runbook](https://github.com/theparitt/chrome-without-gemini/blob/main/docs/AI-QUICKSTART.md)
explains how a local assistant can download and run this for you.
