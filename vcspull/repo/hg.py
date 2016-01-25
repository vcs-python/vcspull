# -*- coding: utf-8 -*-
"""Mercurial Repo object for vcspull.

vcspull.repo.hg
~~~~~~~~~~~~~~~

The following is from pypa/pip (MIT license):

- :py:meth:`MercurialRepo.get_url_rev`
- :py:meth:`MercurialRepo.get_url`
- :py:meth:`MercurialRepo.get_revision`

"""
from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import subprocess
import os
import logging

from .base import BaseRepo
from ..util import run

logger = logging.getLogger(__name__)


class MercurialRepo(BaseRepo):

    schemes = ('hg', 'hg+http', 'hg+https', 'hg+file')

    def __init__(self, url, **kwargs):
        BaseRepo.__init__(self, url, **kwargs)

    def obtain(self):
        self.check_destination()

        url, rev = self.get_url_rev()

        self.run([
            'hg', 'clone', '--noupdate', '-q', url, self['path']])

        self.run([
            'hg', 'update', '-q'
        ], cwd=self['path'])

    def get_revision(self):
        current_rev = run(
            ['hg', 'parents', '--template={rev}'],
            cwd=self['path'],
        )

        return current_rev['stdout']

    def get_url(self, location=None):
        if not location:
            location = self['path']

        url = run(
            ['git', 'showconfig', 'paths.default'],
            cwd=location)['stdout'].strip()
        if self._is_local_repository(url):
            url = path_to_url(url)
        return url.strip()

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.hg')):

            process = self.run(
                ['hg', 'update'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(), cwd=self['path']
            )

            self.run(
                ['hg', 'pull', '-u'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(), cwd=self['path']
            )

        else:
            self.obtain()
            self.update_repo()
