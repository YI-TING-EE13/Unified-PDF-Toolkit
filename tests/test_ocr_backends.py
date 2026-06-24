import builtins
import unittest
from unittest import mock

from PIL import Image

from src.ocr import (
    OcrConsentRequiredError,
    OcrDependencyMissingError,
    OcrEngine,
    OcrRequest,
    get_backend,
)
from src.ocr.consent import AdvancedOcrConsent, require_valid_consent
from src.ocr.tesseract import TesseractBackend
from src.ocr.unlimited_fake import (
    UNLIMITED_OCR_MODEL_ID,
    UNLIMITED_OCR_PROVIDER,
    FakeUnlimitedOcrBackend,
)
from src.utils import diagnostics


class OcrBackendTests(unittest.TestCase):
    def test_registry_exposes_default_tesseract_backend(self):
        backend = get_backend(OcrEngine.TESSERACT)

        self.assertIsInstance(backend, TesseractBackend)

    def test_tesseract_backend_calls_pytesseract_with_language(self):
        image = Image.new("RGB", (20, 10), "white")
        request = OcrRequest(
            engine=OcrEngine.TESSERACT,
            images=[image],
            source_path="sample.pdf",
            page_numbers=[3],
            language="eng+chi_tra",
        )

        with mock.patch("pytesseract.image_to_string", return_value=" OCR text ") as ocr_mock:
            result = TesseractBackend().recognize(request)

        self.assertEqual(result.pages[0].page_number, 3)
        self.assertEqual(result.pages[0].text, "OCR text")
        self.assertIs(ocr_mock.call_args.args[0], image)
        self.assertEqual(ocr_mock.call_args.kwargs["lang"], "eng+chi_tra")

    def test_tesseract_backend_missing_python_dependency_raises_ocr_error(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pytesseract":
                raise ImportError("missing")
            return real_import(name, *args, **kwargs)

        request = OcrRequest(
            engine=OcrEngine.TESSERACT,
            images=[Image.new("RGB", (10, 10), "white")],
        )
        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(OcrDependencyMissingError):
                TesseractBackend().recognize(request)

    def test_tesseract_backend_missing_executable_raises_ocr_error(self):
        import pytesseract

        request = OcrRequest(
            engine=OcrEngine.TESSERACT,
            images=[Image.new("RGB", (10, 10), "white")],
        )
        with mock.patch(
            "pytesseract.image_to_string",
            side_effect=pytesseract.pytesseract.TesseractNotFoundError(),
        ):
            with self.assertRaises(OcrDependencyMissingError):
                TesseractBackend().recognize(request)

    def test_fake_unlimited_ocr_requires_valid_consent(self):
        backend = FakeUnlimitedOcrBackend()
        request = OcrRequest(
            engine=OcrEngine.UNLIMITED_OCR_FAKE,
            images=[Image.new("RGB", (10, 10), "white")],
            page_numbers=[1],
        )

        with self.assertRaises(OcrConsentRequiredError):
            backend.recognize(request)

    def test_fake_unlimited_ocr_returns_deterministic_result(self):
        consent = AdvancedOcrConsent.create(
            provider=UNLIMITED_OCR_PROVIDER,
            model_id=UNLIMITED_OCR_MODEL_ID,
            acknowledged_model_download_risk=True,
            acknowledged_custom_code_risk=True,
            acknowledged_gpu_vram_use=True,
            acknowledged_temporary_page_images=True,
        )
        backend = FakeUnlimitedOcrBackend(consent=consent)
        request = OcrRequest(
            engine=OcrEngine.UNLIMITED_OCR_FAKE,
            images=[Image.new("RGB", (12, 8), "white")],
            source_path="sample.pdf",
            page_numbers=[2],
            prompt="parse this page",
        )

        result = backend.recognize(request)

        self.assertIn("[fake Unlimited-OCR]", result.pages[0].text)
        self.assertIn("page=2", result.pages[0].text)
        self.assertIn("size=12x8", result.pages[0].text)
        self.assertEqual(result.metadata["model_id"], UNLIMITED_OCR_MODEL_ID)


class AdvancedOcrConsentTests(unittest.TestCase):
    def _valid_consent(self) -> AdvancedOcrConsent:
        return AdvancedOcrConsent.create(
            provider=UNLIMITED_OCR_PROVIDER,
            model_id=UNLIMITED_OCR_MODEL_ID,
            acknowledged_model_download_risk=True,
            acknowledged_custom_code_risk=True,
            acknowledged_gpu_vram_use=True,
            acknowledged_temporary_page_images=True,
        )

    def test_consent_is_valid_for_matching_provider_model_and_text_version(self):
        consent = self._valid_consent()

        require_valid_consent(
            consent,
            provider=UNLIMITED_OCR_PROVIDER,
            model_id=UNLIMITED_OCR_MODEL_ID,
        )

    def test_consent_invalidates_when_provider_model_or_text_version_changes(self):
        consent = self._valid_consent()

        self.assertFalse(
            consent.is_valid_for(provider="other", model_id=UNLIMITED_OCR_MODEL_ID)
        )
        self.assertFalse(
            consent.is_valid_for(provider=UNLIMITED_OCR_PROVIDER, model_id="other/model")
        )
        self.assertFalse(
            consent.is_valid_for(
                provider=UNLIMITED_OCR_PROVIDER,
                model_id=UNLIMITED_OCR_MODEL_ID,
                consent_text_version="future-version",
            )
        )

    def test_consent_requires_all_acknowledgements(self):
        consent = AdvancedOcrConsent.create(
            provider=UNLIMITED_OCR_PROVIDER,
            model_id=UNLIMITED_OCR_MODEL_ID,
            acknowledged_model_download_risk=True,
            acknowledged_custom_code_risk=False,
            acknowledged_gpu_vram_use=True,
            acknowledged_temporary_page_images=True,
        )

        with self.assertRaises(OcrConsentRequiredError):
            require_valid_consent(
                consent,
                provider=UNLIMITED_OCR_PROVIDER,
                model_id=UNLIMITED_OCR_MODEL_ID,
            )

    def test_consent_round_trips_through_settings_style_dict(self):
        consent = self._valid_consent()

        loaded = AdvancedOcrConsent.from_dict(consent.to_dict())

        self.assertEqual(loaded, consent)
        require_valid_consent(
            loaded,
            provider=UNLIMITED_OCR_PROVIDER,
            model_id=UNLIMITED_OCR_MODEL_ID,
        )


class AdvancedOcrDiagnosticsTests(unittest.TestCase):
    def test_optional_ai_ocr_diagnostics_do_not_require_optional_dependencies(self):
        with mock.patch.object(diagnostics, "_module_available", return_value=False):
            checks = diagnostics._optional_ai_ocr_checks()

        names = [check.name for check in checks]
        self.assertIn("Advanced OCR torch", names)
        self.assertIn("Advanced OCR transformers", names)
        self.assertIn("Advanced OCR CUDA", names)
        self.assertIn("Advanced OCR model cache", names)
        self.assertFalse([check for check in checks if check.status == "error"])


if __name__ == "__main__":
    unittest.main()
