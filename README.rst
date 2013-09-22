`analects` checkout, update many open source applications for study,
compilation and development.

.. image:: https://travis-ci.org/tony/analects.png?branch=master
   :target: https://travis-ci.org/tony/analects

use YAML, JSON, INI or python dict + pip compatible repository URL's to
checkout + grab the latest source to projects.

Not ready for public use.

===========     ==========================================================
Travis          http://travis-ci.org/tony/analects
Docs            http://analects.rtfd.org
API             http://analects.readthedocs.org/en/latest/api.html
Issues          https://github.com/tony/analects/issues
Source          https://github.com/tony/analects
License         `BSD`_.
git repo        .. code-block:: bash

                    $ git clone https://github.com/tony/analects.git
install dev     .. code-block:: bash

                    $ git clone https://github.com/tony/analects.git analects
                    $ cd ./analects
                    $ virtualenv .env
                    $ source .env/bin/activate
                    $ pip install -e .
tests           .. code-block:: bash

                    $ python ./run_tests.py
===========     ==========================================================

.. _BSD: http://opensource.org/licenses/BSD-3-Clause
