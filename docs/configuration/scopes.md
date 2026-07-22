(config-scopes)=

# Configuration scopes

vcspull reads more than one configuration file. Where each file sits decides
how much it can say: a file in `/etc` speaks for the machine, a file in your
home directory speaks for you, and a `.vcspull.yaml` inside a project speaks
for that project. vcspull calls these *scopes*, resolves them in a fixed
order, and unions them into one set of repositories.

If you keep a single `~/.vcspull.yaml`, that is the whole story and you can
stop reading. Nothing below changes what one file does.

## The search order

Weakest to strongest. Every scope that exists contributes, and a repository
named by more than one scope comes from the strongest.

| Scope | Where | Trust |
| --- | --- | --- |
| system | `/etc/vcspull/*.{yaml,yml,json}` | automatic |
| user directory | `$VCSPULL_CONFIGDIR`, else `$XDG_CONFIG_HOME/vcspull/`, else `~/.config/vcspull/`, else `~/.vcspull/` — the first that exists | automatic |
| user dotfile | `~/.vcspull.yaml` or `~/.vcspull.json` | automatic |
| project | `.vcspull.{yaml,yml,json}` in each ancestor of your working directory, outermost first | gated |

Passing `-f/--file` replaces that entire stack with the one file you name, so
existing scripts and CI jobs behave exactly as they always have.

To see what applies where you are standing:

```vcspull-console
$ vcspull config ls
user     ~/.vcspull.yaml            2 repos (1 overridden)
project  ~/work/proj/.vcspull.yaml  1 repo

2 repositories in effect.
```

Each row is a file in the stack, weakest first, with the count it declares.
"overridden" is how many of those a nearer file replaced, so the last line is
what you will actually sync.

## The upward walk

The project scope walks up from your working directory, so
`~/work/.vcspull.yaml` covers everything under `~/work` — this is what makes
a workspace-of-workspaces manifest usable, and why `vcspull sync` no longer
does nothing from a subdirectory.

The walk stops at `$HOME` or the filesystem root, whichever comes first. A
`.vcspull.yaml` sitting in `/home` or `/` is far likelier to be an accident
than an intent, and the system scope already covers the machine-wide case.
Override the stop set with `VCSPULL_CEILING_PATHS`, a `:`-separated list of
directories.

To ignore the project scope entirely for one command:

```console
$ vcspull --no-project sync --all
```

Export `VCSPULL_NO_PROJECT=1` to make that the default for a shell.

## How the scopes merge

The identity of a repository is its destination on disk — the workspace root
plus the repository name. Two files that name different destinations union;
a project config adds repositories to your user set.

When two files name the same destination, the stronger scope replaces the
entry *whole*. The URL, the VCS, and everything under `options:` come from
the winner. That is deliberate rather than convenient: a project config that
repoints `flask` at a fork must not silently inherit the `rev:` pin from your
user config and check out a revision that does not exist in the fork.

vcspull reports the override only when the two entries actually disagree on
URL or VCS:

```vcspull-output
~/work/proj/.vcspull.yaml overrides ~/.vcspull.yaml for '~/work/proj/vendor/flask' (url or vcs differs)
```

Identical entries across a user and a project file are the common, harmless
case, and stay silent. If every sync warned about them, you would learn to
ignore the channel.

Replacing the whole entry costs you granularity: a project file cannot tweak
one field of an inherited entry. To change anything about a repository your
user config already names, the project file restates that entry in full.

## Trusting a project config

A configuration is a set of destination paths, so a `.vcspull.yaml` inside a
repository you just cloned could name `~/.ssh/` as a workspace root and have
`vcspull sync` clone into it. The project scope is the only scope that can
arrive with untrusted code, so it is the only one vcspull gates.

The gate is containment: a project config is *contained* when every
repository it declares would be checked out at or beneath the directory
holding that config. The check runs over destinations, not over the workspace
roots you wrote — a repository entry can override its destination with
`path:` and never consult its workspace root at all — and it expands `~`,
environment variables, and symlinks on both sides first. A config targeting
`./vendor/` or a sibling checkout is contained, and loads silently. This is
the overwhelming majority of them, which is what keeps the gate from becoming
a nag.

A config that escapes its own directory asks once:

```vcspull-output
! ~/work/proj/escaping/.vcspull.yaml would check repositories out outside its directory:
    ~/.ssh/evil
  Trust this config? [y/N/always]
```

Answering `always` records the project *directory*, not the file, so adding a
second config to a project you already trust does not ask again. The record
lives in `$XDG_STATE_HOME/vcspull/trusted`.

Without a terminal there is no prompt — vcspull fails with the whole remedy in
one line, because a sync in CI must never block on a question nobody can see:

```vcspull-output
vcspull: ~/work/proj/escaping/.vcspull.yaml would check repositories out outside its directory (~/.ssh/evil) and there is no terminal to confirm on. Run 'vcspull trust ~/work/proj/escaping' to allow it, pass --trust-project, or use --no-project to skip project configs.
```

When you do want to accept non-interactively, pass `--trust-project` or export
`VCSPULL_YES=1`. That switch is deliberately its own word rather than a
general `--yes`: an unrelated confirmation flag must never become a standing
grant to write outside a directory.

Trusting a directory is not free. It means a configuration committed to that
directory can direct your checkouts anywhere on disk, including next time,
when somebody else has edited it. Trust the project, not just the file you
read.

The same check guards the commands that write: {ref}`add <cli-add>`,
{ref}`discover <cli-discover>`, {ref}`fmt <cli-fmt>`, and
{ref}`migrate <cli-migrate>`. A repository that ships a config redirecting
your writes deserves the same question as one redirecting your clones. Naming
a file with `-f/--file` is consent and skips the gate, the same way `--file`
skips the scope stack on the read side.

Manage the record directly with {ref}`vcspull trust <cli-trust>`:

```console
$ vcspull trust ~/work/api
```

```console
$ vcspull trust --untrust ~/work/api
```

```console
$ vcspull trust --show
```

## For the Python reader

Everything above is one function. {func}`vcspull.config.load_scoped_configs`
resolves the stack, merges it, and runs the trust gate, returning the same
list of entries the CLI syncs:

```python
from vcspull.config import load_scoped_configs

repos = load_scoped_configs()
```

Pass `config_path` to replace the stack the way `--file` does,
`include_project=False` for `--no-project`, or `cwd` to resolve as if you were
standing somewhere else.

Two lower-level pieces are worth knowing if you are building on this.
{func}`vcspull.config.repo_destinations` answers "where would this check
out?" for a list of entries, honouring `path:` overrides — it is what the
containment check reads. {func}`vcspull.config.ensure_config_trusted` is the
gate the write commands call, and returns `False` when the user declines.
