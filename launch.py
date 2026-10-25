"""Desktop entry point, including a harmless packaged diagnostic for release checks."""

import sys


def main():
    if "--self-test" in sys.argv:
        import json
        import tkinter
        from chrome_without_gemini import __version__
        from chrome_without_gemini.platforms import mac_profile
        import plistlib
        from chrome_without_gemini.gui import App

        assert plistlib.loads(mac_profile())["PayloadContent"][0]["GeminiSettings"] == 1
        root = tkinter.Tk()
        root.withdraw()
        app = App(root, demo=True)
        errors = []
        root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
        root.update()
        assert app.selected_features() == ("gemini", "lens")
        for page in ("toolbar", "recovery", "settings", "integrations"):
            app.show_page(page)
            root.update()
        for variable in app.feature_selection.values():
            variable.set(False)
        app.update_actions()
        assert not app.primary.enabled
        for variable in app.feature_selection.values():
            variable.set(True)
        app.update_actions()
        assert app.primary.enabled

        def forbid(*args, **kwargs):
            raise AssertionError("Preview attempted a real settings operation")

        app.control.disable = forbid
        app.control.restore = forbid
        app.toolbar.hide = forbid
        app.toolbar.restore = forbid
        app.disable()
        app.restore_all()
        app.hide()
        root.update()
        root.deiconify()
        root.geometry("940x620")
        root.update()
        app.show_page("integrations")
        root.update()
        header_y = app.page_title.winfo_rooty()
        footer_y = app.primary.winfo_rooty()
        assert header_y >= root.winfo_rooty()
        assert footer_y + app.primary.winfo_height() <= root.winfo_rooty() + root.winfo_height()
        app.canvas.yview_moveto(1)
        root.update()
        assert app.page_title.winfo_rooty() == header_y
        assert app.primary.winfo_rooty() == footer_y
        assert not errors, errors
        root.destroy()
        print(json.dumps({"app": "Chrome Without Gemini", "version": __version__, "gui": "ok"}))
        return
    from chrome_without_gemini.gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
