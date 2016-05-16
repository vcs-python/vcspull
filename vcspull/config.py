# -*- coding: utf-8 -*-
"""Config utility functions for vcspull.

vcspull.config
~~~~~~~~~~~~~~

A lot of these items are todo.

"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import glob
import logging
import os

import kaptan

from . import exc
from ._compat import string_types
from .util import update_dict

log = logging.getLogger(__name__)


def in_dir(
    config_dir=os.path.expanduser('~/.vcspull'),
    extensions=['.yml', '.yaml', '.json']
):
    """Return a list of configs in ``config_dir``.

    :param config_dir: directory to search
    :type config_dir: string
    :param extensions: filetypes to check (e.g. ``['.yaml', '.json']``).
    :type extensions: list
    :rtype: list

    """
    configs = []

    for filename in os.listdir(config_dir):
        if is_config_file(filename, extensions) and \
           not filename.startswith('.'):
            configs.append(filename)

    return configs


def expand_dir(_dir):
    """Return path with environmental variables and tilde ~ expanded.

    :param dir:
    :type dir: string
    :rtype; string
    """
    return os.path.expanduser(os.path.expandvars(_dir))


def expand_config(config):
    """Return expanded configuration.

    end-user configuration permit inline configuration shortcuts, expand to
    identical format for parsing.

    :param config: the repo config in :py:class:`dict` format.
    :type config: dict
    :rtype: list

    """
    configs = []
    for directory, repos in config.items():
        for repo, repo_data in repos.items():

            conf = {}

            '''
            repo_name: http://myrepo.com/repo.git

            to

            repo_name: { url: 'http://myrepo.com/repo.git' }

            also assures the repo is a :py:class:`dict`.
            '''

            if isinstance(repo_data, string_types):
                conf['url'] = expand_dir(repo_data)
            else:
                conf = update_dict(conf, repo_data)

            '''
            ``shell_command_after``: if str, turn to list.
            '''
            if 'shell_command_after' in conf:
                if isinstance(conf['shell_command_after'], string_types):
                    conf['shell_command_after'] = [
                        conf['shell_command_after']
                    ]

            if 'name' not in conf:
                conf['name'] = repo
            if 'parent_dir' not in conf:
                conf['parent_dir'] = expand_dir(directory)
            if 'repo_dir' not in conf:
                conf['repo_dir'] = expand_dir(
                    os.path.join(conf['parent_dir'], conf['name'])
                )
            if 'remotes' in conf:
                remotes = []
                for remote_name, url in conf['remotes'].items():
                    remotes.append({
                        'remote_name': remote_name,
                        'url': url
                    })
                conf['remotes'] = sorted(
                    remotes, key=lambda x: sorted(x.get('remote_name'))
                )
            configs.append(conf)

    return configs


def is_config_file(filename, extensions=['.yml', '.yaml', '.json']):
    """Return True if file has a valid config file type.

    :param filename: filename to check (e.g. ``mysession.json``).
    :type filename: string
    :param extensions: filetypes to check (e.g. ``['.yaml', '.json']``).
    :type extensions: list or string
    :rtype: bool

    """
    extensions = [extensions] if isinstance(
        extensions, string_types) else extensions
    return any(filename.endswith(e) for e in extensions)


def find_home_config_files(filetype=['json', 'yaml']):
    """Return configs of ``.vcspull.{yaml,json}`` in user's home directory."""
    configs = []

    yaml_config = os.path.expanduser('~/.vcspull.yaml')
    has_yaml_config = os.path.exists(yaml_config)
    json_config = os.path.expanduser('~/.vcspull.json')
    has_json_config = os.path.exists(json_config)

    if not has_yaml_config and not has_json_config:
        log.debug(
            'No config file found. Create a .vcspull.yaml or .vcspull.json'
            ' in your $HOME directory. http://vcspull.rtfd.org for a'
            ' quickstart.'
        )
    else:
        if sum(filter(None, [has_json_config, has_yaml_config])) > int(1):
            raise exc.MultipleRootConfigs(
                'multiple configs found in home directory use only one.'
                ' .yaml, .json.'
            )
        if has_yaml_config:
            configs.append(yaml_config)
        if has_json_config:
            configs.append(json_config)

    return configs


def find_config_files(
    path=['~/.vcspull'],
    match=['*'],
    filetype=['json', 'yaml'],
    include_home=False
):
    """Return repos from a directory and match. Not recursive.

    :param path: list of paths to search
    :type path: list
    :param match: list of globs to search against
    :type match: list
    :param filetype: list of filetypes to search against
    :type filetype: list
    :param include_home: Include home configuration files
    :type include_home: bool
    :raises:
        - LoadConfigRepoConflict: There are two configs that have same path
          and name with different repo urls.
        - NoConfigsFound: No configs found in home directory or ~/.vcspull
          directory.
    :returns: list of absolute paths to config files.
    :rtype: list

    """
    configs = []

    if include_home is True:
        configs.extend(find_home_config_files())

    if isinstance(path, list):
        for p in path:
            configs.extend(find_config_files(p, match, filetype))
            return configs
    else:
        path = os.path.expanduser(path)
        if isinstance(match, list):
            for m in match:
                configs.extend(find_config_files(path, m, filetype))
        else:
            if isinstance(filetype, list):
                for f in filetype:
                    configs.extend(find_config_files(path, match, f))
            else:
                match = os.path.join(path, match)
                match += ".{filetype}".format(filetype=filetype)

                configs = glob.glob(match)

    return configs


def load_configs(configs):
    """Return repos from a directory and fnmatch. Not recursive.

    :todo: Validate scheme, check for duplciate destinations, VCS urls

    :param configs: paths to config file
    :type path: list
    :returns: expanded config dict item
    :rtype: list of dict

    """
    configlist = []
    for config in configs:
        fName, fExt = os.path.splitext(config)
        conf = kaptan.Kaptan(handler=fExt.lstrip('.'))
        conf.import_config(config)

        newconfigs = expand_config(conf.export('dict'))

        if not configlist:
            configlist.extend(newconfigs)
            continue

        dupes = find_dupes(configlist, newconfigs)

        if dupes:
            msg = (
                'repos with same path + different VCS detected!', dupes
            )
            raise Exception(msg)
        configlist.extend(newconfigs)

    return configlist


def find_dupes(repos1, repos2):
    """Return duplicate repos dict if repo_dir same and vcs different.

    :param repos1: list of repo expanded dicts
    :type repos1: list of :py:dict
    :param repos2: list of repo expanded dicts
    :type repos2: list of :py:dict
    :rtype: list of dicts or None
    :returns: Duplicate lists
    """
    dupes = []
    path_dupe_repos = []

    curpaths = [r['repo_dir'] for r in repos1]
    newpaths = [r['repo_dir'] for r in repos2]
    path_duplicates = list(set(curpaths).intersection(newpaths))

    if not path_duplicates:
        return None

    path_dupe_repos.extend(
        [r for r in repos2 if
            any(r['repo_dir'] == p for p in path_duplicates)]
    )

    if not path_dupe_repos:
        return None

    for n in path_dupe_repos:
        currepo = next(
            (r for r in repos1
                if r['repo_dir'] == n['repo_dir']), None
        )
        if n['url'] != currepo['url']:
            dupes += (n, currepo,)
    return dupes
