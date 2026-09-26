import os
import tempfile
import unittest
from pathlib import Path

from src.utils.file_ops import get_output_path


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


if __name__ == "__main__":
    unittest.main()
