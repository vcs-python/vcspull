import pytest

from vcspull import config


@pytest.fixture
def load_yaml(tmpdir):
    def fn(content, dir="randomdir", filename="randomfilename.yaml"):
        _dir = tmpdir.join(dir)
        _dir.mkdir()
        _dir.join(filename).write(content)

        configs = config.find_config_files(path=str(_dir))
        repos = config.load_configs(configs, str(_dir))
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

    assert str(dir.join("vcspull")) == repo["parent_dir"]
    assert str(dir.join("vcspull", "libvcs")) == repo["dir"]


def test_relative_dir(load_yaml):
    dir, _, repos = load_yaml(
        """
./relativedir:
  docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
   """
    )

    configs = config.find_config_files(path=str(dir))
    repos = config.load_configs(configs, str(dir))

    assert len(repos) == 1
    repo = repos[0]

    assert str(dir.join("relativedir")) == repo["parent_dir"]
    assert str(dir.join("relativedir", "docutils")) == repo["dir"]
