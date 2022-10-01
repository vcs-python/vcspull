import getpass
import pathlib
import shutil
import textwrap

import pytest


@pytest.fixture(autouse=True, scope="session")
def home_path(tmp_path_factory: pytest.TempPathFactory):
    return tmp_path_factory.mktemp("home")


@pytest.fixture(autouse=True, scope="session")
def user_path(home_path: pathlib.Path):
    p = home_path / getpass.getuser()
    p.mkdir()
    return p


@pytest.fixture(autouse=True, scope="session")
@pytest.mark.usefixtures("set_user_path")
def xdg_config_path(user_path: pathlib.Path):
    p = user_path / ".config"
    p.mkdir()
    return p


@pytest.fixture(scope="function")
def config_path(xdg_config_path: pathlib.Path, request: pytest.FixtureRequest):
    conf_path = xdg_config_path / "vcspull"
    conf_path.mkdir(exist_ok=True)

    def clean():
        shutil.rmtree(conf_path)

    request.addfinalizer(clean)
    return conf_path


@pytest.fixture(autouse=True)
def set_user_path(monkeypatch: pytest.MonkeyPatch, user_path: pathlib.Path):
    monkeypatch.setenv("HOME", str(user_path))


@pytest.fixture(autouse=True)
def set_xdg_config_path(monkeypatch: pytest.MonkeyPatch, xdg_config_path: pathlib.Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_path))


@pytest.fixture(scope="function")
def repos_path(user_path: pathlib.Path, request: pytest.FixtureRequest):
    """Return temporary directory for repository checkout guaranteed unique."""
    dir = user_path / "repos"
    dir.mkdir(exist_ok=True)

    def clean():
        shutil.rmtree(dir)

    request.addfinalizer(clean)
    return dir


@pytest.fixture(autouse=True, scope="session")
def hgrc(user_path: pathlib.Path):
    hgrc = user_path / ".hgrc"
    hgrc.write_text(
        textwrap.dedent(
            f"""
        [ui]
        username = vcspull tests <vcspull@git-pull.com>
        merge = internal:merge

        [trusted]
        users = {getpass.getuser()}
    """
        ),
        encoding="utf-8",
    )
    return hgrc


@pytest.fixture(autouse=True, scope="module")
def gitconfig(user_path: pathlib.Path):
    gitconfig = user_path / ".gitconfig"
    gitconfig.write_text(
        textwrap.dedent(
            f"""
  [user]
    email = libvcs@git-pull.com
    name = {getpass.getuser()}
    """
        ),
        encoding="utf-8",
    )
    return gitconfig
