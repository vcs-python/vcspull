"""URL handling for vcspull."""

from __future__ import annotations

from typing import Any

from libvcs.url.git import DEFAULT_RULES

_orig_rule_meta: dict[str, tuple[bool, int]] = {}


def enable_ssh_style_url_detection() -> None:
    """Enable detection of SSH-style URLs as explicit Git URLs.

    This makes the core-git-scp rule explicit, which allows URLs like
    'user@hostname:path/to/repo.git' to be detected with is_explicit=True.

    Examples
    --------
        >>> from vcspull.url import enable_ssh_style_url_detection
        >>> from libvcs.url.git import GitURL
        >>> # Without the patch
        >>> GitURL.is_valid('user@hostname:path/to/repo.git', is_explicit=True)
        False
        >>> # With the patch
        >>> enable_ssh_style_url_detection()
        >>> GitURL.is_valid('user@hostname:path/to/repo.git', is_explicit=True)
        True
    """
    # Patch the core-git-scp rule, storing its original state if not already stored
    for rule in DEFAULT_RULES:
        if rule.label == "core-git-scp":
            if rule.label not in _orig_rule_meta:
                _orig_rule_meta[rule.label] = (rule.is_explicit, rule.weight)
            rule.is_explicit = True
            rule.weight = 100
            break


def disable_ssh_style_url_detection() -> None:
    """Disable detection of SSH-style URLs as explicit Git URLs.

    This reverts the core-git-scp rule to its original state, where URLs like
    'user@hostname:path/to/repo.git' are not detected with is_explicit=True.

    Examples
    --------
        >>> from vcspull.url import enable_ssh_style_url_detection
        >>> from vcspull.url import disable_ssh_style_url_detection
        >>> from libvcs.url.git import GitURL
        >>> # Enable the patch
        >>> enable_ssh_style_url_detection()
        >>> GitURL.is_valid('user@hostname:path/to/repo.git', is_explicit=True)
        True
        >>> # Disable the patch
        >>> disable_ssh_style_url_detection()
        >>> GitURL.is_valid('user@hostname:path/to/repo.git', is_explicit=True)
        False
    """
    # Restore the core-git-scp rule to its original state, if known
    for rule in DEFAULT_RULES:
        if rule.label == "core-git-scp":
            orig = _orig_rule_meta.get(rule.label)
            if orig:
                rule.is_explicit, rule.weight = orig
                _orig_rule_meta.pop(rule.label, None)
            else:
                # Fallback to safe defaults
                rule.is_explicit = False
                rule.weight = 0
            break


def is_ssh_style_url_detection_enabled() -> bool:
    """Check if SSH-style URL detection is enabled.

    Returns
    -------
        bool: True if SSH-style URL detection is enabled, False otherwise.
    """
    for rule in DEFAULT_RULES:
        if rule.label == "core-git-scp":
            return rule.is_explicit
    return False


"""
Context manager and utility for SSH-style URL detection.
"""


class ssh_style_url_detection:
    """Context manager to enable/disable SSH-style URL detection."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def __enter__(self) -> None:
        """Enable or disable SSH-style URL detection on context enter."""
        if self.enabled:
            enable_ssh_style_url_detection()
        else:
            disable_ssh_style_url_detection()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Restore original SSH-style URL detection state on context exit."""
        # Always restore to disabled after context
        disable_ssh_style_url_detection()
