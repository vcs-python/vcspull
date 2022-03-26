import logging
import os
import sys

import click
import click.shell_completion

from libvcs.projects.base import BaseProject
from libvcs.projects.constants import DEFAULT_VCS_CLASS_MAP

from ..config import filter_repos, find_config_files, load_configs

log = logging.getLogger(__name__)


def get_repo_completions(ctx: click.core.Context, args, incomplete):
    configs = (
        load_configs(find_config_files(include_home=True))
        if ctx.params["config"] is None
        else load_configs(files=[ctx.params["config"]])
    )
    found_repos = []
    repo_terms = [incomplete]

    for repo_term in repo_terms:
        repo_dir, name = None, None
        if any(repo_term.startswith(n) for n in ["./", "/", "~", "$HOME"]):
            repo_dir = repo_term
        else:
            name = repo_term

        # collect the repos from the config files
        found_repos.extend(
            filter_repos(
                configs,
                filter_repo_dir=repo_dir,
                filter_name=name,
            )
        )
    if len(found_repos) == 0:
        found_repos = configs

    return [o["name"] for o in found_repos if o["name"].startswith(incomplete)]


def get_config_file_completions(ctx, args, incomplete):
    return [
        click.shell_completion.CompletionItem(c)
        for c in find_config_files(include_home=True)
        if str(c).startswith(incomplete)
    ]


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
def sync(repo_terms, config):
    if config:
        configs = load_configs([config])
    else:
        configs = load_configs(find_config_files(include_home=True))

    found_repos = {}

    if repo_terms:
        for repo_term in repo_terms:
            repo_dir, name = None, None

            if any(repo_term.startswith(n) for n in ["./", "/", "~", "$HOME"]):
                repo_dir = repo_term
            else:
                name = repo_term

            # collect the repos from the config files
            found_repos |= filter_repos(
                configs,
                filter_repo_dir=repo_dir,
                filter_name=name,
            )
    else:
        found_repos = configs

    for path, repos in found_repos.items():
        for name, repo in repos.items():
            r: BaseProject = DEFAULT_VCS_CLASS_MAP[repo["vcs"]](
                repo_dir=os.path.join(path, name),
                options=repo["options"],
                progress_callback=progress_cb,
            )
            r.update_repo(set_remotes=True)


def progress_cb(output, timestamp):
    sys.stdout.write(output)
    sys.stdout.flush()
