import pytest

from _pytest.compat import LEGACY_PATH

from libvcs.shortcuts import create_repo_from_pip_url
from libvcs.util import run


@pytest.fixture(scope="function")
def tmpdir_repoparent(tmpdir_factory):
    """Return temporary directory for repository checkout guaranteed unique."""
    fn = tmpdir_factory.mktemp("repo")
    return fn


@pytest.fixture
def git_repo_kwargs(tmpdir_repoparent, git_dummy_repo_dir):
    """Return kwargs for :func:`create_repo_from_pip_url`."""
    repo_name = "repo_clone"
    return {
        "url": "git+file://" + git_dummy_repo_dir,
        "parent_dir": str(tmpdir_repoparent),
        "name": repo_name,
    }


@pytest.fixture
def git_repo(git_repo_kwargs):
    """Create an git repository for tests. Return repo."""
    git_repo = create_repo_from_pip_url(**git_repo_kwargs)
    git_repo.obtain(quiet=True)
    return git_repo


@pytest.fixture
def create_git_dummy_repo(tmpdir_repoparent):
    def fn(repo_name, testfile_filename="testfile.test"):
        repo_path = str(tmpdir_repoparent.join(repo_name))

        run(["git", "init", repo_name], cwd=str(tmpdir_repoparent))

        run(["touch", testfile_filename], cwd=repo_path)
        run(["git", "add", testfile_filename], cwd=repo_path)
        run(["git", "commit", "-m", "test file for %s" % repo_name], cwd=repo_path)

        return repo_path

    yield fn


@pytest.fixture
def git_dummy_repo_dir(tmpdir_repoparent, create_git_dummy_repo):
    """Create a git repo with 1 commit, used as a remote."""
    return create_git_dummy_repo("dummyrepo")


@pytest.fixture
def config_dir(tmpdir: LEGACY_PATH):
    conf_dir = tmpdir.join(".vcspull")
    conf_dir.ensure(dir=True)
    return conf_dir
