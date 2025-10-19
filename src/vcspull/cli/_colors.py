"""Color output utilities for vcspull CLI."""

from __future__ import annotations

import os
import sys
from enum import Enum

from colorama import Fore, Style


class ColorMode(Enum):
    """Color output modes."""

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class Colors:
    """Semantic color constants and utilities."""

    # Semantic colors
    SUCCESS = Fore.GREEN  # Success, additions, up-to-date
    WARNING = Fore.YELLOW  # Warnings, changes needed, behind remote
    ERROR = Fore.RED  # Errors, deletions, conflicts
    INFO = Fore.CYAN  # Information, paths, URLs
    HIGHLIGHT = Fore.MAGENTA  # Workspace roots, important labels
    MUTED = Fore.BLUE  # Subdued info, bullets
    RESET = Style.RESET_ALL

    def __init__(self, mode: ColorMode = ColorMode.AUTO) -> None:
        """Initialize color manager.

        Parameters
        ----------
        mode : ColorMode
            Color mode to use (auto, always, never)
        """
        self.mode = mode
        self._enabled = self._should_enable_color()

    def _should_enable_color(self) -> bool:
        """Determine if color should be enabled.

        Returns
        -------
        bool
            True if colors should be enabled
        """
        # Respect NO_COLOR environment variable
        if os.environ.get("NO_COLOR"):
            return False

        if self.mode == ColorMode.NEVER:
            return False
        if self.mode == ColorMode.ALWAYS:
            return True

        # AUTO mode: check if stdout is a TTY
        return sys.stdout.isatty()

    def colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled.

        Parameters
        ----------
        text : str
            Text to colorize
        color : str
            Color code (e.g., Fore.GREEN)

        Returns
        -------
        str
            Colorized text if enabled, plain text otherwise
        """
        if self._enabled:
            return f"{color}{text}{self.RESET}"
        return text

    def success(self, text: str) -> str:
        """Format text as success (green)."""
        return self.colorize(text, self.SUCCESS)

    def warning(self, text: str) -> str:
        """Format text as warning (yellow)."""
        return self.colorize(text, self.WARNING)

    def error(self, text: str) -> str:
        """Format text as error (red)."""
        return self.colorize(text, self.ERROR)

    def info(self, text: str) -> str:
        """Format text as info (cyan)."""
        return self.colorize(text, self.INFO)

    def highlight(self, text: str) -> str:
        """Format text as highlighted (magenta)."""
        return self.colorize(text, self.HIGHLIGHT)

    def muted(self, text: str) -> str:
        """Format text as muted (blue)."""
        return self.colorize(text, self.MUTED)


def get_color_mode(color_arg: str | None = None) -> ColorMode:
    """Determine color mode from argument.

    Parameters
    ----------
    color_arg : str | None
        Color mode argument (auto, always, never)

    Returns
    -------
    ColorMode
        The determined color mode
    """
    if color_arg is None:
        return ColorMode.AUTO

    try:
        return ColorMode(color_arg.lower())
    except ValueError:
        return ColorMode.AUTO
