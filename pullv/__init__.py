#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv
    ~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""

from __future__ import absolute_import, division, print_function, with_statement
import collections
import os
import sys
import subprocess
import fnmatch
import logging
import urlparse
import re
import kaptan
from . import util
from . import log
from . import timed_subprocess

logger = logging.getLogger()

__version__ = '0.1-dev'


class BackboneCollection(collections.MutableSequence):

    '''emulate backbone collection
    '''
    def __init__(self, models=None):
        self.attributes = list(models) if models is None else []

    def __getitem__(self, index):
        return self.attributes[index]

    def __setitem__(self, index, value):
        self.attributes[index] = value

    def __delitem__(self, index):
        del self.attributes[index]

    def insert(self, index, value):
        self.attributes.insert(index, value)

    def __len__(self):
        return len(self.attributes)


class BackboneModel(collections.MutableMapping):

    '''emulate backbone model
    '''
    def __init__(self, attributes=None):
        self.attributes = dict(attributes) if attributes is not None else {}

    def __getitem__(self, key):
        return self.attributes[key]

    def __setitem__(self, key, value):
        self.attributes[key] = value
        self.dirty = True

    def __delitem__(self, key):
        del self.attributes[key]
        self.dirty = True

    def keys(self):
        return self.attributes.keys()

    def __iter__(self):
        return self.attributes.__iter__()

    def __len__(self):
        return len(self.attributes.keys())


class Repo(BackboneModel):

    def __new__(cls, attributes, *args, **kwargs):
        vcs_url = attributes['url']

        if vcs_url.startswith('git+'):
            return super(Repo, cls).__new__(GitRepo, attributes, *args, **kwargs)
        if vcs_url.startswith('hg+'):
            return super(Repo, cls).__new__(MercurialRepo, attributes, *args, **kwargs)
        if vcs_url.startswith('svn+'):
            return super(Repo, cls).__new__(SubversionRepo, attributes, *args, **kwargs)
        else:
            return super(Repo, cls).__new__(cls, attributes, *args, **kwargs)

    def __init__(self, attributes=None):
        self.attributes = dict(attributes) if attributes is not None else {}

        self['path'] = os.path.join(self['parent_path'], self['name'])

        # Register more schemes with urlparse for various version control
        # systems
        urlparse.uses_netloc.extend(self.schemes)
        # Python >= 2.7.4, 3.3 doesn't have uses_fragment
        if getattr(urlparse, 'uses_fragment', None):
            urlparse.uses_fragment.extend(self.schemes)

    def check_destination(self, *args, **kwargs):
        if not os.path.exists(self['parent_path']):
            os.mkdir(self['parent_path'])
        else:
            if not os.path.exists(self['path']):
                logger.info('Repo directory for %s (%s) does not exist @ %s' % (
                    self['name'], self.vcs, self['path']))
                os.mkdir(self['path'])

        return True

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)

    def get_url_rev(self):
        """
        Returns the correct repository URL and revision by parsing the given
        repository URL

        From pip
        """
        error_message = (
            "Sorry, '%s' is a malformed VCS url. "
            "The format is <vcs>+<protocol>://<url>, "
            "e.g. svn+http://myrepo/svn/MyApp#egg=MyApp")
        assert '+' in self['url'], error_message % self['url']
        url = self['url'].split('+', 1)[1]
        scheme, netloc, path, query, frag = urlparse.urlsplit(url)
        rev = None
        if '@' in path:
            path, rev = path.rsplit('@', 1)
        url = urlparse.urlunsplit((scheme, netloc, path, query, ''))
        return url, rev


class GitRepo(Repo):
    vcs = 'git'

    schemes = ('git')

    def __init__(self, arguments, *args, **kwargs):

        Repo.__init__(self, arguments, *args, **kwargs)

    def get_revision(self):
        current_rev = _run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=self['path']
        )

        return current_rev['stdout']

    def obtain(self):
        self.check_destination()

        url, rev = self.get_url_rev()
        proc = _run(
            ['git', 'clone', '-q', url, self['path']],
            env=os.environ.copy(), cwd=self['path']
        )

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.git')):
            _run([
                'git', 'fetch'
            ], cwd=self['path'])
            _run([
                'git', 'pull'
            ], cwd=self['path'])
        else:
            self.obtain()
            self.update_repo()


class MercurialRepo(Repo):
    vcs = 'hg'

    schemes = ('hg', 'hg+http', 'hg+https', 'hg+file')

    def __init__(self, arguments, *args, **kwargs):
        Repo.__init__(self, arguments, *args, **kwargs)

    def obtain(self):
        self.check_destination()

        url, rev = self.get_url_rev()

        _run([
            'hg', 'clone', '--noupdate', '-q', url, self['path']])

        _run([
            'hg', 'update', '-q', ], cwd=self['path'])

    def get_revision(self):
        current_rev = _run(
            ['hg', 'parents', '--template={rev}'],
            cwd=self['path'],
        )

        return current_rev['stdout']

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.hg')):
            _run([
                'hg', 'update'
            ], cwd=self['path'])
            _run([
                'hg', 'pull', '-u'
            ], cwd=self['path'])
        else:
            self.obtain()
            self.update_repo()


class SubversionRepo(Repo):
    vcs = 'svn'

    schemes = ('svn')

    def __init__(self, arguments, *args, **kwargs):
        Repo.__init__(self, arguments, *args, **kwargs)

    def obtain(self):
        self.check_destination()

        url, rev = self.get_url_rev()
        rev_options = self.get_rev_options(url, rev)

        _run([
            'svn', 'checkout', '-q', url, self['path'],
        ])

    def get_revision(self, location=None):

        if location:
            cwd = location
        else:
            cwd = self['path']

        current_rev = _run(
            ['svn', 'info', cwd],
        )
        infos = current_rev['stdout']

        _INI_RE = re.compile(r"^([^:]+):\s+(\S.*)$", re.M)

        info_list = []
        for infosplit in infos.split('\n\n'):
            info_list.append(_INI_RE.findall(infosplit))

        return int([dict(tmp) for tmp in info_list][0]['Revision'])

    def get_rev_options(self, url, rev):
        ''' from pip pip.vcs.subversion '''
        if rev:
            rev_options = ['-r', rev]
        else:
            rev_options = []

        r = urlparse.urlsplit(url)
        if hasattr(r, 'username'):
            # >= Python-2.5
            username, password = r.username, r.password
        else:
            netloc = r[1]
            if '@' in netloc:
                auth = netloc.split('@')[0]
                if ':' in auth:
                    username, password = auth.split(':', 1)
                else:
                    username, password = auth, None
            else:
                username, password = None, None

        if username:
            rev_options += ['--username', username]
        if password:
            rev_options += ['--password', password]
        return rev_options

    def update_repo(self, dest=None):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.svn')):
            dest = self['path'] if not dest else dest

            url, rev = self.get_url_rev()
            _run(
                ['svn', 'update'],
                cwd=self['path']
            )
        else:
            self.obtain()
            self.update_repo()


def scan(dir):
    matches = []
    for root, dirnames, filenames in os.walk(dir):
        for filename in fnmatch.filter(filenames, '.git'):
            matches.append(os.path.join(root, filename))


def _run(cmd,
         cwd=None,
         stdin=None,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         shell=False,
         env=(),
         timeout=None):
    ''' based off salt's _run '''
    ret = {}

    # kwargs['stdin'] = subprocess.PIPE if 'stdin' not in kwargs else
    # kwargs['stdin']

    kwargs = {
        'cwd': cwd,
        'stdin': stdin,
        'stdout': stdout,
        'stderr': stderr,
        'shell': shell,
        'env': os.environ.copy(),
    }

    try:
        proc = timed_subprocess.TimedProc(cmd, **kwargs)
    except (OSError, IOError) as exc:
        raise Error('Unable to urn command: {0}'.format(exc))

    try:
        proc.wait(timeout)
    except timed_subprocess.TimedProcTimeoutError as exc:
        ret['stdout'] = str(exc)
        ret['stderr'] = ''
        ret['pid'] = proc.process.pid
        ret['retcode'] = 1
        return ret

    out, err = proc.stdout, proc.stderr

    ret['stdout'] = out
    ret['stderr'] = err
    ret['pid'] = proc.process.pid
    ret['retcode'] = proc.process.returncode

    return ret


def main():
    yaml_config = os.path.expanduser('~/.pullv.yaml')
    has_yaml_config = os.path.exists(yaml_config)
    json_config = os.path.expanduser('~/.pullv.json')
    has_json_config = os.path.exists(json_config)
    ini_config = os.path.expanduser('~/.pullv.ini')
    has_ini_config = os.path.exists(ini_config)
    if not has_yaml_config and not has_json_config and not has_ini_config:
        logger.fatal('No config file found. Create a .pullv.{yaml,ini,conf}'
                     ' in your $HOME directory. http://pullv.rtfd.org for a'
                     ' quickstart.')
    else:
        if sum(filter(None, [has_ini_config, has_json_config, has_yaml_config])) > int(1):
            sys.exit(
                'multiple configs found in home directory use only one.'
                ' .yaml, .json, .ini.'
            )

        config = kaptan.Kaptan()
        config.import_config(yaml_config)

        log.enable_pretty_logging()

        logging.info('%r' % config.get())
        logging.info('%r' % util.expand_config(config.get()))
        logging.info('%r' % util.get_repos(util.expand_config(config.get())))

        for repo_dict in util.get_repos(util.expand_config(config.get())):
            r = Repo(repo_dict)
            logger.info('%s' % r)
            r.update_repo()
