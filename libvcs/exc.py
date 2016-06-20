# -*- coding: utf-8 -*-
"""Exceptions for vcspull.

libvcs.exc
~~~~~~~~~~

"""
from __future__ import absolute_import, print_function, unicode_literals

from subprocess import CalledProcessError


class LibVCSException(Exception):

    """Standard exception raised by libvcs."""

    pass


class SubprocessError(LibVCSException, CalledProcessError):
    """This exception is raised on non-zero Base.run, util.run return codes."""

    def __init__(self, returncode, cmd, output):
        CalledProcessError.__init__(self,
                                    returncode=returncode,
                                    cmd=cmd,
                                    output=output)

    def __str__(self):
        return "Command '%s' returned non-zero exit status %d: \n%s" % (
            self.cmd, self.returncode, self.output)