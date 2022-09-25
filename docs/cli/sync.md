(cli-sync)=

(vcspull-sync)=

# vcspull sync

## Error handling

As of 1.13.x, vcspull will continue to the next repo if an error is encountered when syncing multiple repos.

To imitate the old behavior, use `--exit-on-error` / `-x`:

```console
$ vcspull sync --exit-on-error grako django
```

Print traceback for errored repos:

```console
$ vcspull --log-level DEBUG sync --exit-on-error grako django
```

```{eval-rst}
.. click:: vcspull.cli.sync:sync
    :prog: vcspull sync
    :commands: sync
    :nested: full
```
