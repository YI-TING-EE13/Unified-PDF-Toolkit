import builtins
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from PIL import Image

from src.ocr import (
    OcrConsentRequiredError,
    OcrDependencyMissingError,
    OcrEngine,
    OcrPageResult,
    OcrRequest,
    OcrResult,
    get_backend,
)
from src.ocr.consent import AdvancedOcrConsent, require_valid_consent
from src.ocr.exceptions import OcrBackendUnavailableError
from src.ocr.local_endpoint import (
    LOCAL_ENDPOINT_MODEL_ID,
    LOCAL_ENDPOINT_PROVIDER,
    DEFAULT_LOCAL_ENDPOINT_URL,
    LOCAL_ENDPOINT_SETTING_KEY,
    LocalEndpointOcrBackend,
    get_local_endpoint_url,
    post_json,
    set_local_endpoint_url,
    validate_local_endpoint_url,
)
from src.ocr.local_model import (
    LOCAL_MODEL_DEVICE_CUDA,
    LOCAL_MODEL_MODEL_ID,
    LOCAL_MODEL_MODE_DISABLED,
    LOCAL_MODEL_MODE_FAKE_WORKER,
    LOCAL_MODEL_MODE_IN_PROCESS_FUTURE,
    LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LOCAL_MODEL_PROVIDER,
    LOCAL_MODEL_RUNTIME_SETTING_KEY,
    LocalModelOcrBackend,
    LocalModelRuntimeConfig,
    clear_local_model_runtime_config,
    load_local_model_runtime_config,
    save_local_model_runtime_config,
)
from src.ocr import unlimited_ocr_local
from src.ocr.local_worker import (
    build_unlimited_ocr_worker_payload,
    build_local_model_worker_payload,
    default_fake_worker_script_path,
    default_unlimited_ocr_worker_script_path,
    run_local_model_worker_process,
    run_unlimited_ocr_worker_process,
    unlimited_ocr_worker_lock_path,
)
from src.ocr.tesseract import TesseractBackend
from src.ocr.unlimited_fake import (
    UNLIMITED_OCR_MODEL_ID,
    UNLIMITED_OCR_PROVIDER,
    FakeUnlimitedOcrBackend,
)
from src.tools.settings.tool import SettingsTool
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


class LocalEndpointBackendTests(unittest.TestCase):
    def _valid_consent(self) -> AdvancedOcrConsent:
        return AdvancedOcrConsent.create(
            provider=LOCAL_ENDPOINT_PROVIDER,
            model_id=LOCAL_ENDPOINT_MODEL_ID,
            acknowledged_model_download_risk=True,
            acknowledged_custom_code_risk=True,
            acknowledged_gpu_vram_use=True,
            acknowledged_temporary_page_images=True,
        )

    def test_endpoint_url_validation_allows_loopback_only(self):
        self.assertEqual(validate_local_endpoint_url("http://127.0.0.1:8765"), "http://127.0.0.1:8765")
        self.assertEqual(validate_local_endpoint_url("http://[::1]:8765"), "http://[::1]:8765")
        with mock.patch(
            "src.ocr.local_endpoint.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("127.0.0.1", 8765))],
        ):
            self.assertEqual(validate_local_endpoint_url("http://localhost:8765"), "http://localhost:8765")

    def test_endpoint_url_validation_rejects_non_local_or_malformed_urls(self):
        rejected = [
            "",
            "   ",
            "https://127.0.0.1:8765",
            "http://127.0.0.1:0",
            "http://127.0.0.1",
            "http://0.0.0.0:8765",
            "http://192.168.1.2:8765",
            "http://10.0.0.2:8765",
            "http://172.16.0.2:8765",
            "http://8.8.8.8:8765",
            "http://example.com:8765",
            "C:/tmp/file.png",
            "not a url",
            "http://127.0.0.1:bad",
            "http://user:pass@127.0.0.1:8765",
            "http://127.0.0.1:8765/ocr",
            "http://127.0.0.1:8765/path?x=1",
        ]

        for url in rejected:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_local_endpoint_url(url)

    def test_endpoint_url_validation_rejects_localhost_resolving_to_non_loopback(self):
        with mock.patch(
            "src.ocr.local_endpoint.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("192.168.1.2", 8765))],
        ):
            with self.assertRaises(ValueError):
                validate_local_endpoint_url("http://localhost:8765")

    def test_endpoint_requires_valid_consent(self):
        backend = LocalEndpointOcrBackend()
        request = OcrRequest(
            engine=OcrEngine.LOCAL_ENDPOINT,
            images=[Image.new("RGB", (10, 10), "white")],
        )

        with self.assertRaises(OcrConsentRequiredError):
            backend.recognize(request)

    def test_endpoint_success_with_mocked_transport_does_not_send_source_path(self):
        captured = {}

        def fake_transport(url, payload, timeout):
            captured["url"] = url
            captured["payload"] = payload
            captured["timeout"] = timeout
            return {"pages": [{"page_number": 5, "text": "endpoint text", "confidence": 0.8}]}

        backend = LocalEndpointOcrBackend(
            endpoint_url=DEFAULT_LOCAL_ENDPOINT_URL,
            consent=self._valid_consent(),
            timeout_seconds=1.5,
            transport=fake_transport,
        )
        result = backend.recognize(
            OcrRequest(
                engine=OcrEngine.LOCAL_ENDPOINT,
                images=[Image.new("RGB", (12, 8), "white")],
                source_path="C:/secret/source.pdf",
                page_numbers=[5],
                language="eng",
                prompt="parse",
            )
        )

        self.assertEqual(result.pages[0].text, "endpoint text")
        self.assertEqual(result.pages[0].confidence, 0.8)
        self.assertEqual(result.metadata["provider"], LOCAL_ENDPOINT_PROVIDER)
        self.assertEqual(captured["url"], DEFAULT_LOCAL_ENDPOINT_URL)
        self.assertEqual(captured["timeout"], 1.5)
        payload_text = json.dumps(captured["payload"])
        self.assertNotIn("C:/secret/source.pdf", payload_text)
        self.assertNotIn("source_path", captured["payload"])
        self.assertIn("image_base64", captured["payload"]["pages"][0])

    def test_endpoint_transport_errors_surface_as_backend_unavailable(self):
        def failing_transport(url, payload, timeout):
            raise OcrBackendUnavailableError("timeout")

        backend = LocalEndpointOcrBackend(
            consent=self._valid_consent(),
            transport=failing_transport,
        )
        request = OcrRequest(
            engine=OcrEngine.LOCAL_ENDPOINT,
            images=[Image.new("RGB", (10, 10), "white")],
        )

        with self.assertRaises(OcrBackendUnavailableError):
            backend.recognize(request)

    def test_endpoint_transport_timeout_and_connection_errors_are_sanitized(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_ENDPOINT,
            images=[Image.new("RGB", (10, 10), "white")],
            page_numbers=[1],
        )
        for exc, expected in (
            (TimeoutError("contains details"), "timed out"),
            (ConnectionError("C:/secret/source.pdf"), "connection failed"),
            (RuntimeError("C:/secret/source.pdf"), "request failed"),
        ):
            with self.subTest(exc=type(exc).__name__):
                backend = LocalEndpointOcrBackend(
                    consent=self._valid_consent(),
                    transport=lambda url, payload, timeout, err=exc: (_ for _ in ()).throw(err),
                )
                with self.assertRaises(OcrBackendUnavailableError) as raised:
                    backend.recognize(request)
                self.assertIn(expected, str(raised.exception))
                self.assertNotIn("C:/secret/source.pdf", str(raised.exception))

    def test_endpoint_rejects_malformed_response_shapes(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_ENDPOINT,
            images=[Image.new("RGB", (10, 10), "white")],
            page_numbers=[1],
        )
        bad_responses = [
            [],
            {},
            {"pages": {}},
            {"pages": []},
            {"pages": ["bad"]},
            {"pages": [{"page_number": 1}]},
            {"pages": [{"text": "ok"}]},
            {"pages": [{"page_number": 2, "text": "ok"}]},
            {"pages": [{"page_number": 1, "text": 123}]},
            {"pages": [{"page_number": True, "text": "ok"}]},
            {"pages": [{"page_number": 1, "text": "ok", "confidence": "bad"}]},
            {"pages": [{"page_number": 1, "text": "ok", "warnings": "bad"}]},
            {"pages": [{"page_number": 1, "text": "ok"}], "warnings": "bad"},
            {"pages": [{"page_number": 1, "text": "ok"}], "metadata": "bad"},
        ]

        for response in bad_responses:
            with self.subTest(response=response):
                backend = LocalEndpointOcrBackend(
                    consent=self._valid_consent(),
                    transport=lambda url, payload, timeout, value=response: value,
                )
                with self.assertRaises(OcrBackendUnavailableError):
                    backend.recognize(request)

    def test_endpoint_rejects_empty_page_requests(self):
        backend = LocalEndpointOcrBackend(consent=self._valid_consent())
        request = OcrRequest(engine=OcrEngine.LOCAL_ENDPOINT, images=[])

        with self.assertRaises(OcrBackendUnavailableError):
            backend.recognize(request)

    def test_post_json_sanitizes_timeout_and_connection_failures(self):
        class FakeTimeout:
            def __enter__(self):
                raise TimeoutError("C:/secret/source.pdf")

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch("src.ocr.local_endpoint.request.urlopen", return_value=FakeTimeout()):
            with self.assertRaises(OcrBackendUnavailableError) as raised:
                post_json(DEFAULT_LOCAL_ENDPOINT_URL, {"pages": []}, 0.01)
            self.assertNotIn("C:/secret/source.pdf", str(raised.exception))

    def test_importing_local_endpoint_does_not_import_heavy_ai_modules(self):
        for name in ("torch", "transformers", "sglang"):
            self.assertNotIn(name, sys.modules)

    def test_endpoint_url_setting_helpers_validate_before_saving(self):
        store = {}

        def fake_set(key, value):
            store[key] = value

        def fake_get(key, default=None):
            return store.get(key, default)

        with (
            mock.patch("src.ocr.local_endpoint.set_setting", side_effect=fake_set),
            mock.patch("src.ocr.local_endpoint.get_setting", side_effect=fake_get),
        ):
            set_local_endpoint_url("http://127.0.0.1:9999")
            self.assertEqual(store[LOCAL_ENDPOINT_SETTING_KEY], "http://127.0.0.1:9999")
            self.assertEqual(get_local_endpoint_url(), "http://127.0.0.1:9999")
            with self.assertRaises(ValueError):
                set_local_endpoint_url("http://example.com:9999")


class LocalModelBackendTests(unittest.TestCase):
    def _valid_consent(self) -> AdvancedOcrConsent:
        return AdvancedOcrConsent.create(
            provider=LOCAL_MODEL_PROVIDER,
            model_id=LOCAL_MODEL_MODEL_ID,
            acknowledged_model_download_risk=True,
            acknowledged_custom_code_risk=True,
            acknowledged_gpu_vram_use=True,
            acknowledged_temporary_page_images=True,
        )

    def test_local_model_requires_valid_consent(self):
        backend = LocalModelOcrBackend()
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
        )

        with self.assertRaises(OcrConsentRequiredError):
            backend.recognize(request)

    def test_local_model_reports_runtime_or_model_not_configured(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
        )
        cases = [
            (
                LocalModelRuntimeConfig(),
                "runtime is disabled",
            ),
            (
                LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
                ),
                "model path is not configured",
            ),
            (
                LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
                    model_path="C:/models/unlimited-ocr",
                ),
                "worker Python executable is not configured",
            ),
            (
                LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_IN_PROCESS_FUTURE,
                    model_path="C:/models/unlimited-ocr",
                ),
                "in-process runtime is not implemented",
            ),
        ]

        for config, expected in cases:
            with self.subTest(expected=expected):
                backend = LocalModelOcrBackend(
                    consent=self._valid_consent(),
                    config=config,
                )
                with self.assertRaises(OcrBackendUnavailableError) as raised:
                    backend.recognize(request)
                self.assertIn(expected, str(raised.exception))

    def test_importing_local_model_does_not_import_heavy_ai_modules(self):
        for name in ("torch", "transformers", "sglang"):
            self.assertNotIn(name, sys.modules)

    def test_local_model_config_defaults_to_disabled_and_round_trips(self):
        config = LocalModelRuntimeConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.mode, LOCAL_MODEL_MODE_DISABLED)

        loaded = LocalModelRuntimeConfig.from_dict(
            {
                "enabled": True,
                "mode": LOCAL_MODEL_MODE_FAKE_WORKER,
                "model_id": LOCAL_MODEL_MODEL_ID,
                "model_path": "C:/models/unlimited-ocr",
                "python_executable": "C:/runtime/python.exe",
                "worker_script_path": "C:/runtime/worker.py",
                "device_preference": LOCAL_MODEL_DEVICE_CUDA,
                "options": {"future": "value"},
            }
        )

        self.assertTrue(loaded.enabled)
        self.assertEqual(loaded.mode, LOCAL_MODEL_MODE_FAKE_WORKER)
        self.assertEqual(loaded.model_path, "C:/models/unlimited-ocr")
        self.assertEqual(loaded.device_preference, LOCAL_MODEL_DEVICE_CUDA)
        self.assertEqual(loaded.to_dict()["options"], {"future": "value"})

    def test_local_model_config_does_not_store_forbidden_document_content(self):
        config = LocalModelRuntimeConfig.from_dict(
            {
                "enabled": True,
                "mode": LOCAL_MODEL_MODE_WORKER_PROCESS,
                "model_path": "C:/models/unlimited-ocr",
                "ocr_text": "secret OCR text",
                "source_path": "C:/secret/source.pdf",
                "image_base64": "abc123",
                "rendered_page_path": "C:/tmp/page.png",
            }
        )

        stored = config.to_dict()
        self.assertNotIn("ocr_text", stored)
        self.assertNotIn("source_path", stored)
        self.assertNotIn("image_base64", stored)
        self.assertNotIn("rendered_page_path", stored)

    def test_local_model_config_persistence_load_save_and_clear(self):
        store = {}

        def fake_set(key, value):
            store[key] = value

        def fake_get(key, default=None):
            return store.get(key, default)

        def fake_load():
            return dict(store)

        def fake_save(value):
            store.clear()
            store.update(value)

        config = LocalModelRuntimeConfig(
            enabled=True,
            mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
            model_path="C:/models/unlimited-ocr",
            python_executable="C:/runtime/python.exe",
            worker_script_path="C:/runtime/worker.py",
        )
        with (
            mock.patch("src.ocr.local_model.set_setting", side_effect=fake_set),
            mock.patch("src.ocr.local_model.get_setting", side_effect=fake_get),
            mock.patch("src.ocr.local_model.load_settings", side_effect=fake_load),
            mock.patch("src.ocr.local_model.save_settings", side_effect=fake_save),
        ):
            save_local_model_runtime_config(config)
            loaded = load_local_model_runtime_config()
            self.assertTrue(loaded.enabled)
            self.assertEqual(loaded.mode, config.mode)
            self.assertEqual(loaded.model_path, config.model_path)
            self.assertEqual(loaded.python_executable, config.python_executable)
            self.assertEqual(loaded.worker_script_path, config.worker_script_path)
            clear_local_model_runtime_config()
            self.assertNotIn(LOCAL_MODEL_RUNTIME_SETTING_KEY, store)

    def test_fake_worker_success_returns_deterministic_local_model_result(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
            source_path="C:/private/source.pdf",
            page_numbers=[3],
        )
        result = run_local_model_worker_process(
            request,
            model_id=LOCAL_MODEL_MODEL_ID,
            runtime_mode=LOCAL_MODEL_MODE_FAKE_WORKER,
            python_executable=sys.executable,
            worker_script_path=default_fake_worker_script_path(),
        )

        self.assertEqual(result.engine, OcrEngine.LOCAL_MODEL)
        self.assertEqual(result.pages[0].page_number, 3)
        self.assertEqual(
            result.pages[0].text,
            "Fake local model OCR text for page 3.",
        )
        self.assertFalse(result.metadata["real_inference"])

    def test_fake_worker_payload_excludes_sensitive_fields(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
            source_path="C:/private/source.pdf",
            page_numbers=[1],
            options={
                "source_path": "C:/private/source.pdf",
                "image_base64": "abc123",
                "document_content": "secret",
                "safe_flag": "yes",
            },
        )
        payload = build_local_model_worker_payload(
            request,
            model_id=LOCAL_MODEL_MODEL_ID,
            runtime_mode=LOCAL_MODEL_MODE_FAKE_WORKER,
            options=request.options,
        )
        serialized = json.dumps(payload)

        self.assertNotIn("C:/private/source.pdf", serialized)
        self.assertNotIn("abc123", serialized)
        self.assertNotIn("secret", serialized)
        self.assertEqual(payload["options"], {"safe_flag": "yes"})

    def test_fake_worker_timeout_malformed_nonzero_and_cancel_are_sanitized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sleeper = tmp / "sleep_worker.py"
            sleeper.write_text(
                "import time\n"
                "time.sleep(5)\n"
                "print('{\"pages\": []}')\n",
                encoding="utf-8",
            )
            malformed = tmp / "malformed_worker.py"
            malformed.write_text("print('not json')\n", encoding="utf-8")
            failing = tmp / "failing_worker.py"
            failing.write_text(
                "import sys\n"
                "print('secret source path C:/private/source.pdf', file=sys.stderr)\n"
                "raise SystemExit(7)\n",
                encoding="utf-8",
            )

            request = OcrRequest(
                engine=OcrEngine.LOCAL_MODEL,
                images=[Image.new("RGB", (10, 10), "white")],
                source_path="C:/private/source.pdf",
                page_numbers=[1],
            )
            common = {
                "request_data": request,
                "model_id": LOCAL_MODEL_MODEL_ID,
                "runtime_mode": LOCAL_MODEL_MODE_FAKE_WORKER,
                "python_executable": sys.executable,
            }

            with self.assertRaises(OcrBackendUnavailableError) as timeout_error:
                run_local_model_worker_process(
                    **common,
                    worker_script_path=str(sleeper),
                    timeout_seconds=0.05,
                )
            self.assertIn("timed out", str(timeout_error.exception))
            self.assertNotIn("C:/private/source.pdf", str(timeout_error.exception))

            with self.assertRaises(OcrBackendUnavailableError) as malformed_error:
                run_local_model_worker_process(
                    **common,
                    worker_script_path=str(malformed),
                )
            self.assertIn("invalid JSON", str(malformed_error.exception))

            with self.assertRaises(OcrBackendUnavailableError) as failing_error:
                run_local_model_worker_process(
                    **common,
                    worker_script_path=str(failing),
                )
            self.assertIn("process failed", str(failing_error.exception))
            self.assertNotIn("C:/private/source.pdf", str(failing_error.exception))

            calls = {"count": 0}

            def cancel_after_launch():
                calls["count"] += 1
                return calls["count"] > 1

            with self.assertRaises(OcrBackendUnavailableError) as cancelled_error:
                run_local_model_worker_process(
                    **common,
                    worker_script_path=str(sleeper),
                    timeout_seconds=5,
                    cancellation_check=cancel_after_launch,
                )
            self.assertIn("cancelled", str(cancelled_error.exception))

    def test_unlimited_worker_payload_uses_temp_images_and_redacts_source_path(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
            source_path="C:/private/source.pdf",
            page_numbers=[9],
            options={
                "document_content": "secret",
                "safe_timeout": "5",
            },
        )
        payload = build_unlimited_ocr_worker_payload(
            request,
            model_id=LOCAL_MODEL_MODEL_ID,
            model_path="C:/models/unlimited-ocr",
            runtime_mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
            device_preference=LOCAL_MODEL_DEVICE_CUDA,
            page_image_paths=[Path("C:/temp/page_0001.png")],
            options=request.options,
        )
        serialized = json.dumps(payload)

        self.assertNotIn("C:/private/source.pdf", serialized)
        self.assertNotIn("secret", serialized)
        self.assertEqual(payload["pages"][0]["page_number"], 9)
        self.assertEqual(payload["pages"][0]["image_path"], "C:\\temp\\page_0001.png")
        self.assertEqual(payload["options"], {"safe_timeout": "5"})

    def test_unlimited_worker_process_success_timeout_and_failures_are_sanitized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            success = tmp / "success_worker.py"
            success.write_text(
                "import json, sys\n"
                "request=json.load(sys.stdin)\n"
                "pages=[{'page_number': p['page_number'], 'text': 'worker page', 'confidence': None, 'warnings': []} for p in request['pages']]\n"
                "print(json.dumps({'pages': pages, 'metadata': {'runtime': 'worker_process', 'real_inference': True}}))\n",
                encoding="utf-8",
            )
            sleeper = tmp / "sleep_worker.py"
            sleeper.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
            malformed = tmp / "malformed_worker.py"
            malformed.write_text("print('not json')\n", encoding="utf-8")
            failing = tmp / "failing_worker.py"
            failing.write_text(
                "import sys\n"
                "print('secret source path C:/private/source.pdf', file=sys.stderr)\n"
                "raise SystemExit(7)\n",
                encoding="utf-8",
            )

            request = OcrRequest(
                engine=OcrEngine.LOCAL_MODEL,
                images=[Image.new("RGB", (10, 10), "white")],
                source_path="C:/private/source.pdf",
                page_numbers=[2],
            )
            common = {
                "request_data": request,
                "model_id": LOCAL_MODEL_MODEL_ID,
                "model_path": "C:/models/unlimited-ocr",
                "runtime_mode": LOCAL_MODEL_MODE_WORKER_PROCESS,
                "device_preference": LOCAL_MODEL_DEVICE_CUDA,
                "python_executable": sys.executable,
            }

            result = run_unlimited_ocr_worker_process(
                **common,
                worker_script_path=str(success),
            )
            self.assertEqual(result.pages[0].page_number, 2)
            self.assertEqual(result.pages[0].text, "worker page")
            self.assertTrue(result.metadata["real_inference"])

            with self.assertRaises(OcrBackendUnavailableError) as timeout_error:
                run_unlimited_ocr_worker_process(
                    **common,
                    worker_script_path=str(sleeper),
                    timeout_seconds=0.05,
                )
            self.assertIn("timed out", str(timeout_error.exception))
            self.assertNotIn("C:/private/source.pdf", str(timeout_error.exception))

            with self.assertRaises(OcrBackendUnavailableError) as malformed_error:
                run_unlimited_ocr_worker_process(
                    **common,
                    worker_script_path=str(malformed),
                )
            self.assertIn("invalid JSON", str(malformed_error.exception))

            with self.assertRaises(OcrBackendUnavailableError) as failing_error:
                run_unlimited_ocr_worker_process(
                    **common,
                    worker_script_path=str(failing),
                )
            self.assertIn("process failed", str(failing_error.exception))
            self.assertNotIn("C:/private/source.pdf", str(failing_error.exception))
            self.assertFalse(unlimited_ocr_worker_lock_path().exists())

    def test_unlimited_worker_busy_and_structured_errors_are_sanitized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            success = tmp / "success_worker.py"
            success.write_text(
                "import json, sys\n"
                "request=json.load(sys.stdin)\n"
                "pages=[{'page_number': p['page_number'], 'text': 'worker page', 'confidence': None, 'warnings': []} for p in request['pages']]\n"
                "print(json.dumps({'pages': pages, 'metadata': {'runtime': 'worker_process'}}))\n",
                encoding="utf-8",
            )
            safe_error = tmp / "safe_error_worker.py"
            safe_error.write_text(
                "import json\n"
                "print(json.dumps({'error': {'message': 'CUDA is unavailable for local OCR.', 'retryable': False}}))\n"
                "raise SystemExit(3)\n",
                encoding="utf-8",
            )
            unsafe_error = tmp / "unsafe_error_worker.py"
            unsafe_error.write_text(
                "import json\n"
                "print(json.dumps({'error': {'message': 'Failed on source path C:/private/source.pdf', 'retryable': False}}))\n"
                "raise SystemExit(3)\n",
                encoding="utf-8",
            )

            request = OcrRequest(
                engine=OcrEngine.LOCAL_MODEL,
                images=[Image.new("RGB", (10, 10), "white")],
                source_path="C:/private/source.pdf",
                page_numbers=[1],
            )
            common = {
                "request_data": request,
                "model_id": LOCAL_MODEL_MODEL_ID,
                "model_path": "C:/models/unlimited-ocr",
                "runtime_mode": LOCAL_MODEL_MODE_WORKER_PROCESS,
                "device_preference": LOCAL_MODEL_DEVICE_CUDA,
                "python_executable": sys.executable,
            }

            lock_path = unlimited_ocr_worker_lock_path()
            lock_path.write_text("busy", encoding="utf-8")
            try:
                with self.assertRaises(OcrBackendUnavailableError) as busy_error:
                    run_unlimited_ocr_worker_process(
                        **common,
                        worker_script_path=str(success),
                    )
                self.assertIn("worker is busy", str(busy_error.exception))
                self.assertNotIn("C:/private/source.pdf", str(busy_error.exception))
            finally:
                with contextlib.suppress(FileNotFoundError):
                    lock_path.unlink()

            with self.assertRaises(OcrBackendUnavailableError) as cuda_error:
                run_unlimited_ocr_worker_process(
                    **common,
                    worker_script_path=str(safe_error),
                )
            self.assertIn("CUDA is unavailable", str(cuda_error.exception))

            with self.assertRaises(OcrBackendUnavailableError) as unsafe_raised:
                run_unlimited_ocr_worker_process(
                    **common,
                    worker_script_path=str(unsafe_error),
                )
            self.assertIn("process failed", str(unsafe_raised.exception))
            self.assertNotIn("C:/private/source.pdf", str(unsafe_raised.exception))

    def test_local_model_backend_uses_fake_worker_only_when_configured(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
            page_numbers=[1],
        )
        backend = LocalModelOcrBackend(
            consent=self._valid_consent(),
            config=LocalModelRuntimeConfig(
                enabled=True,
                mode=LOCAL_MODEL_MODE_FAKE_WORKER,
                python_executable=sys.executable,
                worker_script_path=default_fake_worker_script_path(),
            ),
        )

        result = backend.recognize(request)

        self.assertEqual(result.pages[0].text, "Fake local model OCR text for page 1.")
        self.assertFalse(result.metadata["real_inference"])

    def test_local_model_backend_uses_worker_process_only_when_configured(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
            page_numbers=[1],
        )
        expected = OcrResult(
            engine=OcrEngine.LOCAL_MODEL,
            pages=[OcrPageResult(page_number=1, text="worker OCR")],
            metadata={"runtime": "worker_process", "real_inference": True},
        )
        with tempfile.TemporaryDirectory() as model_dir, mock.patch(
            "src.ocr.local_model.run_unlimited_ocr_worker_process",
            return_value=expected,
        ) as runner:
            backend = LocalModelOcrBackend(
                consent=self._valid_consent(),
                config=LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
                    model_path=model_dir,
                    python_executable=sys.executable,
                    device_preference=LOCAL_MODEL_DEVICE_CUDA,
                    options={"timeout_seconds": "3"},
                ),
            )
            result = backend.recognize(request)

        self.assertIs(result, expected)
        runner.assert_called_once()
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["runtime_mode"], LOCAL_MODEL_MODE_WORKER_PROCESS)
        self.assertEqual(kwargs["worker_script_path"], default_unlimited_ocr_worker_script_path())
        self.assertEqual(kwargs["timeout_seconds"], 3.0)

    def test_local_unlimited_ocr_requires_model_path_and_optional_dependencies(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
            page_numbers=[1],
        )
        missing_config = LocalModelRuntimeConfig(
            enabled=True,
            mode=LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
        )
        backend = LocalModelOcrBackend(
            consent=self._valid_consent(),
            config=missing_config,
        )
        with self.assertRaises(OcrBackendUnavailableError) as missing_path:
            backend.recognize(request)
        self.assertIn("model path is not configured", str(missing_path.exception))

        with tempfile.TemporaryDirectory() as model_dir:
            backend = LocalModelOcrBackend(
                consent=self._valid_consent(),
                config=LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
                    model_path=model_dir,
                ),
            )
            with (
                mock.patch(
                    "src.ocr.unlimited_ocr_local.importlib.util.find_spec",
                    return_value=None,
                ),
                self.assertRaises(OcrDependencyMissingError) as missing_dependency,
            ):
                backend.recognize(request)
        self.assertIn("torch", str(missing_dependency.exception))

    def test_local_model_backend_uses_local_unlimited_runner_only_when_configured(self):
        request = OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[Image.new("RGB", (10, 10), "white")],
            page_numbers=[1],
        )
        expected = OcrResult(
            engine=OcrEngine.LOCAL_MODEL,
            pages=[OcrPageResult(page_number=1, text="mock real OCR")],
            metadata={"runtime": "local_unlimited_ocr", "real_inference": True},
        )
        with tempfile.TemporaryDirectory() as model_dir, mock.patch(
            "src.ocr.local_model.run_unlimited_ocr_local",
            return_value=expected,
        ) as runner:
            backend = LocalModelOcrBackend(
                consent=self._valid_consent(),
                config=LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
                    model_path=model_dir,
                    device_preference=LOCAL_MODEL_DEVICE_CUDA,
                ),
            )
            result = backend.recognize(request)

        self.assertIs(result, expected)
        runner.assert_called_once()

    def test_unlimited_ocr_local_runner_lazily_uses_transformers_with_mock_model(self):
        class FakeCuda:
            @staticmethod
            def is_available():
                return False

        class FakeTorch:
            bfloat16 = object()
            cuda = FakeCuda()

        class FakeTokenizerFactory:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return object()

        class FakeModel:
            def eval(self):
                return self

            def to(self, device):
                self.device = device
                return self

            def infer(self, *args, **kwargs):
                self.kwargs = kwargs
                print("mock OCR text must not leak")
                return "mock Unlimited-OCR text"

        class FakeModelFactory:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return FakeModel()

        class FakeTransformers:
            AutoTokenizer = FakeTokenizerFactory
            AutoModel = FakeModelFactory

        def fake_import(name):
            if name == "torch":
                return FakeTorch
            if name == "transformers":
                return FakeTransformers
            raise ImportError(name)

        with (
            tempfile.TemporaryDirectory() as model_dir,
            mock.patch(
                "src.ocr.unlimited_ocr_local.importlib.util.find_spec",
                return_value=object(),
            ),
            mock.patch(
                "src.ocr.unlimited_ocr_local.importlib.import_module",
                side_effect=fake_import,
            ),
        ):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = unlimited_ocr_local.run_unlimited_ocr_local(
                    OcrRequest(
                        engine=OcrEngine.LOCAL_MODEL,
                        images=[Image.new("RGB", (10, 10), "white")],
                        page_numbers=[7],
                    ),
                    config=LocalModelRuntimeConfig(
                        enabled=True,
                        mode=LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
                        model_path=model_dir,
                        options={"local_files_only": "true"},
                    ),
                )

        self.assertEqual(result.pages[0].page_number, 7)
        self.assertEqual(result.pages[0].text, "mock Unlimited-OCR text")
        self.assertEqual(result.metadata["runtime"], "local_unlimited_ocr")
        self.assertTrue(result.metadata["real_inference"])
        self.assertNotIn("mock OCR text must not leak", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_unlimited_ocr_local_runner_splits_page_marked_multi_page_output(self):
        class FakeCuda:
            @staticmethod
            def is_available():
                return False

        class FakeTorch:
            bfloat16 = object()
            cuda = FakeCuda()

        class FakeTokenizerFactory:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return object()

        class FakeModel:
            def eval(self):
                return self

            def to(self, device):
                self.device = device
                return self

            def infer_multi(self, *args, **kwargs):
                return ("<PAGE>mock page one\n<PAGE>mock page two", 2)

        class FakeModelFactory:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return FakeModel()

        class FakeTransformers:
            AutoTokenizer = FakeTokenizerFactory
            AutoModel = FakeModelFactory

        def fake_import(name):
            if name == "torch":
                return FakeTorch
            if name == "transformers":
                return FakeTransformers
            raise ImportError(name)

        with (
            tempfile.TemporaryDirectory() as model_dir,
            mock.patch(
                "src.ocr.unlimited_ocr_local.importlib.util.find_spec",
                return_value=object(),
            ),
            mock.patch(
                "src.ocr.unlimited_ocr_local.importlib.import_module",
                side_effect=fake_import,
            ),
        ):
            result = unlimited_ocr_local.run_unlimited_ocr_local(
                OcrRequest(
                    engine=OcrEngine.LOCAL_MODEL,
                    images=[
                        Image.new("RGB", (10, 10), "white"),
                        Image.new("RGB", (10, 10), "white"),
                    ],
                    page_numbers=[3, 4],
                ),
                config=LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
                    model_path=model_dir,
                    options={"local_files_only": "true"},
                ),
            )

        self.assertEqual([page.page_number for page in result.pages], [3, 4])
        self.assertEqual([page.text for page in result.pages], ["mock page one", "mock page two"])
        self.assertNotIn(
            "Local Unlimited-OCR returned a combined multi-page result without page markers.",
            result.warnings,
        )


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

    def test_consent_persistence_load_save_and_reset(self):
        from src.ocr import consent as consent_module

        store = {}

        def fake_set(key, value):
            store[key] = value

        def fake_get(key, default=None):
            return store.get(key, default)

        def fake_load():
            return dict(store)

        def fake_save(value):
            store.clear()
            store.update(value)

        consent = self._valid_consent()
        with (
            mock.patch.object(consent_module, "set_setting", side_effect=fake_set),
            mock.patch.object(consent_module, "get_setting", side_effect=fake_get),
            mock.patch.object(consent_module, "load_settings", side_effect=fake_load),
            mock.patch.object(consent_module, "save_settings", side_effect=fake_save),
        ):
            consent_module.save_advanced_ocr_consent(consent)

            loaded = consent_module.load_advanced_ocr_consent(
                provider=UNLIMITED_OCR_PROVIDER,
                model_id=UNLIMITED_OCR_MODEL_ID,
            )
            self.assertEqual(loaded, consent)

            self.assertIsNone(
                consent_module.load_advanced_ocr_consent(
                    provider=UNLIMITED_OCR_PROVIDER,
                    model_id="other/model",
                )
            )
            self.assertIsNone(
                consent_module.load_advanced_ocr_consent(
                    provider=UNLIMITED_OCR_PROVIDER,
                    model_id=UNLIMITED_OCR_MODEL_ID,
                    consent_text_version="future-version",
                )
            )

            consent_module.clear_advanced_ocr_consent()
            self.assertNotIn(consent_module.ADVANCED_OCR_CONSENT_SETTING_KEY, store)
            self.assertIsNone(consent_module.get_saved_advanced_ocr_consent())

    def test_declined_consent_is_not_created(self):
        from src.ocr.consent import create_advanced_ocr_consent

        consent = create_advanced_ocr_consent(
            provider=UNLIMITED_OCR_PROVIDER,
            model_id=UNLIMITED_OCR_MODEL_ID,
            acknowledgements={
                "acknowledged_model_download_risk": True,
                "acknowledged_custom_code_risk": True,
                "acknowledged_gpu_vram_use": False,
                "acknowledged_temporary_page_images": True,
            },
        )

        self.assertIsNone(consent)


class FakeStatusVar:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value

    def get(self):
        return self.value


class FakeParent:
    def winfo_toplevel(self):
        return self


class AdvancedOcrDiagnosticsTests(unittest.TestCase):
    def test_optional_ai_ocr_diagnostics_do_not_require_optional_dependencies(self):
        with (
            mock.patch.object(diagnostics, "_module_available", return_value=False),
            mock.patch.object(diagnostics, "load_local_model_runtime_config", return_value=LocalModelRuntimeConfig()),
        ):
            checks = diagnostics._optional_ai_ocr_checks()

        names = [check.name for check in checks]
        self.assertIn("Advanced OCR torch", names)
        self.assertIn("Advanced OCR transformers", names)
        self.assertIn("Advanced OCR CUDA", names)
        self.assertIn("Advanced OCR local model runtime", names)
        self.assertIn("Advanced OCR model cache", names)
        self.assertIn("Advanced OCR local endpoint URL", names)
        self.assertFalse([check for check in checks if check.status == "error"])

    def test_local_model_runtime_diagnostics_report_disabled_and_missing_paths(self):
        disabled = diagnostics._local_model_runtime_checks(LocalModelRuntimeConfig())
        self.assertEqual(disabled[0].detail, "disabled")

        configured = diagnostics._local_model_runtime_checks(
            LocalModelRuntimeConfig(
                enabled=True,
                mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
                model_path="C:/missing/model",
                python_executable="C:/missing/python.exe",
                worker_script_path="C:/missing/worker.py",
            )
        )

        names = [check.name for check in configured]
        self.assertIn("Advanced OCR local model runtime", names)
        self.assertIn("Advanced OCR local model path", names)
        self.assertIn("Advanced OCR worker Python", names)
        self.assertIn("Advanced OCR worker script", names)
        self.assertTrue([check for check in configured if check.status == "warning"])

        fake_configured = diagnostics._local_model_runtime_checks(
            LocalModelRuntimeConfig(
                enabled=True,
                mode=LOCAL_MODEL_MODE_FAKE_WORKER,
            )
        )
        fake_names = [check.name for check in fake_configured]
        self.assertIn("Advanced OCR fake worker", fake_names)

        unlimited_configured = diagnostics._local_model_runtime_checks(
            LocalModelRuntimeConfig(
                enabled=True,
                mode=LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
                model_path="C:/missing/model",
                device_preference=LOCAL_MODEL_DEVICE_CUDA,
            )
        )
        unlimited_names = [check.name for check in unlimited_configured]
        self.assertIn("Advanced OCR local Unlimited-OCR", unlimited_names)
        self.assertIn("Advanced OCR local model path", unlimited_names)


class SettingsConsentUiTests(unittest.TestCase):
    def _tool(self) -> SettingsTool:
        tool = SettingsTool()
        tool.parent = FakeParent()
        tool.advanced_ocr_status_var = FakeStatusVar()
        tool.local_model_status_var = FakeStatusVar()
        tool.local_model_enabled_var = FakeStatusVar()
        tool.local_model_mode_var = FakeStatusVar()
        tool.local_model_id_var = FakeStatusVar()
        tool.local_model_path_var = FakeStatusVar()
        tool.local_model_python_var = FakeStatusVar()
        tool.local_model_worker_var = FakeStatusVar()
        tool.local_model_device_var = FakeStatusVar()
        return tool

    def test_settings_consent_cancel_does_not_save(self):
        tool = self._tool()

        with (
            mock.patch("src.tools.settings.tool.request_advanced_ocr_consent", return_value=None),
            mock.patch("src.tools.settings.tool.save_advanced_ocr_consent") as save_mock,
            mock.patch("src.tools.settings.tool.load_advanced_ocr_consent", return_value=None),
            mock.patch("src.tools.settings.tool.get_saved_advanced_ocr_consent", return_value=None),
            mock.patch("src.tools.settings.tool.messagebox.showinfo"),
        ):
            tool._review_advanced_ocr_consent()

        save_mock.assert_not_called()

    def test_settings_consent_accept_saves(self):
        tool = self._tool()
        consent = AdvancedOcrConsent.create(
            provider=UNLIMITED_OCR_PROVIDER,
            model_id=UNLIMITED_OCR_MODEL_ID,
            acknowledged_model_download_risk=True,
            acknowledged_custom_code_risk=True,
            acknowledged_gpu_vram_use=True,
            acknowledged_temporary_page_images=True,
        )

        with (
            mock.patch("src.tools.settings.tool.request_advanced_ocr_consent", return_value=consent),
            mock.patch("src.tools.settings.tool.save_advanced_ocr_consent") as save_mock,
            mock.patch("src.tools.settings.tool.load_advanced_ocr_consent", return_value=consent),
            mock.patch("src.tools.settings.tool.get_saved_advanced_ocr_consent", return_value=consent),
            mock.patch("src.tools.settings.tool.messagebox.showinfo"),
        ):
            tool._review_advanced_ocr_consent()

        save_mock.assert_called_once_with(consent)

    def test_settings_consent_reset_clears(self):
        tool = self._tool()

        with (
            mock.patch("src.tools.settings.tool.clear_advanced_ocr_consent") as clear_mock,
            mock.patch("src.tools.settings.tool.load_advanced_ocr_consent", return_value=None),
            mock.patch("src.tools.settings.tool.get_saved_advanced_ocr_consent", return_value=None),
            mock.patch("src.tools.settings.tool.messagebox.showinfo"),
        ):
            tool._reset_advanced_ocr_consent()

        clear_mock.assert_called_once_with()

    def test_settings_local_model_runtime_save_and_reset(self):
        tool = self._tool()
        tool.local_model_enabled_var.set(True)
        tool.local_model_mode_var.set(LOCAL_MODEL_MODE_FAKE_WORKER)
        tool.local_model_id_var.set(LOCAL_MODEL_MODEL_ID)
        tool.local_model_path_var.set("C:/models/unlimited-ocr")
        tool.local_model_python_var.set("C:/runtime/python.exe")
        tool.local_model_worker_var.set("C:/runtime/worker.py")
        tool.local_model_device_var.set(LOCAL_MODEL_DEVICE_CUDA)

        with (
            mock.patch("src.tools.settings.tool.save_local_model_runtime_config") as save_mock,
            mock.patch(
                "src.tools.settings.tool.load_local_model_runtime_config",
                return_value=LocalModelRuntimeConfig(
                    enabled=True,
                    mode=LOCAL_MODEL_MODE_FAKE_WORKER,
                    model_path="C:/models/unlimited-ocr",
                    python_executable="C:/runtime/python.exe",
                    worker_script_path="C:/runtime/worker.py",
                ),
            ),
            mock.patch("src.tools.settings.tool.messagebox.showinfo"),
        ):
            tool._save_local_model_runtime_settings()

        saved = save_mock.call_args.args[0]
        self.assertTrue(saved.enabled)
        self.assertEqual(saved.mode, LOCAL_MODEL_MODE_FAKE_WORKER)
        self.assertEqual(saved.model_path, "C:/models/unlimited-ocr")
        self.assertEqual(saved.device_preference, LOCAL_MODEL_DEVICE_CUDA)

        with (
            mock.patch("src.tools.settings.tool.clear_local_model_runtime_config") as clear_mock,
            mock.patch("src.tools.settings.tool.load_local_model_runtime_config", return_value=LocalModelRuntimeConfig()),
            mock.patch("src.tools.settings.tool.messagebox.showinfo"),
        ):
            tool._reset_local_model_runtime_settings()

        clear_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
