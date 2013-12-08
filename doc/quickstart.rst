.. _quickstart:

==========
Quickstart
==========

Installation
------------

First, install vcspull.

For latest official version:

.. code-block:: bash

    $ pip install vcspull

Development version:

.. code-block:: bash

    $ pip install -e git+https://github.com/tony/vcspull.git#egg=vcspull

Configuration
-------------

.. seealso:: :ref:`examples`.

We will check out the source code of `flask`_ to ``~/code/flask``.

Prefer JSON? Create a ``~/.vcspull.json`` file:

.. code-block:: json

    {
      "~/code/": {
        "flask": "git+https://github.com/mitsuhiko/flask.git"
      }
    }

YAML? Create a ``~/.vcspull.yaml`` file:

.. code-block:: yaml

    ~/code/:
        "flask": "git+https://github.com/mitsuhiko/flask.git"

The ``git+`` in front of the repository URL. Mercurial repositories use 
``hg+`` and Subversion will use ``svn+``. Repo type and address is
specified in `pip vcs url`_ format.

Now run the command:

.. code-block:: bash

    $ vcspull

.. _pip vcs url: http://www.pip-installer.org/en/latest/logic.html#vcs-support
.. _flask: http://flask.pocoo.org/
