# -*- coding: utf-8 -*-
"""Git Repo object for pullv.

pullv.repo.git
~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details. The following modules also are taken
    from https://github.com/saltstack/salt (Apache License):

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

"""

from .base import BaseRepo
import logging
import tempfile
from ..util import run
import os
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

    os.chmod(helper.name, 0755)

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
                 runas=runas,
                 env=env,
                 **kwargs)

    if identity:
        os.unlink(helper)

    retcode = result['retcode']

    if retcode == 0:
        return result['stdout']
    else:
        raise exceptions.CommandExecutionError(result['stderr'])



class GitRepo(BaseRepo):
    schemes = ('git')

    def __init__(self, arguments, *args, **kwargs):

        BaseRepo.__init__(self, arguments, *args, **kwargs)

    def get_revision(self):
        current_rev = run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=self['path']
        )

        return current_rev['stdout']


    def obtain(self):
        self.check_destination()
        import subprocess
        import sys

        url, rev = self.get_url_rev()
        self.info('Cloning')
        process = subprocess.Popen(
            ['git', 'clone', '--progress', url, self['path']],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(), cwd=self['path'],
        )
        while True:
            err = process.stderr.read(1)
            if err == '' and process.poll() is not None:
                break
            if err != '':
                sys.stderr.write(err)
                sys.stderr.flush()

        self.info('Cloned\n\t%s' % (process.stdout.read()))

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.git')):

            proc = run([
                'git', 'fetch'
            ], cwd=self['path'])

            proc = run([
                'git', 'pull'
            ], cwd=self['path'])

            if 'Already up-to-date' in proc['stdout'].strip():
                self.info('Already up-to-date.')
            else:
                self.info('Updated\n\t%s' % (proc['stdout']))
        else:
            self.obtain()
            self.update_repo()

    def current_branch(cwd, user=None):
        """
        Returns the current branch name, if on a branch.

        CLI Example:

        .. code-block:: bash

            salt '*' git.current_branch /path/to/repo
        """
        cmd = r'git branch --list | grep "^*\ " | cut -d " " -f 2 | ' + \
            'grep -v "(detached"'

        return run(cmd, cwd=cwd, runas=user)


    def revision(cwd, rev='HEAD', short=False, user=None):
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

        CLI Example:

        .. code-block:: bash

            salt '*' git.revision /path/to/repo mybranch
        """
        _check_git()

        cmd = 'git rev-parse {0}{1}'.format('--short ' if short else '', rev)
        return run(cmd, cwd, runas=user)

    def fetch(cwd, opts=None, user=None, identity=None):
        """
        Perform a fetch on the given repository

        cwd
            The path to the Git repository

        opts : None
            Any additional options to add to the command line

        user : None
            Run git as a user other than what the minion runs as

        identity : None
            A path to a private key to use over SSH

        CLI Example:

        .. code-block:: bash

            salt '*' git.fetch /path/to/repo '--all'

            salt '*' git.fetch cwd=/path/to/repo opts='--all' user=johnny
        """
        _check_git()

        if not opts:
            opts = ''
        cmd = 'git fetch {0}'.format(opts)

        return _git_run(cmd, cwd=cwd, runas=user, identity=identity)

    def submodule(cwd, init=True, opts=None, user=None, identity=None):
        """
        Initialize git submodules

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

        CLI Example:

        .. code-block:: bash

            salt '*' git.submodule /path/to/repo.git/sub/repo
        """
        _check_git()

        if not opts:
            opts = ''
        cmd = 'git submodule update {0} {1}'.format('--init' if init else '', opts)
        return _git_run(cmd, cwd=cwd, runas=user, identity=identity)

    def revision(cwd, rev='HEAD', short=False, user=None):
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

        CLI Example:

        .. code-block:: bash

            salt '*' git.revision /path/to/repo mybranch
        """
        _check_git()

        cmd = 'git rev-parse {0}{1}'.format('--short ' if short else '', rev)
        return _git_run(cmd, cwd, runas=user)

    def remote_get(cwd, remote='origin', user=None):
        """
        get the fetch and push URL for a specified remote name

        remote : origin
            the remote name used to define the fetch and push URL

        user : None
            Run git as a user other than what the minion runs as

        CLI Example:

        .. code-block:: bash

            salt '*' git.remote_get /path/to/repo
            salt '*' git.remote_get /path/to/repo upstream
        """
        try:
            cmd = 'git remote show -n {0}'.format(remote)
            ret = _git_run(cmd, cwd=cwd, runas=user)
            lines = ret.splitlines()
            remote_fetch_url = lines[1].replace('Fetch URL: ', '').strip()
            remote_push_url = lines[2].replace('Push  URL: ', '').strip()
            if remote_fetch_url != remote and remote_push_url != remote:
                res = (remote_fetch_url, remote_push_url)
                return res
            else:
                return None
        except exceptions.CommandExecutionError:
            return None

    def remote_set(cwd, name='origin', url=None, user=None):
        """
        sets a remote with name and URL like git remote add <remote_name> <remote_url>

        remote_name : origin
            defines the remote name

        remote_url : None
            defines the remote URL; should not be None!

        user : None
            Run git as a user other than what the minion runs as

        CLI Example:

        .. code-block:: bash

            salt '*' git.remote_set /path/to/repo remote_url=git@github.com:saltstack/salt.git
            salt '*' git.remote_set /path/to/repo origin git@github.com:saltstack/salt.git
        """
        if remote_get(cwd, name):
            cmd = 'git remote rm {0}'.format(name)
            _git_run(cmd, cwd=cwd, runas=user)
        cmd = 'git remote add {0} {1}'.format(name, url)
        _git_run(cmd, cwd=cwd, runas=user)
        return remote_get(cwd=cwd, remote=name, user=None)


    def reset(cwd, opts=None, user=None):
        """
        Reset the repository checkout

        cwd
            The path to the Git repository

        opts : None
            Any additional options to add to the command line

        user : None
            Run git as a user other than what the minion runs as

        CLI Example:

        .. code-block:: bash

            salt '*' git.reset /path/to/repo master
        """
        _check_git()

        if not opts:
            opts = ''
        return _git_run('git reset {0}'.format(opts), cwd=cwd, runas=user)
