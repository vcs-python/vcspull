"""Output formatting utilities for vcspull CLI."""

from __future__ import annotations

import json
import sys
import typing as t
from enum import Enum

if t.TYPE_CHECKING:
    from typing import Any


class OutputMode(Enum):
    """Output format modes."""

    HUMAN = "human"
    JSON = "json"
    NDJSON = "ndjson"


class OutputFormatter:
    """Manages output formatting for different modes (human, JSON, NDJSON)."""

    def __init__(self, mode: OutputMode = OutputMode.HUMAN) -> None:
        """Initialize the output formatter.

        Parameters
        ----------
        mode : OutputMode
            The output mode to use (human, json, ndjson)
        """
        self.mode = mode
        self._json_buffer: list[dict[str, Any]] = []

    def emit(self, data: dict[str, Any]) -> None:
        """Emit a data event.

        Parameters
        ----------
        data : dict
            Event data to emit. Should include a 'reason' field for NDJSON mode.
        """
        if self.mode == OutputMode.NDJSON:
            # Stream one JSON object per line immediately
            print(json.dumps(data), file=sys.stdout)
            sys.stdout.flush()
        elif self.mode == OutputMode.JSON:
            # Buffer for later output as single array
            self._json_buffer.append(data)
        # Human mode: handled by specific command implementations

    def emit_text(self, text: str) -> None:
        """Emit human-readable text (only in HUMAN mode).

        Parameters
        ----------
        text : str
            Text to output
        """
        if self.mode == OutputMode.HUMAN:
            print(text)

    def finalize(self) -> None:
        """Finalize output (flush JSON buffer if needed)."""
        if self.mode == OutputMode.JSON and self._json_buffer:
            print(json.dumps(self._json_buffer, indent=2), file=sys.stdout)
            self._json_buffer.clear()


def get_output_mode(json_flag: bool, ndjson_flag: bool) -> OutputMode:
    """Determine output mode from command flags.

    Parameters
    ----------
    json_flag : bool
        Whether --json was specified
    ndjson_flag : bool
        Whether --ndjson was specified

    Returns
    -------
    OutputMode
        The determined output mode (NDJSON takes precedence over JSON)
    """
    if ndjson_flag:
        return OutputMode.NDJSON
    if json_flag:
        return OutputMode.JSON
    return OutputMode.HUMAN
