# -*- coding: utf-8 -*-
"""Config utility functions for vcspull.

vcspull.config
~~~~~~~~~~~~~~

A lot of these items are todo.

"""

from __future__ import (
    absolute_import, division, print_function, with_statement, unicode_literals
)

import os
import fnmatch
import glob
import logging

import kaptan

from . import exc
from .util import update_dict
from ._compat import string_types

log = logging.getLogger(__name__)


def get_repos(config, dirmatch=None, repomatch=None, namematch=None):
    """Return a :py:obj:`list` list of repos from (expanded) config file.

    :param config: the expanded repo config in :py:class:`dict` format.
    :type config: dict
    :param dirmatch: array of fnmatch's for directory
    :type dirmatch: str or None
    :param repomatch: array of fnmatch's for vcs url
    :type repomatch: str or None
    :param namematch: array of fnmatch's for project name
    :type namematch: str or None
    :rtype: list
    :todo: optimize performance, tests.

    """
    repo_list = []
    for directory, repos in config.items():
        for repo, repo_data in repos.items():
            if dirmatch and not fnmatch.fnmatch(directory, dirmatch):
                continue
            if repomatch and not fnmatch.fnmatch(repo_data['repo'], repomatch):
                continue
            if namematch and not fnmatch.fnmatch(repo, namematch):
                continue
            repo_dict = {
                'name': repo,
                'cwd': directory,
                'url': repo_data['repo'],
            }

            if 'remotes' in repo_data:
                repo_dict['remotes'] = []
                for remote_name, url in repo_data['remotes'].items():
                    remote_dict = {
                        'remote_name': remote_name,
                        'url': url
                    }
                    repo_dict['remotes'].append(remote_dict)
            repo_list.append(repo_dict)
    return repo_list


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


def expand_config(config):
    """Return expanded configuration.

    end-user configuration permit inline configuration shortcuts, expand to
    identical format for parsing.

    :param config: the repo config in :py:class:`dict` format.
    :type config: dict
    :rtype: dict

    """
    for directory, repos in config.items():
        for repo, repo_data in repos.items():

            '''
            repo_name: http://myrepo.com/repo.git

            to

            repo_name: { repo: 'http://myrepo.com/repo.git' }

            also assures the repo is a :py:class:`dict`.
            '''

            if isinstance(repo_data, string_types):
                config[directory][repo] = {'repo': repo_data}

            '''
            ``shell_command_after``: if str, turn to list.
            '''
            if 'shell_command_after' in repo_data:
                if isinstance(repo_data['shell_command_after'], string_types):
                    repo_data['shell_command_after'] = [
                        repo_data['shell_command_after']
                    ]

    config = dict(
        (os.path.expandvars(directory), repo_data) for directory, repo_data in config.items()
    )

    config = dict(
        (os.path.expanduser(directory), repo_data) for directory, repo_data in config.items()
    )

    return config


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


def find_home_configs(filetype=['json', 'yaml']):
    """Return configs of ``.vcspull.{yaml,json}`` in user's home directory.

    """

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


def find_configs(
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
        configs.extend(find_home_configs())

    if isinstance(path, list):
        for p in path:
            configs.extend(find_configs(p, match, filetype))
            return configs
    else:
        path = os.path.expanduser(path)
        if isinstance(match, list):
            for m in match:
                configs.extend(find_configs(path, m, filetype))
        else:
            if isinstance(filetype, list):
                for f in filetype:
                    configs.extend(find_configs(path, match, f))
            else:
                match = os.path.join(path, match)
                match += ".{filetype}".format(filetype=filetype)

                configs = glob.glob(match)

    return configs


def load_configs(configs):
    """Return repos from a directory and fnmatch. Not recursive.

    :param configs: paths to config file
    :type path: list
    :returns: expanded config dict item
    :rtype: iter(dict)

    """

    configdict = {}

    for config in configs:
        fName, fExt = os.path.splitext(config)
        conf = kaptan.Kaptan(handler=fExt.lstrip('.'))
        conf.import_config(config)

        newconfigdict = expand_config(conf.export('dict'))

        if configdict:
            for path in newconfigdict:
                if path in configdict:
                    for repo_name in newconfigdict[path]:
                        if repo_name in configdict[path]:
                            if newconfigdict[path][repo_name] != configdict[path][repo_name]:
                                print('same path + repo for %s' % repo_name)
                                if newconfigdict[path][repo_name]['repo'] != configdict[path][repo_name]['repo']:
                                    msg = (
                                        'same path + repo, different vcs (%s)\n'
                                        '%s\n%s' %
                                        (
                                            repo_name,
                                            configdict[path][repo_name]['repo'],
                                            newconfigdict[path][repo_name]['repo']
                                        )
                                    )
                                    raise Exception(msg)
        configdict = update_dict(configdict, newconfigdict)
        # configdict.update(conf.export('dict'))

    # if configs load and validate_schema, then load.
    # configs = [config for config in configs if validate_schema(config)]

    configdict = expand_config(configdict)

    return configdict


def scan_repos(
    path='~',
    subrepos=False
):
    """Return repositories within directory.

    :param path: path to search
    :type path: string
    :param subrepos: search for repos within repos
    :type subrepos: bool
    :returns: list of Repos from file system
    :rtype: iter(:class:`Repo`)

    """
    pass


def validate_schema(conf):
    """Return True if valid vcspull schema.

    :param conf: configuration
    :type conf: string
    :rtype: bool

    """

    return True
