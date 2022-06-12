import pathlib

import pytest

from vcspull import config


@pytest.fixture
def load_yaml(tmp_path: pathlib.Path):
    def fn(content, dir="randomdir", filename="randomfilename.yaml"):
        _dir = tmp_path / dir
        _dir.mkdir()
        _config = _dir / filename
        _config.write_text(content, encoding="utf-8")

        configs = config.find_config_files(path=_dir)
        repos = config.load_configs(configs, cwd=_dir)
        return _dir, configs, repos

    return fn


def test_simple_format(load_yaml):
    dir, _, repos = load_yaml(
        """
vcspull:
  libvcs: git+https://github.com/vcs-python/libvcs
   """
    )

    assert len(repos) == 1
    repo = repos[0]

    assert dir / "vcspull" == repo["dir"].parent
    assert dir / "vcspull" / "libvcs" == repo["dir"]


def test_relative_dir(load_yaml):
    dir, _, repos = load_yaml(
        """
./relativedir:
  docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
   """
    )

    configs = config.find_config_files(path=dir)
    repos = config.load_configs(configs, dir)

    assert len(repos) == 1
    repo = repos[0]

    assert dir / "relativedir" == repo["dir"].parent
    assert dir / "relativedir" / "docutils" == repo["dir"]
