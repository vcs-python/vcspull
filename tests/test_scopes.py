"""Tests for configuration scope resolution, merging, and project trust."""

from __future__ import annotations

import io
import os
import pathlib
import sys
import textwrap
import typing as t

import pytest

from vcspull import config, exc
from vcspull._internal import scopes
from vcspull.types import ConfigDict

from .helpers import write_config

if t.TYPE_CHECKING:
    from collections.abc import Iterator


class WalkFixture(t.NamedTuple):
    """Fixture for the bounded upward walk."""

    test_id: str
    cwd: str
    ceilings: tuple[str, ...]
    expected: tuple[str, ...]


WALK_FIXTURES: list[WalkFixture] = [
    WalkFixture(
        test_id="stops-below-home",
        cwd="/home/u/work/api/src",
        ceilings=("/home/u",),
        expected=("/home/u/work", "/home/u/work/api", "/home/u/work/api/src"),
    ),
    WalkFixture(
        test_id="ceiling-itself-excluded",
        cwd="/home/u",
        ceilings=("/home/u",),
        expected=(),
    ),
    WalkFixture(
        test_id="outside-home-runs-to-root",
        cwd="/srv/app",
        ceilings=("/home/u",),
        expected=("/", "/srv", "/srv/app"),
    ),
    WalkFixture(
        test_id="custom-ceiling-overrides-home",
        cwd="/home/u/work/api",
        ceilings=("/home/u/work",),
        expected=("/home/u/work/api",),
    ),
    WalkFixture(
        test_id="no-ceiling-runs-to-root",
        cwd="/home/u/work",
        ceilings=(),
        expected=("/", "/home", "/home/u", "/home/u/work"),
    ),
]


@pytest.mark.parametrize(
    list(WalkFixture._fields),
    WALK_FIXTURES,
    ids=[fixture.test_id for fixture in WALK_FIXTURES],
)
def test_project_dirs_walk(
    test_id: str,
    cwd: str,
    ceilings: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    """The walk yields ancestors outermost first and honours its ceiling."""
    result = scopes.project_dirs(
        pathlib.Path(cwd),
        ceilings=frozenset(pathlib.Path(ceiling) for ceiling in ceilings),
    )
    assert result == tuple(pathlib.Path(path) for path in expected)


@pytest.fixture(autouse=True)
def trust_state_isolation(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the trusted-directory record per test.

    ``$HOME`` is session-scoped, so without this the trust state written by one
    test would still be there for the next.
    """
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


@pytest.fixture
def scoped_tree(
    tmp_path: pathlib.Path,
    config_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[pathlib.Path]:
    """Build a user config plus project configs at two depths, and chdir deep.

    Yields the deep working directory. ``shared`` is declared by both the user
    config and the outer project config, which is what makes the override
    observable.
    """
    # ``$HOME`` is session-scoped, so give this tree its own home; otherwise a
    # ``~/.vcspull.yaml`` left by another test joins the user scope.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    work = tmp_path / "work"
    deep = work / "api" / "src" / "deep"
    deep.mkdir(parents=True)

    write_config(
        config_path / "main.yaml",
        textwrap.dedent(
            f"""\
            {work}/vendor/:
              shared:
                repo: git+https://example.com/upstream.git
                options:
                  rev: v1.0.0
            ~/code/:
              flask: git+https://github.com/pallets/flask.git
            """,
        ),
    )
    write_config(
        work / ".vcspull.yaml",
        textwrap.dedent(
            f"""\
            {work}/vendor/:
              shared: git+https://example.com/fork.git
              outer: git+https://example.com/outer.git
            """,
        ),
    )
    write_config(
        work / "api" / ".vcspull.yaml",
        textwrap.dedent(
            f"""\
            {work}/api/deps/:
              inner: git+https://example.com/inner.git
            """,
        ),
    )

    monkeypatch.setenv("VCSPULL_CEILING_PATHS", str(tmp_path))
    monkeypatch.chdir(deep)
    yield deep


def _by_name(repos: list[ConfigDict]) -> dict[str, ConfigDict]:
    return {str(repo["name"]): repo for repo in repos}


def test_scopes_union_with_nearest_tier_winning(
    scoped_tree: pathlib.Path,
) -> None:
    """From a deep subdirectory every scope contributes, nearest wins outright."""
    repos = _by_name(config.load_scoped_configs(cwd=scoped_tree))

    assert set(repos) == {"flask", "shared", "outer", "inner"}
    assert repos["shared"]["url"] == "git+https://example.com/fork.git"
    # Whole-entry replacement: the user config's ``rev`` pin does not survive.
    assert "rev" not in repos["shared"]


def test_no_project_reproduces_user_only_resolution(
    scoped_tree: pathlib.Path,
) -> None:
    """``--no-project`` resolves exactly the pre-change user configuration."""
    repos = _by_name(
        config.load_scoped_configs(cwd=scoped_tree, include_project=False),
    )

    assert set(repos) == {"flask", "shared"}
    assert repos["shared"]["url"] == "git+https://example.com/upstream.git"
    assert repos["shared"]["rev"] == "v1.0.0"


def test_explicit_file_replaces_the_whole_stack(
    scoped_tree: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """``--file`` stays exclusive, exactly as it behaves today."""
    explicit = write_config(
        tmp_path / "explicit.yaml",
        f"{tmp_path}/only/:\n  solo: git+https://example.com/solo.git\n",
    )

    repos = config.load_scoped_configs(explicit, cwd=scoped_tree)

    assert [repo["name"] for repo in repos] == ["solo"]


def test_escaping_project_config_errors_without_a_tty(
    scoped_tree: pathlib.Path,
) -> None:
    """No terminal means a hard error naming ``vcspull trust``, never a hang."""
    write_config(
        scoped_tree.parent / ".vcspull.yaml",
        "~/.ssh/:\n  payload: git+https://example.com/payload.git\n",
    )

    with pytest.raises(exc.VCSPullException, match="vcspull trust"):
        config.load_scoped_configs(cwd=scoped_tree)


def test_escaping_project_config_loads_with_trust_project(
    scoped_tree: pathlib.Path,
) -> None:
    """``--trust-project`` accepts an escaping config non-interactively."""
    write_config(
        scoped_tree.parent / ".vcspull.yaml",
        "~/.ssh/:\n  payload: git+https://example.com/payload.git\n",
    )

    repos = _by_name(config.load_scoped_configs(cwd=scoped_tree, trust_project=True))

    assert "payload" in repos


class _Tty(io.StringIO):
    """Stand-in for an interactive stdin."""

    def isatty(self) -> bool:
        """Report an interactive terminal."""
        return True


class TrustAnswerFixture(t.NamedTuple):
    """Fixture for the interactive trust prompt."""

    test_id: str
    answer: str
    loads: bool
    remembers: bool


TRUST_ANSWER_FIXTURES: list[TrustAnswerFixture] = [
    TrustAnswerFixture(test_id="declined", answer="n", loads=False, remembers=False),
    TrustAnswerFixture(
        test_id="empty-declines", answer="", loads=False, remembers=False
    ),
    TrustAnswerFixture(
        test_id="accepted-once", answer="y", loads=True, remembers=False
    ),
    TrustAnswerFixture(test_id="always", answer="always", loads=True, remembers=True),
]


@pytest.mark.parametrize(
    list(TrustAnswerFixture._fields),
    TRUST_ANSWER_FIXTURES,
    ids=[fixture.test_id for fixture in TRUST_ANSWER_FIXTURES],
)
def test_trust_prompt_answers(
    test_id: str,
    answer: str,
    loads: bool,
    remembers: bool,
    scoped_tree: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The prompt gates the file, and ``always`` remembers the directory."""
    project = scoped_tree.parent
    write_config(
        project / ".vcspull.yaml",
        "~/.ssh/:\n  payload: git+https://example.com/payload.git\n",
    )
    monkeypatch.setattr(sys, "stdin", _Tty())
    monkeypatch.setattr("builtins.input", lambda _prompt="": answer)

    repos = _by_name(config.load_scoped_configs(cwd=scoped_tree))
    trusted = scopes.read_trusted(scopes.trust_state_file())

    assert ("payload" in repos) is loads
    assert (project.resolve() in trusted) is remembers


def test_trusted_directory_skips_the_prompt(
    scoped_tree: pathlib.Path,
) -> None:
    """A remembered project directory loads without asking again."""
    project = scoped_tree.parent
    write_config(
        project / ".vcspull.yaml",
        "~/.ssh/:\n  payload: git+https://example.com/payload.git\n",
    )
    scopes.trust_directory(scopes.trust_state_file(), project)

    assert "payload" in _by_name(config.load_scoped_configs(cwd=scoped_tree))


class DivergenceFixture(t.NamedTuple):
    """Fixture for the override-conflict warning."""

    test_id: str
    nearest_url: str
    warns: bool


DIVERGENCE_FIXTURES: list[DivergenceFixture] = [
    DivergenceFixture(
        test_id="identical-is-silent",
        nearest_url="git+https://example.com/upstream.git",
        warns=False,
    ),
    DivergenceFixture(
        test_id="different-url-warns",
        nearest_url="git+https://example.com/fork.git",
        warns=True,
    ),
    DivergenceFixture(
        test_id="different-vcs-warns",
        nearest_url="hg+https://example.com/upstream.git",
        warns=True,
    ),
]


@pytest.mark.parametrize(
    list(DivergenceFixture._fields),
    DIVERGENCE_FIXTURES,
    ids=[fixture.test_id for fixture in DIVERGENCE_FIXTURES],
)
def test_override_warns_only_on_real_divergence(
    test_id: str,
    nearest_url: str,
    warns: bool,
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An identical duplicate across scopes is the harmless, silent case."""
    weakest = write_config(
        tmp_path / "weakest.yaml",
        f"{tmp_path}/code/:\n  shared: git+https://example.com/upstream.git\n",
    )
    nearest = write_config(
        tmp_path / "nearest.yaml",
        f"{tmp_path}/code/:\n  shared: {nearest_url}\n",
    )

    with caplog.at_level("WARNING", logger="vcspull.config"):
        repos = config.load_configs([weakest, nearest])

    assert [repo["name"] for repo in repos] == ["shared"]
    assert repos[0]["url"] == nearest_url
    assert bool(caplog.records) is warns


class ContainmentFixture(t.NamedTuple):
    """Fixture for the destination containment check."""

    test_id: str
    destinations: tuple[str, ...]
    expected: tuple[str, ...]


CONTAINMENT_FIXTURES: list[ContainmentFixture] = [
    ContainmentFixture(
        test_id="relative-child-contained",
        destinations=("./vendor/flask", "sub/nested/x"),
        expected=(),
    ),
    ContainmentFixture(
        test_id="home-rooted-escapes",
        destinations=("~/.ssh/evil",),
        expected=("~/.ssh/evil",),
    ),
    ContainmentFixture(
        test_id="parent-traversal-escapes",
        destinations=("../elsewhere/x",),
        expected=("../elsewhere/x",),
    ),
    ContainmentFixture(
        test_id="symlink-target-escapes",
        destinations=("./escape-link/x",),
        expected=("./escape-link/x",),
    ),
    ContainmentFixture(
        test_id="mixed-reports-only-escaping",
        destinations=("./vendor/a", "~/.ssh/b", "./vendor/a"),
        expected=("~/.ssh/b",),
    ),
]


@pytest.mark.parametrize(
    list(ContainmentFixture._fields),
    CONTAINMENT_FIXTURES,
    ids=[fixture.test_id for fixture in CONTAINMENT_FIXTURES],
)
def test_escaping_destinations(
    test_id: str,
    destinations: tuple[str, ...],
    expected: tuple[str, ...],
    tmp_path: pathlib.Path,
) -> None:
    """Only destinations landing outside the config's own directory report."""
    project = tmp_path / "project"
    (project / "sub" / "nested").mkdir(parents=True)
    (project / "escape-link").symlink_to(tmp_path / "outside", target_is_directory=True)

    def resolved(entry: str) -> pathlib.Path:
        target = pathlib.Path(entry).expanduser()
        if not target.is_absolute():
            target = project / target
        return pathlib.Path(os.path.realpath(target))

    assert scopes.escaping_destinations(
        [pathlib.Path(entry) for entry in destinations],
        config_dir=project,
        cwd=project,
    ) == tuple(resolved(entry) for entry in expected)


def test_path_override_cannot_smuggle_a_destination_out(
    scoped_tree: pathlib.Path,
) -> None:
    """A contained workspace root does not license an escaping ``path:``.

    ``extract_repos`` honours a per-entry ``path:`` and never consults the
    workspace root, so a gate reading only the top-level keys would clone this
    into ``~/.ssh`` without asking.
    """
    write_config(
        scoped_tree.parent / ".vcspull.yaml",
        textwrap.dedent(
            """\
            ./vendor/:
              evil:
                repo: git+https://example.com/evil.git
                path: ~/.ssh/evil
            """,
        ),
    )

    with pytest.raises(exc.VCSPullException, match="vcspull trust"):
        config.load_scoped_configs(cwd=scoped_tree)


def test_symlinked_home_stops_the_walk_and_loads_once(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``$HOME`` reached through a symlink is still the ceiling.

    Comparing unresolved paths let the walk run past ``$HOME``, which both
    re-read the home dotfile as a project config and exposed everything above
    it.
    """
    real_home = tmp_path / "real" / "u"
    (real_home / "work" / "proj").mkdir(parents=True)
    linked_home = tmp_path / "u"
    linked_home.symlink_to(real_home, target_is_directory=True)
    monkeypatch.setenv("HOME", str(linked_home))
    monkeypatch.delenv("VCSPULL_CEILING_PATHS", raising=False)

    write_config(
        real_home / ".vcspull.yaml",
        f"{tmp_path}/code/:\n  flask: git+https://example.com/flask.git\n",
    )

    for cwd in (real_home / "work" / "proj", linked_home / "work" / "proj"):
        sources = scopes.resolve_sources(cwd=cwd)
        assert [source.scope for source in sources] == ["user"]


def test_both_home_dotfiles_still_raise(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owning ``~/.vcspull.yaml`` and ``~/.vcspull.json`` is still an error."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    write_config(home / ".vcspull.yaml", "{}\n")
    write_config(home / ".vcspull.json", "{}\n")

    with pytest.raises(exc.MultipleConfigWarning):
        scopes.resolve_sources(cwd=home / "work")


def test_vcspull_no_project_env_drops_the_project_scope(
    scoped_tree: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``VCSPULL_NO_PROJECT=1`` resolves the same stack as ``--no-project``."""
    monkeypatch.setenv("VCSPULL_NO_PROJECT", "1")

    repos = _by_name(config.load_scoped_configs(cwd=scoped_tree))

    assert set(repos) == {"flask", "shared"}
    assert repos["shared"]["url"] == "git+https://example.com/upstream.git"


class ScopeDirFixture(t.NamedTuple):
    """Fixture for scope directories that must not crash the resolver."""

    test_id: str
    build: t.Callable[[pathlib.Path], None]
    expected: tuple[str, ...]


def _empty_config(directory: pathlib.Path) -> None:
    write_config(directory / "a.yaml", "# nothing here\n")


def _directory_named_like_a_config(directory: pathlib.Path) -> None:
    (directory / "a.yaml").mkdir()
    write_config(directory / "b.yaml", "{}\n")


def _unreadable(directory: pathlib.Path) -> None:
    write_config(directory / "a.yaml", "{}\n")
    directory.chmod(0o000)


SCOPE_DIR_FIXTURES: list[ScopeDirFixture] = [
    ScopeDirFixture(
        test_id="comment-only-file-is-listed",
        build=_empty_config,
        expected=("a.yaml",),
    ),
    ScopeDirFixture(
        test_id="directory-named-like-a-config-is-skipped",
        build=_directory_named_like_a_config,
        expected=("b.yaml",),
    ),
    ScopeDirFixture(
        test_id="unreadable-directory-yields-nothing",
        build=_unreadable,
        expected=(),
    ),
]


@pytest.mark.skipif(os.getuid() == 0, reason="root ignores directory permissions")
@pytest.mark.parametrize(
    list(ScopeDirFixture._fields),
    SCOPE_DIR_FIXTURES,
    ids=[fixture.test_id for fixture in SCOPE_DIR_FIXTURES],
)
def test_scope_directory_survives_hostile_contents(
    test_id: str,
    build: t.Callable[[pathlib.Path], None],
    expected: tuple[str, ...],
    tmp_path: pathlib.Path,
) -> None:
    """Listing a scope directory never raises, whatever is in it."""
    scope_dir = tmp_path / "scope"
    scope_dir.mkdir()
    build(scope_dir)
    try:
        assert (
            tuple(path.name for path in scopes._config_files_in(scope_dir)) == expected
        )
    finally:
        scope_dir.chmod(0o755)


def test_comment_only_project_config_loads_as_empty(
    scoped_tree: pathlib.Path,
) -> None:
    """A ``.vcspull.yaml`` with nothing in it contributes nothing."""
    write_config(scoped_tree / ".vcspull.yaml", "# nothing yet\n")

    assert "inner" in _by_name(config.load_scoped_configs(cwd=scoped_tree))
