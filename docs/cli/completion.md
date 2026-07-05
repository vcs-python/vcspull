(completion)=

(completions)=

(cli-completions)=

# Completions

Shell completions let your shell suggest vcspull's subcommands and flags as
you type — press tab and the rest is filled in. vcspull 1.15+ generates the
completion scripts with [shtab](https://docs.iterative.ai/shtab/); support
is provisional, and shtab is **installed separately**.

## vcspull 1.15+ (experimental)

```{note}
See the [shtab library's documentation on shell completion](https://docs.iterative.ai/shtab/use/#cli-usage) for the most up to date way of connecting completion for vcspull.
```

Install shtab first — it is **not bundled with vcspull**:

```console
$ pip install shtab --user
```

Or using [uv](https://docs.astral.sh/uv/):

```console
$ uv tool install shtab
```

For one-time use without installation:

```console
$ uvx shtab
```

Then generate and install the completion script for your shell:

:::{tab} bash

```console
$ shtab \
    --shell=bash \
    --error-unimportable \
    vcspull.cli.create_parser \
    | sudo tee "$BASH_COMPLETION_COMPAT_DIR"/VCSPULL
```

:::

:::{tab} zsh

```console
$ shtab \
    --shell=zsh \
    --error-unimportable \
    vcspull.cli.create_parser \
    | sudo tee /usr/local/share/zsh/site-functions/_VCSPULL
```

:::

:::{tab} tcsh

```console
$ shtab \
    --shell=tcsh \
    --error-unimportable \
    vcspull.cli.create_parser \
    | sudo tee /etc/profile.d/VCSPULL.completion.csh
```

:::

## vcspull 0.9 to 1.14

```{note}
See the [click library's documentation on shell completion](https://click.palletsprojects.com/en/8.0.x/shell-completion/) for the most up to date way of connecting completion for vcspull.
```

vcspull 0.9 to 1.14 use [click](https://click.palletsprojects.com)'s completion:

:::{tab} bash

_~/.bashrc_:

```console
$ printf '%s\n' 'eval "$(_VCSPULL_COMPLETE=bash_source vcspull)"' >> ~/.bashrc
```

:::

:::{tab} zsh

_~/.zshrc_:

```console
$ printf '%s\n' 'eval "$(_VCSPULL_COMPLETE=zsh_source vcspull)"' >> ~/.zshrc
```

:::
