import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

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

def get_output_path(input_path: str, output_dir: Optional[str] = None, ext_override: Optional[str] = None) -> str:
    """
    Generates the output file path based on standard naming conventions.
    Format: {filename}_compressed_{YYYYMMDD}_{HHMMSS}{ext}
    
    Args:
        input_path (str): Source file path.
        output_dir (Optional[str]): Optional destination directory. 
                                  If None, uses '~/compressed_files'.
        ext_override (Optional[str]): Force a specific extension (e.g., '.txt.gz').
    
    Returns:
        str: Full path for the target output file.
    """
    input_path = normalize_path(input_path)
    input_p = Path(input_path)
    
    # Determine Output Directory
    if output_dir:
        out_dir = Path(normalize_path(output_dir))
    else:
        out_dir = Path.home() / "compressed_files"
    
    # Ensure directory exists
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fallback to current directory if permission denied
        out_dir = Path.cwd() / "compressed_files"
        out_dir.mkdir(parents=True, exist_ok=True)

    # Generate Filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = input_p.stem
    extension = ext_override if ext_override else input_p.suffix
    
    new_filename = f"{stem}_compressed_{timestamp}{extension}"
    return str(out_dir / new_filename)

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
