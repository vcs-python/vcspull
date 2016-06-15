``vcspull`` - vcs project manager

|pypi| |docs| |build-status| |coverage| |license|

.. image:: https://raw.github.com/tony/vcspull/master/doc/_static/vcspull-demo.gif
    :scale: 100%
    :width: 45%
    :align: center

add projects to ``~/.vcspull.yaml``

.. code-block:: yaml
   
    ~/code/:
      flask: "git+https://github.com/mitsuhiko/flask.git"
    ~/study/c:
      awesome: 'git+git://git.naquadah.org/awesome.git'
    ~/study/data-structures-algorithms/c:
      libds: 'git+https://github.com/zhemao/libds.git'
      algoxy: 
        repo: 'git+https://github.com/liuxinyu95/AlgoXY.git'
        remotes:
          tony: 'git+ssh://git@github.com/tony/AlgoXY.git'

see the author's `.vcspull.yaml`_, more `examples`_.

update your repos

.. code-block:: bash
    
    $ vcspull

keep nested VCS repositories updated too, lets say you have a mercurial or
svn project with a git dependency:

``external_deps.yaml`` in your project root, (can be anything):

.. code-block:: yaml

   ./vendor/:
     sdl2pp: 'git+https://github.com/libSDL2pp/libSDL2pp.git'

update::

    $ vcspull -c external_deps.yaml

filter through hundreds of repos
--------------------------------

supports `fnmatch`_ patterns

.. code-block:: bash

    # any repo starting with "fla"
    $ vcspull "fla*"
    # any repo with django in the name
    $ vcspull "*django*"

    # search by vcs + url
    # since urls are in this format <vcs>+<protocol>://<url>
    $ vcspull "git+*"

    # any git repo with python in the vcspull
    $ vcspull "git+*python*

    # any git repo with django in the vcs url
    $ vcspull "git+*django*"

    # all repositories in your ~/code directory
    vcspull "$HOME/code/*"
 
* supports svn, git, hg version control systems
* automatically checkout fresh repositories
* update to the latest repos with ``$ vcspull``
* `Documentation`_, `API`_ and `Examples`_.
* builds upon `pip`_'s `RFC3986`_-based `url scheme`_.

See the `Quickstart`_.
    
python API
----------

.. code-block:: python

   In [1]: from vcspull.repo import create_repo

   In [2]: r = create_repo(url='git+https://www.github.com/tony/myrepo', parent_dir='/tmp/',
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
.. _.vcspull.yaml: https://github.com/tony/.dot-config/blob/master/.vcspull.yaml
.. _examples: https://vcspull.readthedocs.io/en/latest/examples.html
.. _fnmatch: http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html

More information 
----------------

==============  ==========================================================
Python support  Python 2.7, >= 3.3
VCS supported   git(1), svn(1), hg(1)
Config formats  YAML, JSON, python dict
Source          https://github.com/tony/vcspull
Docs            http://vcspull.rtfd.org
Changelog       http://vcspull.readthedocs.io/en/latest/history.html
API             http://vcspull.readthedocs.io/en/latest/api.html
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
.. _Documentation: http://vcspull.readthedocs.io/en/latest/
.. _API: http://vcspull.readthedocs.io/en/latest/api.html
.. _Quickstart: http://vcspull.readthedocs.io/en/latest/quickstart.html
.. _pip: http://www.pip-installer.org/en/latest/
.. _url scheme: http://www.pip-installer.org/en/latest/logic.html#vcs-support
.. _saltstack: http://www.saltstack.org

.. |pypi| image:: https://img.shields.io/pypi/v/vcspull.svg
    :alt: Python Package
    :target: http://badge.fury.io/py/vcspull

.. |build-status| image:: https://img.shields.io/travis/tony/vcspull.svg
   :alt: Build Status
   :target: https://travis-ci.org/tony/vcspull

.. |coverage| image:: https://codecov.io/gh/tony/vcspull/branch/master/graph/badge.svg
    :alt: Code Coverage
    :target: https://codecov.io/gh/tony/vcspull
    
.. |license| image:: https://img.shields.io/github/license/tony/vcspull.svg
    :alt: License 

.. |docs| image:: https://readthedocs.org/projects/vcspull/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://readthedocs.org/projects/vcspull/
