# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

class VCSPullException(Exception):

    """Standard exception raised by libvcs."""

    pass


class MultipleConfigWarning(VCSPullException):
    message = (
        'Multiple configs found in home directory use only one.'
        ' .yaml, .json.'
    )