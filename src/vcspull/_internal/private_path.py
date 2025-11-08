from __future__ import annotations

import os
import pathlib
import typing as t

if t.TYPE_CHECKING:
    PrivatePathBase = pathlib.Path
else:
    PrivatePathBase = type(pathlib.Path())


class PrivatePath(PrivatePathBase):
    """Path subclass that hides the user's home directory in textual output.

    The class behaves like :class:`pathlib.Path`, but normalizes string and
    representation output to replace the current user's home directory with
    ``~``. This is useful when logging or displaying paths that should not leak
    potentially sensitive information.

    Examples
    --------
    >>> from pathlib import Path
    >>> home = Path.home()
    >>> PrivatePath(home)
    PrivatePath('~')
    >>> PrivatePath(home / "projects" / "vcspull")
    PrivatePath('~/projects/vcspull')
    >>> str(PrivatePath("/tmp/example"))
    '/tmp/example'
    >>> f'build dir: {PrivatePath(home / "build")}'
    'build dir: ~/build'
    >>> '{}'.format(PrivatePath(home / 'notes.txt'))
    '~/notes.txt'
    """

    def __new__(cls, *args: t.Any, **kwargs: t.Any) -> PrivatePath:
        return super().__new__(cls, *args, **kwargs)

    @classmethod
    def _collapse_home(cls, value: str) -> str:
        """Collapse the user's home directory to ``~`` in ``value``."""
        if value.startswith("~"):
            return value

        home = str(pathlib.Path.home())
        if value == home:
            return "~"

        separators = {os.sep}
        if os.altsep:
            separators.add(os.altsep)

        for sep in separators:
            home_with_sep = home + sep
            if value.startswith(home_with_sep):
                return "~" + value[len(home) :]

        return value

    def __str__(self) -> str:
        original = pathlib.Path.__str__(self)
        return self._collapse_home(original)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"


__all__ = ["PrivatePath"]
