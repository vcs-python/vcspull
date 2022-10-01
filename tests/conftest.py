import getpass
import pathlib
import shutil
import textwrap
import typing as t

import pytest

from libvcs._internal.run import run
from libvcs._internal.shortcuts import create_project
from libvcs.sync.git import GitSync


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


@pytest.fixture
def git_repo_kwargs(repos_path: pathlib.Path, git_dummy_repo_dir):
    """Return kwargs for :func:`create_project`."""
    return {
        "url": "git+file://" + git_dummy_repo_dir,
        "dir": str(repos_path / "repo_name"),
        "name": "repo_name",
    }


class DummyRepoProtocol(t.Protocol):
    """Callback for repo fixture factory."""

    def __call__(self, repo_name: str, testfile_filename: str = ...) -> str:
        """Callback signature for subprocess communication."""
        ...


@pytest.fixture
def create_git_dummy_repo(
    repos_path: pathlib.Path,
) -> t.Generator[DummyRepoProtocol, None, None]:
    def fn(repo_name: str, testfile_filename: str = "testfile.test"):
        repo_path = str(repos_path / repo_name)

        run(["git", "init", repo_name], cwd=str(repos_path))

        run(["touch", testfile_filename], cwd=repo_path)
        run(["git", "add", testfile_filename], cwd=repo_path)
        run(["git", "commit", "-m", "test file for %s" % repo_name], cwd=repo_path)

        return repo_path

    yield fn


@pytest.fixture
def git_dummy_repo_dir(
    repos_path: pathlib.Path, create_git_dummy_repo: DummyRepoProtocol
):
    """Create a git repo with 1 commit, used as a remote."""
    return create_git_dummy_repo("dummyrepo")


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
