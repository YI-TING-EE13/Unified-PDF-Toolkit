"""Reusable consent dialog for optional advanced local AI OCR."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict

from ..ocr.consent import (
    ADVANCED_OCR_CONSENT_TEXT_VERSION,
    DEFAULT_ADVANCED_OCR_MODEL_ID,
    DEFAULT_ADVANCED_OCR_PROVIDER,
    AdvancedOcrConsent,
    create_advanced_ocr_consent,
)

ACKNOWLEDGEMENT_LABELS = (
    (
        "acknowledged_model_download_risk",
        "Future real model use may require downloading a large local model.",
    ),
    (
        "acknowledged_custom_code_risk",
        "Future real model use may execute model custom code / trust_remote_code.",
    ),
    (
        "acknowledged_gpu_vram_use",
        "Future real model use may require an NVIDIA GPU and substantial VRAM.",
    ),
    (
        "acknowledged_temporary_page_images",
        "PDF pages may be rendered into temporary local page images for OCR.",
    ),
)


class AdvancedOcrConsentDialog(tk.Toplevel):
    """Modal dialog that returns consent only after explicit acknowledgements."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        provider: str = DEFAULT_ADVANCED_OCR_PROVIDER,
        model_id: str = DEFAULT_ADVANCED_OCR_MODEL_ID,
        consent_text_version: str = ADVANCED_OCR_CONSENT_TEXT_VERSION,
    ) -> None:
        super().__init__(parent)
        self.title("Advanced Local AI OCR Consent")
        self.resizable(False, False)
        self.provider = provider
        self.model_id = model_id
        self.consent_text_version = consent_text_version
        self.result: AdvancedOcrConsent | None = None
        self.vars: Dict[str, tk.BooleanVar] = {
            key: tk.BooleanVar(value=False) for key, _label in ACKNOWLEDGEMENT_LABELS
        }

        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._build_ui()
        self.grab_set()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Optional Advanced Local AI OCR",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "This app does not currently run real Unlimited-OCR inference. "
                "This consent records acknowledgement for future experimental "
                "local AI OCR features only."
            ),
            wraplength=560,
        ).pack(anchor="w", pady=(8, 8))
        ttk.Label(
            frame,
            text=(
                f"Provider/model: {self.provider}/{self.model_id}\n"
                f"Consent text version: {self.consent_text_version}\n"
                "Files and OCR text must not be uploaded by this feature."
            ),
            wraplength=560,
        ).pack(anchor="w", pady=(0, 8))

        checks = ttk.LabelFrame(frame, text="Required acknowledgements", padding=10)
        checks.pack(fill="x", pady=(0, 12))
        for key, label in ACKNOWLEDGEMENT_LABELS:
            ttk.Checkbutton(
                checks,
                text=label,
                variable=self.vars[key],
                command=self._update_state,
            ).pack(anchor="w", pady=2)

        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        ttk.Button(actions, text="Cancel", command=self._cancel).pack(side="right")
        self.accept_btn = ttk.Button(
            actions,
            text="Save Consent",
            command=self._accept,
            state="disabled",
        )
        self.accept_btn.pack(side="right", padx=(0, 8))

    def _acknowledgements(self) -> Dict[str, bool]:
        return {key: bool(var.get()) for key, var in self.vars.items()}

    def _update_state(self) -> None:
        state = "normal" if all(self._acknowledgements().values()) else "disabled"
        self.accept_btn.configure(state=state)

    def _accept(self) -> None:
        self.result = create_advanced_ocr_consent(
            provider=self.provider,
            model_id=self.model_id,
            consent_text_version=self.consent_text_version,
            acknowledgements=self._acknowledgements(),
        )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


def request_advanced_ocr_consent(
    parent: tk.Misc,
    *,
    provider: str = DEFAULT_ADVANCED_OCR_PROVIDER,
    model_id: str = DEFAULT_ADVANCED_OCR_MODEL_ID,
    consent_text_version: str = ADVANCED_OCR_CONSENT_TEXT_VERSION,
) -> AdvancedOcrConsent | None:
    """Show the modal consent dialog and return saved consent or None."""

    dialog = AdvancedOcrConsentDialog(
        parent,
        provider=provider,
        model_id=model_id,
        consent_text_version=consent_text_version,
    )
    parent.wait_window(dialog)
    return dialog.result
