"""Tests for URL handling in vcspull."""

from __future__ import annotations

import pytest
from libvcs.url.git import GitURL


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
    assert GitURL.is_valid(url)
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
    git_url = GitURL(url)
    assert git_url.user == expected_user
    assert git_url.hostname == expected_hostname
    assert git_url.path == expected_path
    assert git_url.suffix == ".git"
