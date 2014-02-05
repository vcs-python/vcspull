#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""vcspull lives at <https://github.com/tony/vcspull>."""

import sys
import os
from setuptools import setup

sys.path.insert(0, os.getcwd())  # we want to grab this:
from package_metadata import p

with open('requirements.pip') as f:
    install_reqs = [line for line in f.read().split('\n') if line]
    tests_reqs = []

if sys.version_info < (2, 7):
    install_reqs += ['argparse']
    tests_reqs += ['unittest2']

readme = open('README.rst').read()
history = open('CHANGES').read().replace('.. :changelog:', '')

setup(
    name=p.title,
    version=p.version,
    url='http://github.com/tony/vcspull/',
    download_url='https://pypi.python.org/pypi/vcspull',
    license=p.license,
    author=p.author,
    author_email=p.email,
    description=p.description,
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    install_requires=install_reqs,
    tests_require=tests_reqs,
    test_suite='vcspull.testsuite',
    zip_safe=False,
    keywords=p.title,
    packages=['vcspull', 'vcspull.testsuite', 'vcspull.repo', 'vcspull._vendor', 'vcspull._vendor.colorama'],
    scripts=['pkg/vcspull.bash', 'pkg/vcspull.zsh', 'pkg/vcspull.tcsh'],
    entry_points=dict(console_scripts=['vcspull=vcspull:cli.main']),
    classifiers=[
        'Development Status :: 3 - Alpha',
        "License :: OSI Approved :: BSD License",
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        "Topic :: Utilities",
        "Topic :: System :: Shells",
    ],
)
