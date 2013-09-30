`pullv`

Obtain and update multiple git, mercurial and subversions repositories
simultaneously.


.. image:: https://travis-ci.org/tony/pullv.png?branch=master
   :target: https://travis-ci.org/tony/pullv

use YAML, JSON, INI or python dict + `pip vcs url format`_ checkout + grab
the latest source to projects.

.. code-block:: yaml

    /home/user/study/:
        linux: git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
        freebsd: https://github.com/freebsd/freebsd.git
    /home/user/github_projects/:
        kaptan:
            repo: git@github.com:tony/kaptan.git
            remotes:
                upstream: https://github.com/emre/kaptan
                marksteve: https://github.com/marksteve/kaptan.git
    /home/tony/:
        .vim:
            repo: git@github.com:tony/vim-config.git
            after_shell_command: ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc
        .tmux: 
            repo: git@github.com:tony/tmux-config.git
            shell_command_after: ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf
            

.. _pip vcs url format: http://www.pip-installer.org/en/latest/logic.html#vcs-support


Not ready for public use.

===========     ==========================================================
Travis          http://travis-ci.org/tony/pullv
Docs            http://pullv.rtfd.org
API             http://pullv.readthedocs.org/en/latest/api.html
Issues          https://github.com/tony/pullv/issues
Source          https://github.com/tony/pullv
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
===========     ==========================================================

.. _BSD: http://opensource.org/licenses/BSD-3-Clause
