"""Tests for vcspull config loading."""
import os
import pathlib
import textwrap

import pytest

from vcspull import config, exc
from vcspull._internal.config_reader import ConfigReader
from vcspull.config import expand_dir, extract_repos
from vcspull.validator import is_valid_config

from .fixtures import example as fixtures
from .helpers import EnvironmentVarGuard, load_raw, write_config


@pytest.fixture()
def yaml_config(config_path: pathlib.Path) -> pathlib.Path:
    yaml_file = config_path / "repos1.yaml"
    yaml_file.touch()
    return yaml_file


@pytest.fixture()
def json_config(config_path: pathlib.Path) -> pathlib.Path:
    json_file = config_path / "repos2.json"
    json_file.touch()
    return json_file


def test_dict_equals_yaml() -> None:
    # Verify that example YAML is returning expected dict format.
    config = ConfigReader._load(
        format="yaml",
        content="""\
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
            """,
    )
    assert fixtures.config_dict == config


def test_export_json(tmp_path: pathlib.Path) -> None:
    json_config = tmp_path / ".vcspull.json"

    config = ConfigReader(content=fixtures.config_dict)

    json_config_data = config.dump("json", indent=2)

    json_config.write_text(json_config_data, encoding="utf-8")

    new_config = ConfigReader._from_file(json_config)
    assert fixtures.config_dict == new_config


def test_export_yaml(tmp_path: pathlib.Path) -> None:
    yaml_config = tmp_path / ".vcspull.yaml"

    config = ConfigReader(content=fixtures.config_dict)

    yaml_config_data = config.dump("yaml", indent=2)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    new_config = ConfigReader._from_file(yaml_config)
    assert fixtures.config_dict == new_config


def test_scan_config(tmp_path: pathlib.Path) -> None:
    config_files: list[str] = []

    exists = os.path.exists
    garbage_file = tmp_path / ".vcspull.psd"
    garbage_file.write_text("wat", encoding="utf-8")

    for _r, _d, file in os.walk(str(tmp_path)):
        config_files += [
            str(tmp_path / scanned_file)
            for scanned_file in file
            if scanned_file.endswith((".json", "yaml"))
            and scanned_file.startswith(".vcspull")
        ]

    files = 0
    if exists(str(tmp_path / ".vcspull.json")):
        files += 1
        assert str(tmp_path / ".vcspull.json") in config_files

    if exists(str(tmp_path / ".vcspull.yaml")):
        files += 1
        assert str(tmp_path / ".vcspull.json") in config_files

    assert len(config_files) == files


def test_expand_shell_command_after() -> None:
    # Expand shell commands from string to list.
    assert is_valid_config(fixtures.config_dict)
    config = extract_repos(fixtures.config_dict)

    assert config, fixtures.config_dict_expanded


def test_expandenv_and_homevars() -> None:
    # Assure ~ tildes and environment template vars expand.
    config1 = load_raw(
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
                """,
        format="yaml",
    )
    config2 = load_raw(
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
                """,
        format="json",
    )

    assert is_valid_config(config1)
    assert is_valid_config(config2)

    config1_expanded = extract_repos(config1)
    config2_expanded = extract_repos(config2)

    paths = [r["dir"].parent for r in config1_expanded]
    assert expand_dir(pathlib.Path("${HOME}/github_projects/")) in paths
    assert expand_dir(pathlib.Path("~/study/")) in paths
    assert expand_dir(pathlib.Path("~")) in paths

    paths = [r["dir"].parent for r in config2_expanded]
    assert expand_dir(pathlib.Path("${HOME}/github_projects/")) in paths
    assert expand_dir(pathlib.Path("~/study/")) in paths


def test_find_config_files(tmp_path: pathlib.Path) -> None:
    # Test find_config_files in home directory.

    pull_config = tmp_path / ".vcspull.yaml"
    pull_config.touch()
    with EnvironmentVarGuard() as env:
        env.set("HOME", str(tmp_path))
        assert pathlib.Path.home() == tmp_path
        expected_in = tmp_path / ".vcspull.yaml"
        results = config.find_home_config_files()

        assert expected_in in results


def test_multiple_config_files_raises_exception(tmp_path: pathlib.Path) -> None:
    json_conf_file = tmp_path / ".vcspull.json"
    json_conf_file.touch()
    yaml_conf_file = tmp_path / ".vcspull.yaml"
    yaml_conf_file.touch()

    with EnvironmentVarGuard() as env:
        env.set("HOME", str(tmp_path))
        with pytest.raises(exc.MultipleConfigWarning):
            config.find_home_config_files()


def test_in_dir(
    config_path: pathlib.Path,
    yaml_config: pathlib.Path,
    json_config: pathlib.Path,
) -> None:
    expected = [yaml_config.stem, json_config.stem]
    result = config.in_dir(config_path)

    assert len(expected) == len(result)


def test_find_config_path_string(
    config_path: pathlib.Path, yaml_config: pathlib.Path, json_config: pathlib.Path
) -> None:
    config_files = config.find_config_files(path=config_path)

    assert yaml_config in config_files
    assert json_config in config_files


def test_find_config_path_list(
    config_path: pathlib.Path,
    yaml_config: pathlib.Path,
    json_config: pathlib.Path,
) -> None:
    config_files = config.find_config_files(path=[config_path])

    assert yaml_config in config_files
    assert json_config in config_files


def test_find_config_match_string(
    config_path: pathlib.Path,
    yaml_config: pathlib.Path,
    json_config: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_files = config.find_config_files(path=config_path, match=yaml_config.stem)
    assert yaml_config in config_files
    assert json_config not in config_files

    config_files = config.find_config_files(path=[config_path], match=json_config.stem)
    assert yaml_config not in config_files
    assert json_config in config_files

    config_files = config.find_config_files(path=[config_path], match="randomstring")
    assert yaml_config not in config_files
    assert json_config not in config_files

    config_files = config.find_config_files(path=[config_path], match="*")
    assert yaml_config in config_files
    assert json_config in config_files

    config_files = config.find_config_files(path=[config_path], match="repos*")
    assert yaml_config in config_files
    assert json_config in config_files

    config_files = config.find_config_files(path=[config_path], match="repos[1-9]*")
    assert len([c for c in config_files if str(yaml_config) in str(c)]) == 1
    assert yaml_config in config_files
    assert json_config in config_files


def test_find_config_match_list(
    config_path: pathlib.Path,
    yaml_config: pathlib.Path,
    json_config: pathlib.Path,
) -> None:
    config_files = config.find_config_files(
        path=[config_path],
        match=[yaml_config.stem, json_config.stem],
    )
    assert yaml_config in config_files
    assert json_config in config_files

    config_files = config.find_config_files(
        path=[config_path], match=[yaml_config.stem]
    )
    assert yaml_config in config_files
    assert len([c for c in config_files if str(yaml_config) in str(c)]) == 1
    assert json_config not in config_files
    assert len([c for c in config_files if str(json_config) in str(c)]) == 0


def test_find_config_filetype_string(
    config_path: pathlib.Path, yaml_config: pathlib.Path, json_config: pathlib.Path
) -> None:
    config_files = config.find_config_files(
        path=[config_path], match=yaml_config.stem, filetype="yaml"
    )
    assert yaml_config in config_files
    assert json_config not in config_files

    config_files = config.find_config_files(
        path=[config_path], match=yaml_config.stem, filetype="json"
    )
    assert yaml_config not in config_files
    assert json_config not in config_files

    config_files = config.find_config_files(
        path=[config_path], match="repos*", filetype="json"
    )
    assert yaml_config not in config_files
    assert json_config in config_files

    config_files = config.find_config_files(
        path=[config_path], match="repos*", filetype="*"
    )
    assert yaml_config in config_files
    assert json_config in config_files


def test_find_config_filetype_list(
    config_path: pathlib.Path, yaml_config: pathlib.Path, json_config: pathlib.Path
) -> None:
    config_files = config.find_config_files(
        path=[config_path], match=["repos*"], filetype=["*"]
    )
    assert yaml_config in config_files
    assert json_config in config_files

    config_files = config.find_config_files(
        path=[config_path], match=["repos*"], filetype=["json", "yaml"]
    )
    assert yaml_config in config_files
    assert json_config in config_files

    config_files = config.find_config_files(
        path=[config_path], filetype=["json", "yaml"]
    )
    assert yaml_config in config_files
    assert json_config in config_files


def test_find_config_include_home_config_files(
    tmp_path: pathlib.Path,
    config_path: pathlib.Path,
    yaml_config: pathlib.Path,
    json_config: pathlib.Path,
) -> None:
    with EnvironmentVarGuard() as env:
        env.set("HOME", str(tmp_path))
        config_files = config.find_config_files(
            path=[config_path], match="*", include_home=True
        )
        assert yaml_config in config_files
        assert json_config in config_files

        config_file3 = tmp_path / ".vcspull.json"
        config_file3.touch()
        results = config.find_config_files(
            path=[config_path], match="*", include_home=True
        )
        expected_in = config_file3
        assert expected_in in results
        assert yaml_config in results
        assert json_config in results


def test_merge_nested_dict(tmp_path: pathlib.Path, config_path: pathlib.Path) -> None:
    config1 = write_config(
        config_path=config_path / "repoduplicate1.yaml",
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
        config_path=config_path / "repoduplicate2.yaml",
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
        path=config_path, match="repoduplicate[1-2]"
    )
    assert config1 in config_files
    assert config2 in config_files
    with pytest.raises(exc.VCSPullException):
        config.load_configs(config_files)
