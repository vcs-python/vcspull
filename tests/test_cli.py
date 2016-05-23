# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function,
                        with_statement)

import unittest

from click.testing import CliRunner

from vcspull.cli import cli


class Cli(unittest.TestCase):

    @unittest.skip('Implement later')
    def test_hi(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['up', 'hi'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Debug mode is on', result.output)
        self.assertIn('Syncing', result.output)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Cli))
    return suite
