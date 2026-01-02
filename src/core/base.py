from abc import ABC, abstractmethod
import os
from ..utils.logger import setup_logger

class BaseCompressor(ABC):
    """
    Abstract base class for all file compression handlers.
    
    This class defines the standard interface that all format-specific
    compressors must implement. It provides common initialization for
    logging and configuration.

    Attributes:
        level (str): The compression level ('low', 'medium', 'high').
        logger (logging.Logger): Logger instance for the specific compressor.
    """

    def __init__(self, level: str = 'medium'):
        """
        Initialize the compressor with a target compression level.

        Args:
            level (str, optional): Target compression level. 
                Must be 'low', 'medium', or 'high'. Defaults to 'medium'.
        """
        self.level = level.lower()
        self.logger = setup_logger(self.__class__.__name__)
        
    @abstractmethod
    def compress(self, input_path: str, output_path: str) -> bool:
        """
        Compresses a single file.

        Args:
            input_path (str): Absolute path to the source file.
            output_path (str): Absolute path where the compressed file should be saved.

        Returns:
            bool: True if compression was successful, False otherwise.
        """
        pass

    def validate(self, input_path: str) -> bool:
        """
        Performs basic validation on the input file.

        Args:
            input_path (str): Path to the file to validate.

        Returns:
            bool: True if file exists and is accessible, False otherwise.
        """
        if not os.path.exists(input_path):
            self.logger.error(f"File not found: {input_path}")
            return False
        return True
