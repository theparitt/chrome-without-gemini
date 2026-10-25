"""Locally drawn desktop components. No remote fonts, images, or dependencies."""

import tkinter as tk
from tkinter import font as tkfont

C = {
    "bg": "#f5f7fa",
    "surface": "#ffffff",
    "ink": "#182334",
    "muted": "#687587",
    "faint": "#98a3b3",
    "line": "#e5eaf1",
    "nav": "#121d2e",
    "nav_active": "#26354b",
    "orange": "#e96832",
    "orange_hover": "#d95723",
    "orange_soft": "#fff2eb",
    "green": "#277d66",
    "green_soft": "#eaf6f0",
    "purple": "#7860cf",
    "purple_soft": "#f1edfc",
    "blue": "#487aba",
    "blue_soft": "#edf3fb",
    "amber": "#a66c24",
    "amber_soft": "#fff6e7",
}


def rounded(canvas, x1, y1, x2, y2, radius=12, **options):
    r = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    return canvas.create_polygon(
        x1 + r,
        y1,
        x2 - r,
        y1,
        x2,
        y1,
        x2,
        y1 + r,
        x2,
        y2 - r,
        x2,
        y2,
        x2 - r,
        y2,
        x1 + r,
        y2,
        x1,
        y2,
        x1,
        y2 - r,
        x1,
        y1 + r,
        x1,
        y1,
        smooth=True,
        splinesteps=24,
        **options,
    )


def text(parent, value, size=11, color=None, bold=False, wrap=0):
    return tk.Label(
        parent,
        text=value,
        font=(parent.winfo_toplevel().ui_font, size, "bold" if bold else "normal"),
        fg=color or C["ink"],
        bg=parent.cget("bg"),
        anchor="w",
        justify="left",
        wraplength=wrap,
        bd=0,
        padx=0,
        pady=0,
    )


class Button(tk.Canvas):
    def __init__(self, parent, label, command, primary=False, width=None, compact=False):
        self.command, self.label, self.primary = command, label, primary
        self.enabled, self.hover, self.focused = True, False, False
        self.font = (parent.winfo_toplevel().ui_font, 10 if compact else 11, "bold")
        super().__init__(
            parent,
            width=width or tkfont.Font(font=self.font).measure(label) + 34,
            height=34 if compact else 44,
            bg=parent.cget("bg"),
            highlightthickness=0,
            takefocus=True,
            cursor="hand2",
            bd=0,
        )
        self.bind("<Configure>", lambda event: self.draw())
        self.bind("<Enter>", lambda event: self.change(hover=True))
        self.bind("<Leave>", lambda event: self.change(hover=False))
        self.bind("<FocusIn>", lambda event: self.change(focused=True))
        self.bind("<FocusOut>", lambda event: self.change(focused=False))
        for event in ("<Button-1>", "<Return>", "<space>"):
            self.bind(event, self.invoke)

    def change(self, **values):
        for key, value in values.items():
            setattr(self, key, value)
        self.draw()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow", takefocus=enabled)
        self.draw()

    def invoke(self, event=None):
        if self.enabled:
            self.focus_set()
            self.command()
        return "break"

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        fill = (
            (C["orange_hover"] if self.hover else C["orange"])
            if self.primary
            else ("#edf1f6" if self.hover else C["surface"])
        )
        ink = "#ffffff" if self.primary else C["ink"]
        if not self.enabled:
            fill, ink = "#e9edf2", "#a2abb8"
        outline = C["orange"] if self.focused else fill if self.primary else C["line"]
        rounded(
            self, 1, 1, w - 1, h - 1, 9, fill=fill, outline=outline, width=2 if self.focused else 1
        )
        self.create_text(w / 2, h / 2, text=self.label, fill=ink, font=self.font)


class Toggle(tk.Canvas):
    def __init__(self, parent, variable, command=None):
        super().__init__(
            parent,
            width=46,
            height=30,
            bg=parent.cget("bg"),
            bd=0,
            highlightthickness=0,
            takefocus=True,
            cursor="hand2",
        )
        self.variable, self.command, self.focused = variable, command, False
        self.trace = variable.trace_add("write", lambda *args: self.draw())
        for event in ("<Button-1>", "<Return>", "<space>"):
            self.bind(event, self.toggle)
        self.bind("<FocusIn>", lambda event: self.focus(True))
        self.bind("<FocusOut>", lambda event: self.focus(False))
        self.bind("<Destroy>", lambda event: variable.trace_remove("write", self.trace))
        self.draw()

    def focus(self, value):
        self.focused = value
        self.draw()

    def toggle(self, event=None):
        self.focus_set()
        self.variable.set(not self.variable.get())
        if self.command:
            self.command()
        return "break"

    def draw(self):
        self.delete("all")
        if self.focused:
            rounded(self, 0, 1, 46, 29, 14, fill="", outline=C["orange"])
        rounded(
            self,
            3,
            4,
            43,
            26,
            11,
            fill=C["orange"] if self.variable.get() else "#cdd5df",
            outline="",
        )
        x = 24 if self.variable.get() else 6
        self.create_oval(x, 7, x + 16, 23, fill="#ffffff", outline="")


class Pill(tk.Canvas):
    def __init__(self, parent, label, color="muted", fill="bg", dot=False):
        self.font = (parent.winfo_toplevel().ui_font, 9)
        self.color, self.fill, self.dot = color, fill, dot
        super().__init__(parent, height=27, bg=parent.cget("bg"), bd=0, highlightthickness=0)
        self.update_value(label)

    def update_value(self, label, color=None, fill=None):
        self.color, self.fill = color or self.color, fill or self.fill
        w = tkfont.Font(font=self.font).measure(label) + (32 if self.dot else 22)
        self.configure(width=w)
        self.delete("all")
        rounded(self, 0, 0, w, 27, 13, fill=C[self.fill], outline="")
        if self.dot:
            self.create_oval(10, 11, 15, 16, fill=C[self.color], outline="")
        self.create_text(
            w / 2 + (4 if self.dot else 0), 13.5, text=label, fill=C[self.color], font=self.font
        )


class Card(tk.Canvas):
    def __init__(self, parent, padding=22):
        super().__init__(parent, bg=parent.cget("bg"), bd=0, highlightthickness=0)
        self.padding = padding
        self.inner = tk.Frame(self, bg=C["surface"])
        self.window = self.create_window(padding, padding, window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>",
            lambda event: self.configure(height=self.inner.winfo_reqheight() + 2 * padding),
        )
        self.bind("<Configure>", self.resize)

    def resize(self, event):
        self.itemconfigure(self.window, width=max(1, event.width - 2 * self.padding))
        self.delete("surface")
        rounded(
            self,
            1,
            1,
            event.width - 1,
            event.height - 1,
            13,
            fill=C["surface"],
            outline=C["line"],
            tags="surface",
        )
        self.tag_lower("surface")


class Icon(tk.Canvas):
    def __init__(self, parent, kind, size=36, color=None, fill=None):
        super().__init__(
            parent, width=size, height=size, bg=parent.cget("bg"), highlightthickness=0, bd=0
        )
        self.kind, self.size = kind, size
        self.draw(color or C["muted"], fill)

    def draw(self, color, fill=None):
        self.delete("all")
        s = self.size / 36
        if fill:
            rounded(self, 0, 0, self.size, self.size, 10, fill=fill, outline="")

        def line(coords):
            self.create_line(
                *[n * s for n in coords],
                fill=color,
                width=1.7 * s,
                capstyle="round",
                joinstyle="round",
            )

        if self.kind == "spark":
            self.create_polygon(
                *[n * s for n in (18, 7, 21, 15, 29, 18, 21, 21, 18, 29, 15, 21, 7, 18, 15, 15)],
                fill=color,
                outline="",
            )
        elif self.kind == "lens":
            for coords in (
                [13, 9, 10, 9, 9, 10, 9, 14],
                [23, 9, 27, 9, 28, 10, 28, 14],
                [9, 23, 9, 27, 10, 28, 14, 28],
                [23, 28, 27, 28, 28, 27, 28, 23],
            ):
                line(coords)
            self.create_oval(13 * s, 13 * s, 23 * s, 23 * s, outline=color, width=1.7 * s)
        elif self.kind == "sliders":
            for y, x in ((11, 14), (18, 23), (25, 16)):
                line([8, y, 28, y])
                self.create_oval(
                    (x - 2) * s, (y - 2) * s, (x + 2) * s, (y + 2) * s, fill=color, outline=""
                )
        elif self.kind in ("browser", "brand"):
            line([8, 11, 28, 11, 28, 27, 8, 27, 8, 11])
            line([8, 16, 28, 16])
            if self.kind == "brand":
                line([16, 22, 20, 26, 28, 18])
        elif self.kind == "undo":
            line([12, 10, 7, 15, 13, 15])
            line([8, 14, 21, 14, 27, 18, 27, 23, 23, 27, 15, 27])
        else:
            self.create_oval(7 * s, 7 * s, 29 * s, 29 * s, outline=color, width=1.5 * s)
            line([18, 16, 18, 24])
            line([18, 12, 18, 12.5])


def app_icon(root):
    icon = tk.PhotoImage(master=root, width=32, height=32)
    for y in range(32):
        for x in range(32):
            if (
                5 <= x < 27
                or 5 <= y < 27
                or (x - (5 if x < 16 else 26)) ** 2 + (y - (5 if y < 16 else 26)) ** 2 <= 25
            ):
                icon.put(C["orange"], (x, y))
    icon.put("#ffffff", to=(7, 9, 25, 24))
    icon.put(C["orange"], to=(9, 14, 23, 22))
    for x in (10, 14, 18):
        icon.put(C["orange"], to=(x, 11, x + 2, 12))
    root.iconphoto(True, icon)
    root._app_icon = icon
