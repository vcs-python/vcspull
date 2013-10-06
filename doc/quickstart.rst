.. _quickstart:

Quickstart
==========

First, install pullv.

.. code-block:: bash

    $ pip install -e git+https://github.com/tony/pullv.git#egg=pullv

Prefer JSON? Create a ``~/.pullv.json`` file:

.. code-block:: json

    {
      "/home/<yourusername>/new/": {
        "amarok": "git+git://anongit.kde.org/amarok.git"
      }
    }

YAML? Create a ``~/.pullv.yaml`` file:

.. code-block:: yaml

    /home/<yourusername>/new/:
        "amarok": "git+git://anongit.kde.org/amarok.git"

The ``git+`` in front of the repository URL. Mercurial repositories use 
``hg+`` and Subversion will use ``svn+``.

Now run the command:

.. code-block:: bash

    $ pullv
