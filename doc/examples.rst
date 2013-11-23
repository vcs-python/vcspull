.. _examples:

========
Examples
========

Repo type and address is specified in `pip vcs url`_ format.

Remote git repostiries and SSH git
----------------------------------

Note, ``git+ssh`` repos such as ``git+git@github.com:tony/kaptan.git``. It
must be listed in remotes.

.. literalinclude:: ../examples/remotes.yaml
    :language: yaml

Christmas tree
--------------

config showing off every current feature and inline shortcut available.

.. literalinclude:: ../examples/christmas-tree.yaml
    :language: yaml

Code scholar
------------

This ``.pullv.yaml`` is used to checkout and sync multiple open source
configs.

YAML:

.. literalinclude:: ../examples/code-scholar.yaml
    :language: yaml
