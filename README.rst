========
pullv(1)
========

.. figure:: http://github.com/tony/pullv/doc/_static/pullv-screenshot.png
    :scale: 100%
    :width: 65%
    :align: center

    Run ``svn update``, ``git pull``, ``hg pull && hg update`` en masse. 

Obtain and update multiple git, mercurial and subversions repositories
simultaneously.

* supports svn, git, hg version control systems
* automatically checkout fresh repositories
* update to the latest repos with ``$ pullv``

.. image:: https://travis-ci.org/tony/pullv.png?branch=master
    :target: https://travis-ci.org/tony/pullv

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
            shell_command_after: ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc
        .tmux:
            repo: git+git@github.com:tony/tmux-config.git
            shell_command_after:
                - ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf

Repo type and address is specified in `pip vcs url`_ format.

.. _pip vcs url: http://www.pip-installer.org/en/latest/logic.html#vcs-support

==============  ==========================================================
Travis          http://travis-ci.org/tony/pullv
Docs            http://pullv.rtfd.org
API             http://pullv.readthedocs.org/en/latest/api.html
Issues          https://github.com/tony/pullv/issues
Source          https://github.com/tony/pullv
License         `BSD`_.
VCS supported   git(1), svn(1), hg(1)
Config formats  YAML, JSON, INI, python dict
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
