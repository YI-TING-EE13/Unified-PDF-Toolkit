import logging
import os
import sys
from datetime import datetime

def setup_logger(name: str = "Compressor", log_dir: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Sets up a logger with console and optional file output.
    
    Args:
        name: The name of the logger.
        log_dir: Directory to save the log file. If None, only console logging is enabled.
        level: Logging level.
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent adding handlers multiple times
    if logger.hasHandlers():
        return logger

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (Optional)
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_filename = f"compression_log_{datetime.now().strftime('%Y%m%d')}.txt"
            log_path = os.path.join(log_dir, log_filename)
            
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to setup file logging: {e}")

    return logger
