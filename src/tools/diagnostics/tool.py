"""Diagnostics and support view."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional

from ...base.tool import BaseTool
from ...utils.diagnostics import collect_diagnostics, diagnostics_to_text


class DiagnosticsTool(BaseTool):
    """GUI tool for runtime dependency and environment diagnostics."""

    name: str = "Diagnostics"
    icon: str = "[?]"

    def render(self, parent: ttk.Frame) -> None:
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(
            actions,
            text="Run Checks",
            command=self.execute,
            style="Accent.TButton",
        ).pack(side="left")
        ttk.Button(actions, text="Copy Results", command=self._copy_results).pack(
            side="left", padx=8
        )

        self.tree = ttk.Treeview(
            parent, columns=("status", "detail", "suggestion"), show="headings", height=12
        )
        self.tree.heading("status", text="Status")
        self.tree.heading("detail", text="Detail")
        self.tree.heading("suggestion", text="Suggestion")
        self.tree.column("status", width=90, stretch=False)
        self.tree.column("detail", width=430)
        self.tree.column("suggestion", width=430)
        self.tree.pack(fill="both", expand=True)

        self.summary = tk.Text(parent, height=8, wrap="word")
        self.summary.pack(fill="x", pady=(8, 0))
        self.execute()

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.checks = collect_diagnostics()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for check in self.checks:
            self.tree.insert(
                "",
                tk.END,
                values=(check.status.upper(), f"{check.name}: {check.detail}", check.suggestion),
            )
        text = diagnostics_to_text(self.checks)
        self.summary.delete("1.0", tk.END)
        self.summary.insert("1.0", text)

    def _copy_results(self) -> None:
        text = self.summary.get("1.0", tk.END).strip()
        if not text:
            return
        self.summary.clipboard_clear()
        self.summary.clipboard_append(text)
        messagebox.showinfo("Copied", "Diagnostic results copied to clipboard.")
