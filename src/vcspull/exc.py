"""Exceptions for vcspull."""


class VCSPullException(Exception):
    """Standard exception raised by vcspull."""


class MultipleConfigWarning(VCSPullException):
    """Multiple eligible config files found at the same time."""

    message = "Multiple configs found in home directory use only one. .yaml, .json."
