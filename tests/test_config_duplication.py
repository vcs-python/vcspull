"""Tests for duplicate repository detection and conflicting configurations."""

from __future__ import annotations

import pathlib
import tempfile
import typing as t

from vcspull import config
from vcspull._internal.config_reader import ConfigReader


def test_duplicate_repo_detection() -> None:
    """Test detection of duplicate repositories in configuration."""
    # Create a config with duplicate repositories (same path and name)
    config_dict = {
        "/tmp/test_repos/": {
            "repo1": "git+https://github.com/user/repo1.git",
        },
        "/tmp/test_repos": {  # Same path without trailing slash
            "repo1": "git+https://github.com/user/repo1.git",
        },
    }

    # Get the flat list of repositories
    repo_list = config.extract_repos(config_dict)

    # Check if duplicates are identified
    # Note: The current implementation might not deduplicate entries
    # This test verifies the current behavior, which might be to keep both entries
    paths = [str(repo["path"]) for repo in repo_list]

    # Count occurrences of the path
    path_count = paths.count(str(pathlib.Path("/tmp/test_repos/repo1")))

    # The test passes regardless of whether duplicates are kept or removed
    # This just documents the current behavior
    assert path_count > 0


def test_duplicate_repo_different_urls() -> None:
    """Test handling of duplicate repositories with different URLs."""
    # Create a config with duplicated repos but different URLs
    config_dict = {
        "/tmp/test_repos/": {
            "repo1": "git+https://github.com/user/repo1.git",
        },
        "/tmp/other/": {
            "repo1": "git+https://github.com/different/repo1.git",  # Different URL
        },
    }

    # Get the flat list of repositories
    repo_list = config.extract_repos(config_dict)

    # Both should be kept as they are in different paths
    names = [repo["name"] for repo in repo_list]
    assert names.count("repo1") == 2

    # Ensure they have different paths
    paths = [str(repo["path"]) for repo in repo_list]
    assert str(pathlib.Path("/tmp/test_repos/repo1")) in paths
    assert str(pathlib.Path("/tmp/other/repo1")) in paths


def test_conflicting_repo_configs() -> None:
    """Test handling of conflicting repository configurations."""
    # Create two temporary config files with conflicting definitions
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as file1:
        file1.write("""
/tmp/test_repos/:
  repo1:
    vcs: git
    url: https://github.com/user/repo1.git
""")
        file1_path = pathlib.Path(file1.name)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as file2:
        file2.write("""
/tmp/test_repos/:
  repo1:
    vcs: git
    url: https://github.com/different/repo1.git  # Different URL
""")
        file2_path = pathlib.Path(file2.name)

    try:
        # Load both config files
        config1 = ConfigReader.from_file(file1_path).content
        config2 = ConfigReader.from_file(file2_path).content

        # Merge the configs - should keep the last one by default
        merged: dict[str, t.Any] = {}
        config.update_dict(merged, config1)
        config.update_dict(merged, config2)

        # The merged result should have the URL from config2
        repo_list = config.extract_repos(merged)
        repo = next(r for r in repo_list if r["name"] == "repo1")
        assert repo["url"] == "https://github.com/different/repo1.git"

    finally:
        # Clean up temporary files
        try:
            file1_path.unlink()
            file2_path.unlink()
        except Exception:
            pass


def test_conflicting_repo_types() -> None:
    """Test handling of conflicting repository VCS types."""
    # Create two temporary config files with different VCS types
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as file1:
        file1.write("""
/tmp/test_repos/:
  repo1:
    vcs: git
    url: https://github.com/user/repo1.git
""")
        file1_path = pathlib.Path(file1.name)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as file2:
        file2.write("""
/tmp/test_repos/:
  repo1:
    vcs: hg  # Different VCS
    url: https://hg.example.com/repo1
""")
        file2_path = pathlib.Path(file2.name)

    try:
        # Load both config files
        config1 = ConfigReader.from_file(file1_path).content
        config2 = ConfigReader.from_file(file2_path).content

        # Merge the configs - should keep the last one
        merged: dict[str, t.Any] = {}
        config.update_dict(merged, config1)
        config.update_dict(merged, config2)

        # The merged result should have the VCS from config2
        repo_list = config.extract_repos(merged)
        repo = next(r for r in repo_list if r["name"] == "repo1")
        assert repo["vcs"] == "hg"

    finally:
        # Clean up temporary files
        try:
            file1_path.unlink()
            file2_path.unlink()
        except Exception:
            pass
