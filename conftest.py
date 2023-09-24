import pathlib
import shutil
import typing as t

import pytest


@pytest.fixture(autouse=True)
def add_doctest_fixtures(
    request: pytest.FixtureRequest,
    doctest_namespace: dict[str, t.Any],
) -> None:
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
    pass


@pytest.fixture(autouse=True)
def cwd_default(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True, scope="session")
def xdg_config_path(user_path: pathlib.Path) -> pathlib.Path:
    p = user_path / ".config"
    p.mkdir()
    return p


@pytest.fixture()
def config_path(
    xdg_config_path: pathlib.Path, request: pytest.FixtureRequest
) -> pathlib.Path:
    conf_path = xdg_config_path / "vcspull"
    conf_path.mkdir(exist_ok=True)

    def clean() -> None:
        shutil.rmtree(conf_path)

    request.addfinalizer(clean)
    return conf_path


@pytest.fixture(autouse=True)
def set_xdg_config_path(
    monkeypatch: pytest.MonkeyPatch, xdg_config_path: pathlib.Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_path))


@pytest.fixture()
def repos_path(user_path: pathlib.Path, request: pytest.FixtureRequest) -> pathlib.Path:
    """Return temporary directory for repository checkout guaranteed unique."""
    dir = user_path / "repos"
    dir.mkdir(exist_ok=True)

    def clean() -> None:
        shutil.rmtree(dir)

    request.addfinalizer(clean)
    return dir
