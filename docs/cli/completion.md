(completion)=

(completions)=

(cli-completions)=

# Completions

## vcspull 1.15+ (experimental)

```{note}
See the [shtab library's documentation on shell completion](https://docs.iterative.ai/shtab/use/#cli-usage) for the most up to date way of connecting completion for vcspull.
```

Provisional support for completions in vcspull 1.17+ are powered by [shtab](https://docs.iterative.ai/shtab/). This must be **installed separately**, as it's **not currently bundled with vcspull**.

```console
$ pip install shtab --user
```

:::{tab} bash

```bash
shtab --shell=bash -u vcspull.cli.create_parser \
  | sudo tee "$BASH_COMPLETION_COMPAT_DIR"/VCSPULL
```

:::

:::{tab} zsh

```zsh
shtab --shell=zsh -u vcspull.cli.create_parser \
  | sudo tee /usr/local/share/zsh/site-functions/_VCSPULL
```

:::

:::{tab} tcsh

```zsh
shtab --shell=tcsh -u vcspull.cli.create_parser \
  | sudo tee /etc/profile.d/VCSPULL.completion.csh
```

:::

## vcspull 0.9 to 1.14

```{note}
See the [click library's documentation on shell completion](https://click.palletsprojects.com/en/8.0.x/shell-completion/) for the most up to date way of connecting completion for vcspull.
```

vcspull 0.1 to 1.14 use [click](https://click.palletsprojects.com)'s completion:

:::{tab} bash

_~/.bashrc_:

```bash

eval "$(_VCSPULL_COMPLETE=bash_source vcspull)"

```

:::

:::{tab} zsh

_~/.zshrc_:

```zsh

eval "$(_VCSPULL_COMPLETE=zsh_source vcspull)"

```

:::
