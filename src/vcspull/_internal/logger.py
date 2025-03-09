"""Logging utilities for VCSPull."""

from __future__ import annotations

import logging
import sys

# Create a logger for this package
logger = logging.getLogger("vcspull")


def setup_logger(
    level: int | str = logging.INFO,
    log_file: str | None = None,
) -> None:
    """Set up the logger with handlers.

    Parameters
    ----------
    level : Union[int, str]
        Logging level
    log_file : Optional[str]
        Path to log file
    """
    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    logger.setLevel(level)

    # Remove existing handlers
    for handler in logger.handlers:
        logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    console_handler.setFormatter(formatter)

    # Add console handler to logger
    logger.addHandler(console_handler)

    # Add file handler if log_file is provided
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
