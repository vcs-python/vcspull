.. _cli:

======================
Command Line Interface
======================

.. _bash_completion:

Bash completion
---------------

For bash, ``.bashrc``:

.. code-block:: bash

    $ source vcspull.bash

For tcsh, ``.tcshrc``:

.. code-block:: bash

    $ complete vcspull 'p/*/`tmuxp.tcsh`/'

For zsh, ``.zshrc``:

.. code-block:: bash

    $ source vcspull.zsh


Load config
-----------

.. argparse::
    :module: vcspull.cli
    :func: get_parser
    :prog: tmuxp
