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

install
"""""""

.. code-block:: sh

    $ pip install --user vcspull

configure
"""""""""

add repos you want vcspull to manage to ``~/.vcspull.yaml``.

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
"""""""""""""""""""""""""

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
""""""""""""""""""""""

have a lot of repos?

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

.. image:: https://raw.github.com/vcs-python/vcspull/master/doc/_static/vcspull-demo.gif
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
- Python support: >= 3.6, pypy
- VCS supported: git(1), svn(1), hg(1)
- Source: https://github.com/vcs-python/vcspull
- Docs: https://vcspull.git-pull.com
- Changelog: https://vcspull.git-pull.com/history.html
- API: https://vcspull.git-pull.com/api.html
- Issues: https://github.com/vcs-python/vcspull/issues
- Test Coverage: https://codecov.io/gh/vcs-python/vcspull
- pypi: https://pypi.python.org/pypi/vcspull
- Open Hub: https://www.openhub.net/p/vcspull
- License: `MIT`_.

.. _MIT: https://opensource.org/licenses/MIT
.. _Documentation: https://vcspull.git-pull.com/
.. _Quickstart: https://vcspull.git-pull.com/quickstart.html
.. _pip: http://www.pip-installer.org/
.. _url scheme: http://www.pip-installer.org/logic.html#vcs-support
.. _libvcs: https://github.com/vcs-python/libvcs
.. _RFC3986: http://tools.ietf.org/html/rfc3986.html
.. _.vcspull.yaml: https://github.com/tony/.dot-config/blob/master/.vcspull.yaml
.. _examples: https://vcspull.git-pull.com/examples.html
.. _fnmatch: http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html

.. |pypi| image:: https://img.shields.io/pypi/v/vcspull.svg
    :alt: Python Package
    :target: http://badge.fury.io/py/vcspull

.. |docs| image:: https://github.com/vcs-python/vcspull/workflows/Publish%20Docs/badge.svg
   :alt: Docs
   :target: https://github.com/vcs-python/vcspull/actions?query=workflow%3A"Publish+Docs"

.. |build-status| image:: https://github.com/vcs-python/vcspull/workflows/tests/badge.svg
   :alt: Build Status
   :target: https://github.com/vcs-python/vcspull/actions?query=workflow%3A"tests"

.. |coverage| image:: https://codecov.io/gh/vcs-python/vcspull/branch/master/graph/badge.svg
    :alt: Code Coverage
    :target: https://codecov.io/gh/vcs-python/vcspull
    
.. |license| image:: https://img.shields.io/github/license/vcs-python/vcspull.svg
    :alt: License 
