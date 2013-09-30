.. pullv documentation master file, created by
   sphinx-quickstart on Mon Sep 23 12:38:49 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=====
pullv
=====

source code management.


internal workflow
-----------------

1. accept YAML, JSON, INI configs with kaptan
2. expand user config info full dict object (todo: specify full dict form
   in tests
3. determine VCS scheme and create a new object of  metaclass Repo +
   (VCS Class). object will be initialized with the full dict form object.
   example coming soon. candidates for inheriting vcs backend are:
   a. readthedocs https://github.com/rtfd/readthedocs.org/tree/master/readthedocs/vcs_support
   b. saltstack - salt/modules/git.py salt/states/git.py
   c. pip's

Contents:

.. toctree::
   :maxdepth: 2

.. _api:

===
API
===

.. module:: pullv


.. autoclass:: Repo
   :members:
   :inherited-members:
   :show-inheritance:

.. autoclass:: GitRepo
   :members:
   :inherited-members:
   :show-inheritance:

.. autoclass:: MercurialRepo
   :members:
   :inherited-members:
   :show-inheritance:

.. automethod:: expand_config

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

