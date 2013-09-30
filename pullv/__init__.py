#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv ~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""

__version__ = '0.1-dev'


import collections
import os
from pip.vcs.bazaar import Bazaar
from pip.vcs.git import Git
from pip.vcs.subversion import Subversion
from pip.vcs.mercurial import Mercurial

import util


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
        vcs_url = attributes['remote_location']
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


class GitRepo(Repo, Git):
    vcs = 'git'

    def __init__(self, arguments, *args, **kwargs):
        Repo.__init__(self, arguments, *args, **kwargs)
        super(Git, self).__init__(
            arguments.get('remote_location'), *args, **kwargs
        )

    def obtain(self, dest=None):
        dest = self['path'] if not dest else dest
        return Git.obtain(self, dest)

    def update_repo(self, dest=None, rev_options=[]):
        dest = self['path'] if not dest else dest
        return Git.update(self, dest, rev_options)


class MercurialRepo(Repo, Mercurial):
    vcs = 'hg'

    def __init__(self, arguments, *args, **kwargs):
        Repo.__init__(self, arguments, *args, **kwargs)
        super(Mercurial, self).__init__(
            arguments.get('remote_location'), *args, **kwargs
        )

    def obtain(self, dest=None):
        dest = self['path'] if not dest else dest
        return Mercurial.obtain(self, dest)

    def update_repo(self, dest=None, rev_options=[]):
        dest = self['path'] if not dest else dest
        return Mercurial.update(self, dest, rev_options)


class SubversionRepo(Repo, Subversion):
    vcs = 'svn'

    def __init__(self, arguments, *args, **kwargs):
        Repo.__init__(self, arguments, *args, **kwargs)
        super(Subversion, self).__init__(
            arguments.get('remote_location'), *args, **kwargs
        )

    def obtain(self, dest=None):
        dest = self['path'] if not dest else dest
        return Subversion.obtain(self, dest)

    def update_repo(self, dest=None):
        dest = self['path'] if not dest else dest
        from pip.vcs.subversion import get_rev_options
        url, rev = Subversion.get_url_rev(self)
        rev_options = get_rev_options(url, rev)
        return Subversion.update(self, dest, rev_options)


class Repos(BackboneCollection):

    """.find, .findWhere returns a ReposProxy class of filtered repos, these
    may be .update()'d.  make repos underscore.py compatible?

    """
    pass

import subprocess

import fnmatch
import os

def scan(dir):
    matches = []
    for root, dirnames, filenames in os.walk(dir):
        for filename in fnmatch.filter(filenames, '.git'):
            matches.append(os.path.join(root, filename))

def main():
    if not os.path.exists(os.path.expanduser('~/.pullv.yaml')) and \
        not os.path.exists(os.path.expanduser('~/.pullv.json')) and \
        not os.path.exists(os.path.expanduser('~/.pullv.ini')):
        print 'oh hi'

        # hi = subprocess.call([
            # 'find', '/', '-name', '".git"'
        # ])

        print 'No config found. I can help you.\n\n'

        print 'pullv scan -g'
        print '\tscan computer system for vcs repos'

        print 'pullv scan .'
        print '\t scan you current working directory recurisvely for repos'

        print 'by default, pullv scan will not seek sub-repos.'

        print 'pullv u [up, update]'

    else:
        print 'config file found'
