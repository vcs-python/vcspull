"""Tests for ``vcspull config ls``, ``vcspull trust``, and the scope flags."""

from __future__ import annotations

import pathlib
import textwrap
import typing as t

import pytest

from tests.helpers import write_config
from vcspull._internal import scopes
from vcspull.cli import cli

if t.TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def scoped_cli(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[pathlib.Path]:
    """Give one test its own home, trust record, and project tree.

    Yields the project directory, already the working directory. The user
    config declares ``flask`` and ``click`` under the project's vendor
    directory; the project config repoints ``flask``, so one entry is
    overridden and one is not.
    """
    home = tmp_path / "home"
    project = home / "work" / "proj"
    project.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("VCSPULL_CEILING_PATHS", raising=False)
    monkeypatch.delenv("VCSPULL_NO_PROJECT", raising=False)
    monkeypatch.chdir(project)

    write_config(
        home / ".vcspull.yaml",
        textwrap.dedent(
            """\
            ~/work/proj/vendor/:
              flask: git+https://github.com/pallets/flask.git
              click: git+https://github.com/pallets/click.git
            """,
        ),
    )
    write_config(
        project / ".vcspull.yaml",
        "./vendor/:\n  flask: git+https://github.com/myfork/flask.git\n",
    )
    yield project


def _escaping(project: pathlib.Path) -> pathlib.Path:
    """Write a project config that checks a repository out into ``~/.ssh``."""
    return write_config(
        project / ".vcspull.yaml",
        textwrap.dedent(
            """\
            ./vendor/:
              evil:
                repo: git+https://example.com/evil.git
                path: ~/.ssh/evil
            """,
        ),
    )


def test_config_ls_lists_tiers_weakest_first(
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every file in effect is named, with its scope and repository count."""
    cli(["config", "ls"])

    lines = capsys.readouterr().out.splitlines()

    assert lines[0].startswith("user")
    assert lines[1].startswith("project")
    assert lines[-1] == "2 repositories in effect."


def test_config_ls_marks_overridden_entries(
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The weaker file says how many of its entries a nearer one displaced."""
    cli(["config", "ls"])

    out = capsys.readouterr().out

    assert "2 repos (1 overridden)" in out
    assert "1 repo\n" in out


def test_config_ls_marks_an_untrusted_project_config(
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``config ls`` diagnoses the refusal instead of reproducing it.

    ``vcspull list`` raises on this tree, so the command you reach for to find
    out why must not raise, prompt, or quietly omit the file.
    """
    _escaping(scoped_cli)

    cli(["config", "ls"])

    out = capsys.readouterr().out
    assert "(untrusted)" in out
    assert "vcspull trust" in out


def test_config_ls_honours_no_project(
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--no-project`` after ``ls`` drops the project tier from the report."""
    cli(["config", "ls", "--no-project"])

    out = capsys.readouterr().out
    assert "project" not in out
    assert "2 repositories in effect." in out


def test_config_ls_without_any_configuration(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A machine with no configuration says so rather than printing a header."""
    home = tmp_path / "empty-home"
    (home / "work").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VCSPULL_CEILING_PATHS", raising=False)
    monkeypatch.chdir(home / "work")

    cli(["config", "ls"])

    assert capsys.readouterr().out == "no configuration files found\n"


class ScopeFlagFixture(t.NamedTuple):
    """Fixture for a scope flag accepted before and after the subcommand."""

    test_id: str
    argv: list[str]


SCOPE_FLAG_FIXTURES: list[ScopeFlagFixture] = [
    ScopeFlagFixture(test_id="root-no-project", argv=["--no-project", "list"]),
    ScopeFlagFixture(test_id="subcommand-no-project", argv=["list", "--no-project"]),
    ScopeFlagFixture(
        test_id="root-trust-project",
        argv=["--trust-project", "list"],
    ),
    ScopeFlagFixture(
        test_id="subcommand-trust-project",
        argv=["list", "--trust-project"],
    ),
]


@pytest.mark.parametrize(
    list(ScopeFlagFixture._fields),
    SCOPE_FLAG_FIXTURES,
    ids=[fixture.test_id for fixture in SCOPE_FLAG_FIXTURES],
)
def test_scope_flags_parse_in_either_position(
    test_id: str,
    argv: list[str],
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both spellings work: nobody should have to remember which side wins."""
    _escaping(scoped_cli)

    cli(argv)

    assert "flask" in capsys.readouterr().out


def test_untrusted_config_reports_one_line_and_exits(
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A refusal is an actionable sentence, not a traceback."""
    _escaping(scoped_cli)

    with pytest.raises(SystemExit) as excinfo:
        cli(["list"])

    captured = capsys.readouterr()
    assert excinfo.value.code == 1
    assert len(captured.err.strip().splitlines()) == 1
    assert "vcspull trust" in captured.err


def test_trust_records_shows_and_forgets(
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``trust``, ``--show``, and ``--untrust`` round-trip one directory."""
    cli(["trust", str(scoped_cli)])
    assert scopes.read_trusted(scopes.trust_state_file()) == frozenset(
        {scoped_cli.resolve()},
    )

    capsys.readouterr()
    cli(["trust", "--show"])
    assert str(scoped_cli.resolve()) in capsys.readouterr().out.replace(
        "~",
        str(pathlib.Path.home()),
    )

    cli(["trust", "--untrust", str(scoped_cli)])
    assert scopes.read_trusted(scopes.trust_state_file()) == frozenset()


def test_trusting_the_project_lets_it_load(
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Trust is what turns the refusal into a load."""
    _escaping(scoped_cli)
    cli(["trust", str(scoped_cli)])
    capsys.readouterr()

    cli(["list"])

    assert "evil" in capsys.readouterr().out


def test_fmt_write_is_gated_on_a_discovered_project_config(
    scoped_cli: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``fmt --write`` runs through the same gate every other command does."""
    escaping = _escaping(scoped_cli)
    before = escaping.read_text(encoding="utf-8")

    with pytest.raises(SystemExit):
        cli(["fmt", "--all", "--write"])

    assert escaping.read_text(encoding="utf-8") == before


def test_discover_yes_does_not_grant_trust(
    scoped_cli: pathlib.Path,
) -> None:
    """``discover --yes`` skips *its own* prompt, never the trust gate.

    The two questions are unrelated, and conflating them would let a routine
    import flag authorize a config that writes outside its directory.
    """
    (pathlib.Path.home() / ".vcspull.yaml").unlink()
    _escaping(scoped_cli)
    (scoped_cli / "vendor").mkdir()

    with pytest.raises(SystemExit):
        cli(["discover", str(scoped_cli / "vendor"), "--yes"])
