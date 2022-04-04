import getpass
import pathlib
import shutil
import textwrap

import pytest

from libvcs.shortcuts import create_repo_from_pip_url
from libvcs.states.git import GitRepo
from libvcs.util import run


@pytest.fixture(autouse=True, scope="session")
def home_path(tmp_path_factory: pytest.TempPathFactory):
    return tmp_path_factory.mktemp("home")


@pytest.fixture(autouse=True, scope="session")
def user_path(home_path: pathlib.Path):
    p = home_path / getpass.getuser()
    p.mkdir()
    return p


@pytest.fixture(autouse=True)
def set_user_path(monkeypatch: pytest.MonkeyPatch, user_path: pathlib.Path):
    monkeypatch.setenv("HOME", str(user_path))


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
    """Return kwargs for :func:`create_repo_from_pip_url`."""
    return {
        "url": "git+file://" + git_dummy_repo_dir,
        "parent_dir": str(repos_path),
        "name": "repo_name",
    }


@pytest.fixture
def git_repo(git_repo_kwargs) -> GitRepo:
    """Create an git repository for tests. Return repo."""
    repo = create_repo_from_pip_url(**git_repo_kwargs)
    repo.obtain(quiet=True)
    return repo


@pytest.fixture
def create_git_dummy_repo(repos_path: pathlib.Path) -> pathlib.Path:
    def fn(repo_name, testfile_filename="testfile.test"):
        repo_path = str(repos_path / repo_name)

        run(["git", "init", repo_name], cwd=str(repos_path))

        run(["touch", testfile_filename], cwd=repo_path)
        run(["git", "add", testfile_filename], cwd=repo_path)
        run(["git", "commit", "-m", "test file for %s" % repo_name], cwd=repo_path)

        return repo_path

    yield fn


@pytest.fixture
def git_dummy_repo_dir(repos_path: pathlib.Path, create_git_dummy_repo):
    """Create a git repo with 1 commit, used as a remote."""
    return create_git_dummy_repo("dummyrepo")


@pytest.fixture(scope="function")
def config_path(home_path: pathlib.Path, request: pytest.FixtureRequest):
    conf_path = home_path / ".vcspull"
    conf_path.mkdir(exist_ok=True)

    def clean():
        shutil.rmtree(conf_path)

    request.addfinalizer(clean)
    return conf_path


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
