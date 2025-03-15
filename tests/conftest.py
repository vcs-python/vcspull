"""Test configuration for pytest.

This module imports fixtures from other modules to make them available
to all tests.
"""

from __future__ import annotations

# Import fixtures from example_configs.py
from tests.fixtures.example_configs import (
    complex_yaml_config,
    config_with_includes,
    json_config,
    simple_yaml_config,
)

# Re-export fixtures to make them available to all tests
__all__ = [
    "complex_yaml_config",
    "config_with_includes",
    "json_config",
    "simple_yaml_config",
]
