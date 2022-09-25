import logging
import sys
from copy import deepcopy

import click
import click.shell_completion
from click.shell_completion import CompletionItem

from libvcs._internal.shortcuts import create_project
from libvcs.url import registry as url_tools
from vcspull.types import ConfigDict

from ..config import filter_repos, find_config_files, load_configs

log = logging.getLogger(__name__)


def get_repo_completions(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    configs = (
        load_configs(find_config_files(include_home=True))
        if ctx.params["config"] is None
        else load_configs(files=[ctx.params["config"]])
    )
    found_repos: list[ConfigDict] = []
    repo_terms = [incomplete]

    for repo_term in repo_terms:
        dir, vcs_url, name = None, None, None
        if any(repo_term.startswith(n) for n in ["./", "/", "~", "$HOME"]):
            dir = dir
        elif any(repo_term.startswith(n) for n in ["http", "git", "svn", "hg"]):
            vcs_url = repo_term
        else:
            name = repo_term

        # collect the repos from the config files
        found_repos.extend(filter_repos(configs, dir=dir, vcs_url=vcs_url, name=name))
    if len(found_repos) == 0:
        found_repos = configs

    return [
        CompletionItem(o["name"])
        for o in found_repos
        if o["name"].startswith(incomplete)
    ]


def get_config_file_completions(ctx, args, incomplete):
    return [
        click.shell_completion.CompletionItem(c)
        for c in find_config_files(include_home=True)
        if str(c).startswith(incomplete)
    ]


def clamp(n, _min, _max):
    return max(_min, min(n, _max))


EXIT_ON_ERROR_MSG = "Exiting via error (--exit-on-error passed)"


@click.command(name="sync")
@click.argument(
    "repo_terms", type=click.STRING, nargs=-1, shell_complete=get_repo_completions
)
@click.option(
    "config",
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Specify config",
    shell_complete=get_config_file_completions,
)
@click.option(
    "exit_on_error",
    "--exit-on-error",
    "-x",
    is_flag=True,
    default=False,
    help="Exit immediately when encountering an error syncing multiple repos",
)
def sync(repo_terms, config, exit_on_error: bool) -> None:
    if config:
        configs = load_configs([config])
    else:
        configs = load_configs(find_config_files(include_home=True))
    found_repos = []

    if repo_terms:
        for repo_term in repo_terms:
            dir, vcs_url, name = None, None, None
            if any(repo_term.startswith(n) for n in ["./", "/", "~", "$HOME"]):
                dir = repo_term
            elif any(repo_term.startswith(n) for n in ["http", "git", "svn", "hg"]):
                vcs_url = repo_term
            else:
                name = repo_term

            # collect the repos from the config files
            found_repos.extend(
                filter_repos(configs, dir=dir, vcs_url=vcs_url, name=name)
            )
    else:
        found_repos = configs

    for repo in found_repos:
        try:
            update_repo(repo)
        except Exception:
            click.echo(
                f'Failed syncing {repo.get("name")}',
            )
            if log.isEnabledFor(logging.DEBUG):
                import traceback

                traceback.print_exc()
            if exit_on_error:
                raise click.ClickException(EXIT_ON_ERROR_MSG)


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
