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

- :py:meth:`GitRepo.get_url_and_revision`
- :py:meth:`GitRepo.get_url`
- :py:meth:`GitRepo.get_revision`

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import logging
import os
import re
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
    env = os.environ.copy()

    if identity:
        helper = _git_ssh_helper(identity)

        env.update({
            'GIT_SSH': helper
        })

    result = run(cmd, cwd=cwd, env=env, **kwargs)

    if identity:
        os.unlink(helper)

    return result


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
        current_rev = self.run(
            ['git', 'rev-parse', 'HEAD'], stream_stderr=False
        )

        return current_rev

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
        self.run(cmd)

        if self['remotes']:
            for r in self['remotes']:
                self.error('Adding remote %s <%s>' %
                           (r['remote_name'], r['url']))
                self.remote_set(
                    name=r['remote_name'],
                    url=r['url']
                )

        self.info('Initializing submodules.')
        self.run(['git', 'submodule', 'init'],)
        cmd = ['git', 'submodule', 'update', '--recursive', '--init']
        cmd.extend(self.attributes['git_submodules'])
        self.run(cmd,)

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
            if symref.stdout_data:
                git_tag = symref.stdout_data.rstrip()
            else:
                git_tag = 'origin/master'
        self.debug("git_tag: %s" % git_tag)

        self.info("Updating to '%s'." % git_tag)

        # Get head sha
        process = self.run([
            'git', 'rev-list', '--max-count=1', 'HEAD'
        ], log_stdout=False)
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
        ], log_stdout=False)
        show_ref_output = process.stdout_data
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
        process = self.run([
            'git', 'rev-list', '--max-count=1', git_tag
        ], log_stdout=False)
        tag_sha = process.stdout_data
        error_code = process.returncode
        self.debug("tag_sha: %s" % tag_sha)

        # Is the hash checkout out what we want?
        somethings_up = (error_code, is_remote_ref, tag_sha != head_sha,)
        if all(not x for x in somethings_up):
            self.info("Already up-to-date.")
            return

        process = self.run(['git', 'fetch'])
        if process.returncode:
            self.error("Failed to fetch repository '%s'" % url)
            return

        if is_remote_ref:
            # Check if stash is needed
            process = self.run(['git', 'status', '--porcelain'])
            if process.returncode:
                self.error("Failed to get the status")
                return
            need_stash = len(process.stdout_data) > 0

            # If not in clean state, stash changes in order to be able
            # to be able to perform git pull --rebase
            if need_stash:
                # If Git < 1.7.6, uses --quiet --all
                git_stash_save_options = '--quiet'
                process = self.run([
                    'git', 'stash', 'save', git_stash_save_options
                ])

                if process.returncode:
                    self.error("Failed to stash changes")

            # Pull changes from the remote branch
            process = self.run([
                'git', 'rebase', git_remote_name + '/' + git_tag
            ], log_stdout=False)
            if process.returncode:
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
                process = self.run([
                    'git', 'stash', 'pop', '--index', '--quiet'
                ])

                if process.returncode:
                    # Stash pop --index failed: Try again dropping the
                    # index
                    self.run(['git', 'reset', '--hard', '--quiet'])
                    process = self.run(['git', 'stash', 'pop', '--quiet'])

                    if process.returncode:
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
            process = self.run(['git', 'checkout', git_tag])
            if process.returncode:
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

    def remotes_get(self, cwd=None, user=None):
        """Get remotes like git remote -v.

        cwd
            The path to the Git repository

        user : None
            Run git as a user other than what the minion runs as

        """
        remotes = {}

        if not cwd:
            cwd = self['path']

        cmd = self.run(['git', 'remote'], cwd=cwd)
        ret = filter(None, cmd.stdout_data.split('\n'))

        for remote_name in ret:
            remotes[remote_name] = self.remote_get(cwd, remote_name)
        return remotes

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
            lines = ret.split('\n')
            print(lines)
            remote_fetch_url = lines[1].replace('Fetch URL: ', '').strip()
            remote_push_url = lines[2].replace('Push  URL: ', '').strip()
            if remote_fetch_url != remote and remote_push_url != remote:
                res = (remote_fetch_url, remote_push_url)
                return res
            else:
                return None
        except exc.VCSPullException:
            return None

    def remote_set(self, url, cwd=None, name='origin'):
        """Set remote with name and URL like git remote add.

        :param url: defines the remote URL
        :type url: string
        :param name: defines the remote name.
        :type name: str
        """

        url = self.chomp_protocol(url)

        if not cwd:
            cwd = self['path']
        if self.remote_get(cwd, name):
            self.run(['git', 'remote', 'rm', 'name'])

        self.run(['git', 'remote', 'add', name, url])
        return self.remote_get(cwd=cwd, remote=name)

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
        return _git_run('git reset {0}'.format(opts), cwd=cwd)
