#!/usr/bin/env python

import pathlib
import subprocess
import sys

vcspath_registry = {".git": "git", ".svn": "svn", ".hg": "hg"}


def find_repo_type(path):
    for path in list(pathlib.Path(path).parents) + [pathlib.Path(path)]:
        for p in path.iterdir():
            if p.is_dir():
                if p.name in vcspath_registry:
                    return vcspath_registry[p.name]


vcs_bin = find_repo_type(pathlib.Path.cwd())


def run(cmd=vcs_bin, cmd_args=sys.argv[1:], *args, **kwargs):
    proc = subprocess.Popen([cmd, *cmd_args])
    proc.communicate()
