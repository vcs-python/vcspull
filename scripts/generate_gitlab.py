#!/usr/bin/env python
"""Example script for export gitlab organization to vcspull config file."""

import argparse
import logging
import os
import pathlib
import sys

import requests
import yaml
from libvcs.sync.git import GitRemote

from vcspull.cli.sync import CouldNotGuessVCSFromURL, guess_vcs
from vcspull.types import RawConfig

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

try:
    gitlab_token = os.environ["GITLAB_TOKEN"]
except KeyError:
    log.info("Please provide the environment variable GITLAB_TOKEN")
    sys.exit(1)

parser = argparse.ArgumentParser(
    description="Script to generate vcsconfig for all repositories \
    under the given namespace (needs Gitlab >= 10.3)",
)
parser.add_argument("gitlab_host", type=str, help="url to the gitlab instance")
parser.add_argument(
    "gitlab_namespace",
    type=str,
    help="namespace/group in gitlab to generate vcsconfig for",
)
parser.add_argument(
    "-c",
    type=str,
    help="path to the target config file (default: ./vcspull.yaml)",
    dest="config_file_name",
    required=False,
    default="./vcspull.yaml",
)

args = vars(parser.parse_args())
gitlab_host = args["gitlab_host"]
gitlab_namespace = args["gitlab_namespace"]
config_filename = pathlib.Path(args["config_file_name"])

try:
    if config_filename.is_file():
        result = input(
            f"The target config file ({config_filename}) already exists, \
            do you want to overwrite it? [y/N] ",
        )

        if result != "y":
            log.info(
                f"Aborting per user request as existing config file ({config_filename})"
                + " should not be overwritten!",
            )
            sys.exit(0)

    config_file = config_filename.open(mode="w")
except OSError:
    log.info(f"File {config_filename} not accessible")
    sys.exit(1)

response = requests.get(
    f"{gitlab_host}/api/v4/groups/{gitlab_namespace}/projects",
    params={"include_subgroups": "true", "per_page": "100"},
    headers={"Authorization": f"Bearer {gitlab_token}"},
)

if response.status_code != 200:
    log.info(f"Error: {response}")
    sys.exit(1)

path_prefix = pathlib.Path().cwd()
config: RawConfig = {}


for group in response.json():
    url_to_repo = group["ssh_url_to_repo"].replace(":", "/")
    namespace_path = group["namespace"]["full_path"]
    reponame = group["path"]

    path = f"{path_prefix}/{namespace_path}"

    if path not in config:
        config[path] = {}

    # simplified config not working - https://github.com/vcs-python/vcspull/issues/332
    # config[path][reponame] = 'git+ssh://%s' % (url_to_repo)

    vcs = guess_vcs(url_to_repo)
    if vcs is None:
        raise CouldNotGuessVCSFromURL(url_to_repo)

    config[path][reponame] = {
        "name": reponame,
        "path": path / reponame,
        "url": f"git+ssh://{url_to_repo}",
        "remotes": {
            "origin": GitRemote(
                name="origin",
                fetch_url=f"ssh://{url_to_repo}",
                push_url=f"ssh://{url_to_repo}",
            ),
        },
        "vcs": vcs,
    }

config_yaml = yaml.dump(config)

log.info(config_yaml)

config_file.write(config_yaml)
config_file.close()
