"""Plan-bound informed consent for optional Unlimited-OCR installation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .metadata import load_compatibility_metadata
from .models import CompatibilityReport, CompatibilityStatus, RuntimePlan

DEPLOYMENT_CONSENT_VERSION = "2026-07-14.1"
INSTALL_ACTION = "install_and_enable"
REQUIRED_INSTALL_ACKNOWLEDGEMENTS = (
    "large_download",
    "private_environment",
    "custom_code",
    "resource_usage",
    "local_processing_and_temporary_files",
    "no_performance_guarantee",
)


@dataclass(frozen=True)
class DeploymentConsent:
    consent_id: str
    consent_version: str
    action: str
    plan_id: str
    model_id: str
    model_revision: str
    metadata_revision: str
    acknowledgements: Mapping[str, bool]
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        plan: RuntimePlan,
        metadata_revision: str,
        acknowledgements: Mapping[str, bool],
        action: str = INSTALL_ACTION,
    ) -> "DeploymentConsent":
        missing = [
            key for key in REQUIRED_INSTALL_ACKNOWLEDGEMENTS if not acknowledgements.get(key)
        ]
        if missing:
            raise ValueError(f"Missing required installation acknowledgements: {', '.join(missing)}")
        created_at = datetime.now(timezone.utc).isoformat()
        material = json.dumps(
            {
                "version": DEPLOYMENT_CONSENT_VERSION,
                "action": action,
                "plan_id": plan.plan_id,
                "model_revision": plan.model_revision,
                "metadata_revision": metadata_revision,
                "created_at": created_at,
            },
            sort_keys=True,
        )
        return cls(
            consent_id=hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
            consent_version=DEPLOYMENT_CONSENT_VERSION,
            action=action,
            plan_id=plan.plan_id,
            model_id=plan.model_id,
            model_revision=plan.model_revision,
            metadata_revision=metadata_revision,
            acknowledgements={
                key: bool(acknowledgements.get(key))
                for key in REQUIRED_INSTALL_ACKNOWLEDGEMENTS
            },
            created_at=created_at,
        )

    def is_valid_for(self, plan: RuntimePlan, *, metadata_revision: str) -> bool:
        return (
            self.consent_version == DEPLOYMENT_CONSENT_VERSION
            and self.action == INSTALL_ACTION
            and self.plan_id == plan.plan_id
            and self.model_id == plan.model_id
            and self.model_revision == plan.model_revision
            and self.metadata_revision == metadata_revision
            and all(self.acknowledgements.get(key) for key in REQUIRED_INSTALL_ACKNOWLEDGEMENTS)
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DeploymentConsent":
        acknowledgements = value.get("acknowledgements", {})
        return cls(
            consent_id=str(value.get("consent_id", "")),
            consent_version=str(value.get("consent_version", "")),
            action=str(value.get("action", "")),
            plan_id=str(value.get("plan_id", "")),
            model_id=str(value.get("model_id", "")),
            model_revision=str(value.get("model_revision", "")),
            metadata_revision=str(value.get("metadata_revision", "")),
            acknowledgements=(
                {str(key): bool(item) for key, item in acknowledgements.items()}
                if isinstance(acknowledgements, Mapping)
                else {}
            ),
            created_at=str(value.get("created_at", "")),
        )


def build_consent_summary(
    compatibility: CompatibilityReport,
    plan: RuntimePlan,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return all material facts that must appear before the install action."""

    estimates = (metadata or load_compatibility_metadata())["resource_estimates"]
    setup_allowed = plan.executable and compatibility.status not in {
        CompatibilityStatus.UNSUPPORTED,
        CompatibilityStatus.UNKNOWN,
    }
    return {
        "why_recommended": (
            "Unlimited-OCR can preserve complex document structure and mixed-language layout "
            "better than basic OCR on supported hardware; quality is verified only after benchmark."
        ),
        "comparison_to_basic_ocr": (
            "The existing Tesseract provider remains installed and is used as a fallback."
        ),
        "local_only": True,
        "data_leaves_device": False,
        "estimated_download_bytes": compatibility.estimated_download_size,
        "estimated_disk_usage_bytes": compatibility.estimated_disk_usage,
        "estimated_vram_bytes": compatibility.estimated_vram_requirement,
        "minimum_ram_bytes": int(estimates["minimum_ram_bytes"]),
        "recommended_ram_bytes": int(estimates["recommended_ram_bytes"]),
        "estimated_ram_note": (
            "The metadata RAM values are conservative gates; actual peak RAM is measured "
            "during the post-install benchmark."
        ),
        "requires_admin": plan.requires_admin,
        "driver_update_included": False,
        "system_cuda_change_included": False,
        "creates_private_environment": True,
        "runtime_root": plan.runtime_root,
        "model_cache_dir": plan.model_cache_dir,
        "backend": plan.backend.value,
        "recommended_backend": compatibility.recommended_backend.value,
        "recommended_runtime": compatibility.recommended_runtime,
        "setup_allowed": setup_allowed,
        "blocking_reasons": plan.blocked_reasons,
        "model_id": plan.model_id,
        "model_revision": plan.model_revision,
        "reversible_changes": plan.reversible_changes,
        "system_changes": plan.system_changes,
        "known_risks": plan.warnings,
        "cannot_guarantee": (
            "OCR accuracy, real-time speed, full 32K context, and freedom from GPU OOM "
            "cannot be guaranteed before a real local benchmark."
        ),
        "actions": (
            ("install_and_enable", "view_technical_details", "not_now")
            if setup_allowed
            else ("view_technical_details", "not_now")
        ),
    }
