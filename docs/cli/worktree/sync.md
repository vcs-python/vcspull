(cli-worktree-sync)=

# vcspull worktree sync

Create or update {ref}`worktrees <cli-worktree>` to match configuration.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: worktree sync
```

## Basic usage

Sync all configured worktrees:

```console
$ vcspull worktree sync '*'
```

Missing worktrees fetch configured remotes and establish their initial target
with Git's linked-worktree operation. Creation holds the repository's ownership
lock through fetch, target selection, worktree creation, and lock setup. Existing
worktrees follow their configured `branch`, `tag`, `commit`, or native `rev`;
changing a tag or commit target moves the checkout to that resolved commit.
Branch updates are fast-forward only. A matching commit is not drift, even
when its branch or tag name differs. `detach: true` keeps a branch target
detached, and `remote` chooses the branch's fetch source.

Each worktree accepts the same `sync` policies as {ref}`cli-sync`:
`drift: keep` leaves an existing checkout untouched; `drift: warn` also logs
when its resolved target differs. The default `dirty: abort` blocks updates
with local changes. `dirty: preserve` retains native recovery material and
restores changes, including the Git index. Conflicts retain their recovery
token and make the operation fail.

`dirty: discard` requires explicit invocation consent, including clean or
missing checkouts:

```console
$ vcspull worktree sync --yes '*'
```

For {ref}`cli-sync` with `--include-worktrees`, the same `--yes` authorizes
configured discard. Worktree consent is checked before the main checkout
changes. Main and linked checkouts are synchronized serially.

Both commands print retained recovery identity after success or failure.
JSON and NDJSON include update/preservation states, ordered errors,
conflicts, and the exact token location required by libvcs recovery. Tokens
remain retained until explicitly released through libvcs; synchronization
does not automatically restore interrupted operations into their source.

## Timeouts and interruption

A requested worktree lock that fails reports an error even when the checkout
was created. Inspect `update_state` before retrying; failed creation can leave
refs or a partial checkout.

Each worktree has its own deadline, including native creation and update.
Set it with `--timeout` or `VCSPULL_SYNC_TIMEOUT_SECONDS`; the default is
10 seconds:

```console
$ vcspull worktree sync --timeout 60 '*'
```

Timeout or Ctrl-C stops the owned worker and its native process group before
the command continues or exits. A timeout skips the remaining worktrees for
that repository. Ctrl-C reports completed entries and retained recovery
material before exiting. An interrupted worker that did not report metadata
leaves `exists` and `is_dirty` unknown (`null` in JSON), not clean or missing.
See {ref}`cli-sync` for recovery inspection and process-group limits.

## Dry run

Preview local target metadata without fetching or changing checkouts. An
unavailable target produces an error plan; execution may resolve it after
fetching:

```console
$ vcspull worktree sync --dry-run '*'
```

## Filtering

Sync worktrees for specific repositories:

```console
$ vcspull worktree sync 'myproject'
```

Use {mod}`fnmatch`-style patterns:

```console
$ vcspull worktree sync 'django*'
```

## JSON output

```console
$ vcspull worktree sync --json '*'
```

## NDJSON output

```console
$ vcspull worktree sync --ndjson '*'
```
