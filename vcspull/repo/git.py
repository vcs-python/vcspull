# -*- coding: utf-8 -*-
"""Git Repo object for vcspull.

vcspull.repo.git
~~~~~~~~~~~~~~~~

From https://github.com/saltstack/salt (Apache License):

- :py:meth:`~._git_ssh_helper`
- :py:meth:`~._git_run`
- :py:meth:`GitRepo.revision`
- :py:meth:`GitRepo.remote`
- :py:meth:`GitRepo.remote_get`
- :py:meth:`GitRepo.remote_set`
- :py:meth:`GitRepo.reset`

From pip (MIT Licnese):

- :py:meth:`GitRepo.get_url_rev`
- :py:meth:`GitRepo.get_url`
- :py:meth:`GitRepo.get_revision`

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import logging
import os
import re
import subprocess
import tempfile

from .. import exc
from .._compat import urlparse
from ..util import run
from .base import BaseRepo

logger = logging.getLogger(__name__)


def _git_ssh_helper(identity):
    """Return the path to a helper script which can be used in the GIT_SSH env.

    Returns the path to a helper script which can be used in the GIT_SSH env
    var to use a custom private key file.

    """
    opts = {
        'StrictHostKeyChecking': 'no',
        'PasswordAuthentication': 'no',
        'KbdInteractiveAuthentication': 'no',
        'ChallengeResponseAuthentication': 'no',
    }

    helper = tempfile.NamedTemporaryFile(delete=False)

    helper.writelines([
        '#!/bin/sh\n',
        'exec ssh {opts} -i {identity} $*\n'.format(
            opts=' '.join('-o%s=%s' % (key, value)
                          for key, value in opts.items()),
            identity=identity,
        )
    ])

    helper.close()

    os.chmod(helper.name, int('755', 8))

    return helper.name


def _git_run(cmd, cwd=None, runas=None, identity=None, **kwargs):
    """Throw an exception with error message on error return code.

    simple, throw an exception with the error message on an error return code.

    this function may be moved to the command module, spliced with
    'cmd.run_all', and used as an alternative to 'cmd.run_all'. Some
    commands don't return proper retcodes, so this can't replace 'cmd.run_all'.

    """
    env = {}

    if identity:
        helper = _git_ssh_helper(identity)

        env = {
            'GIT_SSH': helper
        }

    result = run(cmd,
                 cwd=cwd,
                 env=env,
                 **kwargs)

    if identity:
        os.unlink(helper)

    retcode = result['retcode']

    if retcode == 0:
        return result['stdout']
    else:
        raise exc.VCSPullException(result['stderr'])


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

        :param git_shallow: tell Git to clone with ``--depth 1`` (default False)
        :type git_shallow: bool

        :param git_submodules: Git submodules that shall be updated, all if empty
        :type git_submodules: list

        :param tls_verify: Should certificate for https be checked (default False)
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
        current_rev = run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=self['path']
        )

        return current_rev['stdout']

    def get_url_rev(self):
        """
        Prefixes stub URLs like 'user@hostname:user/repo.git' with 'ssh://'.
        That's required because although they use SSH they sometimes doesn't
        work with a ssh:// scheme (e.g. Github). But we need a scheme for
        parsing. Hence we remove it again afterwards and return it as a stub.
        """
        if '://' not in self['url']:
            assert 'file:' not in self['url']
            self.url = self.url.replace('git+', 'git+ssh://')
            url, rev = super(GitRepo, self).get_url_rev()
            url = url.replace('ssh://', '')
        elif 'github.com:' in self['url']:
            raise exc.VCSPullException(
                "Repo %s is malformatted, please use the convention %s for"
                "ssh / private GitHub repositories." % (
                    self['url'], "git+https://github.com/username/repo.git"
                )
            )
        else:
            url, rev = super(GitRepo, self).get_url_rev()

        return url, rev

    def obtain(self, quiet=False):
        """Retrieve the repository, clone if doesn't exist.

        :param quiet: Suppress stderr output.
        :type quiet: bool

        """
        self.check_destination()

        url, _ = self.get_url_rev()

        cmd = ['git', 'clone', '--progress']
        if self.attributes['git_shallow']:
            cmd.extend(['--depth', '1'])
        if self.attributes['tls_verify']:
            cmd.extend(['-c', 'http.sslVerify=false'])
        cmd.extend([url, self['path']])

        self.info('Cloning.')
        self.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(), cwd=self['path'],
        )

        if self['remotes']:
            for r in self['remotes']:
                self.error('Adding remote %s <%s>' %
                           (r['remote_name'], r['url']))
                self.remote_set(
                    name=r['remote_name'],
                    url=r['url']
                )

        self.info('Initializing submodules.')
        self.run(
            ['git', 'submodule', 'init'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(), cwd=self['path'],
        )
        cmd = ['git', 'submodule', 'update', '--recursive', '--init']
        cmd.extend(self.attributes['git_submodules'])
        self.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(), cwd=self['path'],
        )

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.git')):

            # Get requested revision or tag
            url, git_tag = self.get_url_rev()
            self.debug("git_tag: %s" % git_tag)

            self.info("Updating to '%s'." % git_tag)

            # Get head sha
            process = self.run([
                'git', 'rev-list', '--max-count=1', 'HEAD'
            ], cwd=self['path'], log_stdout=False)
            head_sha = process.stdout_data
            error_code = process.returncode
            self.debug("head_sha: %s" % head_sha)
            if error_code:
                self.error("Failed to get the hash for HEAD")
                return

            # If a remote ref is asked for, which can possibly move around,
            # we must always do a fetch and checkout.
            process = self.run([
                'git', 'show-ref', git_tag
            ], cwd=self['path'], log_stdout=False)
            show_ref_output = process.stdout_data
            self.debug("show_ref_output: %s" % show_ref_output)
            is_remote_ref = "remotes" in show_ref_output
            self.debug("is_remote_ref: %s" % is_remote_ref)

            # Tag is in the form <remote>/<tag> (i.e. origin/master) we must strip
            # the remote from the tag.
            git_remote_name = self.attributes['git_remote_name']
            if "refs/remotes/%s" % git_tag in show_ref_output:
                m = re.match(r'^(?P<git_remote_name>[^/]+)/(?P<git_tag>.+)$', show_ref_output)
                git_remote_name = m.group('git_remote_name')
                git_tag = m.group('git_tag')

            # This will fail if the tag does not exist (it probably has not been fetched
            # yet).
            process = self.run([
                'git', 'rev-list', '--max-count=1', git_tag
            ], cwd=self['path'], log_stdout=False)
            tag_sha = process.stdout_data
            error_code = process.returncode
            self.debug("tag_sha: %s" % tag_sha)

            # Is the hash checkout out what we want?
            if error_code or is_remote_ref or tag_sha != head_sha:
                process = self.run([
                    'git', 'fetch'
                ], cwd=self['path'])
                if process.returncode:
                    self.error("Failed to fetch repository '%s'" % url)
                    return

                if is_remote_ref:
                    # Check if stash is needed
                    process = self.run([
                        'git', 'status', '--porcelain'
                    ], cwd=self['path'])
                    if process.returncode:
                        self.error("Failed to get the status")
                        return
                    need_stash = len(process.stdout_data) > 0

                    # If not in clean state, stash changes in order to be able to be able to
                    # perform git pull --rebase
                    if need_stash:
                        git_stash_save_options = '--quiet' # If Git < 1.7.6, uses --quiet --all
                        process = self.run([
                            'git', 'stash', 'save', git_stash_save_options
                        ], cwd=self['path'])

                        if process.returncode:
                            self.error("Failed to stash changes")

                    # Pull changes from the remote branch
                    process = self.run([
                        'git', 'rebase', git_remote_name + '/' + git_tag
                    ], cwd=self['path'], log_stdout=False)
                    if process.returncode:
                        # Rebase failed: Restore previous state.
                        self.run([
                            'git', 'rebase', '--abort'
                        ], cwd=self['path'])
                        if need_stash:
                            self.run([
                                'git', 'stash', 'pop', '--index', '--quiet'
                            ], cwd=self['path'])

                        self.error("\nFailed to rebase in: '%s'.\nYou will have to resolve the conflicts manually" % self['path'])
                        return

                    if need_stash:
                        process = self.run([
                            'git', 'stash', 'pop', '--index', '--quiet'
                        ], cwd=self['path'])

                        if process.returncode:
                            # Stash pop --index failed: Try again dropping the index
                            self.run([
                                'git', 'reset', '--hard', '--quiet'
                            ], cwd=self['path'])
                            process = self.run([
                                'git', 'stash', 'pop', '--quiet'
                            ], cwd=self['path'])

                            if process.returncode:
                                # Stash pop failed: Restore previous state.
                                self.run([
                                    'git', 'reset', '--hard', '--quiet', head_sha
                                ], cwd=self['path'])
                                self.run([
                                    'git', 'stash', 'pop', '--index', '--quiet'
                                ], cwd=self['path'])
                                self.error("\nFailed to rebase in: '%s'.\n"
                                           "You will have to resolve the conflicts manually" % self['path'])
                                return

                else:
                    process = self.run([
                        'git', 'checkout', git_tag
                    ], cwd=self['path'])
                    if process.returncode:
                        self.error("Failed to checkout tag: '%s'" % git_tag)
                        return

                cmd = ['git', 'submodule', 'update', '--recursive', '--init']
                cmd.extend(self.attributes['git_submodules'])
                self.run(
                    cmd, cwd=self['path'],
                )
            else:
                self.info("Already up-to-date.")
        else:
            self.obtain()
            self.update_repo()

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

        if not cwd:
            cwd = self['path']

        cmd = 'git rev-parse {0}{1}'.format('--short ' if short else '', rev)
        return run(cmd, cwd, runas=user)

    def remotes_get(self, cwd=None, user=None):
        """Get remotes like git remote -v.

        cwd
            The path to the Git repository

        user : None
            Run git as a user other than what the minion runs as

        """

        if not cwd:
            cwd = self['path']

        cmd = ['git', 'remote']
        ret = run(cmd, cwd=cwd)['stdout']
        res = dict()
        for remote_name in ret:
            remote = remote_name.strip()
            res[remote] = self.remote_get(cwd, remote, user=user)
        return res

    def remote_get(self, cwd=None, remote='origin', user=None):
        """Get the fetch and push URL for a specified remote name.

        remote : origin
            the remote name used to define the fetch and push URL

        user : None
            Run git as a user other than what the minion runs as

        """

        if not cwd:
            cwd = self['path']

        try:
            cmd = 'git remote show -n {0}'.format(remote)
            ret = _git_run(cmd, cwd=cwd, runas=user)
            lines = ret
            remote_fetch_url = lines[1].replace('Fetch URL: ', '').strip()
            remote_push_url = lines[2].replace('Push  URL: ', '').strip()
            if remote_fetch_url != remote and remote_push_url != remote:
                res = (remote_fetch_url, remote_push_url)
                return res
            else:
                return None
        except exc.VCSPullException:
            return None

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

    def remote_set(self, cwd=None, name='origin', url=None, user=None):
        """Set remote with name and URL like git remote add <remote_name> <remote_url>.

        remote_name : origin
            defines the remote name

        remote_url : None
            defines the remote URL; should not be None!

        user : None
            Run git as a user other than what the minion runs as

        """

        url = self.chomp_protocol(url)

        if not cwd:
            cwd = self['path']
        if self.remote_get(cwd, name):
            cmd = 'git remote rm {0}'.format(name)
            _git_run(cmd, cwd=cwd, runas=user)
        cmd = 'git remote add {0} {1}'.format(name, url)

        _git_run(cmd, cwd=cwd, runas=user)
        return self.remote_get(cwd=cwd, remote=name, user=None)

    def reset(self, cwd=None, opts=None, user=None):
        """Reset the repository checkout.

        cwd
            The path to the Git repository

        opts : None
            Any additional options to add to the command line

        user : None
            Run git as a user other than what the minion runs as

        """

        if not cwd:
            cwd = self['path']

        if not opts:
            opts = ''
        return _git_run('git reset {0}'.format(opts), cwd=cwd, runas=user)
