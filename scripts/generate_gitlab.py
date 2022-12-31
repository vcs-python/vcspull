#!/usr/bin/env python

import argparse
import os
import sys

import requests
import yaml

from libvcs.sync.git import GitRemote
from vcspull.cli.sync import guess_vcs
from vcspull.types import RawConfig

try:
    gitlab_token = os.environ["GITLAB_TOKEN"]
except KeyError:
    print("Please provide the environment variable GITLAB_TOKEN")
    sys.exit(1)

parser = argparse.ArgumentParser(
    description="Script to generate vcsconfig for all repositories \
    under the given namespace (needs Gitlab >= 10.3)"
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
config_filename = args["config_file_name"]

try:
    if os.path.isfile(config_filename):
        result = input(
            "The target config file (%s) already exists, \
            do you want to overwrite it? [y/N] "
            % (config_filename)
        )

        if result != "y":
            print(
                "Aborting per user request as existing config file (%s) \
                should not be overwritten!"
                % (config_filename)
            )
            sys.exit(0)

    config_file = open(config_filename, "w")
except IOError:
    print("File %s not accesible" % (config_filename))
    sys.exit(1)

response = requests.get(
    "%s/api/v4/groups/%s/projects" % (gitlab_host, gitlab_namespace),
    params={"include_subgroups": "true", "per_page": "100"},
    headers={"Authorization": "Bearer %s" % (gitlab_token)},
)

if 200 != response.status_code:
    print("Error: ", response)
    sys.exit(1)

path_prefix = os.getcwd()
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
        raise Exception(f"Could not guess VCS for URL: {url_to_repo}")

    config[path][reponame] = {
        "name": reponame,
        "dir": path / reponame,
        "url": f"git+ssh://{url_to_repo}",
        "remotes": {
            "origin": GitRemote(
                name="origin",
                fetch_url=f"ssh://{url_to_repo}",
                push_url=f"ssh://{url_to_repo}",
            )
        },
        "vcs": vcs,
    }

config_yaml = yaml.dump(config)

print(config_yaml)

config_file.write(config_yaml)
config_file.close()
