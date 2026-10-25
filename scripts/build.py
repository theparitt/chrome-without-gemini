"""Build on the target OS; bundle Python/Tk so users do not need Python."""

from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
NAME = "ChromeWithoutGemini"
CLI_NAME = "ChromeWithoutGeminiCLI"


def main():
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        NAME,
        "--paths",
        str(ROOT),
        "--noupx",
    ]
    if sys.platform == "darwin":
        command += [
            "--windowed",
            "--onedir",
            "--osx-bundle-identifier",
            "org.chromewithoutgemini.app",
        ]
    else:
        command += ["--onefile"]
        if sys.platform == "win32":
            command += ["--windowed"]
    command += [str(ROOT / "launch.py")]
    subprocess.run(command, cwd=ROOT, check=True)
    architecture = platform.machine().lower()
    architecture = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(
        architecture, architecture
    )
    platform_name = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    output = ROOT / "dist"
    base = output / f"chrome-without-gemini-{platform_name}-{architecture}"
    if sys.platform == "win32":
        destination = base.with_suffix(".exe")
        shutil.copy2(output / (NAME + ".exe"), destination)
    elif sys.platform == "darwin":
        subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(output / (NAME + ".app")),
                str(base.with_suffix(".zip")),
            ],
            check=True,
        )
    else:
        stage = ROOT / "build" / base.name
        stage.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output / NAME, stage / NAME)
        shutil.copy2(ROOT / "README.md", stage / "README.md")
        shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
        shutil.make_archive(str(base), "gztar", root_dir=stage)
    # A separate console build works from terminals and local AI agents, without Tk.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--console",
            "--name",
            CLI_NAME,
            "--paths",
            str(ROOT),
            "--noupx",
            "--exclude-module",
            "tkinter",
            "--exclude-module",
            "_tkinter",
            str(ROOT / "launch_cli.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    cli_base = output / f"chrome-without-gemini-cli-{platform_name}-{architecture}"
    if sys.platform == "win32":
        shutil.copy2(output / (CLI_NAME + ".exe"), cli_base.with_suffix(".exe"))
    else:
        cli_stage = ROOT / "build" / cli_base.name
        cli_stage.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output / CLI_NAME, cli_stage / CLI_NAME)
        shutil.copy2(ROOT / "docs/CLI.md", cli_stage / "README.md")
        shutil.copy2(ROOT / "LICENSE", cli_stage / "LICENSE")
        shutil.make_archive(str(cli_base), "gztar", root_dir=cli_stage)
    print(f"Packaged desktop app and CLI for {platform_name} {architecture} in {output}")


if __name__ == "__main__":
    main()
