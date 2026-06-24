"""Settings and recent activity view."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional

from ...base.tool import BaseTool
from ...ocr.consent import (
    DEFAULT_ADVANCED_OCR_MODEL_ID,
    DEFAULT_ADVANCED_OCR_PROVIDER,
    clear_advanced_ocr_consent,
    get_saved_advanced_ocr_consent,
    load_advanced_ocr_consent,
    save_advanced_ocr_consent,
)
from ...ui.advanced_ocr_consent import request_advanced_ocr_consent
from ...utils.settings import (
    clear_recent_paths,
    get_recent_paths,
    get_setting,
    set_setting,
)


class SettingsTool(BaseTool):
    """GUI tool for global preferences and recent activity."""

    name: str = "Settings / Recent"
    icon: str = "[SET]"

    RECENT_KEYS = (
        ("recent.inputs", "Recent Inputs"),
        ("recent.outputs", "Recent Outputs"),
        ("recent.reports", "Recent Reports"),
    )

    def render(self, parent: ttk.Frame) -> None:
        self.parent = parent
        prefs = ttk.LabelFrame(parent, text="Global Output Preferences", padding=10)
        prefs.pack(fill="x", pady=(0, 10))

        ttk.Label(prefs, text="When an output file already exists:").pack(side="left")
        self.conflict_var = tk.StringVar(
            value=get_setting("output.conflict_policy", "rename")
        )
        ttk.Combobox(
            prefs,
            textvariable=self.conflict_var,
            values=["rename", "overwrite", "skip"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=10)
        ttk.Button(prefs, text="Save", command=self._save_preferences).pack(side="left")

        consent_frame = ttk.LabelFrame(
            parent, text="Experimental Advanced Local AI OCR Consent", padding=10
        )
        consent_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            consent_frame,
            text=(
                "Real Unlimited-OCR inference is not implemented yet. "
                "Consent only records acknowledgement for future optional local AI OCR."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(0, 6))
        self.advanced_ocr_status_var = tk.StringVar()
        ttk.Label(consent_frame, textvariable=self.advanced_ocr_status_var).pack(
            anchor="w", pady=(0, 8)
        )
        consent_actions = ttk.Frame(consent_frame)
        consent_actions.pack(fill="x")
        ttk.Button(
            consent_actions,
            text="Review / Save Consent",
            command=self._review_advanced_ocr_consent,
        ).pack(side="left")
        ttk.Button(
            consent_actions,
            text="Reset Consent",
            command=self._reset_advanced_ocr_consent,
        ).pack(side="left", padx=(8, 0))

        self.lists: Dict[str, tk.Listbox] = {}
        recent_frame = ttk.Frame(parent)
        recent_frame.pack(fill="both", expand=True)
        recent_frame.columnconfigure((0, 1, 2), weight=1)
        recent_frame.rowconfigure(0, weight=1)

        for column, (key, label) in enumerate(self.RECENT_KEYS):
            frame = ttk.LabelFrame(recent_frame, text=label, padding=10)
            frame.grid(row=0, column=column, sticky="nsew", padx=5)
            listbox = tk.Listbox(frame, height=14)
            listbox.pack(fill="both", expand=True)
            self.lists[key] = listbox
            ttk.Button(
                frame,
                text="Copy Selected",
                command=lambda k=key: self._copy_selected(k),
            ).pack(fill="x", pady=(8, 4))
            ttk.Button(
                frame,
                text="Clear",
                command=lambda k=key: self._clear_recent(k),
            ).pack(fill="x")

        ttk.Button(parent, text="Refresh", command=self._refresh).pack(anchor="e")
        self._refresh()

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        self._save_preferences()

    def _save_preferences(self) -> None:
        set_setting("output.conflict_policy", self.conflict_var.get())
        messagebox.showinfo("Saved", "Output preference saved.")

    def _refresh(self) -> None:
        self._refresh_advanced_ocr_status()
        for key, listbox in self.lists.items():
            listbox.delete(0, tk.END)
            for path in get_recent_paths(key):
                listbox.insert(tk.END, path)

    def _refresh_advanced_ocr_status(self) -> None:
        valid = load_advanced_ocr_consent()
        saved = get_saved_advanced_ocr_consent()
        if valid:
            self.advanced_ocr_status_var.set(
                f"Valid consent saved for {valid.provider}/{valid.model_id} at {valid.timestamp_utc}."
            )
        elif saved:
            self.advanced_ocr_status_var.set(
                "Saved consent exists but is no longer valid for the current provider/model/version."
            )
        else:
            self.advanced_ocr_status_var.set(
                f"No valid consent saved for {DEFAULT_ADVANCED_OCR_PROVIDER}/{DEFAULT_ADVANCED_OCR_MODEL_ID}."
            )

    def _review_advanced_ocr_consent(self) -> None:
        consent = request_advanced_ocr_consent(self.parent.winfo_toplevel())
        if consent is None:
            messagebox.showinfo("Consent Not Saved", "Advanced OCR consent was not saved.")
        else:
            save_advanced_ocr_consent(consent)
            messagebox.showinfo("Saved", "Advanced OCR consent saved.")
        self._refresh_advanced_ocr_status()

    def _reset_advanced_ocr_consent(self) -> None:
        clear_advanced_ocr_consent()
        self._refresh_advanced_ocr_status()
        messagebox.showinfo("Reset", "Advanced OCR consent cleared.")

    def _copy_selected(self, key: str) -> None:
        listbox = self.lists[key]
        selection = listbox.curselection()
        if not selection:
            return
        value = listbox.get(selection[0])
        listbox.clipboard_clear()
        listbox.clipboard_append(value)
        messagebox.showinfo("Copied", "Path copied to clipboard.")

    def _clear_recent(self, key: str) -> None:
        clear_recent_paths(key)
        self._refresh()
