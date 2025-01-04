"""Tests for vcspull configuration format."""

import pathlib
import typing as t

import pytest

from vcspull import config

if t.TYPE_CHECKING:
    from vcspull.types import ConfigDict


class LoadYAMLFn(t.Protocol):
    """Typing for load_yaml pytest fixture."""

    def __call__(
        self,
        content: str,
        path: str = "randomdir",
        filename: str = "randomfilename.yaml",
    ) -> tuple[pathlib.Path, list[t.Union[t.Any, pathlib.Path]], list["ConfigDict"]]:
        """Callable function type signature for load_yaml pytest fixture."""
        ...


@pytest.fixture
def load_yaml(tmp_path: pathlib.Path) -> LoadYAMLFn:
    """Return a yaml loading function that uses temporary directory path."""

    def fn(
        content: str,
        path: str = "randomdir",
        filename: str = "randomfilename.yaml",
    ) -> tuple[pathlib.Path, list[pathlib.Path], list["ConfigDict"]]:
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
