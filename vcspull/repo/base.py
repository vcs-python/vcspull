# -*- coding: utf-8 -*-
"""Base class for Repository objects.

vcspull.repo.base
~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

from __future__ import absolute_import, division, print_function, with_statement
import collections
import os
import sys
import logging
from ..util import mkdir_p, urlparse

logger = logging.getLogger(__name__)


class RepoLoggingAdapter(logging.LoggerAdapter):

    """Adapter for adding Repo related content to logger."""

    def process(self, msg, kwargs):
        """Return extra kwargs for :class:`Repo` prefixed with``repo_``.

        Both :class:`Repo` and :py:class:`logging.LogRecord` use ``name``.

        """

        prefixed_dict = {}
        for key, v in self.attributes.items():
            prefixed_dict['repo_' + key] = v

        kwargs["extra"] = prefixed_dict

        return msg, kwargs


class BaseRepo(collections.MutableMapping, RepoLoggingAdapter):

    """Base class for repositories.

    Extends :py:class:`collections.MutableMapping` and
    :py:class:`logging.LoggerAdapter`.

    """

    def __init__(self, attributes=None):
        self.attributes = dict(attributes) if attributes is not None else {}

        self['path'] = os.path.join(self['parent_path'], self['name'])

        # Register more schemes with urlparse for various version control
        # systems
        urlparse.uses_netloc.extend(self.schemes)
        # Python >= 2.7.4, 3.3 doesn't have uses_fragment
        if getattr(urlparse, 'uses_fragment', None):
            urlparse.uses_fragment.extend(self.schemes)

        RepoLoggingAdapter.__init__(self, logger, self.attributes)

    def check_destination(self, *args, **kwargs):
        """Assure destination path exists. If not, create directories."""
        if not os.path.exists(self['parent_path']):
            mkdir_p(self['parent_path'])
        else:
            if not os.path.exists(self['path']):
                self.info('Repo directory for %s (%s) does not exist @ %s' % (
                    self['name'], self['vcs'], self['path']))
                mkdir_p(self['path'])

        return True

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)

    def get_url_rev(self):
        """Return repo URL and revision by parsing :attr:`~.url`."""
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

    def __getitem__(self, key):
        return self.attributes[key]

    def __setitem__(self, key, value):
        self.attributes[key] = value
        self.dirty = True

    def __delitem__(self, key):
        del self.attributes[key]
        self.dirty = True

    def keys(self):
        """Return keys."""
        return self.attributes.keys()

    def __iter__(self):
        return self.attributes.__iter__()

    def __len__(self):
        return len(self.attributes.keys())
