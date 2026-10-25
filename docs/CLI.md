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

## Windows: one action to remove both entry points

```powershell
.\chrome-without-gemini-cli-windows-x64.exe status
.\chrome-without-gemini-cli-windows-x64.exe disable
```

Save your work and restart Chrome. Open `chrome://policy` and verify
**GeminiSettings = 1**, status **OK**. Both the Ask Gemini context-menu item and
the tab button depend on this integration, so no second hide command is needed.
If access is denied, rerun from an administrator terminal using the same Windows
account. Chrome may show its local-policy management label.

Undo:

```powershell
.\chrome-without-gemini-cli-windows-x64.exe restore-gemini
```

## macOS: export, then install the profile

```bash
./ChromeWithoutGeminiCLI export-macos-policy ChromeWithoutGemini.mobileconfig
open ChromeWithoutGemini.mobileconfig
```

Install **Chrome Without Gemini** in **System Settings → General → Device Management**.
Restart Chrome and verify **GeminiSettings = 1**, status **OK**, at `chrome://policy`.
Exporting alone does not disable Gemini. Installation requires an interactive
System Settings step; the CLI does not silently install profiles.

Undo by removing that profile in System Settings. The command
`./ChromeWithoutGeminiCLI restore-gemini` prints those instructions.

## Linux: create the AI-off launcher

```bash
./ChromeWithoutGeminiCLI disable
```

Quit every Chrome process, then launch **Chrome (Without Gemini)** from your desktop's
application menu. Check `chrome://version` for `--disable-features=Glic`.
This experimental fallback only affects starts through that launcher. It requires
standard Google Chrome stable and does not handle Flatpak, Snap, or Chromium.
Creating the launcher does not change an existing Chrome process. On a headless
machine, you can create the launcher but need a desktop session to use it.

Undo:

```bash
./ChromeWithoutGeminiCLI restore-gemini
```

Then fully quit Chrome and start it with your normal launcher.

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
| `disable` | Windows: save policy. Linux: create launcher. macOS: explain profile export |
| `restore-gemini` | Restore this tool's original policy / remove launcher; macOS: removal instructions |
| `hide-button` | Hide the tab button in every discovered profile; Chrome must be closed |
| `restore-button` | Restore the original button settings; Chrome must be closed |
| `export-macos-policy FILE` | Export a removable `.mobileconfig`, without installing it |

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
