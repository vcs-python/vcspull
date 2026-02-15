"""User settings for vcspull.

Reads optional ``settings.toml`` from the vcspull config directory
(see :func:`vcspull.util.get_config_dir`) and provides typed access to
user preferences.
"""

from __future__ import annotations

import dataclasses
import logging

from vcspull.types import ConfigStyle
from vcspull.util import get_config_dir

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[import-not-found]

log = logging.getLogger(__name__)

SETTINGS_FILENAME = "settings.toml"


@dataclasses.dataclass
class VcspullSettings:
    """Parsed vcspull user settings.

    Examples
    --------
    >>> VcspullSettings()
    VcspullSettings(config_style=<ConfigStyle.STANDARD: 'standard'>)
    """

    config_style: ConfigStyle = ConfigStyle.STANDARD


def load_settings() -> VcspullSettings:
    """Load settings from the vcspull config directory.

    Returns the default settings when no ``settings.toml`` exists or
    when parsing fails.

    Returns
    -------
    VcspullSettings
        Parsed settings (or defaults on error).

    Examples
    --------
    >>> settings = load_settings()
    >>> isinstance(settings, VcspullSettings)
    True
    """
    config_dir = get_config_dir()
    settings_path = config_dir / SETTINGS_FILENAME

    if not settings_path.is_file():
        return VcspullSettings()

    try:
        with settings_path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        log.warning(
            "Failed to parse %s; using default settings",
            settings_path,
            exc_info=True,
        )
        return VcspullSettings()

    style_value = data.get("config_style")
    if style_value is not None:
        try:
            style = ConfigStyle(style_value)
        except ValueError:
            log.warning(
                "Unknown config_style '%s' in %s; using default 'standard'",
                style_value,
                settings_path,
            )
            style = ConfigStyle.STANDARD
    else:
        style = ConfigStyle.STANDARD

    return VcspullSettings(config_style=style)


def resolve_style(
    cli_style: str | None,
    settings: VcspullSettings | None = None,
) -> ConfigStyle:
    """Resolve the effective config style from CLI flag and user settings.

    The CLI ``--style`` flag overrides the ``settings.toml`` value, which
    itself overrides the built-in default (``standard``).

    Parameters
    ----------
    cli_style : str | None
        Value from ``--style`` CLI flag, or ``None`` if not specified.
    settings : VcspullSettings | None
        Pre-loaded settings; loaded lazily when ``None``.

    Returns
    -------
    ConfigStyle
        The resolved config style.

    Examples
    --------
    >>> from vcspull.types import ConfigStyle
    >>> resolve_style("concise")
    <ConfigStyle.CONCISE: 'concise'>
    >>> resolve_style(None, VcspullSettings(config_style=ConfigStyle.VERBOSE))
    <ConfigStyle.VERBOSE: 'verbose'>
    >>> resolve_style(None)  # doctest: +ELLIPSIS
    <ConfigStyle.STANDARD: 'standard'>
    """
    if cli_style is not None:
        try:
            return ConfigStyle(cli_style)
        except ValueError:
            log.warning("Unknown --style '%s'; falling back to 'standard'", cli_style)
            return ConfigStyle.STANDARD

    if settings is None:
        settings = load_settings()

    return settings.config_style
