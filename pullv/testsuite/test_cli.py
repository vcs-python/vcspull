# -*- coding: utf-8 -*-
"""Tests for pullv.

pullv.tests.test_cli
~~~~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

import logging
import os
import tempfile
import kaptan
from pullv.repo import BaseRepo, Repo, GitRepo, MercurialRepo, SubversionRepo
from pullv.util import expand_config, run, get_repos
from .helpers import RepoTest

logger = logging.getLogger(__name__)


class ConfigLoadRepos(RepoTest):

    """Verify load_repos() load functionality."""

    def test_load_repos(self):
        """Load all repos from all configs."""
        self.maxDiff = None
