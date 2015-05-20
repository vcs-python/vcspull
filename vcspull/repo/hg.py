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

import re
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

        clone = self.run([
            'hg', 'clone', '--noupdate', '-q', url, self['path']])

        update = self.run([
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

    def get_tag_revs(self, location=None):
        if not location:
            location = self['path']

        tags = run(
            ['git', 'tags'], cwd=location)
        tag_revs = []
        for line in tags.splitlines():
            tags_match = re.search(r'([\w\d\.-]+)\s*([\d]+):.*$', line)
            if tags_match:
                tag = tags_match.group(1)
                rev = tags_match.group(2)
                if "tip" != tag:
                    tag_revs.append((rev.strip(), tag.strip()))
        return dict(tag_revs)

    def get_branch_revs(self, location=None):

        if not location:
            location = self['path']

        branches = run(
            ['git', 'branches'], cwd=location)
        branch_revs = []
        for line in branches.splitlines():
            branches_match = re.search(r'([\w\d\.-]+)\s*([\d]+):.*$', line)
            if branches_match:
                branch = branches_match.group(1)
                rev = branches_match.group(2)
                if "default" != branch:
                    branch_revs.append((rev.strip(), branch.strip()))
        return dict(branch_revs)

    def get_revision(self, location=None):
        if not location:
            location = self['path']

        current_revision = run(
            ['git', 'parents', '--template={rev}'],
            cwd=location)['stdout']
        return current_revision

    def get_revision_hash(self, location=None):
        if not location:
            location = self['path']

        current_rev_hash = run(
            ['git', 'parents', '--template={node}'],
            cwd=location)['stdout'].strip()
        return current_rev_hash

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.hg')):

            process = self.run(
                ['hg', 'update'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(), cwd=self['path']
            )

            process = self.run(
                ['hg', 'pull', '-u'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(), cwd=self['path']
            )

        else:
            self.obtain()
            self.update_repo()
