# -*- coding: utf-8 -*-
"""Git Repo object for vcspull.

vcspull.repo.git
~~~~~~~~~~~~~~~~

From https://github.com/saltstack/salt (Apache License):

- :py:meth:`GitRepo.revision`
- :py:meth:`GitRepo.remote`
- :py:meth:`GitRepo.remote_get`
- :py:meth:`GitRepo.remote_set`
- :py:meth:`GitRepo.reset`

From pip (MIT Licnese):

- :py:meth:`GitRepo.get_url_and_revision` (get_url_rev)
- :py:meth:`GitRepo.get_url`
- :py:meth:`GitRepo.get_revision`

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import logging
import os
import re

from .. import exc
from .._compat import urlparse
from ..util import run
from .base import BaseRepo

logger = logging.getLogger(__name__)


class GitRepo(BaseRepo):
    schemes = ('git')

    def __init__(self, url, remotes=None, **kwargs):
        """A git repository.

        :param url: URL in pip vcs format:

            - ``git+https://github.com/tony/vcspull.git``
            - ``git+ssh://git@github.com:tony/vcspull.git``
        :type url: str

        :param remotes: list of remotes in dict format::

            [{
            "remote_name": "myremote",
            "url": "https://github.com/tony/vim-config.git"
            }]
        :type remotes: list

        :param git_remote_name: name of the remote (default "origin")
        :type git_remote_name: str

        :param git_shallow: clone with ``--depth 1`` (default False)
        :type git_shallow: bool

        :param git_submodules: Git submodules that shall be updated, all if
            empty
        :type git_submodules: list

        :param tls_verify: Should certificate for https be checked (default
            False)
        :type tls_verify: bool
        """
        if 'git_remote_name' not in kwargs:
            kwargs['git_remote_name'] = "origin"
        if 'git_shallow' not in kwargs:
            kwargs['git_shallow'] = False
        if 'git_submodules' not in kwargs:
            kwargs['git_submodules'] = []
        if 'tls_verify' not in kwargs:
            kwargs['tls_verify'] = False
        BaseRepo.__init__(self, url, **kwargs)

        self['remotes'] = remotes

    def get_revision(self):
        """Return current revision. Initial repositories return 'initial'."""
        try:
            return self.run(['git', 'rev-parse', '--verify', 'HEAD'])
        except exc.VCSPullSubprocessException:
            return 'initial'

    def get_url_and_revision(self):
        """
        Prefixes stub URLs like 'user@hostname:user/repo.git' with 'ssh://'.
        That's required because although they use SSH they sometimes doesn't
        work with a ssh:// scheme (e.g. Github). But we need a scheme for
        parsing. Hence we remove it again afterwards and return it as a stub.
        """
        self.debug("get_url_and_revision for %s" % self['url'])
        if '://' not in self['url']:
            assert 'file:' not in self['url']
            self.url = self.url.replace('git+', 'git+ssh://')
            url, rev = super(GitRepo, self).get_url_and_revision()
            url = url.replace('ssh://', '')
        elif 'github.com:' in self['url']:
            raise exc.VCSPullException(
                "Repo %s is malformatted, please use the convention %s for"
                "ssh / private GitHub repositories." % (
                    self['url'], "git+https://github.com/username/repo.git"
                )
            )
        else:
            url, rev = super(GitRepo, self).get_url_and_revision()

        return url, rev

    def obtain(self, quiet=False):
        """Retrieve the repository, clone if doesn't exist.

        :param quiet: Suppress stderr output.
        :type quiet: bool

        """
        self.check_destination()

        url, _ = self.get_url_and_revision()

        cmd = ['git', 'clone', '--progress']
        if self.attributes['git_shallow']:
            cmd.extend(['--depth', '1'])
        if self.attributes['tls_verify']:
            cmd.extend(['-c', 'http.sslVerify=false'])
        cmd.extend([url, self['path']])

        self.info('Cloning.')
        self.run_buffered(cmd)

        if self['remotes']:
            for r in self['remotes']:
                self.error('Adding remote %s <%s>' %
                           (r['remote_name'], r['url']))
                self.remote_set(
                    name=r['remote_name'],
                    url=r['url']
                )

        self.info('Initializing submodules.')
        self.run_buffered(['git', 'submodule', 'init'],)
        cmd = ['git', 'submodule', 'update', '--recursive', '--init']
        cmd.extend(self.attributes['git_submodules'])
        self.run_buffered(cmd)

    def update_repo(self):
        self.check_destination()

        if not os.path.isdir(os.path.join(self['path'], '.git')):
            self.obtain()
            self.update_repo()
            return

        # Get requested revision or tag
        url, git_tag = self.get_url_and_revision()
        if not git_tag:
            self.debug("No git revision set, defaulting to origin/master")
            symref = self.run(['git', 'symbolic-ref', '--short', 'HEAD'])
            if symref:
                git_tag = symref.rstrip()
            else:
                git_tag = 'origin/master'
        self.debug("git_tag: %s" % git_tag)

        self.info("Updating to '%s'." % git_tag)

        # Get head sha
        try:
            head_sha = self.run([
                'git', 'rev-list', '--max-count=1', 'HEAD'
            ], print_stdout_on_progress_end=False)
        except exc.VCSPullSubprocessException as e:
            self.error("Failed to get the hash for HEAD")
            return

        self.debug("head_sha: %s" % head_sha)

        # If a remote ref is asked for, which can possibly move around,
        # we must always do a fetch and checkout.
        show_ref_output = self.run([
            'git', 'show-ref', git_tag
        ], print_stdout_on_progress_end=False)
        self.debug("show_ref_output: %s" % show_ref_output)
        is_remote_ref = "remotes" in show_ref_output
        self.debug("is_remote_ref: %s" % is_remote_ref)

        # Tag is in the form <remote>/<tag> (i.e. origin/master) we must
        # strip the remote from the tag.
        git_remote_name = self.attributes['git_remote_name']
        if "refs/remotes/%s" % git_tag in show_ref_output:
            m = re.match(r'^(?P<git_remote_name>[^/]+)/(?P<git_tag>.+)$',
                         show_ref_output)
            git_remote_name = m.group('git_remote_name')
            git_tag = m.group('git_tag')

        # This will fail if the tag does not exist (it probably has not
        # been fetched yet).
        try:
            error_code = 0
            tag_sha = self.run([
                'git', 'rev-list', '--max-count=1', git_tag
            ], print_stdout_on_progress_end=False)
        except exc.VCSPullSubprocessException as e:
            error_code = e.subprocess.returncode
        self.debug("tag_sha: %s" % tag_sha)

        # Is the hash checkout out what we want?
        somethings_up = (error_code, is_remote_ref, tag_sha != head_sha,)
        if all(not x for x in somethings_up):
            self.info("Already up-to-date.")
            return

        process = self.run_buffered(['git', 'fetch'])
        if process.returncode:
            self.error("Failed to fetch repository '%s'" % url)
            return

        if is_remote_ref:
            # Check if stash is needed
            try:
                process = self.run(['git', 'status', '--porcelain'])
            except exc.VCSPullSubprocessException as e:
                self.error("Failed to get the status")
                return
            need_stash = len(process.stdout_data) > 0

            # If not in clean state, stash changes in order to be able
            # to be able to perform git pull --rebase
            if need_stash:
                # If Git < 1.7.6, uses --quiet --all
                git_stash_save_options = '--quiet'
                try:
                    process = self.run([
                        'git', 'stash', 'save', git_stash_save_options
                    ])
                except exc.VCSPullSubprocessException as e:
                    self.error("Failed to stash changes")

            # Pull changes from the remote branch
            try:
                process = self.run([
                    'git', 'rebase', git_remote_name + '/' + git_tag
                ], print_stdout_on_progress_end=False)
            except exc.VCSPullSubprocessException as e:
                # Rebase failed: Restore previous state.
                self.run(['git', 'rebase', '--abort'])
                if need_stash:
                    self.run(['git', 'stash', 'pop', '--index', '--quiet'])

                self.error(
                    "\nFailed to rebase in: '%s'.\n"
                    "You will have to resolve the conflicts manually" %
                    self['path'])
                return

            if need_stash:
                try:
                    process = self.run([
                        'git', 'stash', 'pop', '--index', '--quiet'
                    ])
                except exc.VCSPullSubprocessException as e:
                    # Stash pop --index failed: Try again dropping the
                    # index
                    self.run(['git', 'reset', '--hard', '--quiet'])
                    try:
                        process = self.run(['git', 'stash', 'pop', '--quiet'])
                    except exc.VCSPullSubprocessException as e:
                        # Stash pop failed: Restore previous state.
                        self.run(
                            ['git', 'reset', '--hard', '--quiet', head_sha]
                        )
                        self.run(['git', 'stash', 'pop', '--index', '--quiet'])
                        self.error("\nFailed to rebase in: '%s'.\n"
                                   "You will have to resolve the "
                                   "conflicts manually" % self['path'])
                        return

        else:
            try:
                process = self.run(['git', 'checkout', git_tag])
            except exc.VCSPullSubprocessException as e:
                self.error("Failed to checkout tag: '%s'" % git_tag)
                return

        cmd = ['git', 'submodule', 'update', '--recursive', '--init']
        cmd.extend(self.attributes['git_submodules'])
        self.run(cmd)

    def revision(self, cwd=None, rev='HEAD', short=False, user=None):
        """
        Return long ref of a given identifier (ref, branch, tag, HEAD, etc)

        cwd
            The path to the Git repository

        rev: HEAD
            The revision

        short: False
            Return an abbreviated SHA1 git hash

        user : None
            Run git as a user other than what the minion runs as

        """

        cmd = 'git rev-parse {0}{1}'.format('--short ' if short else '', rev)
        return run(cmd, cwd, runas=user)

    @property
    def remotes_get(self):
        """Return remotes like git remote -v.

        :rtype: dict of tuples
        """
        remotes = {}

        cmd = self.run(['git', 'remote'])
        ret = filter(None, cmd.split('\n'))

        for remote_name in ret:
            remotes[remote_name] = self.remote_get(remote_name)
        return remotes

    def remote_get(self, remote='origin'):
        """Get the fetch and push URL for a specified remote name.

        :param remote: the remote name used to define the fetch and push URL
        :type remote: str
        :returns: remote name and url in tuple form
        :rtype: tuple
        """
        try:
            ret = self.run(['git', 'remote', 'show', '-n', remote])
            lines = ret.split('\n')
            remote_fetch_url = lines[1].replace('Fetch URL: ', '').strip()
            remote_push_url = lines[2].replace('Push  URL: ', '').strip()
            if remote_fetch_url != remote and remote_push_url != remote:
                res = (remote_fetch_url, remote_push_url)
                return res
            else:
                return None
        except exc.VCSPullException:
            return None

    def remote_set(self, url, name='origin'):
        """Set remote with name and URL like git remote add.

        :param url: defines the remote URL
        :type url: string
        :param name: defines the remote name.
        :type name: str
        """

        url = self.chomp_protocol(url)

        if self.remote_get(name):
            self.run(['git', 'remote', 'rm', 'name'])

        self.run(['git', 'remote', 'add', name, url])
        return self.remote_get(remote=name)

    @staticmethod
    def chomp_protocol(url):
        """Return clean VCS url from RFC-style url

        :param url: url
        :type url: string
        :return type: string
        :returns: url as VCS software would accept it
        :seealso: #14
        """
        if '+' in url:
            url = url.split('+', 1)[1]
        scheme, netloc, path, query, frag = urlparse.urlsplit(url)
        rev = None
        if '@' in path:
            path, rev = path.rsplit('@', 1)
        url = urlparse.urlunsplit((scheme, netloc, path, query, ''))
        if url.startswith('ssh://git@github.com/'):
            url = url.replace('ssh://', 'git+ssh://')
        elif '://' not in url:
            assert 'file:' not in url
            url = url.replace('git+', 'git+ssh://')
            url = url.replace('ssh://', '')
        return url

    def reset(self, cwd=None, opts=None):
        """Reset the repository checkout.

        :param cwd: The path to the Git repository
        :type cwd: string
        :param opts: Any additional options to add to the command line
        :type opts: string
        """

        if not cwd:
            cwd = self['path']

        if not opts:
            opts = ''
        return self.run(['git', 'reset', opts])
