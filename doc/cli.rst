.. _cli:

======================
Command Line Interface
======================

.. _bash_completion:

Bash completion
"""""""""""""""

For bash, ``.bashrc``:

.. code-block:: bash

    $ source pullv.bash

For tcsh, ``.tcshrc``:

.. code-block:: bash

    $ complete pullv 'p/*/`tmuxp.tcsh`/'

For zsh, ``.zshrc``:

.. code-block:: bash

    $ source pullv.zsh


Load config
"""""""""""

.. argparse::
    :module: pullv.cli
    :func: get_parser
    :prog: tmuxp
