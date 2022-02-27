from vcspull import config


def test_relative_dir(tmpdir):
    arbitrary_dir = tmpdir.join("moo")
    arbitrary_dir.mkdir()

    arbitrary_dir.join("rel.yaml").write(
        """
./relativedir:
  docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
   """
    )

    configs = config.find_config_files(path=str(arbitrary_dir))
    repos = config.load_configs(configs, str(arbitrary_dir))

    assert str(arbitrary_dir.join("relativedir")) == repos[0]["parent_dir"]
    assert str(arbitrary_dir.join("relativedir", "docutils")) == repos[0]["repo_dir"]
