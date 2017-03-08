``vcspull`` - synchronize your repos. built on `libvcs`_

|pypi| |docs| |build-status| |coverage| |license|

Manage your commonly used repos from YAML / JSON manifest(s).
Compare to `myrepos`_.

Great if you use the same repos at the same locations across multiple
machines or want to clone / update a pattern of repos without having
to ``cd`` into each one.

* clone  /update to the latest repos with ``$ vcspull``
* use filters to specify a location, repo url or pattern
  in the manifest to clone / update
* supports svn, git, hg version control systems
* automatically checkout fresh repositories
* `Documentation`_  and `Examples`_.
* supports `pip`_-style URL's (`RFC3986`_-based `url scheme`_)

.. _myrepos: http://myrepos.branchable.com/

how to
------

add repos to ``~/.vcspull.yaml`` manifest first.

*vcspull does not currently scan for repos on your system, but it may in
the future*

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

(see the author's `.vcspull.yaml`_, more `examples`_.)

next, on other machines, copy your ``$HOME/.vcspull.yaml`` file
or ``$HOME/.vcspull/`` directory them and you can clone your repos
consistently. vcspull automatically handles building nested
directories. Updating already cloned/checked out repos is done
automatically if they already exist.

clone / update your repos

.. code-block:: bash
    
    $ vcspull

keep nested VCS repositories updated too, lets say you have a mercurial or
svn project with a git dependency:

``external_deps.yaml`` in your project root, (can be anything):

.. code-block:: yaml

   ./vendor/:
     sdl2pp: 'git+https://github.com/libSDL2pp/libSDL2pp.git'

clone / update repos::

    $ vcspull -c external_deps.yaml

See the `Quickstart`_ for more.

pulling specific repos
----------------------

you can choose to update only select repos through `fnmatch`_ patterns.
remember to add the repos to your ``~/.vcspull.{json,yaml}`` first.

The patterns can be filtered by by directory, repo name or vcs url.

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
    $ vcspull "$HOME/code/*"

.. image:: https://raw.github.com/tony/vcspull/master/doc/_static/vcspull-demo.gif
    :scale: 100%
    :width: 45%
    :align: center

Donations
---------

Your donations fund development of new features, testing and support.
Your money will go directly to maintenance and development of the project.
If you are an individual, feel free to give whatever feels right for the
value you get out of the project.

See donation options at https://git-pull.com/support.html.

More information 
----------------

==============  ==========================================================
Python support  Python 2.7, >= 3.3
VCS supported   git(1), svn(1), hg(1)
Config formats  YAML, JSON, python dict
Source          https://github.com/tony/vcspull
Docs            http://vcspull.git-pull.com
Changelog       http://vcspull.git-pull.com/en/latest/history.html
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

                    $ py.test
run             .. code-block:: bash

                    $ vcspull
==============  ==========================================================

.. _BSD: http://opensource.org/licenses/BSD-3-Clause
.. _Documentation: http://vcspull.git-pull.com/en/latest/
.. _Quickstart: http://vcspull.git-pull.com/en/latest/quickstart.html
.. _pip: http://www.pip-installer.org/en/latest/
.. _url scheme: http://www.pip-installer.org/en/latest/logic.html#vcs-support
.. _libvcs: https://github.com/tony/libvcs
.. _RFC3986: http://tools.ietf.org/html/rfc3986.html
.. _.vcspull.yaml: https://github.com/tony/.dot-config/blob/master/.vcspull.yaml
.. _examples: https://vcspull.git-pull.com/en/latest/examples.html
.. _fnmatch: http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html

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
