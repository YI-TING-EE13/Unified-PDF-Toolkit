import hashlib
import os
import tempfile
from pathlib import Path
from typing import Callable, Optional

# Application name used for default save directories
_APP_NAME = "PDFToolkit"
WINDOWS_MAX_COMPONENT_UNITS = 255
FILESYSTEM_MAX_COMPONENT_BYTES = 255
_COMPRESSION_MARKER = "_compressed_"


def get_default_save_dir(subfolder: str) -> str:
    """
    Returns a standard default save directory under the user's Documents folder.

    Path format: ~/Documents/PDFToolkit/Saved/{subfolder}/
    Creates the directory tree if it doesn't exist.
    Falls back to CWD-based path if permission is denied on Documents.

    Args:
        subfolder (str): Tool-specific subfolder name 
                        (e.g., "Merged", "Compressed", "Images").

    Returns:
        str: Absolute path to the ready-to-use output directory.
    """
    base = Path.home() / "Documents" / _APP_NAME / "Saved" / subfolder
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fallback: use CWD if Documents is not writable (rare on Windows)
        base = Path.cwd() / _APP_NAME / "Saved" / subfolder
        base.mkdir(parents=True, exist_ok=True)
    return str(base)


def normalize_path(path: str) -> str:
    """
    Normalizes a file path ensuring it is absolute and user vars are expanded.
    
    Args:
        path (str): The raw input path (e.g., "~/doc.pdf").

    Returns:
        str: Absolute, normalized path.
    """
    if not path:
        return ""
    try:
        # Expand ~ to user home
        expanded = os.path.expanduser(path)
        # Resolve to absolute path
        normalized = os.path.abspath(expanded)
        return normalized
    except Exception:
        return path

def _compression_output_parts(
    input_path: str,
    output_dir: Optional[str],
    ext_override: Optional[str],
) -> tuple[Path, str, str, str, str]:
    """Return destination and stable source-name parts for compression output."""
    normalized_input = normalize_path(input_path)
    input_p = Path(normalized_input)
    try:
        resolved_input = input_p.resolve()
    except (OSError, RuntimeError):
        resolved_input = input_p
    source_identity = os.path.normcase(str(resolved_input))
    source_id = hashlib.sha256(
        source_identity.encode("utf-8", errors="surrogatepass")
    ).hexdigest()

    if output_dir:
        out_dir = Path(normalize_path(output_dir))
    else:
        out_dir = Path(get_default_save_dir("Compressed"))

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        out_dir = Path.cwd() / "compressed_files"
        out_dir.mkdir(parents=True, exist_ok=True)

    extension = ext_override if ext_override else resolved_input.suffix
    # Keep compound overrides such as .txt.gz intact so rename suffixes do not
    # split or alter the extension.
    final_extension = Path(f"output{extension}").suffix
    extension_prefix = (
        extension[: -len(final_extension)] if final_extension else extension
    )
    return out_dir, resolved_input.stem, source_id, extension_prefix, final_extension


def _utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2


def _truncate_stem(stem: str, utf16_budget: int, utf8_budget: int) -> str:
    """Keep a readable prefix within Windows and byte-counted component budgets."""
    safe_stem = "".join(
        "\uFFFD" if 0xD800 <= ord(character) <= 0xDFFF else character
        for character in stem
    )
    kept: list[str] = []
    used_utf16 = 0
    used_utf8 = 0
    for character in safe_stem:
        utf16_width = _utf16_units(character)
        utf8_width = len(character.encode("utf-8"))
        if (
            used_utf16 + utf16_width > utf16_budget
            or used_utf8 + utf8_width > utf8_budget
        ):
            break
        kept.append(character)
        used_utf16 += utf16_width
        used_utf8 += utf8_width
    return "".join(kept)


def _build_compression_filename(
    stem: str,
    source_id: str,
    extension_prefix: str,
    final_extension: str,
    rename_suffix: str = "",
) -> str:
    tail = (
        f"{_COMPRESSION_MARKER}{source_id}{rename_suffix}"
        f"{extension_prefix}{final_extension}"
    )
    stem_budget = WINDOWS_MAX_COMPONENT_UNITS - _utf16_units(tail)
    byte_budget = FILESYSTEM_MAX_COMPONENT_BYTES - len(tail.encode("utf-8"))
    if stem_budget < 0 or byte_budget < 0:
        raise ValueError("The compression output extension exceeds the filename component limit.")
    bounded_stem = _truncate_stem(stem, stem_budget, byte_budget)
    filename = f"{bounded_stem}{tail}"
    if (
        _utf16_units(filename) > WINDOWS_MAX_COMPONENT_UNITS
        or len(filename.encode("utf-8")) > FILESYSTEM_MAX_COMPONENT_BYTES
    ):
        raise ValueError("The compression output filename exceeds the component limit.")
    return filename


def get_output_path(input_path: str, output_dir: Optional[str] = None, ext_override: Optional[str] = None) -> str:
    """
    Generates the output file path based on standard naming conventions.
    Format: {bounded_stem}_compressed_{source_id}{ext}. The stable SHA-256
    source ID is derived from the resolved path so same-named files remain
    distinct. The readable stem is shortened only when needed to keep the full
    filename component within the Windows UTF-16 limit. Conflict policy is
    applied later to this logical output path.

    Args:
        input_path (str): Source file path.
        output_dir (Optional[str]): Optional destination directory.
                                  If None, defaults to ~/Documents/PDFToolkit/Saved/Compressed/.
        ext_override (Optional[str]): Force a specific extension (e.g., '.txt.gz').

    Returns:
        str: Full path for the target output file.
    """
    out_dir, stem, source_id, extension_prefix, final_extension = (
        _compression_output_parts(input_path, output_dir, ext_override)
    )
    # Keep the logical output stable so skip/overwrite can find it across runs.
    filename = _build_compression_filename(
        stem, source_id, extension_prefix, final_extension
    )
    return str(out_dir / filename)


def resolve_compression_output_path(
    input_path: str,
    output_dir: Optional[str] = None,
    ext_override: Optional[str] = None,
    conflict_policy: str = "rename",
) -> Optional[str]:
    """Return a nonbinding compression destination hint.

    This compatibility helper does not acquire ownership and must not be used
    by production writers. Use ``create_staged_compression_output`` and commit
    the resulting transaction instead.
    """
    out_dir, stem, source_id, extension_prefix, final_extension = (
        _compression_output_parts(input_path, output_dir, ext_override)
    )
    policy = (conflict_policy or "rename").lower()
    original = out_dir / _build_compression_filename(
        stem, source_id, extension_prefix, final_extension
    )
    if policy == "skip" and _path_entry_exists(original):
        return None
    if policy == "overwrite":
        return str(original)

    counter = 1
    while True:
        suffix = "" if counter == 1 else f"_{counter}"
        candidate = out_dir / _build_compression_filename(
            stem, source_id, extension_prefix, final_extension, suffix
        )
        if not _path_entry_exists(candidate):
            return str(candidate)
        counter += 1


def _path_entry_exists(path: Path) -> bool:
    """Return whether a directory entry exists, including a dangling symlink."""
    return os.path.lexists(path)


def _build_output_candidate(path: Path, index: int) -> Path:
    """Build a bounded generic rename candidate, preserving the extension."""
    if index == 1:
        return path
    suffix = f"_{index}"
    extension = path.suffix
    tail = f"{suffix}{extension}"
    stem_budget = WINDOWS_MAX_COMPONENT_UNITS - _utf16_units(tail)
    byte_budget = FILESYSTEM_MAX_COMPONENT_BYTES - len(tail.encode("utf-8"))
    if stem_budget < 0 or byte_budget < 0:
        raise ValueError("The output extension exceeds the filename component limit.")
    bounded_stem = _truncate_stem(path.stem, stem_budget, byte_budget)
    filename = f"{bounded_stem}{tail}"
    if (
        _utf16_units(filename) > WINDOWS_MAX_COMPONENT_UNITS
        or len(filename.encode("utf-8")) > FILESYSTEM_MAX_COMPONENT_BYTES
    ):
        raise ValueError("The output filename exceeds the component limit.")
    return path.with_name(filename)


def _publish_without_replacing(staged_path: Path, output_path: Path) -> None:
    """Publish a complete file only if the destination directory entry is free."""
    if os.name == "nt":
        # Python documents that Windows rename raises FileExistsError when dst exists.
        os.rename(staged_path, output_path)
        return

    # POSIX link() atomically creates a new directory entry and fails with EEXIST.
    # The staging directory shares the output directory's filesystem.
    os.link(staged_path, output_path)


class StagedOutput:
    """A staged artifact committed under one output conflict policy.

    The staging directory is unique to this invocation. The final directory
    entry is acquired only when ``commit`` publishes the completed artifact.
    """

    def __init__(
        self,
        *,
        logical_path: Path,
        policy: str,
        first_index: int,
        candidate_builder: Callable[[int], Path],
        staging_directory: Path,
    ) -> None:
        self.logical_path = logical_path
        self.policy = policy
        self.first_index = first_index
        self._candidate_builder = candidate_builder
        self.initial_path = candidate_builder(first_index)
        self.staging_directory = staging_directory
        # Keep the writer-visible extension, but not the potentially long source
        # name. This also supports compound outputs such as .txt.gz via .gz.
        self.staging_path = staging_directory / f"output{logical_path.suffix}"
        self._completed = False

    def commit(self) -> Optional[str]:
        """Publish the staged file and return its actual path, or None for skip."""
        if self._completed:
            raise RuntimeError("This staged output has already been committed or skipped.")

        if self.policy == "overwrite":
            os.replace(self.staging_path, self.logical_path)
            self._completed = True
            self.cleanup()
            return str(self.logical_path)

        index = self.first_index
        while True:
            candidate = self._candidate_builder(index)
            try:
                _publish_without_replacing(self.staging_path, candidate)
            except FileExistsError:
                if self.policy == "skip":
                    self._completed = True
                    self.cleanup()
                    return None
                index += 1
                continue

            self._completed = True
            self.cleanup()
            return str(candidate)

    def cleanup(self) -> None:
        """Remove only this invocation's staged file and empty staging directory."""
        try:
            self.staging_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # A locked staging artifact can remain orphaned, but never blocks
            # the logical destination or causes cleanup to touch another file.
            return
        try:
            self.staging_directory.rmdir()
        except OSError:
            # Do not recursively remove anything another process may have placed
            # in the private directory after it was created.
            pass

    def __enter__(self) -> "StagedOutput":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.cleanup()


def _create_staged_output(
    logical_path: Path,
    policy: str,
    candidate_builder: Callable[[int], Path],
) -> Optional[StagedOutput]:
    if policy not in {"skip", "overwrite", "rename"}:
        raise ValueError("Conflict policy must be one of: rename, overwrite, skip.")

    if policy == "skip":
        if _path_entry_exists(logical_path):
            return None
        first_index = 1
    elif policy == "overwrite":
        first_index = 1
    else:
        first_index = 1
        while _path_entry_exists(candidate_builder(first_index)):
            first_index += 1

    os.makedirs(logical_path.parent, exist_ok=True)
    staging_directory = Path(
        tempfile.mkdtemp(prefix=".pdf-toolkit-stage-", dir=str(logical_path.parent))
    )
    return StagedOutput(
        logical_path=logical_path,
        policy=policy,
        first_index=first_index,
        candidate_builder=candidate_builder,
        staging_directory=staging_directory,
    )


def create_staged_output(
    path: str,
    conflict_policy: str = "rename",
) -> Optional[StagedOutput]:
    """Prepare an invocation-owned staging path for a normal output target.

    ``skip`` and ``rename`` are enforced at commit with an atomic no-clobber
    filesystem primitive; the earlier lookup only chooses the first candidate.
    ``overwrite`` atomically replaces the requested logical path where supported.
    """
    normalized = normalize_path(path)
    logical_path = Path(normalized)
    policy = (conflict_policy or "rename").casefold()
    return _create_staged_output(
        logical_path,
        policy,
        lambda index: _build_output_candidate(logical_path, index),
    )


def create_staged_compression_output(
    input_path: str,
    output_dir: Optional[str] = None,
    ext_override: Optional[str] = None,
    conflict_policy: str = "rename",
) -> Optional[StagedOutput]:
    """Prepare compression output while retaining its bounded stable naming."""
    out_dir, stem, source_id, extension_prefix, final_extension = (
        _compression_output_parts(input_path, output_dir, ext_override)
    )
    logical_path = out_dir / _build_compression_filename(
        stem, source_id, extension_prefix, final_extension
    )

    def candidate_builder(index: int) -> Path:
        suffix = "" if index == 1 else f"_{index}"
        return out_dir / _build_compression_filename(
            stem, source_id, extension_prefix, final_extension, suffix
        )

    policy = (conflict_policy or "rename").casefold()
    return _create_staged_output(logical_path, policy, candidate_builder)

def check_permissions(path: str, mode: str = 'r') -> bool:
    """
    Verifies if a file or directory has the requested permission.
    
    Args:
        path (str): Path to check.
        mode (str): 'r' for read, 'w' for write.

    Returns:
        bool: True if authorized.
    """
    if not path:
        return False
        
    path_obj = Path(path)
    
    if mode == 'r':
        return path_obj.exists() and os.access(path, os.R_OK)
    elif mode == 'w':
        # If path exists, check write permission
        if path_obj.exists():
            return os.access(path, os.W_OK)
        # If path doesn't exist, check parent write permission
        parent = path_obj.parent
        return parent.exists() and os.access(str(parent), os.W_OK)
    
    return False

def get_file_size(path: str) -> int:
    """Returns size of file in bytes. Returns 0 on error."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0

def ensure_unique_path(path: str) -> str:
    """Returns a non-existing variant by appending _2, _3, etc."""
    candidate = Path(path)
    if not _path_entry_exists(candidate):
        return str(candidate)

    counter = 2
    while True:
        next_candidate = _build_output_candidate(candidate, counter)
        if not _path_entry_exists(next_candidate):
            return str(next_candidate)
        counter += 1

def resolve_output_path(path: str, conflict_policy: str = "rename") -> Optional[str]:
    """
    Return a nonbinding output path hint for compatibility and display.

    This lookup does not acquire ownership and is not safe to pass directly to
    a writer. Production code must use ``create_staged_output`` and commit the
    staged artifact so skip/rename collisions are resolved atomically.

    Policies:
    - rename: append _2, _3, etc. when a file already exists.
    - overwrite: keep the requested path.
    - skip: return None when the requested path exists.
    """
    normalized = normalize_path(path)
    policy = (conflict_policy or "rename").lower()
    if policy == "skip" and _path_entry_exists(Path(normalized)):
        return None
    if policy == "overwrite":
        return normalized
    return ensure_unique_path(normalized)

def format_size(size_bytes: int) -> str:
    """
    Formats a byte count into a human-readable string (e.g., '10.5 MB').
    
    Args:
        size_bytes (int): Size in bytes.
    
    Returns:
        str: Formatted string.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
