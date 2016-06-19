# -*- coding: utf-8 -*-
"""Exceptions for vcspull.

vcspull.exc
~~~~~~~~~~~

"""
from __future__ import absolute_import, print_function, unicode_literals

from subprocess import CalledProcessError


class VCSPullException(Exception):

    """Standard VCSPullException."""

    pass


class VCSPullSubprocessException(VCSPullException, CalledProcessError):
    """This exception is raised on non-zero Base.run, util.run return codes."""

    def __init__(self, returncode, cmd, output):
        CalledProcessError.__init__(self,
                                    returncode=returncode,
                                    cmd=cmd,
                                    output=output)

    def __str__(self):
        return "Command '%s' returned non-zero exit status %d: \n%s" % (
            self.cmd, self.returncode, self.output)


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
