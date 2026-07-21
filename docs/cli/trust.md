(cli-trust)=

# vcspull trust

A `.vcspull.yaml` inside a repository you cloned is code somebody else wrote,
and it names paths on your disk. vcspull loads such a file silently as long as
every repository it declares lands inside that file's own directory. When one
does not, vcspull asks — and `vcspull trust` is how you answer ahead of time,
or take the answer back.

Most people never run this command. See {ref}`config-scopes` for when the
question comes up at all.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: trust
```

## Allowing a project

```vcspull-console
$ vcspull trust ~/work/api
trusted ~/work/api
```

Trust is recorded per *directory*, not per file, so a second config in the
same project does not ask again. The trade-off is real: a configuration
committed to that directory can now direct your checkouts anywhere on disk,
including after somebody else edits it.

## Reviewing and revoking

```vcspull-console
$ vcspull trust --show
~/work/api
```

```vcspull-console
$ vcspull trust --untrust ~/work/api
untrusted ~/work/api
```

The record lives in `$XDG_STATE_HOME/vcspull/trusted`, one directory per line.

## In automation

There is no prompt without a terminal — a sync in CI fails loudly rather than
blocking on a question nobody can see. To accept without asking, pass
`--trust-project` or export `VCSPULL_YES=1`.
