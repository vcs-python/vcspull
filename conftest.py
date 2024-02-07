"""Conftest.py (root-level).

We keep this in root pytest fixtures in pytest's doctest plugin to be available, as well
as avoiding conftest.py from being included in the wheel, in addition to pytest_plugin
for pytester only being available via the root directory.

See "pytest_plugins in non-top-level conftest files" in
https://docs.pytest.org/en/stable/deprecations.html
"""
import pathlib
import shutil
import typing as t

import pytest


@pytest.fixture(autouse=True)
def add_doctest_fixtures(
    request: pytest.FixtureRequest,
    doctest_namespace: dict[str, t.Any],
) -> None:
    """Harness pytest fixtures to doctests namespace."""
    from _pytest.doctest import DoctestItem

    if isinstance(request._pyfuncitem, DoctestItem):
        request.getfixturevalue("add_doctest_fixtures")
        request.getfixturevalue("set_home")


@pytest.fixture(autouse=True)
def setup(
    request: pytest.FixtureRequest,
    gitconfig: pathlib.Path,
    set_home: pathlib.Path,
    xdg_config_path: pathlib.Path,
) -> None:
    """Automatically load the pytest fixtures in the parameters."""
    pass


@pytest.fixture(autouse=True)
def cwd_default(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Change the current directory to a temporary directory."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def xdg_config_path(
    user_path: pathlib.Path,
    set_home: pathlib.Path,
) -> pathlib.Path:
    """Create and return path to use for XDG Config Path."""
    p = user_path / ".config"
    if not p.exists():
        p.mkdir()
    return p


@pytest.fixture(scope="function")
def config_path(
    xdg_config_path: pathlib.Path,
    request: pytest.FixtureRequest,
) -> pathlib.Path:
    """Ensure and return vcspull configuration path."""
    conf_path = xdg_config_path / "vcspull"
    conf_path.mkdir(exist_ok=True)

    def clean() -> None:
        shutil.rmtree(conf_path)

    request.addfinalizer(clean)
    return conf_path


@pytest.fixture(autouse=True)
def set_xdg_config_path(
    monkeypatch: pytest.MonkeyPatch,
    xdg_config_path: pathlib.Path,
) -> None:
    """Set XDG_CONFIG_HOME environment variable."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_path))


@pytest.fixture(scope="function")
def repos_path(user_path: pathlib.Path, request: pytest.FixtureRequest) -> pathlib.Path:
    """Return temporary directory for repository checkout guaranteed unique."""
    dir = user_path / "repos"
    dir.mkdir(exist_ok=True)

    def clean() -> None:
        shutil.rmtree(dir)

    request.addfinalizer(clean)
    return dir
