# -*- coding: utf-8 -*-
"""Exceptions for vcspull.

vcspull.exc
~~~~~~~~~~~

"""

from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals


class VCSPullException(Exception):

    """Standard VCSPullException."""

    pass


class NoConfigsFound(VCSPullException):
    message = (
        'No config file found. Create a .vcspull.yaml or .vcspull.json'
        ' in your $HOME directory. http://vcspull.rtfd.org for a'
        ' quickstart.'
    )

class MultipleRootConfigs(VCSPullException):
    message = (
        'Multiple configs found in home directory use only one.'
        ' .yaml, .json.'
    )
