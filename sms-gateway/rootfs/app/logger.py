#!/usr/bin/env python3
"""
Colored Logger Module for SMS Gateway
Provides ANSI colored console output and plain-text file logging
"""

import logging
import sys
from datetime import datetime, timezone

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    DEBUG = '\033[36m'      # Cyan
    INFO = '\033[32m'       # Green
    WARNING = '\033[33m'    # Yellow
    ERROR = '\033[31m'      # Red
    CRITICAL = '\033[1;31m' # Bold Red


class ColoredFormatter(logging.Formatter):
    """Formatter that adds ANSI colors to log levels"""
    
    def __init__(self, fmt=None, datefmt=None, use_colors=True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors
        
        self.color_map = {
            logging.DEBUG: Colors.DEBUG,
            logging.INFO: Colors.INFO,
            logging.WARNING: Colors.WARNING,
            logging.ERROR: Colors.ERROR,
            logging.CRITICAL: Colors.CRITICAL,
        }
    
    def format(self, record):
        if self.use_colors and record.levelno in self.color_map:
            # Add color to the level name
            levelname_color = self.color_map[record.levelno] + record.levelname + Colors.RESET
            record_copy = logging.makeLogRecord(record.__dict__)
            record_copy.levelname = levelname_color
            return super().format(record_copy)
        return super().format(record)


class PlainFormatter(logging.Formatter):
    """Formatter for plain text file output (no colors)"""
    pass


def setup_logger(name, log_file='/tmp/gammu.log', level=logging.DEBUG, use_colors=True):
    """
    Setup a logger with colored console output and plain file output
    
    Args:
        name: Logger name
        log_file: Path to log file (default: /tmp/gammu.log)
        level: Logging level (default: DEBUG)
        use_colors: Whether to use colors in console output
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s UTC - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        use_colors=use_colors
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with plain text (append mode)
    try:
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(level)
        file_formatter = PlainFormatter(
            fmt='%(asctime)s UTC - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Failed to setup file logging to {log_file}: {e}")
    
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False
    
    return logger


def get_logger(name):
    """
    Get or create a logger with standard configuration
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # If logger has no handlers, set it up
    if not logger.handlers:
        return setup_logger(name)
    
    return logger
