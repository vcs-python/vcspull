(completion)=

# Completion

```{note}
See the [click library's documentation on shell completion](https://click.palletsprojects.com/en/8.0.x/shell-completion/).
```

:::{tab} bash

_~/.bashrc_:

```bash
eval "$(_VCSPULL_COMPLETE=bash_source vcspull)"
```

:::

:::{tab} zsh

_~/.zshrc`_:

```zsh
eval "$(_VCSPULL_COMPLETE=zsh_source vscpull)"
```

:::
