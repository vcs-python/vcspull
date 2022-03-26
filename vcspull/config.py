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

from . import exc
from .util import get_config_dir

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
    filetype: list[Literal["json", "yaml"]] = ["json", "yaml"],
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


def load_configs(files: list[Union[str, pathlib.Path]]):
    """Return repos from a list of files.

    Parameters
    ----------
    files : list
        paths to config file

    Returns
    -------
    list of dict :
        config dict item

    Todo
    ----
    Validate scheme, check for duplicate destinations, VCS urls
    """
    repos = {}
    for f in files:
        if isinstance(f, str):
            f = pathlib.Path(f)
        ext = f.suffix.lstrip(".")

        _, ext = os.path.splitext(f)
        conf = kaptan.Kaptan(handler=ext.lstrip(".")).import_config(f).export("dict")

        newrepos = {}

        for path, repo in conf.items():
            newrepos[expand_dir(path)] = repo

        dupes = detect_duplicate_repos(repos, newrepos)

        if dupes:
            msg = ("repos for the same parent_dir and repo_name detected!", dupes)
            raise exc.VCSPullException(msg)

        repos |= newrepos

    return repos


def detect_duplicate_repos(config1, config2):
    """Return duplicate repos dict if repo_dir is the same

    Parameters
    ----------
    config1 : dict
        config dict

    config2 : dict
        config dict

    Returns
    -------
    list of dict, or None
        Duplicate repos
    """
    if not config1:
        return None

    dupes = []

    for parent_path, repos in config2.items():
        if parent_path in config1:
            for name, repo in repos.items():
                if name in config1[parent_path]:
                    dupes += (repo, config1[parent_path][name])

    return dupes


def get_repo_dirs(config):
    """return a dict of repo paths with their corresponding repos for each repo
    in the config list.

    Parameters
    ----------
    config: dict
        list of repos

    Returns
    -------
    dict
    """
    path_repos = {}
    for parent_dir, repos in config.items():
        for name, repo in repos.items():
            path_repos[os.path.join(parent_dir, name)] = repo

    return path_repos


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


def filter_repos(config, filter_repo_dir=None, filter_name=None):
    """Return a :py:obj:`list` list of repos from config file.

    dir, vcs_url and name all support fnmatch.

    Parameters
    ----------
    config : dict
        the repo config in :py:class:`dict` format.
    filter_repo_dir : str, Optional
        directory of checkout location, fnmatch pattern supported
    filter_name : str, Optional
        project name, fnmatch pattern supported

    Returns
    -------
    list :
        Repos
    """
    matched_repos = {}

    if filter_repo_dir:
        for path, repos in config.items():
            if fnmatch.fnmatch(path, filter_repo_dir):
                matched_repos[filter_repo_dir] = repos

    if filter_name:
        for path, repos in config.items():
            for name, repo in repos.items():
                if fnmatch.fnmatch(name, filter_name):
                    matched_repos[path] = {filter_name: repo}

    return matched_repos


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
