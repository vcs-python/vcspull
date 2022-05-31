"""Config utility functions for vcspull.
vcspull.config
~~~~~~~~~~~~~~

A lot of these items are todo.

"""
import fnmatch
import logging
import os
import pathlib
from typing import Literal, Optional, Union

import kaptan

from libvcs.projects.git import GitRemote

from . import exc
from .util import get_config_dir, update_dict

log = logging.getLogger(__name__)


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


def extract_repos(config: dict, cwd=pathlib.Path.cwd()) -> list[dict]:
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
    configs = []
    for directory, repos in config.items():
        for repo, repo_data in repos.items():

            conf = {}

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
            if "parent_dir" not in conf:
                conf["parent_dir"] = expand_dir(directory, cwd=cwd)

            # repo_dir -> dir in libvcs 0.12.0b25
            if "repo_dir" in conf and "dir" not in conf:
                conf["dir"] = conf.pop("repo_dir")

            if "dir" not in conf:
                conf["dir"] = expand_dir(conf["parent_dir"] / conf["name"], cwd)

            if "remotes" in conf:
                for remote_name, url in conf["remotes"].items():
                    conf["remotes"][remote_name] = GitRemote(
                        name=remote_name, fetch_url=url, push_url=url
                    )
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
    path: Optional[Union[list[pathlib.Path], pathlib.Path]] = None,
    match: Union[list[str], str] = ["*"],
    filetype: Union[
        Literal["json", "yaml", "*"], list[Literal["json", "yaml", "*"]]
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
                configs = path.glob(match)

    return configs


def load_configs(files: list[Union[str, pathlib.Path]], cwd=pathlib.Path.cwd()):
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
    repos = []
    for file in files:
        if isinstance(file, str):
            file = pathlib.Path(file)
        ext = file.suffix.lstrip(".")
        conf = kaptan.Kaptan(handler=ext).import_config(str(file))
        newrepos = extract_repos(conf.export("dict"), cwd=cwd)

        if not repos:
            repos.extend(newrepos)
            continue

        dupes = detect_duplicate_repos(repos, newrepos)

        if dupes:
            msg = ("repos with same path + different VCS detected!", dupes)
            raise exc.VCSPullException(msg)
        repos.extend(newrepos)

    return repos


def detect_duplicate_repos(repos1: list[dict], repos2: list[dict]):
    """Return duplicate repos dict if repo_dir same and vcs different.

    Parameters
    ----------
    repos1 : dict
        list of repo expanded dicts

    repos2 : dict
        list of repo expanded dicts

    Returns
    -------
    list of dict, or None
        Duplicate repos
    """
    dupes = []
    path_dupe_repos = []

    curpaths = [r["dir"] for r in repos1]
    newpaths = [r["dir"] for r in repos2]
    path_duplicates = list(set(curpaths).intersection(newpaths))

    if not path_duplicates:
        return None

    path_dupe_repos.extend(
        [r for r in repos2 if any(r["dir"] == p for p in path_duplicates)]
    )

    if not path_dupe_repos:
        return None

    for n in path_dupe_repos:
        currepo = next((r for r in repos1 if r["dir"] == n["dir"]), None)
        if n["url"] != currepo["url"]:
            dupes += (n, currepo)
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
    config: dict,
    dir: Union[pathlib.Path, None] = None,
    vcs_url: Union[str, None] = None,
    name: Union[str, None] = None,
):
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
    repo_list = []

    if dir:
        repo_list.extend([r for r in config if fnmatch.fnmatch(r["parent_dir"], dir)])

    if vcs_url:
        repo_list.extend(
            r for r in config if fnmatch.fnmatch(r.get("url", r.get("repo")), vcs_url)
        )

    if name:
        repo_list.extend([r for r in config if fnmatch.fnmatch(r.get("name"), name)])

    return repo_list


def is_config_file(filename: str, extensions: list[str] = [".yml", ".yaml", ".json"]):
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
