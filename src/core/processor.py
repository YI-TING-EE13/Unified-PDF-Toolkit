import os
from typing import List, Optional, Callable, Dict, Any

from ..utils.file_ops import get_output_path, check_permissions, get_file_size
from ..utils.logger import setup_logger
from .base import BaseCompressor
from ..handlers.pdf import PDFCompressor
from ..handlers.image import ImageCompressor
from ..handlers.text import TextCompressor

class BatchProcessor:
    """
    Manages the batch compression workflow for multiple files.
    
    This class handles:
    1. File type detection and handler factory logic.
    2. Path generation and permission validation.
    3. Error aggregation and result tracking.
    4. Progress callback execution.
    """
    
    def __init__(self):
        """Initialize the BatchProcessor and internal handler cache."""
        self.logger = setup_logger("BatchProcessor")
        self._handlers: Dict[str, BaseCompressor] = {}
        
    def _get_handler(self, ext: str, level: str) -> Optional[BaseCompressor]:
        """
        Factory method to retrieve or create a compressor for the specific file extension.
        
        Args:
            ext (str): File extension (e.g., '.pdf').
            level (str): Compression level.

        Returns:
            Optional[BaseCompressor]: A configured compressor instance, or None if unsupported.
        """
        ext = ext.lower()
        key = f"{ext}_{level}"
        
        # Cache handlers to avoid redundant instantiation
        if key in self._handlers:
            return self._handlers[key]
            
        handler = None
        if ext == '.pdf':
            handler = PDFCompressor(level)
        elif ext in ('.jpg', '.jpeg', '.png'):
            handler = ImageCompressor(level)
        elif ext == '.txt':
            handler = TextCompressor(level)
            
        if handler:
            self._handlers[key] = handler
            
        return handler

    def process_files(
        self, 
        files: List[str], 
        output_dir: Optional[str], 
        level: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes compression on a list of files.

        Args:
            files (List[str]): List of absolute file paths to process.
            output_dir (Optional[str]): Target directory for output. 
                                      If None, defaults to `~/compressed_files`.
            level (str): Compression level ('low', 'medium', 'high').
            progress_callback (Optional[Callable]): Callback function(current_idx, total, message).

        Returns:
            Dict[str, Any]: Application result summary containing:
                - 'success': Count of successfully processed files.
                - 'failed': Count of failures.
                - 'skipped': Count of skipped/unsupported files.
                - 'total_saved_bytes': Total bytes saved.
                - 'errors': List of error messages.
        """
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total_saved_bytes': 0,
            'errors': []
        }
        
        total = len(files)
        
        for i, input_path in enumerate(files):
            try:
                # 1. Validation phase
                if not os.path.exists(input_path):
                    # Should rarely happen if glob worked correctly
                    results['skipped'] = results.get('skipped', 0) + 1
                    continue
                    
                ext = os.path.splitext(input_path)[1]
                handler = self._get_handler(ext, level)
                
                if not handler:
                    self.logger.warning(f"Unsupported format: {input_path}")
                    results['skipped'] += 1
                    continue

                # 2. Output Path Preparation
                # Text files receive a special extension override (.gz)
                ext_override = '.txt.gz' if ext == '.txt' else None
                output_path = get_output_path(input_path, output_dir, ext_override=ext_override)

                # 3. Permission Check
                if not check_permissions(os.path.dirname(output_path), 'w'):
                     msg = f"Permission denied for output directory: {output_path}"
                     self.logger.error(msg)
                     results['failed'] += 1
                     results['errors'].append(msg)
                     continue

                # 4. Execution
                if progress_callback:
                    progress_callback(i, total, f"Processing {os.path.basename(input_path)}")
                
                original_size = get_file_size(input_path)
                success = handler.compress(input_path, output_path)
                
                if success:
                    compressed_size = get_file_size(output_path)
                    saved = original_size - compressed_size
                    # Note: Negative saved bytes (file grew) is possible for very small files
                    # due to header overhead. We accept this as valid output.
                    
                    results['success'] += 1
                    results['total_saved_bytes'] += saved
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Compression failed for {input_path}")
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Error processing {input_path}: {str(e)}")
                self.logger.error(f"Unexpected error on {input_path}: {e}")

        # Final callback update
        if progress_callback:
            progress_callback(total, total, "Completed")
            
        return results
