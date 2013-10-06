#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv.repo.hg
    ~~~~~~~~~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""


from .base import BaseRepo
import logging
from ..util import _run
import os
logger = logging.getLogger(__name__)


class MercurialRepo(BaseRepo):

    schemes = ('hg', 'hg+http', 'hg+https', 'hg+file')

    def __init__(self, arguments, *args, **kwargs):
        BaseRepo.__init__(self, arguments, *args, **kwargs)

    def obtain(self):
        self.check_destination()

        url, rev = self.get_url_rev()

        clone = _run([
            'hg', 'clone', '--noupdate', '-q', url, self['path']])

        self.info('Cloned\n\t%s' % clone['stdout'])
        update = _run([
            'hg', 'update', '-q'
        ], cwd=self['path'])
        self.info('Updated\n\t%s' % update['stdout'])

    def get_revision(self):
        current_rev = _run(
            ['hg', 'parents', '--template={rev}'],
            cwd=self['path'],
        )

        return current_rev['stdout']

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.hg')):
            _run([
                'hg', 'update'
            ], cwd=self['path'])
            _run([
                'hg', 'pull', '-u'
            ], cwd=self['path'])
        else:
            self.obtain()
            self.update_repo()
