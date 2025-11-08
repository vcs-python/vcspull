from __future__ import annotations

import os
from pathlib import Path

from vcspull._internal.private_path import PrivatePath


def test_str_collapses_home_directory() -> None:
    home = Path.home()
    assert str(PrivatePath(home)) == "~"

    project_path = PrivatePath(home / "projects" / "vcspull")
    assert str(project_path) == f"~{os.sep}projects{os.sep}vcspull"


def test_repr_uses_tilde_for_home_directory() -> None:
    home = Path.home()
    project_path = PrivatePath(home / "projects")
    assert repr(project_path) == f"PrivatePath('~{os.sep}projects')"


def test_absolute_paths_outside_home_are_unmodified() -> None:
    path = PrivatePath("/tmp/vcspull-example")
    assert str(path) == "/tmp/vcspull-example"
    assert repr(path) == "PrivatePath('/tmp/vcspull-example')"


def test_existing_tilde_prefix_is_preserved() -> None:
    path = PrivatePath("~/.config/vcspull")
    assert str(path) == "~/.config/vcspull"


def test_trailing_slash_collapses_to_directory_label() -> None:
    home = Path.home()
    path = PrivatePath(home / "projects/")
    assert str(path) == f"~{os.sep}projects"


def test_relative_path_unmodified() -> None:
    path = PrivatePath("relative/path")
    assert str(path) == "relative/path"
