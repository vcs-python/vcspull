.. _examples:

========
Examples
========

Repo type and address is specified in `pip vcs url`_ format.

.. _git_remote_ssh_git:

Remote git repositories and SSH git
-----------------------------------

Note, ``git+ssh`` repos such as ``git+git@github.com:tony/kaptan.git``.
Must use the format ``git+ssh://git@github.com/tony/kaptan.git``

.. literalinclude:: ../examples/remotes.yaml
    :language: yaml

Christmas tree
--------------

config showing off every current feature and inline shortcut available.

.. literalinclude:: ../examples/christmas-tree.yaml
    :language: yaml

Code scholar
------------

This ``.vcspull.yaml`` is used to checkout and sync multiple open source
configs.

YAML:

.. literalinclude:: ../examples/code-scholar.yaml
    :language: yaml

.. _pip vcs url: https://pip.pypa.io/en/latest/reference/pip_install/#vcs-support
