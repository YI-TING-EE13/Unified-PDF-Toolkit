import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src.ocr.consent import AdvancedOcrConsent
from src.ocr.document_workflow import (
    DOCUMENT_OCR_BACKEND_LOCAL_UNLIMITED_WORKER,
    DOCUMENT_OCR_BACKEND_TESSERACT,
    local_unlimited_worker_backend_config,
    run_document_ocr_workflow,
    tesseract_document_backend_config,
)
from src.ocr.exceptions import OcrBackendUnavailableError
from src.ocr.local_model import (
    LOCAL_MODEL_CANCELLATION_CHECK_OPTION,
    LOCAL_MODEL_DEVICE_CUDA,
    LOCAL_MODEL_MODE_FAKE_WORKER,
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LOCAL_MODEL_MODEL_ID,
    LOCAL_MODEL_PROVIDER,
    LocalModelRuntimeConfig,
)
from src.ocr.models import OcrEngine, OcrPageResult, OcrResult
from src.tools.document_ocr.tool import (
    EXPERIMENTAL_LOCAL_OCR_ENV,
    LOCAL_UNLIMITED_BACKEND_LABEL,
    TESSERACT_BACKEND_LABEL,
    DocumentOcrTool,
    available_document_ocr_backend_labels,
    experimental_local_ocr_enabled,
)


class _FakeVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class _FakeBackend:
    def __init__(self, engine: OcrEngine, text: str = "OCR text") -> None:
        self.engine = engine
        self.text = text
        self.requests = []

    def recognize(self, request):
        self.requests.append(request)
        return OcrResult(
            engine=self.engine,
            pages=[
                OcrPageResult(
                    page_number=request.page_numbers[0] if request.page_numbers else 1,
                    text=self.text,
                )
            ],
        )


class _CancellingBackend:
    engine = OcrEngine.LOCAL_MODEL

    def __init__(self, cancelled_state) -> None:
        self.cancelled_state = cancelled_state
        self.requests = []

    def recognize(self, request):
        self.requests.append(request)
        if callable(request.options.get(LOCAL_MODEL_CANCELLATION_CHECK_OPTION)):
            self.cancelled_state["value"] = True
        raise OcrBackendUnavailableError("Local AI OCR worker process was cancelled.")


def _valid_local_model_consent() -> AdvancedOcrConsent:
    return AdvancedOcrConsent.create(
        provider=LOCAL_MODEL_PROVIDER,
        model_id=LOCAL_MODEL_MODEL_ID,
        acknowledged_model_download_risk=True,
        acknowledged_custom_code_risk=True,
        acknowledged_gpu_vram_use=True,
        acknowledged_temporary_page_images=True,
    )


class DocumentOcrToolTests(unittest.TestCase):
    def test_document_ocr_tool_registered_by_default(self):
        from src import app

        with mock.patch.dict(os.environ, {}, clear=True):
            tool_names = [tool.name for tool in app.build_tools_list()]

        self.assertIn("Document OCR", tool_names)
        self.assertNotIn("[Dev] Document OCR Shell", tool_names)

    def test_experimental_local_ocr_backend_gate_controls_label(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(experimental_local_ocr_enabled())
            self.assertEqual(
                available_document_ocr_backend_labels(),
                [TESSERACT_BACKEND_LABEL],
            )

        with mock.patch.dict(os.environ, {EXPERIMENTAL_LOCAL_OCR_ENV: "1"}):
            self.assertTrue(experimental_local_ocr_enabled())
            self.assertEqual(
                available_document_ocr_backend_labels(),
                [TESSERACT_BACKEND_LABEL, LOCAL_UNLIMITED_BACKEND_LABEL],
            )

        managed = LocalModelRuntimeConfig(
            enabled=True,
            mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
            options={"managed_plan_id": "reviewed-plan"},
        )
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "src.tools.document_ocr.tool.load_local_model_runtime_config",
                return_value=managed,
            ),
        ):
            self.assertTrue(experimental_local_ocr_enabled())
            self.assertEqual(
                available_document_ocr_backend_labels(),
                [TESSERACT_BACKEND_LABEL, LOCAL_UNLIMITED_BACKEND_LABEL],
            )

    def test_tesseract_is_default_document_ocr_backend(self):
        tool = DocumentOcrTool()
        tool.backend_var = _FakeVar(TESSERACT_BACKEND_LABEL)
        tool.language_var = _FakeVar("eng+chi_tra")

        config = tool._backend_config()

        self.assertEqual(config.backend, DOCUMENT_OCR_BACKEND_TESSERACT)
        self.assertEqual(config.tesseract_language, "eng+chi_tra")

    def test_experimental_backend_requires_gate_and_worker_process_mode(self):
        tool = DocumentOcrTool()
        tool.backend_var = _FakeVar(LOCAL_UNLIMITED_BACKEND_LABEL)
        tool.language_var = _FakeVar("eng")

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(Exception, "not enabled"):
                tool._backend_config()

        with (
            mock.patch.dict(os.environ, {EXPERIMENTAL_LOCAL_OCR_ENV: "1"}),
            mock.patch(
                "src.tools.document_ocr.tool.load_local_model_runtime_config",
                return_value=LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_FAKE_WORKER,
                ),
            ),
        ):
            with self.assertRaisesRegex(Exception, "worker_process"):
                tool._backend_config()

    def test_document_ocr_tesseract_workflow_writes_txt_and_markdown(self):
        fake_backend = _FakeBackend(OcrEngine.TESSERACT, text="Tesseract text")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            output_dir = root / "out"
            Image.new("RGB", (18, 12), "white").save(image_path)

            with mock.patch(
                "src.ocr.document_workflow.get_backend",
                return_value=fake_backend,
            ):
                result = run_document_ocr_workflow(
                    [str(image_path)],
                    str(output_dir),
                    ["txt", "md"],
                    backend_config=tesseract_document_backend_config(language="eng"),
                )

            self.assertFalse(result.failed)
            self.assertEqual(len(result.outputs), 2)
            txt_path = next(Path(output.path) for output in result.outputs if output.format == "txt")
            md_path = next(Path(output.path) for output in result.outputs if output.format == "md")
            txt = txt_path.read_text(encoding="utf-8")
            md = md_path.read_text(encoding="utf-8")
            self.assertIn("Document OCR output", txt)
            self.assertIn("Backend: Tesseract OCR", txt)
            self.assertIn("Tesseract text", txt)
            self.assertIn("# Document OCR Output", md)
            self.assertNotIn(str(image_path), txt)
            self.assertNotIn(str(image_path), md)
            self.assertEqual(fake_backend.requests[0].source_path, str(image_path))

    def test_local_unlimited_workflow_does_not_send_source_path_to_backend(self):
        fake_backend = _FakeBackend(OcrEngine.LOCAL_MODEL, text="Local model text")
        config = LocalModelRuntimeConfig(
            enabled=True,
            mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
            model_path="C:/models/unlimited-ocr",
            python_executable="C:/runtime/python.exe",
            device_preference=LOCAL_MODEL_DEVICE_CUDA,
        )
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            output_dir = root / "out"
            Image.new("RGB", (18, 12), "white").save(image_path)

            with mock.patch(
                "src.ocr.document_workflow.LocalModelOcrBackend",
                return_value=fake_backend,
            ):
                result = run_document_ocr_workflow(
                    [str(image_path)],
                    str(output_dir),
                    ["txt"],
                    backend_config=local_unlimited_worker_backend_config(config),
                    consent=_valid_local_model_consent(),
                )

            self.assertFalse(result.failed)
            self.assertEqual(
                result.outputs[0].format,
                "txt",
            )
            self.assertEqual(
                local_unlimited_worker_backend_config(config).backend,
                DOCUMENT_OCR_BACKEND_LOCAL_UNLIMITED_WORKER,
            )
            self.assertIsNone(fake_backend.requests[0].source_path)

    def test_local_unlimited_workflow_returns_cancelled_when_worker_is_cancelled(self):
        cancelled_state = {"value": False}
        fake_backend = _CancellingBackend(cancelled_state)
        config = LocalModelRuntimeConfig(
            enabled=True,
            mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
            model_path="C:/models/unlimited-ocr",
            python_executable="C:/runtime/python.exe",
            device_preference=LOCAL_MODEL_DEVICE_CUDA,
        )
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            output_dir = root / "out"
            Image.new("RGB", (18, 12), "white").save(image_path)

            with mock.patch(
                "src.ocr.document_workflow.LocalModelOcrBackend",
                return_value=fake_backend,
            ):
                result = run_document_ocr_workflow(
                    [str(image_path)],
                    str(output_dir),
                    ["txt"],
                    backend_config=local_unlimited_worker_backend_config(config),
                    consent=_valid_local_model_consent(),
                    cancellation_check=lambda: cancelled_state["value"],
                )

            self.assertTrue(result.cancelled)
            self.assertFalse(result.failed)
            self.assertFalse(result.outputs)
            self.assertIsNone(fake_backend.requests[0].source_path)

    def test_importing_document_ocr_tool_does_not_import_heavy_ai_runtime(self):
        for module_name in ("torch", "transformers", "sglang"):
            self.assertNotIn(module_name, sys.modules)


if __name__ == "__main__":
    unittest.main()
