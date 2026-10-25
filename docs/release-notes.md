Your browser. Your choice.

Privacy update: profile selectors now use generic labels like "Default profile"
and "Profile 1", rather than Chrome account display names. No personal Chrome
profiles or local screenshots are included in the app or source.

Download the executable for your platform. Python and build tools are included;
you do not need to compile anything.

| Platform | Download |
| --- | --- |
| Windows 10/11, Intel/AMD 64-bit | `chrome-without-gemini-windows-x64.exe` |
| macOS 15+, Apple Silicon | `chrome-without-gemini-macos-arm64.zip` |
| macOS 15+, Intel | `chrome-without-gemini-macos-x64.zip` |
| Linux x64, glibc 2.35+ with a desktop session | `chrome-without-gemini-linux-x64.tar.gz` |

Two controls: disable Chrome's Gemini integration, or hide only the Gemini tab button.
Each has an undo path. Windows uses the current-user GeminiSettings policy; macOS
exports a removable profile that you must install in System Settings; Linux creates
a separate launcher with `--disable-features=Glic` that you must use after fully
quitting Chrome. The Linux fallback is experimental and does not change other launchers.

These are unsigned community builds. Windows or macOS may warn about an unknown
publisher. Decide whether to trust the app after reviewing the source and build logs;
do not disable your operating system's protections. The public workflow builds every
asset from this tagged source, runs isolated backend tests and a packaged GUI launch
check on each platform, and publishes SHA-256 checksums. These checks do not constitute
end-to-end validation of Gemini removal in a signed-in Chrome session on every OS.

For Windows policy verification, restart Chrome and check `chrome://policy` for
`GeminiSettings = 1`, status **OK**. Local policy can add Chrome's "Managed by your
organization" label. On macOS, profile export alone is not installation.

See the README for setup, exact changes, limitations, and Undo instructions.

