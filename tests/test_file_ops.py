import gzip
import string
import os
import tempfile
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from src.core.processor import BatchProcessor
from src.utils import file_ops
from src.utils.file_ops import (
    FILESYSTEM_MAX_COMPONENT_BYTES,
    WINDOWS_MAX_COMPONENT_UNITS,
    create_staged_compression_output,
    create_staged_output,
    get_output_path,
    resolve_compression_output_path,
)


def _component_units(path: Path) -> int:
    return len(path.name.encode("utf-16-le")) // 2


def _component_bytes(path: Path) -> int:
    return len(path.name.encode("utf-8"))


class StableCompressionOutputPathTests(unittest.TestCase):
    def test_equivalent_relative_and_dot_segment_paths_share_a_target(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "source-dir" / "same.txt"
            source.parent.mkdir()
            source.write_text("source", encoding="utf-8")
            output_dir = root / "out"

            relative = os.path.relpath(source, Path.cwd())
            parent, filename = os.path.split(relative)
            with_dot_segments = os.path.join(
                parent, ".", "temporary", "..", filename
            )
            targets = {
                get_output_path(str(source), str(output_dir), ".txt.gz"),
                get_output_path(relative, str(output_dir), ".txt.gz"),
                get_output_path(with_dot_segments, str(output_dir), ".txt.gz"),
            }

            self.assertEqual(len(targets), 1)

    @unittest.skipUnless(os.name == "nt", "Windows paths are case-insensitive")
    def test_windows_case_variants_share_a_target(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "same.txt"
            source.write_text("source", encoding="utf-8")
            output_dir = root / "out"

            original = get_output_path(str(source), str(output_dir), ".txt.gz")
            case_variant = get_output_path(
                str(source).swapcase(), str(output_dir), ".txt.gz"
            )

            self.assertEqual(case_variant, original)

    def test_symlink_alias_shares_the_resolved_source_target(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "same.txt"
            alias = root / "alias.data"
            source.write_text("source", encoding="utf-8")
            output_dir = root / "out"
            try:
                alias.symlink_to(source)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"file symlinks are unavailable: {exc}")

            source_target = get_output_path(str(source), str(output_dir))
            alias_target = get_output_path(str(alias), str(output_dir))

            self.assertEqual(alias_target, source_target)

    def test_long_txt_source_compresses_with_stable_bounded_identity_name(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / f"{'t' * 174}.txt"
            source_text = "A long source identity stays readable and deterministic. " * 8
            source.write_text(source_text, encoding="utf-8")
            output_dir = root / "out"

            result = BatchProcessor().process_files(
                [str(source)], str(output_dir), "Medium", conflict_policy="rename"
            )

            self.assertEqual(result["success"], 1, result["errors"])
            output = Path(result["records"][0]["output"])
            self.assertTrue(output.is_file())
            self.assertLessEqual(_component_units(output), WINDOWS_MAX_COMPONENT_UNITS)
            self.assertLessEqual(_component_bytes(output), FILESYSTEM_MAX_COMPONENT_BYTES)
            self.assertTrue(output.name.startswith("t"))
            self.assertTrue(output.name.endswith(".txt.gz"))
            digest_and_extension = output.name.split("_compressed_", 1)[1]
            digest = digest_and_extension[: -len(".txt.gz")]
            self.assertTrue(digest)
            self.assertTrue(set(digest) <= set(string.hexdigits.lower()))
            with gzip.open(output, "rt", encoding="utf-8") as compressed:
                self.assertEqual(compressed.read(), source_text)
            self.assertEqual(
                get_output_path(str(source), str(output_dir), ".txt.gz"),
                str(output_dir / output.name),
            )

    def test_long_pdf_and_tiff_sources_keep_extensions_within_component_budget(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "out"
            for extension, stem_length in ((".pdf", 176), (".tiff", 175)):
                with self.subTest(extension=extension):
                    source = root / f"{'p' * stem_length}{extension}"
                    source.write_bytes(b"fixture")
                    output = Path(get_output_path(str(source), str(output_dir)))

                    self.assertLessEqual(
                        _component_units(output), WINDOWS_MAX_COMPONENT_UNITS
                    )
                    self.assertLessEqual(
                        _component_bytes(output), FILESYSTEM_MAX_COMPONENT_BYTES
                    )
                    self.assertTrue(output.name.endswith(extension))
                    self.assertTrue(output.name.startswith("p"))

    def test_cjk_stem_truncation_obeys_utf8_budget_on_filesystem(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / f"{'漢' * 80}.pdf"
            source.write_bytes(b"fixture")

            output = Path(get_output_path(str(source), str(root / "out")))

            self.assertTrue(source.is_file())
            self.assertLessEqual(_component_bytes(output), FILESYSTEM_MAX_COMPONENT_BYTES)
            self.assertLessEqual(_component_units(output), WINDOWS_MAX_COMPONENT_UNITS)
            self.assertTrue(output.name.startswith("漢"))
            readable_prefix = output.name.split("_compressed_", 1)[0]
            self.assertLess(len(readable_prefix), len(source.stem))

    def test_rename_suffixes_fit_at_component_limit_and_compound_extension(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / f"{'n' * 220}.txt"
            source.write_text("source", encoding="utf-8")
            output_dir = root / "out"

            original = Path(
                resolve_compression_output_path(
                    str(source), str(output_dir), ".txt.gz", "rename"
                )
            )
            self.assertEqual(_component_units(original), WINDOWS_MAX_COMPONENT_UNITS)
            self.assertLessEqual(_component_bytes(original), FILESYSTEM_MAX_COMPONENT_BYTES)
            self.assertTrue(original.name.endswith(".txt.gz"))
            original.write_bytes(b"original")

            second = Path(
                resolve_compression_output_path(
                    str(source), str(output_dir), ".txt.gz", "rename"
                )
            )
            self.assertIn("_2.txt.gz", second.name)
            self.assertLessEqual(_component_units(second), WINDOWS_MAX_COMPONENT_UNITS)
            self.assertLessEqual(_component_bytes(second), FILESYSTEM_MAX_COMPONENT_BYTES)
            second.write_bytes(b"second")

            next_candidate = second
            for expected_suffix in range(3, 11):
                next_candidate.write_bytes(f"suffix-{expected_suffix - 1}".encode())
                next_candidate = Path(
                    resolve_compression_output_path(
                        str(source), str(output_dir), ".txt.gz", "rename"
                    )
                )
                self.assertIn(f"_{expected_suffix}.txt.gz", next_candidate.name)
                self.assertLessEqual(
                    _component_units(next_candidate), WINDOWS_MAX_COMPONENT_UNITS
                )
                self.assertLessEqual(
                    _component_bytes(next_candidate), FILESYSTEM_MAX_COMPONENT_BYTES
                )
            tenth = next_candidate

            self.assertIsNone(
                resolve_compression_output_path(
                    str(source), str(output_dir), ".txt.gz", "skip"
                )
            )
            self.assertEqual(
                resolve_compression_output_path(
                    str(source), str(output_dir), ".txt.gz", "overwrite"
                ),
                str(original),
            )
            self.assertIn("_10.txt.gz", tenth.name)

    def test_emoji_stem_truncation_preserves_valid_unicode(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / f"{'😀' * 60}.pdf"
            source.write_bytes(b"fixture")
            output = Path(get_output_path(str(source), str(root / "out")))

            self.assertLessEqual(_component_units(output), WINDOWS_MAX_COMPONENT_UNITS)
            self.assertLessEqual(_component_bytes(output), FILESYSTEM_MAX_COMPONENT_BYTES)
            output.name.encode("utf-8")
            self.assertTrue(output.name.startswith("😀"))


class AtomicOutputPublicationTests(unittest.TestCase):
    def test_no_clobber_primitive_publishes_and_preserves_existing_target(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            destination = root / "destination.pdf"
            staged = root / "staged.pdf"
            staged.write_bytes(b"our output")

            file_ops._publish_without_replacing(staged, destination)

            self.assertEqual(destination.read_bytes(), b"our output")

            foreign_staged = root / "foreign-stage.pdf"
            foreign_staged.write_bytes(b"other output")
            with self.assertRaises(FileExistsError):
                file_ops._publish_without_replacing(foreign_staged, destination)

            self.assertEqual(destination.read_bytes(), b"our output")
            self.assertEqual(foreign_staged.read_bytes(), b"other output")

    def test_rename_preserves_foreign_files_created_after_lookup(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            transaction = create_staged_output(str(requested), "rename")
            self.assertIsNotNone(transaction)
            transaction.staging_path.write_bytes(b"our output")

            requested.write_bytes(b"foreign base")
            requested.with_name("output_2.pdf").write_bytes(b"foreign _2")

            committed = transaction.commit()
            try:
                self.assertEqual(committed, str(requested.with_name("output_3.pdf")))
                self.assertEqual(requested.read_bytes(), b"foreign base")
                self.assertEqual(
                    requested.with_name("output_2.pdf").read_bytes(), b"foreign _2"
                )
                self.assertEqual(
                    requested.with_name("output_3.pdf").read_bytes(), b"our output"
                )
            finally:
                transaction.cleanup()

    def test_skip_does_not_overwrite_a_file_created_after_lookup(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            transaction = create_staged_output(str(requested), "skip")
            self.assertIsNotNone(transaction)
            transaction.staging_path.write_bytes(b"our output")
            requested.write_bytes(b"foreign output")

            try:
                self.assertIsNone(transaction.commit())
                self.assertEqual(requested.read_bytes(), b"foreign output")
            finally:
                transaction.cleanup()

    def test_unexpected_publish_failure_is_terminal_and_cleanup_is_scoped(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            requested.write_bytes(b"foreign output")
            transaction = create_staged_output(str(requested), "rename")
            self.assertIsNotNone(transaction)
            staged_path = transaction.staging_path
            staged_path.write_bytes(b"our output")
            next_candidate = requested.with_name("output_2.pdf")

            with mock.patch(
                "src.utils.file_ops._publish_without_replacing",
                side_effect=PermissionError("injected publish failure"),
            ):
                with self.assertRaisesRegex(PermissionError, "injected publish failure"):
                    transaction.commit()

            self.assertIs(transaction._state, file_ops._StagedOutputState.FAILED)
            self.assertTrue(staged_path.is_file())
            self.assertFalse(next_candidate.exists())
            self.assertEqual(requested.read_bytes(), b"foreign output")

            with self.assertRaisesRegex(RuntimeError, "failed"):
                transaction.commit()
            self.assertFalse(next_candidate.exists())

            transaction.cleanup()
            transaction.cleanup()
            self.assertFalse(staged_path.parent.exists())
            self.assertEqual(requested.read_bytes(), b"foreign output")
            self.assertFalse(next_candidate.exists())

    def test_overwrite_publish_failure_is_terminal_and_preserves_target(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            requested.write_bytes(b"original output")
            transaction = create_staged_output(str(requested), "overwrite")
            self.assertIsNotNone(transaction)
            transaction.staging_path.write_bytes(b"replacement output")

            with mock.patch(
                "src.utils.file_ops.os.replace",
                side_effect=PermissionError("injected replace failure"),
            ):
                with self.assertRaisesRegex(PermissionError, "injected replace failure"):
                    transaction.commit()

            self.assertIs(transaction._state, file_ops._StagedOutputState.FAILED)
            self.assertEqual(requested.read_bytes(), b"original output")
            with self.assertRaisesRegex(RuntimeError, "failed"):
                transaction.commit()
            transaction.cleanup()
            self.assertEqual(requested.read_bytes(), b"original output")

    def test_successful_and_skipped_transactions_reject_second_commit(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            requested = root / "success.pdf"
            successful = create_staged_output(str(requested), "rename")
            self.assertIsNotNone(successful)
            successful.staging_path.write_bytes(b"complete output")
            self.assertEqual(successful.commit(), str(requested))
            self.assertIs(successful._state, file_ops._StagedOutputState.COMMITTED)
            with self.assertRaisesRegex(RuntimeError, "committed"):
                successful.commit()
            with self.assertRaisesRegex(RuntimeError, "committed"):
                _ = successful.staging_path
            successful.cleanup()
            self.assertEqual(requested.read_bytes(), b"complete output")

            skipped_path = root / "skip.pdf"
            skipped = create_staged_output(str(skipped_path), "skip")
            self.assertIsNotNone(skipped)
            skipped.staging_path.write_bytes(b"our output")
            skipped_path.write_bytes(b"foreign output")
            self.assertIsNone(skipped.commit())
            self.assertIs(skipped._state, file_ops._StagedOutputState.SKIPPED)
            with self.assertRaisesRegex(RuntimeError, "skipped"):
                skipped.commit()
            skipped.cleanup()
            self.assertEqual(skipped_path.read_bytes(), b"foreign output")

    def test_cleanup_closes_an_open_transaction(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            transaction = create_staged_output(str(requested), "rename")
            self.assertIsNotNone(transaction)
            staged_path = transaction.staging_path
            staged_path.write_bytes(b"discarded output")

            transaction.cleanup()

            self.assertIs(transaction._state, file_ops._StagedOutputState.CLEANED)
            self.assertFalse(staged_path.exists())
            with self.assertRaisesRegex(RuntimeError, "cleaned"):
                transaction.commit()
            with self.assertRaisesRegex(RuntimeError, "cleaned"):
                _ = transaction.staging_path

    def test_concurrent_rename_producers_publish_distinct_outputs(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            transactions = [
                create_staged_output(str(requested), "rename") for _ in range(2)
            ]
            self.assertTrue(all(transaction is not None for transaction in transactions))
            for index, transaction in enumerate(transactions, start=1):
                transaction.staging_path.write_bytes(f"producer-{index}".encode())

            barrier = threading.Barrier(2)

            def commit(transaction):
                barrier.wait(timeout=5)
                return transaction.commit()

            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    outputs = list(executor.map(commit, transactions))

                self.assertEqual(len(set(outputs)), 2)
                self.assertEqual(
                    {Path(output).name for output in outputs},
                    {"output.pdf", "output_2.pdf"},
                )
                self.assertEqual(
                    {Path(output).read_bytes() for output in outputs},
                    {b"producer-1", b"producer-2"},
                )
            finally:
                for transaction in transactions:
                    transaction.cleanup()

    def test_overwrite_replaces_existing_target_without_delete_first(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            requested.write_bytes(b"old output")
            transaction = create_staged_output(str(requested), "overwrite")
            self.assertIsNotNone(transaction)
            transaction.staging_path.write_bytes(b"new output")
            original_replace = os.replace
            target_existed_at_replace = []

            def observe_replace(source, target):
                target_existed_at_replace.append(Path(target).is_file())
                return original_replace(source, target)

            try:
                with mock.patch("src.utils.file_ops.os.replace", side_effect=observe_replace):
                    self.assertEqual(transaction.commit(), str(requested))
                self.assertEqual(target_existed_at_replace, [True])
                self.assertEqual(requested.read_bytes(), b"new output")
            finally:
                transaction.cleanup()

    def test_overwrite_does_not_interfere_with_a_concurrent_rename_transaction(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            requested.write_bytes(b"old output")
            rename_transaction = create_staged_output(str(requested), "rename")
            overwrite_transaction = create_staged_output(str(requested), "overwrite")
            self.assertIsNotNone(rename_transaction)
            self.assertIsNotNone(overwrite_transaction)
            rename_transaction.staging_path.write_bytes(b"renamed output")
            overwrite_transaction.staging_path.write_bytes(b"replacement output")

            try:
                self.assertEqual(overwrite_transaction.commit(), str(requested))
                self.assertEqual(
                    rename_transaction.commit(),
                    str(requested.with_name("output_2.pdf")),
                )
                self.assertEqual(requested.read_bytes(), b"replacement output")
                self.assertEqual(
                    requested.with_name("output_2.pdf").read_bytes(), b"renamed output"
                )
            finally:
                rename_transaction.cleanup()
                overwrite_transaction.cleanup()

    def test_generic_rename_suffixes_remain_bounded_through_ten(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / f"{'n' * 251}.pdf"
            outputs = []
            for index in range(1, 11):
                transaction = create_staged_output(str(requested), "rename")
                self.assertIsNotNone(transaction)
                transaction.staging_path.write_bytes(str(index).encode())
                try:
                    outputs.append(Path(transaction.commit()))
                finally:
                    transaction.cleanup()

            self.assertIn("_10.pdf", outputs[-1].name)
            self.assertTrue(
                all(_component_units(output) <= WINDOWS_MAX_COMPONENT_UNITS for output in outputs)
            )
            self.assertTrue(
                all(_component_bytes(output) <= FILESYSTEM_MAX_COMPONENT_BYTES for output in outputs)
            )

    def test_compression_transaction_keeps_compound_extension_and_bounded_suffixes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / f"{'n' * 220}.txt"
            source.write_text("source", encoding="utf-8")
            output_dir = root / "out"
            outputs = []
            for index in range(1, 11):
                transaction = create_staged_compression_output(
                    str(source), str(output_dir), ".txt.gz", "rename"
                )
                self.assertIsNotNone(transaction)
                transaction.staging_path.write_bytes(str(index).encode())
                try:
                    outputs.append(Path(transaction.commit()))
                finally:
                    transaction.cleanup()

            self.assertIn("_10.txt.gz", outputs[-1].name)
            self.assertTrue(
                all(output.name.endswith(".txt.gz") for output in outputs)
            )
            self.assertTrue(
                all(_component_units(output) <= WINDOWS_MAX_COMPONENT_UNITS for output in outputs)
            )
            self.assertTrue(
                all(_component_bytes(output) <= FILESYSTEM_MAX_COMPONENT_BYTES for output in outputs)
            )

    def test_cleanup_only_removes_its_own_staging_directory(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            first = create_staged_output(str(requested), "rename")
            second = create_staged_output(str(requested), "rename")
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            first_stage = first.staging_path
            second_stage = second.staging_path
            first_stage.write_bytes(b"first")
            second_stage.write_bytes(b"second")

            first.cleanup()

            self.assertFalse(first_stage.parent.exists())
            self.assertTrue(second_stage.is_file())
            self.assertEqual(second.commit(), str(requested))
            second.cleanup()
            self.assertEqual(requested.read_bytes(), b"second")

    def test_abandoned_staging_directory_does_not_reserve_a_logical_target(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            abandoned = create_staged_output(str(requested), "rename")
            self.assertIsNotNone(abandoned)
            abandoned.staging_path.write_bytes(b"crash artifact")
            abandoned_staging_dir = abandoned.staging_directory

            active = create_staged_output(str(requested), "rename")
            self.assertIsNotNone(active)
            active.staging_path.write_bytes(b"active output")
            try:
                self.assertEqual(active.initial_path, requested)
                self.assertEqual(active.commit(), str(requested))
                self.assertEqual(requested.read_bytes(), b"active output")
                self.assertTrue(abandoned_staging_dir.is_dir())
            finally:
                active.cleanup()
                abandoned.cleanup()

    def test_existing_skip_target_returns_no_transaction(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            requested.write_bytes(b"existing")

            self.assertIsNone(create_staged_output(str(requested), "skip"))
            self.assertEqual(requested.read_bytes(), b"existing")

    def test_compressor_preserves_destinations_claimed_after_lookup(self):
        from src.utils import file_ops

        for policy in ("skip", "rename"):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory(
                dir=Path.cwd()
            ) as temp_dir:
                root = Path(temp_dir)
                source = root / "source.txt"
                source.write_text("compress this payload " * 20, encoding="utf-8")
                output_dir = root / "out"
                logical_output = Path(
                    get_output_path(str(source), str(output_dir), ".txt.gz")
                )
                injected = {}
                original_publish = file_ops._publish_without_replacing

                def inject_foreign_file(staged_path, destination):
                    target = Path(destination)
                    if not injected:
                        target.write_bytes(b"foreign compressed output")
                        injected["path"] = target
                    return original_publish(staged_path, destination)

                with mock.patch(
                    "src.utils.file_ops._publish_without_replacing",
                    side_effect=inject_foreign_file,
                ):
                    result = BatchProcessor().process_files(
                        [str(source)],
                        str(output_dir),
                        "Medium",
                        conflict_policy=policy,
                    )

                self.assertEqual(injected["path"], logical_output)
                self.assertEqual(logical_output.read_bytes(), b"foreign compressed output")
                if policy == "skip":
                    self.assertEqual(result["success"], 0)
                    self.assertEqual(result["skipped"], 1)
                    self.assertFalse(logical_output.with_name(
                        f"{logical_output.name.removesuffix('.txt.gz')}_2.txt.gz"
                    ).exists())
                else:
                    self.assertEqual(result["success"], 1, result["errors"])
                    output = Path(result["records"][0]["output"])
                    self.assertEqual(
                        output.name,
                        f"{logical_output.name.removesuffix('.txt.gz')}_2.txt.gz",
                    )
                    with gzip.open(output, "rt", encoding="utf-8") as compressed:
                        self.assertEqual(compressed.read(), source.read_text(encoding="utf-8"))
                self.assertEqual(list(output_dir.glob(".pdf-toolkit-stage-*")), [])

    def test_deep_output_directory_is_not_rejected_for_its_total_path_length(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.pdf"
            source.write_bytes(b"fixture")
            output_dir = root
            for index in range(4):
                output_dir = output_dir / f"segment-{index}-{'d' * 55}"

            output = Path(get_output_path(str(source), str(output_dir)))

            self.assertTrue(output_dir.is_dir())
            self.assertGreater(len(str(output)), 260)
            self.assertLessEqual(_component_units(output), WINDOWS_MAX_COMPONENT_UNITS)
            self.assertLessEqual(_component_bytes(output), FILESYSTEM_MAX_COMPONENT_BYTES)


if __name__ == "__main__":
    unittest.main()
