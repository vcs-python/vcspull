(cli-config)=

# vcspull config

vcspull rarely reads just one file. `vcspull config ls` answers the question
that follows from that: standing here, which files are in effect, and which
one wins? Reach for it when `vcspull sync` picks up a repository you did not
expect, or refuses one you did.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: config
```

## Reading the report

```vcspull-console
$ vcspull config ls
user     ~/.vcspull.yaml            2 repos (1 overridden)
project  ~/work/proj/.vcspull.yaml  1 repo

2 repositories in effect.
```

Rows run weakest to strongest, the same order
{ref}`the scopes resolve in <config-scopes>`. The count is what each file
declares; "overridden" is how many of those a nearer file replaced. The final
line is the total you will actually sync.

## Diagnosing a refusal

A project config that would check a repository out beyond its own directory
needs {ref}`trust <cli-trust>` before it loads. `config ls` shows it rather
than dropping it, and never prompts — this is the command you run *because*
something else refused:

```vcspull-output
user     ~/.vcspull.yaml                     2 repos
project  ~/work/proj/.vcspull.yaml           1 repo
project  ~/work/proj/escaping/.vcspull.yaml  1 repo (untrusted)

3 repositories in effect.
Untrusted configs are not loaded. Allow one with 'vcspull trust DIR'.
```

## Ignoring the project scope

```console
$ vcspull config ls --no-project
```

Both `vcspull --no-project config ls` and `vcspull config ls --no-project`
work.
