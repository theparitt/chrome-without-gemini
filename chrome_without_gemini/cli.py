"""Optional, inspectable CLI using exactly the same backend as the desktop UI."""

import argparse
from pathlib import Path
import sys

from .core import AppError, Journal, Toolbar, default_chrome_root, discover_profiles
from .platforms import GeminiControl
from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(description="Chrome Without Gemini")
    parser.add_argument(
        "--version", action="version", version=f"Chrome Without Gemini {__version__}"
    )
    parser.add_argument("--chrome-root", type=Path, default=default_chrome_root())
    parser.add_argument("--state-root", type=Path)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    sub.add_parser("disable")
    sub.add_parser("restore-gemini")
    sub.add_parser("hide-button")
    sub.add_parser("restore-button")
    export = sub.add_parser("export-macos-policy")
    export.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    journal = Journal(args.state_root)
    control = GeminiControl(journal)
    toolbar = Toolbar(journal)
    try:
        if args.action == "status":
            print(control.status())
            for profile in discover_profiles(args.chrome_root):
                print(
                    f"{profile.name}: button {'hidden' if profile.pinned is False else 'visible/default'}"
                )
            return 0
        actions = {
            "disable": control.disable,
            "restore-gemini": control.restore,
            "restore-button": toolbar.restore,
        }
        if args.action == "hide-button":
            result = toolbar.hide(discover_profiles(args.chrome_root))
        elif args.action == "export-macos-policy":
            result = control.export_mac(args.destination)
        else:
            result = actions[args.action]()
        print(result)
        return 0
    except (AppError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
