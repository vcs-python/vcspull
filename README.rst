========
pullv(1)
========

.. image:: https://travis-ci.org/tony/pullv.png?branch=master
    :target: https://travis-ci.org/tony/pullv

.. figure:: https://raw.github.com/tony/pullv/master/doc/_static/pullv-screenshot.png
    :scale: 100%
    :width: 65%
    :align: center

    Run ``svn update``, ``git pull``, ``hg pull && hg update`` en masse. 

Sync multiple git, mercurial and subversions repositories via a YAML /
JSON file.

* supports svn, git, hg version control systems
* automatically checkout fresh repositories
* update to the latest repos with ``$ pullv``

YAML config at ``~/.pullv.yaml``:

.. code-block:: yaml

    /home/user/study/:
        linux: git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
        freebsd: git+https://github.com/freebsd/freebsd.git
        sphinx: hg+https://bitbucket.org/birkenfeld/sphinx
        docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
    /home/user/github_projects/:
        kaptan:
            repo: git+git@github.com:tony/kaptan.git
            remotes:
                upstream: git+https://github.com/emre/kaptan
                marksteve: git+https://github.com/marksteve/kaptan.git
    /home/user/:
        .vim:
            repo: git+git@github.com:tony/vim-config.git
        .tmux:
            repo: git+git@github.com:tony/tmux-config.git

Repo type and address is specified in `pip vcs url`_ format.

.. _pip vcs url: http://www.pip-installer.org/en/latest/logic.html#vcs-support

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
