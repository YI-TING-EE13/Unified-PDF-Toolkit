from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import fitz

from src.tools.page_manager import tool as page_manager_module
from src.tools.page_manager.tool import PageManagerTool
from src.utils import file_ops


class _FakeExtractDocument:
    def __init__(self, *, insert_error=None, save_error=None, write_file=True):
        self.insert_error = insert_error
        self.save_error = save_error
        self.write_file = write_file
        self.closed = False
        self.insert_calls = []
        self.save_paths = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def close(self):
        self.closed = True

    def insert_pdf(self, source, *, from_page, to_page):
        self.insert_calls.append((from_page, to_page))
        if self.insert_error is not None:
            raise self.insert_error

    def save(self, output_path, **kwargs):
        path = Path(output_path)
        self.save_paths.append(path)
        if self.write_file:
            path.write_bytes(b"partial staged PDF")
        if self.save_error is not None:
            raise self.save_error


class PageManagerExtractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.output = self.root / "extract.pdf"
        self.source_path = self.root / "source.pdf"

        with fitz.open() as source:
            for page_number in range(1, 4):
                page = source.new_page()
                page.insert_text((72, 72), f"Page {page_number}")
            self.source_path.write_bytes(source.tobytes())
        self.source = fitz.open(self.source_path)
        self.addCleanup(self.source.close)

        self.tool = PageManagerTool()
        self.tool.doc = self.source
        self.tool.current_pdf_path = str(self.source_path)
        self.tool.total_pages = self.source.page_count
        self.tool.extract_entry = mock.Mock()
        self.tool.extract_entry.get.return_value = "3,1"
        self.tool.output_actions = mock.Mock()
        self.tool.status_lbl = mock.Mock()

    def _run_extract(
        self,
        policy,
        *,
        new_document=None,
        patch_open=False,
        extra_patches=(),
    ):
        transactions = []
        real_create = page_manager_module.create_staged_output

        def create_transaction(*args, **kwargs):
            transaction = real_create(*args, **kwargs)
            transactions.append(transaction)
            if transaction is not None:
                transaction.commit = mock.Mock(wraps=transaction.commit)
            return transaction

        with ExitStack() as stack:
            mocks = {
                "asksave": stack.enter_context(
                    mock.patch.object(
                        page_manager_module.filedialog,
                        "asksaveasfilename",
                        return_value=str(self.output),
                    )
                ),
                "get_setting": stack.enter_context(
                    mock.patch.object(
                        page_manager_module, "get_setting", return_value=str(self.root)
                    )
                ),
                "get_default_save_dir": stack.enter_context(
                    mock.patch.object(
                        page_manager_module,
                        "get_default_save_dir",
                        return_value=str(self.root),
                    )
                ),
                "set_setting": stack.enter_context(
                    mock.patch.object(page_manager_module, "set_setting")
                ),
                "get_conflict_policy": stack.enter_context(
                    mock.patch.object(
                        page_manager_module, "get_conflict_policy", return_value=policy
                    )
                ),
                "showinfo": stack.enter_context(
                    mock.patch.object(page_manager_module.messagebox, "showinfo")
                ),
                "showerror": stack.enter_context(
                    mock.patch.object(page_manager_module.messagebox, "showerror")
                ),
                "showwarning": stack.enter_context(
                    mock.patch.object(page_manager_module.messagebox, "showwarning")
                ),
                "create_transaction": stack.enter_context(
                    mock.patch.object(
                        page_manager_module,
                        "create_staged_output",
                        side_effect=create_transaction,
                    )
                ),
            }
            if patch_open:
                mocks["fitz_open"] = stack.enter_context(
                    mock.patch.object(
                        page_manager_module.fitz, "open", return_value=new_document
                    )
                )
            extra_mocks = [stack.enter_context(patch) for patch in extra_patches]

            self.tool._extract_pages()

        return mocks, transactions, extra_mocks

    def _assert_valid_extraction(self, path, expected_pages):
        with fitz.open(str(path)) as document:
            self.assertEqual(document.page_count, len(expected_pages))
            text = [page.get_text() for page in document]
        for extracted_text, page_number in zip(text, expected_pages):
            self.assertIn(f"Page {page_number}", extracted_text)

    def _assert_success_ui(self, actual_path, mocks):
        actual = str(actual_path)
        self.tool.output_actions.set_path.assert_called_once_with(actual)
        mocks["set_setting"].assert_called_once_with(
            "page_manager.output_dir", str(actual_path.parent)
        )
        self.assertIn(actual, self.tool.status_lbl.config.call_args.kwargs["text"])
        self.assertIn(actual, mocks["showinfo"].call_args.args[1])
        mocks["showerror"].assert_not_called()

    def test_success_extracts_selected_pages_and_publishes_committed_path(self):
        mocks, transactions, _ = self._run_extract("rename")

        self.assertEqual(len(transactions), 1)
        transaction = transactions[0]
        self.assertEqual(transaction.initial_path, self.output)
        self.assertEqual(transaction.commit.call_count, 1)
        self.assertEqual(transaction.commit.call_args, mock.call())
        self._assert_valid_extraction(self.output, [3, 1])
        self._assert_success_ui(self.output, mocks)
        self.tool.extract_entry.delete.assert_called_once()
        self.assertFalse(transaction.staging_directory.exists())
        self.assertEqual(list(self.root.glob(".pdf-toolkit-stage-*")), [])

    def test_initial_skip_preserves_existing_output_without_claiming_success(self):
        original = b"pre-existing output"
        self.output.write_bytes(original)
        fake_document = _FakeExtractDocument()
        mocks, transactions, _ = self._run_extract(
            "skip", new_document=fake_document, patch_open=True
        )

        self.assertEqual(transactions, [None])
        mocks["fitz_open"].assert_not_called()
        self.assertEqual(self.output.read_bytes(), original)
        mocks["showinfo"].assert_called_once()
        self.assertIn("Skipped", mocks["showinfo"].call_args.args[1])
        mocks["showerror"].assert_not_called()
        mocks["set_setting"].assert_not_called()
        self.tool.output_actions.set_path.assert_not_called()
        self.tool.extract_entry.delete.assert_not_called()
        self.assertEqual(list(self.root.glob(".pdf-toolkit-stage-*")), [])

    def test_save_failure_cleans_partial_stage_and_preserves_overwrite_target(self):
        original = b"original destination"
        self.output.write_bytes(original)
        foreign_stage = self.root / ".pdf-toolkit-stage-foreign"
        foreign_stage.mkdir()
        foreign_file = foreign_stage / "keep.bin"
        foreign_file.write_bytes(b"foreign staging data")
        fake_document = _FakeExtractDocument(
            save_error=OSError("injected save failure")
        )

        mocks, transactions, _ = self._run_extract(
            "overwrite", new_document=fake_document, patch_open=True
        )

        transaction = transactions[0]
        self.assertEqual(transaction.commit.call_count, 0)
        self.assertTrue(fake_document.closed)
        self.assertEqual(fake_document.save_paths[0].parent, transaction.staging_directory)
        self.assertFalse(fake_document.save_paths[0].parent.exists())
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(foreign_file.read_bytes(), b"foreign staging data")
        mocks["showerror"].assert_called_once()
        self.assertIn("injected save failure", mocks["showerror"].call_args.args[1])
        mocks["showinfo"].assert_not_called()
        self.tool.output_actions.set_path.assert_not_called()

    def test_page_insertion_failure_closes_document_and_does_not_commit(self):
        original = b"original destination"
        self.output.write_bytes(original)
        fake_document = _FakeExtractDocument(
            insert_error=RuntimeError("injected page insertion failure")
        )

        mocks, transactions, _ = self._run_extract(
            "overwrite", new_document=fake_document, patch_open=True
        )

        self.assertTrue(fake_document.closed)
        self.assertEqual(fake_document.save_paths, [])
        self.assertEqual(transactions[0].commit.call_count, 0)
        self.assertEqual(self.output.read_bytes(), original)
        self.assertFalse(transactions[0].staging_directory.exists())
        mocks["showerror"].assert_called_once()
        mocks["showinfo"].assert_not_called()

    def test_successful_save_without_staged_file_is_rejected_before_commit(self):
        original = b"original destination"
        self.output.write_bytes(original)
        fake_document = _FakeExtractDocument(write_file=False)

        mocks, transactions, _ = self._run_extract(
            "overwrite", new_document=fake_document, patch_open=True
        )

        self.assertTrue(fake_document.closed)
        self.assertEqual(transactions[0].commit.call_count, 0)
        self.assertEqual(self.output.read_bytes(), original)
        self.assertFalse(transactions[0].staging_directory.exists())
        mocks["showerror"].assert_called_once()
        self.assertIn("did not create", mocks["showerror"].call_args.args[1])
        mocks["showinfo"].assert_not_called()

    def test_late_skip_collision_preserves_foreign_file_and_reports_skip(self):
        foreign_bytes = b"foreign output created before commit"
        injected = []
        original_publish = file_ops._publish_without_replacing

        def create_late_collision(staged_path, destination):
            target = Path(destination)
            target.write_bytes(foreign_bytes)
            injected.append(target)
            return original_publish(staged_path, target)

        mocks, transactions, _ = self._run_extract(
            "skip",
            extra_patches=(
                mock.patch.object(
                    file_ops,
                    "_publish_without_replacing",
                    side_effect=create_late_collision,
                ),
            ),
        )

        self.assertEqual(injected, [self.output])
        self.assertEqual(self.output.read_bytes(), foreign_bytes)
        self.assertEqual(transactions[0].commit.call_count, 1)
        self.assertFalse(transactions[0].staging_directory.exists())
        mocks["showinfo"].assert_called_once()
        self.assertIn("Skipped", mocks["showinfo"].call_args.args[1])
        mocks["showerror"].assert_not_called()
        mocks["set_setting"].assert_not_called()
        self.tool.output_actions.set_path.assert_not_called()

    def test_late_rename_collisions_publish_next_path_and_update_ui(self):
        foreign_outputs = {
            self.output: b"foreign base output",
            self.output.with_name("extract_2.pdf"): b"foreign second output",
        }
        original_publish = file_ops._publish_without_replacing

        def create_late_collisions(staged_path, destination):
            target = Path(destination)
            if target in foreign_outputs and not target.exists():
                target.write_bytes(foreign_outputs[target])
            return original_publish(staged_path, target)

        mocks, transactions, _ = self._run_extract(
            "rename",
            extra_patches=(
                mock.patch.object(
                    file_ops,
                    "_publish_without_replacing",
                    side_effect=create_late_collisions,
                ),
            ),
        )

        actual_path = self.output.with_name("extract_3.pdf")
        self.assertEqual(self.output.read_bytes(), foreign_outputs[self.output])
        self.assertEqual(
            self.output.with_name("extract_2.pdf").read_bytes(),
            foreign_outputs[self.output.with_name("extract_2.pdf")],
        )
        self._assert_valid_extraction(actual_path, [3, 1])
        self._assert_success_ui(actual_path, mocks)
        self.assertEqual(transactions[0].commit.call_count, 1)
        self.assertFalse(transactions[0].staging_directory.exists())

    def test_overwrite_atomically_replaces_existing_destination(self):
        self.output.write_bytes(b"old output")
        existed_at_replace = []
        original_replace = os.replace

        def observe_replace(source, destination):
            existed_at_replace.append(Path(destination).is_file())
            return original_replace(source, destination)

        mocks, transactions, _ = self._run_extract(
            "overwrite",
            extra_patches=(
                mock.patch.object(file_ops.os, "replace", side_effect=observe_replace),
            ),
        )

        self.assertEqual(existed_at_replace, [True])
        self.assertEqual(transactions[0].commit.call_count, 1)
        self._assert_valid_extraction(self.output, [3, 1])
        self._assert_success_ui(self.output, mocks)
        self.assertFalse(transactions[0].staging_directory.exists())

    def test_unexpected_commit_failure_preserves_target_and_is_not_retried(self):
        original = b"original destination"
        self.output.write_bytes(original)

        mocks, transactions, _ = self._run_extract(
            "overwrite",
            extra_patches=(
                mock.patch.object(
                    file_ops.os,
                    "replace",
                    side_effect=PermissionError("injected commit failure"),
                ),
            ),
        )

        self.assertEqual(transactions[0].commit.call_count, 1)
        self.assertEqual(self.output.read_bytes(), original)
        self.assertFalse(transactions[0].staging_directory.exists())
        mocks["showerror"].assert_called_once()
        self.assertIn("injected commit failure", mocks["showerror"].call_args.args[1])
        mocks["showinfo"].assert_not_called()
        mocks["set_setting"].assert_not_called()
        self.tool.output_actions.set_path.assert_not_called()


if __name__ == "__main__":
    unittest.main()
