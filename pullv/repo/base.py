#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv.repo.base
    ~~~~~~~~~~~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""

from __future__ import absolute_import, division, print_function, with_statement
import collections
import os
import sys
import urlparse
from .. import util
from .. import log

import logging
logger = logging.getLogger(__name__)


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


class BaseRepo(BackboneModel):

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
                    self['name'], self['vcs'], self['path']))
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

    @property
    def prefixed_dict(self):
        prefixed_dict = {}
        for key, v in self.attributes.iteritems():
            prefixed_dict['repo_' + key] = v

        return prefixed_dict
