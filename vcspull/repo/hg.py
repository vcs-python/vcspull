# -*- coding: utf-8 -*-
"""Mercurial Repo object for vcspull.

vcspull.repo.hg
~~~~~~~~~~~~~~~

The following is from pypa/pip (MIT license):

- :py:meth:`MercurialRepo.get_url_and_revision`
- :py:meth:`MercurialRepo.get_url`
- :py:meth:`MercurialRepo.get_revision`

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import logging
import os

from .base import BaseRepo

logger = logging.getLogger(__name__)


class MercurialRepo(BaseRepo):

    schemes = ('hg', 'hg+http', 'hg+https', 'hg+file')

    def __init__(self, url, **kwargs):
        BaseRepo.__init__(self, url, **kwargs)

    def obtain(self):
        self.check_destination()

        url, rev = self.get_url_and_revision()

        self.run(['hg', 'clone', '--noupdate', '-q', url, self['path']])
        self.run(['hg', 'update', '-q'])

    def get_revision(self):
        return self.run(
            ['hg', 'parents', '--template={rev}'], stream_stderr=False)

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.hg')):
            self.run(['hg', 'update'],)
            self.run(['hg', 'pull', '-u'])

        else:
            self.obtain()
            self.update_repo()
