"""Tests for edge cases in configuration file handling."""

from __future__ import annotations

import pathlib
import tempfile
from json.decoder import JSONDecodeError

import pytest
from yaml.scanner import ScannerError

from vcspull import exc
from vcspull._internal.config_reader import ConfigReader


def test_empty_config_file() -> None:
    """Test behavior when loading empty configuration files."""
    # Create an empty temporary file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        encoding="utf-8",
    ) as tmp_file:
        tmp_path = pathlib.Path(tmp_file.name)

    try:
        # Try to load the empty file
        config_reader = ConfigReader.from_file(tmp_path)

        # Check that it returns an empty dictionary or None
        # An empty file might be parsed as None by YAML parser
        assert config_reader.content == {} or config_reader.content is None
    finally:
        # Clean up the temporary file
        tmp_path.unlink()


def test_empty_config_with_comments() -> None:
    """Test behavior with configuration files containing only comments."""
    # Create a file with only comments
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        encoding="utf-8",
    ) as tmp_file:
        tmp_file.write("# Just a comment\n# Another comment\n\n")
        tmp_path = pathlib.Path(tmp_file.name)

    try:
        # Try to load the file with only comments
        config_reader = ConfigReader.from_file(tmp_path)

        # Check that it returns an empty dictionary or None
        # A file with only comments might be parsed as None by YAML parser
        assert config_reader.content == {} or config_reader.content is None
    finally:
        # Clean up the temporary file
        tmp_path.unlink()


def test_malformed_yaml() -> None:
    """Test behavior when loading malformed YAML configuration files."""
    # Create a file with malformed YAML
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        encoding="utf-8",
    ) as tmp_file:
        tmp_file.write(
            "invalid: yaml: content:\n  - missing colon\n  unclosed: 'string",
        )
        tmp_path = pathlib.Path(tmp_file.name)

    try:
        # Try to load the malformed file
        # Should raise a YAML parsing error
        with pytest.raises((ScannerError, exc.ConfigLoadError)):
            ConfigReader.from_file(tmp_path)
    finally:
        # Clean up the temporary file
        tmp_path.unlink()


def test_malformed_json() -> None:
    """Test behavior when loading malformed JSON configuration files."""
    # Create a file with malformed JSON
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as tmp_file:
        tmp_file.write('{"invalid": "json", "missing": "comma" "unclosed": "string}')
        tmp_path = pathlib.Path(tmp_file.name)

    try:
        # Try to load the malformed file
        # Should raise a JSON parsing error
        with pytest.raises((JSONDecodeError, exc.ConfigLoadError)):
            ConfigReader.from_file(tmp_path)
    finally:
        # Clean up the temporary file
        tmp_path.unlink()
