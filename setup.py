#!/usr/bin/env python
# -*- coding: utf8 - *-
"""vcspull lives at <https://github.com/tony/vcspull>.

vcspull
-------

Mass update git, hg and svn repos simultaneously from YAML / JSON file.

"""
import sys
from setuptools import setup

with open('requirements.pip') as f:
    install_reqs = [line for line in f.read().split('\n') if line]
    tests_reqs = []

if sys.version_info < (2, 7):
    install_reqs += ['argparse']
    tests_reqs += ['unittest2']

import re
VERSIONFILE = "vcspull/__init__.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    __version__ = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

setup(
    name='vcspull',
    version=__version__,
    url='http://github.com/tony/vcspull/',
    download_url='https://pypi.python.org/pypi/vcspull',
    license='BSD',
    author='Tony Narlock',
    author_email='tony@git-pull.com',
    description='Mass update git, hg and svn repos simultaneously from '
                'YAML / JSON file.',
    long_description=open('README.rst').read(),
    include_package_data=True,
    install_requires=install_reqs,
    tests_require=tests_reqs,
    test_suite='vcspull.testsuite',
    zip_safe=False,
    packages=['vcspull', 'vcspull.testsuite', 'vcspull.repo', 'vcspull._vendor', 'vcspull._vendor.colorama'],
    scripts=['pkg/vcspull.bash', 'pkg/vcspull.zsh', 'pkg/vcspull.tcsh'],
    entry_points=dict(console_scripts=['vcspull=vcspull:cli.main']),
    classifiers=[
        'Development Status :: 3 - Alpha',
        "License :: OSI Approved :: BSD License",
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        "Topic :: Utilities",
        "Topic :: System :: Shells",
    ],
)
