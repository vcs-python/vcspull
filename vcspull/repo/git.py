# -*- coding: utf-8 -*-
"""Git Repo object for vcspull.

vcspull.repo.git
~~~~~~~~~~~~~~~~

From https://github.com/saltstack/salt (Apache License):

- :py:meth:`~._git_ssh_helper`
- :py:meth:`~._git_run`
- :py:meth:`GitRepo.revision`
- :py:meth:`GitRepo.submodule`
- :py:meth:`GitRepo.remote`
- :py:meth:`GitRepo.remote_get`
- :py:meth:`GitRepo.remote_set`
- :py:meth:`GitRepo.fetch`
- :py:meth:`GitRepo.current_branch`
- :py:meth:`GitRepo.reset`

From pip (MIT Licnese):

- :py:meth:`GitRepo.get_url_rev`
- :py:meth:`GitRepo.get_url`
- :py:meth:`GitRepo.get_revision`

"""
from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import os
import logging
import tempfile
import subprocess

from .base import BaseRepo
from ..util import run
from .. import exc

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

    def __init__(self, url, **kwargs):

        BaseRepo.__init__(self, url, **kwargs)

        self['remotes'] = kwargs.get('remotes', [])

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

    def get_url(self, location):
        url = run(
            ['git', 'config', 'remote.origin.url'],
            show_stdout=False, cwd=location)
        return url.strip()

    def get_revision(self, location=None):

        if not location:
            location = self['path']

        current_rev = run(
            ['git', 'rev-parse', 'HEAD'], cwd=location)['stdout']
        return current_rev

    def get_refs(self, location):
        """Return map of named refs (branches or tags) to commit hashes."""
        output = run(
            ['git', 'show-ref'],
            show_stdout=False, cwd=location
        )
        rv = {}
        for line in output:
            commit, ref = line.split(' ', 1)
            ref = ref.strip()
            ref_name = None
            if ref.startswith('refs/remotes/'):
                ref_name = ref[len('refs/remotes/'):]
            elif ref.startswith('refs/heads/'):
                ref_name = ref[len('refs/heads/'):]
            elif ref.startswith('refs/tags/'):
                ref_name = ref[len('refs/tags/'):]
            if ref_name is not None:
                rv[ref_name] = commit.strip()
        return rv

    def obtain(self, quiet=False):
        """Retrieve the repository, clone if doesn't exist.

        :param quiet: Suppress stderr output.
        :type quiet: bool

        """
        self.check_destination()

        url, rev = self.get_url_rev()
        self.info('Cloning.')
        process = self.run(
            ['git', 'clone', '--progress', url, self['path']],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(), cwd=self['path'],
        )

        if self['remotes']:
            for r in self['remotes']:
                self.error('Adding remote %s <%s>' % (r['remote_name'], r['url']))
                self.remote_set(
                    name=r['remote_name'],
                    url=r['url']
                )

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.git')):

            self.run([
                'git', 'fetch'
            ], cwd=self['path'])

            p = self.run([
                'git', 'pull'
            ], cwd=self['path'])

            # if 'Already up-to-date' in proc['stdout']:
            #     self.info('Already up-to-date.')
            # else:
            #     if proc['stderr']:
            #         if 'You are not currently on a branch' in proc['stderr'][0]:
            #             self.info('Not on branch, Fetched.')
            #     else:
            #         self.info('\n'.join(proc['stdout']))
        else:
            self.obtain()
            self.update_repo()

    def current_branch(self, cwd=None, user=None):
        """Returns the current branch name, if on a branch.

        """
        if not cwd:
            cwd = self['path']
        cmd = r'git branch --list | grep "^*\ " | cut -d " " -f 2 | ' + \
            'grep -v "(detached"'

        return run(cmd, cwd=cwd, runas=user)

    def revision(self, cwd=None, rev='HEAD', short=False, user=None):
        """
        Returns the long hash of a given identifier (hash, branch, tag, HEAD, etc)

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

    def fetch(self, cwd=None, opts=None, user=None, identity=None):
        """Perform a fetch on the given repository.

        cwd
            The path to the Git repository

        opts : None
            Any additional options to add to the command line

        user : None
            Run git as a user other than what the minion runs as

        identity : None
            A path to a private key to use over SSH

        """

        if not cwd:
            cwd = self['path']

        if not opts:
            opts = ''
        cmd = 'git fetch {0}'.format(opts)

        return _git_run(cmd, cwd=cwd, runas=user, identity=identity)

    def submodule(self, cwd, init=True, opts=None, user=None, identity=None):
        """Initialize git submodules.

        cwd
            The path to the Git repository

        init : True
            Ensure that new submodules are initialized

        opts : None
            Any additional options to add to the command line

        user : None
            Run git as a user other than what the minion runs as

        identity : None
            A path to a private key to use over SSH

        """

        if not cwd:
            cwd = self['path']

        if not opts:
            opts = ''
        cmd = 'git submodule update {0} {1}'.format('--init' if init else '', opts)
        return _git_run(cmd, cwd=cwd, runas=user, identity=identity)

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

    def remote_set(self, cwd=None, name='origin', url=None, user=None):
        """Set remote with name and URL like git remote add <remote_name> <remote_url>.

        remote_name : origin
            defines the remote name

        remote_url : None
            defines the remote URL; should not be None!

        user : None
            Run git as a user other than what the minion runs as

        """
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
