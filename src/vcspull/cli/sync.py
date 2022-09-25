import argparse
import logging
import pathlib
import sys
import typing as t
from copy import deepcopy
from datetime import datetime

from libvcs._internal.shortcuts import create_project
from libvcs._internal.types import VCSLiteral
from libvcs.sync.git import GitSync
from libvcs.url import registry as url_tools

from ..config import filter_repos, find_config_files, load_configs

log = logging.getLogger(__name__)


def clamp(n: int, _min: int, _max: int) -> int:
    return max(_min, min(n, _max))


EXIT_ON_ERROR_MSG = "Exiting via error (--exit-on-error passed)"
NO_REPOS_FOR_TERM_MSG = 'No repo found in config(s) for "{name}"'


def create_sync_subparser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    config_file = parser.add_argument(
        "--config",
        "-c",
        metavar="config-file",
        help="optional filepath to specify vcspull config",
    )
    parser.add_argument(
        "repo_patterns",
        metavar="filter",
        nargs="*",
        help="patterns / terms of repos, accepts globs / fnmatch(3)",
    )
    parser.add_argument(
        "--exit-on-error",
        "-x",
        action="store_true",
        dest="exit_on_error",
        help="exit immediately encountering error (when syncing multiple repos)",
    )

    try:
        import shtab

        config_file.complete = shtab.FILE  # type: ignore
    except ImportError:
        pass
    return parser


def sync(
    repo_patterns: t.List[str],
    config: pathlib.Path,
    exit_on_error: bool,
    parser: t.Optional[
        argparse.ArgumentParser
    ] = None,  # optional so sync can be unit tested
) -> None:
    if isinstance(repo_patterns, list) and len(repo_patterns) == 0:
        if parser is not None:
            parser.print_help()
        sys.exit(2)

    if config:
        configs = load_configs([config])
    else:
        configs = load_configs(find_config_files(include_home=True))
    found_repos = []

    for repo_pattern in repo_patterns:
        dir, vcs_url, name = None, None, None
        if any(repo_pattern.startswith(n) for n in ["./", "/", "~", "$HOME"]):
            dir = repo_pattern
        elif any(repo_pattern.startswith(n) for n in ["http", "git", "svn", "hg"]):
            vcs_url = repo_pattern
        else:
            name = repo_pattern

        # collect the repos from the config files
        found = filter_repos(configs, dir=dir, vcs_url=vcs_url, name=name)
        if len(found) == 0:
            print(NO_REPOS_FOR_TERM_MSG.format(name=name))
        found_repos.extend(filter_repos(configs, dir=dir, vcs_url=vcs_url, name=name))

    for repo in found_repos:
        try:
            update_repo(repo)
        except Exception:
            print(
                f'Failed syncing {repo.get("name")}',
            )
            if log.isEnabledFor(logging.DEBUG):
                import traceback

                traceback.print_exc()
            if exit_on_error:
                if parser is not None:
                    parser.exit(status=1, message=EXIT_ON_ERROR_MSG)
                else:
                    raise SystemExit(EXIT_ON_ERROR_MSG)


def progress_cb(output: str, timestamp: datetime) -> None:
    sys.stdout.write(output)
    sys.stdout.flush()


def guess_vcs(url: str) -> t.Optional[VCSLiteral]:
    vcs_matches = url_tools.registry.match(url=url, is_explicit=True)

    if len(vcs_matches) == 0:
        log.warning(f"No vcs found for {url}")
        return None
    if len(vcs_matches) > 1:
        log.warning(f"No exact matches for {url}")
        return None

    return t.cast(VCSLiteral, vcs_matches[0].vcs)


def update_repo(
    repo_dict: t.Any,
    # repo_dict: Dict[str, Union[str, Dict[str, GitRemote], pathlib.Path]]
) -> GitSync:
    repo_dict = deepcopy(repo_dict)
    if "pip_url" not in repo_dict:
        repo_dict["pip_url"] = repo_dict.pop("url")
    if "url" not in repo_dict:
        repo_dict["url"] = repo_dict.pop("pip_url")
    repo_dict["progress_callback"] = progress_cb

    if repo_dict.get("vcs") is None:
        vcs = guess_vcs(url=repo_dict["url"])
        if vcs is None:
            raise Exception(
                f'Could not automatically determine VCS for {repo_dict["url"]}'
            )

        repo_dict["vcs"] = vcs

    r = create_project(**repo_dict)  # Creates the repo object
    r.update_repo(set_remotes=True)  # Creates repo if not exists and fetches

    # TODO: Fix this
    return r  # type:ignore
