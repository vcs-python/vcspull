# -*- coding: utf-8 -*-
"""Utility functions for vcspull.

vcspull.util
~~~~~~~~~~~~

"""
from __future__ import absolute_import, print_function, unicode_literals

import os

from libvcs._compat import PY2

if PY2:
    from collections import Mapping
else:
    from collections.abc import Mapping

CONFIG_DIR = os.path.expanduser('~/.vcspull/')  # remove dupes of this


def update_dict(d, u):
    """Return updated dict.

    Parameters
    ----------
    d : dict
    u : dict
    
    Returns
    -------
    dict :
        Updated dictionary

    Notes
    -----
    Thanks: http://stackoverflow.com/a/3233356
    """
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = update_dict(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d
