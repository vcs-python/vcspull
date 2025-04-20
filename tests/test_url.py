"""Tests for URL handling in vcspull."""

from __future__ import annotations

import pytest
from libvcs.url.git import GitURL

from vcspull.url import disable_ssh_style_url_detection, enable_ssh_style_url_detection


def test_ssh_style_url_detection_toggle() -> None:
    """Test that SSH-style URL detection can be toggled on and off."""
    url = "user@myhostname.de:org/repo.git"

    # First, disable the detection
    disable_ssh_style_url_detection()

    # Without the patch, SSH-style URLs should not be detected as explicit
    assert GitURL.is_valid(url)  # Should be valid in non-explicit mode
    assert not GitURL.is_valid(
        url, is_explicit=True
    )  # Should not be valid in explicit mode

    # Now enable the detection
    enable_ssh_style_url_detection()

    # With the patch, SSH-style URLs should be detected as explicit
    assert GitURL.is_valid(url)  # Should still be valid in non-explicit mode
    assert GitURL.is_valid(
        url, is_explicit=True
    )  # Should now be valid in explicit mode

    # Verify the rule used
    git_url = GitURL(url)
    assert git_url.rule == "core-git-scp"

    # Re-enable for other tests
    enable_ssh_style_url_detection()


@pytest.mark.parametrize(
    "url",
    [
        "user@myhostname.de:org/repo.git",
        "git@github.com:vcs-python/vcspull.git",
        "git@gitlab.com:vcs-python/vcspull.git",
        "user@custom-host.com:path/to/repo.git",
    ],
)
def test_ssh_style_url_detection(url: str) -> None:
    """Test that SSH-style URLs are correctly detected."""
    # Ensure detection is enabled
    enable_ssh_style_url_detection()

    assert GitURL.is_valid(url)
    assert GitURL.is_valid(url, is_explicit=True)  # Should be valid in explicit mode
    git_url = GitURL(url)
    assert git_url.rule == "core-git-scp"


@pytest.mark.parametrize(
    "url,expected_user,expected_hostname,expected_path",
    [
        (
            "user@myhostname.de:org/repo.git",
            "user",
            "myhostname.de",
            "org/repo",
        ),
        (
            "git@github.com:vcs-python/vcspull.git",
            "git",
            "github.com",
            "vcs-python/vcspull",
        ),
        (
            "git@gitlab.com:vcs-python/vcspull.git",
            "git",
            "gitlab.com",
            "vcs-python/vcspull",
        ),
        (
            "user@custom-host.com:path/to/repo.git",
            "user",
            "custom-host.com",
            "path/to/repo",
        ),
    ],
)
def test_ssh_style_url_parsing(
    url: str, expected_user: str, expected_hostname: str, expected_path: str
) -> None:
    """Test that SSH-style URLs are correctly parsed."""
    # Ensure detection is enabled
    enable_ssh_style_url_detection()

    git_url = GitURL(url)
    assert git_url.user == expected_user
    assert git_url.hostname == expected_hostname
    assert git_url.path == expected_path
    assert git_url.suffix == ".git"
