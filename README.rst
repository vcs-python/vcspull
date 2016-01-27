``vcspull`` - manage your git, mercurial and svn repositories via CLI.
Configure via JSON / YAML config files.

|pypi| |docs| |build-status| |coverage| |license|

.. image:: https://raw.github.com/tony/vcspull/master/doc/_static/vcspull-demo.gif
    :scale: 100%
    :width: 45%
    :align: center

Above: Run ``svn update``, ``git pull``, ``hg pull && hg update`` en masse. 

Sync multiple git, mercurial and subversion repositories via a YAML /
JSON file.

* supports svn, git, hg version control systems
* automatically checkout fresh repositories
* update to the latest repos with ``$ vcspull``
* `Documentation`_, `API`_ and `Examples`_.
* builds upon `pip`_'s `RFC3986`_-based `url scheme`_.

See the `Quickstart`_ to jump in. Or see an `example .vcspull.yaml`_.

Command line Usage
------------------

Create a ``.vcspull.yaml``:

.. code-block:: yaml
   
    ~/code/:
        "flask": "git+https://github.com/mitsuhiko/flask.git"

Clone and update your repositories at any time:

.. code-block:: bash
    
    $ vcspull
    
Have a lot of projects? Use arguments to clone / update what you need.

.. code-block:: bash
    
    $ vcspull flask
    
Use `fnmatch`_:

.. code-block:: bash

    # any repo starting with "fla"
    $ vcspull "fla*"
    
    # inside of a directory with "co" anywhere, on github.
    $ vcspull -d "*co*" -r "*github.com*" "fla*"

Python API Usage
----------------

.. code-block:: python

   In [1]: from vcspull.repo import create_repo

   In [2]: r = create_repo(url='git+https://www.github.com/tony/myrepo', cwd='/tmp/',
            name='myrepo')

   In [3]: r.update_repo()
   |myrepo| (git)  Repo directory for myrepo (git) does not exist @ /tmp/myrepo
   |myrepo| (git)  Cloning.
   |myrepo| (git)  git clone --progress https://www.github.com/tony/myrepo /tmp/myrepo
   Cloning into '/tmp/myrepo'...
   Checking connectivity... done.
   |myrepo| (git)  git fetch
   |myrepo| (git)  git pull
   Already up-to-date.

.. _RFC3986: http://tools.ietf.org/html/rfc3986.html
.. _example .vcspull.yaml: https://github.com/tony/.dot-config/blob/master/.vcspull.yaml
.. _fnmatch: http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html

More information 
----------------

==============  ==========================================================
Python support  Python 2.7, >= 3.3
VCS supported   git(1), svn(1), hg(1)
Config formats  YAML, JSON, python dict
Source          https://github.com/tony/vcspull
Docs            http://vcspull.rtfd.org
Changelog       http://vcspull.readthedocs.org/en/latest/history.html
API             http://vcspull.readthedocs.org/en/latest/api.html
Issues          https://github.com/tony/vcspull/issues
Travis          http://travis-ci.org/tony/vcspull
Test Coverage   https://coveralls.io/r/tony/vcspull
pypi            https://pypi.python.org/pypi/vcspull
Open Hub        https://www.openhub.net/p/vcspull
License         `BSD`_.
git repo        .. code-block:: bash

                    $ git clone https://github.com/tony/vcspull.git
install dev     .. code-block:: bash

                    $ git clone https://github.com/tony/vcspull.git vcspull
                    $ cd ./vcspull
                    $ virtualenv .venv
                    $ source .venv/bin/activate
                    $ pip install -e .
tests           .. code-block:: bash

                    $ python ./run-tests.py
run             .. code-block:: bash

                    $ vcspull
==============  ==========================================================

.. _BSD: http://opensource.org/licenses/BSD-3-Clause
.. _Documentation: http://vcspull.readthedocs.org/en/latest/
.. _API: http://vcspull.readthedocs.org/en/latest/api.html
.. _Examples: http://vcspull.readthedocs.org/en/latest/examples.html
.. _Quickstart: http://vcspull.readthedocs.org/en/latest/quickstart.html
.. _pip: http://www.pip-installer.org/en/latest/
.. _url scheme: http://www.pip-installer.org/en/latest/logic.html#vcs-support
.. _saltstack: http://www.saltstack.org

.. |pypi| image:: https://img.shields.io/pypi/v/vcspull.svg
    :alt: Python Package
    :target: http://badge.fury.io/py/vcspull

.. |build-status| image:: https://img.shields.io/travis/tony/vcspull.svg
   :alt: Build Status
   :target: https://travis-ci.org/tony/vcspull

.. |coverage| image:: https://img.shields.io/coveralls/tony/vcspull.svg
    :alt: Code Coverage
    :target: https://coveralls.io/r/tony/vcspull?branch=master
    
.. |license| image:: https://img.shields.io/github/license/tony/vcspull.svg
    :alt: License 

.. |docs| image:: https://readthedocs.org/projects/vcspull/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://readthedocs.org/projects/vcspull/
