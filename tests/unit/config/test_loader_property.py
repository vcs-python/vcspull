"""Property-based tests for configuration loader.

This module contains property-based tests using Hypothesis for the
VCSPull configuration loader to ensure it properly handles loading,
merging, and saving configurations.
"""

from __future__ import annotations

import json
import pathlib
import typing as t

import hypothesis.strategies as st
import yaml
from hypothesis import HealthCheck, given, settings

from vcspull.config.loader import load_config, resolve_includes, save_config
from vcspull.config.models import Repository, Settings, VCSPullConfig


# Reuse strategies from test_models_property.py
@st.composite
def valid_url_strategy(draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any]) -> str:
    """Generate valid URLs for repositories."""
    protocols = ["https://", "http://", "git://", "ssh://git@"]
    domains = ["github.com", "gitlab.com", "bitbucket.org", "example.com"]
    usernames = ["user", "organization", "team", draw(st.text(min_size=3, max_size=10))]
    repo_names = [
        "repo",
        "project",
        "library",
        f"repo-{
            draw(
                st.text(
                    alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_',
                    min_size=1,
                    max_size=8,
                )
            )
        }",
    ]

    protocol = draw(st.sampled_from(protocols))
    domain = draw(st.sampled_from(domains))
    username = draw(st.sampled_from(usernames))
    repo_name = draw(st.sampled_from(repo_names))

    suffix = ".git" if protocol != "ssh://git@" else ""

    return f"{protocol}{domain}/{username}/{repo_name}{suffix}"


@st.composite
def valid_path_strategy(draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any]) -> str:
    """Generate valid paths for repositories."""
    base_dirs = ["~/code", "~/projects", "/tmp", "./projects"]
    sub_dirs = [
        "repo",
        "lib",
        "src",
        f"dir-{
            draw(
                st.text(
                    alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_',
                    min_size=1,
                    max_size=8,
                )
            )
        }",
    ]

    base_dir = draw(st.sampled_from(base_dirs))
    sub_dir = draw(st.sampled_from(sub_dirs))

    return f"{base_dir}/{sub_dir}"


@st.composite
def repository_strategy(
    draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any],
) -> Repository:
    """Generate valid Repository instances."""
    name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
    url = draw(valid_url_strategy())
    path = draw(valid_path_strategy())
    vcs = draw(st.one_of(st.none(), st.sampled_from(["git", "hg", "svn"])))

    # Optionally generate remotes
    remotes = {}
    if draw(st.booleans()):
        remote_names = ["upstream", "origin", "fork"]
        remote_count = draw(st.integers(min_value=1, max_value=3))
        for _ in range(remote_count):
            remote_name = draw(st.sampled_from(remote_names))
            if remote_name not in remotes:  # Avoid duplicates
                remotes[remote_name] = draw(valid_url_strategy())

    rev = draw(
        st.one_of(
            st.none(),
            st.text(min_size=1, max_size=40),  # Can be branch name, tag, or commit hash
        ),
    )

    web_url = draw(
        st.one_of(
            st.none(),
            st.sampled_from(
                [
                    f"https://github.com/user/{name}"
                    if name
                    else "https://github.com/user/repo",
                    f"https://gitlab.com/user/{name}"
                    if name
                    else "https://gitlab.com/user/repo",
                ],
            ),
        ),
    )

    return Repository(
        name=name,
        url=url,
        path=path,
        vcs=vcs,
        remotes=remotes,
        rev=rev,
        web_url=web_url,
    )


@st.composite
def settings_strategy(draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any]) -> Settings:
    """Generate valid Settings instances."""
    sync_remotes = draw(st.booleans())
    default_vcs = draw(st.one_of(st.none(), st.sampled_from(["git", "hg", "svn"])))
    depth = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=10)))

    return Settings(
        sync_remotes=sync_remotes,
        default_vcs=default_vcs,
        depth=depth,
    )


@st.composite
def vcspull_config_strategy(
    draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any],
    with_includes: bool = False,
) -> VCSPullConfig:
    """Generate valid VCSPullConfig instances.

    Parameters
    ----------
    draw : t.Callable
        Hypothesis draw function
    with_includes : bool, optional
        Whether to add include files to the config, by default False

    Returns
    -------
    VCSPullConfig
        A generated VCSPullConfig instance
    """
    settings = draw(settings_strategy())

    # Generate between 0 and 5 repositories
    repo_count = draw(st.integers(min_value=0, max_value=5))
    repositories = [draw(repository_strategy()) for _ in range(repo_count)]

    # Generate includes
    includes = []
    if with_includes:
        include_count = draw(st.integers(min_value=1, max_value=3))
        includes = [f"include{i}.yaml" for i in range(include_count)]

    return VCSPullConfig(
        settings=settings,
        repositories=repositories,
        includes=includes,
    )


class TestConfigLoaderProperties:
    """Property-based tests for configuration loading."""

    @given(config=vcspull_config_strategy())
    @settings(
        max_examples=10,  # Limit examples to avoid too many temp files
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_load_save_roundtrip(
        self, config: VCSPullConfig, tmp_path: pathlib.Path
    ) -> None:
        """Test that saving and loading a configuration preserves its content."""
        # Save the config to a temporary YAML file
        yaml_path = tmp_path / "config.yaml"
        save_config(config, yaml_path, format_type="yaml")

        # Load the config back
        loaded_config = load_config(yaml_path)

        # Check that loaded config matches original
        assert loaded_config.settings.model_dump() == config.settings.model_dump()
        assert len(loaded_config.repositories) == len(config.repositories)
        for i, repo in enumerate(config.repositories):
            assert loaded_config.repositories[i].url == repo.url
            assert loaded_config.repositories[i].path == repo.path

        # Also test with JSON format
        json_path = tmp_path / "config.json"
        save_config(config, json_path, format_type="json")

        # Load JSON config
        json_loaded_config = load_config(json_path)

        # Check that JSON loaded config matches original
        assert json_loaded_config.settings.model_dump() == config.settings.model_dump()
        assert len(json_loaded_config.repositories) == len(config.repositories)

    @given(
        main_config=vcspull_config_strategy(with_includes=True),
        included_configs=st.lists(vcspull_config_strategy(), min_size=1, max_size=3),
    )
    @settings(
        max_examples=10,  # Limit the number of examples
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_include_resolution(
        self,
        main_config: VCSPullConfig,
        included_configs: t.List[VCSPullConfig],
        tmp_path: pathlib.Path,
    ) -> None:
        """Test that include resolution properly merges configurations."""
        # Create and save included configs
        included_paths = []
        for i, include_config in enumerate(included_configs):
            include_path = tmp_path / f"include{i}.yaml"
            save_config(include_config, include_path)
            included_paths.append(include_path)

        # Update main config's includes to point to the actual files
        main_config.includes = [str(path) for path in included_paths]

        # Save main config
        main_path = tmp_path / "main.yaml"
        save_config(main_config, main_path)

        # Load and resolve includes
        loaded_config = load_config(main_path)
        resolved_config = resolve_includes(loaded_config, main_path.parent)

        # Verify all repositories are present in the resolved config
        all_repos = list(main_config.repositories)
        for include_config in included_configs:
            all_repos.extend(include_config.repositories)

        # Check that all repositories are present in the resolved config
        assert len(resolved_config.repositories) == len(all_repos)

        # Check that includes are cleared
        assert len(resolved_config.includes) == 0

        # Verify URLs of repositories match (as a basic check)
        resolved_urls = {repo.url for repo in resolved_config.repositories}
        original_urls = {repo.url for repo in all_repos}
        assert resolved_urls == original_urls

    @given(configs=st.lists(vcspull_config_strategy(), min_size=2, max_size=4))
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_nested_includes_resolution(
        self,
        configs: t.List[VCSPullConfig],
        tmp_path: pathlib.Path,
    ) -> None:
        """Test that nested includes are resolved properly."""
        # Save configs with nested includes
        # Last config has no includes
        paths = []
        for i, config in enumerate(configs):
            config_path = tmp_path / f"config{i}.yaml"

            # Add includes to each config (except the last one)
            if i < len(configs) - 1:
                config.includes = [f"config{i + 1}.yaml"]
            else:
                config.includes = []

            save_config(config, config_path)
            paths.append(config_path)

        # Load and resolve includes for the first config
        first_config = load_config(paths[0])
        resolved_config = resolve_includes(first_config, tmp_path)

        # Gather all repositories from original configs
        all_repos = []
        for config in configs:
            all_repos.extend(config.repositories)

        # Check repository count
        assert len(resolved_config.repositories) == len(all_repos)

        # Check all repositories are included
        resolved_urls = {repo.url for repo in resolved_config.repositories}
        original_urls = {repo.url for repo in all_repos}
        assert resolved_urls == original_urls

        # Check no includes remain
        assert len(resolved_config.includes) == 0

    @given(config=vcspull_config_strategy())
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_save_config_formats(
        self, config: VCSPullConfig, tmp_path: pathlib.Path
    ) -> None:
        """Test that configs can be saved in different formats."""
        # Save in YAML format
        yaml_path = tmp_path / "config.yaml"
        saved_yaml_path = save_config(config, yaml_path, format_type="yaml")
        assert saved_yaml_path.exists()

        # Verify YAML file is valid
        with saved_yaml_path.open() as f:
            yaml_content = yaml.safe_load(f)
        assert isinstance(yaml_content, dict)

        # Save in JSON format
        json_path = tmp_path / "config.json"
        saved_json_path = save_config(config, json_path, format_type="json")
        assert saved_json_path.exists()

        # Verify JSON file is valid
        with saved_json_path.open() as f:
            json_content = json.load(f)
        assert isinstance(json_content, dict)

        # Load both formats and compare
        yaml_config = load_config(saved_yaml_path)
        json_config = load_config(saved_json_path)

        # Check that both loaded configs match the original
        assert yaml_config.model_dump() == config.model_dump()
        assert json_config.model_dump() == config.model_dump()
