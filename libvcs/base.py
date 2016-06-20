# -*- coding: utf-8 -*-
"""Base class for Repository objects.

libvcs.base
~~~~~~~~~~~

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import subprocess
import sys

from . import exc
from ._compat import console_to_str, text_type, urlparse
from .util import mkdir_p, run

logger = logging.getLogger(__name__)


class RepoLoggingAdapter(logging.LoggerAdapter):

    """Adapter for adding Repo related content to logger."""

    def __init__(self, *args, **kwargs):
        self.indent = 0
        self.in_progress = None
        self.in_progress_hanging = False

        logging.LoggerAdapter.__init__(self, *args, **kwargs)

    def _show_progress(self):
        """Should we display download progress."""
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
                # Erase any messages shown with show_progress (besides .'s)
                self.show_progress('')
                self.show_progress('')
                sys.stdout.write(msg)
                sys.stdout.flush()
        self.in_progress = None
        self.in_progress_hanging = False

    def show_progress(self, message=None):
        """If in progress scope with no log messages shown yet, append '.'."""
        if self.in_progress_hanging:
            if message is None:
                # sys.stdout.write('.')
                sys.stdout.flush()
            else:
                if self.last_message:
                    padding = ' ' * max(
                        0, len(self.last_message) - len(message)
                    )
                else:
                    padding = ''
                sys.stdout.write(
                    '\r%s%s%s' %
                    (' ' * self.indent, message, padding)
                )
                sys.stdout.flush()
                self.last_message = message


class BaseRepo(RepoLoggingAdapter, object):

    """Base class for repositories.

    Extends and :py:class:`logging.LoggerAdapter`.
    """

    def __init__(self, url, parent_dir, *args, **kwargs):
        self.__dict__.update(kwargs)
        self.url = url
        self.parent_dir = parent_dir

        self.path = os.path.join(self.parent_dir, self.name)

        # Register more schemes with urlparse for various version control
        # systems
        urlparse.uses_netloc.extend(self.schemes)
        # Python >= 2.7.4, 3.3 doesn't have uses_fragment
        if getattr(urlparse, 'uses_fragment', None):
            urlparse.uses_fragment.extend(self.schemes)

        RepoLoggingAdapter.__init__(self, logger, {})

    @classmethod
    def from_pip_url(cls, *args, **kwargs):
        self = cls(*args, **kwargs)
        url, rev = self.get_url_and_revision_from_pip_url()
        if url:
            self.url = url
        self.rev = rev if rev else None
        return self

    def run_buffered(
        self, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=os.environ.copy(), cwd=None, print_stdout_on_progress_end=False,
        *args, **kwargs
    ):
        """Run command with stderr directly to buffer, for CLI usage.

        This method will also prefix the VCS command bin_name.

        This is meant for buffering the raw progress of git/hg/etc. to CLI
        when it is processing.

        :param cwd: dir command is run from, defaults :path:`~.path`.
        :type cwd: string
        :param print_stdout_on_progress_end: print final (non-buffered) stdout
            message to buffer in cases like git pull, this would be
            'Already up to date.'
            You will also have this stdout information in ``.stdout_data``
            of the return object.
        :type print_stdout_on_progress_end: bool
        :returns: subprocess instance ``.stdout_data`` attached.
        :rtype: :class:`Subprocess.Popen`
        """
        if cwd is None:
            cwd = getattr(self, 'path', None)

        cmd = [self.bin_name] + cmd

        process = subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr,
            env=env, cwd=cwd
        )

        self.start_progress(' '.join(cmd))
        while True:
            err = console_to_str(process.stderr.read(128))
            if err == '' and process.poll() is not None:
                break
            elif 'ERROR' in err:
                raise exc.LibVCSException(
                    err + console_to_str(process.stderr.read())
                )
            else:
                self.show_progress("%s" % err)

        process.stdout_data = console_to_str(process.stdout.read())
        self.end_progress(
            '%s' % process.stdout_data if print_stdout_on_progress_end else '')

        process.stderr.close()
        process.stdout.close()
        return process

    def run(
        self, cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=os.environ.copy(), cwd=None, *args, **kwargs
    ):
        """Return combined stderr/stdout from a command.

        This method will also prefix the VCS command bin_name.
        By default runs using the cwd :attr:`~.path` of the repo.

        :param cwd: dir command is run from, defaults :attr:`~.path`.
        :type cwd: string
        :returns: combined stdout/stderr in a big string, \n's retained
        :rtype: str
        """

        if cwd is None:
            cwd = getattr(self, 'path', None)

        cmd = [self.bin_name] + cmd

        return run(
            cmd,
            stdout=stdout,
            stderr=stderr,
            env=env, cwd=cwd,
            *args, **kwargs
        )

    def check_destination(self, *args, **kwargs):
        """Assure destination path exists. If not, create directories."""
        if not os.path.exists(self.parent_dir):
            mkdir_p(self.parent_dir)
        else:
            if not os.path.exists(self.path):
                self.debug('Repo directory for %s (%s) does not exist @ %s' % (
                    self.name, self.vcs, self.path))
                mkdir_p(self.path)

        return True

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)

    def get_url_and_revision_from_pip_url(self):
        """Return repo URL and revision by parsing :attr:`~.url`."""
        error_message = (
            "Sorry, '%s' is a malformed VCS url. "
            "The format is <vcs>+<protocol>://<url>, "
            "e.g. svn+http://myrepo/svn/MyApp#egg=MyApp")
        assert '+' in self.url, error_message % self.url
        url = self.url.split('+', 1)[1]
        scheme, netloc, path, query, frag = urlparse.urlsplit(url)
        rev = None
        if '@' in path:
            path, rev = path.rsplit('@', 1)
        url = urlparse.urlunsplit((scheme, netloc, path, query, ''))
        return url, rev
