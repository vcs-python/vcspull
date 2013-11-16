#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    import unittest2 as unittest
except ImportError:  # Python 2.7
    import unittest
import os
import sys
import logging
import argparse
logging.disable(logging.CRITICAL)


pullv_path = sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
if pullv_path not in sys.path:
    sys.path.insert(0, pullv_path)


def main(verbosity=2, failfast=False):
    """Run TestSuite for pullv. Exit with code 0 if success."""

    suites = unittest.TestLoader().discover('pullv.testsuite', pattern="test_*.py")
    result = unittest.TextTestRunner(
        verbosity=verbosity, failfast=failfast).run(suites)
    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='''\
        Run tests suite for pullv. With no arguments, runs all test suites in pullv.testsuite.

        Default usage:
            $ ./run_tests.py
        ''',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--tests',
        nargs='*',
        default=None,
        help='''\
        Test individual, TestCase or TestSuites, or multiple. Example for test_config TestSuite:

        by TestSuite (module):
            $ ./run_tests.py test_config

        by TestCase:
            $ ./run_tests.py test_config.ImportExportTest
        individual tests:
            $ ./run_tests.py test_config.ImportExportTest.test_export_json

        Multiple can be separated by spaces:
            $ ./run_tests.py test_config.ImportExportTest.test_export_json \\
                test_config.ImportExportTest.test_window

        ./run_tests will automatically assume the package namespace ``pullv.testsuite``.

            $ ./run_tests.py test_config.ImportExportTest

        is the same as:

            $ ./run_tests.py pullv.testsuite.test_config.ImportExportTest
        '''
    )
    parser.add_argument('-l', '--log-level', dest='log_level', default='INFO',
                        help='Log level')
    parser.add_argument(
        '-v', '--verbosity', dest='verbosity', type=int, default=2,
        help='unittest verbosity level')
    parser.add_argument(
        '-F', '--failfast', dest='failfast', action='store_true',

        help='Stop on first test failure. failfast=True')
    args = parser.parse_args()

    verbosity = args.verbosity

    import logging
    logging.getLogger('pullv.testsuite').setLevel(args.log_level.upper())

    if 'help' in args:
        parser.print_help()
    if args.tests and len(args.tests) > int(0):
        for arg in args.tests:
            if not arg.startswith('pullv.testsuite'):
                loc = args.tests.index(arg)
                args.tests[loc] = 'pullv.testsuite.%s' % arg
        suites = unittest.TestLoader().loadTestsFromNames(args.tests)
        result = unittest.TextTestRunner(
            verbosity=verbosity, failfast=args.failfast).run(suites)
    else:
        main(verbosity=verbosity, failfast=args.failfast)
