# -*- coding: utf-8 -*-
"""Base class for Repository objects.

vcspull.repo.base
~~~~~~~~~~~~~~~~~

"""
from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import collections
import os
import sys
import subprocess
import logging

from .. import exc
from ..util import mkdir_p
from .._compat import urlparse, text_type, console_to_str

logger = logging.getLogger(__name__)


class RepoLoggingAdapter(logging.LoggerAdapter):

    """Adapter for adding Repo related content to logger."""

    def __init__(self, *args, **kwargs):
        self.indent = 0
        self.in_progress = None
        self.in_progress_hanging = False

        logging.LoggerAdapter.__init__(self, *args, **kwargs)

    def process(self, msg, kwargs):
        """Return extra kwargs for :class:`Repo` prefixed with``repo_``.

        Both :class:`Repo` and :py:class:`logging.LogRecord` use ``name``.

        """

        prefixed_dict = {}
        for key, v in self.attributes.items():
            prefixed_dict['repo_' + key] = v

        kwargs["extra"] = prefixed_dict

        return msg, kwargs

    def _show_progress(self):
        """Should we display download progress?"""
        return sys.stdout.isatty()

    def start_progress(self, msg=True):
        assert not self.in_progress, (
            "Tried to start_progress(%r) while in_progress %r"
            % (msg, self.in_progress))
        if self._show_progress():
            if msg and isinstance(msg, text_type):
                self.info(' ' * self.indent + msg)
            sys.stdout.flush()
            self.in_progress_hanging = True
        else:
            self.in_progress_hanging = False
        self.in_progress = msg
        self.last_message = None

    def end_progress(self, msg='done.'):
        assert self.in_progress, (
            "Tried to end_progress without start_progress")
        if self._show_progress():
            if not self.in_progress_hanging and isinstance(msg, text_type):
                # Some message has been printed out since start_progress
                sys.stdout.write('...' + self.in_progress + msg + '\n')
                sys.stdout.flush()
            else:
                # These erase any messages shown with show_progress (besides .'s)
                self.show_progress('')
                self.show_progress('')
                sys.stdout.write(msg)
                #sys.stdout.write(msg + '\n')
                sys.stdout.flush()
        self.in_progress = None
        self.in_progress_hanging = False

    def show_progress(self, message=None):
        """If we are in a progress scope, and no log messages have been
        shown, write out another '.'"""
        if self.in_progress_hanging:
            if message is None:
                # sys.stdout.write('.')
                sys.stdout.flush()
            else:
                if self.last_message:
                    padding = ' ' * max(0, len(self.last_message) - len(message))
                else:
                    padding = ''
                sys.stdout.write('\r%s%s%s' %
                                (' ' * self.indent, message, padding))
                sys.stdout.flush()
                self.last_message = message


class BaseRepo(collections.MutableMapping, RepoLoggingAdapter):

    """Base class for repositories.

    Extends :py:class:`collections.MutableMapping` and
    :py:class:`logging.LoggerAdapter`.

    """

    def __init__(self, url, cwd, *args, **kwargs):
        self.attributes = kwargs
        self.attributes['url'] = url
        self.attributes['cwd'] = cwd

        self['path'] = os.path.join(self['cwd'], self['name'])

        # Register more schemes with urlparse for various version control
        # systems
        urlparse.uses_netloc.extend(self.schemes)
        # Python >= 2.7.4, 3.3 doesn't have uses_fragment
        if getattr(urlparse, 'uses_fragment', None):
            urlparse.uses_fragment.extend(self.schemes)

        RepoLoggingAdapter.__init__(self, logger, self.attributes)

    def run(
        self, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=os.environ.copy(), cwd=None, stream_stderr=True, *args, **kwargs
    ):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(), cwd=cwd
        )

        if stream_stderr:
            self.start_progress(' '.join(cmd))
            while True:

                err = console_to_str(process.stderr.read(128))
                if err == '' and process.poll() is not None:
                    break
                elif 'ERROR' in err:
                    raise exc.VCSPullException(err + console_to_str(process.stderr.read()))
                if err != '':
                    self.show_progress("%s" % err)

            self.end_progress('%s' % (console_to_str(process.stdout.read())))
        else:
            self.info('%s' % (process.stdout.read()))

        return process


    def check_destination(self, *args, **kwargs):
        """Assure destination path exists. If not, create directories."""
        if not os.path.exists(self['cwd']):
            mkdir_p(self['cwd'])
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
