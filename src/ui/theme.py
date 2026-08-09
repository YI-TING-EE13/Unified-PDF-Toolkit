"""Shared visual tokens and ttk styles for the desktop application."""

from __future__ import annotations

from dataclasses import dataclass
from tkinter import ttk


@dataclass(frozen=True)
class Palette:
    canvas: str = "#F3F5F8"
    surface: str = "#FFFFFF"
    surface_muted: str = "#EEF2F6"
    border: str = "#D9E0E8"
    border_strong: str = "#C7D0DB"
    text: str = "#172033"
    text_muted: str = "#667085"
    text_subtle: str = "#98A2B3"
    accent: str = "#2563EB"
    accent_hover: str = "#1D4ED8"
    accent_soft: str = "#E8F0FF"
    success: str = "#0F9D72"
    danger: str = "#C2415C"
    sidebar: str = "#121A2A"
    sidebar_hover: str = "#1A2538"
    sidebar_active: str = "#22314A"
    sidebar_text: str = "#D7DEEA"


PALETTE = Palette()
FONT_FAMILY = "Segoe UI"


def configure_theme(root) -> ttk.Style:
    """Apply the app theme and return the configured ttk style registry."""

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.configure(background=PALETTE.canvas)
    root.option_add("*Font", (FONT_FAMILY, 10))
    root.option_add("*Listbox.background", PALETTE.surface)
    root.option_add("*Listbox.foreground", PALETTE.text)
    root.option_add("*Listbox.selectBackground", PALETTE.accent_soft)
    root.option_add("*Listbox.selectForeground", PALETTE.text)
    root.option_add("*Listbox.relief", "flat")
    root.option_add("*Listbox.borderWidth", 0)
    root.option_add("*Listbox.highlightThickness", 1)
    root.option_add("*Listbox.highlightBackground", PALETTE.border)
    root.option_add("*Listbox.highlightColor", PALETTE.accent)
    root.option_add("*Text.background", PALETTE.surface)
    root.option_add("*Text.foreground", PALETTE.text)
    root.option_add("*Text.relief", "flat")
    root.option_add("*Text.borderWidth", 0)
    root.option_add("*Text.highlightThickness", 1)
    root.option_add("*Text.highlightBackground", PALETTE.border)
    root.option_add("*Text.highlightColor", PALETTE.accent)

    style.configure(".", font=(FONT_FAMILY, 10), foreground=PALETTE.text)
    style.configure("TFrame", background=PALETTE.surface)
    style.configure("Main.TFrame", background=PALETTE.canvas)
    style.configure("View.TFrame", background=PALETTE.canvas)
    style.configure("ToolHeader.TFrame", background=PALETTE.canvas)
    style.configure("ToolBody.TFrame", background=PALETTE.surface)
    style.configure("Status.TFrame", background=PALETTE.surface)

    style.configure("TLabel", background=PALETTE.surface, foreground=PALETTE.text)
    style.configure(
        "Eyebrow.TLabel",
        background=PALETTE.canvas,
        foreground=PALETTE.accent,
        font=(FONT_FAMILY, 9, "bold"),
    )
    style.configure(
        "Header.TLabel",
        background=PALETTE.canvas,
        foreground=PALETTE.text,
        font=(FONT_FAMILY, 24, "bold"),
    )
    style.configure(
        "Subheader.TLabel",
        background=PALETTE.canvas,
        foreground=PALETTE.text_muted,
        font=(FONT_FAMILY, 10),
    )
    style.configure("Muted.TLabel", foreground=PALETTE.text_muted)
    style.configure("Subtle.TLabel", foreground=PALETTE.text_subtle)
    style.configure(
        "Success.TLabel", foreground=PALETTE.success, font=(FONT_FAMILY, 9, "bold")
    )
    style.configure(
        "Status.TLabel", background=PALETTE.surface, foreground=PALETTE.text_muted
    )
    style.configure(
        "StatusStrong.TLabel",
        background=PALETTE.surface,
        foreground=PALETTE.text,
        font=(FONT_FAMILY, 9, "bold"),
    )

    style.configure(
        "TLabelframe",
        background=PALETTE.surface,
        bordercolor=PALETTE.border,
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "TLabelframe.Label",
        background=PALETTE.surface,
        foreground=PALETTE.text,
        font=(FONT_FAMILY, 10, "bold"),
    )

    style.configure(
        "TButton",
        background=PALETTE.surface_muted,
        foreground=PALETTE.text,
        bordercolor=PALETTE.border,
        lightcolor=PALETTE.surface_muted,
        darkcolor=PALETTE.surface_muted,
        borderwidth=1,
        focusthickness=2,
        focuscolor=PALETTE.accent,
        padding=(12, 8),
    )
    style.map(
        "TButton",
        background=[("pressed", PALETTE.border), ("active", "#E5EAF0")],
        bordercolor=[("focus", PALETTE.accent), ("active", PALETTE.border_strong)],
        foreground=[("disabled", PALETTE.text_subtle)],
    )
    style.configure(
        "Quiet.TButton",
        background=PALETTE.surface,
        bordercolor=PALETTE.border,
        lightcolor=PALETTE.surface,
        darkcolor=PALETTE.surface,
        padding=(10, 7),
    )
    style.map(
        "Quiet.TButton",
        background=[("pressed", PALETTE.surface_muted), ("active", PALETTE.surface_muted)],
    )
    style.configure(
        "Accent.TButton",
        background=PALETTE.accent,
        foreground="#FFFFFF",
        bordercolor=PALETTE.accent,
        lightcolor=PALETTE.accent,
        darkcolor=PALETTE.accent,
        font=(FONT_FAMILY, 10, "bold"),
        padding=(16, 9),
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", PALETTE.accent_hover), ("active", PALETTE.accent_hover)],
        bordercolor=[("pressed", PALETTE.accent_hover), ("active", PALETTE.accent_hover)],
        foreground=[("disabled", "#D0D5DD"), ("!disabled", "#FFFFFF")],
    )
    style.configure(
        "Danger.TButton",
        background=PALETTE.surface,
        foreground=PALETTE.danger,
        bordercolor="#F2C7D0",
        lightcolor=PALETTE.surface,
        darkcolor=PALETTE.surface,
    )

    field_options = {
        "fieldbackground": PALETTE.surface,
        "foreground": PALETTE.text,
        "bordercolor": PALETTE.border,
        "lightcolor": PALETTE.surface,
        "darkcolor": PALETTE.surface,
        "padding": 7,
    }
    style.configure("TEntry", **field_options)
    style.configure("TCombobox", **field_options)
    style.configure("TSpinbox", **field_options)
    for style_name in ("TEntry", "TCombobox", "TSpinbox"):
        style.map(
            style_name,
            bordercolor=[("focus", PALETTE.accent)],
            lightcolor=[("focus", PALETTE.accent)],
            darkcolor=[("focus", PALETTE.accent)],
        )

    style.configure("TCheckbutton", background=PALETTE.surface, foreground=PALETTE.text)
    style.configure("TRadiobutton", background=PALETTE.surface, foreground=PALETTE.text)
    style.map(
        "TCheckbutton",
        background=[("active", PALETTE.surface)],
        indicatorcolor=[("selected", PALETTE.accent)],
    )
    style.map(
        "TRadiobutton",
        background=[("active", PALETTE.surface)],
        indicatorcolor=[("selected", PALETTE.accent)],
    )

    style.configure(
        "Treeview",
        background=PALETTE.surface,
        fieldbackground=PALETTE.surface,
        foreground=PALETTE.text,
        bordercolor=PALETTE.border,
        rowheight=30,
    )
    style.configure(
        "Treeview.Heading",
        background=PALETTE.surface_muted,
        foreground=PALETTE.text,
        font=(FONT_FAMILY, 9, "bold"),
        padding=(8, 7),
        relief="flat",
    )
    style.map("Treeview", background=[("selected", PALETTE.accent_soft)])

    style.configure("TNotebook", background=PALETTE.surface, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=PALETTE.surface_muted,
        foreground=PALETTE.text_muted,
        padding=(14, 8),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", PALETTE.surface)],
        foreground=[("selected", PALETTE.accent)],
    )
    style.configure(
        "Horizontal.TProgressbar",
        background=PALETTE.accent,
        troughcolor=PALETTE.surface_muted,
        bordercolor=PALETTE.surface_muted,
        lightcolor=PALETTE.accent,
        darkcolor=PALETTE.accent,
        thickness=8,
    )
    style.configure("TSeparator", background=PALETTE.border)
    return style
