# -*- coding: utf-8 -*-
"""For accessing vcspull as a package.

vcspull
~~~~~~~

"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import os
import sys


def run():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, base)
    import vcspull.cli

if __name__ == '__main__':
    exit = run()
    if exit:
        sys.exit(exit)
