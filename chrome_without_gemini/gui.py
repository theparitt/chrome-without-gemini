"""Small native Tk interface. Importing this module never changes Chrome settings."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .core import AppError, Journal, Toolbar, chrome_running, default_chrome_root, discover_profiles
from .controls import ChromeControl, DEFAULT_FEATURES

BG = "#f5f2ec"
INK = "#222724"
MUTED = "#616b65"
ACCENT = "#cc4a13"
WHITE = "#ffffff"
TEAL = "#dcebe4"


class App:
    def __init__(
        self, root: tk.Tk, chrome_root: Path | None = None, state_root: Path | None = None
    ):
        self.root = root
        self.chrome_root = chrome_root or default_chrome_root()
        self.journal = Journal(state_root)
        self.control = ChromeControl(self.journal)
        self.feature_selection = {name: tk.BooleanVar(value=True) for name in DEFAULT_FEATURES}
        self.toolbar = Toolbar(self.journal)
        self.profiles = []
        self.profile_selection = {}
        self.root.title("Chrome Without Gemini")
        self.root.geometry("810x850")
        self.root.minsize(720, 680)
        self.root.configure(bg=BG)
        self.root.report_callback_exception = self.callback_error
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 10), padding=(14, 8), background=WHITE)
        style.configure("Accent.TButton", background=ACCENT, foreground=WHITE, borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#ad3d0c")])
        style.configure("TCheckbutton", background=WHITE, foreground=INK, font=("Segoe UI", 10))
        # Scrollable layout remains usable on smaller displays and at higher scaling.
        canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(canvas, bg=BG, padx=28, pady=24)
        window_id = canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind(
            "<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))

        def wheel(event):
            canvas.yview_scroll(-1 if event.delta > 0 or event.num == 4 else 1, "units")

        root.bind("<MouseWheel>", wheel)
        root.bind("<Button-4>", wheel)
        root.bind("<Button-5>", wheel)

        self.label(self.body, "YOUR BROWSER. YOUR CHOICE.", fg=ACCENT, size=10, bold=True)
        self.label(self.body, "Chrome Without Gemini", size=28, bold=True, pady=(5, 3))
        self.label(self.body, "Remove the extra AI entry points. Keep browsing your way.", fg=MUTED)

        status_frame = tk.Frame(self.body, bg=TEAL, padx=14, pady=11)
        status_frame.pack(fill="x", pady=(18, 14))
        self.status_text = self.label(status_frame, "Checking Chrome...", bg=TEAL, size=10)

        card = self.card("01", "Remove Gemini and Google Lens")
        self.label(
            card,
            "Choose the integrations to disable. Both are selected by default. "
            "Unchecking an option leaves its current setting unchanged; use Undo to restore it.",
            fg=MUTED,
            bg=WHITE,
            wrap=650,
        )
        ttk.Checkbutton(
            card,
            text="Gemini - right-click menu and top-right tab button",
            variable=self.feature_selection["gemini"],
        ).pack(anchor="w", pady=(10, 3))
        ttk.Checkbutton(
            card,
            text="Google Lens - visual search and page-sharing entry points",
            variable=self.feature_selection["lens"],
        ).pack(anchor="w", pady=(0, 6))
        self.label(
            card,
            "Lens also blocks Chrome's AI Mode page/file sharing. Some Chrome "
            "versions can retain ordinary image search.",
            fg=MUTED,
            bg=WHITE,
            size=10,
            wrap=650,
        )
        if sys.platform == "win32":
            note = "Uses a local Chrome policy. Chrome may show 'Managed by your organization'."
            primary = "Disable selected (default: both)"
        elif sys.platform == "darwin":
            note = "Export a removable policy profile, then install it in System Settings. "
            note += "Exporting alone does not apply the change."
            primary = "Export macOS policy..."
        else:
            note = "Creates a separate Chrome launcher. Quit all Chrome processes, then use "
            note += "'Chrome (Without Gemini)'. The normal launcher stays unchanged."
            primary = "Create AI-off launcher"
        self.label(card, note, fg=MUTED, bg=WHITE, size=10, wrap=650, pady=(10, 10))
        buttons = tk.Frame(card, bg=WHITE)
        buttons.pack(fill="x")
        ttk.Button(buttons, text=primary, style="Accent.TButton", command=self.disable).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(
            buttons,
            text="Undo selected",
            command=lambda: self.perform(lambda: self.control.restore(self.selected_features())),
        ).pack(side="left")

        card = self.card("02", "Hide only the tab / toolbar button")
        self.label(
            card,
            "Hide the Gemini button at the top right while leaving Gemini available "
            "elsewhere. Quit Chrome completely before changing this setting.",
            fg=MUTED,
            bg=WHITE,
            wrap=650,
        )
        self.profile_frame = tk.Frame(card, bg=WHITE)
        self.profile_frame.pack(fill="x", pady=(12, 10))
        buttons = tk.Frame(card, bg=WHITE)
        buttons.pack(fill="x")
        ttk.Button(
            buttons, text="Hide selected buttons", style="Accent.TButton", command=self.hide
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            buttons, text="Undo button changes", command=lambda: self.perform(self.toolbar.restore)
        ).pack(side="left")

        footer = tk.Frame(self.body, bg=BG)
        footer.pack(fill="x", pady=(5, 0))
        ttk.Button(footer, text="Refresh", command=self.refresh).pack(side="left", padx=(0, 6))
        ttk.Button(footer, text="Choose Chrome folder...", command=self.choose_root).pack(
            side="left"
        )
        self.label(
            self.body,
            f"v{__version__}  /  Open source  /  No network calls  /  Reversible",
            fg=MUTED,
            size=10,
            pady=(16, 2),
        )
        self.label(
            self.body,
            "Policies and preferences can change between Chrome releases. "
            "Check chrome://policy after applying a policy.",
            fg=MUTED,
            size=9,
            wrap=680,
        )
        self.refresh()

    def label(self, parent, text, *, bg=BG, fg=INK, size=11, bold=False, wrap=0, pady=0):
        widget = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            anchor="w",
            justify="left",
            wraplength=wrap,
        )
        widget.pack(anchor="w", fill="x", pady=pady)
        return widget

    def card(self, number, title):
        outer = tk.Frame(
            self.body,
            bg=WHITE,
            padx=20,
            pady=18,
            highlightthickness=1,
            highlightbackground="#e0dfd8",
        )
        outer.pack(fill="x", pady=(0, 14))
        self.label(outer, f"{number}   {title}", bg=WHITE, size=16, bold=True, pady=(0, 8))
        return outer

    def refresh(self):
        try:
            running = chrome_running()
            policy = self.control.status()
            self.status_text.configure(
                text=f"Chrome: {'running' if running else 'closed'}  |  {policy}", wraplength=660
            )
            selected = {path: var.get() for path, var in self.profile_selection.items()}
            self.profiles = discover_profiles(self.chrome_root)
            for child in self.profile_frame.winfo_children():
                child.destroy()
            self.profile_selection = {}
            for profile in self.profiles:
                var = tk.BooleanVar(value=selected.get(profile.path, True))
                self.profile_selection[profile.path] = var
                hint = "hidden" if profile.pinned is False else "visible / Chrome default"
                ttk.Checkbutton(
                    self.profile_frame,
                    text=f"{profile.name}  -  {hint}",
                    variable=var,
                ).pack(anchor="w", pady=2)
            if not self.profiles:
                self.label(
                    self.profile_frame,
                    "No Chrome stable profiles found. Choose your Chrome user-data folder below.",
                    bg=WHITE,
                    fg=MUTED,
                    wrap=620,
                )
        except (AppError, OSError) as exc:
            self.status_text.configure(text=str(exc), wraplength=660)

    def perform(self, operation):
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        try:
            result = operation()
        except PermissionError:
            messagebox.showerror(
                "Permission needed",
                "Windows or your administrator blocked this "
                "change. If this is your own PC, close this app and use 'Run as "
                "administrator'. Keep the same Windows account so Undo can find "
                "the original settings. No admin rights are needed for the "
                "toolbar-only option.",
                parent=self.root,
            )
        except (AppError, OSError, ValueError) as exc:
            messagebox.showerror("Could not apply change", str(exc), parent=self.root)
        else:
            messagebox.showinfo("Chrome Without Gemini", result, parent=self.root)
        finally:
            self.root.configure(cursor="")
            self.refresh()

    def disable(self):
        if sys.platform == "darwin":
            destination = filedialog.asksaveasfilename(
                parent=self.root,
                title="Export Chrome Without Gemini policy",
                initialfile="ChromeWithoutGemini.mobileconfig",
                defaultextension=".mobileconfig",
                filetypes=[("macOS profile", "*.mobileconfig")],
            )
            if destination:

                def export():
                    result = self.control.export_mac(Path(destination), self.selected_features())
                    subprocess.Popen(["open", destination])
                    return result

                self.perform(export)
        else:
            self.perform(lambda: self.control.disable(self.selected_features()))

    def selected_features(self):
        return tuple(name for name in DEFAULT_FEATURES if self.feature_selection[name].get())

    def hide(self):
        profiles = [p for p in self.profiles if self.profile_selection[p.path].get()]
        self.perform(lambda: self.toolbar.hide(profiles))

    def choose_root(self):
        path = filedialog.askdirectory(
            parent=self.root,
            title="Choose Chrome user-data folder",
            initialdir=self.chrome_root.parent,
        )
        if path:
            self.chrome_root = Path(path)
            self.refresh()

    def callback_error(self, kind, value, traceback):
        messagebox.showerror(
            "Unexpected error",
            f"{kind.__name__}: {value}\n\nYour recovery information is kept in changes.json.",
            parent=self.root,
        )


def main():
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
