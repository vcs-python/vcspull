# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from libvcs import GitRepo, MercurialRepo, SubversionRepo


def create_repo_from_pip_url(url, **kwargs):
    r"""Return object with base class :class:`BaseRepo` depending on url.

    Return instance of :class:`libvcs.svn.SubversionRepo`,
    :class:`libvcs.git.GitRepo` or
    :class:`libvcs.hg.MercurialRepo`.
    The object returned is a child of :class:`libvcs.base.BaseRepo`.

    Usage Example::

        In [1]: from libvcs import create_repo_from_pip_url

        In [2]: r = create_repo_from_pip_url(url='git+https://www.github.com/you/myrepo',
                    parent_dir='/tmp/',
                    name='myrepo')

        In [3]: r.update_repo()
        |myrepo| (git)  Repo directory for myrepo (git) does not exist @ \
            /tmp/myrepo
        |myrepo| (git)  Cloning.
        |myrepo| (git)  git clone --progress https://www.github.com/tony/myrepo
            /tmp/myrepo
        Cloning into '/tmp/myrepo'...
        Checking connectivity... done.
        |myrepo| (git)  git fetch
        |myrepo| (git)  git pull
        Already up-to-date.
    """
    if url.startswith('git+'):
        if 'vcs' not in kwargs:
            kwargs['vcs'] = 'git'
        return GitRepo.from_pip_url(url, **kwargs)
    if url.startswith('hg+'):
        if 'vcs' not in kwargs:
            kwargs['vcs'] = 'hg'
        return MercurialRepo.from_pip_url(url, **kwargs)
    if url.startswith('svn+'):
        if 'vcs' not in kwargs:
            kwargs['vcs'] = 'svn'
        return SubversionRepo.from_pip_url(url, **kwargs)
    else:
        raise Exception(
            'repo URL %s requires a vcs scheme. Prepend hg+,'
            ' git+, svn+ to the repo URL. Examples:\n'
            '\t %s\n'
            '\t %s\n'
            '\t %s\n' % (
                url,
                'git+https://github.com/freebsd/freebsd.git',
                'hg+https://bitbucket.org/birkenfeld/sphinx',
                'svn+http://svn.code.sf.net/p/docutils/code/trunk'
            )
        )