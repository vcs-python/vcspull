# -*- coding: utf-8 -*-
"""For accessing vcspull as a package.

vcspull
~~~~~~~

"""

from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import sys
import os


def run():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, base)
    import vcspull
    vcspull.cli.main()

if __name__ == '__main__':
    exit = run()
    if exit:
        sys.exit(exit)
