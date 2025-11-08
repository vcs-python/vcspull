#!/usr/bin/env python3
"""Runtime dependency smoke test for vcspull.

This script attempts to import every module within the ``vcspull`` package and
invokes each CLI sub-command with ``--help``.  It is intended to run inside an
environment that only has the package's runtime dependencies installed to catch
missing dependency declarations (for example, ``typing_extensions``).
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import subprocess

ModuleName = str


def parse_args() -> argparse.Namespace:
    """Return parsed CLI arguments for the smoke test runner."""
    parser = argparse.ArgumentParser(
        description=(
            "Probe vcspull's runtime dependencies by importing all modules "
            "and exercising CLI entry points."
        ),
    )
    parser.add_argument(
        "--package",
        default="vcspull",
        help="Root package name to inspect (defaults to vcspull).",
    )
    parser.add_argument(
        "--cli-module",
        default="vcspull.cli",
        help="Module that exposes the create_parser helper for CLI discovery.",
    )
    parser.add_argument(
        "--cli-executable",
        default="vcspull",
        help="Console script to run for CLI smoke checks.",
    )
    parser.add_argument(
        "--cli-probe-arg",
        action="append",
        dest="cli_probe_args",
        default=None,
        help=(
            "Additional argument(s) appended after each CLI sub-command; "
            "may be repeated. Defaults to --help."
        ),
    )
    parser.add_argument(
        "--skip-imports",
        action="store_true",
        help="Skip module import validation.",
    )
    parser.add_argument(
        "--skip-cli",
        action="store_true",
        help="Skip CLI command execution.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print verbose output for each check.",
    )
    return parser.parse_args()


def discover_modules(package_name: str) -> list[ModuleName]:
    """Return a sorted list of module names within *package_name*."""
    package = importlib.import_module(package_name)
    module_names: set[str] = {package_name}
    package_path = getattr(package, "__path__", None)
    if package_path is None:
        return sorted(module_names)
    module_names.update(
        module_info.name
        for module_info in pkgutil.walk_packages(
            package_path,
            prefix=f"{package_name}.",
        )
    )
    return sorted(module_names)


def import_all_modules(module_names: list[ModuleName], verbose: bool) -> list[str]:
    """Attempt to import each module and return a list of failure messages."""
    failures: list[str] = []
    for module_name in module_names:
        if verbose:
            pass
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - reporting only
            detail = f"{module_name}: {exc!r}"
            failures.append(detail)
    return failures


def _find_cli_subcommands(
    cli_module_name: str,
) -> tuple[list[str], argparse.ArgumentParser]:
    """Return CLI sub-command names via vcspull.cli.create_parser."""
    cli_module = importlib.import_module(cli_module_name)
    try:
        parser = cli_module.create_parser()
    except AttributeError as exc:  # pragma: no cover - defensive
        msg = f"{cli_module_name} does not expose create_parser()"
        raise RuntimeError(msg) from exc

    commands: set[str] = set()
    for action in parser._actions:  # pragma: no branch - argparse internals
        if isinstance(action, argparse._SubParsersAction):
            commands.update(action.choices.keys())
    return sorted(commands), parser


def run_cli_command(
    executable: str,
    args: list[str],
    *,
    verbose: bool,
) -> tuple[int, str, str]:
    """Execute CLI command and capture its result."""
    command = [executable, *args]
    if verbose:
        pass
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if result.stdout:
            pass
        if result.stderr:
            pass
    return result.returncode, result.stdout, result.stderr


def exercise_cli(
    executable: str,
    cli_module_name: str,
    probe_args: list[str],
    verbose: bool,
) -> list[str]:
    """Run base CLI plus every sub-command, returning failure messages."""
    failures: list[str] = []
    subcommands, _parser = _find_cli_subcommands(cli_module_name)

    # Always test the base command with --help to verify the entry point.
    base_exit, _, _ = run_cli_command(executable, ["--help"], verbose=verbose)
    if base_exit != 0:
        failures.append(f"{executable} --help (exit code {base_exit})")

    for subcommand in subcommands:
        exit_code, _, _ = run_cli_command(
            executable,
            [subcommand, *probe_args],
            verbose=verbose,
        )
        if exit_code != 0:
            probe_display = " ".join(probe_args)
            failures.append(
                f"{executable} {subcommand} {probe_display} (exit code {exit_code})",
            )
    return failures


def main() -> int:
    """Entry point for the runtime dependency smoke test."""
    args = parse_args()
    cli_probe_args = args.cli_probe_args or ["--help"]
    failures: list[str] = []

    if not args.skip_imports:
        modules = discover_modules(args.package)
        failures.extend(import_all_modules(modules, args.verbose))

    if not args.skip_cli:
        failures.extend(
            exercise_cli(
                args.cli_executable,
                args.cli_module,
                cli_probe_args,
                args.verbose,
            ),
        )

    if failures:
        for _failure in failures:
            pass
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
