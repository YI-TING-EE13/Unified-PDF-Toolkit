import gzip
import shutil
import os

from ..core.base import BaseCompressor

class TextCompressor(BaseCompressor):
    """
    Handles compression for text-based files using GZIP.
    
    Strategy:
    - Reads input file in binary chunks (streamed).
    - Writes to a new GZIP archive (.gz).
    - Uses 8KB buffer size to manage memory for large files.
    """
    
    # GZIP compression levels (1-9)
    LEVEL_MAP = {
        'low': 1,      # Fastest
        'medium': 6,   # Default balance
        'high': 9      # Best compression
    }

    def compress(self, input_path: str, output_path: str) -> bool:
        """
        Compresses input text file to .gz format.
        
        Args:
            input_path (str): Path to source text file.
            output_path (str): Target path. Should end with .gz.
        
        Returns:
            bool: Success status.
        """
        if not self.validate(input_path):
            return False

        try:
            comp_level = self.LEVEL_MAP.get(self.level, 6)
            chunk_size = 8192 # 8KB chunks for memory safety

            # Ensure output extension implies gzip for transparency
            if not output_path.endswith('.gz'):
                output_path += '.gz'

            self.logger.debug(f"Compressing {input_path} to {output_path} with gzip level {comp_level}")

            # Stream-based processing to handle large files (e.g., GB logs) without RAM spikes
            with open(input_path, 'rb') as f_in, gzip.open(output_path, 'wb', compresslevel=comp_level) as f_out:
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
            
            return True

        except Exception as e:
            self.logger.error(f"Failed to compress Text file {input_path}: {e}")
            # Clean up partial file
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            return False
