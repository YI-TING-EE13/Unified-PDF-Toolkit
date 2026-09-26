import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from src import cli
from src.utils import file_ops


class OcrCliOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _capture_transactions(self):
        transactions = []
        create_staged_output = file_ops.create_staged_output

        def create(path, policy):
            transaction = create_staged_output(path, policy)
            if transaction is not None:
                transaction.commit = mock.Mock(wraps=transaction.commit)
                transactions.append(transaction)
            return transaction

        return transactions, create

    def test_writes_utf8_json_to_a_staged_file_and_reports_committed_path(self):
        output = self.root / "report.json"
        payload = {"status": "就緒", "message": "繁體中文 😀"}
        stdout = io.StringIO()

        with (
            mock.patch.object(
                cli, "create_staged_output", wraps=file_ops.create_staged_output
            ) as create_staged_output,
            contextlib.redirect_stdout(stdout),
        ):
            cli._write_or_print_ocr_payload(
                payload,
                argparse.Namespace(output=str(output), json=False),
                human="human summary",
            )

        self.assertEqual(create_staged_output.call_args.args, (str(output.resolve()), "overwrite"))
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), payload)
        self.assertIn("繁體中文".encode("utf-8"), output.read_bytes())
        self.assertEqual(stdout.getvalue(), f"Report written: {output.resolve()}\n")
        self.assertEqual(list(self.root.iterdir()), [output])

    def test_overwrite_keeps_the_old_target_until_atomic_replace(self):
        output = self.root / "report.json"
        original = b'{"old": true}'
        output.write_bytes(original)
        real_replace = file_ops.os.replace
        observed = []

        def record_replace(source, destination):
            observed.append(
                (
                    Path(source),
                    Path(destination),
                    Path(source).is_file(),
                    output.exists(),
                    output.read_bytes(),
                )
            )
            return real_replace(source, destination)

        with (
            mock.patch.object(file_ops.os, "replace", side_effect=record_replace),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cli._write_or_print_ocr_payload(
                {"new": True},
                argparse.Namespace(output=str(output), json=True),
                human="unused",
            )

        self.assertEqual(len(observed), 1)
        stage, destination, stage_existed, target_existed, target_bytes = observed[0]
        self.assertTrue(stage_existed)
        self.assertEqual(destination, output.resolve())
        self.assertTrue(target_existed)
        self.assertEqual(target_bytes, original)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"new": True})
        self.assertEqual(list(self.root.iterdir()), [output])

    def test_partial_staging_write_failure_preserves_target_and_cleans_stage(self):
        output = self.root / "report.json"
        original = b'{"old": "keep me"}'
        output.write_bytes(original)
        transactions, create = self._capture_transactions()
        real_write_text = Path.write_text
        stdout = io.StringIO()

        def write_partial_then_fail(path, data, **kwargs):
            real_write_text(path, "partial staged JSON", encoding="utf-8")
            raise OSError("simulated staging write failure")

        with (
            mock.patch.object(cli, "create_staged_output", side_effect=create),
            mock.patch.object(
                Path, "write_text", autospec=True, side_effect=write_partial_then_fail
            ),
            contextlib.redirect_stdout(stdout),
            self.assertRaisesRegex(OSError, "simulated staging write failure"),
        ):
            cli._write_or_print_ocr_payload(
                {"new": True},
                argparse.Namespace(output=str(output), json=False),
                human="unused",
            )

        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(len(transactions), 1)
        transactions[0].commit.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(list(self.root.iterdir()), [output])

    def test_commit_failure_preserves_target_and_does_not_report_success_or_retry(self):
        output = self.root / "report.json"
        original = b'{"old": "keep me"}'
        output.write_bytes(original)
        transactions, create = self._capture_transactions()
        stdout = io.StringIO()

        with (
            mock.patch.object(cli, "create_staged_output", side_effect=create),
            mock.patch.object(
                file_ops.os, "replace", side_effect=PermissionError("simulated commit failure")
            ),
            contextlib.redirect_stdout(stdout),
            self.assertRaisesRegex(PermissionError, "simulated commit failure"),
        ):
            cli._write_or_print_ocr_payload(
                {"new": True},
                argparse.Namespace(output=str(output), json=False),
                human="unused",
            )

        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(len(transactions), 1)
        transactions[0].commit.assert_called_once_with()
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(list(self.root.iterdir()), [output])

    def test_json_mode_writes_file_and_emits_only_stdout_json(self):
        output = self.root / "report.json"
        payload = {"status": "就緒", "value": 17}
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            cli._write_or_print_ocr_payload(
                payload,
                argparse.Namespace(output=str(output), json=True),
                human="unused",
            )

        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), payload)
        self.assertEqual(json.loads(stdout.getvalue()), payload)
        self.assertNotIn("Report written:", stdout.getvalue())

    def test_without_output_keeps_human_stdout_and_does_not_create_transaction(self):
        stdout = io.StringIO()

        with (
            mock.patch.object(cli, "create_staged_output") as create_staged_output,
            contextlib.redirect_stdout(stdout),
        ):
            cli._write_or_print_ocr_payload(
                {"status": "ready"},
                argparse.Namespace(output=None, json=False),
                human="Human OCR summary",
            )

        create_staged_output.assert_not_called()
        self.assertEqual(stdout.getvalue(), "Human OCR summary\n")

    def test_json_serialization_failure_cleans_stage_and_preserves_target(self):
        output = self.root / "report.json"
        original = b'{"old": "keep me"}'
        output.write_bytes(original)
        transactions, create = self._capture_transactions()
        stdout = io.StringIO()

        with (
            mock.patch.object(cli, "create_staged_output", side_effect=create),
            contextlib.redirect_stdout(stdout),
            self.assertRaises(TypeError),
        ):
            cli._write_or_print_ocr_payload(
                {"not_json": object()},
                argparse.Namespace(output=str(output), json=False),
                human="unused",
            )

        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(len(transactions), 1)
        transactions[0].commit.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(list(self.root.iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
