"""Tests for vcspull add command functionality."""

from __future__ import annotations

import contextlib
import logging
import typing as t

import pytest
import yaml

from vcspull.cli import cli
from vcspull.cli.add import add_repo

if t.TYPE_CHECKING:
    import pathlib

    from typing_extensions import TypeAlias

    ExpectedOutput: TypeAlias = t.Optional[t.Union[str, list[str]]]


@pytest.fixture(autouse=True)
def clear_logging_handlers() -> t.Generator[None, None, None]:
    """Clear logging handlers after each test to prevent stream closure issues."""
    yield
    # Clear handlers from all CLI loggers after test
    cli_loggers = [
        "vcspull",
        "vcspull.cli.add",
        "vcspull.cli.add_from_fs",
        "vcspull.cli.sync",
    ]
    for logger_name in cli_loggers:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()


class AddRepoFixture(t.NamedTuple):
    """Pytest fixture for vcspull add command."""

    # pytest internal: used for naming test
    test_id: str

    # test parameters
    cli_args: list[str]
    initial_config: dict[str, t.Any] | None
    expected_config_contains: dict[str, t.Any]
    expected_in_output: ExpectedOutput = None
    expected_not_in_output: ExpectedOutput = None
    expected_log_level: str = "INFO"
    should_create_config: bool = False


ADD_REPO_FIXTURES: list[AddRepoFixture] = [
    # Simple repo addition with default base dir
    AddRepoFixture(
        test_id="simple-repo-default-dir",
        cli_args=["add", "myproject", "git@github.com:user/myproject.git"],
        initial_config=None,
        should_create_config=True,
        expected_config_contains={
            "./": {
                "myproject": {"repo": "git@github.com:user/myproject.git"},
            },
        },
        expected_in_output="Successfully added 'myproject'",
    ),
    # Add with custom base directory
    AddRepoFixture(
        test_id="custom-base-dir",
        cli_args=[
            "add",
            "mylib",
            "https://github.com/org/mylib",
            "--dir",
            "~/projects/libs",
        ],
        initial_config=None,
        should_create_config=True,
        expected_config_contains={
            "~/projects/libs/": {
                "mylib": {"repo": "https://github.com/org/mylib"},
            },
        },
        expected_in_output="Successfully added 'mylib'",
    ),
    # Add to existing config
    AddRepoFixture(
        test_id="add-to-existing",
        cli_args=[
            "add",
            "project2",
            "git@github.com:user/project2.git",
            "--dir",
            "~/work",
        ],
        initial_config={
            "~/work/": {
                "project1": {"repo": "git@github.com:user/project1.git"},
            },
        },
        expected_config_contains={
            "~/work/": {
                "project1": {"repo": "git@github.com:user/project1.git"},
                "project2": {"repo": "git@github.com:user/project2.git"},
            },
        },
        expected_in_output="Successfully added 'project2'",
    ),
    # Duplicate repo detection
    AddRepoFixture(
        test_id="duplicate-repo",
        cli_args=[
            "add",
            "existing",
            "git@github.com:other/existing.git",
            "--dir",
            "~/code",
        ],
        initial_config={
            "~/code/": {
                "existing": {"repo": "git@github.com:user/existing.git"},
            },
        },
        expected_config_contains={
            "~/code/": {
                "existing": {"repo": "git@github.com:user/existing.git"},
            },
        },
        expected_in_output=[
            "Repository 'existing' already exists",
            "Current URL: git@github.com:user/existing.git",
        ],
        expected_log_level="WARNING",
    ),
    # Path inference
    AddRepoFixture(
        test_id="path-inference",
        cli_args=[
            "add",
            "inferred",
            "git@github.com:user/inferred.git",
            "--path",
            "~/dev/projects/inferred",
        ],
        initial_config=None,
        should_create_config=True,
        expected_config_contains={
            "~/dev/projects/inferred/": {
                "inferred": {"repo": "git@github.com:user/inferred.git"},
            },
        },
        expected_in_output="Successfully added 'inferred'",
    ),
]


@pytest.mark.parametrize(
    list(AddRepoFixture._fields),
    ADD_REPO_FIXTURES,
    ids=[test.test_id for test in ADD_REPO_FIXTURES],
)
def test_add_repo_cli(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    test_id: str,
    cli_args: list[str],
    initial_config: dict[str, t.Any] | None,
    expected_config_contains: dict[str, t.Any],
    expected_in_output: ExpectedOutput,
    expected_not_in_output: ExpectedOutput,
    expected_log_level: str,
    should_create_config: bool,
) -> None:
    """Test vcspull add command through CLI."""
    caplog.set_level(expected_log_level)

    # Set up config file path
    config_file = tmp_path / ".vcspull.yaml"

    # Create initial config if provided
    if initial_config:
        yaml_content = yaml.dump(initial_config, default_flow_style=False)
        config_file.write_text(yaml_content, encoding="utf-8")

    # Add config path to CLI args if not specified
    if "-c" not in cli_args and "--config" not in cli_args:
        cli_args = [*cli_args[:1], "-c", str(config_file), *cli_args[1:]]

    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    # Run CLI command
    with contextlib.suppress(SystemExit):
        cli(cli_args)

    # Capture output
    captured = capsys.readouterr()
    output = "".join([*caplog.messages, captured.out, captured.err])

    # Check expected output (strip ANSI codes for comparison)
    import re

    clean_output = re.sub(r"\x1b\[[0-9;]*m", "", output)  # Strip ANSI codes

    if expected_in_output is not None:
        if isinstance(expected_in_output, str):
            expected_in_output = [expected_in_output]
        for needle in expected_in_output:
            assert needle in clean_output, (
                f"Expected '{needle}' in output, got: {clean_output}"
            )

    if expected_not_in_output is not None:
        if isinstance(expected_not_in_output, str):
            expected_not_in_output = [expected_not_in_output]
        for needle in expected_not_in_output:
            assert needle not in clean_output, f"Unexpected '{needle}' in output"

    # Verify config file
    if should_create_config or initial_config:
        assert config_file.exists(), "Config file should exist"

        # Load and verify config
        with config_file.open() as f:
            config_data = yaml.safe_load(f)

        # Check expected config contents
        for key, value in expected_config_contains.items():
            assert key in config_data, f"Expected key '{key}' in config"
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    assert subkey in config_data[key], (
                        f"Expected '{subkey}' in config['{key}']"
                    )
                    assert config_data[key][subkey] == subvalue, (
                        f"Config mismatch for {key}/{subkey}: "
                        f"expected {subvalue}, got {config_data[key][subkey]}"
                    )


class TestAddRepoUnit:
    """Unit tests for add_repo function."""

    def test_add_repo_direct_call(
        self,
        tmp_path: pathlib.Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test direct add_repo function call."""
        config_file = tmp_path / ".vcspull.yaml"

        # Call add_repo directly
        add_repo(
            name="direct-test",
            url="git@github.com:user/direct.git",
            config_file_path_str=str(config_file),
            path=None,
            base_dir=None,
        )

        # Verify
        assert config_file.exists()
        with config_file.open() as f:
            config_data = yaml.safe_load(f)

        assert "./" in config_data
        assert "direct-test" in config_data["./"]
        assert config_data["./"]["direct-test"] == {
            "repo": "git@github.com:user/direct.git",
        }

    def test_add_repo_invalid_config(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test handling of invalid config file."""
        config_file = tmp_path / ".vcspull.yaml"

        # Write invalid YAML
        config_file.write_text("invalid: yaml: content:", encoding="utf-8")

        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Try to add repo
        add_repo(
            name="test",
            url="git@github.com:user/test.git",
            config_file_path_str=str(config_file),
            path=None,
            base_dir=None,
        )

        # Should log error to stderr
        captured = capsys.readouterr()
        assert "Error loading YAML" in captured.err


def test_add_command_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test add command help output."""
    with contextlib.suppress(SystemExit):
        cli(["add", "--help"])

    captured = capsys.readouterr()
    output = captured.out + captured.err

    # Check help content
    assert "Add a repository to the vcspull configuration file" in output
    assert "name" in output
    assert "url" in output
    assert "--path" in output
    assert "--dir" in output
    assert "--config" in output
