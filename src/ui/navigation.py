"""Grouped navigation rail with one animated active indicator."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .motion import MotionController
from .theme import FONT_FAMILY, PALETTE


class NavigationRail(tk.Frame):
    """Own grouped navigation layout, hover states, and active-item motion."""

    def __init__(
        self,
        parent,
        *,
        on_select: Callable[[str], None],
        motion: MotionController,
    ) -> None:
        super().__init__(parent, background=PALETTE.sidebar, highlightthickness=0)
        self._on_select = on_select
        self._motion = motion
        self._buttons: dict[str, tk.Button] = {}
        self._active_item: str | None = None
        self._indicator = tk.Frame(self, background=PALETTE.accent, width=3, height=1)

    @property
    def active_item(self) -> str | None:
        return self._active_item

    @property
    def buttons(self) -> dict[str, tk.Button]:
        """Return the maintained button mapping for compatibility and inspection."""

        return dict(self._buttons)

    def add_section(self, label: str) -> None:
        tk.Label(
            self,
            text=label.upper(),
            background=PALETTE.sidebar,
            foreground="#7F8BA1",
            font=(FONT_FAMILY, 8, "bold"),
            anchor="w",
            padx=18,
            pady=7,
        ).pack(fill="x", pady=(8, 1))

    def add_item(self, item_id: str, label: str) -> None:
        button = tk.Button(
            self,
            text=label,
            command=lambda: self._on_select(item_id),
            background=PALETTE.sidebar,
            foreground=PALETTE.sidebar_text,
            activebackground=PALETTE.sidebar_hover,
            activeforeground="#FFFFFF",
            disabledforeground="#69758A",
            font=(FONT_FAMILY, 10),
            anchor="w",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=18,
            pady=8,
            cursor="hand2",
        )
        button.pack(fill="x", padx=(10, 8), pady=1)
        button.bind("<Enter>", lambda _event, key=item_id: self._set_hover(key, True))
        button.bind("<Leave>", lambda _event, key=item_id: self._set_hover(key, False))
        self._buttons[item_id] = button

    def select(self, item_id: str, *, animate: bool = True) -> None:
        if item_id not in self._buttons:
            raise KeyError(f"Unknown navigation item: {item_id}")

        previous = self._active_item
        if previous and previous in self._buttons:
            self._buttons[previous].configure(
                background=PALETTE.sidebar,
                foreground=PALETTE.sidebar_text,
                font=(FONT_FAMILY, 10),
            )

        button = self._buttons[item_id]
        button.configure(
            background=PALETTE.sidebar_active,
            foreground="#FFFFFF",
            font=(FONT_FAMILY, 10, "bold"),
        )
        self._active_item = item_id
        self.update_idletasks()
        target_y = button.winfo_y()
        target_height = max(1, button.winfo_height())
        if target_height <= 1:
            self.after_idle(lambda: self.select(item_id, animate=False))
            return

        current_y = self._indicator.winfo_y() if previous else target_y
        self._indicator.lift()

        def update(value: float) -> None:
            y = round(current_y + (target_y - current_y) * value)
            self._indicator.place(x=6, y=y, width=3, height=target_height)

        self._motion.animate(
            "navigation-indicator",
            170 if animate else 0,
            update,
        )

    def _set_hover(self, item_id: str, entered: bool) -> None:
        if item_id == self._active_item:
            return
        self._buttons[item_id].configure(
            background=PALETTE.sidebar_hover if entered else PALETTE.sidebar
        )
