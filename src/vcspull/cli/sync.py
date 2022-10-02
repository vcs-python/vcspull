import argparse
import logging
import sys
import typing as t
from copy import deepcopy

from libvcs._internal.shortcuts import create_project
from libvcs.url import registry as url_tools

from ..config import filter_repos, find_config_files, load_configs

log = logging.getLogger(__name__)


def clamp(n, _min, _max):
    return max(_min, min(n, _max))


EXIT_ON_ERROR_MSG = "Exiting via error (--exit-on-error passed)"
NO_REPOS_FOR_TERM_MSG = 'No repo found in config(s) for "{name}"'


def create_sync_subparser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--config", "-c", help="Specify config")
    parser.add_argument(
        "repo_terms",
        nargs="+",
        help="Filters of repo terms, separated by spaces, supports globs / fnmatch (1)",
    )
    parser.add_argument(
        "--exit-on-error",
        "-x",
        action="store_true",
        dest="exit_on_error",
        help="Exit immediately when encountering an error syncing multiple repos",
    )
    return parser


def sync(
    repo_terms,
    config,
    exit_on_error: bool,
    parser: t.Optional[
        argparse.ArgumentParser
    ] = None,  # optional so sync can be unit tested
) -> None:
    if config:
        configs = load_configs([config])
    else:
        configs = load_configs(find_config_files(include_home=True))
    found_repos = []

    for repo_term in repo_terms:
        dir, vcs_url, name = None, None, None
        if any(repo_term.startswith(n) for n in ["./", "/", "~", "$HOME"]):
            dir = repo_term
        elif any(repo_term.startswith(n) for n in ["http", "git", "svn", "hg"]):
            vcs_url = repo_term
        else:
            name = repo_term

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


def progress_cb(output, timestamp):
    sys.stdout.write(output)
    sys.stdout.flush()


def update_repo(repo_dict):
    repo_dict = deepcopy(repo_dict)
    if "pip_url" not in repo_dict:
        repo_dict["pip_url"] = repo_dict.pop("url")
    if "url" not in repo_dict:
        repo_dict["url"] = repo_dict.pop("pip_url")
    repo_dict["progress_callback"] = progress_cb

    if repo_dict.get("vcs") is None:
        vcs_matches = url_tools.registry.match(url=repo_dict["url"], is_explicit=True)

        if len(vcs_matches) == 0:
            raise Exception(f"No vcs found for {repo_dict}")
        if len(vcs_matches) > 1:
            raise Exception(f"No exact matches for {repo_dict}")

        repo_dict["vcs"] = vcs_matches[0].vcs

    r = create_project(**repo_dict)  # Creates the repo object
    r.update_repo(set_remotes=True)  # Creates repo if not exists and fetches

    return r
