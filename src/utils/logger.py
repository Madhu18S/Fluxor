"""
Structured logging configuration with Loguru
"""

import sys
import os
from pathlib import Path
from loguru import logger as loguru_logger
from datetime import datetime


def setup_logger(name: str = "fluxor", level: str = "INFO"):
    """
    Configure structured logging with Loguru
    
    Args:
        name: Logger name/module
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    
    # Remove default handler
    loguru_logger.remove()
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Console output format
    console_format = (
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # File output format (more detailed)
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )
    
    # Add console handler
    loguru_logger.add(
        sys.stdout,
        format=console_format,
        level=level,
        colorize=True,
    )
    
    # Add file handler for all logs
    log_file = log_dir / f"fluxor_{datetime.now().strftime('%Y%m%d')}.log"
    loguru_logger.add(
        str(log_file),
        format=file_format,
        level="DEBUG",
        rotation="500 MB",
        retention="7 days",
    )
    
    # Add separate error log file
    error_log_file = log_dir / f"fluxor_errors_{datetime.now().strftime('%Y%m%d')}.log"
    loguru_logger.add(
        str(error_log_file),
        format=file_format,
        level="ERROR",
        rotation="500 MB",
        retention="30 days",
    )
    
    return loguru_logger.bind(name=name)


# Create default logger
logger = setup_logger()
