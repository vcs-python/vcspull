# -*- coding: utf-8 -*-
"""Tests for vcspull.

vcspull.testsuite
~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

from .. import log
import logging
logger = logging.getLogger()


if not logger.handlers:
    channel = logging.StreamHandler()
    channel.setFormatter(log.DebugLogFormatter())
    logger.addHandler(channel)
    logger.setLevel('INFO')

    # enable DEBUG message if channel is at testsuite + testsuite.* packages.
    testsuite_logger = logging.getLogger(__name__)

    testsuite_logger.setLevel('INFO')


def suite():
    """Return TestSuite."""
    try:
        import unittest2 as unittest
    except ImportError:  # Python 2.7
        import unittest

    return unittest.TestLoader().discover('.', pattern="test_*.py")
