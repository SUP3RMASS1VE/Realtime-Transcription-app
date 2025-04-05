import logging
import sys
import os

LOGS_DIR = "logs"

class ColorFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels"""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[34;20m"
    green = "\x1b[32;20m"
    reset = "\x1b[0m"
    
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    FORMATS = {
        logging.DEBUG: blue + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def setup_logging(level=None):
    """Configure logging for the entire application"""

    # Get level from environment variable or use default
    if level is None:
        level_name = os.getenv('LOG_LEVEL', 'INFO')
        level = getattr(logging, level_name.upper(), logging.INFO)
    
    # Configure stream handler (console output) with color formatter
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(ColorFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers = []
    root_logger.addHandler(stream_handler)

    # Prevent duplicate logging
    root_logger.propagate = False

    # Optionally configure file handler
    os.makedirs(LOGS_DIR, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'app.log'))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(file_handler)

    # Get comma-separated list of loggers to suppress from env
    suppress_loggers = os.getenv('SUPPRESS_LOGGERS', '').strip()
    if suppress_loggers:
        for logger_name in suppress_loggers.split(','):
            logger_name = logger_name.strip()
            if logger_name:
                logging.getLogger(logger_name).setLevel(logging.WARNING)

    logging.info(f"Logging configured with level: {logging.getLevelName(level)}")