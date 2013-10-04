#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv
    ~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""

from __future__ import absolute_import, division, print_function, with_statement
import collections
import os
import sys
import subprocess
import fnmatch
import logging
import urlparse
import re
import kaptan
from . import util
from . import log
from . import timed_subprocess
from .repo import Repo

__version__ = '0.1-dev'

logger = logging.getLogger('main')



def main():
    #logger.setLevel('INFO')
    #channel = logging.StreamHandler()
    #channel.setFormatter(log.LogFormatter())
    #logger.addHandler(channel)


    yaml_config = os.path.expanduser('~/.pullv.yaml')
    has_yaml_config = os.path.exists(yaml_config)
    json_config = os.path.expanduser('~/.pullv.json')
    has_json_config = os.path.exists(json_config)
    ini_config = os.path.expanduser('~/.pullv.ini')
    has_ini_config = os.path.exists(ini_config)
    if not has_yaml_config and not has_json_config and not has_ini_config:
        logger.fatal('No config file found. Create a .pullv.{yaml,ini,conf}'
                     ' in your $HOME directory. http://pullv.rtfd.org for a'
                     ' quickstart.')
    else:
        if sum(filter(None, [has_ini_config, has_json_config, has_yaml_config])) > int(1):
            sys.exit(
                'multiple configs found in home directory use only one.'
                ' .yaml, .json, .ini.'
            )

        config = kaptan.Kaptan()
        config.import_config(yaml_config)




        #logging.info('%r' % config.get())
        #logging.info('%r' % util.expand_config(config.get()))
        #logging.info('%r' % util.get_repos(util.expand_config(config.get())))

        for repo_dict in util.get_repos(util.expand_config(config.get())):
            r = Repo(repo_dict)
            #logger.info('%s' % r)
            r.update_repo()
