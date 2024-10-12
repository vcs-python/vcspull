"""Tests for sync functionality of vcspull."""

import pathlib
import textwrap
import typing as t

import pytest
from libvcs._internal.shortcuts import create_project
from libvcs.pytest_plugin import CreateRepoPytestFixtureFn
from libvcs.sync.git import GitRemote, GitSync

from vcspull._internal.config_reader import ConfigReader
from vcspull.cli.sync import update_repo
from vcspull.config import extract_repos, filter_repos, load_configs
from vcspull.validator import is_valid_config

from .helpers import write_config

if t.TYPE_CHECKING:
    from vcspull.types import ConfigDict


def test_makes_recursive(
    tmp_path: pathlib.Path,
    git_remote_repo: pathlib.Path,
) -> None:
    """Ensure that syncing creates directories recursively."""
    conf = ConfigReader._load(
        fmt="yaml",
        content=textwrap.dedent(
            f"""
        {tmp_path}/study/myrepo:
            my_url: git+file://{git_remote_repo}
    """,
        ),
    )
    if is_valid_config(conf):
        repos = extract_repos(config=conf)
        assert len(repos) > 0

        filtered_repos = filter_repos(repos, path="*")
        assert len(filtered_repos) > 0

        for r in filtered_repos:
            assert isinstance(r, dict)
            repo = create_project(**r)  # type: ignore
            repo.obtain()

            assert repo.path.exists()


def write_config_remote(
    config_path: pathlib.Path,
    tmp_path: pathlib.Path,
    config_tpl: str,
    path: pathlib.Path,
    clone_name: str,
) -> pathlib.Path:
    """Write vcspull configuration with git remote."""
    return write_config(
        config_path=config_path,
        content=config_tpl.format(
            tmp_path=str(tmp_path.parent),
            path=path,
            CLONE_NAME=clone_name,
        ),
    )


class ConfigVariationTest(t.NamedTuple):
    """pytest fixture for testing vcspull configuration."""

    # pytest (internal), used for naming tests
    test_id: str

    # fixture params
    config_tpl: str
    remote_list: list[str]


CONFIG_VARIATION_FIXTURES: list[ConfigVariationTest] = [
    ConfigVariationTest(
        test_id="default",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{path}
        """,
        remote_list=["origin"],
    ),
    ConfigVariationTest(
        test_id="expanded_repo_style",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{path}
        """,
        remote_list=["repo"],
    ),
    ConfigVariationTest(
        test_id="expanded_repo_style_with_remote",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{path}
                remotes:
                  secondremote: git+file://{path}
        """,
        remote_list=["secondremote"],
    ),
    ConfigVariationTest(
        test_id="expanded_repo_style_with_unprefixed_remote",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{path}
                remotes:
                  git_scheme_repo: git@codeberg.org:tmux-python/tmuxp.git
        """,
        remote_list=["git_scheme_repo"],
    ),
    ConfigVariationTest(
        test_id="expanded_repo_style_with_unprefixed_remote_2",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{path}
                remotes:
                  git_scheme_repo: git@github.com:tony/vcspull.git
        """,
        remote_list=["git_scheme_repo"],
    ),
]


@pytest.mark.parametrize(
    list(ConfigVariationTest._fields),
    CONFIG_VARIATION_FIXTURES,
    ids=[test.test_id for test in CONFIG_VARIATION_FIXTURES],
)
def test_config_variations(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    create_git_remote_repo: CreateRepoPytestFixtureFn,
    test_id: str,
    config_tpl: str,
    remote_list: list[str],
) -> None:
    """Test vcspull sync'ing across a variety of configurations."""
    dummy_repo = create_git_remote_repo()

    config_file = write_config_remote(
        config_path=tmp_path / "myrepos.yaml",
        tmp_path=tmp_path,
        config_tpl=config_tpl,
        path=dummy_repo,
        clone_name="myclone",
    )
    configs = load_configs([config_file])

    # TODO: Merge repos
    repos = filter_repos(configs, path="*")
    assert len(repos) == 1

    for repo_dict in repos:
        repo: GitSync = update_repo(repo_dict)
        remotes = repo.remotes() or {}
        remote_names = set(remotes.keys())
        assert set(remote_list).issubset(remote_names) or {"origin"}.issubset(
            remote_names,
        )

        for remote_name in remotes:
            current_remote = repo.remote(remote_name)
            assert current_remote is not None
            assert repo_dict is not None
            assert isinstance(remote_name, str)
            if (
                "remotes" in repo_dict
                and isinstance(repo_dict["remotes"], dict)
                and remote_name in repo_dict["remotes"]
            ):
                if repo_dict["remotes"][remote_name].fetch_url.startswith(
                    "git+file://",
                ):
                    assert current_remote.fetch_url == repo_dict["remotes"][
                        remote_name
                    ].fetch_url.replace(
                        "git+",
                        "",
                    ), "Final git remote should chop git+ prefix"
                else:
                    assert (
                        current_remote.fetch_url
                        == repo_dict["remotes"][remote_name].fetch_url
                    )


class UpdatingRemoteFixture(t.NamedTuple):
    """pytest fixture for vcspull configuration with a git remote."""

    # pytest (internal), used for naming tests
    test_id: str

    # fixture params
    config_tpl: str
    has_extra_remotes: bool


UPDATING_REMOTE_FIXTURES: list[UpdatingRemoteFixture] = [
    UpdatingRemoteFixture(
        test_id="no_remotes",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{path}
        """,
        has_extra_remotes=False,
    ),
    UpdatingRemoteFixture(
        test_id="no_remotes_expanded_repo_style",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{path}
        """,
        has_extra_remotes=False,
    ),
    UpdatingRemoteFixture(
        test_id="has_remotes_expanded_repo_style",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{path}
                remotes:
                  mirror_repo: git+file://{path}
        """,
        has_extra_remotes=True,
    ),
]


@pytest.mark.parametrize(
    list(UpdatingRemoteFixture._fields),
    UPDATING_REMOTE_FIXTURES,
    ids=[test.test_id for test in UPDATING_REMOTE_FIXTURES],
)
def test_updating_remote(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateRepoPytestFixtureFn,
    test_id: str,
    config_tpl: str,
    has_extra_remotes: bool,
) -> None:
    """Verify yaml configuration state is applied and reflected to local VCS clone."""
    dummy_repo = create_git_remote_repo()

    mirror_name = "mirror_repo"
    mirror_repo = create_git_remote_repo()

    repo_parent = tmp_path / "study" / "myrepo"
    repo_parent.mkdir(parents=True)

    initial_config: ConfigDict = {
        "vcs": "git",
        "name": "myclone",
        "path": tmp_path / "study/myrepo/myclone",
        "url": f"git+file://{dummy_repo}",
        "remotes": {
            mirror_name: GitRemote(
                name=mirror_name,
                fetch_url=f"git+file://{dummy_repo}",
                push_url=f"git+file://{dummy_repo}",
            ),
        },
    }

    for repo_dict in filter_repos(
        [initial_config],
    ):
        local_git_remotes = update_repo(repo_dict).remotes()
        assert "origin" in local_git_remotes

    expected_remote_url = f"git+file://{mirror_repo}"

    expected_config: ConfigDict = initial_config.copy()
    assert isinstance(expected_config["remotes"], dict)
    expected_config["remotes"][mirror_name] = GitRemote(
        name=mirror_name,
        fetch_url=expected_remote_url,
        push_url=expected_remote_url,
    )

    repo_dict = filter_repos([expected_config], name="myclone")[0]
    assert isinstance(repo_dict, dict)
    repo = update_repo(repo_dict)
    for remote_name in repo.remotes():
        remote = repo.remote(remote_name)
        if remote is not None:
            current_remote_url = remote.fetch_url.replace("git+", "")
            if remote_name in expected_config["remotes"]:
                assert (
                    expected_config["remotes"][remote_name].fetch_url.replace(
                        "git+",
                        "",
                    )
                    == current_remote_url
                )

            elif remote_name == "origin" and remote_name in expected_config["remotes"]:
                assert (
                    expected_config["remotes"]["origin"].fetch_url.replace("git+", "")
                    == current_remote_url
                )
