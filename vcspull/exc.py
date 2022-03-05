class VCSPullException(Exception):

    """Standard exception raised by libvcs."""


class MultipleConfigWarning(VCSPullException):
    message = "Multiple configs found in home directory use only one." " .yaml, .json."
