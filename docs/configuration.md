(configuration)=

# Configuration

Repo type and address is specified in [pip vcs url][pip vcs url] format.

[pip vcs url]: https://pip.pypa.io/en/latest/reference/pip_install/#vcs-support

(git-remote-ssh-git)=

## SSH Git URLs

For git remotes using SSH authorization such as `git+git@github.com:tony/kaptan.git` use `git+ssh`:

```sh
git+ssh://git@github.com/tony/kaptan.git
```

## Examples

````{tab} Simple

_~/.vcspull.yaml_:

```{literalinclude} ../examples/remotes.yaml
:language: yaml

```

Then type:

```sh
vcspull kaptan
```

````

````{tab} Complex

**Christmas tree**

config showing off every current feature and inline shortcut available.

```{literalinclude} ../examples/christmas-tree.yaml
:language: yaml

```

````

````{tab} Open Source Student

**Code scholar**

This `.vcspull.yaml` is used to checkout and sync multiple open source
configs.

YAML:

```{literalinclude} ../examples/code-scholar.yaml
:language: yaml

```

````
