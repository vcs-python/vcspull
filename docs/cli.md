(cli)=

# Command Line Interface

(completion)=

## Completion

```{note}
See the [click library's documentation on shell completion](https://click.palletsprojects.com/en/8.0.x/shell-completion/) for the most up to date way of connecting completion for vcspull.
```

In bash (`~/.bashrc`):

```{code-block} sh

eval "$(_VCSPULL_COMPLETE=bash_source vcspull)"

```

In zsh (`~/.zshrc`):

```{code-block} sh

eval "$(_VCSPULL_COMPLETE=zsh_source vscpull)"

```

(cli-shell)=

## Shell

```{eval-rst}
.. click:: vcspull.cli:cli
    :prog: vcspull
    :show-nested:
```
