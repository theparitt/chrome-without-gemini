"""Build on the target OS; bundle Python/Tk so users do not need Python."""

from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
NAME = "ChromeWithoutGemini"


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
    print(f"Packaged {platform_name} {architecture} in {output}")


if __name__ == "__main__":
    main()
