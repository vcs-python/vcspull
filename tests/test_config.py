"""Tests for vcspull configuration format."""

from __future__ import annotations

import logging
import typing as t

import pytest

from vcspull import config

if t.TYPE_CHECKING:
    import pathlib

    from vcspull.types import ConfigDict, RawConfigDict


class LoadYAMLFn(t.Protocol):
    """Typing for load_yaml pytest fixture."""

    def __call__(
        self,
        content: str,
        path: str = "randomdir",
        filename: str = "randomfilename.yaml",
    ) -> tuple[pathlib.Path, list[t.Any | pathlib.Path], list[ConfigDict]]:
        """Callable function type signature for load_yaml pytest fixture."""
        ...


@pytest.fixture
def load_yaml(tmp_path: pathlib.Path) -> LoadYAMLFn:
    """Return a yaml loading function that uses temporary directory path."""

    def fn(
        content: str,
        path: str = "randomdir",
        filename: str = "randomfilename.yaml",
    ) -> tuple[pathlib.Path, list[pathlib.Path], list[ConfigDict]]:
        """Return vcspull configurations and write out config to temp directory."""
        dir_ = tmp_path / path
        dir_.mkdir()
        config_ = dir_ / filename
        config_.write_text(content, encoding="utf-8")

        configs = config.find_config_files(path=dir_)
        repos = config.load_configs(configs, cwd=dir_)
        return dir_, configs, repos

    return fn


def test_simple_format(load_yaml: LoadYAMLFn) -> None:
    """Test simple configuration YAML file for vcspull."""
    path, _, repos = load_yaml(
        """
vcspull:
  libvcs: git+https://github.com/vcs-python/libvcs
   """,
    )

    assert len(repos) == 1
    repo = repos[0]

    assert path / "vcspull" == repo["path"].parent
    assert path / "vcspull" / "libvcs" == repo["path"]


def test_relative_dir(load_yaml: LoadYAMLFn) -> None:
    """Test configuration files for vcspull support relative directories."""
    path, _, repos = load_yaml(
        """
./relativedir:
  docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
   """,
    )

    config_files = config.find_config_files(path=path)
    repos = config.load_configs(config_files, path)

    assert len(repos) == 1
    repo = repos[0]

    assert path / "relativedir" == repo["path"].parent
    assert path / "relativedir" / "docutils" == repo["path"]


class ExtractWorkspaceFixture(t.NamedTuple):
    """Fixture capturing workspace root injection scenarios."""

    test_id: str
    raw_config: dict[str, dict[str, str | dict[str, str]]]
    expected_roots: dict[str, str]


EXTRACT_WORKSPACE_FIXTURES: list[ExtractWorkspaceFixture] = [
    ExtractWorkspaceFixture(
        test_id="tilde-workspace",
        raw_config={
            "~/code/": {
                "alpha": {"repo": "git+https://example.com/alpha.git"},
            },
        },
        expected_roots={"alpha": "~/code/"},
    ),
    ExtractWorkspaceFixture(
        test_id="relative-workspace",
        raw_config={
            "./projects": {
                "beta": "git+https://example.com/beta.git",
            },
        },
        expected_roots={"beta": "./projects"},
    ),
]


@pytest.mark.parametrize(
    list(ExtractWorkspaceFixture._fields),
    EXTRACT_WORKSPACE_FIXTURES,
    ids=[fixture.test_id for fixture in EXTRACT_WORKSPACE_FIXTURES],
)
def test_extract_repos_injects_workspace_root(
    test_id: str,
    raw_config: dict[str, dict[str, str | dict[str, str]]],
    expected_roots: dict[str, str],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure extract_repos assigns workspace_root consistently."""
    import pathlib as pl

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    typed_raw_config = t.cast("RawConfigDict", raw_config)
    repos = config.extract_repos(typed_raw_config, cwd=tmp_path)

    assert len(repos) == len(expected_roots)

    for repo in repos:
        name = repo["name"]
        expected_root = expected_roots[name]
        assert repo["workspace_root"] == expected_root
        expected_path = config.expand_dir(pl.Path(expected_root), cwd=tmp_path) / name
        assert repo["path"] == expected_path


def _write_duplicate_config(tmp_path: pathlib.Path) -> pathlib.Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        (
            "~/workspace/:\n"
            "  alpha:\n"
            "    repo: git+https://example.com/alpha.git\n"
            "~/workspace/:\n"
            "  beta:\n"
            "    repo: git+https://example.com/beta.git\n"
        ),
        encoding="utf-8",
    )
    return config_path


def test_load_configs_merges_duplicate_workspace_roots(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate workspace roots are merged to keep every repository."""
    monkeypatch.setenv("HOME", str(tmp_path))
    caplog.set_level(logging.INFO, logger="vcspull.config")

    config_path = _write_duplicate_config(tmp_path)

    repos = config.load_configs([config_path], cwd=tmp_path)

    repo_names = {repo["name"] for repo in repos}
    assert repo_names == {"alpha", "beta"}

    merged_messages = [message for message in caplog.messages if "merged" in message]
    assert merged_messages, "Expected a merge log entry for duplicate roots"


def test_load_configs_can_skip_merging_duplicates(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The merge step can be skipped while still warning about duplicates."""
    monkeypatch.setenv("HOME", str(tmp_path))
    caplog.set_level(logging.WARNING, logger="vcspull.config")

    config_path = _write_duplicate_config(tmp_path)

    repos = config.load_configs(
        [config_path],
        cwd=tmp_path,
        merge_duplicates=False,
    )

    repo_names = {repo["name"] for repo in repos}
    assert repo_names == {"beta"}

    warning_messages = [
        message for message in caplog.messages if "duplicate" in message
    ]
    assert warning_messages, "Expected a warning about duplicate workspace roots"
