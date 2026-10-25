Your browser. Your choice.

New in v0.3.0: Google Lens is a separate option, and **Gemini + Lens are both
selected by default** in the app, CLI `disable`, and macOS profile export.
Use `--only gemini` / `--only lens` to choose one. Use `restore` for Undo both,
or `restore --only lens` / `--only gemini` for one. Existing Gemini recovery
files are migrated while preserving the original values. Generic labels and
the GitHub no-reply commit identity are retained.

Download the executable for your platform. Python and build tools are included;
you do not need to compile anything.

| Platform | Download |
| --- | --- |
| Windows 10/11, Intel/AMD 64-bit | `chrome-without-gemini-windows-x64.exe` |
| macOS 15+, Apple Silicon | `chrome-without-gemini-macos-arm64.zip` |
| macOS 15+, Intel | `chrome-without-gemini-macos-x64.zip` |
| Linux x64, glibc 2.35+ with a desktop session | `chrome-without-gemini-linux-x64.tar.gz` |

| CLI platform | Download |
| --- | --- |
| Windows x64 | `chrome-without-gemini-cli-windows-x64.exe` |
| macOS Apple Silicon | `chrome-without-gemini-cli-macos-arm64.tar.gz` |
| macOS Intel | `chrome-without-gemini-cli-macos-x64.tar.gz` |
| Linux x64, glibc 2.35+ | `chrome-without-gemini-cli-linux-x64.tar.gz` |

The CLI also runs without a graphical desktop. Applying the macOS profile or
using the Linux launcher still requires the interactive steps described in the README.
Run `--help` first. On Windows, `disable` applies the selected policies; Linux's
`disable` creates its launcher; macOS uses `export-macos-policy FILE`.

Choose Gemini, Google Lens, or the default both. Button-only hiding remains separate.
Each has an undo path. Windows uses current-user GeminiSettings and/or
SearchContentSharingSettings policies; macOS
exports a removable profile that you must install in System Settings; Linux creates
a separate launcher with default `--disable-features=Glic,LensOverlay,LensStandalone` that you must use after fully
quitting Chrome. The Linux fallback is experimental and does not change other launchers.

These are unsigned community builds. Windows or macOS may warn about an unknown
publisher. Decide whether to trust the app after reviewing the source and build logs;
do not disable your operating system's protections. The public workflow builds every
asset from this tagged source, runs isolated backend tests and a packaged GUI launch
check on each platform, and publishes SHA-256 checksums. These checks do not constitute
end-to-end validation of Gemini removal in a signed-in Chrome session on every OS.

For Windows policy verification, restart Chrome and check `chrome://policy` for
`GeminiSettings = 1` and `SearchContentSharingSettings = 1` for the default selection,
status **OK**. Lens policy also blocks Chrome's AI Mode page/file-sharing panel.
An ordinary image-search row or fallback label may remain on some Chrome builds;
verify the actual menu. Local policy can add Chrome's "Managed by your
organization" label. On macOS, profile export alone is not installation.

See the README for setup, exact changes, limitations, and Undo instructions.

