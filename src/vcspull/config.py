"""Config utility functions for vcspull.
vcspull.config
~~~~~~~~~~~~~~

A lot of these items are todo.

"""
import fnmatch
import logging
import os
import pathlib
import typing as t

from libvcs._internal.types import StrPath
from libvcs.sync.git import GitRemote
from vcspull._internal.config_reader import ConfigReader

from . import exc
from .types import ConfigDict, RawConfigDict
from .util import get_config_dir, update_dict

log = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    from typing_extensions import TypeGuard


def expand_dir(
    _dir: pathlib.Path, cwd: pathlib.Path = pathlib.Path.cwd()
) -> pathlib.Path:
    """Return path with environmental variables and tilde ~ expanded.

    Parameters
    ----------
    _dir : pathlib.Path
    cwd : pathlib.Path, optional
        current working dir (for deciphering relative _dir paths), defaults to
        :py:meth:`os.getcwd()`

    Returns
    -------
    pathlib.Path :
        Absolute directory path
    """
    _dir = pathlib.Path(os.path.expanduser(os.path.expandvars(str(_dir))))
    if not _dir.is_absolute():
        _dir = pathlib.Path(os.path.normpath(cwd / _dir))
        assert _dir == pathlib.Path(cwd, _dir).resolve(strict=False)
    return _dir


def extract_repos(config: RawConfigDict, cwd=pathlib.Path.cwd()) -> list[ConfigDict]:
    """Return expanded configuration.

    end-user configuration permit inline configuration shortcuts, expand to
    identical format for parsing.

    Parameters
    ----------
    config : dict
        the repo config in :py:class:`dict` format.
    cwd : pathlib.Path
        current working dir (for deciphering relative paths)

    Returns
    -------
    list : List of normalized repository information
    """
    configs: list[ConfigDict] = []
    for directory, repos in config.items():
        assert isinstance(repos, dict)
        for repo, repo_data in repos.items():
            conf: dict = {}

            """
            repo_name: http://myrepo.com/repo.git

            to

            repo_name: { url: 'http://myrepo.com/repo.git' }

            also assures the repo is a :py:class:`dict`.
            """

            if isinstance(repo_data, str):
                conf["url"] = repo_data
            else:
                conf = update_dict(conf, repo_data)

            if "repo" in conf:
                if "url" not in conf:
                    conf["url"] = conf.pop("repo")
                else:
                    conf.pop("repo", None)

            if "name" not in conf:
                conf["name"] = repo

            if "dir" not in conf:
                conf["dir"] = expand_dir(
                    pathlib.Path(expand_dir(pathlib.Path(directory), cwd=cwd))
                    / conf["name"],
                    cwd,
                )

            if "remotes" in conf:
                assert isinstance(conf["remotes"], dict)
                for remote_name, url in conf["remotes"].items():
                    if isinstance(url, GitRemote):
                        continue
                    if isinstance(url, str):
                        conf["remotes"][remote_name] = GitRemote(
                            name=remote_name, fetch_url=url, push_url=url
                        )
                    elif isinstance(url, dict):
                        assert "push_url" in url
                        assert "fetch_url" in url
                        conf["remotes"][remote_name] = GitRemote(
                            name=remote_name, **url
                        )

            def is_valid_config_dict(val: t.Any) -> "TypeGuard[ConfigDict]":
                assert isinstance(val, dict)
                return True

            assert is_valid_config_dict(conf)

            configs.append(conf)

    return configs


def find_home_config_files(
    filetype: list[str] = ["json", "yaml"]
) -> list[pathlib.Path]:
    """Return configs of ``.vcspull.{yaml,json}`` in user's home directory."""
    configs = []

    yaml_config = pathlib.Path(os.path.expanduser("~/.vcspull.yaml"))
    has_yaml_config = yaml_config.exists()
    json_config = pathlib.Path(os.path.expanduser("~/.vcspull.json"))
    has_json_config = json_config.exists()

    if not has_yaml_config and not has_json_config:
        log.debug(
            "No config file found. Create a .vcspull.yaml or .vcspull.json"
            " in your $HOME directory. http://vcspull.git-pull.com for a"
            " quickstart."
        )
    else:
        if sum(filter(None, [has_json_config, has_yaml_config])) > int(1):
            raise exc.MultipleConfigWarning()
        if has_yaml_config:
            configs.append(yaml_config)
        if has_json_config:
            configs.append(json_config)

    return configs


def find_config_files(
    path: t.Optional[t.Union[list[pathlib.Path], pathlib.Path]] = None,
    match: t.Union[list[str], str] = ["*"],
    filetype: t.Union[
        t.Literal["json", "yaml", "*"], list[t.Literal["json", "yaml", "*"]]
    ] = ["json", "yaml"],
    include_home: bool = False,
):
    """Return repos from a directory and match. Not recursive.

    Parameters
    ----------
    path : list
        list of paths to search
    match : list
        list of globs to search against
    filetype: list
        of filetypes to search against
    include_home : bool
        Include home configuration files

    Raises
    ------
    LoadConfigRepoConflict :
        There are two configs that have same path and name with different repo urls.

    Returns
    -------
    list :
        list of absolute paths to config files.
    """
    configs = []
    if path is None:
        path = get_config_dir()

    if include_home is True:
        configs.extend(find_home_config_files())

    if isinstance(path, list):
        for p in path:
            configs.extend(find_config_files(p, match, filetype))
            return configs
    else:
        path = pathlib.Path(os.path.expanduser(path))
        if isinstance(match, list):
            for m in match:
                configs.extend(find_config_files(path, m, filetype))
        else:
            if isinstance(filetype, list):
                for f in filetype:
                    configs.extend(find_config_files(path, match, f))
            else:
                match = f"{match}.{filetype}"
                configs = list(path.glob(match))

    return configs


def load_configs(files: list[StrPath], cwd=pathlib.Path.cwd()):
    """Return repos from a list of files.

    Parameters
    ----------
    files : list
        paths to config file
    cwd : pathlib.Path
        current path (pass down for :func:`extract_repos`

    Returns
    -------
    list of dict :
        expanded config dict item

    Todo
    ----
    Validate scheme, check for duplicate destinations, VCS urls
    """
    repos: list[ConfigDict] = []
    for file in files:
        if isinstance(file, str):
            file = pathlib.Path(file)
        assert isinstance(file, pathlib.Path)
        conf = ConfigReader._from_file(file)
        newrepos = extract_repos(conf, cwd=cwd)

        if not repos:
            repos.extend(newrepos)
            continue

        dupes = detect_duplicate_repos(repos, newrepos)

        if len(dupes) > 0:
            msg = ("repos with same path + different VCS detected!", dupes)
            raise exc.VCSPullException(msg)
        repos.extend(newrepos)

    return repos


ConfigDictTuple = tuple[ConfigDict, ConfigDict]


def detect_duplicate_repos(
    config1: list[ConfigDict], config2: list[ConfigDict]
) -> list[ConfigDictTuple]:
    """Return duplicate repos dict if repo_dir same and vcs different.

    Parameters
    ----------
    config1 : list[ConfigDict]

    config2 : list[ConfigDict]

    Returns
    -------
    list[ConfigDictTuple]
        List of duplicate tuples
    """
    if not config1:
        return []

    dupes: list[ConfigDictTuple] = []

    repo_dirs = {
        pathlib.Path(repo["dir"]).parent / repo["name"]: repo for repo in config1
    }
    repo_dirs_2 = {
        pathlib.Path(repo["dir"]).parent / repo["name"]: repo for repo in config2
    }

    for repo_dir, repo in repo_dirs.items():
        if repo_dir in repo_dirs_2:
            dupes.append((repo, repo_dirs_2[repo_dir]))

    return dupes


def in_dir(config_dir=None, extensions: list[str] = [".yml", ".yaml", ".json"]):
    """Return a list of configs in ``config_dir``.

    Parameters
    ----------
    config_dir : str
        directory to search
    extensions : list
        filetypes to check (e.g. ``['.yaml', '.json']``).

    Returns
    -------
    list
    """
    if config_dir is not None:
        config_dir = get_config_dir()
    configs = []

    for filename in os.listdir(config_dir):
        if is_config_file(filename, extensions) and not filename.startswith("."):
            configs.append(filename)

    return configs


def filter_repos(
    config: list[ConfigDict],
    dir: t.Union[pathlib.Path, t.Literal["*"], None] = None,
    vcs_url: t.Union[str, None] = None,
    name: t.Union[str, None] = None,
) -> list[ConfigDict]:
    """Return a :py:obj:`list` list of repos from (expanded) config file.

    dir, vcs_url and name all support fnmatch.

    Parameters
    ----------
    config : dict
        the expanded repo config in :py:class:`dict` format.
    dir : str, Optional
        directory of checkout location, fnmatch pattern supported
    vcs_url : str, Optional
        url of vcs remote, fn match pattern supported
    name : str, Optional
        project name, fnmatch pattern supported

    Returns
    -------
    list :
        Repos
    """
    repo_list: list[ConfigDict] = []

    if dir:
        repo_list.extend(
            [
                r
                for r in config
                if fnmatch.fnmatch(str(pathlib.Path(r["dir"]).parent), str(dir))
            ]
        )

    if vcs_url:
        repo_list.extend(
            r
            for r in config
            if fnmatch.fnmatch(str(r.get("url", r.get("repo"))), vcs_url)
        )

    if name:
        repo_list.extend(
            [r for r in config if fnmatch.fnmatch(str(r.get("name")), name)]
        )

    return repo_list


def is_config_file(
    filename: str, extensions: t.Union[list[str], str] = [".yml", ".yaml", ".json"]
):
    """Return True if file has a valid config file type.

    Parameters
    ----------
    filename : str
        filename to check (e.g. ``mysession.json``).
    extensions : list or str
        filetypes to check (e.g. ``['.yaml', '.json']``).

    Returns
    -------
    bool : True if is a valid config file type
    """
    extensions = [extensions] if isinstance(extensions, str) else extensions
    return any(filename.endswith(e) for e in extensions)
