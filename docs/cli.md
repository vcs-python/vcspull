(cli)=

# Command Line Interface

(completion)=

## Completion

In bash (`~/.bashrc`):

```{code-block} sh

eval "$(_VCSPULL_COMPLETE=source vcspull)"

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
