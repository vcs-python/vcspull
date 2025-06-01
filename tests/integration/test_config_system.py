"""Integration tests for configuration system.

This module contains tests that verify the end-to-end behavior
of the configuration loading, validation, and processing system.
"""

from __future__ import annotations

import pathlib

from vcspull.config.loader import load_config, resolve_includes, save_config
from vcspull.config.models import Repository, Settings, VCSPullConfig


def test_complete_config_workflow(tmp_path: pathlib.Path) -> None:
    """Test the complete configuration workflow from creation to resolution."""
    # 1. Create a multi-level configuration setup

    # Base config with settings
    base_config = VCSPullConfig(
        settings=Settings(
            sync_remotes=True,
            default_vcs="git",
            depth=1,
        ),
        includes=["repos1.yaml", "repos2.yaml"],
    )

    # First included config with Git repositories
    repos1_config = VCSPullConfig(
        repositories=[
            Repository(
                name="repo1",
                url="https://github.com/example/repo1.git",
                path=str(tmp_path / "repos/repo1"),
                vcs="git",
            ),
            Repository(
                name="repo2",
                url="https://github.com/example/repo2.git",
                path=str(tmp_path / "repos/repo2"),
                vcs="git",
            ),
        ],
        includes=["nested/more-repos.yaml"],
    )

    # Second included config with Mercurial repositories
    repos2_config = VCSPullConfig(
        repositories=[
            Repository(
                name="hg-repo1",
                url="https://hg.example.org/repo1",
                path=str(tmp_path / "repos/hg-repo1"),
                vcs="hg",
            ),
        ],
    )

    # Nested included config with more repositories
    nested_config = VCSPullConfig(
        repositories=[
            Repository(
                name="nested-repo",
                url="https://github.com/example/nested-repo.git",
                path=str(tmp_path / "repos/nested-repo"),
                vcs="git",
            ),
            Repository(
                name="svn-repo",
                url="svn://svn.example.org/repo",
                path=str(tmp_path / "repos/svn-repo"),
                vcs="svn",
            ),
        ],
    )

    # 2. Save all config files

    # Create nested directory
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir(exist_ok=True)

    # Save all configs
    base_path = tmp_path / "vcspull.yaml"
    repos1_path = tmp_path / "repos1.yaml"
    repos2_path = tmp_path / "repos2.yaml"
    nested_path = nested_dir / "more-repos.yaml"

    save_config(base_config, base_path)
    save_config(repos1_config, repos1_path)
    save_config(repos2_config, repos2_path)
    save_config(nested_config, nested_path)

    # 3. Load and resolve the configuration

    loaded_config = load_config(base_path)
    resolved_config = resolve_includes(loaded_config, base_path.parent)

    # 4. Verify the result

    # All repositories should be present
    assert len(resolved_config.repositories) == 5

    # Settings should be preserved
    assert resolved_config.settings.sync_remotes is True
    assert resolved_config.settings.default_vcs == "git"
    assert resolved_config.settings.depth == 1

    # No includes should remain
    assert len(resolved_config.includes) == 0

    # Check repositories by name
    repo_names = {repo.name for repo in resolved_config.repositories}
    expected_names = {"repo1", "repo2", "hg-repo1", "nested-repo", "svn-repo"}
    assert repo_names == expected_names

    # Verify all paths are absolute
    for repo in resolved_config.repositories:
        assert pathlib.Path(repo.path).is_absolute()

    # 5. Test saving the resolved config

    resolved_path = tmp_path / "resolved.yaml"
    save_config(resolved_config, resolved_path)

    # 6. Load the saved resolved config and verify

    final_config = load_config(resolved_path)

    # It should match the original resolved config
    assert final_config.model_dump() == resolved_config.model_dump()

    # And have all the repositories
    assert len(final_config.repositories) == 5


def test_missing_include_handling(tmp_path: pathlib.Path) -> None:
    """Test that missing includes are handled gracefully."""
    # Create a config with a non-existent include
    config = VCSPullConfig(
        settings=Settings(sync_remotes=True),
        repositories=[
            Repository(
                name="repo1",
                url="https://github.com/example/repo1.git",
                path=str(tmp_path / "repos/repo1"),
            ),
        ],
        includes=["missing.yaml"],
    )

    # Save the config
    config_path = tmp_path / "config.yaml"
    save_config(config, config_path)

    # Load and resolve includes
    loaded_config = load_config(config_path)
    resolved_config = resolve_includes(loaded_config, tmp_path)

    # The config should still contain the original repository
    assert len(resolved_config.repositories) == 1
    assert resolved_config.repositories[0].name == "repo1"

    # And no includes (they're removed even if missing)
    assert len(resolved_config.includes) == 0


def test_circular_include_prevention(tmp_path: pathlib.Path) -> None:
    """Test that circular includes don't cause infinite recursion."""
    # Create configs that include each other
    config1 = VCSPullConfig(
        repositories=[
            Repository(
                name="repo1",
                url="https://github.com/example/repo1.git",
                path=str(tmp_path / "repos/repo1"),
            ),
        ],
        includes=["config2.yaml"],
    )

    config2 = VCSPullConfig(
        repositories=[
            Repository(
                name="repo2",
                url="https://github.com/example/repo2.git",
                path=str(tmp_path / "repos/repo2"),
            ),
        ],
        includes=["config1.yaml"],  # Creates a circular reference
    )

    # Save both configs
    config1_path = tmp_path / "config1.yaml"
    config2_path = tmp_path / "config2.yaml"
    save_config(config1, config1_path)
    save_config(config2, config2_path)

    # Load and resolve includes for the first config
    loaded_config = load_config(config1_path)
    resolved_config = resolve_includes(loaded_config, tmp_path)

    # The repositories might contain duplicates due to circular references
    # Get the unique URLs to check if both repos are included
    repo_urls = {repo.url for repo in resolved_config.repositories}
    expected_urls = {
        "https://github.com/example/repo1.git",
        "https://github.com/example/repo2.git",
    }
    assert repo_urls == expected_urls

    # And no includes
    assert len(resolved_config.includes) == 0
