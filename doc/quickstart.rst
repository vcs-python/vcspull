.. _quickstart:

Quickstart
==========

Installation
------------

First, install pullv.

For latest official version:

.. code-block:: bash

    $ pip install pullv

Development version:

.. code-block:: bash

    $ pip install -e git+https://github.com/tony/pullv.git#egg=pullv

Configuration
-------------

.. seealso:: :ref:`examples`.

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
