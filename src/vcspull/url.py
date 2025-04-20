"""URL handling for vcspull."""

from __future__ import annotations

from libvcs.url.git import DEFAULT_RULES


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
    for rule in DEFAULT_RULES:
        if rule.label == "core-git-scp":
            # Make the rule explicit so it can be detected with is_explicit=True
            rule.is_explicit = True
            # Increase the weight to ensure it takes precedence
            rule.weight = 100


def disable_ssh_style_url_detection() -> None:
    """Disable detection of SSH-style URLs as explicit Git URLs.

    This reverts the core-git-scp rule to its original state, where URLs like
    'user@hostname:path/to/repo.git' are not detected with is_explicit=True.

    Examples
    --------
        >>> from vcspull.url import enable_ssh_style_url_detection, disable_ssh_style_url_detection
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
    for rule in DEFAULT_RULES:
        if rule.label == "core-git-scp":
            # Revert to original state
            rule.is_explicit = False
            rule.weight = 0


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


# Enable SSH-style URL detection by default
enable_ssh_style_url_detection()
