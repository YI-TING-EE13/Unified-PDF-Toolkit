import gzip
import string
import os
import tempfile
import unittest
from pathlib import Path

from src.core.processor import BatchProcessor
from src.utils.file_ops import (
    FILESYSTEM_MAX_COMPONENT_BYTES,
    WINDOWS_MAX_COMPONENT_UNITS,
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

            third = Path(
                resolve_compression_output_path(
                    str(source), str(output_dir), ".txt.gz", "rename"
                )
            )
            self.assertIn("_3.txt.gz", third.name)
            self.assertLessEqual(_component_units(third), WINDOWS_MAX_COMPONENT_UNITS)
            self.assertLessEqual(_component_bytes(third), FILESYSTEM_MAX_COMPONENT_BYTES)

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

    def test_emoji_stem_truncation_preserves_valid_unicode(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / f"{'😀' * 100}.pdf"
            source.write_bytes(b"fixture")
            output = Path(get_output_path(str(source), str(root / "out")))

            self.assertLessEqual(_component_units(output), WINDOWS_MAX_COMPONENT_UNITS)
            self.assertLessEqual(_component_bytes(output), FILESYSTEM_MAX_COMPONENT_BYTES)
            output.name.encode("utf-8")
            self.assertTrue(output.name.startswith("😀"))

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
