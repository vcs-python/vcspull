#!/usr/bin/env python
# -*- coding: utf8 - *-
"""pullv lives at <https://github.com/tony/pullv>.

pullv
-----

Obtain and update multiple git, mercurial and subversions repositories
simultaneously.

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
VERSIONFILE = "pullv/__init__.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    __version__ = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

setup(
    name='pullv',
    version=__version__,
    url='http://github.com/tony/pullv/',
    download_url='https://pypi.python.org/pypi/pullv',
    license='BSD',
    author='Tony Narlock',
    author_email='tony@git-pull.com',
    description='Manage multiple git, mercurial and subversion '
                'repositories from a YAML / JSON file.',
    long_description=open('README.rst').read(),
    include_package_data=True,
    install_requires=install_reqs,
    tests_require=tests_reqs,
    test_suite='pullv.testsuite',
    zip_safe=False,
    packages=['pullv', 'pullv.testsuite', 'pullv.repo', 'pullv._vendor', 'pullv._vendor.colorama'],
    scripts=['pkg/pullv.bash', 'pkg/pullv.zsh', 'pkg/pullv.tcsh'],
    entry_points=dict(console_scripts=['pullv=pullv:cli.main']),
    classifiers=[
        'Development Status :: 3 - Alpha',
        "License :: OSI Approved :: BSD License",
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        "Topic :: Utilities",
        "Topic :: System :: Shells",
    ],
)
