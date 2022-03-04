"""Tests for vcspull config loading."""
import os
import textwrap

import pytest

import kaptan
from _pytest.compat import LEGACY_PATH

from vcspull import config, exc
from vcspull.config import expand_dir, extract_repos

from .fixtures import example as fixtures
from .helpers import EnvironmentVarGuard


def write_config(config_dir: LEGACY_PATH, filename: str, content: str):
    config = config_dir.join(filename)
    config.write(content)
    return config


@pytest.fixture
def config_dir(tmpdir: LEGACY_PATH):
    conf_dir = tmpdir.join(".vcspull")
    conf_dir.ensure(dir=True)
    return conf_dir


@pytest.fixture
def yaml_config(config_dir: LEGACY_PATH):
    yaml_file = config_dir.join("repos1.yaml")
    yaml_file.write("")
    return yaml_file


@pytest.fixture
def json_config(config_dir: LEGACY_PATH):
    json_file = config_dir.join("repos2.json")
    json_file.write("")
    return json_file


def test_dict_equals_yaml():
    # Verify that example YAML is returning expected dict format.
    config = kaptan.Kaptan(handler="yaml").import_config(
        textwrap.dedent(
            """\
            /home/me/myproject/study/:
              linux: git+git://git.kernel.org/linux/torvalds/linux.git
              freebsd: git+https://github.com/freebsd/freebsd.git
              sphinx: hg+https://bitbucket.org/birkenfeld/sphinx
              docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
            /home/me/myproject/github_projects/:
              kaptan:
                url: git+git@github.com:tony/kaptan.git
                remotes:
                  upstream: git+https://github.com/emre/kaptan
                  ms: git+https://github.com/ms/kaptan.git
            /home/me/myproject:
              .vim:
                url: git+git@github.com:tony/vim-config.git
                shell_command_after: ln -sf /home/me/.vim/.vimrc /home/me/.vimrc
              .tmux:
                url: git+git@github.com:tony/tmux-config.git
                shell_command_after:
                  - ln -sf /home/me/.tmux/.tmux.conf /home/me/.tmux.conf
            """
        )
    )
    assert fixtures.config_dict == config.export("dict")


def test_export_json(tmpdir):
    json_config = tmpdir.join(".vcspull.json")
    json_config_file = str(json_config)

    config = kaptan.Kaptan()
    config.import_config(fixtures.config_dict)

    json_config_data = config.export("json", indent=2)

    json_config.write(json_config_data)

    new_config = kaptan.Kaptan().import_config(json_config_file).get()
    assert fixtures.config_dict == new_config


def test_export_yaml(tmpdir):
    yaml_config = tmpdir.join(".vcspull.yaml")
    yaml_config_file = str(yaml_config)

    config = kaptan.Kaptan()
    config.import_config(fixtures.config_dict)

    yaml_config_data = config.export("yaml", indent=2)
    yaml_config.write(yaml_config_data)

    new_config = kaptan.Kaptan().import_config(yaml_config_file).get()
    assert fixtures.config_dict == new_config


def test_scan_config(tmpdir):
    config_files = []

    exists = os.path.exists
    garbage_file = tmpdir.join(".vcspull.psd")
    garbage_file.write("wat")

    for r, d, f in os.walk(str(tmpdir)):
        for filela in (
            x for x in f if x.endswith((".json", "yaml")) and x.startswith(".vcspull")
        ):
            config_files.append(str(tmpdir.join(filela)))

    files = 0
    if exists(str(tmpdir.join(".vcspull.json"))):
        files += 1
        assert str(tmpdir.join(".vcspull.json")) in config_files

    if exists(str(tmpdir.join(".vcspull.yaml"))):
        files += 1
        assert str(tmpdir.join(".vcspull.json")) in config_files

    assert len(config_files) == files


def test_expand_shell_command_after():
    # Expand shell commands from string to list.
    config = extract_repos(fixtures.config_dict)

    assert config, fixtures.config_dict_expanded


def test_expandenv_and_homevars():
    # Assure ~ tildes and environment template vars expand.
    config1 = (
        kaptan.Kaptan(handler="yaml")
        .import_config(
            textwrap.dedent(
                """\
                '~/study/':
                  sphinx: hg+file://{hg_repo_path}
                  docutils: svn+file://{svn_repo_path}
                  linux: git+file://{git_repo_path}
                '${HOME}/github_projects/':
                  kaptan:
                    url: git+file://{git_repo_path}
                    remotes:
                      test_remote: git+file://{git_repo_path}
                '~':
                  .vim:
                    url: git+file://{git_repo_path}
                  .tmux:
                    url: git+file://{git_repo_path}
                """
            )
        )
        .export("dict")
    )
    config2 = (
        kaptan.Kaptan(handler="json")
        .import_config(
            textwrap.dedent(
                """\
                {
                  "~/study/": {
                    "sphinx": "hg+file://${hg_repo_path}",
                    "docutils": "svn+file://${svn_repo_path}",
                    "linux": "git+file://${git_repo_path}"
                  },
                  "${HOME}/github_projects/": {
                    "kaptan": {
                      "url": "git+file://${git_repo_path}",
                      "remotes": {
                        "test_remote": "git+file://${git_repo_path}"
                      }
                    }
                  }
                }
                """
            )
        )
        .export("dict")
    )

    config1_expanded = extract_repos(config1)
    config2_expanded = extract_repos(config2)

    paths = [r["parent_dir"] for r in config1_expanded]
    assert expand_dir("${HOME}/github_projects/") in paths
    assert expand_dir("~/study/") in paths
    assert expand_dir("~") in paths

    paths = [r["parent_dir"] for r in config2_expanded]
    assert expand_dir("${HOME}/github_projects/") in paths
    assert expand_dir("~/study/") in paths


def test_find_config_files(tmpdir):
    # Test find_config_files in home directory.

    tmpdir.join(".vcspull.yaml").write("")
    with EnvironmentVarGuard() as env:
        env.set("HOME", str(tmpdir))
        os.environ.get("HOME") == str(tmpdir)
        expectedIn = str(tmpdir.join(".vcspull.yaml"))
        results = config.find_home_config_files()

        assert expectedIn in results


def test_multiple_config_files_raises_exception(tmpdir):
    tmpdir.join(".vcspull.json").write("")
    tmpdir.join(".vcspull.yaml").write("")
    with EnvironmentVarGuard() as env:
        with pytest.raises(exc.MultipleConfigWarning):
            env.set("HOME", str(tmpdir))
            os.environ.get("HOME") == str(tmpdir)

            config.find_home_config_files()


def test_in_dir(config_dir, yaml_config, json_config):
    expected = [yaml_config.purebasename, json_config.purebasename]
    result = config.in_dir(str(config_dir))

    assert len(expected) == len(result)


def test_find_config_path_string(config_dir, yaml_config, json_config):
    config_files = config.find_config_files(path=str(config_dir))

    assert str(yaml_config) in config_files
    assert str(json_config) in config_files


def test_find_config_path_list(config_dir, yaml_config, json_config):
    config_files = config.find_config_files(path=[str(config_dir)])

    assert str(yaml_config) in config_files
    assert str(json_config) in config_files


def test_find_config_match_string(config_dir, yaml_config, json_config):
    config_files = config.find_config_files(
        path=str(config_dir), match=yaml_config.purebasename
    )
    assert str(yaml_config) in config_files
    assert str(json_config) not in config_files

    config_files = config.find_config_files(
        path=[str(config_dir)], match=json_config.purebasename
    )
    assert str(yaml_config) not in config_files
    assert str(json_config) in config_files

    config_files = config.find_config_files(
        path=[str(config_dir)], match="randomstring"
    )
    assert str(yaml_config) not in config_files
    assert str(json_config) not in config_files

    config_files = config.find_config_files(path=[str(config_dir)], match="*")
    assert str(yaml_config) in config_files
    assert str(json_config) in config_files

    config_files = config.find_config_files(path=[str(config_dir)], match="repos*")
    assert str(yaml_config) in config_files
    assert str(json_config) in config_files

    config_files = config.find_config_files(path=[str(config_dir)], match="repos[1-9]*")
    assert len([c for c in config_files if str(yaml_config) in c]) == 1
    assert str(yaml_config) in config_files
    assert str(json_config) in config_files


def test_find_config_match_list(config_dir, yaml_config, json_config):
    config_files = config.find_config_files(
        path=[str(config_dir)],
        match=[yaml_config.purebasename, json_config.purebasename],
    )
    assert str(yaml_config) in config_files
    assert str(json_config) in config_files

    config_files = config.find_config_files(
        path=[str(config_dir)], match=[yaml_config.purebasename]
    )
    assert str(yaml_config) in config_files
    assert len([c for c in config_files if str(yaml_config) in c]) == 1
    assert str(json_config) not in config_files
    assert len([c for c in config_files if str(json_config) in c]) == 0


def test_find_config_filetype_string(config_dir, yaml_config, json_config):
    config_files = config.find_config_files(
        path=[str(config_dir)], match=yaml_config.purebasename, filetype="yaml"
    )
    assert str(yaml_config) in config_files
    assert str(json_config) not in config_files

    config_files = config.find_config_files(
        path=[str(config_dir)], match=yaml_config.purebasename, filetype="json"
    )
    assert str(yaml_config) not in config_files
    assert str(json_config) not in config_files

    config_files = config.find_config_files(
        path=[str(config_dir)], match="repos*", filetype="json"
    )
    assert str(yaml_config) not in config_files
    assert str(json_config) in config_files

    config_files = config.find_config_files(
        path=[str(config_dir)], match="repos*", filetype="*"
    )
    assert str(yaml_config) in config_files
    assert str(json_config) in config_files


def test_find_config_filetype_list(config_dir, yaml_config, json_config):
    config_files = config.find_config_files(
        path=[str(config_dir)], match=["repos*"], filetype=["*"]
    )
    assert str(yaml_config) in config_files
    assert str(json_config) in config_files

    config_files = config.find_config_files(
        path=[str(config_dir)], match=["repos*"], filetype=["json", "yaml"]
    )
    assert str(yaml_config) in config_files
    assert str(json_config) in config_files

    config_files = config.find_config_files(
        path=[str(config_dir)], filetype=["json", "yaml"]
    )
    assert str(yaml_config) in config_files
    assert str(json_config) in config_files


def test_find_config_include_home_config_files(
    tmpdir: LEGACY_PATH,
    config_dir: LEGACY_PATH,
    yaml_config: LEGACY_PATH,
    json_config: LEGACY_PATH,
):
    with EnvironmentVarGuard() as env:
        env.set("HOME", str(tmpdir))
        config_files = config.find_config_files(
            path=[str(config_dir)], match="*", include_home=True
        )
        assert str(yaml_config) in config_files
        assert str(json_config) in config_files

        config_file3 = tmpdir.join(".vcspull.json")
        config_file3.write("")
        results = config.find_config_files(
            path=[str(config_dir)], match="*", include_home=True
        )
        expectedIn = str(config_file3)
        assert expectedIn in results
        assert str(yaml_config) in results
        assert str(json_config) in results


def test_merge_nested_dict(tmpdir: LEGACY_PATH, config_dir: LEGACY_PATH):
    config1 = write_config(
        config_dir=config_dir,
        filename="repoduplicate1.yaml",
        content=textwrap.dedent(
            """\
/path/to/test/:
  subRepoDiffVCS:
    url: svn+file:///path/to/svnrepo
  subRepoSameVCS: git+file://path/to/gitrepo
  vcsOn1: svn+file:///path/to/another/svn
            """
        ),
    )
    config2 = write_config(
        config_dir=config_dir,
        filename="repoduplicate2.yaml",
        content=textwrap.dedent(
            """\
/path/to/test/:
  subRepoDiffVCS:
    url: git+file:///path/to/diffrepo
  subRepoSameVCS: git+file:///path/to/gitrepo
  vcsOn2: svn+file:///path/to/another/svn
            """
        ),
    )

    # Duplicate path + name with different repo URL / remotes raises.
    config_files = config.find_config_files(
        path=str(config_dir), match="repoduplicate[1-2]"
    )
    assert str(config1) in config_files
    assert str(config2) in config_files
    with pytest.raises(Exception):
        config.load_configs(config_files)
