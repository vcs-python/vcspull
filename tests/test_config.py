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


def test_relative_dir(load_yaml):
    dir, _, repos = load_yaml(
        """
./relativedir:
  docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
   """
    )

    configs = config.find_config_files(path=str(dir))
    repos = config.load_configs(configs, str(dir))

    assert str(dir.join("relativedir")) == repos[0]["parent_dir"]
    assert str(dir.join("relativedir", "docutils")) == repos[0]["repo_dir"]
