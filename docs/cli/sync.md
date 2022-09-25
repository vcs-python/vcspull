(cli-sync)=

(vcspull-sync)=

# vcspull sync

## Error handling

### Repos not found in config

As of 1.13.x, if you enter a repo term (or terms) that aren't found throughout
your configurations, it will show a warning:

```console
$ vcspull sync non_existent_repo
No repo found in config(s) for "non_existent_repo"
```

```console
$ vcspull sync non_existent_repo existing_repo
No repo found in config(s) for "non_existent_repo"
```

```console
$ vcspull sync non_existent_repo existing_repo another_repo_not_in_config
No repo found in config(s) for "non_existent_repo"
No repo found in config(s) for "another_repo_not_in_config"
```

Since syncing terms are treated as a filter rather than a lookup, the message is
considered a warning, so will not exit even if `--exit-on-error` flag is used.

### Syncing

As of 1.13.x, vcspull will continue to the next repo if an error is encountered when syncing multiple repos.

To imitate the old behavior, the `--exit-on-error` / `-x` flag:

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
