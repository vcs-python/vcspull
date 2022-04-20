import logging
import sys
from copy import deepcopy

import click
import click.shell_completion

from libvcs.shortcuts import create_repo_from_pip_url

from ..config import filter_repos, find_config_files, load_configs
from ..log import setup_logger

MIN_ASYNC = 3  # minimum amount of repos to sync concurrently
MAX_ASYNC = 8  # maximum processes to open:w

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
    "--run-async",
    "-a",
    is_flag=True,
    help="Run repo syncing concurrently (experimental)",
)
@click.option(
    "--log-level",
    default="INFO",
    help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.option(
    "config",
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Specify config",
    shell_complete=get_config_file_completions,
)
def sync(repo_terms, run_async, log_level, config):
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

    found_repos_n = len(found_repos)
    # turn them into :class:`Repo` objects and clone/update them
    if run_async and found_repos_n >= MIN_ASYNC:
        from multiprocessing import Pool

        p = Pool(clamp(found_repos_n, MIN_ASYNC, MAX_ASYNC))
        p.map_async(update_repo, found_repos).get()
    else:
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

    remote_settings = repo_dict.get("remotes", {})
    if remote_settings.get("origin", {}) == {}:
        from libvcs.git import GitRemote

        remote_settings["origin"] = GitRemote(
            name="origin",
            push_url=repo_dict["pip_url"],
            fetch_url=repo_dict["pip_url"],
        )

    remotes_updated = False
    r.update_repo()  # Creates repo if not exists and fetches

    for remote_name, remote_setting in remote_settings.items():
        config_remote_name = remote_name  # From config file
        try:
            current_remote = r.remote(config_remote_name)
        except FileNotFoundError:  # git repo doesn't exist yet, so cna't be outdated
            break

        current_fetch_url = (
            current_remote.fetch_url if current_remote is not None else None
        )

        if current_remote is None or current_fetch_url != remote_setting.fetch_url:
            print(
                "Updating remote {name} ({current_url}) with {new_url}".format(
                    name=config_remote_name,
                    current_url=current_fetch_url,
                    new_url=remote_setting.fetch_url,
                )
            )
            r.set_remote(
                name=config_remote_name, url=remote_setting.fetch_url, overwrite=True
            )
            remotes_updated = True

    if remotes_updated:  # Fetch again since we added / changed remotes
        r.update_repo()
    return r
