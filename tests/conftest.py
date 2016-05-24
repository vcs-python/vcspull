# -*- coding: utf-8 -*-
import pytest


@pytest.fixture
def tmpdir_repoparent(tmpdir_factory, scope='function'):
    """Return temporary directory for repository checkout guaranteed unique."""
    fn = tmpdir_factory.mktemp("repo")
    return fn
