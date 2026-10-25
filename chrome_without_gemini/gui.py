"""Desktop UI with fixed navigation, header and actions. Only content scrolls."""

from pathlib import Path
import re
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont

from . import __version__
from .core import (
    AppError,
    Journal,
    Profile,
    Toolbar,
    chrome_running,
    default_chrome_root,
    discover_profiles,
)
from .controls import ChromeControl, DEFAULT_FEATURES, POLICIES
from .ui import C, Button, Card, Icon, Pill, Toggle, app_icon, text


class App:
    def __init__(self, root, chrome_root=None, state_root=None, *, demo=False):
        self.root, self.demo = root, demo
        families = set(tkfont.families(root))
        root.ui_font = next(
            (f for f in ("Segoe UI", "Helvetica Neue", "DejaVu Sans") if f in families),
            "TkDefaultFont",
        )
        self.chrome_root = chrome_root or default_chrome_root()
        self.journal = Journal(state_root)
        self.control, self.toolbar = ChromeControl(self.journal), Toolbar(self.journal)
        self.feature_selection = {name: tk.BooleanVar(value=True) for name in DEFAULT_FEATURES}
        self.profile_selection, self.feature_states, self.nav_widgets = {}, {}, {}
        self.profiles = []
        self.recovery = {"integrations": False, "toolbar": False}
        self.busy, self.running, self.custom_folder = False, False, chrome_root is not None
        self.active_page, self.notification = "integrations", None
        root.title("Chrome Without Gemini")
        w, h = min(1140, root.winfo_screenwidth() - 60), min(800, root.winfo_screenheight() - 90)
        root.geometry(f"{w}x{h}")
        root.minsize(min(940, w), min(620, h))
        root.configure(bg=C["bg"])
        root.report_callback_exception = self.callback_error
        app_icon(root)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self.sidebar = tk.Frame(root, bg=C["nav"], width=220)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.build_sidebar()
        main = tk.Frame(root, bg=C["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        header = tk.Frame(main, bg=C["bg"], padx=32, pady=24)
        header.grid(row=0, column=0, sticky="ew")
        top = tk.Frame(header, bg=C["bg"])
        top.pack(fill="x")
        text(top, "CHROME PREFERENCES", 9, C["muted"], True).pack(side="left")
        self.chrome_pill = Pill(top, "Checking Chrome", dot=True)
        self.chrome_pill.pack(side="right")
        self.page_title = text(header, "Browser controls", 25, bold=True)
        self.page_title.pack(fill="x", pady=(15, 5))
        self.page_subtitle = text(header, "Choose what stays in your browser.", 11, C["muted"])
        self.page_subtitle.pack(fill="x")
        self.notice = tk.Frame(main, bg=C["bg"], padx=32)
        self.notice.grid(row=1, column=0, sticky="ew")
        shell = tk.Frame(main, bg=C["bg"])
        shell.grid(row=2, column=0, sticky="nsew")
        self.canvas = tk.Canvas(shell, bg=C["bg"], bd=0, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar = tk.Scrollbar(
            shell, command=self.canvas.yview, width=9, bd=0, highlightthickness=0
        )
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.body = tk.Frame(self.canvas, bg=C["bg"], padx=32)
        self.body_window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind(
            "<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", self.resize_body)
        for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind(event, self.wheel, add="+")
        footer = tk.Frame(main, bg=C["surface"], padx=32, pady=18)
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.footer_note = text(footer, "2 integrations selected", 10, C["muted"])
        self.footer_note.grid(row=0, column=0, sticky="w")
        self.secondary = Button(footer, "Restore selected", self.restore_selected)
        self.secondary.grid(row=0, column=1, padx=(12, 10))
        self.primary = Button(footer, "Apply changes", self.disable, primary=True, width=170)
        self.primary.grid(row=0, column=2)
        self.load_status()
        self.show_page("integrations")

    def build_sidebar(self):
        brand = tk.Frame(self.sidebar, bg=C["nav"], padx=22, pady=28)
        brand.pack(fill="x")
        Icon(brand, "brand", 44, "#ffffff", C["orange"]).pack(anchor="w", pady=(0, 14))
        text(brand, "Chrome", 18, "#ffffff", True).pack(anchor="w")
        text(brand, "Without Gemini", 12, "#c4cedd").pack(anchor="w", pady=(2, 0))
        text(brand, "BROWSER UTILITY", 8, "#8191a8", True).pack(anchor="w", pady=(12, 0))
        tk.Frame(self.sidebar, bg="#29364a", height=1).pack(fill="x", padx=22, pady=(0, 22))
        text(self.sidebar, "WORKSPACE", 8, "#7f90a9", True).pack(anchor="w", padx=24, pady=(0, 10))
        for key, label, kind in (
            ("integrations", "Browser controls", "sliders"),
            ("toolbar", "Toolbar visibility", "browser"),
            ("recovery", "Restore changes", "undo"),
        ):
            row = tk.Frame(
                self.sidebar, bg=C["nav"], cursor="hand2", padx=11, pady=8, takefocus=True
            )
            row.pack(fill="x", padx=12, pady=3)
            icon = Icon(row, kind, 25, "#99a8bd")
            icon.pack(side="left", padx=(0, 8))
            label = text(row, label, 10, "#b8c5d7")
            label.pack(side="left")
            for widget in (row, icon, label):
                widget.bind("<Button-1>", lambda event, page=key: self.show_page(page))
            for event in ("<Return>", "<space>"):
                row.bind(event, lambda event, page=key: self.show_page(page))
            self.nav_widgets[key] = (row, icon, label)
        bottom = tk.Frame(self.sidebar, bg=C["nav"], padx=22, pady=23)
        bottom.pack(side="bottom", fill="x")
        settings = text(bottom, "Settings & about", 10, "#b8c5d7")
        settings.configure(cursor="hand2", takefocus=True)
        settings.pack(fill="x", pady=(0, 23))
        for event in ("<Button-1>", "<Return>", "<space>"):
            settings.bind(event, lambda event: self.show_page("settings"))
        tk.Frame(bottom, bg="#29364a", height=1).pack(fill="x", pady=(0, 18))
        text(bottom, "LOCAL. PRIVATE. YOURS.", 8, "#9cacbf", True).pack(anchor="w")
        text(bottom, "No accounts. No uploads.", 9, "#7f90a9").pack(anchor="w", pady=(6, 0))
        text(bottom, f"VERSION {__version__}", 8, "#64768f").pack(anchor="w", pady=(15, 0))

    def resize_body(self, event):
        self.canvas.itemconfigure(self.body_window, width=event.width)
        self.wrap_labels(self.body, max(200, event.width - 118))

    def wrap_labels(self, parent, width):
        for child in parent.winfo_children():
            if isinstance(child, tk.Label) and getattr(child, "flex_wrap", False):
                child.configure(wraplength=width)
            self.wrap_labels(child, width)

    def wheel(self, event):
        x, y = self.root.winfo_pointerxy()
        inside = (
            self.canvas.winfo_rootx() <= x < self.canvas.winfo_rootx() + self.canvas.winfo_width()
            and self.canvas.winfo_rooty()
            <= y
            < self.canvas.winfo_rooty() + self.canvas.winfo_height()
        )
        bbox = self.canvas.bbox("all")
        if not inside or not bbox or bbox[3] <= self.canvas.winfo_height():
            return
        up = getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0
        self.canvas.yview_scroll(-2 if up else 2, "units")
        return "break"

    def paragraph(self, parent, value, size=10, color=None):
        label = text(
            parent, value, size, color or C["muted"], wrap=max(250, self.canvas.winfo_width() - 118)
        )
        label.flex_wrap = True
        label.pack(fill="x", pady=(0, 4))
        return label

    def load_status(self):
        try:
            if self.demo:
                self.running = False
                self.profiles = [
                    Profile(Path("Default/Preferences"), "Default profile", False),
                    Profile(Path("Profile 1/Preferences"), "Profile 1", True),
                ]
                self.feature_states = dict.fromkeys(DEFAULT_FEATURES, "Not configured")
                self.recovery = {"integrations": False, "toolbar": False}
            else:
                self.running = chrome_running()
                self.profiles = discover_profiles(self.chrome_root)
                state = self.journal.read()
                self.recovery = {
                    "integrations": bool(state.get("policy_changes") or state.get("disable")),
                    "toolbar": bool(state.get("toolbar")),
                }
                if sys.platform == "win32":
                    for feature in DEFAULT_FEATURES:
                        policy = self.control._policy(POLICIES[feature])
                        self.feature_states[feature] = (
                            "Policy set"
                            if policy.read() == policy.disabled_snapshot()
                            else "Not configured"
                        )
                elif sys.platform == "darwin":
                    self.feature_states = dict.fromkeys(DEFAULT_FEATURES, "Verify in Chrome")
                else:
                    active = (state.get("disable") or {}).get(
                        "features", ["gemini"] if state.get("disable") else []
                    )
                    self.feature_states = {
                        f: "Launcher saved" if f in active else "Not configured"
                        for f in DEFAULT_FEATURES
                    }
            self.chrome_pill.update_value(
                "Preview · sample data"
                if self.demo
                else "Chrome is running"
                if self.running
                else "Chrome is closed",
                "amber" if self.running else "green",
                "amber_soft" if self.running else "green_soft",
            )
            previous = {p: v.get() for p, v in self.profile_selection.items()}
            self.profile_selection = {
                p.path: tk.BooleanVar(value=previous.get(p.path, True)) for p in self.profiles
            }
        except (AppError, OSError) as exc:
            self.chrome_pill.update_value("Status unavailable", "amber", "amber_soft")
            self.show_notice("Could not read Chrome settings", str(exc), error=True)

    def show_page(self, page):
        if self.busy:
            return
        self.active_page = page
        for key, (row, icon, label) in self.nav_widgets.items():
            bg = C["nav_active"] if key == page else C["nav"]
            row.configure(bg=bg)
            icon.configure(bg=bg)
            icon.draw(C["orange"] if key == page else "#99a8bd")
            label.configure(bg=bg, fg="#ffffff" if key == page else "#b8c5d7")
        for child in self.body.winfo_children():
            child.destroy()
        title, subtitle = {
            "integrations": (
                "Browser controls",
                "Less clutter in Chrome. More room for what matters.",
            ),
            "toolbar": (
                "Toolbar visibility",
                "Hide the Gemini button without disabling the integration.",
            ),
            "recovery": ("Restore changes", "Return to your original settings, whenever you want."),
            "settings": ("Settings & about", "A small utility. A clear view of what it changes."),
        }[page]
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)
        getattr(self, "page_" + page)()
        self.update_actions()
        self.root.after_idle(lambda: self.canvas.yview_moveto(0))

    def page_integrations(self):
        card = Card(self.body)
        card.pack(fill="x", pady=(0, 16))
        head = tk.Frame(card.inner, bg=C["surface"])
        head.pack(fill="x", pady=(0, 5))
        text(head, "Choose features to disable", 14, bold=True).pack(side="left")
        self.selection_pill = Pill(head, "2 selected", "orange", "orange_soft")
        self.selection_pill.pack(side="right")
        self.paragraph(
            card.inner, "Both selected by default. Unselected features keep their current setting."
        )
        for feature, name, description, kind, color, soft in (
            (
                "gemini",
                "Gemini",
                "Right-click assistance and the button beside your tabs.",
                "spark",
                "purple",
                "purple_soft",
            ),
            (
                "lens",
                "Google Lens",
                "Visual search and Chrome's page-sharing entry points.",
                "lens",
                "blue",
                "blue_soft",
            ),
        ):
            tk.Frame(card.inner, bg=C["line"], height=1).pack(fill="x", pady=(17, 18))
            row = tk.Frame(card.inner, bg=C["surface"])
            row.pack(fill="x")
            Icon(row, kind, 42, C[color], C[soft]).pack(side="left", padx=(0, 15), anchor="n")
            Toggle(row, self.feature_selection[feature], self.update_actions).pack(
                side="right", padx=(16, 0), anchor="n", pady=5
            )
            copy = tk.Frame(row, bg=C["surface"])
            copy.pack(side="left", fill="both", expand=True)
            title = tk.Frame(copy, bg=C["surface"])
            title.pack(fill="x")
            text(title, name, 12, bold=True).pack(side="left", padx=(0, 10))
            state = self.feature_states.get(feature, "Status unavailable")
            set_here = state in ("Policy set", "Launcher saved")
            Pill(
                title, state, "green" if set_here else "muted", "green_soft" if set_here else "bg"
            ).pack(side="left")
            text(copy, description, 10, C["muted"], wrap=430).pack(fill="x", pady=(6, 0))
            if feature == "lens":
                text(
                    copy,
                    "Also affects AI Mode page/file sharing in Chrome.",
                    9,
                    C["faint"],
                    wrap=430,
                ).pack(fill="x", pady=(5, 0))
        hint = tk.Frame(self.body, bg=C["bg"])
        hint.pack(fill="x", pady=(2, 16))
        Icon(hint, "info", 25).pack(side="left", anchor="n", padx=(0, 9))
        copy = tk.Frame(hint, bg=C["bg"])
        copy.pack(side="left", fill="x", expand=True)
        text(copy, "What happens next", 10, bold=True).pack(anchor="w", pady=(2, 6))
        note = "Save your work, then restart Chrome after applying. Local policies may add a management label."
        if sys.platform == "darwin":
            note = "Export your selection, then install the profile in System Settings. Exporting alone does not apply it."
        elif sys.platform != "win32":
            note = "Creates a separate launcher. Quit Chrome completely, then start Chrome (Without Gemini)."
        self.paragraph(copy, note)
        self.paragraph(
            copy,
            "Some Chrome versions retain ordinary image search. Verify policy or launcher changes in Chrome.",
            9,
        )

    def page_toolbar(self):
        card = Card(self.body)
        card.pack(fill="x", pady=(0, 16))
        head = tk.Frame(card.inner, bg=C["surface"])
        head.pack(fill="x", pady=(0, 8))
        text(head, "Choose profiles", 14, bold=True).pack(side="left")
        Pill(head, f"{len(self.profiles)} profiles").pack(side="right")
        self.paragraph(
            card.inner,
            "Changes only the top-right Gemini button. Other Gemini features stay available.",
        )
        for profile in self.profiles:
            tk.Frame(card.inner, bg=C["line"], height=1).pack(fill="x", pady=(14, 12))
            row = tk.Frame(card.inner, bg=C["surface"])
            row.pack(fill="x")
            Icon(row, "browser", 34, C["muted"], C["bg"]).pack(side="left", padx=(0, 12))
            text(row, profile.name, 11, bold=True).pack(side="left", padx=(0, 12))
            Pill(
                row,
                "Button hidden" if profile.pinned is False else "Visible / default",
                "green" if profile.pinned is False else "muted",
                "green_soft" if profile.pinned is False else "bg",
            ).pack(side="left")
            Toggle(row, self.profile_selection[profile.path], self.update_actions).pack(
                side="right"
            )
        if not self.profiles:
            self.paragraph(
                card.inner,
                "No Chrome stable profiles found. Choose a Chrome folder in Settings & about.",
            )
        hint = Card(self.body, padding=18)
        hint.pack(fill="x", pady=(0, 16))
        self.paragraph(hint.inner, "Quit Chrome before changing button visibility.", 11, C["ink"])
        self.paragraph(
            hint.inner, "The app will never close your tabs. Profile names are kept anonymous."
        )
        Button(hint.inner, "Refresh Chrome status", self.refresh, compact=True).pack(
            anchor="w", pady=(10, 0)
        )

    def page_recovery(self):
        for kind, title, description, command, icon in (
            (
                "integrations",
                "Restore integrations",
                "Restore the original Gemini and Lens controls.",
                self.restore_all,
                "undo",
            ),
            (
                "toolbar",
                "Restore toolbar buttons",
                "Restore button visibility in the profiles changed by this app.",
                lambda: self.perform(self.toolbar.restore, "Toolbar settings restored"),
                "browser",
            ),
        ):
            card = Card(self.body)
            card.pack(fill="x", pady=(0, 16))
            row = tk.Frame(card.inner, bg=C["surface"])
            row.pack(fill="x", pady=(0, 14))
            Icon(row, icon, 38, C["blue"], C["blue_soft"]).pack(side="left", padx=(0, 12))
            text(row, title, 13, bold=True).pack(side="left")
            available = self.recovery[kind]
            Pill(
                row,
                "Saved changes" if available else "No saved changes",
                "green" if available else "muted",
                "green_soft" if available else "bg",
            ).pack(side="right")
            self.paragraph(card.inner, description)
            button = Button(
                card.inner,
                "View restore instructions"
                if kind == "integrations" and sys.platform == "darwin"
                else "Restore original settings",
                command,
                compact=True,
            )
            button.pack(anchor="w", pady=(12, 0))
            button.set_enabled(available or kind == "integrations" and sys.platform == "darwin")
        self.paragraph(
            self.body,
            "Recovery uses the original values saved on this device. Keep changes.json until you are done. Conflicting newer changes are preserved.",
            9,
        )

    def page_settings(self):
        card = Card(self.body)
        card.pack(fill="x", pady=(0, 16))
        text(card.inner, "Chrome installation", 14, bold=True).pack(anchor="w", pady=(0, 12))
        self.paragraph(
            card.inner,
            "Google Chrome stable · "
            + ("Custom user-data folder" if self.custom_folder else "Default user-data folder"),
            11,
            C["ink"],
        )
        self.paragraph(
            card.inner, "Account names and full folder paths are not displayed in the app."
        )
        row = tk.Frame(card.inner, bg=C["surface"])
        row.pack(fill="x", pady=(12, 0))
        Button(row, "Choose Chrome folder", self.choose_root, compact=True).pack(
            side="left", padx=(0, 8)
        )
        Button(row, "Refresh status", self.refresh, compact=True).pack(side="left")
        card = Card(self.body)
        card.pack(fill="x", pady=(0, 16))
        text(card.inner, "Transparent by design", 14, bold=True).pack(anchor="w", pady=(0, 14))
        for title, description in (
            ("Local operation", "No account, uploads, telemetry, or background service."),
            (
                "Reversible controls",
                "Original settings are saved before a change. Undo remains available.",
            ),
            (
                "Inspectable source",
                "MIT licensed. Built from public source using native platform runners.",
            ),
        ):
            text(card.inner, title, 10, bold=True).pack(anchor="w", pady=(4, 5))
            self.paragraph(card.inner, description)
        self.paragraph(
            card.inner,
            f"Chrome Without Gemini {__version__} · Independent project. Not affiliated with Google.",
            9,
        )
        Button(card.inner, "Technical details", self.technical_details, compact=True).pack(
            anchor="w", pady=(12, 0)
        )

    def update_actions(self):
        if self.active_page == "integrations":
            count = len(self.selected_features())
            self.selection_pill.update_value(f"{count} selected")
            self.footer_note.configure(
                text=f"{count} integration{'s' if count != 1 else ''} selected"
            )
            label = (
                "Export profile"
                if sys.platform == "darwin"
                else "Create launcher"
                if sys.platform != "win32"
                else "Apply changes"
            )
            self.primary.change(label=label)
            self.primary.command = self.disable
            self.secondary.change(label="Restore selected")
            self.secondary.command = self.restore_selected
            self.primary.set_enabled(count > 0 and not self.busy)
            self.secondary.set_enabled(
                count > 0
                and not self.busy
                and (self.recovery["integrations"] or sys.platform == "darwin")
            )
            self.primary.grid()
            self.secondary.grid()
        elif self.active_page == "toolbar":
            count = sum(var.get() for var in self.profile_selection.values())
            self.footer_note.configure(
                text="Quit Chrome to apply" if self.running else f"{count} profiles selected"
            )
            self.primary.change(label="Hide selected buttons")
            self.primary.command = self.hide
            self.secondary.change(label="Restore buttons")
            self.secondary.command = lambda: self.perform(
                self.toolbar.restore, "Toolbar settings restored"
            )
            self.primary.set_enabled(count > 0 and not self.busy and not self.running)
            self.secondary.set_enabled(self.recovery["toolbar"] and not self.busy)
            self.primary.grid()
            self.secondary.grid()
        else:
            self.footer_note.configure(
                text="Preview only · no settings will change"
                if self.demo
                else "Changes stay on this device"
            )
            self.primary.grid_remove()
            self.secondary.grid_remove()

    def show_notice(self, title, description, error=False):
        for path, label in (
            (self.chrome_root, "[Chrome data]"),
            (self.journal.root, "[Recovery folder]"),
            (Path.home(), "[Home]"),
        ):
            for variant in (str(path), str(path).replace("\\", "/")):
                description = re.sub(
                    re.escape(variant), lambda match: label, description, flags=re.IGNORECASE
                )
        if self.notification and self.notification.winfo_exists():
            self.notification.destroy()
        self.notification = tk.Frame(
            self.notice, bg=C["amber_soft"] if error else C["green_soft"], padx=14, pady=12
        )
        self.notification.pack(fill="x", pady=(0, 16))
        close = text(self.notification, "×", 15, C["muted"])
        close.configure(cursor="hand2")
        close.pack(side="right", anchor="n", padx=(10, 0))
        close.bind("<Button-1>", lambda event: self.notification.destroy())
        copy = tk.Frame(self.notification, bg=self.notification.cget("bg"))
        copy.pack(fill="both", expand=True)
        text(copy, title, 10, C["amber"] if error else C["green"], True).pack(anchor="w")
        text(copy, description, 9, C["ink"], wrap=650).pack(fill="x", pady=(5, 0))

    def dialog(self, title, description):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.ui_font = self.root.ui_font
        window.configure(bg=C["surface"])
        window.transient(self.root)
        window.geometry("570x370")
        frame = tk.Frame(window, bg=C["surface"], padx=28, pady=24)
        frame.pack(fill="both", expand=True)
        text(frame, title, 18, bold=True).pack(anchor="w", pady=(0, 16))
        message = tk.Text(
            frame,
            wrap="word",
            font=(self.root.ui_font, 10),
            bg=C["surface"],
            fg=C["muted"],
            relief="flat",
            bd=0,
            height=9,
            highlightthickness=0,
        )
        message.insert("1.0", description)
        message.configure(state="disabled")
        message.pack(fill="both", expand=True)
        Button(frame, "Done", window.destroy, primary=True, width=100).pack(
            side="right", pady=(16, 0)
        )
        window.bind("<Escape>", lambda event: window.destroy())

    def technical_details(self):
        self.dialog(
            "What this app changes",
            "Windows: selected current-user policies GeminiSettings=1 and/or SearchContentSharingSettings=1. "
            "Restart Chrome and verify at chrome://policy.\n\n"
            "macOS: exports a removable profile. Install it in System Settings; export alone applies nothing. "
            "Selective Undo needs removal of the combined profile and a single-feature replacement.\n\n"
            "Linux: a separate launcher uses Glic and/or LensOverlay,LensStandalone. Quit Chrome before "
            "using it. Other launchers are unaffected.\n\n"
            "Lens also blocks Chrome's AI Mode page/file sharing. Some versions retain image search. "
            "Toolbar-only edits change glic.pinned_to_tabstrip while Chrome is closed.",
        )

    def perform(self, operation, title="Settings saved"):
        if self.demo:
            self.show_notice(
                "Preview only", "This is a design preview. No Chrome settings were changed."
            )
            return
        self.busy = True
        self.root.configure(cursor="watch")
        self.update_actions()
        self.root.update_idletasks()
        try:
            result = operation()
        except PermissionError:
            self.show_notice(
                "Permission needed",
                "Windows blocked the change. If this is your own PC, run the app "
                "as administrator using the same account so Undo can find your original settings.",
                True,
            )
        except (AppError, OSError, ValueError) as exc:
            self.show_notice("Change could not be completed", str(exc), True)
        else:
            self.dialog(title, result)
            self.show_notice(
                title, "Review the completion instructions and verify the result in Chrome."
            )
        finally:
            self.busy = False
            self.root.configure(cursor="")
            self.load_status()
            self.show_page(self.active_page)

    def selected_features(self):
        return tuple(name for name in DEFAULT_FEATURES if self.feature_selection[name].get())

    def disable(self):
        if self.demo:
            self.perform(lambda: None)
        elif sys.platform == "darwin":
            destination = filedialog.asksaveasfilename(
                parent=self.root,
                title="Export Chrome policy",
                initialfile="ChromeWithoutGemini.mobileconfig",
                defaultextension=".mobileconfig",
                filetypes=[("macOS profile", "*.mobileconfig")],
            )
            if destination:

                def export():
                    result = self.control.export_mac(Path(destination), self.selected_features())
                    subprocess.Popen(["open", destination])
                    return result

                self.perform(export, "Profile exported · installation required")
        else:
            self.perform(lambda: self.control.disable(self.selected_features()))

    def restore_selected(self):
        self.perform(
            lambda: self.control.restore(self.selected_features()),
            "Restore instructions" if sys.platform == "darwin" else "Original settings restored",
        )

    def restore_all(self):
        self.perform(
            self.control.restore,
            "Restore instructions" if sys.platform == "darwin" else "Original settings restored",
        )

    def hide(self):
        profiles = [p for p in self.profiles if self.profile_selection[p.path].get()]
        self.perform(lambda: self.toolbar.hide(profiles), "Toolbar preference saved")

    def choose_root(self):
        if self.demo:
            self.show_notice(
                "Preview only", "Folder selection is disabled in this sample-data preview."
            )
            return
        path = filedialog.askdirectory(
            parent=self.root,
            title="Choose Chrome user-data folder",
            initialdir=self.chrome_root.parent,
        )
        if path:
            self.chrome_root, self.custom_folder = Path(path), True
            self.refresh()

    def refresh(self):
        self.load_status()
        self.show_page(self.active_page)

    def callback_error(self, kind, value, traceback):
        self.show_notice(
            "Something needs attention",
            f"{kind.__name__}: {value}. Your saved recovery data is retained.",
            True,
        )


def main():
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    App(root, demo="--demo" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
