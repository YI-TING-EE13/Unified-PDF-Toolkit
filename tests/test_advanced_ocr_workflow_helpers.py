import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.ocr import OcrConsentRequiredError, OcrEngine
from src.ocr.consent import AdvancedOcrConsent
from src.ocr.exceptions import OcrBackendUnavailableError
from src.ocr.local_endpoint import (
    LOCAL_ENDPOINT_MODEL_ID,
    LOCAL_ENDPOINT_PROVIDER,
    DEFAULT_LOCAL_ENDPOINT_URL,
)
from src.ocr.local_model import (
    LOCAL_MODEL_MODEL_ID,
    LOCAL_MODEL_PROVIDER,
    LocalModelOcrBackend,
)
from src.ocr.models import OcrPageResult, OcrResult
from src.ocr.unlimited_fake import UNLIMITED_OCR_MODEL_ID, UNLIMITED_OCR_PROVIDER
from src.ocr.workflow import (
    AdvancedOcrBackendChoice,
    AdvancedOcrBackendSelection,
    create_backend_for_selection,
    fake_backend_selection,
    local_model_future_selection,
    local_endpoint_mock_selection,
    normalise_output_formats,
    provider_model_for_selection,
    require_consent_for_selection,
    run_advanced_ocr_workflow,
    user_safe_ocr_error_message,
    write_ocr_outputs,
)


def _fake_consent() -> AdvancedOcrConsent:
    return AdvancedOcrConsent.create(
        provider=UNLIMITED_OCR_PROVIDER,
        model_id=UNLIMITED_OCR_MODEL_ID,
        acknowledged_model_download_risk=True,
        acknowledged_custom_code_risk=True,
        acknowledged_gpu_vram_use=True,
        acknowledged_temporary_page_images=True,
    )


def _endpoint_consent() -> AdvancedOcrConsent:
    return AdvancedOcrConsent.create(
        provider=LOCAL_ENDPOINT_PROVIDER,
        model_id=LOCAL_ENDPOINT_MODEL_ID,
        acknowledged_model_download_risk=True,
        acknowledged_custom_code_risk=True,
        acknowledged_gpu_vram_use=True,
        acknowledged_temporary_page_images=True,
    )


def _local_model_consent() -> AdvancedOcrConsent:
    return AdvancedOcrConsent.create(
        provider=LOCAL_MODEL_PROVIDER,
        model_id=LOCAL_MODEL_MODEL_ID,
        acknowledged_model_download_risk=True,
        acknowledged_custom_code_risk=True,
        acknowledged_gpu_vram_use=True,
        acknowledged_temporary_page_images=True,
    )


class AdvancedOcrWorkflowHelperTests(unittest.TestCase):
    def test_backend_selection_provider_model_mapping(self):
        self.assertEqual(
            provider_model_for_selection(fake_backend_selection()),
            (UNLIMITED_OCR_PROVIDER, UNLIMITED_OCR_MODEL_ID),
        )
        self.assertEqual(
            provider_model_for_selection(
                local_endpoint_mock_selection(
                    endpoint_url=DEFAULT_LOCAL_ENDPOINT_URL,
                    transport=lambda url, payload, timeout: {"pages": []},
                )
            ),
            (LOCAL_ENDPOINT_PROVIDER, LOCAL_ENDPOINT_MODEL_ID),
        )
        self.assertEqual(
            provider_model_for_selection(local_model_future_selection()),
            (LOCAL_MODEL_PROVIDER, LOCAL_MODEL_MODEL_ID),
        )

    def test_consent_gate_allows_matching_and_rejects_missing_or_wrong_consent(self):
        require_consent_for_selection(_fake_consent(), fake_backend_selection())
        require_consent_for_selection(_local_model_consent(), local_model_future_selection())

        with self.assertRaises(OcrConsentRequiredError):
            require_consent_for_selection(None, fake_backend_selection())
        with self.assertRaises(OcrConsentRequiredError):
            require_consent_for_selection(_endpoint_consent(), local_model_future_selection())
        with self.assertRaises(OcrConsentRequiredError):
            require_consent_for_selection(_fake_consent(), local_endpoint_mock_selection(
                endpoint_url=DEFAULT_LOCAL_ENDPOINT_URL,
                transport=lambda url, payload, timeout: {"pages": []},
            ))

    def test_local_model_future_selection_creates_scaffold_backend(self):
        backend = create_backend_for_selection(
            local_model_future_selection(),
            consent=_local_model_consent(),
        )

        self.assertIsInstance(backend, LocalModelOcrBackend)

    def test_local_endpoint_selection_requires_mock_transport(self):
        selection = AdvancedOcrBackendSelection(
            AdvancedOcrBackendChoice.LOCAL_ENDPOINT_MOCK,
            endpoint_url=DEFAULT_LOCAL_ENDPOINT_URL,
        )

        with self.assertRaises(OcrBackendUnavailableError):
            create_backend_for_selection(selection, consent=_endpoint_consent())

    def test_output_format_normalization(self):
        self.assertEqual(normalise_output_formats([".txt", "md", "txt"]), ["txt", "md"])
        with self.assertRaises(ValueError):
            normalise_output_formats(["json"])
        with self.assertRaises(ValueError):
            normalise_output_formats([])

    def test_txt_and_markdown_output_writer_is_deterministic_and_local(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            result = OcrResult(
                engine=OcrEngine.UNLIMITED_OCR_FAKE,
                pages=[OcrPageResult(page_number=1, text="safe OCR text")],
                source_path="C:/secret/source.png",
            )

            outputs = write_ocr_outputs(root, "source.png", result, ["txt", "md"])

            self.assertEqual(len(outputs), 2)
            for output in outputs:
                content = Path(output.path).read_text(encoding="utf-8")
                self.assertIn("safe OCR text", content)
                self.assertNotIn("C:/secret/source.png", content)
                self.assertTrue(str(Path(output.path)).startswith(str(root)))

    def test_run_workflow_uses_mock_local_endpoint_without_source_path_leakage(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            output_dir = root / "out"
            Image.new("RGB", (16, 12), "white").save(image_path)
            captured = {}

            def transport(url, payload, timeout):
                captured["payload"] = payload
                return {"pages": [{"page_number": 1, "text": "endpoint mock text"}]}

            result = run_advanced_ocr_workflow(
                [str(image_path)],
                str(output_dir),
                ["txt"],
                selection=local_endpoint_mock_selection(
                    endpoint_url=DEFAULT_LOCAL_ENDPOINT_URL,
                    transport=transport,
                ),
                consent=_endpoint_consent(),
            )

            self.assertFalse(result.failed)
            self.assertEqual(len(result.outputs), 1)
            self.assertIn("endpoint mock text", Path(result.outputs[0].path).read_text(encoding="utf-8"))
            self.assertNotIn(str(image_path), str(captured["payload"]))
            self.assertIn("image_base64", captured["payload"]["pages"][0])

    def test_workflow_maps_errors_to_user_safe_messages(self):
        self.assertEqual(
            user_safe_ocr_error_message(OcrConsentRequiredError("C:/secret/source.pdf")),
            "Advanced OCR consent is required before this backend can run.",
        )
        self.assertEqual(
            user_safe_ocr_error_message(
                OcrBackendUnavailableError("Local OCR endpoint response must include pages")
            ),
            "The selected OCR backend returned an invalid response.",
        )
        self.assertEqual(
            user_safe_ocr_error_message(
                OcrBackendUnavailableError("Local OCR endpoint request timed out.")
            ),
            "The selected OCR backend timed out.",
        )
        self.assertEqual(
            user_safe_ocr_error_message(
                OcrBackendUnavailableError(
                    "Local AI OCR model runtime is not installed or configured."
                )
            ),
            "The local AI OCR model runtime is not installed or configured.",
        )
        self.assertEqual(
            user_safe_ocr_error_message(
                OcrBackendUnavailableError(
                    "Local OCR worker is busy. Wait for the current local OCR job to finish."
                )
            ),
            "The local OCR worker is busy. Wait for the current OCR job to finish and try again.",
        )
        self.assertEqual(
            user_safe_ocr_error_message(
                OcrBackendUnavailableError(
                    "Local Unlimited-OCR model path was not found."
                )
            ),
            "The configured local Unlimited-OCR model path was not found.",
        )
        self.assertEqual(
            user_safe_ocr_error_message(
                OcrBackendUnavailableError(
                    "Local Unlimited-OCR worker Python executable was not found."
                )
            ),
            "The configured local Unlimited-OCR worker Python executable was not found.",
        )
        self.assertEqual(
            user_safe_ocr_error_message(
                OcrBackendUnavailableError(
                    "CUDA device requested but GPU/VRAM is unavailable."
                )
            ),
            "The local AI OCR runtime could not use the requested GPU/CUDA device.",
        )
        self.assertEqual(
            user_safe_ocr_error_message(RuntimeError("C:/secret/source.pdf")),
            "Advanced OCR workflow failed.",
        )

    def test_helper_imports_no_heavy_ai_runtime(self):
        for module_name in ("torch", "transformers", "sglang"):
            self.assertNotIn(module_name, sys.modules)


if __name__ == "__main__":
    unittest.main()
