``pullv`` - mass-update vcs from JSON / YAML config files.

.. image:: https://travis-ci.org/tony/pullv.png?branch=master
    :target: https://travis-ci.org/tony/pullv

.. image:: https://badge.fury.io/py/pullv.png
    :target: http://badge.fury.io/py/pullv

.. figure:: https://raw.github.com/tony/pullv/master/doc/_static/pullv-screenshot.png
    :scale: 100%
    :width: 45%
    :align: center

    Run ``svn update``, ``git pull``, ``hg pull && hg update`` en masse. 

Sync multiple git, mercurial and subversions repositories via a YAML /
JSON file.

* supports svn, git, hg version control systems
* automatically checkout fresh repositories
* update to the latest repos with ``$ pullv``
* `Documentation`_, `API`_ and `Examples`_.

See the `Quickstart`_ to jump in.

**Current Limitations:**

- Main repo URL may not be ``git+ssh`` format. For a workaround, add
  ``git+ssh`` server as remotes and use a public include. See `remote git
  repo example`_ in the docs.
- Support for ``svn`` username and password.

.. _remote git repo example: http://pullv.readthedocs.org/en/latest/examples.html#remote-git-repositories-and-ssh-git

==============  ==========================================================
Python support  Python 2.6, 2.7 (3.3 in development)
VCS supported   git(1), svn(1), hg(1)
Config formats  YAML, JSON, python dict
Travis          http://travis-ci.org/tony/pullv
Crate.io        https://crate.io/packages/pullv/
Source          https://github.com/tony/pullv
Docs            http://pullv.rtfd.org
API             http://pullv.readthedocs.org/en/latest/api.html
Issues          https://github.com/tony/pullv/issues
pypi            https://pypi.python.org/pypi/pullv
Crate.io        https://crate.io/packages/pullv/
Ohloh           https://www.ohloh.net/p/pullv
License         `BSD`_.
git repo        .. code-block:: bash

                    $ git clone https://github.com/tony/pullv.git
install dev     .. code-block:: bash

                    $ git clone https://github.com/tony/pullv.git pullv
                    $ cd ./pullv
                    $ virtualenv .env
                    $ source .env/bin/activate
                    $ pip install -e .
tests           .. code-block:: bash

                    $ python ./run_tests.py
run             .. code-block:: bash

                    $ pullv
==============  ==========================================================

.. _BSD: http://opensource.org/licenses/BSD-3-Clause
.. _Documentation: http://pullv.readthedocs.org/en/latest/
.. _API: http://pullv.readthedocs.org/en/latest/api.html
.. _Examples: http://pullv.readthedocs.org/en/latest/examples.html
.. _Quickstart: http://pullv.readthedocs.org/en/latest/quickstart.html
