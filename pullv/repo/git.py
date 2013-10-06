#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv.repo.git
    ~~~~~~~~~~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""

from .base import BaseRepo
import logging
from ..util import run
import os
logger = logging.getLogger(__name__)


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
