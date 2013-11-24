#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Subversion object for pullv.

pullv.repo.svn
~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details.

The follow are from salt Apache license:

    - :py:meth:`SubversionRepo.get_revision_file`

The following are from pip MIT license:

    - :py:meth:`SubversionRepo.get_url_rev`
    - :py:meth:`SubversionRepo.get_url`
    - :py:meth:`SubversionRepo.get_revision`
    - :py:meth:`~.get_rev_options`

"""

import re
import os
import logging
import urlparse
from ..util import run
from .base import BaseRepo

logger = logging.getLogger(__name__)


class SubversionRepo(BaseRepo):
    vcs = 'svn'

    schemes = ('svn')

    def __init__(self, arguments, *args, **kwargs):
        BaseRepo.__init__(self, arguments, *args, **kwargs)

    def obtain(self):
        self.check_destination()

        url, rev = self.get_url_rev()
        rev_options = get_rev_options(url, rev)

        checkout = run([
            'svn', 'checkout', '-q', url, self['path'],
        ])
        self.info('Checked out\n\t%s', checkout['stdout'])

    def get_revision_file(self, location=None):
        """Return revision for a file."""

        if location:
            cwd = location
        else:
            cwd = self['path']

        current_rev = run(
            ['svn', 'info', cwd],
        )
        infos = current_rev['stdout']

        _INI_RE = re.compile(r"^([^:]+):\s+(\S.*)$", re.M)

        info_list = []
        for infosplit in infos.split('\n\n'):
            info_list.append(_INI_RE.findall(infosplit))

        return int([dict(tmp) for tmp in info_list][0]['Revision'])

    def get_location(self, dist, dependency_links):
        for url in dependency_links:
            egg_fragment = Link(url).egg_fragment
            if not egg_fragment:
                continue
            if '-' in egg_fragment:
                ## FIXME: will this work when a package has - in the name?
                key = '-'.join(egg_fragment.split('-')[:-1]).lower()
            else:
                key = egg_fragment
            if key == dist.key:
                return url.split('#', 1)[0]
        return None

    def get_revision(self, location=None):
        """
        Return the maximum revision for all files under a given location
        """

        if not location:
            location = self['url']

        if os.path.exists(location) and not os.path.isdir(location):
            return self.get_revision_file(location)

        # Note: taken from setuptools.command.egg_info
        revision = 0

        for base, dirs, files in os.walk(location):
            if '.svn' not in dirs:
                dirs[:] = []
                continue    # no sense walking uncontrolled subdirs
            dirs.remove('.svn')
            entries_fn = os.path.join(base, '.svn', 'entries')
            if not os.path.exists(entries_fn):
                ## FIXME: should we warn?
                continue

            dirurl, localrev = self._get_svn_url_rev(base)

            if base == location:
                base_url = dirurl + '/'   # save the root url
            elif not dirurl or not dirurl.startswith(base_url):
                dirs[:] = []
                continue    # not part of the same svn tree, skip it
            revision = max(revision, localrev)
        return revision

    def get_url_rev(self):
        # hotfix the URL scheme after removing svn+ from svn+ssh:// readd it
        url, rev = super(SubversionRepo, self).get_url_rev()
        if url.startswith('ssh://'):
            url = 'svn+' + url
        return url, rev

    def get_url(self, location=None):
        if not location:
            location = self['url']

        # In cases where the source is in a subdirectory, not alongside setup.py
        # we have to look up in the location until we find a real setup.py
        orig_location = location
        while not os.path.exists(os.path.join(location, 'setup.py')):
            last_location = location
            location = os.path.dirname(location)
            if location == last_location:
                # We've traversed up to the root of the filesystem without finding setup.py
                logger.warn("Could not find setup.py for directory %s (tried all parent directories)"
                            % orig_location)
                return None

        return self._get_svn_url_rev(location)[0]

    def _get_svn_url_rev(self, location):
        from pip.exceptions import InstallationError

        f = open(os.path.join(location, '.svn', 'entries'))
        data = f.read()
        f.close()
        if data.startswith('8') or data.startswith('9') or data.startswith('10'):
            data = list(map(str.splitlines, data.split('\n\x0c\n')))
            del data[0][0]  # get rid of the '8'
            url = data[0][3]
            revs = [int(d[9]) for d in data if len(d) > 9 and d[9]] + [0]
        elif data.startswith('<?xml'):
            match = _svn_xml_url_re.search(data)
            if not match:
                raise ValueError('Badly formatted data: %r' % data)
            url = match.group(1)    # get repository URL
            revs = [int(m.group(1)) for m in _svn_rev_re.finditer(data)] + [0]
        else:
            try:
                # subversion >= 1.7
                xml = run(['git', 'info', '--xml', location])['stdout']
                url = _svn_info_xml_url_re.search(xml).group(1)
                revs = [int(m.group(1)) for m in _svn_info_xml_rev_re.finditer(xml)]
            except InstallationError:
                url, revs = None, []

        if revs:
            rev = max(revs)
        else:
            rev = 0

        return url, rev

    def get_tag_revs(self, svn_tag_url):
        stdout = run(
            ['git', 'ls', '-v', svn_tag_url], show_stdout=False)
        results = []
        for line in stdout.splitlines():
            parts = line.split()
            rev = int(parts[0])
            tag = parts[-1].strip('/')
            results.append((tag, rev))
        return results

    def find_tag_match(self, rev, tag_revs):
        best_match_rev = None
        best_tag = None
        for tag, tag_rev in tag_revs:
            if (tag_rev > rev and
                (best_match_rev is None or best_match_rev > tag_rev)):
                # FIXME: Is best_match > tag_rev really possible?
                # or is it a sign something is wacky?
                best_match_rev = tag_rev
                best_tag = tag
        return best_tag

    def update_repo(self, dest=None):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.svn')):
            dest = self['path'] if not dest else dest

            url, rev = self.get_url_rev()
            proc = run(
                ['svn', 'update'],
                cwd=self['path']
            )

            self.info('Updated\n\t%s' % (proc['stdout']))
        else:
            self.obtain()
            self.update_repo()


def get_rev_options(url, rev):
    """Return revision options.

    from pip pip.vcs.subversion.

    """
    if rev:
        rev_options = ['-r', rev]
    else:
        rev_options = []

    r = urlparse.urlsplit(url)
    if hasattr(r, 'username'):
        # >= Python-2.5
        username, password = r.username, r.password
    else:
        netloc = r[1]
        if '@' in netloc:
            auth = netloc.split('@')[0]
            if ':' in auth:
                username, password = auth.split(':', 1)
            else:
                username, password = auth, None
        else:
            username, password = None, None

    if username:
        rev_options += ['--username', username]
    if password:
        rev_options += ['--password', password]
    return rev_options
