"""Utility functions for vcspull.

vcspull.util
~~~~~~~~~~~~

"""
import os
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
