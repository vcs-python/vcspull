import pathlib
import typing as t

import pytest

from libvcs._internal.types import StrPath
from vcspull import config as config_tools


class LoadYaml(t.Protocol):
    def __call__(
        self, content: str, dir: StrPath = ..., filename: str = ...
    ) -> pathlib.Path:
        ...


@pytest.fixture
def load_yaml(tmp_path: pathlib.Path) -> LoadYaml:
    def fn(
        content: str, dir: StrPath = "randomdir", filename: str = "randomfilename.yaml"
    ) -> pathlib.Path:
        _dir = tmp_path / dir
        _dir.mkdir()
        _config = _dir / filename
        _config.write_text(content, encoding="utf-8")

        return _config

    return fn


def test_simple_format(load_yaml: LoadYaml) -> None:
    config_file = load_yaml(
        """
vcspull:
  libvcs: git+https://github.com/vcs-python/libvcs
   """
    )

    config = config_tools.Config.from_yaml_file(config_file)

    assert len(config.repos) == 1
    repo = config.repos[0]
    dir = repo.dir.parent.parent

    assert dir / "vcspull" == repo.dir.parent
    assert dir / "vcspull" / "libvcs" == repo.dir

    assert hasattr(config, "filter_repos")
    assert callable(config.filter_repos)
    assert config.filter_repos(dir=dir / "vcspull" / "libvcs") == [repo]
