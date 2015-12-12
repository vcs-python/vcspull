.. _developing:

===========
Development
===========

Testing
-------

Tests are inside ``./vcspull/testsuite``. Tests are implemented using
:py:mod:`unittest`.

.. _install_dev_env:

Install the latest code from git
--------------------------------

To begin developing, check out the code from github:

.. code-block:: sh

    $ git clone git@github.com:tony/vcspull.git
    $ cd vcspull

Now create a virtualenv, if you don't know how to, you can create a
virtualenv with:

.. code-block:: sh

    $ virtualenv .venv

Then activate it to current tty / terminal session with:

.. code-block:: sh

    $ source .venv/bin/activate

Good! Now let's run this:

.. code-block:: sh

    $ pip install -e .

This has ``pip``, a python package manager install the python package
in the current directory. ``-e`` means ``--editable``, which means you can
adjust the code and the installed software will reflect the changes.

Test Runner
-----------

As you seen above, the ``vcspull`` command will now be available to you,
since you are in the virtual environment, your `PATH` environment was
updated to include a special version of ``python`` inside your ``.venv``
folder with its own packages.

.. code-block:: bash

    $ ./run-tests.py

You probably didn't see anything but tests scroll by.

If you found a problem or are trying to write a test, you can file an
`issue on github`_.

.. _test_specific_tests:

Test runner options
~~~~~~~~~~~~~~~~~~~

Testing specific TestSuites and TestCase.

.. code-block:: bash

    $ ./run-tests.py config

will test the ``testsuite.config`` :py:class:`unittest.TestSuite`.

.. code-block:: bash

    $ ./run-tests.py config.ImportExportTest

tests ``testsuite.config.ConfigFormatTest`` :py:class:`unittest.TestCase`.

individual tests:

.. code-block:: bash

    $ ./run-tests.py config.ConfigFormatTest

Multiple can be separated by spaces:

.. code-block:: bash

    $ ./run-tests.py repo_hg repo_git config.ConfigFormatTest
