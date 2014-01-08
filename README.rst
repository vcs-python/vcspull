``vcspull`` - mass-update vcs from JSON / YAML config files.

.. image:: https://travis-ci.org/tony/vcspull.png?branch=master
    :target: https://travis-ci.org/tony/vcspull

.. image:: https://badge.fury.io/py/vcspull.png
    :target: http://badge.fury.io/py/vcspull

.. image:: https://coveralls.io/repos/tony/vcspull/badge.png?branch=master
    :target: https://coveralls.io/r/tony/vcspull?branch=master

.. figure:: https://raw.github.com/tony/vcspull/master/doc/_static/vcspull-screenshot.png
    :scale: 100%
    :width: 45%
    :align: center

    Run ``svn update``, ``git pull``, ``hg pull && hg update`` en masse. 

Sync multiple git, mercurial and subversions repositories via a YAML /
JSON file.

* supports svn, git, hg version control systems
* automatically checkout fresh repositories
* update to the latest repos with ``$ vcspull``
* `Documentation`_, `API`_ and `Examples`_.
* vcspull builds upon `pip`_'s `RFC3986`_-based `url scheme`_.

See the `Quickstart`_ to jump in.

**Current Limitations:**

- Main repo URL may not be ``git+ssh`` format. For a workaround, add
  ``git+ssh`` server as remotes and use a public include. See `remote git
  repo example`_ in the docs.
- Support for ``svn`` username and password.

.. _remote git repo example: http://vcspull.readthedocs.org/en/latest/examples.html#remote-git-repositories-and-ssh-git
.. _RFC3986: http://tools.ietf.org/html/rfc3986.html

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
Ohloh           https://www.ohloh.net/p/vcspull
License         `BSD`_.
git repo        .. code-block:: bash

                    $ git clone https://github.com/tony/vcspull.git
install dev     .. code-block:: bash

                    $ git clone https://github.com/tony/vcspull.git vcspull
                    $ cd ./vcspull
                    $ virtualenv .env
                    $ source .env/bin/activate
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
