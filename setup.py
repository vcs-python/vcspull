#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""vcspull lives at <https://github.com/tony/vcspull>."""

import sys

from setuptools import setup
from setuptools.command.test import test as TestCommand

about = {}
with open("vcspull/__about__.py") as fp:
    exec(fp.read(), about)

with open('requirements/base.txt') as f:
    install_reqs = [line for line in f.read().split('\n') if line]

with open('requirements/test.txt') as f:
    tests_reqs = [line for line in f.read().split('\n') if line]

readme = open('README.rst').read()
history = open('CHANGES').read().replace('.. :changelog:', '')


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def run_tests(self):
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)

setup(
    name=about['__title__'],
    version=about['__version__'],
    url='http://github.com/tony/vcspull/',
    download_url='https://pypi.python.org/pypi/vcspull',
    license=about['__license__'],
    author=about['__author__'],
    author_email=about['__email__'],
    description=about['__description__'],
    long_description=readme,
    include_package_data=True,
    install_requires=install_reqs,
    tests_require=tests_reqs,
    cmdclass={'test': PyTest},
    zip_safe=False,
    keywords=about['__title__'],
    packages=[
        'vcspull',
        'vcspull.repo',
    ],
    entry_points=dict(console_scripts=['vcspull=vcspull:cli.cli']),
    classifiers=[
        'Development Status :: 4 - Beta',
        "License :: OSI Approved :: BSD License",
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        "Operating System :: POSIX",
        "Operating System :: MacOS :: MacOS X",
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        "Topic :: Utilities",
        "Topic :: System :: Shells",
    ],
)
