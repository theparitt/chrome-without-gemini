"""Desktop entry point, including a harmless packaged diagnostic for release checks."""

import sys


def main():
    if "--self-test" in sys.argv:
        import json
        import tkinter
        from chrome_without_gemini import __version__
        from chrome_without_gemini.platforms import mac_profile
        import plistlib

        assert plistlib.loads(mac_profile())["PayloadContent"][0]["GeminiSettings"] == 1
        root = tkinter.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        print(json.dumps({"app": "Chrome Without Gemini", "version": __version__, "gui": "ok"}))
        return
    from chrome_without_gemini.gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
