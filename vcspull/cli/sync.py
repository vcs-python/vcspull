import logging
import sys
from copy import deepcopy

import click
import click.shell_completion

from libvcs.shortcuts import create_repo_from_pip_url

from ..config import filter_repos, find_config_files, load_configs
from ..log import setup_logger

log = logging.getLogger(__name__)


def get_repo_completions(ctx: click.core.Context, args, incomplete):
    configs = load_configs(find_config_files(include_home=True))
    found_repos = []
    repo_terms = [incomplete]

    for repo_term in repo_terms:
        repo_dir, vcs_url, name = None, None, None
        if any(repo_term.startswith(n) for n in ["./", "/", "~", "$HOME"]):
            repo_dir = repo_term
        elif any(repo_term.startswith(n) for n in ["http", "git", "svn", "hg"]):
            vcs_url = repo_term
        else:
            name = repo_term

        # collect the repos from the config files
        found_repos.extend(
            filter_repos(configs, repo_dir=repo_dir, vcs_url=vcs_url, name=name)
        )
    if len(found_repos) == 0:
        found_repos = configs

    return [o["name"] for o in found_repos if o["name"].startswith(incomplete)]


def get_config_file_completions(ctx, args, incomplete):
    return [
        click.shell_completion.CompletionItem(c)
        for c in find_config_files(include_home=True)
        if c.startswith(incomplete)
    ]


def clamp(n, _min, _max):
    return max(_min, min(n, _max))


@click.command(name="sync")
@click.argument(
    "repo_terms", type=click.STRING, nargs=-1, shell_complete=get_repo_completions
)
@click.option(
    "--log-level",
    default="INFO",
    help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.option(
    "config",
    "-c",
    type=click.Path(exists=True),
    help="Specify config",
    shell_complete=get_config_file_completions,
)
def sync(repo_terms, log_level, config):
    setup_logger(log=log, level=log_level.upper())

    if config:
        configs = load_configs([config])
    else:
        configs = load_configs(find_config_files(include_home=True))
    found_repos = []

    if repo_terms:
        for repo_term in repo_terms:
            repo_dir, vcs_url, name = None, None, None
            if any(repo_term.startswith(n) for n in ["./", "/", "~", "$HOME"]):
                repo_dir = repo_term
            elif any(repo_term.startswith(n) for n in ["http", "git", "svn", "hg"]):
                vcs_url = repo_term
            else:
                name = repo_term

            # collect the repos from the config files
            found_repos.extend(
                filter_repos(configs, repo_dir=repo_dir, vcs_url=vcs_url, name=name)
            )
    else:
        found_repos = configs

    list(map(update_repo, found_repos))


def progress_cb(output, timestamp):
    sys.stdout.write(output)
    sys.stdout.flush()


def update_repo(repo_dict):
    repo_dict = deepcopy(repo_dict)
    if "pip_url" not in repo_dict:
        repo_dict["pip_url"] = repo_dict.pop("url")
    repo_dict["progress_callback"] = progress_cb

    r = create_repo_from_pip_url(**repo_dict)  # Creates the repo object
    r.update_repo(set_remotes=True)  # Creates repo if not exists and fetches

    return r
