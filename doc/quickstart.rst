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

Now run the command, to pull all the repositories in your
``.vcspull.yaml`` / ``.vcspull.json``.

.. code-block:: bash

    $ vcspull

You can also use `fnmatch`_ to pull repositories from your config in
various fashions, e.g.:

.. code-block:: bash
   
   $ vcspull django
   $ vcspull django\*
   # or
   $ vcspull "django*"
   
Filter by vcs URL:

.. code-block:: bash
   
   # pull / update repositories I have with github in the repo url
   $ vcspull -r "*github*"

   # pull / update repositories I have with bitbucket in the repo url
   $ vcspull -r "*bitbucket*"
   
Filter by the path of the repo on your local machine:

.. code-block:: bash
   
   # pull all the repos I have inside of ~/study/python
   $ vcspull -d "$HOME/study/python"

   # pull all the repos I have in directories on my config with "python"
   $ vcspull -d "*python*"
   
Mix them all:

.. code-block:: bash
   
    # Repos with "python" in the name of the directory, on github.com,
    # with sql* in the name.
    $ vcspull -d "*python*" -r "*github.com*" "sql*"

.. _pip vcs url: http://www.pip-installer.org/en/latest/logic.html#vcs-support
.. _flask: http://flask.pocoo.org/
.. _fnmatch: http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html
